from __future__ import annotations

from motion_capture.geometry.landmarks import (
    FINGER_JOINTS,
    FINGER_NAMES,
    FINGERTIPS,
    HAND_CONNECTIONS,
    NUM_HAND_LANDMARKS,
)


def test_hand_connections_match_mediapipe():
    import mediapipe as mp

    ours = {tuple(sorted(pair)) for pair in HAND_CONNECTIONS}
    theirs = {tuple(sorted(pair)) for pair in mp.solutions.hands.HAND_CONNECTIONS}
    assert ours == theirs
    assert len(HAND_CONNECTIONS) == len(ours)  # no duplicates


def test_every_finger_has_three_joints_ending_at_its_tip():
    assert tuple(FINGER_JOINTS) == FINGER_NAMES
    for finger, joints in FINGER_JOINTS.items():
        assert len(joints) == 3
        assert joints[-1][-1] == FINGERTIPS[finger]
        for joint in joints:
            assert all(0 <= idx < NUM_HAND_LANDMARKS for idx in joint)
