"""Identify the build a running API came from.

The product image bakes the repository in rather than bind-mounting it, so the
code on disk is exactly what was built. That makes "what commit is the product
running?" otherwise unanswerable without diffing source by hand: the image
carries no git metadata, no commit label and no commit environment variable.

`Dockerfile.prod` bakes the values below at build time and `compose.demo.yml`
passes them as build args, so `/api/health` reports them. Everything degrades
to `null` when the variables are absent, which is the dev case where the
working tree is bind-mounted and git describes the tree directly.
"""

from __future__ import annotations

import os
from typing import Any


#: Build-time provenance. Unset in dev, where the source tree is bind-mounted.
_COMMIT_ENV = "PROJECT_N3_BUILD_COMMIT"
_COMMIT_TIME_ENV = "PROJECT_N3_BUILD_COMMIT_TIME"
_DIRTY_ENV = "PROJECT_N3_BUILD_DIRTY"

UNKNOWN = "unknown"


def build_identity() -> dict[str, Any]:
    """Return the provenance of this build.

    Fields are nullable rather than omitted so the response shape is stable:
    a dev process reports nulls, a product process reports the commit.
    """
    dirty = os.environ.get(_DIRTY_ENV, "").strip()
    return {
        "commit": os.environ.get(_COMMIT_ENV) or None,
        "commit_time": os.environ.get(_COMMIT_TIME_ENV) or None,
        # An explicit "true" is meaningful; anything else, including empty, is
        # not, because the dev process has no build-time tree to dirty.
        "dirty": dirty.lower() == "true" if dirty else None,
        "source": "baked" if os.environ.get(_COMMIT_ENV) else "bind-mounted",
    }


def describe_build_identity() -> str:
    """One-line human summary, for logs and the CLI."""
    identity = build_identity()
    commit = identity["commit"] or UNKNOWN
    suffix = " (dirty)" if identity["dirty"] else ""
    return f"{commit}{suffix} via {identity['source']}"
