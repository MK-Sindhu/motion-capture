/**
 * The website must compute exactly what the Python package computes.
 *
 * fixtures/parity-cases.json is written by the Python package
 * (python -m tests.parity_cases): inputs, and the outputs the Python code
 * produced for them. Every case is run through the TypeScript code here.
 * Numbers must agree to within `tolerance` (1e-9); text must match exactly.
 */

import { describe, expect, it } from "vitest";

import { runHandCheck } from "../src/apps/handCheck";
import { runVeenaMatch } from "../src/apps/veenaMatch";
import { fixed } from "../src/compat/format";
import { DEFAULT_SETTINGS, type Settings, validateSettings } from "../src/config/settings";
import { fingerBends, fingerJointAngles, jointAngle } from "../src/geometry/angles";
import * as landmarks from "../src/geometry/landmarks";
import { isThumbsUp, ThumbsUpDetector } from "../src/gestures/thumbsUp";
import type { Key } from "../src/rendering/keys";
import { fingerErrors, handError } from "../src/scoring/compare";
import { ScoreAccumulator, scoreFromError } from "../src/scoring/report";
import { Session } from "../src/session/state";
import { assignSides } from "../src/tracking/sides";
import { type Hand, HAND_ROLES, SIDES, type Side } from "../src/tracking/types";
import fixtureJson from "./fixtures/parity-cases.json";
import {
  captureOutput,
  differences,
  FakeClock,
  fakeFrameOps,
  LoopingFrames,
  type PoolHand,
  RecordingDisplay,
  ScriptedFrames,
  type ScriptedHands,
  ScriptedKeys,
  ScriptedTracker,
} from "./helpers";

// ---------------------------------------------------------------- the fixture

type Pair = readonly [number, number] | null;

interface Fixture {
  tolerance: number;
  inputs: {
    hands: PoolHand[];
    joint_angle: [number[], number[], number[]][];
    assign_sides: [number, string][][];
    thumbs_up_sequences: { required_frames: number; frames: number[][] }[];
    session_scripts: { countdown_sec: number; ops: [string, number?][] }[];
    compare_pairs: [number, number][];
    score_from_error: [number, number][];
    accumulator_scenarios: {
      name: string;
      threshold_deg: number;
      frames: { Left: Pair; Right: Pair }[];
    }[];
    format: [number, number][];
    invalid_settings: [string, string, unknown][];
    veena_scenarios: {
      name: string;
      config: {
        countdown_sec: number;
        start_gesture_frames: number;
        angle_threshold_deg: number;
        reference_is_mirrored: boolean;
      };
      fps: number;
      user: ScriptedHands[];
      reference: ScriptedHands[];
      keys: Record<string, string>;
    }[];
    hand_check_scenarios: {
      name: string;
      config: { trail_length: number; max_bend_deg: number };
      fps: number;
      frames: ScriptedHands[];
      keys: Record<string, string>;
    }[];
  };
  expected: Record<string, unknown> & {
    veena_scenarios: { report: unknown; printed: string; frames_shown: number }[];
    hand_check_scenarios: Record<string, unknown>[];
  };
}

const fixture = fixtureJson as unknown as Fixture;
const { inputs, expected, tolerance } = fixture;
const pool = inputs.hands;

/** Fails with a readable list of the first differences, if any. */
function expectSame(name: string, actual: unknown): void {
  const diffs = differences(expected[name], actual, tolerance, name);
  expect(diffs.slice(0, 20)).toEqual([]);
}

function hand(index: number, side: Side = "Left"): Hand {
  const pooled = pool[index] as PoolHand;
  return { side, imagePoints: pooled.image, worldPoints: pooled.world };
}

const KEYS: Record<string, Key> = { space: "Space", esc: "Escape" };

function scriptedKeys(keys: Record<string, string>): ScriptedKeys {
  const map: Record<number, Key> = {};
  for (const [poll, key] of Object.entries(keys)) map[Number(poll)] = KEYS[key] as Key;
  return new ScriptedKeys(map);
}

// ---------------------------------------------------------------- tests

