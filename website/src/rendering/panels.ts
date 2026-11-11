/**
 * Bigger on-screen elements: the finger-bend panel, status lines, score overlays.
 * (The canvas version of src/motion_capture/rendering/panels.py.)
 */

import { fixedWidth } from "../compat/format";
import { clip } from "../compat/numeric";
import { FINGER_NAMES, type Finger } from "../geometry/landmarks";
import { HAND_ROLES, type Side } from "../tracking/types";
import { css, GREY, RED, SIDE_COLORS, WHITE, YELLOW } from "./colors";
import { putText } from "./draw";

// ---------------------------------------------------------------- hand check

// Size of the finger-bend panel, in pixels:
//   PANEL_W / PANEL_H = panel width / height
//   BAR_X = how far from the panel's left edge the bars start (room for the name)
//   BAR_W = length of a completely full bar
export const PANEL_W = 300;
export const PANEL_H = 190;
export const BAR_X = 90;
export const BAR_W = 150;

/**
 * Per-finger bend bars for one hand, top-left (Left) or top-right (Right).
 *
 * bends is {finger: degrees}, or null if the hand wasn't found (the panel
 * then says NOT DETECTED). On a frame too narrow for two panels side by side,
 * Right goes below Left.
 */
export function drawBendPanel(
  context: CanvasRenderingContext2D,
  frameWidth: number,
  side: Side,
  bends: Record<Finger, number> | null,
  maxBendDeg: number,
): void {
  const sideBySide = frameWidth >= 2 * PANEL_W + 30;
  // (x0, y0) = the panel's top-left corner; in images y = 0 is the TOP.
  const x0 = side === "Left" || !sideBySide ? 10 : frameWidth - PANEL_W - 10;
  const y0 = side === "Left" || sideBySide ? 10 : PANEL_H + 20;

  // Darken the panel's rectangle to 35% brightness, so the text stands out.
  context.fillStyle = "rgba(0, 0, 0, 0.65)";
  context.fillRect(x0, y0, PANEL_W, PANEL_H);

  const color = SIDE_COLORS[side];
  putText(context, `${side} hand (${HAND_ROLES[side]})`, x0 + 10, y0 + 25, 0.65, color, 2);
  if (bends === null) {
    putText(context, "NOT DETECTED", x0 + 10, y0 + 100, 0.9, RED, 2);
    return;
  }

  // One row per finger: name, bar, number. Rows are 27 px apart.
  FINGER_NAMES.forEach((finger, i) => {
    const bend = bends[finger];
    const y = y0 + 55 + i * 27;
    putText(context, finger, x0 + 10, y, 0.6, WHITE, 1);
    const fill = Math.trunc((clip(bend, 0, maxBendDeg) / maxBendDeg) * BAR_W);
    // Grey outline of the full bar, then the coloured part
    context.strokeStyle = css(GREY);
    context.lineWidth = 1;
    context.strokeRect(x0 + BAR_X + 0.5, y - 14 + 0.5, BAR_W, 14);
    context.fillStyle = css(color);
    context.fillRect(x0 + BAR_X, y - 14, fill + 1, 15);
    putText(context, fixedWidth(bend, 0, 3), x0 + BAR_X + BAR_W + 10, y, 0.6, WHITE, 1);
  });
}

/** Bottom line: frames per second and how often each hand has been found. */
export function drawTrackingStatus(
  context: CanvasRenderingContext2D,
  frameHeight: number,
  fps: number,
  trackedPct: Record<Side, number>,
): void {
  const text =
    `FPS ${fixedWidth(fps, 1, 4)}   tracked so far: Left ${fixedWidth(trackedPct.Left, 0, 3)}%` +
    `  Right ${fixedWidth(trackedPct.Right, 0, 3)}%`;
  putText(context, text, 10, frameHeight - 15, 0.65, WHITE, 2);
}

// ---------------------------------------------------------------- veena match

export function drawWaitingMessage(context: CanvasRenderingContext2D): void {
  putText(context, "Show THUMBS UP (or press SPACE) to start", 40, 60);
}

/** "Hands on the veena..." plus a big number in the middle. */
export function drawCountdown(
  context: CanvasRenderingContext2D,
  frameWidth: number,
  frameHeight: number,
  secondsLeft: number,
): void {
  putText(context, "Hands on the veena...", 40, 60);
  putText(
    context,
    String(secondsLeft),
    Math.floor(frameWidth / 2) - 40,
    Math.floor(frameHeight / 2) + 40,
    4,
    YELLOW,
    8,
  );
}

export function drawNoHandsWarning(context: CanvasRenderingContext2D): void {
  putText(context, "No hands visible - move closer / improve lighting", 40, 60, 0.8, RED);
}
