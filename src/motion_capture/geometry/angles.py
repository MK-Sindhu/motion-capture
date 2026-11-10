"""Joint-angle maths for a hand's 3D points (pure numpy, no camera or MediaPipe).

All functions take `world_points`: a 21 x 3 array where row i is the (x, y, z)
of landmark point i in metres, as estimated by MediaPipe. Using 3D points
means a finger bending toward or away from the camera is still measured; on
the flat image the same bend would look much smaller or larger.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from motion_capture.geometry.landmarks import FINGER_JOINTS


def joint_angle(a: ArrayLike, b: ArrayLike, c: ArrayLike) -> float:
    """Angle in degrees at point b, between the lines b->a and b->c.

    Uses the dot-product rule: cos(angle) = (ba . bc) / (|ba| * |bc|).
    """
    # Arrows from the joint b to the points a and c
    ba = np.array(a) - np.array(b)
    bc = np.array(c) - np.array(b)
    # + 1e-6 avoids dividing by zero if two points land on top of each other
    cosang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    # Rounding can push cosang slightly past +-1, where arccos is undefined,
    # so clip it into range first. arccos gives radians; convert to degrees.
    return float(np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0))))


def finger_joint_angles(
    world_points: NDArray[np.float64],
) -> dict[str, NDArray[np.float64]]:
    """The 3 joint angles of each finger: {"Thumb": array([a1, a2, a3]), ...}.

    180 = straight joint; smaller = more bent.
    """
    pts = world_points
    return {
        finger: np.array([joint_angle(pts[a], pts[b], pts[c]) for a, b, c in joints])
        for finger, joints in FINGER_JOINTS.items()
    }


def finger_bends(world_points: NDArray[np.float64]) -> dict[str, float]:
    """How bent each finger is, in degrees: 0 = straight, larger = more curled.

    A finger's bend is 180 minus the average of its 3 joint angles.
    """
    return {
        finger: float(180.0 - np.mean(angles))
        for finger, angles in finger_joint_angles(world_points).items()
    }
