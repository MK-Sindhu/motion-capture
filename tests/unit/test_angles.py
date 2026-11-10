from __future__ import annotations

import numpy as np
import pytest

from motion_capture.geometry.angles import (
    finger_bends,
    finger_joint_angles,
    joint_angle,
)
from motion_capture.geometry.landmarks import FINGER_NAMES
from tests.helpers import make_world_points


@pytest.mark.parametrize(
    ("a", "b", "c", "expected"),
    [
        ((0, 1, 0), (0, 0, 0), (0, -1, 0), 180.0),  # straight
        ((1, 0, 0), (0, 0, 0), (0, 1, 0), 90.0),  # right angle
        ((1, 0, 0), (0, 0, 0), (1, 1, 0), 45.0),
        ((0, 0, 1), (0, 0, 0), (0, 0, 2), 0.0),  # folded back on itself
    ],
)
def test_joint_angle_known_shapes(a, b, c, expected):
    assert joint_angle(a, b, c) == pytest.approx(expected, abs=0.1)


def test_joint_angle_is_finite_when_points_coincide():
    assert np.isfinite(joint_angle((0, 0, 0), (0, 0, 0), (1, 0, 0)))


def test_straight_hand_has_straight_joints_and_no_bend():
    world = make_world_points()
    for angles in finger_joint_angles(world).values():
        assert angles == pytest.approx([180.0, 180.0, 180.0], abs=0.1)
    assert finger_bends(world) == pytest.approx({f: 0.0 for f in FINGER_NAMES}, abs=0.1)


def test_bent_finger_angles_and_bend():
    world = make_world_points({"Index": (10.0, 40.0, 70.0)})
    angles = finger_joint_angles(world)
    assert angles["Index"] == pytest.approx([170.0, 140.0, 110.0], abs=0.1)
    assert angles["Middle"] == pytest.approx([180.0, 180.0, 180.0], abs=0.1)
    assert finger_bends(world)["Index"] == pytest.approx(40.0, abs=0.1)


def test_angles_do_not_depend_on_hand_size():
    world = make_world_points({"Ring": (30.0, 30.0, 30.0)})
    small = finger_joint_angles(world)["Ring"]
    large = finger_joint_angles(world * 2.5)["Ring"]
    assert large == pytest.approx(small, abs=0.1)


@pytest.mark.xfail(
    strict=True,
    reason="Known bias: the + 1e-6 in joint_angle is not negligible for metre-scale "
    "MediaPipe world points (finger bones ~0.03 m), so a straight joint reads "
    "~177.3 deg. Kept for now so the refactor doesn't change any scores; fixing "
    "it means updating tests/golden/golden.json.",
)
def test_straight_joint_at_real_finger_scale_reads_180():
    bone = 0.03  # metres, a typical finger bone in MediaPipe world coordinates
    assert joint_angle((0, bone, 0), (0, 0, 0), (0, -bone, 0)) == pytest.approx(
        180.0, abs=0.1
    )
