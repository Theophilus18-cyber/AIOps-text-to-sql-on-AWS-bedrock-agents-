"""Tests for the schema-doc Markdown renderer."""

from __future__ import annotations

from src.doc_builder.extractors.base import ColumnDoc, TableDoc
from src.doc_builder.renderer import render_table_doc


def _table() -> TableDoc:
    return TableDoc(
        database="text2sql_dev_lake",
        name="credit_card_transactions",
        description="One row per transaction.",
        columns=(
            ColumnDoc("amt", "double", "amount in USD"),
            ColumnDoc("is_fraud", "int", "0 or 1"),
            ColumnDoc("year", "int", "partition", is_partition=True),
        ),
        partition_keys=("year",),
        row_count=1296675,
        location="s3://lake/raw/",
    )


def test_renders_header_and_columns() -> None:
    doc = render_table_doc(_table())
    assert "# Table: text2sql_dev_lake.credit_card_transactions" in doc
    assert "| amt | double |" in doc
    assert "amount in USD" in doc
    assert "Approximate row count: 1,296,675" in doc


def test_renders_glossary_code_values_and_examples() -> None:
    glossary = {
        "credit_card_transactions": {
            "description": "Business description.",
            "code_values": {"is_fraud": "0 = no, 1 = yes"},
            "example_questions": [
                {"question": "Total spend?", "answer": "Sum of amt.", "sql": "SELECT sum(amt) ..."}
            ],
        }
    }
    doc = render_table_doc(_table(), glossary)
    assert "Business description." in doc
    assert "`is_fraud`: 0 = no, 1 = yes" in doc
    assert "**Q:** Total spend?" in doc
    assert "```sql" in doc


def test_pipe_in_description_is_escaped() -> None:
    table = TableDoc(
        database="db",
        name="t",
        columns=(ColumnDoc("c", "string", "a|b"),),
    )
    doc = render_table_doc(table)
    assert "a\\|b" in doc
