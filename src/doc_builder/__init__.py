"""Doc-builder Lambda: renders Glue table metadata into Bedrock KB docs.

The refresh pipeline runs the Glue crawler, invokes this Lambda, which reads
table metadata from the Glue catalog, merges it with the human-authored
glossary, writes one Markdown document per table under
``schema-docs/approved/``, and starts a Knowledge Base ingestion job.
"""

from .handler import lambda_handler

__all__ = ["lambda_handler"]
