"""Local web console for asking the deployed orchestrator questions.

Usage: ``python scripts/ask_server.py [--env dev] [--port 8000] [--profile banking]``

Starts a tiny local server on http://127.0.0.1:<port>. Type a question and the
orchestrator's answer is rendered as Markdown in the browser, so you no longer
have to read it through escaped CloudWatch JSON. The request invokes the same
Lambda the smoke test uses, so the full tool loop (get_schema_context -> run_sql
-> Athena) runs exactly as it does in production.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import boto3

from _tf import terraform_output

_UI = Path(__file__).with_name("ask_ui.html").read_text(encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default="dev", help="Terraform environment")
    parser.add_argument("--port", type=int, default=8000, help="Local port to serve on")
    parser.add_argument("--profile", default="banking", help="AWS CLI profile for Lambda access")
    return parser.parse_args()


class Handler(BaseHTTPRequestHandler):
    function_name = ""
    env = "dev"
    region = "us-east-1"
    client = None
    ready = threading.Event()

    def do_GET(self) -> None:
        if self.path not in ("/", "/index.html"):
            self.send_response(404)
            self.end_headers()
            return
        if not self._await_name():
            return
        body = (
            _UI.replace("__FN__", self.function_name)
            .replace("__ENV__", self.env)
            .replace("__REGION__", self.region)
            .encode("utf-8")
        )
        self._html(200, body)

    def do_POST(self) -> None:
        if self.path != "/ask":
            self.send_response(404)
            self.end_headers()
            return
        if not self._await_name():
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            req = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            req = {}
        question = (req.get("question") or "").strip()
        if not question:
            self._json(400, {"error": "question is required."})
            return
        history = req.get("history") if isinstance(req.get("history"), list) else []
        try:
            payload = {"question": question}
            if history:
                payload["history"] = history
            response = self.client.invoke(
                FunctionName=self.function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )
            payload = json.loads(response["Payload"].read().decode("utf-8"))
            if "FunctionError" in response:
                self._json(200, {"error": json.dumps(payload)})
                return
            answer = payload.get("answer") or payload.get("error") or json.dumps(payload)
            self._json(200, {"answer": answer})
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            self._json(500, {"error": str(exc)})

    def _await_name(self) -> bool:
        """Block until the background resolver finishes, or fail with an error."""
        if self.ready.wait(timeout=60) and self.function_name:
            return True
        self._json(500, {"error": "could not resolve the orchestrator function name (check `terraform output`)."})
        return False

    def _html(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[ask] " + fmt % args + "\n")


def _find_orchestrator(client, env: str) -> str:
    """Resolve the orchestrator function name from the Lambda API.

    This mirrors the Terraform name ``<project>-<env>-orchestrator`` without
    hardcoding an account ID, region or ARN, and without reading state from S3.
    """
    suffix = f"-{env}-orchestrator"
    for page in client.get_paginator("list_functions").paginate():
        for fn in page.get("Functions", []):
            name = fn.get("FunctionName", "")
            if name.endswith(suffix):
                return name
    raise RuntimeError(f"no Lambda function ending in {suffix!r}")


def main() -> None:
    args = _parse_args()
    session = boto3.Session(profile_name=args.profile)
    Handler.env = args.env
    Handler.region = session.region_name or "us-east-1"
    Handler.client = session.client("lambda")

    # Resolve the function name in the background. `terraform output` takes a
    # few seconds on Windows, and running it before binding the socket is what
    # made the browser report ERR_CONNECTION_REFUSED during startup. Binding
    # first and resolving in a thread means the port is open immediately.
    #
    # `terraform output` reads the backend state out of S3, so when that is
    # unavailable the server falls back to a Lambda API lookup (same
    # deterministic name, no S3 dependency).
    def _resolve() -> None:
        try:
            Handler.function_name = terraform_output(args.env, "orchestrator_function_name", profile=args.profile)
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"[ask] terraform output failed ({exc}); trying Lambda lookup\n")
            try:
                Handler.function_name = _find_orchestrator(Handler.client, args.env)
            except Exception as fallback:  # noqa: BLE001
                sys.stderr.write(f"[ask] failed to resolve function name: {fallback}\n")
        finally:
            Handler.ready.set()

    threading.Thread(target=_resolve, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Serving http://127.0.0.1:{args.port}  (env={args.env})", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
