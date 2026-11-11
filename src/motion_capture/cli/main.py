"""The `motion-capture` command.

    motion-capture hand-check [--camera N | --video PATH] [--trail-length N]
    motion-capture veena --reference PATH [--camera N | --video PATH]
                         [--threshold DEG] [--countdown SEC]

The score is printed at the end and shown on screen; it isn't saved anywhere.

Settings come from the defaults, then motion-capture.toml (or --config), then
these flags. Exit status: 0 = success, 1 = an error such as a missing file or
camera (printed as "error: ..."), 2 = invalid command-line usage,
130 = interrupted with Ctrl+C.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

from motion_capture import __version__
from motion_capture.config.loader import load_settings
from motion_capture.config.settings import Settings
from motion_capture.errors import MotionCaptureError, VideoError
from motion_capture.rendering.window import OpenCVWindow, Window
from motion_capture.video.sources import VideoSource, open_camera, open_video

log = logging.getLogger("motion_capture")

# Creates the display window: (title, max_width) -> Window. Tests pass one
# that returns a HeadlessWindow.
WindowFactory = Callable[[str, "int | None"], Window]


def main(
    argv: Sequence[str] | None = None, *, window_factory: WindowFactory | None = None
) -> int:
    """Run the command line; returns the exit status."""
    args = build_parser().parse_args(argv)
    make_window: WindowFactory = window_factory or OpenCVWindow
    with native_logs_hidden(enabled=not args.verbose):
        _configure_logging(args.verbose)
        try:
            settings = load_settings(args.config, overrides_from_args(args))
            if args.command == "hand-check":
                return _run_hand_check(args, settings, make_window)
            return _run_veena(args, settings, make_window)
        except MotionCaptureError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("interrupted", file=sys.stderr)
            return 130


@contextmanager
def native_logs_hidden(enabled: bool) -> Iterator[None]:
    """Hide MediaPipe's C++ log lines while keeping Python's own stderr visible.

    MediaPipe's C++ code writes INFO / W0000 lines (GL context, XNNPACK,
    feedback tensors) straight to file descriptor 2, from its own threads and
    ignoring the usual GLOG / TF log-level variables. So for the whole run,
    descriptor 2 goes to /dev/null, and Python's sys.stderr (our errors,
    warnings and tracebacks) is pointed at a copy of the real terminal.

    Only done when stderr is a terminal: when it is redirected (to a file, CI
    logs, pytest) everything is left alone. Restored afterwards, even on errors.
    """
    if not enabled or not os.isatty(2):
        yield
        return
    sys.stderr.flush()
    original_stderr = sys.stderr
    terminal = os.fdopen(os.dup(2), "w", buffering=1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 2)
    os.close(devnull)
    sys.stderr = terminal
    try:
        yield
    finally:
        terminal.flush()
        os.dup2(terminal.fileno(), 2)
        sys.stderr = original_stderr
        terminal.close()


# ---------------------------------------------------------------- arguments


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="motion-capture",
        description="Compare finger movements in your webcam with a reference video.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    # Options shared by every command
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        help="settings file (default: ./motion-capture.toml if it exists)",
    )
    source = common.add_mutually_exclusive_group()
    source.add_argument(
        "--camera", type=int, metavar="N", help="webcam number (default 0)"
    )
    source.add_argument(
        "--video",
        type=Path,
        metavar="PATH",
        help="use a recorded video of YOUR hands instead of the webcam",
    )
    common.add_argument(
        "--resolution",
        type=_resolution,
        metavar="WxH",
        help="webcam resolution to ask for, e.g. 1280x720",
    )
    common.add_argument(
        "-v", "--verbose", action="store_true", help="show detailed and MediaPipe logs"
    )

    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    hand_check = commands.add_parser(
        "hand-check",
        parents=[common],
        help="live check that your hands and fingers are tracked (no scoring)",
        description="Show tracked hands, fingertip trails and finger bend. ESC quits.",
    )
    hand_check.add_argument(
        "--trail-length", type=int, metavar="N", help="frames of fingertip trail"
    )
    hand_check.add_argument(
        "--max-bend", type=float, metavar="DEG", help="bend that fills a bar"
    )

    veena = commands.add_parser(
        "veena",
        parents=[common],
        help="score your finger movements against a reference video",
        description=(
            "Reference on the left, you on the right. Thumbs up (or SPACE) starts, "
            "ESC finishes and shows the score."
        ),
    )
    veena.add_argument("--reference", type=Path, metavar="PATH", help="reference clip")
    veena.add_argument(
        "--threshold",
        type=float,
        metavar="DEG",
        help="average finger-joint error that scores 0%% (default 20)",
    )
    veena.add_argument(
        "--countdown", type=float, metavar="SEC", help="seconds before scoring starts"
    )
    veena.add_argument(
        "--start-frames",
        type=int,
        metavar="N",
        help="frames in a row the thumbs up must be seen",
    )
    veena.add_argument(
        "--reference-mirrored",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="the reference clip is already a mirrored (selfie) recording",
    )
    return parser


def overrides_from_args(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    """Settings from the flags the user actually gave (unset flags are None)."""
    wanted = {
        "camera": {"index": "camera", "resolution": "resolution"},
        "hand_check": {"trail_length": "trail_length", "max_bend_deg": "max_bend"},
        "veena": {
            "reference": "reference",
            "angle_threshold_deg": "threshold",
            "countdown_sec": "countdown",
            "start_gesture_frames": "start_frames",
            "reference_is_mirrored": "reference_mirrored",
        },
    }
    overrides: dict[str, dict[str, Any]] = {}
    for section, keys in wanted.items():
        for key, attr in keys.items():
            value = getattr(args, attr, None)
            if value is not None:
                overrides.setdefault(section, {})[key] = value
    return overrides


def _resolution(text: str) -> tuple[int, int]:
    """Parse "1280x720" into (1280, 720)."""
    try:
        width, height = (int(part) for part in text.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected WIDTHxHEIGHT, e.g. 1280x720, got {text!r}"
        ) from None
    return width, height


def _configure_logging(verbose: bool) -> None:
    # force=True: replace handlers from an earlier call (they may point at an
    # old sys.stderr; see native_logs_hidden).
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )


# ---------------------------------------------------------------- commands


def _open_user_source(args: argparse.Namespace, settings: Settings) -> VideoSource:
    """Your hands: a recorded video if --video was given, otherwise the webcam."""
    if args.video is not None:
        return open_video(args.video)
    return open_camera(settings.camera.index, settings.camera.resolution)


def _run_hand_check(
    args: argparse.Namespace, settings: Settings, make_window: WindowFactory
) -> int:
    # Imported here, not at the top: loading MediaPipe takes about a second,
    # which `--help` and argument errors shouldn't have to wait for.
    from motion_capture.apps.hand_check import WINDOW_TITLE, run_hand_check
    from motion_capture.tracking.hands import HandTracker

    with ExitStack() as stack:
        source = stack.enter_context(_open_user_source(args, settings))
        tracker = stack.enter_context(HandTracker(settings.tracker))
        window = make_window(WINDOW_TITLE, None)
        stack.callback(window.close)
        run_hand_check(source, tracker, window, settings.hand_check)
    return 0


def _run_veena(
    args: argparse.Namespace, settings: Settings, make_window: WindowFactory
) -> int:
    from motion_capture.apps.veena_match import WINDOW_TITLE, run_veena_match
    from motion_capture.tracking.hands import HandTracker
    from motion_capture.video.sources import LoopingVideo

    config = settings.veena
    if not config.reference.is_file():
        raise VideoError(
            f"Reference video not found: {config.reference}. Pass --reference PATH "
            "or set [veena] reference in motion-capture.toml."
        )

    with ExitStack() as stack:
        reference = stack.enter_context(LoopingVideo(open_video(config.reference)))
        camera = stack.enter_context(_open_user_source(args, settings))
        # One tracker per stream (see tracking/hands.py)
        user_tracker = stack.enter_context(HandTracker(settings.tracker))
        reference_tracker = stack.enter_context(HandTracker(settings.tracker))
        window = make_window(WINDOW_TITLE, config.max_window_width)
        stack.callback(window.close)
        # Prints the score and shows the final screen. The score is not saved.
        run_veena_match(
            camera, reference, user_tracker, reference_tracker, window, config
        )
    return 0
