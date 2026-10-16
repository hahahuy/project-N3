"""Bounded native esminiLib session and WebSocket-friendly state contract.

The native binding is deliberately optional.  Without a configured shared
library this module returns an explicit unavailable session and never falls
back to the internal kinematic preview.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import threading
import uuid
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

LIVE_CONTRACT_VERSION = "esmini-live-session-v1"
ADAPTER_VERSION = "esmini-ctypes-adapter-v1"
MAX_SESSIONS = 4


class NativeBinding(Protocol):
    version: str

    def load(self, xosc_path: str, xodr_path: str, timestep_s: float) -> None: ...
    def step(self, timestep_s: float) -> None: ...
    def close(self) -> None: ...
    def state(self) -> dict[str, Any]: ...
    def reset(self) -> None: ...
    def control(self, command: dict[str, Any]) -> None: ...
    def camera(self, command: dict[str, Any]) -> None: ...


class CtypesEsminiBinding:
    """Small ABI seam for a native esminiLib build.

    esminiLib builds differ in exported symbols and ABI details.  We only
    activate this binding when the required symbols are present; unsupported
    builds remain unavailable rather than being called unsafely.
    """

    REQUIRED = (
        "SE_Init",
        "SE_StepDT",
        "SE_Close",
        "SE_GetSimulationTime",
        "SE_GetNumberOfObjects",
        "SE_GetId",
        "SE_GetObjectState",
        "SE_GetObjectName",
    )

    class ScenarioObjectState(ctypes.Structure):
        _fields_ = [
            ("id", ctypes.c_int),
            ("model_id", ctypes.c_int),
            ("ctrl_type", ctypes.c_int),
            ("timestamp", ctypes.c_double),
            ("x", ctypes.c_double),
            ("y", ctypes.c_double),
            ("z", ctypes.c_double),
            ("h", ctypes.c_double),
            ("p", ctypes.c_double),
            ("r", ctypes.c_double),
            ("road_id", ctypes.c_uint32),
            ("junction_id", ctypes.c_uint32),
            ("t", ctypes.c_double),
            ("lane_id", ctypes.c_int),
            ("lane_offset", ctypes.c_double),
            ("s", ctypes.c_double),
            ("speed", ctypes.c_double),
            ("center_offset_x", ctypes.c_double),
            ("center_offset_y", ctypes.c_double),
            ("center_offset_z", ctypes.c_double),
            ("width", ctypes.c_double),
            ("length", ctypes.c_double),
            ("height", ctypes.c_double),
            ("object_type", ctypes.c_int),
            ("object_category", ctypes.c_int),
            ("wheel_angle", ctypes.c_double),
            ("wheel_rot", ctypes.c_double),
            ("visibility_mask", ctypes.c_int),
        ]

    def __init__(self, library_path: str | Path):
        self.library_path = str(library_path)
        self.library = ctypes.CDLL(self.library_path)
        missing = [name for name in self.REQUIRED if not hasattr(self.library, name)]
        if missing:
            raise RuntimeError(f"esminiLib_required_symbols_missing:{','.join(missing)}")
        self.version = os.environ.get("ESMINILIB_VERSION", "unknown")
        self.library.SE_Init.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.library.SE_Init.restype = ctypes.c_int
        self.library.SE_StepDT.argtypes = [ctypes.c_double]
        self.library.SE_StepDT.restype = ctypes.c_int
        self.library.SE_Close.argtypes = []
        self.library.SE_Close.restype = None
        self.library.SE_GetNumberOfObjects.argtypes = []
        self.library.SE_GetNumberOfObjects.restype = ctypes.c_int
        self.library.SE_GetSimulationTime.argtypes = []
        self.library.SE_GetSimulationTime.restype = ctypes.c_double
        self.library.SE_GetId.argtypes = [ctypes.c_int]
        self.library.SE_GetId.restype = ctypes.c_int
        self.library.SE_GetObjectState.argtypes = [ctypes.c_int, ctypes.POINTER(self.ScenarioObjectState)]
        self.library.SE_GetObjectState.restype = ctypes.c_int
        self.library.SE_GetObjectName.argtypes = [ctypes.c_int]
        self.library.SE_GetObjectName.restype = ctypes.c_char_p
        self._loaded = False

    def load(self, xosc_path: str, xodr_path: str, timestep_s: float) -> None:
        self._xosc_path = xosc_path
        result = self.library.SE_Init(xosc_path.encode(), 0, 0, 0, 0)
        if result != 0:
            raise RuntimeError(f"esminiLib_init_failed:{result}")
        self._loaded = True

    def step(self, timestep_s: float) -> None:
        if not self._loaded or self.library.SE_StepDT(float(timestep_s)) != 0:
            raise RuntimeError("esminiLib_step_failed")

    def close(self) -> None:
        self.library.SE_Close()

    def state(self) -> dict[str, Any]:
        if not self._loaded:
            raise RuntimeError("esminiLib_state_abi_unavailable")
        objects = []
        for index in range(self.library.SE_GetNumberOfObjects()):
            object_id = self.library.SE_GetId(index)
            state = self.ScenarioObjectState()
            if object_id < 0 or self.library.SE_GetObjectState(object_id, ctypes.byref(state)) != 0:
                continue
            name = self.library.SE_GetObjectName(object_id)
            objects.append({
                "id": name.decode(errors="replace") if name else str(object_id),
                "x_m": state.x,
                "y_m": state.y,
                "z_m": state.z,
                "yaw_rad": state.h,
                "pitch_rad": state.p,
                "roll_rad": state.r,
                "speed_mps": state.speed,
                "length_m": state.length,
                "width_m": state.width,
                "height_m": state.height,
            })
        return {"objects": objects, "events": []}

    def reset(self) -> None:
        if not self._loaded or not getattr(self, "_xosc_path", None):
            raise RuntimeError("esminiLib_reset_requires_reload")
        self.library.SE_Close()
        result = self.library.SE_Init(self._xosc_path.encode(), 0, 0, 0, 0)
        if result != 0:
            self._loaded = False
            raise RuntimeError(f"esminiLib_reset_reload_failed:{result}")

    def control(self, command: dict[str, Any]) -> None:
        raise RuntimeError("esminiLib_control_abi_unavailable")

    def camera(self, command: dict[str, Any]) -> None:
        # Camera presentation belongs to the browser-native renderer. Live
        # sessions disable the native viewer and therefore must not require an
        # X11/display context for camera state updates.
        del command


@dataclass(slots=True)
class LiveSession:
    session_id: str
    scenario_id: str
    xosc_path: Path
    xodr_path: Path
    xosc_sha256: str
    xodr_sha256: str
    timestep_s: float
    binding: NativeBinding | None
    status: str
    unavailable_reason: str | None = None
    simulation_time_s: float = 0.0
    camera_state: dict[str, Any] = field(default_factory=dict)
    native_lock: threading.RLock | None = None

    def metadata(self) -> dict[str, Any]:
        return {
            "contract_version": LIVE_CONTRACT_VERSION,
            "session_id": self.session_id,
            "scenario_id": self.scenario_id,
            "status": self.status,
            "unavailable_reason": self.unavailable_reason,
            "adapter": "esminiLib",
            "adapter_version": ADAPTER_VERSION,
            "simulator_version": self.binding.version if self.binding else None,
            "xosc_sha256": self.xosc_sha256,
            "xodr_sha256": self.xodr_sha256,
            "timestep_s": self.timestep_s,
            "simulation_time_s": self.simulation_time_s,
            "coordinate_frame": "esmini_local",
            "transform_version": "esmini-state-v1",
            "authoritative_state_source": "native_esminiLib" if self.binding else None,
            "commands": ["pause", "resume", "step", "reset", "control", "camera"],
            "command_capabilities": {
                "reset": {"available": True, "implementation": "reload_same_artifact_pair"},
                "control": {"available": False, "unavailable_reason": "esminiLib_control_abi_unavailable"},
                "camera": {"available": True, "implementation": "browser_native_renderer"},
            },
            "rendering": {"browser_native": True, "screenshot_stream": False},
            "sensors": {"post_edit_frames": "unsupported"},
            "artifact_visibility": "local_private",
        }

    def frame(self) -> dict[str, Any]:
        lock = self.native_lock or nullcontext()
        with lock:
            payload = self.binding.state() if self.binding else {"objects": [], "events": []}
            if self.binding:
                self.simulation_time_s = float(self.binding.library.SE_GetSimulationTime()) if hasattr(self.binding, "library") else self.simulation_time_s
        return {
            **self.metadata(),
            "message_type": "state",
            "objects": payload.get("objects", []),
            "events": payload.get("events", []),
            "camera": self.camera_state,
        }

    def command(self, command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        if command not in {"pause", "resume", "step", "reset", "control", "camera"}:
            raise ValueError("unsupported_live_command")
        if self.binding is None:
            if command == "control":
                _validate_control(payload)
            elif command == "camera":
                _validate_camera(payload)
            return self.metadata() | {"message_type": "command_result", "command": command}
        lock = self.native_lock or nullcontext()
        with lock:
            if command == "pause":
                self.status = "paused"
            elif command == "resume":
                self.status = "running"
            elif command == "step":
                if self.status == "unavailable":
                    raise RuntimeError("live_session_unavailable")
                self.binding.step(self.timestep_s)
                self.simulation_time_s += self.timestep_s
            elif command == "reset":
                self.binding.reset()
                self.simulation_time_s = 0.0
                self.status = "reset"
            elif command == "control":
                _validate_control(payload)
                self.binding.control(payload)
            elif command == "camera":
                _validate_camera(payload)
                self.binding.camera(payload)
                self.camera_state = dict(payload)
        return self.frame()


class LiveSessionService:
    def __init__(self, project_root: Path, library_path: str | None = None, max_sessions: int = MAX_SESSIONS, binding_factory: Any = CtypesEsminiBinding):
        self.project_root = project_root.resolve()
        self.library_path = library_path
        self.max_sessions = max_sessions
        self.binding_factory = binding_factory
        self.sessions: dict[str, LiveSession] = {}
        self._lock = threading.RLock()
        self._native_lock = threading.RLock()

    def capability(self) -> dict[str, Any]:
        configured = bool(self.library_path)
        available = False
        reason = "esminiLib_not_configured"
        if configured:
            try:
                binding = CtypesEsminiBinding(self.library_path or "")
                available = True
                reason = None
                version = binding.version
            except (OSError, RuntimeError) as error:
                version = None
                reason = str(error)
        else:
            version = None
        return {
            "contract_version": LIVE_CONTRACT_VERSION,
            "configured": configured,
            "available": available,
            "library": self.library_path,
            "version": version,
            "adapter_version": ADAPTER_VERSION,
            "max_sessions": self.max_sessions,
            "active_sessions": len(self.sessions),
            "unavailable_reason": reason,
            "commands": ["pause", "resume", "step", "reset", "control", "camera"],
            "browser_renderer": "browser-native-state-renderer",
            "screenshot_stream": False,
            "command_capabilities": {
                "reset": {"available": True, "implementation": "reload_same_artifact_pair"},
                "control": {"available": False, "unavailable_reason": "esminiLib_control_abi_unavailable"},
                "camera": {"available": True, "implementation": "browser_native_renderer"},
            },
        }

    def create(self, scenario_id: str, xosc_path: str, xodr_path: str, timestep_s: float) -> LiveSession:
        if not 0.001 <= timestep_s <= 1.0:
            raise ValueError("timestep_s_must_be_between_0.001_and_1.0")
        xosc = _confined_file(self.project_root, xosc_path, "xosc")
        xodr = _confined_file(self.project_root, xodr_path, "xodr")
        with self._lock:
            if len(self.sessions) >= self.max_sessions:
                raise RuntimeError("live_session_limit_reached")
            if any(session.binding is not None for session in self.sessions.values()):
                raise RuntimeError("native_live_session_limit_reached")
            binding: NativeBinding | None = None
            status = "unavailable"
            reason = "esminiLib_not_configured"
            if self.library_path:
                try:
                    binding = self.binding_factory(self.library_path)
                    with self._native_lock:
                        binding.load(str(xosc), str(xodr), timestep_s)
                    status, reason = "paused", None
                except (OSError, RuntimeError) as error:
                    if binding is not None:
                        try:
                            with self._native_lock:
                                binding.close()
                        except (OSError, RuntimeError):
                            pass
                    binding = None
                    reason = str(error)
            session = LiveSession(
                session_id=f"live-{uuid.uuid4().hex[:12]}",
                scenario_id=scenario_id,
                xosc_path=xosc,
                xodr_path=xodr,
                xosc_sha256=_sha256(xosc),
                xodr_sha256=_sha256(xodr),
                timestep_s=timestep_s,
                binding=binding,
                status=status,
                unavailable_reason=reason,
                native_lock=self._native_lock if binding is not None else None,
            )
            self.sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> LiveSession:
        try:
            return self.sessions[session_id]
        except KeyError as error:
            raise KeyError("live_session_not_found") from error

    def close(self, session_id: str) -> None:
        with self._lock:
            session = self.get(session_id)
            if session.binding:
                with self._native_lock:
                    session.binding.close()
            del self.sessions[session_id]


def _confined_file(root: Path, value: str, suffix: str) -> Path:
    path = Path(value).expanduser().resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{suffix}_path_outside_project_root") from error
    if path.suffix.lower() != f".{suffix}" or not path.is_file():
        raise ValueError(f"valid_{suffix}_file_required")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _validate_control(payload: dict[str, Any]) -> None:
    allowed = {"actor_id", "throttle", "brake", "steering"}
    if set(payload) - allowed or "actor_id" not in payload:
        raise ValueError("invalid_live_control_fields")
    for key in ("throttle", "brake", "steering"):
        if key in payload and not isinstance(payload[key], (int, float)):
            raise ValueError("live_control_values_must_be_numeric")
        if key in payload and (key != "steering" and not 0 <= float(payload[key]) <= 1):
            raise ValueError("live_control_range_invalid")
        if key == "steering" and key in payload and not -1 <= float(payload[key]) <= 1:
            raise ValueError("live_steering_range_invalid")


def _validate_camera(payload: dict[str, Any]) -> None:
    allowed = {"mode", "x_m", "y_m", "z_m", "yaw_rad", "pitch_rad"}
    if set(payload) - allowed or payload.get("mode") not in {"third-person", "in-car"}:
        raise ValueError("invalid_live_camera_fields")
    for key in set(payload) - {"mode"}:
        if not isinstance(payload[key], (int, float)):
            raise ValueError("live_camera_values_must_be_numeric")
