/**
 * All settings, grouped by what they affect, with their default values.
 * (Same defaults and checks as src/motion_capture/config/settings.py.)
 *
 * Where values come from (later ones win):
 *   1. the defaults written below
 *   2. the page link, e.g. ?threshold=25&countdown=5 (see config/loader.ts)
 *   3. the settings form on the page
 *
 * Settings the Python version has but the website doesn't need:
 *   - camera.index: the page has a camera picker instead.
 *   - tracker.model_complexity: the browser's MediaPipe has a single model.
 *   - veena.reference: you pick the video file on the page.
 *   - veena.max_window_width: the page resizes to fit the screen.
 */

import { ConfigError } from "../errors";

export interface CameraSettings {
  // [width, height] in pixels to ask the webcam for. Fingers are small, so more
  // pixels = sharper fingers = more accurate points. The camera may deliver a
  // different size if it doesn't support this one.
  readonly resolution: readonly [number, number];
}

export interface TrackerSettings {
  // 1 or 2. The left/right assignment assumes at most one fretting and one
  // plucking hand.
  readonly maxNumHands: number;
  // How sure (0..1) the model must be before it reports a NEW hand.
  readonly minDetectionConfidence: number;
  // If confidence in a hand it is already following drops below this, the
  // hand counts as lost and the model searches again.
  readonly minTrackingConfidence: number;
}

export interface VeenaSettings {
  // Average finger-joint error (degrees) that scores 0%. Below it a hand is
  // drawn green, at or above it red. Raise it to be more forgiving.
  readonly angleThresholdDeg: number;
  // How many frames in a row the thumbs up must be seen before starting.
  readonly startGestureFrames: number;
  // Seconds to put your hand back on the veena after the thumbs up.
  readonly countdownSec: number;
  // True only if the reference clip is already a mirrored (selfie) recording.
  readonly referenceIsMirrored: boolean;
}

export interface HandCheckSettings {
  // How many past positions of each fingertip to draw as a trail
  // (10 frames is about 1/3 of a second at 30 FPS).
  readonly trailLength: number;
  // A finger bent this much (degrees) fills its bar completely.
  readonly maxBendDeg: number;
}

export interface Settings {
  readonly camera: CameraSettings;
  readonly tracker: TrackerSettings;
  readonly veena: VeenaSettings;
  readonly handCheck: HandCheckSettings;
}

export const DEFAULT_SETTINGS: Settings = {
  camera: { resolution: [1280, 720] },
  tracker: { maxNumHands: 2, minDetectionConfidence: 0.5, minTrackingConfidence: 0.5 },
  veena: {
    angleThresholdDeg: 20.0,
    startGestureFrames: 3,
    countdownSec: 3.0,
    referenceIsMirrored: false,
  },
  handCheck: { trailLength: 10, maxBendDeg: 120.0 },
};

function require(condition: boolean, message: string): void {
  if (!condition) throw new ConfigError(message);
}

/** Check every value; throws ConfigError with the same message as Python. */
export function validateSettings(settings: Settings): Settings {
  const { camera, tracker, veena, handCheck } = settings;
  require(camera.resolution.length === 2 &&
    camera.resolution.every(
      (v) => v > 0,
    ), "camera.resolution must be two positive numbers, e.g. [1280, 720]");
  require(tracker.maxNumHands === 1 ||
    tracker.maxNumHands === 2, "tracker.max_num_hands must be 1 or 2");
  for (const [name, value] of [
    ["min_detection_confidence", tracker.minDetectionConfidence],
    ["min_tracking_confidence", tracker.minTrackingConfidence],
  ] as const) {
    require(value >= 0 && value <= 1, `tracker.${name} must be between 0 and 1`);
  }
  require(veena.angleThresholdDeg > 0, "veena.angle_threshold_deg must be > 0");
  require(veena.startGestureFrames >= 1, "veena.start_gesture_frames must be >= 1");
  require(veena.countdownSec >= 0, "veena.countdown_sec must be 0 or more");
  require(handCheck.trailLength >= 1, "hand_check.trail_length must be >= 1");
  require(handCheck.maxBendDeg > 0, "hand_check.max_bend_deg must be > 0");
  return settings;
}
