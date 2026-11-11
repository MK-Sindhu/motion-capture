"""The veena program, run headless on sample clips, must match the original numbers."""

from __future__ import annotations

import io

import pytest

from motion_capture.apps.veena_match import run_veena_match
from motion_capture.cli.main import main
from motion_capture.config.settings import TrackerConfig, VeenaConfig
from motion_capture.rendering.window import KEY_SPACE, HeadlessWindow
from motion_capture.tracking.hands import HandTracker
from motion_capture.video.sources import LoopingVideo, open_video
from tests.integration.conftest import GOLDEN, TOLERANCE

pytestmark = pytest.mark.integration


def _check_against_golden(report: dict, golden: dict) -> None:
    assert report["frames_running"] == golden["frames_running"]
    assert set(report["hands"]) == set(golden["hands"])
    for side, expected in golden["hands"].items():
        hand = report["hands"][side]
        assert hand["frames_compared"] == expected["frames_compared"]
        assert hand["mean_error_deg"] == pytest.approx(
            expected["mean_error_deg"], abs=TOLERANCE
        )
        assert hand["finger_errors_deg"] == pytest.approx(
            expected["fingers"], abs=TOLERANCE
        )
    assert report["mean_error_deg"] == pytest.approx(
        golden["mean_error_deg"], abs=TOLERANCE
    )
    assert report["score_pct"] == pytest.approx(golden["score_pct"], abs=TOLERANCE)


@pytest.mark.parametrize("case", sorted(GOLDEN["veena"]))
def test_run_veena_match_reproduces_golden_numbers(case, clips):
    golden = GOLDEN["veena"][case]
    config = VeenaConfig(
        reference=clips[golden["reference_clip"]],
        countdown_sec=0,
        reference_is_mirrored=golden["reference_mirrored"],
    )
    # SPACE on the first frame starts the countdown, like the original harness.
    window = HeadlessWindow(keys={0: KEY_SPACE})
    out = io.StringIO()
    with (
        open_video(clips[golden["camera_clip"]]) as camera,
        LoopingVideo(open_video(config.reference)) as reference,
        HandTracker(TrackerConfig()) as user,
        HandTracker(TrackerConfig()) as ref,
    ):
        report = run_veena_match(camera, reference, user, ref, window, config, out=out)

    assert report is not None
    _check_against_golden(report.to_dict(), golden)
    assert f"Match Score: {golden['score_pct']:.1f}%" in out.getvalue()
    # The final score screen was shown after the session frames.
    assert window.frames_shown == golden["frames_running"] + 2


def test_cli_veena_prints_the_score_and_saves_nothing(clips, tmp_path, capsys):
    golden = GOLDEN["veena"]["different_pose"]
    status = main(
        [
            "veena",
            "--video",
            str(clips[golden["camera_clip"]]),
            "--reference",
            str(clips[golden["reference_clip"]]),
            "--countdown",
            "0",
        ],
        window_factory=lambda title, max_width: HeadlessWindow(keys={0: KEY_SPACE}),
    )
    assert status == 0
    printed = capsys.readouterr().out
    assert f"Match Score: {golden['score_pct']:.1f}%" in printed
    assert "Biggest difference: Left hand" in printed
    # The test runs inside the empty tmp_path folder: no score file appeared.
    assert list(tmp_path.iterdir()) == []


def test_cli_veena_without_starting_records_nothing(clips, capsys):
    status = main(
        [
            "veena",
            "--video",
            str(clips["pointing_up"]),
            "--reference",
            str(clips["pointing_up"]),
        ],
        # No SPACE and no thumbs up in the clip: the session never starts.
        window_factory=lambda title, max_width: HeadlessWindow(),
    )
    assert status == 0
    assert "No finger comparison recorded" in capsys.readouterr().out
