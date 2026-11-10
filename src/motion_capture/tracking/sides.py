"""Decide which detected hand is the player's left and which is the right."""

from __future__ import annotations

from collections.abc import Sequence

from motion_capture.geometry.landmarks import WRIST
from motion_capture.tracking.types import Detection, Hand, HandsBySide, Side


def assign_sides(detections: Sequence[Detection]) -> HandsBySide:
    """Map detections to the player's own left / right hand.

    Expects detections from a mirrored (selfie-view) image, which is what
    MediaPipe's handedness labels assume; there the player's right hand is on
    the image's right.

    With two hands, sort by position instead of trusting MediaPipe's label: on
    a veena the fretting hand is always on the neck side and the plucking hand
    on the resonator side, while the label is often the same for both hands.
    With one hand there is nothing to compare, so use MediaPipe's label.
    """
    if not detections:
        return {}

    if len(detections) == 2:
        # The hand whose wrist is further left on screen (smaller x) is the left hand.
        left, right = sorted(detections, key=lambda d: d.image_points[WRIST, 0])
        return {
            Side.LEFT: Hand(Side.LEFT, left.image_points, left.world_points),
            Side.RIGHT: Hand(Side.RIGHT, right.image_points, right.world_points),
        }

    if len(detections) > 2:
        # TrackerConfig limits the tracker to two hands, so this is a bug.
        raise ValueError(f"expected at most 2 hands, got {len(detections)}")

    only = detections[0]
    side = Side(only.label)
    return {side: Hand(side, only.image_points, only.world_points)}
