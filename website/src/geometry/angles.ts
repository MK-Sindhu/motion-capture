/**
 * Joint-angle maths for a hand's 3D points (no camera or MediaPipe).
 * (Same as src/motion_capture/geometry/angles.py.)
 *
 * All functions take `worldPoints`: 21 points [x, y, z] in metres, as
 * estimated by MediaPipe. Using 3D points means a finger bending toward or away
 * from the camera is still measured; on the flat image the same bend would
 * look much smaller or larger.
 */

import { clip, degrees, mean } from "../compat/numeric";
import type { Point3 } from "../tracking/types";
import { FINGER_JOINTS, FINGER_NAMES, type Finger } from "./landmarks";

/** The 3 joint angles of one finger, from the knuckle to the tip. */
export type JointAngles = readonly [number, number, number];

/**
 * Angle in degrees at point b, between the lines b->a and b->c.
 *
 * Uses the dot-product rule: cos(angle) = (ba . bc) / (|ba| * |bc|).
 */
export function jointAngle(a: Point3, b: Point3, c: Point3): number {
  // Arrows from the joint b to the points a and c
  const ba = [a[0] - b[0], a[1] - b[1], a[2] - b[2]] as const;
  const bc = [c[0] - b[0], c[1] - b[1], c[2] - b[2]] as const;
  const dot = ba[0] * bc[0] + ba[1] * bc[1] + ba[2] * bc[2];
  const lengthBa = Math.sqrt(ba[0] * ba[0] + ba[1] * ba[1] + ba[2] * ba[2]);
  const lengthBc = Math.sqrt(bc[0] * bc[0] + bc[1] * bc[1] + bc[2] * bc[2]);
  // + 1e-6 avoids dividing by zero if two points land on top of each other.
  // (It also makes a straight joint read about 177 degrees at real finger
  // size; kept so the website scores exactly like the Python version.)
  const cosAngle = dot / (lengthBa * lengthBc + 1e-6);
  // Rounding can push cosAngle slightly past +-1, where acos is undefined, so
  // clip it into range first. acos gives radians; convert to degrees.
  return degrees(Math.acos(clip(cosAngle, -1, 1)));
}

/** The 3 joint angles of each finger. 180 = straight joint; smaller = more bent. */
export function fingerJointAngles(worldPoints: readonly Point3[]): Record<Finger, JointAngles> {
  const point = (i: number): Point3 => worldPoints[i] as Point3;
  const result = {} as Record<Finger, JointAngles>;
  for (const finger of FINGER_NAMES) {
    const [j1, j2, j3] = FINGER_JOINTS[finger];
    result[finger] = [
      jointAngle(point(j1[0]), point(j1[1]), point(j1[2])),
      jointAngle(point(j2[0]), point(j2[1]), point(j2[2])),
      jointAngle(point(j3[0]), point(j3[1]), point(j3[2])),
    ];
  }
  return result;
}

/**
 * How bent each finger is, in degrees: 0 = straight, larger = more curled.
 * A finger's bend is 180 minus the average of its 3 joint angles.
 */
export function fingerBends(worldPoints: readonly Point3[]): Record<Finger, number> {
  const angles = fingerJointAngles(worldPoints);
  const result = {} as Record<Finger, number>;
  for (const finger of FINGER_NAMES) result[finger] = 180 - mean(angles[finger]);
  return result;
}
