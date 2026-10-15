#!/usr/bin/env python3
"""Run the M5B one-vehicle CARLA feasibility spike."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

from real2scenario import artifact_from_json, choose_best_anchor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--world", default="Town04")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--fixed-delta", type=float, default=0.05)
    args = parser.parse_args()
    try:
        import carla
    except ImportError as error:
        raise SystemExit("CARLA Python client is unavailable.") from error

    scenario, _, _ = artifact_from_json(args.scenario.read_text(encoding="utf-8"))
    source_payload = args.scenario.read_bytes()
    config_hash = hashlib.sha256(source_payload).hexdigest()
    git_commit = _git_commit()
    actors = scenario.actors
    selected = [actor for actor in actors if actor.actor_id == scenario.ego_actor_id]
    selected.extend(
        actor
        for actor in actors
        if actor.actor_id != scenario.ego_actor_id and actor.actor_type.startswith("vehicle")
    )
    selected = selected[:2]
    if len(selected) < 2:
        raise SystemExit("M5B requires an ego actor and one vehicle actor.")

    args.output.mkdir(parents=True, exist_ok=True)
    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world = client.load_world(args.world)
    mapped = choose_best_anchor(scenario, world, world_name=args.world)
    selected = [mapped.scenario.actors[next(i for i, item in enumerate(mapped.scenario.actors) if item.actor_id == actor.actor_id)] for actor in selected]
    (args.output / "config.json").write_text(
        json.dumps(
            {
                "scenario": str(args.scenario),
                "world": args.world,
                "fixed_delta_seconds": args.fixed_delta,
                "mode": "open-loop-transform-playback",
                "source_coordinate_frame": scenario.coordinate_frame,
                "execution_coordinate_frame": mapped.scenario.coordinate_frame,
                "actor_ids": [actor.actor_id for actor in selected],
                "mapping_provenance": mapped.provenance(),
                "git_commit": git_commit,
                "config_sha256": config_hash,
                "seed": scenario.provenance.get("variant_seed", "not-applicable"),
                "waypoint_validation": [asdict(match) for match in mapped.matches],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if not mapped.valid:
        raise RuntimeError(
            "Mapped scenario failed CARLA waypoint validation: "
            f"max_distance_m={mapped.max_waypoint_distance_m}"
        )
    original = world.get_settings()
    spawned = []
    trace_path = args.output / "trace.jsonl"
    start = time.monotonic()
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = args.fixed_delta
        world.apply_settings(settings)
        blueprint = world.get_blueprint_library().filter("vehicle.tesla.model3")[0]
        for actor in selected:
            state = actor.trajectory[0]
            vehicle = world.try_spawn_actor(
                blueprint,
                carla.Transform(
                    carla.Location(x=state.x_m, y=state.y_m, z=mapped.anchor.z_m + 0.5),
                    carla.Rotation(yaw=state.yaw_rad * 57.29577951308232),
                ),
            )
            if vehicle is None:
                raise RuntimeError(f"Could not spawn CARLA actor for {actor.actor_id}.")
            spawned.append((actor, vehicle))
        with trace_path.open("w", encoding="utf-8") as trace:
            for index in range(max(len(actor.trajectory) for actor, _ in spawned)):
                for actor, vehicle in spawned:
                    state = actor.trajectory[min(index, len(actor.trajectory) - 1)]
                    vehicle.set_transform(
                        carla.Transform(
                            carla.Location(x=state.x_m, y=state.y_m, z=mapped.anchor.z_m + 0.5),
                            carla.Rotation(yaw=state.yaw_rad * 57.29577951308232),
                        )
                    )
                tick = world.tick()
                for actor, vehicle in spawned:
                    transform = vehicle.get_transform()
                    trace.write(json.dumps({"tick": tick, "time_s": (tick - 1) * args.fixed_delta, "actor_id": actor["actor_id"], "x_m": transform.location.x, "y_m": transform.location.y, "z_m": transform.location.z, "yaw_deg": transform.rotation.yaw}, sort_keys=True) + "\n")
    finally:
        for _, vehicle in spawned:
            vehicle.destroy()
        world.apply_settings(original)
    manifest = {
        "status": "completed",
        "world": args.world,
        "trace": trace_path.name,
        "runtime_s": time.monotonic() - start,
        "cleanup": "actors destroyed and world settings restored",
        "source_coordinate_frame": scenario.coordinate_frame,
        "execution_coordinate_frame": mapped.scenario.coordinate_frame,
        "mapping_provenance": mapped.provenance(),
        "git_commit": git_commit,
        "config_sha256": config_hash,
        "seed": scenario.provenance.get("variant_seed", "not-applicable"),
        "waypoint_validation": [asdict(match) for match in mapped.matches],
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
