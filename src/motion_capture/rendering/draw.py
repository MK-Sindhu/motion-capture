"""Drawing hands and text on frames, with plain OpenCV.

draw_skeleton() reproduces MediaPipe's own drawing_utils.draw_landmarks()
pixel for pixel (a test checks this), without needing MediaPipe's types.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from motion_capture.geometry.landmarks import HAND_CONNECTIONS, WRIST
from motion_capture.rendering.colors import (
    MEDIAPIPE_RED,
    MEDIAPIPE_WHITE,
    WHITE,
    YELLOW,
    Color,
)
from motion_capture.video.frames import Frame


@dataclass(frozen=True)
class Style:
    """How to draw points or bones: colour, line thickness (px), dot radius (px)."""

    color: Color
    thickness: int = 2
    circle_radius: int = 2


# MediaPipe's default look: red dots, light-grey bones.
DEFAULT_POINT_STYLE = Style(MEDIAPIPE_RED)
DEFAULT_BONE_STYLE = Style(MEDIAPIPE_WHITE)


def to_pixel(x: float, y: float, width: int, height: int) -> tuple[int, int] | None:
    """A point given as fractions of the image size, in pixels.

    None if the point lies outside the image (it is then not drawn), exactly
    like MediaPipe's drawing code.
    """

    def inside(value: float) -> bool:
        return (value > 0 or math.isclose(0, value)) and (
            value < 1 or math.isclose(1, value)
        )

    if not (inside(x) and inside(y)):
        return None
    return min(math.floor(x * width), width - 1), min(
        math.floor(y * height), height - 1
    )


def draw_skeleton(
    frame: Frame,
    image_points: NDArray[np.float64],
    point_style: Style = DEFAULT_POINT_STYLE,
    bone_style: Style = DEFAULT_BONE_STYLE,
    connections: Sequence[tuple[int, int]] = HAND_CONNECTIONS,
) -> None:
    """Draw a hand: lines along the bones, then a dot on each of the 21 points."""
    height, width = frame.shape[:2]
    pixels = {}
    for idx, (x, y) in enumerate(image_points):
        px = to_pixel(float(x), float(y), width, height)
        if px is not None:
            pixels[idx] = px

    # Bones first, only where both ends are inside the image
    for start, end in connections:
        if start in pixels and end in pixels:
            cv2.line(
                frame,
                pixels[start],
                pixels[end],
                bone_style.color,
                bone_style.thickness,
            )

    # Then the dots on top: a light ring, then the coloured dot
    for px in pixels.values():
        ring_radius = max(
            point_style.circle_radius + 1, int(point_style.circle_radius * 1.2)
        )
        cv2.circle(frame, px, ring_radius, MEDIAPIPE_WHITE, point_style.thickness)
        cv2.circle(
            frame,
            px,
            point_style.circle_radius,
            point_style.color,
            point_style.thickness,
        )


def put_text(
    frame: Frame,
    text: str,
    org: tuple[int, int],
    scale: float = 1.0,
    color: Color = YELLOW,
    thickness: int = 2,
    antialiased: bool = False,
) -> None:
    """Write text. org = (x, y) pixel position of the text's bottom-left corner."""
    line_type = cv2.LINE_AA if antialiased else cv2.LINE_8
    cv2.putText(
        frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, line_type
    )


def put_label_at_wrist(
    frame: Frame,
    image_points: NDArray[np.float64],
    text: str,
    color: Color = WHITE,
    dx: int = -40,
    antialiased: bool = False,
) -> None:
    """Write a label just below the hand's wrist (in images, y grows downward)."""
    height, width = frame.shape[:2]
    x, y = image_points[WRIST]
    org = (int(x * width) + dx, int(y * height) + 30)
    put_text(frame, text, org, 0.7, color, 2, antialiased=antialiased)


def draw_trail(frame: Frame, trail: Sequence[tuple[int, int]], color: Color) -> None:
    """Join recent fingertip positions with lines, thicker toward the newest."""
    for i in range(1, len(trail)):
        # i / len(trail) goes from ~0 (oldest) to 1 (newest): thickness 1 -> 4 px
        thickness = 1 + 3 * i // len(trail)
        cv2.line(frame, trail[i - 1], trail[i], color, thickness, cv2.LINE_AA)
