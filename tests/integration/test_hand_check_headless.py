"""The hand-check program, run headless on sample clips, must match the original."""

from __future__ import annotations

import io

import pytest

from motion_capture.apps.hand_check import run_hand_check
from motion_capture.cli.main import main
from motion_capture.config.settings import HandCheckConfig, TrackerConfig
from motion_capture.rendering.window import HeadlessWindow
from motion_capture.tracking.hands import HandTracker
from motion_capture.tracking.types import Side
from motion_capture.video.sources import open_video
from tests.integration.conftest import GOLDEN, TOLERANCE

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("case", sorted(GOLDEN["hand_check"]))
def test_run_hand_check_reproduces_golden_numbers(case, clips):
    golden = GOLDEN["hand_check"][case]
    window = HeadlessWindow()
    out = io.StringIO()
    with (
        open_video(clips[golden["clip"]]) as source,
        HandTracker(TrackerConfig()) as tracker,
    ):
        result = run_hand_check(source, tracker, window, HandCheckConfig(), out=out)

    assert result.frames == golden["frames"]
    assert window.frames_shown == golden["frames"]
    for side in Side:
        assert result.tracked[side] == golden["tracked"][side.value]
        expected = golden["mean_bends_deg"].get(side.value)
        if expected is None:
            assert result.mean_bends(side) is None
        else:
            assert result.mean_bends(side) == pytest.approx(expected, abs=TOLERANCE)
    assert "Left hand (fretting) tracked in 100% of frames" in out.getvalue()


def test_cli_hand_check_on_a_video(clips, capsys):
    status = main(
        ["hand-check", "--video", str(clips["pointing_up"])],
        window_factory=lambda title, max_width: HeadlessWindow(),
    )
    assert status == 0
    out = capsys.readouterr().out
    assert "40 frames in" in out
    assert "Right hand (plucking) tracked in 0% of frames  <- move the camera" in out
