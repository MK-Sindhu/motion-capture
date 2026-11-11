"""Shared test cases that keep the Python package and the website in step.

The website (website/) runs in the browser, so it re-implements the program's
logic in TypeScript: joint angles, left/right assignment, the thumbs-up start,
the session stages, scoring, the final report and the hand-check summary.

This module builds fixed inputs (synthetic hands, scripted sessions), runs them
through the Python code and saves inputs + outputs to

    website/tests/fixtures/parity-cases.json

The website's tests (website/tests/parity.test.ts) feed the same inputs to the
TypeScript code and must produce the same numbers and the same text.
tests/unit/test_parity_cases.py re-runs the Python side on the saved inputs, so
the file can't silently go out of date.

After changing the Python logic on purpose, regenerate the file with

    python -m tests.parity_cases

and then make the website match (its parity tests will show what differs).
"""

from __future__ import annotations

import dataclasses
import io
import json
import math
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import numpy as np

from motion_capture.apps.hand_check import run_hand_check
from motion_capture.apps.veena_match import run_veena_match
from motion_capture.config.settings import (
    CameraConfig,
    HandCheckConfig,
    Settings,
    TrackerConfig,
    VeenaConfig,
)
from motion_capture.errors import ConfigError
from motion_capture.geometry import landmarks
from motion_capture.geometry.angles import (
    finger_bends,
    finger_joint_angles,
    joint_angle,
)
from motion_capture.geometry.landmarks import FINGER_NAMES
from motion_capture.gestures.thumbs_up import ThumbsUpDetector, is_thumbs_up
from motion_capture.rendering.window import KEY_ESC, KEY_SPACE, HeadlessWindow
from motion_capture.scoring.compare import finger_errors, hand_error
from motion_capture.scoring.report import ScoreAccumulator, score_from_error
from motion_capture.session.state import Session
from motion_capture.tracking.sides import assign_sides
from motion_capture.tracking.types import (
    HAND_ROLES,
    SIDES,
    Detection,
    Hand,
    HandsBySide,
    Side,
)
from motion_capture.video.sources import LoopingVideo
from tests.helpers import FakeClock, make_world_points

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "website"
    / "tests"
    / "fixtures"
    / "parity-cases.json"
)

# Numbers may differ in the last few binary digits between Python and
# JavaScript (or between machines), e.g. when numpy uses fused multiply-add.
# Text output must match exactly.
TOLERANCE = 1e-9

KEYS = {"space": KEY_SPACE, "esc": KEY_ESC}


# ---------------------------------------------------------------- inputs


def _pool_hand(k: int) -> dict[str, Any]:
    """The k-th synthetic hand: every finger bent differently, at real scale."""
    turns = {
        finger: tuple(float((17 * k + 29 * fi + 11 * j) % 80) for j in range(3))
        for fi, finger in enumerate(FINGER_NAMES)
    }
    # Real finger bones are about 3 cm long, so the + 1e-6 in joint_angle
    # matters here just as it does for MediaPipe's points.
    world = make_world_points(turns) * 0.03
    # A fixed wobble so the hand isn't perfectly flat or perfectly regular.
    world = world + 0.002 * np.sin(np.arange(63).reshape(21, 3) * (k + 1.3))
    image = 0.5 + 2.0 * world[:, :2]
    # Spread the wrists across the image (left/right is decided by wrist x).
    image[:, 0] += 0.1 * ((k % 5) - 2)
    if k in (0, 1):
        # Thumbs up: thumb tip above its joint, index and middle tips below it.
        image[4, 1] = image[3, 1] - 0.05
        image[8, 1] = image[3, 1] + 0.05
        image[12, 1] = image[3, 1] + 0.06
    if k == 11:
        # Two points on top of each other: a zero-length bone.
        world[6] = world[5]
        world[15] = world[14]
    return {"world": world.tolist(), "image": image.tolist()}


