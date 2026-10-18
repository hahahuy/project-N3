#!/usr/bin/env python3
"""Measure the bounded batch admission contract without replay evidence."""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from r2s_web.app import create_app
from r2s_web.config import WebSettings
from r2s_web.jobs import BatchService


FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "synthetic-variant-artifact.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="r2s-batch-benchmark-") as root_name:
        root = Path(root_name)
        artifacts = root / "scenarios"
        artifacts.mkdir()
        shutil.copy(FIXTURE, artifacts / "baseline.json")
        settings = WebSettings(
            project_root=root,
            artifact_root=artifacts,
            output_root=root / "reports",
            dataset_root=None,
            esmini_bin=None,
            esmini_dat2csv=None,
            batch_max_workers=1,
            batch_max_pending=1,
            batch_accept_grace_s=0.0,
        )
        entered = threading.Event()
        release = threading.Event()
        original = BatchService._run

        def delayed_run(self, record, request):
            entered.set()
            release.wait(timeout=5)
            return original(self, record, request)

        BatchService._run = delayed_run
        try:
            client = TestClient(create_app(settings))
            body = {
                "scenario_id": "synthetic-variant-001",
                "speed_multipliers": [1.0],
                "initial_gap_deltas_m": [0.0],
                "timing_offsets_s": [0.0],
            }
            started = time.perf_counter()
            first = client.post("/api/batches", json=body)
            accepted_s = time.perf_counter() - started
            entered.wait(timeout=2)
            second = client.post("/api/batches", json=body)
            third = client.post("/api/batches", json=body)
            release.set()
            completed_started = time.perf_counter()
            status = client.get(f"/api/batches/{first.json()['job_id']}")
            while status.json()["status"] not in {"completed", "failed"}:
                time.sleep(0.005)
                status = client.get(f"/api/batches/{first.json()['job_id']}")
            completed_s = time.perf_counter() - completed_started
            print(json.dumps({
                "benchmark_version": "batch-admission-benchmark-v1",
                "scientific_role": "engineering-orchestration-only",
                "dec_018": "no browser/WASM or recorded display data enters replay.csv, ADE/FDE, gates or reports",
                "config": {"max_workers": 1, "max_pending": 1, "accept_grace_s": 0.0},
                "first_status": first.json()["status"],
                "second_status": second.status_code,
                "third_status": third.status_code,
                "third_reason": third.json().get("detail"),
                "time_to_accept_s": round(accepted_s, 6),
                "time_to_observe_completed_s": round(completed_s, 6),
            }, indent=2, sort_keys=True))
        finally:
            BatchService._run = original
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
