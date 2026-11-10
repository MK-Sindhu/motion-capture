"""Test helpers: synthetic hands with known joint angles, and a fake clock."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray

from motion_capture.geometry.landmarks import FINGER_NAMES, NUM_HAND_LANDMARKS
from motion_capture.tracking.types import Detection, Hand, Side

# Landmark numbers of each finger's 4 points, from the base to the tip.
_CHAINS = {
    "Thumb": (1, 2, 3, 4),
    "Index": (5, 6, 7, 8),
    "Middle": (9, 10, 11, 12),
    "Ring": (13, 14, 15, 16),
    "Pinky": (17, 18, 19, 20),
}
# Unit-length bones keep the + 1e-6 in joint_angle negligible (see test_angles.py).
_BONE_LENGTH = 1.0

# Direction each finger points away from the wrist, spread out in the x-y plane.
_SPREAD_DEG = {"Thumb": -60, "Index": -20, "Middle": 0, "Ring": 20, "Pinky": 40}


def make_world_points(
    turns: Mapping[str, tuple[float, float, float]] | None = None,
) -> NDArray[np.float64]:
    """A 21 x 3 hand where each finger's joints bend by the given angles (degrees).

    turns["Index"] = (t1, t2, t3) bends the index finger's three joints by t1,
    t2, t3 degrees, curling out of the x-y plane like a real finger, so the
    joint angles are exactly 180 - t. Fingers not listed stay straight.
    """
    turns = turns or {}
    pts = np.zeros((NUM_HAND_LANDMARKS, 3))
    for finger in FINGER_NAMES:
        spread = np.radians(_SPREAD_DEG[finger])
        flat = np.array([np.sin(spread), -np.cos(spread), 0.0])  # "up" the image
        out = np.array([0.0, 0.0, -1.0])  # towards the camera
        phi = 0.0
        position = np.zeros(3)
        for step, idx in enumerate(_CHAINS[finger]):
            if step > 0:
                phi += np.radians(turns.get(finger, (0.0, 0.0, 0.0))[step - 1])
            direction = np.cos(phi) * flat + np.sin(phi) * out
            position = position + _BONE_LENGTH * direction
            pts[idx] = position
    return pts


def make_image_points(
    world: NDArray[np.float64], wrist_x: float = 0.5
) -> NDArray[np.float64]:
    """Project world points onto a fake image, with the wrist at x = wrist_x."""
    image = 0.5 + 0.1 * world[:, :2]
    image[:, 0] += wrist_x - image[0, 0]
    return image


def make_hand(side: Side = Side.LEFT, turns=None, wrist_x: float = 0.5) -> Hand:
    world = make_world_points(turns)
    return Hand(side, make_image_points(world, wrist_x), world)


def make_detection(label: str, wrist_x: float, turns=None) -> Detection:
    world = make_world_points(turns)
    return Detection(make_image_points(world, wrist_x), world, label)


class FakeClock:
    """A clock that only moves when told to."""

    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
