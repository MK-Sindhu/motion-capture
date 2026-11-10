"""The MediaPipe hand tracker. This is the ONLY module that imports mediapipe.

It turns MediaPipe's results into plain numpy `Detection` / `Hand` objects
(see tracking/types.py), so nothing else depends on MediaPipe's types.
Porting to a different tracker (e.g. MediaPipe 1.x's HandLandmarker) only
means rewriting this file.

How the tracker estimates 3D points from a flat webcam image: its neural
network was trained on real and computer-generated hands with known 3D
positions, so it predicts depth from cues like foreshortening, overlap and
hand anatomy. It is an estimate, not a measurement.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import mediapipe as mp
import numpy as np

from motion_capture.config.settings import TrackerConfig
from motion_capture.tracking.sides import assign_sides
from motion_capture.tracking.types import Detection, HandsBySide
from motion_capture.video.frames import Frame, bgr_to_rgb


class HandTracker:
    """Finds up to two hands in each frame of ONE video stream.

    Use one tracker per stream: in video mode the tracker follows each hand
    from frame to frame, so sharing one between the webcam and the reference
    clip would make each stream's predictions pollute the other's.
    """

    def __init__(self, config: TrackerConfig) -> None:
        self._hands = mp.solutions.hands.Hands(
            # Video mode: find the hand once, then follow it from frame to
            # frame (faster and steadier than searching every frame).
            static_image_mode=False,
            max_num_hands=config.max_num_hands,
            model_complexity=config.model_complexity,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        )

    def detect(self, frame: Frame) -> list[Detection]:
        """Every hand in a BGR frame, before deciding which is left or right."""
        result = self._hands.process(bgr_to_rgb(frame))
        if not result.multi_hand_landmarks:
            return []
        # MediaPipe returns three parallel lists, one entry per hand found.
        return [
            Detection(
                image_points=_points(image_lm, ("x", "y")),
                world_points=_points(world_lm, ("x", "y", "z")),
                label=handedness.classification[0].label,
            )
            for image_lm, world_lm, handedness in zip(
                result.multi_hand_landmarks,
                result.multi_hand_world_landmarks,
                result.multi_handedness,
            )
        ]

    def process(self, frame: Frame) -> HandsBySide:
        """The hands in a mirrored BGR frame, keyed by the player's left / right."""
        return assign_sides(self.detect(frame))

    def close(self) -> None:
        self._hands.close()

    def __enter__(self) -> HandTracker:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def _points(landmark_list: Any, axes: tuple[str, ...]) -> np.ndarray:
    """A MediaPipe landmark list as a 21 x len(axes) float array."""
    return np.array(
        [[getattr(p, axis) for axis in axes] for p in landmark_list.landmark],
        dtype=np.float64,
    )
