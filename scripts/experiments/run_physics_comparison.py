#!/usr/bin/env python3
"""Run the isolated dynamic-single-track vs CARLA physics comparison.

This is an experiment runner, not a production backend or same-XOSC claim.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path

import carla

from real2scenario import State, compare_trajectory, integrate_dynamic_single_track


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--world", default="Town10HD_Opt")
    parser.add_argument("--duration", type=float, default=6.0)
    parser.add_argument("--dt", type=float, default=0.05)
    parser.add_argument("--steer", type=float, default=0.06)
    parser.add_argument("--speed", type=float, default=6.0)
    parser.add_argument("--spawn-index", type=int, default=20)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    reference = _desired_reference(args.duration, args.dt, args.speed)
    dynamic = integrate_dynamic_single_track(
        reference[0],
        actor_id="ego",
        duration_s=args.duration,
        steering_profile=((0.0, args.steer),),
        acceleration_profile=((0.0, 0.0),),
    )
    if dynamic.status != "valid":
        raise RuntimeError(f"dynamic prototype invalid: {dynamic.violations}")
    # The analytic dynamic trace is the desired edited motion supplied to CARLA.
    # This keeps the comparison about model/controller divergence, not a straight
    # reference versus a deliberately curved steering command.
    reference = dynamic.states

    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)
    world = client.load_world(args.world)
    original = world.get_settings()
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = args.dt
    settings.no_rendering_mode = True
    world.apply_settings(settings)
    actor = None
    collisions: list[dict[str, object]] = []
    carla_states: list[State] = []
    try:
        blueprint = world.get_blueprint_library().find("vehicle.tesla.model3")
        spawn = world.get_map().get_spawn_points()[args.spawn_index]
        actor = world.try_spawn_actor(blueprint, spawn)
        if actor is None:
            raise RuntimeError("carla_physics_spawn_failed")
        actor.set_simulate_physics(True)
        heading = math.radians(spawn.rotation.yaw)
        actor.set_target_velocity(carla.Vector3D(
            x=reference[0].speed_mps * math.cos(heading),
            y=reference[0].speed_mps * math.sin(heading),
            z=0.0,
        ))
        collision_bp = world.get_blueprint_library().find("sensor.other.collision")
        collision_sensor = world.spawn_actor(collision_bp, carla.Transform(), attach_to=actor)
        collision_sensor.listen(lambda event: collisions.append({
            "frame": event.frame,
            "timestamp_s": event.timestamp,
            "other_actor_id": None if event.other_actor is None else event.other_actor.id,
        }))
        world.tick()
        execution_anchor = actor.get_transform()
        for index, target in enumerate(reference):
            velocity = actor.get_velocity()
            actual_speed = math.hypot(velocity.x, velocity.y)
            speed_error = target.speed_mps - actual_speed
            throttle = max(0.0, min(1.0, 0.35 + 0.28 * speed_error))
            brake = max(0.0, min(1.0, -0.35 * speed_error))
            current = actor.get_transform()
            lookahead_index = min(index + max(1, int(round(4.0 / args.dt))), len(reference) - 1)
            lookahead = reference[lookahead_index]
            target_world = _to_world(lookahead, execution_anchor)
            current_yaw = math.radians(current.rotation.yaw)
            dx = target_world.location.x - current.location.x
            dy = target_world.location.y - current.location.y
            alpha = _wrap(math.atan2(dy, dx) - current_yaw)
            wheelbase_m = 2.8
            lookahead_m = max(1.0, math.hypot(dx, dy))
            wheel_angle = math.atan2(2.0 * wheelbase_m * math.sin(alpha), lookahead_m)
            steer = max(-1.0, min(1.0, wheel_angle / 0.5))
            actor.apply_control(carla.VehicleControl(
                throttle=throttle,
                steer=steer,
                brake=brake,
            ))
            frame = world.tick()
            transform = actor.get_transform()
            velocity = actor.get_velocity()
            local = _to_local(transform, velocity, spawn, index * args.dt)
            carla_states.append(local)
        collision_sensor.stop()
        collision_sensor.destroy()
    finally:
        if actor is not None and actor.is_alive:
            actor.destroy()
        world.apply_settings(original)

    metrics = compare_trajectory(dynamic.states, carla_states)
    report = {
        "status": "completed",
        "mode": "physics-enabled-low-level-speed-pid",
        "server_version": client.get_server_version(),
        "client_version": client.get_client_version(),
        "world": world.get_map().name,
        "duration_s": args.duration,
        "timestep_s": args.dt,
        "steering_rad": args.steer,
        "target_speed_mps": args.speed,
        "dynamic_status": dynamic.status,
        "dynamic_violations": [asdict(item) for item in dynamic.violations],
        "collision_count": len(collisions),
        "collisions": collisions,
        "metrics": asdict(metrics),
        "reference_samples": len(dynamic.states),
        "carla_samples": len(carla_states),
        "physics_enabled": True,
        "initial_velocity_setup": "set_target_velocity_once_before_first_tick",
        "same_xosc": False,
        "sensor_output": False,
        "cleanup": "actor destroyed and world settings restored",
    }
    (args.output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.output / "dynamic_trace.jsonl").write_text("\n".join(json.dumps(asdict(item)) for item in dynamic.states) + "\n", encoding="utf-8")
    (args.output / "carla_trace.jsonl").write_text("\n".join(json.dumps(asdict(item)) for item in carla_states) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


def _desired_reference(duration: float, dt: float, speed: float) -> tuple[State, ...]:
    count = int(round(duration / dt))
    return tuple(State(index * dt, index * dt * speed, 0.0, 0.0, speed) for index in range(count + 1))


def _to_world(state: State, anchor) -> carla.Transform:
    theta = math.radians(anchor.rotation.yaw)
    c, s = math.cos(theta), math.sin(theta)
    return carla.Transform(
        carla.Location(
            x=anchor.location.x + c * state.x_m - s * state.y_m,
            y=anchor.location.y + s * state.x_m + c * state.y_m,
            z=anchor.location.z,
        ),
        carla.Rotation(yaw=anchor.rotation.yaw + math.degrees(state.yaw_rad)),
    )


def _to_local(transform, velocity, anchor, time_s: float) -> State:
    theta = math.radians(anchor.rotation.yaw)
    c, s = math.cos(theta), math.sin(theta)
    dx = transform.location.x - anchor.location.x
    dy = transform.location.y - anchor.location.y
    yaw = math.radians(transform.rotation.yaw) - theta
    speed = math.hypot(velocity.x, velocity.y)
    return State(time_s, c * dx + s * dy, -s * dx + c * dy, math.atan2(math.sin(yaw), math.cos(yaw)), speed)


def _wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


if __name__ == "__main__":
    raise SystemExit(main())
