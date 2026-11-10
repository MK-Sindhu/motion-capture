"""Plain data types for tracked hands. No MediaPipe types leave the tracking package.

Converting MediaPipe's results into these numpy-based objects at one place
(tracking/hands.py) means the rest of the program, and its tests, never
depend on MediaPipe. Switching to a different tracker later only changes
tracking/hands.py.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray


class Side(str, Enum):
    """The player's own left or right hand."""

    LEFT = "Left"
    RIGHT = "Right"

    def __str__(self) -> str:
        return self.value


# Both hands, in the order they are listed everywhere (panels, reports).
SIDES: tuple[Side, ...] = (Side.LEFT, Side.RIGHT)

# What each hand does on a veena.
HAND_ROLES: Mapping[Side, str] = {Side.LEFT: "fretting", Side.RIGHT: "plucking"}


@dataclass(frozen=True)
class Detection:
    """One hand as found by the tracker, before we decide which hand it is.

    image_points: 21 x 2, the (x, y) of each landmark as fractions of the image
        size: x = 0 at the left edge, 1 at the right; y = 0 at the TOP, 1 at
        the bottom. Multiply by the image width/height to get pixels.
    world_points: 21 x 3, the same points in 3D, in metres, measured from
        roughly the centre of the hand. Used for angles.
    label: MediaPipe's own guess, "Left" or "Right" (assumes a mirrored image).
    """

    image_points: NDArray[np.float64]
    world_points: NDArray[np.float64]
    label: str


@dataclass(frozen=True)
class Hand:
    """A hand once we know whether it is the player's left or right hand."""

    side: Side
    image_points: NDArray[np.float64]
    world_points: NDArray[np.float64]


# What a tracker returns for one frame: {Side.LEFT: Hand, Side.RIGHT: Hand},
# with only the hands that were found.
HandsBySide = dict[Side, Hand]
