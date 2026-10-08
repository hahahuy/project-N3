from pathlib import Path
import sys

import pytest

from real2scenario import EsminiConfig, parse_esmini_csv_trace, run_esmini


TRACE_HEADER = "time, id, name, x, y, z, h, p, r, speed, wheel_angle, wheel_rot\n"
TRACE_ROWS = "0, 0, ego, 0, 0, 0, 0, 0, 0, 2, 0, 0\n1, 0, ego, 2, 0, 0, 0, 0, 0, 2, 0, 0\n"


def _fake_esmini(tmp_path: Path, body: str) -> Path:
    executable = tmp_path / "fake_esmini.py"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if '--version' in sys.argv:\n"
        "    print('esmini fake 1.0')\n"
        "    raise SystemExit(0)\n"
        + body,
        encoding="utf-8",
    )
    return executable


def _fake_dat2csv(tmp_path: Path) -> Path:
    converter = tmp_path / "fake_dat2csv.py"
    converter.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if '--version' in sys.argv:\n"
        "    print('dat2csv fake 1.0')\n"
        "    raise SystemExit(0)\n"
        "output = sys.argv[sys.argv.index('--csv') + 1]\n"
        f"open(output, 'w', encoding='utf-8').write({TRACE_HEADER!r} + {TRACE_ROWS!r})\n",
        encoding="utf-8",
    )
    return converter


def test_runner_captures_success_version_and_normalized_trace(tmp_path: Path) -> None:
    scenario = tmp_path / "baseline.xosc"
    scenario.write_text("<OpenSCENARIO/>", encoding="utf-8")
    executable = _fake_esmini(
        tmp_path,
        "recording = sys.argv[sys.argv.index('--record') + 1]\n"
        "open(recording, 'wb').write(b'fake dat')\n"
        "print('replay complete')\n",
    )
    converter = _fake_dat2csv(tmp_path)

    report = run_esmini(
        scenario,
        tmp_path / "trace.csv",
        EsminiConfig(
            executable=(sys.executable, str(executable)),
            trace_converter=(sys.executable, str(converter)),
        ),
    )

    assert report.completed
    assert report.exit_code == 0
    assert report.stdout == "replay complete\n"
    assert report.tool_version == "esmini fake 1.0"
    assert "--fixed_timestep" in report.command
    assert "0.05" in report.command
    assert report.trace is not None
    assert report.trace.states_for("ego")[1].x_m == 2.0


def test_runner_records_nonzero_exit_and_stderr(tmp_path: Path) -> None:
    scenario = tmp_path / "baseline.xosc"
    scenario.write_text("<OpenSCENARIO/>", encoding="utf-8")
    executable = _fake_esmini(tmp_path, "print('bad scenario', file=sys.stderr)\nraise SystemExit(7)\n")

    report = run_esmini(
        scenario, tmp_path / "trace.csv", EsminiConfig(executable=(sys.executable, str(executable)))
    )

    assert not report.completed
    assert report.exit_code == 7
    assert report.stderr == "bad scenario\n"
    assert report.tool_version == "esmini fake 1.0"


def test_trace_parser_rejects_empty_and_invalid_trace(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text(TRACE_HEADER, encoding="utf-8")
    invalid = tmp_path / "invalid.csv"
    invalid.write_text("time_s,actor_id\n0,ego\n", encoding="utf-8")

    with pytest.raises(ValueError, match="empty"):
        parse_esmini_csv_trace(empty)
    with pytest.raises(ValueError, match="exactly"):
        parse_esmini_csv_trace(invalid)
