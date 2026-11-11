"""Metadata extractors.

The extractor is the seam between the Glue catalog (the operational source of
truth in scope) and any future external catalog such as an Oracle/enterprise
metadata store.  Each extractor produces the same neutral ``TableDoc`` model.
"""

from .base import ColumnDoc, TableDoc
from .glue import GlueExtractor

__all__ = ["ColumnDoc", "GlueExtractor", "TableDoc"]
