"""Glue Data Catalog extractor."""

from __future__ import annotations

from typing import Any

import src.common.aws as aws
from src.doc_builder.extractors.base import ColumnDoc, TableDoc


class GlueExtractor:
    """Reads table + column metadata from the Glue catalog."""

    def __init__(self, client: Any | None = None) -> None:
        self.client = client or aws.glue()

    def list_tables(self, database: str) -> list[str]:
        names: list[str] = []
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"DatabaseName": database}
            if token:
                kwargs["NextToken"] = token
            response = self.client.get_tables(**kwargs)
            for table in response.get("TableList", []):
                name = table.get("Name")
                if name:
                    names.append(name)
            token = response.get("NextToken")
            if token is None:
                break
        return sorted(names)

    def get_table(self, database: str, name: str) -> TableDoc:
        response = self.client.get_table(DatabaseName=database, Name=name)
        table = response["Table"]

        columns: list[ColumnDoc] = []
        partition_names: list[str] = []
        for column in table.get("StorageDescriptor", {}).get("Columns", []):
            columns.append(
                ColumnDoc(
                    name=column.get("Name", ""),
                    data_type=column.get("Type", ""),
                    comment=column.get("Comment", "") or "",
                )
            )
        for column in table.get("PartitionKeys", []):
            partition_names.append(column.get("Name", ""))
            columns.append(
                ColumnDoc(
                    name=column.get("Name", ""),
                    data_type=column.get("Type", ""),
                    comment=column.get("Comment", "") or "",
                    is_partition=True,
                )
            )

        parameters = table.get("Parameters", {})
        row_count = None
        if parameters.get("CrawlerSchemaSerializerVersion") is not None:  # real table
            raw = parameters.get("recordCount")
            if raw and raw.isdigit():
                row_count = int(raw)

        return TableDoc(
            database=database,
            name=name,
            description=parameters.get("comment", "") or "",
            columns=tuple(columns),
            partition_keys=tuple(partition_names),
            row_count=row_count,
            location=table.get("StorageDescriptor", {}).get("Location", ""),
        )
