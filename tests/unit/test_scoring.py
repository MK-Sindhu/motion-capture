from __future__ import annotations

import pytest

from motion_capture.geometry.landmarks import FINGER_NAMES
from motion_capture.scoring.compare import finger_errors, hand_error
from motion_capture.scoring.report import ScoreAccumulator, score_from_error
from motion_capture.tracking.types import Side
from tests.helpers import make_hand


@pytest.mark.parametrize(
    ("error", "expected"), [(0, 100.0), (5, 75.0), (10, 50.0), (20, 0.0), (35, 0.0)]
)
def test_score_from_error(error, expected):
    assert score_from_error(error, threshold_deg=20) == pytest.approx(expected)


def test_identical_hands_have_no_error():
    hand = make_hand(turns={"Index": (20, 30, 40)})
    errors = finger_errors(hand, hand)
    assert list(errors) == list(FINGER_NAMES)
    assert errors == pytest.approx({f: 0.0 for f in FINGER_NAMES}, abs=0.1)


def test_error_is_measured_per_finger():
    straight = make_hand()
    curled_middle = make_hand(turns={"Middle": (30, 30, 30)})
    errors = finger_errors(curled_middle, straight)
    assert errors["Middle"] == pytest.approx(30.0, abs=0.1)
    assert errors["Index"] == pytest.approx(0.0, abs=0.1)
    assert hand_error(errors) == pytest.approx(6.0, abs=0.1)


def _per_finger(value: float, **overrides: float) -> dict[str, float]:
    errors = {f: value for f in FINGER_NAMES}
    errors.update(overrides)
    return errors


def test_no_comparisons_means_no_report():
    acc = ScoreAccumulator()
    acc.start_frame()
    assert acc.report(threshold_deg=20) is None


def test_report_numbers():
    acc = ScoreAccumulator()
    # Frame 1: both hands compared; frame 2: only the left hand was found.
    acc.start_frame()
    acc.add(Side.LEFT, _per_finger(4.0, Pinky=14.0), hand_error=6.0)
    acc.add(Side.RIGHT, _per_finger(10.0), hand_error=10.0)
    acc.start_frame()
    acc.add(Side.LEFT, _per_finger(4.0, Pinky=14.0), hand_error=6.0)

    report = acc.report(threshold_deg=20)
    assert report is not None
    left, right = report.hands
    assert (left.side, right.side) == (Side.LEFT, Side.RIGHT)
    assert left.mean_error_deg == pytest.approx(6.0)
    assert left.score_pct == pytest.approx(70.0)
    assert left.coverage_pct == pytest.approx(100.0)
    assert right.coverage_pct == pytest.approx(50.0)
    assert left.finger_errors_deg["Pinky"] == pytest.approx(14.0)
    # Overall = mean of every per-frame hand error: (6 + 10 + 6) / 3
    assert report.mean_error_deg == pytest.approx(22 / 3)
    assert (report.worst_side, report.worst_finger) == (Side.LEFT, "Pinky")


def test_report_text_matches_the_original_script_format():
    acc = ScoreAccumulator()
    acc.start_frame()
    acc.add(Side.LEFT, _per_finger(5.0), hand_error=5.0)
    report = acc.report(threshold_deg=20)
    assert report is not None
    assert report.format_text() == "\n".join(
        [
            "",
            "Compared 1 frames",
            "",
            "Left hand (fretting): avg error 5.0 deg, score 75.0%  "
            "(tracked in 100% of frames)",
            "    Thumb     5.0 deg",
            "    Index     5.0 deg",
            "    Middle    5.0 deg",
            "    Ring      5.0 deg",
            "    Pinky     5.0 deg",
            "",
            "Average finger-joint error: 5.0 deg",
            "Match Score: 75.0%",
            "Biggest difference: Left hand, Thumb",
        ]
    )


def test_report_to_dict_is_json_friendly():
    import json

    acc = ScoreAccumulator()
    acc.start_frame()
    acc.add(Side.RIGHT, _per_finger(2.0), hand_error=2.0)
    report = acc.report(threshold_deg=20)
    assert report is not None
    data = json.loads(json.dumps(report.to_dict()))
    assert data["hands"]["Right"]["role"] == "plucking"
    assert data["score_pct"] == pytest.approx(90.0)
    assert data["biggest_difference"] == {"hand": "Right", "finger": "Thumb"}
