/**
 * The thumbs-up start gesture. (Same as src/motion_capture/gestures/thumbs_up.py.)
 */

import { INDEX_TIP, MIDDLE_TIP, THUMB_IP, THUMB_TIP } from "../geometry/landmarks";
import type { Point2 } from "../tracking/types";

/**
 * True if the hand looks like a thumbs up.
 *
 * imagePoints: the hand's 21 points as fractions of the image size. In images
 * y = 0 is the TOP, so a smaller y means higher up. A thumbs up has the thumb
 * tip above the thumb's own joint, and the index and middle fingertips below
 * that joint (fingers curled into a fist).
 */
export function isThumbsUp(imagePoints: readonly Point2[]): boolean {
  const y = (i: number): number => (imagePoints[i] as Point2)[1];
  return y(THUMB_TIP) < y(THUMB_IP) && y(INDEX_TIP) > y(THUMB_IP) && y(MIDDLE_TIP) > y(THUMB_IP);
}

/**
 * Says "start" once a thumbs up has been seen in enough frames in a row.
 *
 * Requiring several frames in a row stops a single wrong detection from
 * starting the session.
 */
export class ThumbsUpDetector {
  // How many frames in a row a thumbs up has been seen
  streak = 0;

  constructor(readonly requiredFrames: number) {}

  /** Feed one frame's hands (their image points); true once the gesture counts. */
  update(hands: Iterable<readonly Point2[]>): boolean {
    let seen = false;
    for (const points of hands) {
      if (isThumbsUp(points)) {
        seen = true;
        break;
      }
    }
    // Streak broken: start counting again
    this.streak = seen ? this.streak + 1 : 0;
    return this.streak >= this.requiredFrames;
  }
}
