from __future__ import annotations

import numpy as np
import pytest

from motion_capture.rendering.draw import Style, draw_skeleton, to_pixel
from tests.helpers import make_image_points, make_world_points


def _mediapipe_drawing(image_points, point_spec=None, bone_spec=None):
    """Draw with MediaPipe's own drawing_utils, for comparison."""
    import mediapipe as mp
    from mediapipe.framework.formats import landmark_pb2

    landmarks = landmark_pb2.NormalizedLandmarkList()
    for x, y in image_points:
        landmarks.landmark.add(x=float(x), y=float(y), z=0.0)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    args = [] if point_spec is None else [point_spec, bone_spec]
    mp.solutions.drawing_utils.draw_landmarks(
        frame, landmarks, mp.solutions.hands.HAND_CONNECTIONS, *args
    )
    return frame


def _hand_points(shift_x: float = 0.0) -> np.ndarray:
    world = make_world_points({"Index": (20, 40, 60), "Pinky": (10, 10, 10)})
    points = make_image_points(world, wrist_x=0.5 + shift_x)
    # MediaPipe stores coordinates as 32-bit floats, so real image_points always
    # hold float32 values; round the same way so both drawings see equal input.
    return points.astype(np.float32).astype(np.float64)


@pytest.mark.parametrize("shift_x", [0.0, 0.42])  # 0.42 pushes some points off-image
def test_default_style_matches_mediapipe_pixel_for_pixel(shift_x):
    points = _hand_points(shift_x)
    ours = np.zeros((240, 320, 3), dtype=np.uint8)
    draw_skeleton(ours, points)
    np.testing.assert_array_equal(ours, _mediapipe_drawing(points))


def test_custom_style_matches_mediapipe_pixel_for_pixel():
    from mediapipe.python.solutions.drawing_utils import DrawingSpec

    points = _hand_points()
    spec = DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3)
    ours = np.zeros((240, 320, 3), dtype=np.uint8)
    style = Style((0, 255, 0), thickness=2, circle_radius=3)
    draw_skeleton(ours, points, style, style)
    np.testing.assert_array_equal(ours, _mediapipe_drawing(points, spec, spec))


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (0.0, 0.0, (0, 0)),
        (0.5, 0.25, (160, 60)),
        (1.0, 1.0, (319, 239)),  # clamped to the last pixel
        (-0.01, 0.5, None),  # outside the image: not drawn
        (0.5, 1.01, None),
    ],
)
def test_to_pixel(x, y, expected):
    assert to_pixel(x, y, 320, 240) == expected
