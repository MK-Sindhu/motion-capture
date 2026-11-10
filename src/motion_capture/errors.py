"""Errors the program reports to the user as a short message (no traceback).

The CLI catches MotionCaptureError, prints "error: <message>" and exits with
status 1. Anything else is a bug and keeps its full traceback.
"""

from __future__ import annotations


class MotionCaptureError(Exception):
    """Base class for expected, user-facing errors."""


class ConfigError(MotionCaptureError):
    """A settings file or value is invalid (unknown key, wrong type, out of range)."""


class CameraError(MotionCaptureError):
    """A webcam could not be opened or stopped delivering frames."""


class VideoError(MotionCaptureError):
    """A video file is missing, unreadable or empty."""
