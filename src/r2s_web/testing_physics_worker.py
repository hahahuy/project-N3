"""Subprocess entrypoint for isolated internal physics testing runs."""

from __future__ import annotations

import json
import sys

from .testing_physics import recalculate_path
from .schemas import CanvasKeyframeRequest


def main() -> int:
    payload = json.load(sys.stdin)
    keyframes = tuple(CanvasKeyframeRequest(**item) for item in payload["keyframes"])
    result = recalculate_path(keyframes, obstacles=payload.get("obstacles", ()))
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