def make_inputs() -> dict[str, Any]:
    """Every input, built from fixed formulas (no randomness)."""
    pool = [_pool_hand(k) for k in range(12)]
    p = [np.array(h["world"]) for h in pool]

    joint_angle_cases = [
        # straight, right angle, folded back, zero-length bone, unit scale
        [[0, 0, 0], [0, 1, 0], [0, 2, 0]],
        [[1, 0, 0], [0, 0, 0], [0, 1, 0]],
        [[0, 1, 0], [0, 0, 0], [0, 1, 0]],
        [[0, 0, 0], [0, 0, 0], [1, 0, 0]],
        [[0.0, 0.0, 0.0], [0.0, 0.03, 0.0], [0.0, 0.06, 0.0]],
    ] + [
        [p[k][i].tolist(), p[k][i + 1].tolist(), p[k][i + 2].tolist()]
        for k, i in [(0, 0), (1, 5), (2, 9), (3, 13), (4, 17), (5, 1), (6, 2), (11, 4)]
    ]

    def det(hand: int, label: str) -> list[Any]:
        return [hand, label]

    assign_sides_cases = [
        [],
        [det(2, "Left")],
        [det(3, "Right")],
        # Both labelled "Left" (common on a veena): position decides.
        [det(4, "Left"), det(5, "Left")],
        [det(5, "Right"), det(4, "Right")],
        [det(6, "Right"), det(7, "Left")],
    ]

    thumbs_up_sequences = [
        {"required_frames": 3, "frames": [[0], [0], [2], [0], [1], [0, 2], [3], [1]]},
        {"required_frames": 1, "frames": [[], [4], [1], [5, 6], [0]]},
    ]

    session_scripts = [
        {
            "countdown_sec": 2.0,
            "ops": [
                ["tick"],
                ["start"],
                ["advance", 0.5],
                ["tick"],
                ["advance", 1.5],
                ["tick"],
                ["advance", 0.25],
                ["tick"],
                ["start"],
            ],
        },
        {"countdown_sec": 0.0, "ops": [["start"], ["tick"], ["advance", 1.0]]},
    ]

    compare_pairs = [[0, 1], [2, 3], [4, 4], [5, 9], [10, 11], [7, 6]]

    score_cases = [
        [0.0, 20.0],
        [5.0, 20.0],
        [10.0, 20.0],
        [20.0, 20.0],
        [35.0, 20.0],
        [3.3, 25.0],
        [12.75, 15.0],
    ]

    def pairs(*sides: list[int] | None) -> dict[str, Any]:
        return {"Left": sides[0], "Right": sides[1]}

    accumulator_scenarios = [
        {
            "name": "both hands, some frames missing",
            "threshold_deg": 20.0,
            "frames": [
                pairs([2, 3], [4, 5]),
                pairs([2, 6], None),
                pairs(None, None),
                pairs([7, 3], [4, 9]),
                pairs([8, 3], [10, 5]),
                pairs(None, [11, 5]),
                pairs([2, 2], [4, 4]),
                pairs([9, 3], [6, 5]),
                pairs([2, 3], [4, 5]),
                pairs([3, 2], [5, 4]),
            ],
        },
        {
            # 5 of 8 frames = 62.5% coverage: an exact tie when rounded to a
            # whole number (Python rounds ties to even: 62%).
            "name": "coverage tie",
            "threshold_deg": 25.0,
            "frames": [pairs([2, 3], None)] * 5 + [pairs(None, None)] * 3,
        },
        {
            "name": "identical hands",
            "threshold_deg": 20.0,
            "frames": [pairs([4, 4], [6, 6])] * 3,
        },
        {
            "name": "nothing compared",
            "threshold_deg": 20.0,
            "frames": [pairs(None, None)],
        },
    ]

    format_cases = [
        [0.5, 0],
        [1.5, 0],
        [2.5, 0],
        [62.5, 0],
        [37.5, 0],
        [0.25, 1],
        [1.25, 1],
        [0.35, 1],
        [2.675, 2],
        [99.95, 1],
        [7.0, 1],
        [123.456, 1],
        [0.04, 0],
    ]

    invalid_settings = [
        ["camera", "resolution", [0, 720]],
        ["tracker", "max_num_hands", 3],
        ["tracker", "min_detection_confidence", 1.5],
        ["tracker", "min_tracking_confidence", -0.1],
        ["veena", "angle_threshold_deg", 0.0],
        ["veena", "start_gesture_frames", 0],
        ["veena", "countdown_sec", -1.0],
        ["hand_check", "trail_length", 0],
        ["hand_check", "max_bend_deg", 0.0],
    ]

    def frame_hands(*entries: list[Any]) -> list[list[Any]]:
        return [list(e) for e in entries]

    # User hands per camera frame / reference hands per reference frame.
    two = frame_hands([2, "Left"], [3, "Left"])
    wave = [
        two,
        frame_hands([4, "Right"], [5, "Left"]),
        frame_hands([6, "Left"]),
        [],
        frame_hands([7, "Right"], [8, "Right"]),
        frame_hands([9, "Right"]),
    ]
    reference_frames = [
        frame_hands([3, "Left"], [2, "Right"]),
        frame_hands([5, "Left"], [4, "Left"]),
        frame_hands([8, "Left"]),
        frame_hands([9, "Right"], [10, "Left"]),
        [],
        frame_hands([6, "Right"]),
        frame_hands([2, "Left"], [7, "Right"]),
    ]
    thumbs = frame_hands([0, "Right"])

    veena_scenarios = [
        {
            "name": "thumbs up starts it, ESC stops it",
            "config": {
                "countdown_sec": 0.1,
                "start_gesture_frames": 3,
                "angle_threshold_deg": 30.0,
                "reference_is_mirrored": False,
            },
            "fps": 30,
            "user": [wave[2], wave[3], wave[0], wave[5]]
            + [thumbs] * 3
            + [wave[i % 6] for i in range(33)],
            "reference": reference_frames,
            "keys": {"35": "esc"},
        },
        {
            "name": "SPACE starts it, the camera runs out, mirrored reference",
            "config": {
                "countdown_sec": 0.0,
                "start_gesture_frames": 3,
                "angle_threshold_deg": 15.0,
                "reference_is_mirrored": True,
            },
            "fps": 30,
            "user": [wave[(i * 5) % 6] for i in range(20)],
            "reference": reference_frames[:5],
            "keys": {"2": "space", "4": "space"},
        },
        {
            "name": "interrupted thumbs up, then a longer countdown",
            "config": {
                "countdown_sec": 0.5,
                "start_gesture_frames": 2,
                "angle_threshold_deg": 25.0,
                "reference_is_mirrored": False,
            },
            "fps": 25,
            "user": [thumbs, wave[0], thumbs, thumbs]
            + [wave[i % 6] for i in range(30)],
            "reference": reference_frames[2:],
            "keys": {},
        },
        {
            "name": "never started",
            "config": {
                "countdown_sec": 3.0,
                "start_gesture_frames": 3,
                "angle_threshold_deg": 20.0,
                "reference_is_mirrored": False,
            },
            "fps": 30,
            "user": [wave[i % 6] for i in range(12)],
            "reference": reference_frames,
            "keys": {"10": "esc"},
        },
    ]

    hand_check_scenarios = [
        {
            "name": "both hands, then one, then none",
            "config": {"trail_length": 3, "max_bend_deg": 120.0},
            "fps": 30,
            "frames": [wave[i % 6] for i in range(15)] + [[]] * 3,
            "keys": {},
        },
        {
            "name": "stopped with ESC, hands rarely seen",
            "config": {"trail_length": 10, "max_bend_deg": 90.0},
            "fps": 24,
            "frames": [[], [], wave[2], [], [], [], wave[5], [], [], []],
            "keys": {"8": "esc"},
        },
    ]

    return {
        "hands": pool,
        "joint_angle": joint_angle_cases,
        "assign_sides": assign_sides_cases,
        "thumbs_up_sequences": thumbs_up_sequences,
        "session_scripts": session_scripts,
        "compare_pairs": compare_pairs,
        "score_from_error": score_cases,
        "accumulator_scenarios": accumulator_scenarios,
        "format": format_cases,
        "invalid_settings": invalid_settings,
        "veena_scenarios": veena_scenarios,
        "hand_check_scenarios": hand_check_scenarios,
    }