describe("the website matches the Python package", () => {
  it("uses the same landmark numbers, joints, fingertips and bones", () => {
    expectSame("landmarks", {
      num_hand_landmarks: landmarks.NUM_HAND_LANDMARKS,
      wrist: landmarks.WRIST,
      thumb_ip: landmarks.THUMB_IP,
      thumb_tip: landmarks.THUMB_TIP,
      index_tip: landmarks.INDEX_TIP,
      middle_tip: landmarks.MIDDLE_TIP,
      finger_names: [...landmarks.FINGER_NAMES],
      finger_joints: landmarks.FINGER_JOINTS,
      fingertips: landmarks.FINGERTIPS,
      hand_connections: landmarks.HAND_CONNECTIONS,
      hand_roles: HAND_ROLES,
    });
  });

  it("has the same default settings", () => {
    const d = DEFAULT_SETTINGS;
    expectSame("defaults", {
      camera: { resolution: [...d.camera.resolution] },
      tracker: {
        max_num_hands: d.tracker.maxNumHands,
        min_detection_confidence: d.tracker.minDetectionConfidence,
        min_tracking_confidence: d.tracker.minTrackingConfidence,
      },
      veena: {
        angle_threshold_deg: d.veena.angleThresholdDeg,
        start_gesture_frames: d.veena.startGestureFrames,
        countdown_sec: d.veena.countdownSec,
        reference_is_mirrored: d.veena.referenceIsMirrored,
      },
      hand_check: {
        trail_length: d.handCheck.trailLength,
        max_bend_deg: d.handCheck.maxBendDeg,
      },
    });
  });

  it("rejects the same bad settings with the same messages", () => {
    const names: Record<string, string> = {
      camera: "camera",
      tracker: "tracker",
      veena: "veena",
      hand_check: "handCheck",
      resolution: "resolution",
      max_num_hands: "maxNumHands",
      min_detection_confidence: "minDetectionConfidence",
      min_tracking_confidence: "minTrackingConfidence",
      angle_threshold_deg: "angleThresholdDeg",
      start_gesture_frames: "startGestureFrames",
      countdown_sec: "countdownSec",
      trail_length: "trailLength",
      max_bend_deg: "maxBendDeg",
    };
    const messages = inputs.invalid_settings.map(([section, key, value]) => {
      const group = names[section] as keyof Settings;
      const settings = {
        ...DEFAULT_SETTINGS,
        [group]: { ...DEFAULT_SETTINGS[group], [names[key] as string]: value },
      } as Settings;
      try {
        validateSettings(settings);
        return "accepted";
      } catch (error) {
        return (error as Error).message;
      }
    });
    expectSame("invalid_settings", messages);
  });

  it("computes the same joint angles", () => {
    expectSame(
      "joint_angle",
      inputs.joint_angle.map(([a, b, c]) => jointAngle(a as never, b as never, c as never)),
    );
    expectSame(
      "finger_joint_angles",
      pool.map((h) => fingerJointAngles(h.world)),
    );
    expectSame(
      "finger_bends",
      pool.map((h) => fingerBends(h.world)),
    );
  });

  it("sees the same thumbs up", () => {
    expectSame(
      "is_thumbs_up",
      pool.map((h) => isThumbsUp(h.image)),
    );
    expectSame(
      "thumbs_up_sequences",
      inputs.thumbs_up_sequences.map((sequence) => {
        const detector = new ThumbsUpDetector(sequence.required_frames);
        return sequence.frames.map((frame) =>
          detector.update(frame.map((h) => (pool[h] as PoolHand).image)),
        );
      }),
    );
  });

  it("assigns left and right the same way", () => {
    expectSame(
      "assign_sides",
      inputs.assign_sides.map((entries) => {
        const result = assignSides(
          entries.map(([h, label]) => ({
            imagePoints: (pool[h] as PoolHand).image,
            worldPoints: (pool[h] as PoolHand).world,
            label,
          })),
        );
        // Which input hand (by its pool number) ended up as which side.
        const found: Record<string, number> = {};
        for (const side of SIDES) {
          const sided = result[side];
          if (sided) found[side] = pool.findIndex((p) => p.world === sided.worldPoints);
        }
        return found;
      }),
    );
    const three = [0, 1, 2].map((h) => ({
      imagePoints: (pool[h] as PoolHand).image,
      worldPoints: (pool[h] as PoolHand).world,
      label: "Left",
    }));
    expect(() => assignSides(three)).toThrow(expected.assign_sides_too_many as string);
  });

  it("runs the session stages the same way", () => {
    expectSame(
      "session_scripts",
      inputs.session_scripts.map((script) => {
        const clock = new FakeClock(10);
        const session = new Session(script.countdown_sec, clock.read);
        return script.ops.map(([op, value]) => {
          let error: string | null = null;
          if (op === "start") {
            try {
              session.startCountdown();
            } catch (e) {
              error = (e as Error).message;
            }
          } else if (op === "tick") {
            session.tick();
          } else if (op === "advance") {
            clock.advance(value as number);
          }
          return { phase: session.phase, seconds_left: session.secondsLeft(), error };
        });
      }),
    );
  });

  it("compares hands and scores them the same way", () => {
    expectSame(
      "compare_pairs",
      inputs.compare_pairs.map(([u, r]) => {
        const perFinger = fingerErrors(hand(u), hand(r));
        return { fingers: perFinger, hand: handError(perFinger) };
      }),
    );
    expectSame(
      "score_from_error",
      inputs.score_from_error.map(([e, t]) => scoreFromError(e, t)),
    );
  });

  it("builds the same final report", () => {
    expectSame(
      "accumulator_scenarios",
      inputs.accumulator_scenarios.map((scenario) => {
        const scores = new ScoreAccumulator();
        for (const frame of scenario.frames) {
          scores.startFrame();
          for (const side of SIDES) {
            const pair = frame[side];
            if (pair) {
              const perFinger = fingerErrors(hand(pair[0], side), hand(pair[1], side));
              scores.add(side, perFinger, handError(perFinger));
            }
          }
        }
        const report = scores.report(scenario.threshold_deg);
        return {
          report: report ? report.toDict() : null,
          text: report ? report.formatText() : null,
        };
      }),
    );
  });

  it("writes numbers like Python's f-strings", () => {
    expectSame(
      "format",
      inputs.format.map(([value, digits]) => fixed(value, digits)),
    );
  });

  it("runs whole veena sessions the same way", async () => {
    const results = [];
    for (const scenario of inputs.veena_scenarios) {
      let cameraReads = 0;
      const camera = new ScriptedFrames(scenario.user.length, () => {
        cameraReads += 1;
      });
      const display = new RecordingDisplay();
      const output = captureOutput();
      const report = await runVeenaMatch({
        camera,
        reference: new LoopingFrames(new ScriptedFrames(scenario.reference.length)),
        userTracker: new ScriptedTracker(scenario.user, pool),
        referenceTracker: new ScriptedTracker(scenario.reference, pool),
        frames: fakeFrameOps,
        display,
        keys: scriptedKeys(scenario.keys),
        config: {
          countdownSec: scenario.config.countdown_sec,
          startGestureFrames: scenario.config.start_gesture_frames,
          angleThresholdDeg: scenario.config.angle_threshold_deg,
          referenceIsMirrored: scenario.config.reference_is_mirrored,
        },
        clock: () => cameraReads / scenario.fps,
        out: output.out,
      });
      results.push({
        report: report ? report.toDict() : null,
        printed: output.text(),
        frames_shown: display.framesShown,
      });
    }
    expectSame("veena_scenarios", results);
  });

  it("runs whole hand checks the same way", async () => {
    const results = [];
    for (const scenario of inputs.hand_check_scenarios) {
      let reads = 0;
      const display = new RecordingDisplay();
      const output = captureOutput();
      const result = await runHandCheck({
        source: new ScriptedFrames(scenario.frames.length, () => {
          reads += 1;
        }),
        tracker: new ScriptedTracker(scenario.frames, pool),
        frames: fakeFrameOps,
        display,
        keys: scriptedKeys(scenario.keys),
        config: {
          trailLength: scenario.config.trail_length,
          maxBendDeg: scenario.config.max_bend_deg,
        },
        clock: () => reads / scenario.fps,
        out: output.out,
      });
      results.push({
        frames: result.frames,
        elapsed_sec: result.elapsedSec,
        tracked: result.tracked,
        bend_totals: result.bendTotals,
        mean_bends: { Left: result.meanBends("Left"), Right: result.meanBends("Right") },
        printed: output.text(),
        frames_shown: display.framesShown,
      });
    }
    expectSame("hand_check_scenarios", results);
  });
});
