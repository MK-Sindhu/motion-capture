"""The stages of a matching session: WAITING -> COUNTDOWN -> RUNNING.

    WAITING    the reference loops; waiting for a thumbs up (or SPACE)
    COUNTDOWN  the reference is rewound and held still for `countdown_sec`
               seconds while the player puts their hand back on the veena
    RUNNING    frames are compared and scored

The clock is passed in, so tests can move time forward without waiting.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum


class Phase(Enum):
    WAITING = "waiting"
    COUNTDOWN = "countdown"
    RUNNING = "running"


class Session:
    def __init__(
        self, countdown_sec: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.countdown_sec = countdown_sec
        self._clock = clock
        self.phase = Phase.WAITING
        # Clock time at which the countdown finishes
        self._countdown_end = 0.0

    def start_countdown(self) -> None:
        """Start counting down (thumbs up or SPACE seen). Only valid while waiting."""
        if self.phase is not Phase.WAITING:
            raise RuntimeError(f"cannot start the countdown while {self.phase.value}")
        self.phase = Phase.COUNTDOWN
        self._countdown_end = self._clock() + self.countdown_sec

    def tick(self) -> Phase:
        """Switch COUNTDOWN to RUNNING once time is up; return the phase."""
        if self.phase is Phase.COUNTDOWN and self._clock() >= self._countdown_end:
            self.phase = Phase.RUNNING
        return self.phase

    def seconds_left(self) -> float:
        """Seconds until the countdown ends (0 if not counting down)."""
        if self.phase is not Phase.COUNTDOWN:
            return 0.0
        return max(0.0, self._countdown_end - self._clock())