# ---------------------------------------------------------------- expected


class _ScriptedFrames:
    """Stands in for a camera or video: frame i is an image whose pixels all equal i.

    The scripted trackers read the number back from the pixels to know which
    frame they were given, so rewinding, holding and looping are all visible.
    """

    def __init__(self, count: int, on_read: Callable[[], None] | None = None) -> None:
        self.count = count
        self.position = 0
        self.description = "scripted frames"
        self._on_read = on_read

    def read(self) -> np.ndarray | None:
        if self.position >= self.count:
            return None
        frame = np.full((48, 64, 3), self.position, np.uint8)
        self.position += 1
        if self._on_read is not None:
            self._on_read()
        return frame

    def rewind(self) -> None:
        self.position = 0

    def close(self) -> None:
        return None


class _ScriptedTracker:
    """Returns the scripted hands of whichever frame it is shown."""

    def __init__(self, script: list[list[Any]], pool: list[dict[str, Any]]) -> None:
        self.script = script
        self.pool = pool

    def process(self, frame: np.ndarray) -> HandsBySide:
        index = int(frame[0, 0, 0])
        detections = [
            Detection(
                np.array(self.pool[hand]["image"]),
                np.array(self.pool[hand]["world"]),
                label,
            )
            for hand, label in self.script[index]
        ]
        return assign_sides(detections)


