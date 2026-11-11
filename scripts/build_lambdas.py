"""Build the two Lambda deployment packages into ``dist/``.

Each zip contains:

* the ``src`` package (``src/common`` plus the lambda's own package),
* a top-level ``handler.py`` shim that re-exports ``lambda_handler`` so the
  Terraform ``handler = "handler.lambda_handler"`` reference resolves,
* any third-party dependencies installed from the package's ``requirements.txt``.

Dependencies are installed with ``--platform manylinux2014_x86_64`` and
``--only-binary=:all:`` so the resulting zip targets the Lambda Linux runtime
even when the build runs on Windows.  Both runtime dependencies (sqlglot,
pyyaml) are pure-Python wheels, so no native toolchain is required.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"

LAMBDAS: dict[str, dict[str, object]] = {
    "orchestrator": {
        "packages": ["common", "action_group", "orchestrator"],
        "requirements": ROOT / "src" / "action_group" / "requirements.txt",
        "entry": "from src.orchestrator.handler import lambda_handler  # noqa: F401\n",
    },
    "doc_builder": {
        "packages": ["common", "doc_builder"],
        "requirements": ROOT / "src" / "doc_builder" / "requirements.txt",
        "entry": "from src.doc_builder.handler import lambda_handler  # noqa: F401\n",
    },
}


def _copytree(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def _install_requirements(requirements: Path, target: Path) -> None:
    if not requirements.exists():
        return
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        str(requirements),
        "--target",
        str(target),
        "--platform",
        "manylinux2014_x86_64",
        "--implementation",
        "cp",
        "--python-version",
        "3.12",
        "--only-binary=:all:",
        "--upgrade",
        "--quiet",
    ]
    subprocess.run(cmd, check=True)


def _zip_dir(source: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source))


def build_one(name: str) -> Path:
    spec = LAMBDAS[name]
    staging = BUILD / name
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    src_pkg = staging / "src"
    src_pkg.mkdir()
    for package in spec["packages"]:
        _copytree(ROOT / "src" / str(package), src_pkg / str(package))

    (staging / "handler.py").write_text(str(spec["entry"]), encoding="utf-8")

    _install_requirements(spec["requirements"], staging)

    DIST.mkdir(exist_ok=True)
    zip_path = DIST / f"{name}.zip"
    _zip_dir(staging, zip_path)
    return zip_path


def main() -> int:
    for name in LAMBDAS:
        zip_path = build_one(name)
        print(f"built {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
