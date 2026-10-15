from pathlib import Path

import pytest

from r2s_web.live_session import LiveSessionService


class FakeBinding:
    version = "fake-esminiLib-1.0"

    def __init__(self, _path: str):
        self.time = 0.0
        self.closed = False

    def load(self, _xosc: str, _xodr: str, _timestep: float) -> None: pass
    def step(self, timestep: float) -> None: self.time += timestep
    def close(self) -> None: self.closed = True
    def state(self) -> dict: return {"objects": [{"id": "ego", "x_m": self.time, "y_m": 0.0, "yaw_rad": 0.0}], "events": []}
    def reset(self) -> None: self.time = 0.0
    def control(self, _command: dict) -> None: pass
    def camera(self, _command: dict) -> None: pass


def _files(tmp_path: Path) -> tuple[str, str]:
    xosc = tmp_path / "scenario.xosc"
    xodr = tmp_path / "road.xodr"
    xosc.write_text("<OpenSCENARIO version='1.1'/>")
    xodr.write_text("<OpenDRIVE revMajor='1' revMinor='6'/>")
    return str(xosc), str(xodr)


def test_unconfigured_live_session_is_explicit_and_hashes_inputs(tmp_path: Path) -> None:
    xosc, xodr = _files(tmp_path)
    service = LiveSessionService(tmp_path)

    session = service.create("scenario-1", xosc, xodr, 0.05)
    payload = session.frame()

    assert payload["contract_version"] == "esmini-live-session-v1"
    assert payload["status"] == "unavailable"
    assert payload["unavailable_reason"] == "esminiLib_not_configured"
    assert payload["xosc_sha256"].startswith("sha256:")
    assert payload["xodr_sha256"].startswith("sha256:")
    assert payload["rendering"]["screenshot_stream"] is False
    assert payload["objects"] == []


def test_live_session_rejects_unconfined_and_invalid_inputs(tmp_path: Path) -> None:
    xosc, xodr = _files(tmp_path)
    service = LiveSessionService(tmp_path)

    with pytest.raises(ValueError, match="xosc_path_outside_project_root"):
        service.create("scenario-1", "/tmp/other.xosc", xodr, 0.05)
    with pytest.raises(ValueError, match="timestep_s"):
        service.create("scenario-1", xosc, xodr, 2.0)


def test_unavailable_session_validates_commands_without_native_execution(tmp_path: Path) -> None:
    xosc, xodr = _files(tmp_path)
    session = LiveSessionService(tmp_path).create("scenario-1", xosc, xodr, 0.05)

    result = session.command("camera", {"mode": "in-car", "yaw_rad": 0.2})

    assert result["message_type"] == "command_result"
    with pytest.raises(ValueError, match="invalid_live_control_fields"):
        session.command("control", {"throttle": 2})


def test_fake_native_binding_supports_lifecycle_and_timestamped_state(tmp_path: Path) -> None:
    xosc, xodr = _files(tmp_path)
    session = LiveSessionService(tmp_path, "fake.so", binding_factory=FakeBinding).create("scenario-1", xosc, xodr, 0.05)

    assert session.status == "paused"
    stepped = session.command("step")
    assert stepped["simulation_time_s"] == 0.05
    assert stepped["objects"][0]["x_m"] == 0.05
    session.command("pause")
    session.command("reset")
    assert session.simulation_time_s == 0.0


def test_native_command_capabilities_separate_supported_reset_and_control(tmp_path: Path) -> None:
    xosc, xodr = _files(tmp_path)
    session = LiveSessionService(tmp_path, "fake.so", binding_factory=FakeBinding).create(
        "scenario-1", xosc, xodr, 0.05
    )

    capabilities = session.metadata()["command_capabilities"]
    assert capabilities["reset"]["available"] is True
    assert capabilities["reset"]["implementation"] == "reload_same_artifact_pair"
    assert capabilities["control"]["available"] is False
    session.command("control", {"actor_id": "ego", "throttle": 0.2})
