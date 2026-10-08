"""esmini process execution and normalized CSV replay traces."""

from __future__ import annotations

import csv
import os
import subprocess
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from .models import State


@dataclass(frozen=True, slots=True)
class ReplayState:
    """One normalized simulator state in SI units."""

    actor_id: str
    state: State

    def __post_init__(self) -> None:
        if not self.actor_id:
            raise ValueError("ReplayState actor_id must not be empty.")


@dataclass(frozen=True, slots=True)
class ReplayTrace:
    """Ordered normalized states emitted by a replay backend."""

    states: tuple[ReplayState, ...]

    def __post_init__(self) -> None:
        if not self.states:
            raise ValueError("ReplayTrace must contain at least one state.")
        previous_time_by_actor: dict[str, float] = {}
        for item in self.states:
            previous_time = previous_time_by_actor.get(item.actor_id)
            if previous_time is not None and item.state.time_s <= previous_time:
                raise ValueError("ReplayTrace timestamps must strictly increase for each actor.")
            previous_time_by_actor[item.actor_id] = item.state.time_s

    def states_for(self, actor_id: str) -> tuple[State, ...]:
        """Return one actor's chronologically ordered replay trajectory."""
        states = tuple(item.state for item in self.states if item.actor_id == actor_id)
        if not states:
            raise ValueError(f"ReplayTrace has no states for actor {actor_id!r}.")
        return states


@dataclass(frozen=True, slots=True)
class EsminiConfig:
    """External esmini invocation settings, with no machine path embedded in code."""

    executable: str | Path | tuple[str, ...] | None = None
    trace_converter: str | Path | tuple[str, ...] | None = None
    timeout_s: float = 30.0
    fixed_timestep_s: float = 0.05

    def __post_init__(self) -> None:
        for field_name, value in (
            ("timeout_s", self.timeout_s),
            ("fixed_timestep_s", self.fixed_timestep_s),
        ):
            if not isfinite(value) or value <= 0:
                raise ValueError(f"EsminiConfig {field_name} must be finite and positive.")

    def resolve_command(self) -> tuple[str, ...]:
        """Resolve an explicit executable or the caller-provided ``ESMINI_BIN``."""
        executable = self.executable or os.environ.get("ESMINI_BIN")
        if not executable:
            raise ValueError("esmini executable is required; set EsminiConfig.executable or ESMINI_BIN.")
        if isinstance(executable, tuple):
            if not executable or any(not item for item in executable):
                raise ValueError("EsminiConfig executable command must not be empty.")
            return executable
        return (str(executable),)

    def resolve_trace_converter_command(self) -> tuple[str, ...]:
        """Resolve the external ``dat2csv`` command used for esmini recordings."""
        converter = self.trace_converter or os.environ.get("ESMINI_DAT2CSV")
        if not converter:
            raise ValueError(
                "esmini dat2csv executable is required; set EsminiConfig.trace_converter "
                "or ESMINI_DAT2CSV."
            )
        if isinstance(converter, tuple):
            if not converter or any(not item for item in converter):
                raise ValueError("EsminiConfig trace converter command must not be empty.")
            return converter
        return (str(converter),)


@dataclass(frozen=True, slots=True)
class ReplayReport:
    """Auditable outcome of one esmini invocation."""

    command: tuple[str, ...]
    completed: bool
    timed_out: bool
    exit_code: int | None
    stdout: str
    stderr: str
    tool_version: str | None
    trace_path: Path
    trace: ReplayTrace | None


