"""Renders TableDoc + glossary entries into the Markdown ingested by the KB.

The rendered document is written to S3 *whole* (the KB data source uses
``chunking_strategy = NONE``) so each document is retrieved as one unit and
the agent sees the complete table description in a single retrieval result.
"""

from __future__ import annotations

from typing import Any

from src.doc_builder.extractors.base import TableDoc


def render_table_doc(
    table: TableDoc,
    glossary: dict[str, Any] | None = None,
) -> str:
    """Render one table as Markdown.

    ``glossary`` is the decoded glossary YAML keyed by table name; it supplies
    human-authored business definitions and example Q&A that the crawler alone
    cannot produce.
    """
    glossary = glossary or {}
    entry = glossary.get(table.name) or glossary.get(table.qualified_name) or {}

    lines: list[str] = []
    lines.append(f"# Table: {table.qualified_name}")
    lines.append("")
    lines.append(entry.get("description") or table.description or "No description.")
    lines.append("")

    # Business context section (human-authored, higher value to the agent).
    for section in ("business_meaning", "usage_notes"):
        text = entry.get(section)
        if text:
            lines.append(f"## {section.replace('_', ' ').title()}")
            lines.append("")
            lines.append(text)
            lines.append("")

    if entry.get("metrics"):
        lines.append("## Common Metrics")
        lines.append("")
        for metric in entry["metrics"]:
            lines.append(f"- {metric}")
        lines.append("")

    lines.append("## Columns")
    lines.append("")
    lines.append("| Column | Type | Partition | Description |")
    lines.append("| --- | --- | --- | --- |")
    for column in table.columns:
        description = (
            entry.get("columns", {}).get(column.name, {}).get("description", column.comment) or ""
        )
        lines.append(
            f"| {_cell(column.name)} | {_cell(column.data_type)} "
            f"| {'yes' if column.is_partition else ''} | {_cell(description)} |"
        )
    lines.append("")

    code_values = entry.get("code_values")
    if code_values:
        lines.append("## Code Values")
        lines.append("")
        for column_name, values in code_values.items():
            lines.append(f"- `{column_name}`: {values}")
        lines.append("")

    if entry.get("join_keys"):
        lines.append("## Join Keys")
        lines.append("")
        for key in entry["join_keys"]:
            lines.append(f"- {key}")
        lines.append("")

    examples = entry.get("example_questions")
    if examples:
        lines.append("## Example Questions & Answers")
        lines.append("")
        for example in examples:
            question = example.get("question", "")
            answer = example.get("answer", "")
            sql = example.get("sql", "")
            lines.append(f"**Q:** {question}")
            lines.append("")
            if answer:
                lines.append(f"**A:** {answer}")
                lines.append("")
            if sql:
                lines.append("```sql")
                lines.append(sql)
                lines.append("```")
                lines.append("")
    else:
        lines.append("## Example Questions")
        lines.append("")
        lines.append("(none provided in the glossary)")
        lines.append("")

    if table.row_count is not None:
        lines.append(f"Approximate row count: {table.row_count:,}")
    if table.location:
        lines.append(f"Location: `{table.location}`")

    return "\n".join(lines).strip() + "\n"


def _cell(value: str) -> str:
    """Escape Markdown table cells."""
    return value.replace("|", "\\|").replace("\n", " ").strip()
