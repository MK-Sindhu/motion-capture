/**
 * Hand tracking check: no reference video, no scoring.
 * (Same steps, in the same order, as src/motion_capture/apps/hand_check.py.)
 *
 * Shows whether MediaPipe picks up both hands and how much each finger bends,
 * live, so you can check camera framing and lighting before practising.
 *
 * On screen:
 *   - each detected hand as a skeleton (Left = blue, Right = orange)
 *   - a short trail behind every fingertip, so movement is easy to see
 *   - a panel per hand with one bar per finger showing how bent it is
 *   - at the bottom: frames per second and how often each hand was found
 */

import { fixed } from "../compat/format";
import { fingerBends } from "../geometry/angles";
import { FINGER_NAMES, FINGERTIPS, type Finger } from "../geometry/landmarks";
import type { HandCheckSettings } from "../config/settings";
import type { Keys } from "../rendering/keys";
import { type Clock, monotonicSeconds } from "../session/state";
import {
  HAND_ROLES,
  type HandsBySide,
  type HandTracking,
  type Point2,
  SIDES,
  type Side,
} from "../tracking/types";
import type { FrameOps, FrameSource } from "../video/frames";

// Below this % of frames tracked, the summary suggests improving the setup.
export const GOOD_TRACKING_PCT = 80;

/** Pixel positions [x, y] of one fingertip in recent frames, oldest first. */
export type Trail = readonly (readonly [number, number])[];

/** Everything the display needs to draw one frame. */
export interface HandCheckView<F> {
  readonly frame: F;
  readonly hands: HandsBySide;
  // How bent each finger of each found hand is, in degrees
  readonly bends: Partial<Record<Side, Record<Finger, number>>>;
  readonly trails: Record<Side, Record<Finger, Trail>>;
  readonly fps: number;
  // % of frames so far in which each hand was found
  readonly trackedPct: Record<Side, number>;
  readonly maxBendDeg: number;
}

export interface HandCheckDisplay<F> {
  show(view: HandCheckView<F>): void;
}

/** What happened during a hand-check run. */
export class HandCheckResult {
  constructor(
    readonly frames: number,
    readonly elapsedSec: number,
    // tracked.Left = number of frames the left hand was found in
    readonly tracked: Record<Side, number>,
    // bendTotals.Left.Index = sum of that finger's bend over the frames the
    // hand was found in (divide by tracked.Left for the average)
    readonly bendTotals: Record<Side, Record<Finger, number>>,
  ) {}

  trackedPct(side: Side): number {
    return this.frames ? (100 * this.tracked[side]) / this.frames : 0;
  }

  /** Average bend of each finger, or null if the hand was never found. */
  meanBends(side: Side): Record<Finger, number> | null {
    if (!this.tracked[side]) return null;
    const result = {} as Record<Finger, number>;
    for (const finger of FINGER_NAMES) {
      result[finger] = this.bendTotals[side][finger] / this.tracked[side];
    }
    return result;
  }

  /** The summary text (the Python version prints the same in the terminal). */
  formatText(): string {
    const fps = this.elapsedSec > 0 ? this.frames / this.elapsedSec : 0;
    const lines = [
      "",
      `${this.frames} frames in ${fixed(this.elapsedSec, 1)}s (${fixed(fps, 1)} FPS)`,
    ];
    for (const side of SIDES) {
      const pct = this.trackedPct(side);
      const hint =
        pct >= GOOD_TRACKING_PCT ? "" : "  <- move the camera closer or add light on this hand";
      lines.push(
        `${side} hand (${HAND_ROLES[side]}) tracked in ${fixed(pct, 0)}% of frames${hint}`,
      );
    }
    return lines.join("\n");
  }
}

export interface HandCheckParts<F> {
  // The webcam or a video file
  source: FrameSource<F>;
  tracker: HandTracking<F>;
  frames: FrameOps<F>;
  display: HandCheckDisplay<F>;
  keys: Keys;
  config: HandCheckSettings;
  clock?: Clock;
  out?: (text: string) => void;
}

function perFinger<T>(make: () => T): Record<Finger, T> {
  const result = {} as Record<Finger, T>;
  for (const finger of FINGER_NAMES) result[finger] = make();
  return result;
}

/** Run until the source ends or Esc is pressed; write and return the summary. */
export async function runHandCheck<F>(parts: HandCheckParts<F>): Promise<HandCheckResult> {
  const { source, tracker, frames: ops, display, keys, config } = parts;
  const clock = parts.clock ?? monotonicSeconds;
  const out = parts.out ?? ((text: string) => console.log(text));

  let frames = 0;
  const tracked: Record<Side, number> = { Left: 0, Right: 0 };
  const bendTotals: Record<Side, Record<Finger, number>> = {
    Left: perFinger(() => 0),
    Right: perFinger(() => 0),
  };
  // trails.Left.Index = the last `trailLength` pixel positions of that fingertip
  const trails: Record<Side, Record<Finger, [number, number][]>> = {
    Left: perFinger(() => []),
    Right: perFinger(() => []),
  };
  let fps = 0;
  let lastTime = clock();
  const startTime = lastTime;

  for (;;) {
    const next: F | null = await source.read();
    if (next === null) break;
    let frame: F = next;
    // Mirror view (selfie), which the hand tracker's left/right labels assume.
    // A video file is mirrored too, the same as the veena program does.
    frame = ops.mirror(frame);
    const { width, height } = ops.size(frame);

    const hands = tracker.process(frame);
    frames += 1;

    const bends: Partial<Record<Side, Record<Finger, number>>> = {};
    for (const side of SIDES) {
      const hand = hands[side];
      if (!hand) {
        // Hand lost: forget its trails, otherwise the next time it is found
        // a line would be drawn from where it used to be.
        for (const finger of FINGER_NAMES) trails[side][finger].length = 0;
        continue;
      }
      tracked[side] += 1;
      for (const finger of FINGER_NAMES) {
        const [x, y] = hand.imagePoints[FINGERTIPS[finger]] as Point2;
        const trail = trails[side][finger];
        // Math.trunc = Python's int(): drop the decimals
        trail.push([Math.trunc(x * width), Math.trunc(y * height)]);
        if (trail.length > config.trailLength) trail.shift();
      }
      const handBends = fingerBends(hand.worldPoints);
      for (const finger of FINGER_NAMES) bendTotals[side][finger] += handBends[finger];
      bends[side] = handBends;
    }

    // Frames per second. 1 / (time this frame took) jumps around, so blend
    // 10% of the new value into 90% of the old one for a steady number.
    const now = clock();
    fps = 0.9 * fps + 0.1 / Math.max(now - lastTime, 1e-6);
    lastTime = now;

    display.show({
      frame,
      hands,
      bends,
      trails: {
        Left: perFingerCopy(trails.Left),
        Right: perFingerCopy(trails.Right),
      },
      fps,
      trackedPct: { Left: (100 * tracked.Left) / frames, Right: (100 * tracked.Right) / frames },
      maxBendDeg: config.maxBendDeg,
    });
    if (keys.poll() === "Escape") break;
  }

  const result = new HandCheckResult(frames, clock() - startTime, tracked, bendTotals);
  if (frames) out(result.formatText());
  return result;
}

function perFingerCopy(trails: Record<Finger, [number, number][]>): Record<Finger, Trail> {
  const result = {} as Record<Finger, Trail>;
  for (const finger of FINGER_NAMES) result[finger] = [...trails[finger]];
  return result;
}
