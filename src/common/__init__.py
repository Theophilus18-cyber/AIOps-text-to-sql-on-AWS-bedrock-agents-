"""Shared helpers used by both Lambda packages and local scripts.

This package must stay free of any dependency that is not part of the Python
standard library, because it is vendored into both Lambda zips.  The AWS SDK
(boto3) is imported lazily by the callers that need it, never here.
"""

from . import config

__all__ = ["config"]
