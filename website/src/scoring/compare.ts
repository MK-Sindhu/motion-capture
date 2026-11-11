/**
 * Compare one of your hands with the same hand in the reference, for one frame.
 * (Same as src/motion_capture/scoring/compare.py.)
 */

import { mean } from "../compat/numeric";
import { fingerJointAngles } from "../geometry/angles";
import { FINGER_NAMES, type Finger } from "../geometry/landmarks";
import type { Hand } from "../tracking/types";

/** Error of each finger in degrees, e.g. { Thumb: 4.2, Index: 10.0, ... }. */
export type FingerErrors = Record<Finger, number>;

/**
 * A finger's error is the average of |your angle - reference angle| over its
 * 3 joints, using the 3D joint angles of both hands.
 */
export function fingerErrors(user: Hand, reference: Hand): FingerErrors {
  const userAngles = fingerJointAngles(user.worldPoints);
  const refAngles = fingerJointAngles(reference.worldPoints);
  const result = {} as FingerErrors;
  for (const finger of FINGER_NAMES) {
    const u = userAngles[finger];
    const r = refAngles[finger];
    result[finger] = mean([Math.abs(u[0] - r[0]), Math.abs(u[1] - r[1]), Math.abs(u[2] - r[2])]);
  }
  return result;
}

/** Error of the whole hand: the average over its 5 fingers. */
export function handError(perFinger: FingerErrors): number {
  return mean(FINGER_NAMES.map((finger) => perFinger[finger]));
}
