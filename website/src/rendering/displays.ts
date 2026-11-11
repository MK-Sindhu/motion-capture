/**
 * Draw each frame of the two programs onto the page's canvas.
 * (What the Python versions draw onto their OpenCV frames, in the same order.)
 */

import type { HandCheckDisplay, HandCheckView } from "../apps/handCheck";
import type { VeenaDisplay, VeenaView } from "../apps/veenaMatch";
import { fixed } from "../compat/format";
import { FINGER_NAMES } from "../geometry/landmarks";
import type { Report } from "../scoring/report";
import type { Phase } from "../session/state";
import { SIDES } from "../tracking/types";
import { type CanvasFrame, drawFrame } from "../video/browser";
import { GREEN, RED, SIDE_COLORS, WHITE } from "./colors";
import { drawSkeleton, drawTrail, putLabelAtWrist, style } from "./draw";
import {
  drawBendPanel,
  drawCountdown,
  drawNoHandsWarning,
  drawTrackingStatus,
  drawWaitingMessage,
} from "./panels";

function context2d(canvas: HTMLCanvasElement): CanvasRenderingContext2D {
  const context = canvas.getContext("2d");
  if (!context) throw new Error("This browser can't draw on a canvas");
  return context;
}

function setSize(canvas: HTMLCanvasElement, width: number, height: number): void {
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;
}

/** The reference on the left, you on the right. */
export class VeenaCanvasDisplay implements VeenaDisplay<CanvasFrame> {
  private readonly context: CanvasRenderingContext2D;

  /** onPhase: told the session's stage every frame (the page shows/hides buttons). */
  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly onPhase: (phase: Phase) => void = () => {},
  ) {
    this.context = context2d(canvas);
  }

  show(view: VeenaView<CanvasFrame>): void {
    const { width, height } = view.user;
    const context = this.context;
    setSize(this.canvas, 2 * width, height);
    drawFrame(context, view.reference, 0, 0);
    drawFrame(context, view.user, width, 0);

    // ---- the reference (left half) ----
    this.withinHalf(0, width, height, () => {
      for (const side of SIDES) {
        const hand = view.referenceHands[side];
        if (!hand) continue;
        drawSkeleton(context, hand.imagePoints, width, height);
        putLabelAtWrist(context, hand.imagePoints, width, height, side, WHITE);
      }
    });

    // ---- you (right half) ----
    this.withinHalf(width, width, height, () => {
      for (const side of SIDES) {
        const hand = view.userHands[side];
        if (!hand) continue;
        const error = view.frameError[side];
        // Green if close to the reference this frame; red otherwise, or when
        // there was nothing to compare (e.g. before starting).
        const ok = error !== undefined && error < view.thresholdDeg;
        const color = ok ? GREEN : RED;
        const handStyle = style(color, 2, 3);
        drawSkeleton(context, hand.imagePoints, width, height, handStyle, handStyle);
        const label = error === undefined ? side : `${side} ${fixed(error, 0)} deg`;
        putLabelAtWrist(context, hand.imagePoints, width, height, label, color);
      }
      if (view.phase === "waiting") drawWaitingMessage(context);
      else if (view.phase === "countdown") drawCountdown(context, width, height, view.secondsLeft);
      else if (!view.userHands.Left && !view.userHands.Right) drawNoHandsWarning(context);
    });

    this.onPhase(view.phase);
  }

  /**
   * The website shows live results only (for now): when a session ends the
   * last frame stays on screen, without the Python version's final score screen.
   */
  showFinal(view: VeenaView<CanvasFrame>, _report: Report): void {
    this.show(view);
  }

  /** Draw inside one half only (like drawing on that video's own frame). */
  private withinHalf(x: number, width: number, height: number, draw: () => void): void {
    this.context.save();
    this.context.beginPath();
    this.context.rect(x, 0, width, height);
    this.context.clip();
    this.context.translate(x, 0);
    draw();
    this.context.restore();
  }
}

/** The tracking check: skeletons, fingertip trails, bend panels, status line. */
export class HandCheckCanvasDisplay implements HandCheckDisplay<CanvasFrame> {
  private readonly context: CanvasRenderingContext2D;

  constructor(private readonly canvas: HTMLCanvasElement) {
    this.context = context2d(canvas);
  }

  show(view: HandCheckView<CanvasFrame>): void {
    const { width, height } = view.frame;
    const context = this.context;
    setSize(this.canvas, width, height);
    drawFrame(context, view.frame);

    for (const side of SIDES) {
      const hand = view.hands[side];
      const bends = view.bends[side];
      if (!hand || !bends) {
        drawBendPanel(context, width, side, null, view.maxBendDeg);
        continue;
      }
      const color = SIDE_COLORS[side];
      // Fingertip trails, drawn under the skeleton.
      for (const finger of FINGER_NAMES) drawTrail(context, view.trails[side][finger], color);
      const handStyle = style(color, 2, 3);
      drawSkeleton(context, hand.imagePoints, width, height, handStyle, handStyle);
      putLabelAtWrist(context, hand.imagePoints, width, height, side, color, -25);
      drawBendPanel(context, width, side, bends, view.maxBendDeg);
    }
    drawTrackingStatus(context, height, view.fps, view.trackedPct);
  }
}