def _hand(pool: list[dict[str, Any]], index: int, side: Side = Side.LEFT) -> Hand:
    return Hand(side, np.array(pool[index]["image"]), np.array(pool[index]["world"]))


def _floats(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: np.asarray(value).tolist() for key, value in values.items()}


def _run_veena(
    scenario: Mapping[str, Any], pool: list[dict[str, Any]]
) -> dict[str, Any]:
    reads = {"camera": 0}

    def counted() -> None:
        reads["camera"] += 1

    fps = scenario["fps"]
    camera = _ScriptedFrames(len(scenario["user"]), on_read=counted)
    reference = LoopingVideo(_ScriptedFrames(len(scenario["reference"])))
    window = HeadlessWindow(
        keys={int(poll): KEYS[key] for poll, key in scenario["keys"].items()}
    )
    out = io.StringIO()
    report = run_veena_match(
        camera,
        reference,
        _ScriptedTracker(scenario["user"], pool),
        _ScriptedTracker(scenario["reference"], pool),
        window,
        VeenaConfig(**scenario["config"]),
        clock=lambda: reads["camera"] / fps,
        out=out,
    )
    return {
        "report": report.to_dict() if report else None,
        "printed": out.getvalue(),
        "frames_shown": window.frames_shown,
    }


def _run_hand_check(
    scenario: Mapping[str, Any], pool: list[dict[str, Any]]
) -> dict[str, Any]:
    reads = {"count": 0}

    def counted() -> None:
        reads["count"] += 1

    fps = scenario["fps"]
    source = _ScriptedFrames(len(scenario["frames"]), on_read=counted)
    window = HeadlessWindow(
        keys={int(poll): KEYS[key] for poll, key in scenario["keys"].items()}
    )
    out = io.StringIO()
    result = run_hand_check(
        source,
        _ScriptedTracker(scenario["frames"], pool),
        window,
        HandCheckConfig(**scenario["config"]),
        clock=lambda: reads["count"] / fps,
        out=out,
    )
    return {
        "frames": result.frames,
        "elapsed_sec": result.elapsed_sec,
        "tracked": {str(side): n for side, n in result.tracked.items()},
        "bend_totals": {str(side): dict(t) for side, t in result.bend_totals.items()},
        "mean_bends": {str(side): result.mean_bends(side) for side in SIDES},
        "printed": out.getvalue(),
        "frames_shown": window.frames_shown,
    }


