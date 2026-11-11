"""Offline evaluation runner for the text-to-SQL orchestrator.

Invokes the deployed orchestrator once per golden case, then checks:

* ``expected_sql`` / ``expected_sql_extra`` — those SQL fragments appear in the
  SQL the agent ran (case-insensitive, whitespace-normalised).
* ``refusal`` — the agent must decline rather than answer with data.

The runner never calls ``terraform apply`` and reads no data; it only exercises
the agent API that was already deployed.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

try:
    import boto3
except ImportError:  # pragma: no cover - dev-only dependency
    boto3 = None


@dataclass(frozen=True)
class EvaluationResult:
    passed: int
    failed: int
    failures: tuple[dict[str, str], ...] = field(default_factory=tuple)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _load_golden(path: Path) -> list[dict[str, object]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or []


def _invoke(function_name: str, question: str) -> str:
    if boto3 is None:
        raise RuntimeError("boto3 is required for evaluation (pip install boto3).")
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps({"question": question}),
    )
    payload = json.loads(response["Payload"].read().decode("utf-8"))
    if "FunctionError" in response:
        raise RuntimeError(f"orchestrator error: {payload}")
    return payload.get("answer") or payload.get("error") or json.dumps(payload)


def evaluate(function_name: str, golden_path: Path) -> EvaluationResult:
    cases = _load_golden(golden_path)
    passed = 0
    failures: list[dict[str, str]] = []

    for case in cases:
        case_id = str(case["id"])
        question = str(case["question"])
        try:
            response = _invoke(function_name, question)
        except Exception as exc:
            failures.append({"id": case_id, "reason": f"invoke error: {exc}"})
            continue

        normalised = _normalise(response)

        if case.get("refusal"):
            if _looks_like_refusal(response):
                passed += 1
            else:
                failures.append({"id": case_id, "reason": "expected refusal, got an answer"})
            continue

        expected = _normalise(str(case.get("expected_sql", "")))
        extra = _normalise(str(case.get("expected_sql_extra", "")))
        if expected and expected not in normalised:
            failures.append({"id": case_id, "reason": f"missing SQL fragment: {expected}"})
            continue
        if extra and extra not in normalised:
            failures.append({"id": case_id, "reason": f"missing SQL fragment: {extra}"})
            continue
        passed += 1

    return EvaluationResult(passed=passed, failed=len(failures), failures=tuple(failures))


_REFUSAL_MARKERS = (
    "cannot",
    "can't",
    "i can't",
    "not able",
    "decline",
    "off-topic",
    "off topic",
    "not related",
    "pii",
    "personally identifiable",
    "won't",
    "cannot help",
)


def _looks_like_refusal(response: str) -> bool:
    lowered = response.lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


def main() -> int:
    """CLI entry point: reads the orchestrator function name, prints a JSON report."""
    function_name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not function_name:
        print("usage: python -m src.evaluation.runner FUNCTION_NAME", file=sys.stderr)
        return 2

    golden = Path(__file__).parent / "golden_set.yaml"
    result = evaluate(function_name, golden)

    report = {
        "passed": result.passed,
        "failed": result.failed,
        "failures": list(result.failures),
    }
    print(json.dumps(report, indent=2))
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
