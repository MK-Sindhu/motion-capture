from __future__ import annotations

import numpy as np

from motion_capture.geometry.landmarks import INDEX_TIP, MIDDLE_TIP, THUMB_IP, THUMB_TIP
from motion_capture.gestures.thumbs_up import ThumbsUpDetector, is_thumbs_up


def _points(thumb_tip_y: float, finger_tip_y: float) -> np.ndarray:
    """21 x 2 points with the thumb joint at y=0.5 and chosen tip heights."""
    pts = np.full((21, 2), 0.5)
    pts[THUMB_IP, 1] = 0.5
    pts[THUMB_TIP, 1] = thumb_tip_y
    pts[INDEX_TIP, 1] = finger_tip_y
    pts[MIDDLE_TIP, 1] = finger_tip_y
    return pts


THUMBS_UP = _points(
    thumb_tip_y=0.3, finger_tip_y=0.6
)  # thumb above, fingers curled below
OPEN_HAND = _points(
    thumb_tip_y=0.3, finger_tip_y=0.2
)  # fingertips above the thumb joint
THUMBS_DOWN = _points(thumb_tip_y=0.7, finger_tip_y=0.6)


def test_is_thumbs_up():
    assert is_thumbs_up(THUMBS_UP)
    assert not is_thumbs_up(OPEN_HAND)
    assert not is_thumbs_up(THUMBS_DOWN)


def test_detector_needs_enough_frames_in_a_row():
    detector = ThumbsUpDetector(required_frames=3)
    assert not detector.update([THUMBS_UP])
    assert not detector.update([THUMBS_UP])
    assert detector.update([THUMBS_UP])


def test_detector_streak_resets_on_a_miss_or_no_hands():
    detector = ThumbsUpDetector(required_frames=2)
    detector.update([THUMBS_UP])
    assert not detector.update([OPEN_HAND])
    detector.update([THUMBS_UP])
    assert not detector.update([])
    assert detector.streak == 0


def test_detector_accepts_thumbs_up_from_either_hand():
    detector = ThumbsUpDetector(required_frames=1)
    assert detector.update([OPEN_HAND, THUMBS_UP])