def _run_session(script: Mapping[str, Any]) -> list[dict[str, Any]]:
    clock = FakeClock(start=10.0)
    session = Session(script["countdown_sec"], clock)
    states = []
    for op in script["ops"]:
        error = None
        if op[0] == "start":
            try:
                session.start_countdown()
            except RuntimeError as exc:
                error = str(exc)
        elif op[0] == "tick":
            session.tick()
        elif op[0] == "advance":
            clock.advance(op[1])
        states.append(
            {
                "phase": session.phase.value,
                "seconds_left": session.seconds_left(),
                "error": error,
            }
        )
    return states


def _invalid_setting_message(section: str, key: str, value: Any) -> str:
    groups = {
        "camera": CameraConfig,
        "tracker": TrackerConfig,
        "veena": VeenaConfig,
        "hand_check": HandCheckConfig,
    }
    if isinstance(value, list):
        value = tuple(value)
    try:
        groups[section](**{key: value})
    except ConfigError as exc:
        return str(exc)
    raise AssertionError(f"{section}.{key}={value!r} was accepted")


def _shared_defaults() -> dict[str, Any]:
    """The default value of every setting the website has too."""
    s = Settings()
    shared = {
        "camera": ["resolution"],
        "tracker": [
            "max_num_hands",
            "min_detection_confidence",
            "min_tracking_confidence",
        ],
        "veena": [
            "angle_threshold_deg",
            "start_gesture_frames",
            "countdown_sec",
            "reference_is_mirrored",
        ],
        "hand_check": ["trail_length", "max_bend_deg"],
    }
    out: dict[str, Any] = {}
    for section, keys in shared.items():
        values = dataclasses.asdict(getattr(s, section))
        out[section] = {
            k: list(values[k]) if isinstance(values[k], tuple) else values[k]
            for k in keys
        }
    return out


def _landmark_constants() -> dict[str, Any]:
    """The point numbers both versions must agree on."""
    return {
        "num_hand_landmarks": landmarks.NUM_HAND_LANDMARKS,
        "wrist": landmarks.WRIST,
        "thumb_ip": landmarks.THUMB_IP,
        "thumb_tip": landmarks.THUMB_TIP,
        "index_tip": landmarks.INDEX_TIP,
        "middle_tip": landmarks.MIDDLE_TIP,
        "finger_names": list(landmarks.FINGER_NAMES),
        "finger_joints": {
            finger: [list(joint) for joint in joints]
            for finger, joints in landmarks.FINGER_JOINTS.items()
        },
        "fingertips": dict(landmarks.FINGERTIPS),
        "hand_connections": [list(pair) for pair in landmarks.HAND_CONNECTIONS],
        "hand_roles": {str(side): role for side, role in HAND_ROLES.items()},
    }


