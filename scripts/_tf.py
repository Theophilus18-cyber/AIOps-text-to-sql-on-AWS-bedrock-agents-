"""Small helper for reading Terraform outputs from scripts.

Scripts that need deployed resource IDs shell out to ``terraform output``
rather than hardcoding ARNs, so no account ID or resource name ever appears in
source.  The working directory for each env is ``terraform/envs/<env>``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def terraform_output(env: str, name: str, profile: str | None = None) -> str:
    """Return a string Terraform output for ``env`` (e.g. ``lake_bucket``).

    ``terraform`` reads credentials through its provider's chain, which honours
    ``AWS_PROFILE``. Callers that resolve their own profile (rather than relying
    on an exported ``AWS_PROFILE``) pass it here so the subprocess uses the same
    account as the rest of the script.
    """
    chdir = ROOT / "terraform" / "envs" / env
    subprocess_env = os.environ.copy()
    if profile:
        subprocess_env["AWS_PROFILE"] = profile
        subprocess_env["AWS_DEFAULT_PROFILE"] = profile
    result = subprocess.run(
        ["terraform", "output", "-json", name],
        cwd=chdir,
        env=subprocess_env,
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
