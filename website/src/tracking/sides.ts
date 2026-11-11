/**
 * Decide which detected hand is the player's left and which is the right.
 * (Same as src/motion_capture/tracking/sides.py.)
 */

import { WRIST } from "../geometry/landmarks";
import type { Detection, Hand, HandsBySide, Point2, Side } from "./types";

function asHand(side: Side, detection: Detection): Hand {
  return { side, imagePoints: detection.imagePoints, worldPoints: detection.worldPoints };
}

function wristX(detection: Detection): number {
  return (detection.imagePoints[WRIST] as Point2)[0];
}

/**
 * Map detections to the player's own left / right hand.
 *
 * Expects detections from a mirrored (selfie-view) image; there the player's
 * right hand is on the image's right.
 *
 * With two hands, sort by position instead of trusting the tracker's label:
 * on a veena the fretting hand is always on the neck side and the plucking
 * hand on the resonator side, while the label is often the same for both.
 * With one hand there is nothing to compare, so use the tracker's label.
 */
export function assignSides(detections: readonly Detection[]): HandsBySide {
  if (detections.length === 0) return {};
  if (detections.length === 2) {
    // The hand whose wrist is further left on screen (smaller x) is the left
    // hand. (sort() keeps the original order of equal values, like Python.)
    const [left, right] = [...detections].sort((a, b) => wristX(a) - wristX(b)) as [
      Detection,
      Detection,
    ];
    return { Left: asHand("Left", left), Right: asHand("Right", right) };
  }
  if (detections.length > 2) {
    // The tracker is limited to two hands, so this is a bug.
    throw new Error(`expected at most 2 hands, got ${detections.length}`);
  }
  const only = detections[0] as Detection;
  if (only.label !== "Left" && only.label !== "Right") {
    throw new Error(`'${only.label}' is not a valid Side`);
  }
  return { [only.label]: asHand(only.label, only) };
}