def compute_expected(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Run every input through the Python code."""
    pool = inputs["hands"]
    worlds = [np.array(h["world"]) for h in pool]
    images = [np.array(h["image"]) for h in pool]

    def detections(entries: list[Any]) -> list[Detection]:
        return [Detection(images[h], worlds[h], label) for h, label in entries]

    def sides_of(entries: list[Any]) -> dict[str, int]:
        # Which input hand (by its pool number) ended up as which side.
        result = assign_sides(detections(entries))
        found = {}
        for side, hand in result.items():
            for h, _ in entries:
                if hand.world_points is worlds[h]:
                    found[str(side)] = h
        return found

    sequences = []
    for seq in inputs["thumbs_up_sequences"]:
        detector = ThumbsUpDetector(seq["required_frames"])
        sequences.append([detector.update(images[h] for h in f) for f in seq["frames"]])

    compare = []
    for u, r in inputs["compare_pairs"]:
        per_finger = finger_errors(_hand(pool, u), _hand(pool, r))
        compare.append({"fingers": per_finger, "hand": hand_error(per_finger)})

    accumulator = []
    for scenario in inputs["accumulator_scenarios"]:
        acc = ScoreAccumulator()
        for frame in scenario["frames"]:
            acc.start_frame()
            for side in SIDES:
                pair = frame[str(side)]
                if pair is not None:
                    per_finger = finger_errors(
                        _hand(pool, pair[0], side), _hand(pool, pair[1], side)
                    )
                    acc.add(side, per_finger, hand_error(per_finger))
        report = acc.report(scenario["threshold_deg"])
        accumulator.append(
            {
                "report": report.to_dict() if report else None,
                "text": report.format_text() if report else None,
            }
        )

    return {
        "landmarks": _landmark_constants(),
        "defaults": _shared_defaults(),
        "joint_angle": [joint_angle(a, b, c) for a, b, c in inputs["joint_angle"]],
        "finger_joint_angles": [_floats(finger_joint_angles(w)) for w in worlds],
        "finger_bends": [finger_bends(w) for w in worlds],
        "is_thumbs_up": [is_thumbs_up(i) for i in images],
        "assign_sides": [sides_of(entries) for entries in inputs["assign_sides"]],
        "assign_sides_too_many": _too_many_hands_message(images, worlds),
        "thumbs_up_sequences": sequences,
        "session_scripts": [_run_session(s) for s in inputs["session_scripts"]],
        "compare_pairs": compare,
        "score_from_error": [
            score_from_error(e, t) for e, t in inputs["score_from_error"]
        ],
        "accumulator_scenarios": accumulator,
        "format": [format(v, f".{d}f") for v, d in inputs["format"]],
        "invalid_settings": [
            _invalid_setting_message(*case) for case in inputs["invalid_settings"]
        ],
        "veena_scenarios": [_run_veena(s, pool) for s in inputs["veena_scenarios"]],
        "hand_check_scenarios": [
            _run_hand_check(s, pool) for s in inputs["hand_check_scenarios"]
        ],
    }


def _too_many_hands_message(images: list[Any], worlds: list[Any]) -> str:
    try:
        assign_sides([Detection(images[i], worlds[i], "Left") for i in range(3)])
    except ValueError as exc:
        return str(exc)
    raise AssertionError("three hands were accepted")


# ---------------------------------------------------------------- comparing


def differences(
    expected: Any, actual: Any, path: str = "", tolerance: float = TOLERANCE
) -> list[str]:
    """Where `actual` differs from `expected` (numbers within `tolerance`)."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return [] if expected is actual else [f"{path}: {actual!r} != {expected!r}"]
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if math.isclose(expected, actual, rel_tol=0, abs_tol=tolerance):
            return []
        return [f"{path}: {actual!r} != {expected!r}"]
    if isinstance(expected, dict) and isinstance(actual, dict):
        if list(expected) != list(actual):
            return [f"{path}: keys {list(actual)} != {list(expected)}"]
        return [
            d
            for key in expected
            for d in differences(expected[key], actual[key], f"{path}.{key}", tolerance)
        ]
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{path}: length {len(actual)} != {len(expected)}"]
        return [
            d
            for i, (e, a) in enumerate(zip(expected, actual))
            for d in differences(e, a, f"{path}[{i}]", tolerance)
        ]
    return [] if expected == actual else [f"{path}: {actual!r} != {expected!r}"]


# ---------------------------------------------------------------- writing


def _dumps(data: Any) -> str:
    """JSON with one key per line, but short lists of numbers on a single line."""
    text = json.dumps(data, indent=1, ensure_ascii=False)
    # Collapse lists that contain only numbers (and line breaks) onto one line.
    number_list = re.compile(r"\[\s*((?:-?[\d.eE+-]+,\s*)*-?[\d.eE+-]+)\s*\]")
    return number_list.sub(
        lambda m: "[" + re.sub(r",\s+", ", ", m.group(1)) + "]", text
    )


def write_fixture(path: Path = FIXTURE_PATH) -> None:
    inputs = make_inputs()
    data = {
        "about": (
            "Generated by `python -m tests.parity_cases` from the Python package. "
            "The website's tests must reproduce `expected` from `inputs`. "
            "Don't edit by hand."
        ),
        "tolerance": TOLERANCE,
        "inputs": inputs,
        "expected": compute_expected(inputs),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dumps(data) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_fixture()
    print(f"wrote {FIXTURE_PATH}")
