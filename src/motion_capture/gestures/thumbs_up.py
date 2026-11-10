"""The thumbs-up start gesture."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from numpy.typing import NDArray

from motion_capture.geometry.landmarks import INDEX_TIP, MIDDLE_TIP, THUMB_IP, THUMB_TIP


def is_thumbs_up(image_points: NDArray[np.float64]) -> bool:
    """True if the hand looks like a thumbs up.

    image_points: the hand's 21 x 2 points as fractions of the image size.
    In images y = 0 is the TOP, so a smaller y means higher up. A thumbs up
    has the thumb tip above the thumb's own joint, and the index and middle
    fingertips below that joint (fingers curled into a fist).
    """
    y = image_points[:, 1]
    return bool(
        y[THUMB_TIP] < y[THUMB_IP]
        and y[INDEX_TIP] > y[THUMB_IP]
        and y[MIDDLE_TIP] > y[THUMB_IP]
    )


class ThumbsUpDetector:
    """Says "start" once a thumbs up has been seen in enough frames in a row.

    Requiring several frames in a row stops a single wrong detection from
    starting the session.
    """

    def __init__(self, required_frames: int) -> None:
        self.required_frames = required_frames
        # How many frames in a row a thumbs up has been seen
        self.streak = 0

    def update(self, hands: Iterable[NDArray[np.float64]]) -> bool:
        """Feed one frame's hands (their image_points); True once the gesture counts."""
        if any(is_thumbs_up(points) for points in hands):
            self.streak += 1
        else:
            # Streak broken: start counting again
            self.streak = 0
        return self.streak >= self.required_frames
