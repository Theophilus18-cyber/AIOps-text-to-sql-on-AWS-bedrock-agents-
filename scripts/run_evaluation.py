"""Run the offline evaluation set against the deployed orchestrator.

Reads the orchestrator function name from Terraform outputs and delegates to
the evaluation runner in ``src/evaluation``.

Usage: ``python scripts/run_evaluation.py --env dev``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _tf import terraform_output

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.evaluation.runner import evaluate  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default="dev", help="Terraform environment")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    function_name = terraform_output(args.env, "orchestrator_function_name")
    golden = ROOT / "src" / "evaluation" / "golden_set.yaml"

    result = evaluate(function_name, golden)
    print(f"passed: {result.passed}")
    print(f"failed: {result.failed}")
    for failure in result.failures:
        print(f"  - {failure['id']}: {failure['reason']}")

    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