def run_esmini(
    scenario_path: str | Path,
    trace_path: str | Path,
    config: EsminiConfig = EsminiConfig(),
) -> ReplayReport:
    """Run esmini headlessly and parse its normalized CSV trace when available.

    The configured executable must support ``--osc``, ``--headless``, and
    ``--record``. Its DAT recording is normalized through the configured
    ``dat2csv`` companion command.
    A failed invocation returns an auditable report instead of hiding stderr.
    """
    executable_command = config.resolve_command()
    scenario = Path(scenario_path)
    trace = Path(trace_path)
    if not scenario.is_file():
        raise ValueError(f"OpenSCENARIO file does not exist: {scenario}.")
    trace.parent.mkdir(parents=True, exist_ok=True)
    recording_path = trace.with_suffix(".dat")
    command = (
        *executable_command,
        "--osc",
        str(scenario),
        "--headless",
        "--fixed_timestep",
        format(config.fixed_timestep_s, ".12g"),
        "--record",
        str(recording_path),
    )
    tool_version = _tool_version(executable_command, config.timeout_s)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=config.timeout_s,
        )
    except subprocess.TimeoutExpired as error:
        return ReplayReport(
            command=command,
            completed=False,
            timed_out=True,
            exit_code=None,
            stdout=_as_text(error.stdout),
            stderr=_as_text(error.stderr),
            tool_version=tool_version,
            trace_path=trace,
            trace=None,
        )
    except OSError as error:
        return ReplayReport(
            command=command,
            completed=False,
            timed_out=False,
            exit_code=None,
            stdout="",
            stderr=str(error),
            tool_version=tool_version,
            trace_path=trace,
            trace=None,
        )

    if completed.returncode != 0:
        return ReplayReport(
            command=command,
            completed=False,
            timed_out=False,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            tool_version=tool_version,
            trace_path=trace,
            trace=None,
        )
    try:
        converter_command = config.resolve_trace_converter_command()
        conversion = subprocess.run(
            (
                *converter_command,
                "--file",
                str(recording_path),
                "--csv",
                str(trace),
                "--precision",
                "12",
            ),
            capture_output=True,
            check=False,
            text=True,
            timeout=config.timeout_s,
        )
        if conversion.returncode != 0:
            raise ValueError(
                f"dat2csv failed with exit code {conversion.returncode}: {conversion.stderr.strip()}"
            )
        normalized_trace = parse_esmini_csv_trace(trace)
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        return ReplayReport(
            command=command,
            completed=False,
            timed_out=False,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=f"{completed.stderr}{error}",
            tool_version=tool_version,
            trace_path=trace,
            trace=None,
        )
    return ReplayReport(
        command=command,
        completed=True,
        timed_out=False,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        tool_version=tool_version,
        trace_path=trace,
        trace=normalized_trace,
    )


def parse_esmini_csv_trace(path: str | Path) -> ReplayTrace:
    """Normalize esmini dat2csv output into the project's replay trace contract."""
    trace_path = Path(path)
    required_fields = ("time", "id", "name", "x", "y", "z", "h", "p", "r", "speed", "wheel_angle", "wheel_rot")
    try:
        with trace_path.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValueError(
                    "Replay trace must have exactly these CSV columns: "
                    f"{', '.join(required_fields)}."
                )
            reader.fieldnames = [field.strip() for field in reader.fieldnames]
            if set(reader.fieldnames) != set(required_fields):
                raise ValueError(
                    "Replay trace must have exactly these CSV columns: "
                    f"{', '.join(required_fields)}."
                )
            states = tuple(
                _esmini_replay_state_from_row(
                    {key.strip(): value.strip() if value is not None else None for key, value in row.items()},
                    line_number,
                )
                for line_number, row in enumerate(reader, 2)
            )
    except OSError as error:
        raise ValueError(f"Unable to read replay trace {trace_path}: {error}.") from error
    if not states:
        raise ValueError(f"Replay trace {trace_path} is empty.")
    return ReplayTrace(states=states)


def _esmini_replay_state_from_row(row: dict[str, str | None], line_number: int) -> ReplayState:
    try:
        actor_id = row["name"]
        if not actor_id:
            raise ValueError("actor_id is empty")
        return ReplayState(
            actor_id=actor_id,
            state=State(
                time_s=float(row["time"] or ""),
                x_m=float(row["x"] or ""),
                y_m=float(row["y"] or ""),
                yaw_rad=float(row["h"] or ""),
                speed_mps=float(row["speed"] or ""),
            ),
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"Replay trace row {line_number} is invalid: {error}.") from error


def _tool_version(command: tuple[str, ...], timeout_s: float) -> str | None:
    try:
        version = subprocess.run(
            (*command, "--version"),
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = version.stdout.strip() or version.stderr.strip()
    return output or None


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode() if isinstance(value, bytes) else value
