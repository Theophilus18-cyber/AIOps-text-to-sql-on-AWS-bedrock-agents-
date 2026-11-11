"""Neutral metadata model shared by every extractor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ColumnDoc:
    name: str
    data_type: str
    comment: str = ""
    is_partition: bool = False


@dataclass(frozen=True)
class TableDoc:
    database: str
    name: str
    description: str = ""
    columns: tuple[ColumnDoc, ...] = field(default_factory=tuple)
    partition_keys: tuple[str, ...] = field(default_factory=tuple)
    row_count: int | None = None
    location: str = ""

    @property
    def qualified_name(self) -> str:
        return f"{self.database}.{self.name}"


class Extractor(Protocol):
    """Produces a neutral table document from a catalog."""

    def list_tables(self, database: str) -> list[str]: ...

    def get_table(self, database: str, name: str) -> TableDoc: ...
