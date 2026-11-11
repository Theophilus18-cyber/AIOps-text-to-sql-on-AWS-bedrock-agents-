"""Placeholder extractor for an enterprise/Oracle metadata catalog.

Out of scope for this project.  It exists so the extractor seam is explicit:
swap the Glue catalog for an Oracle metadata store by implementing the same
``TableDoc`` contract here and changing the extractor used by ``handler.py``.
"""

from __future__ import annotations

from src.doc_builder.extractors.base import TableDoc


class OracleExtractor:
    def list_tables(self, database: str) -> list[str]:
        raise NotImplementedError("Oracle metadata extractor is out of scope.")

    def get_table(self, database: str, name: str) -> TableDoc:
        raise NotImplementedError("Oracle metadata extractor is out of scope.")
