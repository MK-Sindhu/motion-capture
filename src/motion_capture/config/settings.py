"""All settings, grouped by what they affect, with their default values.

Each group is a frozen (read-only) dataclass, so settings can't be changed by
accident halfway through a run. Values are checked as soon as they are
created; a bad value raises ConfigError naming the setting.

Where values come from (later ones win):
    1. the defaults written below
    2. a TOML file (motion-capture.toml), see motion-capture.example.toml
    3. command-line flags, e.g. --camera 1

See config/loader.py for how 2 and 3 are applied.

Note: the type annotations here are read at runtime by the loader to check
TOML values, so they stay simple (int, float, bool, Path, tuple[int, int]).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from motion_capture.errors import ConfigError


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


@dataclass(frozen=True)
class CameraConfig:
    """Which webcam to open and at what size."""

    # 0 = first camera the OS lists, 1 = second, ... On a Mac, a nearby iPhone
    # (Continuity Camera) can take number 0 and push the Mac's own camera to 1.
    index: int = 0
    # (width, height) in pixels to ask the webcam for. Fingers are small, so more
    # pixels = sharper fingers = more accurate points. The camera may deliver a
    # different size if it doesn't support this one.
    resolution: tuple[int, int] = (1280, 720)

    def __post_init__(self) -> None:
        _require(self.index >= 0, "camera.index must be 0 or more")
        _require(
            len(self.resolution) == 2 and all(v > 0 for v in self.resolution),
            "camera.resolution must be two positive numbers, e.g. [1280, 720]",
        )


@dataclass(frozen=True)
class TrackerConfig:
    """MediaPipe hand tracker options (used for both the webcam and the reference)."""

    # 1 or 2. The left/right assignment assumes at most one fretting and one
    # plucking hand.
    max_num_hands: int = 2
    # 0 = lite model (faster), 1 = full model (more accurate).
    model_complexity: int = 1
    # How sure (0..1) the model must be before it reports a NEW hand.
    min_detection_confidence: float = 0.5
    # If confidence in a hand it is already following drops below this, the
    # hand counts as lost and the model searches again.
    min_tracking_confidence: float = 0.5

    def __post_init__(self) -> None:
        _require(self.max_num_hands in (1, 2), "tracker.max_num_hands must be 1 or 2")
        _require(
            self.model_complexity in (0, 1), "tracker.model_complexity must be 0 or 1"
        )
        for name in ("min_detection_confidence", "min_tracking_confidence"):
            value = getattr(self, name)
            _require(0.0 <= value <= 1.0, f"tracker.{name} must be between 0 and 1")


@dataclass(frozen=True)
class VeenaConfig:
    """The veena finger-matching program (`motion-capture veena`)."""

    # Reference clip to compare against. A relative path in a TOML file is
    # relative to that file's folder; on the command line, to the current folder.
    reference: Path = Path("data/references/veena_reference.mp4")
    # Average finger-joint error (degrees) that scores 0%. Below it a hand is
    # drawn green, at or above it red. Raise it to be more forgiving.
    angle_threshold_deg: float = 20.0
    # How many frames in a row the thumbs up must be seen before starting
    # (stops a single wrong detection from starting the session).
    start_gesture_frames: int = 3
    # Seconds to put your hand back on the veena after the thumbs up.
    countdown_sec: float = 3.0
    # True only if the reference clip is already a mirrored (selfie) recording.
    reference_is_mirrored: bool = False
    # The window starts at most this wide (pixels) so it fits on screen.
    max_window_width: int = 1600

    def __post_init__(self) -> None:
        _require(self.angle_threshold_deg > 0, "veena.angle_threshold_deg must be > 0")
        _require(
            self.start_gesture_frames >= 1, "veena.start_gesture_frames must be >= 1"
        )
        _require(self.countdown_sec >= 0, "veena.countdown_sec must be 0 or more")
        _require(self.max_window_width > 0, "veena.max_window_width must be > 0")


@dataclass(frozen=True)
class HandCheckConfig:
    """The live tracking check (`motion-capture hand-check`)."""

    # How many past positions of each fingertip to draw as a trail
    # (10 frames is about 1/3 of a second at 30 FPS).
    trail_length: int = 10
    # A finger bent this much (degrees) fills its bar completely.
    max_bend_deg: float = 120.0

    def __post_init__(self) -> None:
        _require(self.trail_length >= 1, "hand_check.trail_length must be >= 1")
        _require(self.max_bend_deg > 0, "hand_check.max_bend_deg must be > 0")


@dataclass(frozen=True)
class Settings:
    """Every setting, one attribute per TOML section."""

    camera: CameraConfig = field(default_factory=CameraConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    veena: VeenaConfig = field(default_factory=VeenaConfig)
    hand_check: HandCheckConfig = field(default_factory=HandCheckConfig)
