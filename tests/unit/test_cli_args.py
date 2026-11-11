from __future__ import annotations

from pathlib import Path

import pytest

from motion_capture import __version__
from motion_capture.cli import main as cli
from motion_capture.errors import CameraError


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    # The CLI reads ./motion-capture.toml if present; keep tests independent of one.
    monkeypatch.chdir(tmp_path)


def parse(*argv: str):
    return cli.build_parser().parse_args(argv)


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        [],  # no command
        ["dance"],  # unknown command
        ["veena", "--threshold", "lots"],
        ["hand-check", "--camera", "1", "--video", "x.mp4"],  # pick one source
        ["hand-check", "--resolution", "big"],
    ],
)
def test_bad_usage_exits_with_status_2(argv):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2


def test_veena_has_no_option_to_save_the_score(capsys):
    # Scores are only printed and shown, not saved (there's no --output yet).
    with pytest.raises(SystemExit) as exc:
        cli.main(["veena", "--output", "report.json"])
    assert exc.value.code == 2
    assert "unrecognized arguments: --output" in capsys.readouterr().err


def test_only_given_flags_become_overrides():
    assert cli.overrides_from_args(parse("veena")) == {}
    args = parse(
        "veena",
        "--camera",
        "1",
        "--resolution",
        "640x480",
        "--threshold",
        "25",
        "--no-reference-mirrored",
        "--reference",
        "clip.mp4",
    )
    assert cli.overrides_from_args(args) == {
        "camera": {"index": 1, "resolution": (640, 480)},
        "veena": {
            "angle_threshold_deg": 25.0,
            "reference_is_mirrored": False,
            "reference": Path("clip.mp4"),
        },
    }


def test_hand_check_flags():
    args = parse("hand-check", "--trail-length", "5", "--max-bend", "90")
    assert cli.overrides_from_args(args) == {
        "hand_check": {"trail_length": 5, "max_bend_deg": 90.0}
    }


def test_missing_reference_is_a_friendly_error(capsys):
    assert cli.main(["veena", "--reference", "nope.mp4"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: Reference video not found: nope.mp4")
    assert "--reference" in err


def test_invalid_flag_value_is_reported_as_a_flag(capsys):
    assert cli.main(["veena", "--countdown", "-2"]) == 1
    assert "command-line flags: veena.countdown_sec" in capsys.readouterr().err


def test_bad_config_file_is_reported(tmp_path, capsys):
    (tmp_path / "motion-capture.toml").write_text("[camera]\nindx = 1\n")
    assert cli.main(["hand-check"]) == 1
    assert "unknown key 'indx'" in capsys.readouterr().err


def test_camera_that_cannot_open(monkeypatch, capsys):
    def fail(index, resolution):
        raise CameraError(f"Cannot open webcam (device {index}).")

    monkeypatch.setattr(cli, "open_camera", fail)
    assert cli.main(["hand-check", "--camera", "9"]) == 1
    assert "error: Cannot open webcam (device 9)." in capsys.readouterr().err


def test_ctrl_c_exits_with_status_130(monkeypatch, capsys):
    def interrupted(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_run_hand_check", interrupted)
    assert cli.main(["hand-check"]) == 130
    assert "interrupted" in capsys.readouterr().err
