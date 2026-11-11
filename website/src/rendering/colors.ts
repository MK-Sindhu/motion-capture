/**
 * Named colours. (The same colours as src/motion_capture/rendering/colors.py.)
 *
 * The browser writes colours as (Red, Green, Blue); OpenCV in the Python
 * version writes them as (Blue, Green, Red), so the numbers there are in the
 * opposite order.
 */

import type { Side } from "../tracking/types";

export type Color = readonly [number, number, number];

export const GREEN: Color = [0, 255, 0];
export const RED: Color = [255, 0, 0];
export const YELLOW: Color = [255, 255, 0];
export const WHITE: Color = [255, 255, 255];
export const GREY: Color = [90, 90, 90];

export const SIDE_COLORS: Readonly<Record<Side, Color>> = {
  // blue
  Left: [0, 170, 255],
  // orange
  Right: [255, 200, 0],
};

// MediaPipe's own drawing colours (used for the reference video's skeletons)
export const MEDIAPIPE_WHITE: Color = [224, 224, 224];
export const MEDIAPIPE_RED: Color = [255, 0, 0];

/** The colour as CSS text, e.g. "rgb(0 170 255)". */
export function css(color: Color): string {
  return `rgb(${color[0]} ${color[1]} ${color[2]})`;
}
