/**
 * Collect the per-frame errors of a session and turn them into the final report.
 * (Same as src/motion_capture/scoring/report.py.)
 */

import { fixed, fixedWidth } from "../compat/format";
import { mean } from "../compat/numeric";
import { FINGER_NAMES, type Finger } from "../geometry/landmarks";
import { HAND_ROLES, SIDES, type Side } from "../tracking/types";
import type { FingerErrors } from "./compare";

/**
 * Turn an average angle error into a percentage.
 *
 * 0 deg of error -> 100%, error at/above the threshold -> 0%, in a straight
 * line between. With a 20 deg threshold: 5 deg -> 75%, 10 deg -> 50%.
 */
export function scoreFromError(errorDeg: number, thresholdDeg: number): number {
  return Math.max(0, 100 * (1 - errorDeg / thresholdDeg));
}

export interface HandReport {
  readonly side: Side;
  // Average error over every frame this hand was compared in
  readonly meanErrorDeg: number;
  readonly scorePct: number;
  // Number of frames in which this hand was found in BOTH videos
  readonly framesCompared: number;
  // framesCompared as a % of all running frames
  readonly coveragePct: number;
  // Average error of each finger
  readonly fingerErrorsDeg: FingerErrors;
}

export class Report {
  constructor(
    readonly framesRunning: number,
    readonly thresholdDeg: number,
    readonly hands: readonly HandReport[],
    // Average of every per-frame hand error, both hands together
    readonly meanErrorDeg: number,
    readonly scorePct: number,
    // The (hand, finger) with the largest average error
    readonly worstSide: Side,
    readonly worstFinger: Finger,
  ) {}

  /** The report as plain data, with the same names as the Python version's to_dict(). */
  toDict(): Record<string, unknown> {
    const hands: Record<string, unknown> = {};
    for (const hand of this.hands) {
      hands[hand.side] = {
        role: HAND_ROLES[hand.side],
        mean_error_deg: hand.meanErrorDeg,
        score_pct: hand.scorePct,
        frames_compared: hand.framesCompared,
        coverage_pct: hand.coveragePct,
        finger_errors_deg: { ...hand.fingerErrorsDeg },
      };
    }
    return {
      frames_running: this.framesRunning,
      threshold_deg: this.thresholdDeg,
      mean_error_deg: this.meanErrorDeg,
      score_pct: this.scorePct,
      biggest_difference: { hand: this.worstSide, finger: this.worstFinger },
      hands,
    };
  }

  /** The summary text (the Python version prints the same in the terminal). */
  formatText(): string {
    const lines = ["", `Compared ${this.framesRunning} frames`];
    for (const hand of this.hands) {
      lines.push(
        "",
        `${hand.side} hand (${HAND_ROLES[hand.side]}): avg error ` +
          `${fixed(hand.meanErrorDeg, 1)} deg, score ${fixed(hand.scorePct, 1)}%  ` +
          `(tracked in ${fixed(hand.coveragePct, 0)}% of frames)`,
      );
      for (const finger of FINGER_NAMES) {
        const err = hand.fingerErrorsDeg[finger];
        lines.push(`    ${finger.padEnd(7)} ${fixedWidth(err, 1, 5)} deg`);
      }
    }
    lines.push(
      "",
      `Average finger-joint error: ${fixed(this.meanErrorDeg, 1)} deg`,
      `Match Score: ${fixed(this.scorePct, 1)}%`,
      `Biggest difference: ${this.worstSide} hand, ${this.worstFinger}`,
    );
    return lines.join("\n");
  }
}

/** Keeps every per-frame error while a session runs. */
export class ScoreAccumulator {
  // How many frames were in the running phase (compared or not)
  framesRunning = 0;
  // handErrors.Left = that hand's error in each frame it was compared
  readonly handErrors: Record<Side, number[]> = { Left: [], Right: [] };
  // That finger's error in each frame, keyed "Left|Index", in the order the
  // pairs were first seen (used to break ties for "worst", like Python)
  readonly fingerErrors = new Map<string, { side: Side; finger: Finger; errors: number[] }>();

  /** Count one running frame (call it even if no hand could be compared). */
  startFrame(): void {
    this.framesRunning += 1;
  }

  /** Record one hand's comparison for the current frame. */
  add(side: Side, perFinger: FingerErrors, handError: number): void {
    for (const finger of FINGER_NAMES) {
      const key = `${side}|${finger}`;
      let entry = this.fingerErrors.get(key);
      if (!entry) {
        entry = { side, finger, errors: [] };
        this.fingerErrors.set(key, entry);
      }
      entry.errors.push(perFinger[finger]);
    }
    this.handErrors[side].push(handError);
  }

  /** The final report, or null if no hand was ever compared. */
  report(thresholdDeg: number): Report | null {
    const compared = SIDES.filter((side) => this.handErrors[side].length > 0);
    if (compared.length === 0) return null;

    const hands: HandReport[] = compared.map((side) => {
      const errors = this.handErrors[side];
      const meanError = mean(errors);
      const perFinger = {} as FingerErrors;
      for (const finger of FINGER_NAMES) {
        perFinger[finger] = mean(this.fingerErrors.get(`${side}|${finger}`)?.errors ?? []);
      }
      return {
        side,
        meanErrorDeg: meanError,
        scorePct: scoreFromError(meanError, thresholdDeg),
        framesCompared: errors.length,
        coveragePct: (100 * errors.length) / this.framesRunning,
        fingerErrorsDeg: perFinger,
      };
    });

    const overall = mean(compared.flatMap((side) => this.handErrors[side]));

    // The largest average; on a tie the first one recorded wins (like Python's max()).
    let worst: { side: Side; finger: Finger } | null = null;
    let worstError = -Infinity;
    for (const entry of this.fingerErrors.values()) {
      const err = mean(entry.errors);
      if (worst === null || err > worstError) {
        worst = entry;
        worstError = err;
      }
    }
    const { side: worstSide, finger: worstFinger } = worst as { side: Side; finger: Finger };

    return new Report(
      this.framesRunning,
      thresholdDeg,
      hands,
      overall,
      scoreFromError(overall, thresholdDeg),
      worstSide,
      worstFinger,
    );
  }
}
