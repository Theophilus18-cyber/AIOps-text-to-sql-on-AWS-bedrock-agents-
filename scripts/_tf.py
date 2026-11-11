"""Small helper for reading Terraform outputs from scripts.

Scripts that need deployed resource IDs shell out to ``terraform output``
rather than hardcoding ARNs, so no account ID or resource name ever appears in
source.  The working directory for each env is ``terraform/envs/<env>``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def terraform_output(env: str, name: str) -> str:
    """Return a string Terraform output for ``env`` (e.g. ``lake_bucket``)."""
    chdir = ROOT / "terraform" / "envs" / env
    result = subprocess.run(
        ["terraform", "output", "-json", name],
        cwd=chdir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"terraform output '{name}' failed: {result.stderr.strip()}")
    value = json.loads(result.stdout)
    if not isinstance(value, str):
        raise RuntimeError(f"terraform output '{name}' is not a string: {value!r}")
    return value
