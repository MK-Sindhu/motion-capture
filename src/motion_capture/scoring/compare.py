"""Compare one of your hands with the same hand in the reference, for one frame."""

from __future__ import annotations

import numpy as np

from motion_capture.geometry.angles import finger_joint_angles
from motion_capture.geometry.landmarks import FINGER_NAMES
from motion_capture.tracking.types import Hand


def finger_errors(user: Hand, reference: Hand) -> dict[str, float]:
    """Error of each finger in degrees: {"Thumb": 4.2, "Index": 10.0, ...}.

    A finger's error is the average of |your angle - reference angle| over its
    3 joints, using the 3D joint angles of both hands.
    """
    user_angles = finger_joint_angles(user.world_points)
    ref_angles = finger_joint_angles(reference.world_points)
    return {
        finger: float(np.mean(np.abs(user_angles[finger] - ref_angles[finger])))
        for finger in FINGER_NAMES
    }


def hand_error(per_finger: dict[str, float]) -> float:
    """Error of the whole hand: the average over its 5 fingers."""
    return float(np.mean(list(per_finger.values())))
