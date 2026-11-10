"""Collect the per-frame errors of a session and turn them into the final report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from motion_capture.geometry.landmarks import FINGER_NAMES
from motion_capture.tracking.types import HAND_ROLES, SIDES, Side


def score_from_error(error_deg: float, threshold_deg: float) -> float:
    """Turn an average angle error into a percentage.

    0 deg of error -> 100%, error at/above the threshold -> 0%, in a straight
    line between. With a 20 deg threshold: 5 deg -> 75%, 10 deg -> 50%.
    """
    return max(0.0, 100.0 * (1.0 - error_deg / threshold_deg))


@dataclass(frozen=True)
class HandReport:
    side: Side
    # Average error over every frame this hand was compared in
    mean_error_deg: float
    score_pct: float
    # Number of frames in which this hand was found in BOTH videos
    frames_compared: int
    # frames_compared as a % of all running frames
    coverage_pct: float
    # Average error of each finger, in FINGER_NAMES order
    finger_errors_deg: dict[str, float]


@dataclass(frozen=True)
class Report:
    frames_running: int
    threshold_deg: float
    hands: tuple[HandReport, ...]
    # Average of every per-frame hand error, both hands together
    mean_error_deg: float
    score_pct: float
    # The (hand, finger) with the largest average error
    worst_side: Side
    worst_finger: str

    def to_dict(self) -> dict[str, Any]:
        """A JSON-friendly version (for --output report.json)."""
        return {
            "frames_running": self.frames_running,
            "threshold_deg": self.threshold_deg,
            "mean_error_deg": self.mean_error_deg,
            "score_pct": self.score_pct,
            "biggest_difference": {
                "hand": self.worst_side.value,
                "finger": self.worst_finger,
            },
            "hands": {
                hand.side.value: {
                    "role": HAND_ROLES[hand.side],
                    "mean_error_deg": hand.mean_error_deg,
                    "score_pct": hand.score_pct,
                    "frames_compared": hand.frames_compared,
                    "coverage_pct": hand.coverage_pct,
                    "finger_errors_deg": dict(hand.finger_errors_deg),
                }
                for hand in self.hands
            },
        }

    def format_text(self) -> str:
        """The summary printed in the terminal at the end of a session."""
        lines = ["", f"Compared {self.frames_running} frames"]
        for hand in self.hands:
            lines += [
                "",
                f"{hand.side} hand ({HAND_ROLES[hand.side]}): avg error "
                f"{hand.mean_error_deg:.1f} deg, score {hand.score_pct:.1f}%  "
                f"(tracked in {hand.coverage_pct:.0f}% of frames)",
            ]
            lines += [
                f"    {finger:<7} {err:5.1f} deg"
                for finger, err in hand.finger_errors_deg.items()
            ]
        lines += [
            "",
            f"Average finger-joint error: {self.mean_error_deg:.1f} deg",
            f"Match Score: {self.score_pct:.1f}%",
            f"Biggest difference: {self.worst_side} hand, {self.worst_finger}",
        ]
        return "\n".join(lines)


class ScoreAccumulator:
    """Keeps every per-frame error while a session runs."""

    def __init__(self) -> None:
        # How many frames were in the RUNNING phase (compared or not)
        self.frames_running = 0
        # hand_errors[Side.LEFT] = that hand's error in each frame it was compared
        self.hand_errors: dict[Side, list[float]] = {side: [] for side in SIDES}
        # finger_errors[(Side.LEFT, "Index")] = that finger's error in each frame,
        # in the order the pairs were first seen (used to break ties for "worst")
        self.finger_errors: dict[tuple[Side, str], list[float]] = {}

    def start_frame(self) -> None:
        """Count one RUNNING frame (call it even if no hand could be compared)."""
        self.frames_running += 1

    def add(self, side: Side, per_finger: dict[str, float], hand_error: float) -> None:
        """Record one hand's comparison for the current frame."""
        for finger, err in per_finger.items():
            self.finger_errors.setdefault((side, finger), []).append(err)
        self.hand_errors[side].append(hand_error)

    def report(self, threshold_deg: float) -> Report | None:
        """The final report, or None if no hand was ever compared."""
        compared = [side for side in SIDES if self.hand_errors[side]]
        if not compared:
            return None

        hands = []
        for side in compared:
            errors = self.hand_errors[side]
            mean_error = float(np.mean(errors))
            hands.append(
                HandReport(
                    side=side,
                    mean_error_deg=mean_error,
                    score_pct=score_from_error(mean_error, threshold_deg),
                    frames_compared=len(errors),
                    coverage_pct=100.0 * len(errors) / self.frames_running,
                    finger_errors_deg={
                        f: float(np.mean(self.finger_errors[(side, f)]))
                        for f in FINGER_NAMES
                    },
                )
            )

        overall = float(
            np.mean(np.concatenate([self.hand_errors[side] for side in compared]))
        )
        worst_side, worst_finger = max(
            self.finger_errors, key=lambda key: np.mean(self.finger_errors[key])
        )
        return Report(
            frames_running=self.frames_running,
            threshold_deg=threshold_deg,
            hands=tuple(hands),
            mean_error_deg=overall,
            score_pct=score_from_error(overall, threshold_deg),
            worst_side=worst_side,
            worst_finger=worst_finger,
        )
