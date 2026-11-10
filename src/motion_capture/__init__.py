"""motion_capture: compare hand and finger movements in a webcam feed with a
reference video.

The package is split into one sub-package per concern:

    config/     settings: defaults, TOML file, command-line overrides
    geometry/   hand landmark numbering and joint-angle maths (pure numpy)
    tracking/   MediaPipe hand tracker -> plain numpy Hand objects
    video/      opening cameras and video files, frame helpers
    gestures/   start gesture (thumbs up)
    scoring/    comparing two hands, accumulating errors, final report
    session/    waiting -> countdown -> running state machine
    rendering/  drawing skeletons, panels and text; the display window
    apps/       the programs themselves (hand check, veena match)
    cli/        the `motion-capture` command

See docs/architecture.md for how the pieces fit together.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("motion-capture")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
