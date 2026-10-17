"""Time selection helpers for display-only nuScenes preview evidence.

This module deliberately knows nothing about replay traces or metrics. It maps
scenario-relative time onto already ordered dataset records for camera/LiDAR
preview consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence


@dataclass(frozen=True, slots=True)
class PreviewTimeResolution:
    requested_time_s: float
    resolved_time_s: float
    timestamp_us: int
    index: int
    delta_s: float
    policy: str
    status: str


def resolve_preview_time(
    requested_time_s: float,
    timestamps_us: Sequence[int],
    *,
    policy: str = "nearest",
) -> PreviewTimeResolution:
    """Resolve scenario-relative time against an ordered sample timestamp list.

    Timestamp zero is the first record in the source window. Values outside the
    available range are clamped to the endpoint rather than extrapolated.
    """
    if policy not in {"nearest", "at-or-before"}:
        raise ValueError(f"unsupported_preview_time_policy:{policy}")
    if not timestamps_us:
        raise ValueError("preview_timestamps_unavailable")
    try:
        normalized_timestamps = tuple(int(value) for value in timestamps_us)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("preview_timestamps_must_be_integers") from error
    if any(isinstance(value, bool) or float(value) != value for value in timestamps_us):
        raise ValueError("preview_timestamps_must_be_integers")
    if any(current <= previous for previous, current in zip(normalized_timestamps, normalized_timestamps[1:])):
        raise ValueError("preview_timestamps_not_strictly_increasing")
    try:
        requested_time_s = float(requested_time_s)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("preview_time_not_finite") from error
    if not isfinite(requested_time_s):
        raise ValueError("preview_time_not_finite")

    start_us = normalized_timestamps[0]
    relative = [(timestamp - start_us) / 1_000_000 for timestamp in normalized_timestamps]
    if requested_time_s <= relative[0]:
        index = 0
    elif requested_time_s >= relative[-1]:
        index = len(relative) - 1
    elif policy == "at-or-before":
        index = max(index for index, value in enumerate(relative) if value <= requested_time_s)
    else:
        index = min(range(len(relative)), key=lambda candidate: abs(relative[candidate] - requested_time_s))

    resolved_time_s = relative[index]
    return PreviewTimeResolution(
        requested_time_s=float(requested_time_s),
        resolved_time_s=resolved_time_s,
        timestamp_us=normalized_timestamps[index],
        index=index,
        delta_s=resolved_time_s - float(requested_time_s),
        policy=policy,
        status="exact" if resolved_time_s == requested_time_s else "resolved",
    )
