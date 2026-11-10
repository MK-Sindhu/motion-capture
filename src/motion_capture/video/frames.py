"""Small helpers for video frames.

A frame is a numpy array of shape (height, width, 3): one row per pixel row,
3 colour values per pixel in OpenCV's Blue-Green-Red order (not RGB).
"""

from __future__ import annotations

from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

Frame = NDArray[np.uint8]


def as_frame(image: Any) -> Frame:
    """Tell the type checker an OpenCV result is an 8-bit frame.

    OpenCV's type stubs describe every image as a generic array; frames read
    from cameras and video files, and anything derived from them here, are
    always 8-bit.
    """
    return cast(Frame, image)


def mirror(frame: Frame) -> Frame:
    """Flip left <-> right, like looking in a mirror (selfie view)."""
    return as_frame(cv2.flip(frame, 1))


def bgr_to_rgb(frame: Frame) -> Frame:
    """OpenCV gives BGR colour order; MediaPipe expects RGB."""
    return as_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


def resize(frame: Frame, size: tuple[int, int]) -> Frame:
    """Resize to (width, height) pixels (the aspect ratio is not kept)."""
    return as_frame(cv2.resize(frame, size))
