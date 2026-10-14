#!/usr/bin/env python3
"""Check documentation layout and stale/current boundary rules."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def main() -> int:
    errors: list[str] = []
    required = (
        DOCS / "README.md",
        DOCS / "current" / "project-status.md",
        DOCS / "current" / "decisions.md",
        DOCS / "current" / "technical-contracts.md",
        DOCS / "current" / "evidence-index.md",
    )
    errors.extend(f"missing required docs entrypoint: {path}" for path in required if not path.is_file())
    for path in (DOCS / "archive").rglob("*.md") if (DOCS / "archive").is_dir() else ():
        text = path.read_text(encoding="utf-8")
        if "Historical" not in text and "historical" not in text:
            errors.append(f"archived document lacks historical banner: {path}")
    for path in DOCS.rglob("*.md"):
        if "archive" in path.parts or path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"/home/[^\s`]+|/Users/[^\s`]+", text):
            errors.append(f"absolute host path in committed docs: {path}")
        if "archive" not in path.parts:
            for target in re.findall(r"(?<!!)\[[^]]+\]\(([^)]+)\)", text):
                parsed = urlparse(target)
                if parsed.scheme or parsed.netloc or target.startswith("#"):
                    continue
                link_path = unquote(parsed.path)
                if not link_path:
                    continue
                resolved = (path.parent / link_path).resolve()
                if not resolved.is_file() and not resolved.is_dir():
                    errors.append(f"broken local doc link: {path} -> {target}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("docs consistency: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
