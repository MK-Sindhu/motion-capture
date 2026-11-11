/**
 * Small drawing helpers: hand skeletons, text, labels, fingertip trails.
 * (The canvas version of src/motion_capture/rendering/draw.py; same sizes and
 * positions, in pixels of the video frame.)
 */

import { HAND_CONNECTIONS, WRIST } from "../geometry/landmarks";
import type { Point2 } from "../tracking/types";
import { type Color, css, MEDIAPIPE_RED, MEDIAPIPE_WHITE, WHITE, YELLOW } from "./colors";

/** How to draw points or bones: colour, line thickness (px), dot radius (px). */
export interface Style {
  readonly color: Color;
  readonly thickness: number;
  readonly circleRadius: number;
}

export function style(color: Color, thickness = 2, circleRadius = 2): Style {
  return { color, thickness, circleRadius };
}

export const DEFAULT_POINT_STYLE = style(MEDIAPIPE_RED);
export const DEFAULT_BONE_STYLE = style(MEDIAPIPE_WHITE);

function isClose(a: number, b: number): boolean {
  // Python's math.isclose() with its default tolerance
  return Math.abs(a - b) <= 1e-9 * Math.max(Math.abs(a), Math.abs(b));
}

/**
 * A point given as fractions of the image size, in pixels. null if the point
 * lies outside the image (it is then not drawn), like MediaPipe's own drawing.
 */
export function toPixel(
  x: number,
  y: number,
  width: number,
  height: number,
): [number, number] | null {
  const inside = (v: number): boolean => (v > 0 || isClose(0, v)) && (v < 1 || isClose(1, v));
  if (!(inside(x) && inside(y))) return null;
  return [Math.min(Math.floor(x * width), width - 1), Math.min(Math.floor(y * height), height - 1)];
}

function line(
  context: CanvasRenderingContext2D,
  from: readonly [number, number],
  to: readonly [number, number],
  color: Color,
  thickness: number,
): void {
  context.strokeStyle = css(color);
  context.lineWidth = thickness;
  context.lineCap = "round";
  context.beginPath();
  context.moveTo(from[0], from[1]);
  context.lineTo(to[0], to[1]);
  context.stroke();
}

function circle(
  context: CanvasRenderingContext2D,
  center: readonly [number, number],
  radius: number,
  color: Color,
  thickness: number,
): void {
  context.strokeStyle = css(color);
  context.lineWidth = thickness;
  context.beginPath();
  context.arc(center[0], center[1], radius, 0, 2 * Math.PI);
  context.stroke();
}

/** Draw a hand: lines along the bones, then a dot on each of the 21 points. */
export function drawSkeleton(
  context: CanvasRenderingContext2D,
  imagePoints: readonly Point2[],
  width: number,
  height: number,
  pointStyle: Style = DEFAULT_POINT_STYLE,
  boneStyle: Style = DEFAULT_BONE_STYLE,
): void {
  const pixels = new Map<number, [number, number]>();
  imagePoints.forEach(([x, y], index) => {
    const pixel = toPixel(x, y, width, height);
    if (pixel) pixels.set(index, pixel);
  });
  // Bones first, only where both ends are inside the image
  for (const [start, end] of HAND_CONNECTIONS) {
    const a = pixels.get(start);
    const b = pixels.get(end);
    if (a && b) line(context, a, b, boneStyle.color, boneStyle.thickness);
  }
  // Then the dots on top: a light ring, then the coloured dot
  const ringRadius = Math.max(
    pointStyle.circleRadius + 1,
    Math.trunc(pointStyle.circleRadius * 1.2),
  );
  for (const pixel of pixels.values()) {
    circle(context, pixel, ringRadius, MEDIAPIPE_WHITE, pointStyle.thickness);
    circle(context, pixel, pointStyle.circleRadius, pointStyle.color, pointStyle.thickness);
  }
}

/**
 * Write text. (x, y) is the text's bottom-left corner. `scale` and
 * `thickness` mean the same as in OpenCV's putText: scale 1 is about 22 px
 * tall capital letters.
 */
export function putText(
  context: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  scale = 1.0,
  color: Color = YELLOW,
  thickness = 2,
): void {
  const weight = thickness >= 4 ? 800 : thickness >= 2 ? 700 : 500;
  context.font = `${weight} ${Math.round(30 * scale)}px system-ui, -apple-system, "Segoe UI", sans-serif`;
  context.textBaseline = "alphabetic";
  context.fillStyle = css(color);
  context.fillText(text, x, y);
}

/** Write a label just below the hand's wrist (in images, y grows downward). */
export function putLabelAtWrist(
  context: CanvasRenderingContext2D,
  imagePoints: readonly Point2[],
  width: number,
  height: number,
  text: string,
  color: Color = WHITE,
  dx = -40,
): void {
  const [x, y] = imagePoints[WRIST] as Point2;
  putText(context, text, Math.trunc(x * width) + dx, Math.trunc(y * height) + 30, 0.7, color, 2);
}

/** Join recent fingertip positions with lines, thicker toward the newest. */
export function drawTrail(
  context: CanvasRenderingContext2D,
  trail: readonly (readonly [number, number])[],
  color: Color,
): void {
  for (let i = 1; i < trail.length; i++) {
    // i / trail.length goes from ~0 (oldest) to 1 (newest): thickness 1 -> 4 px
    const thickness = 1 + Math.floor((3 * i) / trail.length);
    line(context, trail[i - 1] as [number, number], trail[i] as [number, number], color, thickness);
  }
}
