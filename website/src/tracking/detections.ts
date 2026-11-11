/**
 * Turn MediaPipe's results into our own Detection objects.
 * (The website's version of `_points()` in src/motion_capture/tracking/hands.py.)
 *
 * Kept apart from handTracker.ts so it can be tested without loading MediaPipe.
 */

import type { HandLandmarkerResult } from "@mediapipe/tasks-vision";

import type { Detection } from "./types";

/**
 * The browser's MediaPipe labels hands the other way round from the Python
 * package's MediaPipe, for the same (mirrored) picture. Measured on MediaPipe's
 * sample images: where the Python version says "Left" the browser model says
 * "Right", and vice versa. Swapping the label here means "Left" means the same
 * thing in both versions, so the left/right logic (tracking/sides.ts) can be
 * identical.
 */
export function swapLabel(label: string): string {
  if (label === "Left") return "Right";
  if (label === "Right") return "Left";
  return label;
}

/** One Detection per hand found, with image points, 3D points and label. */
export function toDetections(
  result: Pick<HandLandmarkerResult, "landmarks" | "worldLandmarks" | "handedness">,
): Detection[] {
  return result.landmarks.map((points, i) => ({
    imagePoints: points.map((p) => [p.x, p.y] as const),
    worldPoints: (result.worldLandmarks[i] ?? []).map((p) => [p.x, p.y, p.z] as const),
    label: swapLabel(result.handedness[i]?.[0]?.categoryName ?? ""),
  }));
}
