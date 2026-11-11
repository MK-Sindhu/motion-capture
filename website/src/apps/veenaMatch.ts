/**
 * Veena finger matching: your webcam next to a reference video, scored.
 * (Same steps, in the same order, as src/motion_capture/apps/veena_match.py.)
 *
 * Compares the finger joint angles of both hands frame by frame:
 *   - Left hand  = fretting hand (presses / pulls the strings on the neck)
 *   - Right hand = plucking hand
 *
 * A session goes:
 *   1. waiting   - the reference loops. Show a thumbs up (or press Space).
 *   2. countdown - the reference rewinds and pauses while you put your hand
 *                  back on the veena.
 *   3. running   - every frame, each of your hands is compared with the same
 *                  hand in the reference, and drawn green (close) or red.
 *   4. Esc       - the match score, a score per hand and an error per finger.
 */

import { ThumbsUpDetector } from "../gestures/thumbsUp";
import type { Keys } from "../rendering/keys";
import { fingerErrors, handError } from "../scoring/compare";
import { type Report, ScoreAccumulator } from "../scoring/report";
import { type Clock, monotonicSeconds, type Phase, Session } from "../session/state";
import type { VeenaSettings } from "../config/settings";
import {
  foundHands,
  type HandsBySide,
  type HandTracking,
  SIDES,
  type Side,
} from "../tracking/types";
import type { FrameOps, FrameSource, LoopingSource } from "../video/frames";

export const NO_COMPARISON_MESSAGE =
  "No finger comparison recorded - did you start with a THUMBS UP (or SPACE), " +
  "and were your hands visible in both videos?";

/** Everything the display needs to draw one frame. */
export interface VeenaView<F> {
  // The reference frame, already resized to the webcam's size
  readonly reference: F;
  readonly user: F;
  readonly referenceHands: HandsBySide;
  readonly userHands: HandsBySide;
  // That hand's error in THIS frame (only while running, for hands in both videos)
  readonly frameError: Partial<Record<Side, number>>;
  readonly phase: Phase;
  // Whole seconds left in the countdown (0 otherwise)
  readonly secondsLeft: number;
  readonly thresholdDeg: number;
}

/** Shows the frames: a canvas on the page, or a recorder in the tests. */
export interface VeenaDisplay<F> {
  show(view: VeenaView<F>): void;
  /** The final screen: the last frame with the scores on top. */
  showFinal(view: VeenaView<F>, report: Report): void;
}

export interface VeenaMatchParts<F> {
  camera: FrameSource<F>;
  reference: LoopingSource<F>;
  // Use a separate tracker for each video: a tracker follows hands from one
  // frame to the next, so sharing one would mix the two videos up.
  userTracker: HandTracking<F>;
  referenceTracker: HandTracking<F>;
  frames: FrameOps<F>;
  display: VeenaDisplay<F>;
  keys: Keys;
  config: VeenaSettings;
  clock?: Clock;
  // Where the summary text goes (the Python version prints it)
  out?: (text: string) => void;
}

/**
 * Run a session until the camera stops or Esc is pressed.
 *
 * Writes the summary to `out`, shows the final score screen, and returns the
 * report (null if no hand was ever compared).
 */
export async function runVeenaMatch<F>(parts: VeenaMatchParts<F>): Promise<Report | null> {
  const { camera, reference, frames, display, keys, config } = parts;
  const clock = parts.clock ?? monotonicSeconds;
  const out = parts.out ?? ((text: string) => console.log(text));

  const session = new Session(config.countdownSec, clock);
  const thumbsUp = new ThumbsUpDetector(config.startGestureFrames);
  const scores = new ScoreAccumulator();
  // The reference's first frame, shown frozen during the countdown
  let heldReference: F | null = null;
  // The last frame shown (reused for the final score screen)
  let lastView: VeenaView<F> | null = null;

  const startCountdown = async (): Promise<void> => {
    heldReference = await reference.restart();
    session.startCountdown();
  };

  for (;;) {
    const nextUser: F | null = await camera.read();
    if (nextUser === null) break;
    let userFrame: F = nextUser;

    let refFrame: F;
    if (session.phase === "countdown" && heldReference !== null) {
      // Frames are never drawn on here (the display draws on its own canvas),
      // so the held frame can be reused as it is.
      refFrame = heldReference;
    } else {
      const nextRef: F | null = await reference.read();
      if (nextRef === null) break;
      refFrame = nextRef;
    }

    // Both views are shown and tracked as a mirror. Tracking one stream
    // mirrored and the other not would show the model a left hand in one and a
    // (mirror-image) right hand in the other, and its estimates for the two
    // differ by several degrees even for an identical pose.
    userFrame = frames.mirror(userFrame);
    if (!config.referenceIsMirrored) refFrame = frames.mirror(refFrame);
    const { width, height } = frames.size(userFrame);

    // Track the reference at its own size so its hands aren't stretched; the
    // points are fractions of the image size, so they still line up after
    // resizing it to match the webcam for display.
    const referenceHands = parts.referenceTracker.process(refFrame);
    const userHands = parts.userTracker.process(userFrame);
    refFrame = frames.resize(refFrame, width, height);

    // ---- start gesture / countdown ----
    if (session.phase === "waiting") {
      if (thumbsUp.update(foundHands(userHands).map((hand) => hand.imagePoints))) {
        await startCountdown();
      }
    } else if (session.phase === "countdown") {
      session.tick();
    }

    // ---- compare ----
    // frameError[side] = that hand's error in THIS frame (colour + label)
    const frameError: Partial<Record<Side, number>> = {};
    if (session.phase === "running") {
      scores.startFrame();
      for (const side of SIDES) {
        const user = userHands[side];
        const ref = referenceHands[side];
        // Only a hand found in BOTH videos this frame can be compared
        if (user && ref) {
          const perFinger = fingerErrors(user, ref);
          const error = handError(perFinger);
          frameError[side] = error;
          scores.add(side, perFinger, error);
        }
      }
    }

    // ---- draw ----
    lastView = {
      reference: refFrame,
      user: userFrame,
      referenceHands,
      userHands,
      frameError,
      phase: session.phase,
      secondsLeft: session.phase === "countdown" ? Math.ceil(session.secondsLeft()) : 0,
      thresholdDeg: config.angleThresholdDeg,
    };
    display.show(lastView);

    const key = keys.poll();
    if (key === "Escape") break;
    if (key === "Space" && session.phase === "waiting") await startCountdown();
  }

  const report = scores.report(config.angleThresholdDeg);
  if (report === null || lastView === null) {
    out(NO_COMPARISON_MESSAGE);
    return report;
  }
  out(report.formatText());
  display.showFinal(lastView, report);
  return report;
}
