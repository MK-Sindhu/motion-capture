from __future__ import annotations

import pytest

from motion_capture.tracking.sides import assign_sides
from motion_capture.tracking.types import Side
from tests.helpers import make_detection


def test_no_detections_means_no_hands():
    assert assign_sides([]) == {}


@pytest.mark.parametrize(
    "labels", [("Right", "Right"), ("Left", "Left"), ("Right", "Left")]
)
def test_two_hands_are_assigned_by_position_not_label(labels):
    on_left = make_detection(labels[0], wrist_x=0.2)
    on_right = make_detection(labels[1], wrist_x=0.8)

    for order in ([on_left, on_right], [on_right, on_left]):
        hands = assign_sides(order)
        assert hands[Side.LEFT].image_points is on_left.image_points
        assert hands[Side.RIGHT].image_points is on_right.image_points
        assert hands[Side.LEFT].side is Side.LEFT
        assert hands[Side.RIGHT].side is Side.RIGHT


@pytest.mark.parametrize(
    ("label", "side"), [("Left", Side.LEFT), ("Right", Side.RIGHT)]
)
def test_single_hand_uses_mediapipe_label(label, side):
    detection = make_detection(label, wrist_x=0.9)
    hands = assign_sides([detection])
    assert list(hands) == [side]
    assert hands[side].world_points is detection.world_points


def test_more_than_two_hands_is_a_bug():
    with pytest.raises(ValueError):
        assign_sides([make_detection("Left", x) for x in (0.1, 0.5, 0.9)])
