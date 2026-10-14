#!/usr/bin/env python3
"""Verify a clean checkout of the committed tree and emit release evidence.

The check answers one question: can the committed repository state reproduce its
own verification evidence without the developer's working tree? It exports
``HEAD`` with ``git archive``, runs the documented verification commands against
that export, scans it for restricted dataset content and host paths, and writes
a local/private release evidence bundle.

This is engineering evidence. It creates no scientific acceptance claim and no
owner sign-off.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


RELEASE_EVIDENCE_VERSION = "release-evidence-v1"
RESTRICTED_PATTERNS = (
    "data/v1.0-mini/",
    "data/v1.0-trainval/",
    "data/v1.0-test/",
    "*.pcd",
    "*.bin",
    "*.npy",
    "*.jpg",
    "*.jpeg",
    "*.png",
    "*.bag",
)
RESTRICTED_TOKEN_FILE = "v1.0-trainval"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help="Interpreter used to run verification against the clean checkout.",
    )
    parser.add_argument("--keep-checkout", action="store_true")
    parser.add_argument(
        "--source",
        choices=("head", "working-tree"),
        default="head",
        help=(
            "head: verify the committed release candidate (default). "
            "working-tree: verify current uncommitted sources for engineering evidence."
        ),
    )
    args = parser.parse_args()

    project_root = args.project_root.expanduser().resolve()
    revision = _run(["git", "-C", str(project_root), "rev-parse", "HEAD"])
    dirty = bool(
        _run(["git", "-C", str(project_root), "status", "--porcelain"]).strip()
    )
    checkout_parent = Path(tempfile.mkdtemp(prefix="r2s-clean-checkout-"))
    checkout = checkout_parent / "checkout"
    checkout.mkdir()
    if args.source == "head":
        archive = subprocess.run(
            ["git", "-C", str(project_root), "archive", "--format=tar", "HEAD"],
            capture_output=True,
            check=True,
        ).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            _safe_extract(bundle, checkout)
    else:
        shutil.copytree(
            project_root,
            checkout,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                ".git", ".venv", "node_modules", "__pycache__", "*.pyc",
                "data", "reports", "scenarios", "dist", ".pytest_cache",
                ".playwright-mcp",
            ),
        )
    if not any(checkout.iterdir()):
        raise SystemExit("The exported checkout is empty.")

    tests = _verification(
        [
            str(args.python),
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        checkout,
        project_root,
    )
    docs = _verification(
        [str(args.python), "scripts/check_docs_consistency.py"], checkout, project_root
    )
    restricted = _restricted_content(checkout)
    host_paths = _host_path_findings(checkout)
    lockfile = checkout / "requirements.lock.txt"

    evidence: dict[str, Any] = {
        "evidence_version": RELEASE_EVIDENCE_VERSION,
        "git_revision": revision,
        "working_tree_clean_at_verification": not dirty,
        "verification_mode": (
            "clean_git_archive_checkout"
            if args.source == "head"
            else "working_tree_snapshot_checkout"
        ),
        "verification_source": args.source,
        "interpreter_major_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
        "checks": {
            "pytest": tests,
            "docs_consistency": docs,
            "restricted_dataset_content": {
                "status": "pass" if not restricted else "fail",
                "findings": restricted,
                "patterns": list(RESTRICTED_PATTERNS),
            },
            "committed_host_paths": {
                "status": "pass" if not host_paths else "fail",
                "findings": host_paths,
            },
            "dependency_lockfile": {
                "status": "present" if lockfile.is_file() else "missing",
                "path": "requirements.lock.txt",
            },
            "license_files": {
                "license": (checkout / "LICENSE").is_file(),
                "notice": (checkout / "NOTICE").is_file(),
            },
        },
        "tree_sha256": _tree_hash(checkout),
        "file_count": sum(1 for path in checkout.rglob("*") if path.is_file()),
        "sign_off": {
            "status": "pending_owner",
            "note": "Engineering verification only; no owner or scientific sign-off.",
        },
    }
    passed = (
        tests["status"] == "pass"
        and docs["status"] == "pass"
        and not restricted
        and not host_paths
    )
    evidence["status"] = "pass" if passed else "fail"

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.keep_checkout:
        print(f"clean checkout kept at {checkout}")
    else:
        shutil.rmtree(checkout_parent, ignore_errors=True)
    print(output)
    print(f"release evidence: {evidence['status']}")
    return 0 if passed else 1


def _safe_extract(bundle: tarfile.TarFile, destination: Path) -> None:
    """Extract only regular files and directories below the destination."""
    root = destination.resolve()
    for member in bundle.getmembers():
        target = (root / member.name).resolve()
        if not target.is_relative_to(root) or member.issym() or member.islnk():
            raise SystemExit(f"Refusing to extract unsafe archive member: {member.name}")
    bundle.extractall(destination, filter="data")


def _verification(command: list[str], checkout: Path, project_root: Path) -> dict[str, Any]:
    environment = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(checkout / "src"),
    }
    result = subprocess.run(
        command,
        cwd=checkout,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    tail = (result.stdout or "").strip().splitlines()[-3:]
    return {
        "command": ["python", *(Path(part).name if index else part for index, part in enumerate(command[1:], start=1))],
        "status": "pass" if result.returncode == 0 else "fail",
        "exit_code": result.returncode,
        "summary": " | ".join(tail),
        "source_root": "clean_checkout",
    }


def _restricted_content(checkout: Path) -> list[str]:
    findings: list[str] = []
    for pattern in RESTRICTED_PATTERNS:
        for path in sorted(checkout.glob(pattern)):
            findings.append(path.relative_to(checkout).as_posix())
    for path in sorted(checkout.rglob(RESTRICTED_TOKEN_FILE)):
        findings.append(path.relative_to(checkout).as_posix())
    return sorted(set(findings))


def _host_path_findings(checkout: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted((checkout / "docs").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if "/home/" in line or "/Users/" in line:
                findings.append(
                    f"{path.relative_to(checkout).as_posix()}:{number}"
                )
    return findings


def _tree_hash(checkout: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(checkout.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(checkout).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(str(path.stat().st_size).encode("ascii"))
    return digest.hexdigest()


def _run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return result.stdout.strip()


if __name__ == "__main__":
    sys.exit(main())