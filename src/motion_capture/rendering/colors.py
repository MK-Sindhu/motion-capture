"""Named colours.

OpenCV writes colours as (Blue, Green, Red), NOT (Red, Green, Blue).
"""

from __future__ import annotations

from collections.abc import Mapping

from motion_capture.tracking.types import Side

Color = tuple[int, int, int]

GREEN: Color = (0, 255, 0)
RED: Color = (0, 0, 255)
YELLOW: Color = (0, 255, 255)
WHITE: Color = (255, 255, 255)
GREY: Color = (90, 90, 90)

# hand-check: one colour per hand
SIDE_COLORS: Mapping[Side, Color] = {
    Side.LEFT: (255, 170, 0),  # blue
    Side.RIGHT: (0, 200, 255),  # orange
}

# MediaPipe's default drawing style, used for the reference hands.
MEDIAPIPE_WHITE: Color = (224, 224, 224)
MEDIAPIPE_RED: Color = (0, 0, 255)
