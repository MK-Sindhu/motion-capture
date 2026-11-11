/**
 * Website-only behaviour that the shared Python cases don't cover: reading
 * settings from the page link, MediaPipe's label swap, and what the programs
 * hand to the trackers and the display.
 */

import { describe, expect, it } from "vitest";

import { runHandCheck } from "../src/apps/handCheck";
import { runVeenaMatch } from "../src/apps/veenaMatch";
import { fixed } from "../src/compat/format";
import { mean, pairwiseSum } from "../src/compat/numeric";
import { optionsFromQuery, parseResolution, settingsFromOptions } from "../src/config/loader";
import { DEFAULT_SETTINGS } from "../src/config/settings";
import { ConfigError } from "../src/errors";
import { toPixel } from "../src/rendering/draw";
import { KeyQueue } from "../src/rendering/keys";
import { swapLabel, toDetections } from "../src/tracking/detections";
import fixtureJson from "./fixtures/parity-cases.json";
import {
  fakeFrameOps,
  LoopingFrames,
  type PoolHand,
  RecordingDisplay,
  ScriptedFrames,
  type ScriptedHands,
  ScriptedKeys,
  ScriptedTracker,
} from "./helpers";

const pool = (fixtureJson as unknown as { inputs: { hands: PoolHand[] } }).inputs.hands;

describe("settings from the page link", () => {
  it("uses the defaults when the link has no options", () => {
    expect(settingsFromOptions(optionsFromQuery(""))).toEqual(DEFAULT_SETTINGS);
  });

  it("reads the same option names as the Python command's flags", () => {
    const settings = settingsFromOptions(
      optionsFromQuery(
        "?threshold=25&countdown=0&start-frames=5&reference-mirrored&" +
          "trail-length=4&max-bend=90&resolution=640x480&utm_source=x",
      ),
    );
    expect(settings.veena).toEqual({
      angleThresholdDeg: 25,
      countdownSec: 0,
      startGestureFrames: 5,
      referenceIsMirrored: true,
    });
    expect(settings.handCheck).toEqual({ trailLength: 4, maxBendDeg: 90 });
    expect(settings.camera.resolution).toEqual([640, 480]);
  });

  it("explains bad values", () => {
    expect(() => settingsFromOptions({ threshold: "lots" })).toThrow(
      new ConfigError("threshold must be a number, got 'lots'"),
    );
    expect(() => settingsFromOptions({ "start-frames": "2.5" })).toThrow(
      "start-frames must be a whole number",
    );
    expect(() => settingsFromOptions({ "reference-mirrored": "maybe" })).toThrow(
      "reference-mirrored must be true or false",
    );
    expect(() => settingsFromOptions({ threshold: "0" })).toThrow(
      "veena.angle_threshold_deg must be > 0",
    );
    expect(() => parseResolution("big")).toThrow("expected WIDTHxHEIGHT");
    expect(parseResolution(" 1920X1080 ")).toEqual([1920, 1080]);
  });
});

describe("helpers that copy Python", () => {
  it("rounds exact ties to even, like Python", () => {
    expect([0.5, 1.5, 2.5, 62.5].map((v) => fixed(v, 0))).toEqual(["0", "2", "2", "62"]);
    expect(fixed(-2.5, 0)).toBe("-2");
    expect(fixed(1.25, 1)).toBe("1.2");
    expect(fixed(Number.NaN, 1)).toBe("nan");
  });

  it("sums like numpy (pairwise), which matches plain summing up to rounding", () => {
    const values = Array.from({ length: 300 }, (_, i) => Math.sin(i) * 10);
    const plain = values.reduce((a, b) => a + b, 0);
    expect(pairwiseSum(values)).toBeCloseTo(plain, 10);
    expect(mean([1, 2, 3, 4])).toBe(2.5);
  });

  it("finds pixels like MediaPipe's drawing code", () => {
    expect(toPixel(0, 0, 640, 480)).toEqual([0, 0]);
    expect(toPixel(1, 1, 640, 480)).toEqual([639, 479]);
    expect(toPixel(0.5, 0.25, 640, 480)).toEqual([320, 120]);
    expect(toPixel(-0.01, 0.5, 640, 480)).toBeNull();
    expect(toPixel(0.5, 1.01, 640, 480)).toBeNull();
  });
});

describe("MediaPipe results", () => {
  it("swaps the browser model's labels to match the Python version", () => {
    expect(swapLabel("Left")).toBe("Right");
    expect(swapLabel("Right")).toBe("Left");
  });

  it("become detections with image points, 3D points and the swapped label", () => {
    const point = (x: number, y: number, z: number) => ({ x, y, z, visibility: 0 });
    const detections = toDetections({
      landmarks: [[point(0.1, 0.2, 0.3)]],
      worldLandmarks: [[point(1, 2, 3)]],
      handedness: [[{ score: 0.9, index: 0, categoryName: "Left", displayName: "Left" }]],
    });
    expect(detections).toEqual([
      { imagePoints: [[0.1, 0.2]], worldPoints: [[1, 2, 3]], label: "Right" },
    ]);
  });
});

describe("the veena program", () => {
  const twoHands: ScriptedHands = [
    [2, "Left"],
    [3, "Left"],
  ];

  async function run(referenceIsMirrored: boolean) {
    const user = new ScriptedTracker([twoHands, twoHands, twoHands], pool);
    const reference = new ScriptedTracker([twoHands, twoHands], pool);
    const display = new RecordingDisplay();
    const report = await runVeenaMatch({
      camera: new ScriptedFrames(3),
      reference: new LoopingFrames(new ScriptedFrames(2)),
      userTracker: user,
      referenceTracker: reference,
      frames: fakeFrameOps,
      display,
      keys: new ScriptedKeys({ 0: "Space" }),
      config: { ...DEFAULT_SETTINGS.veena, countdownSec: 0, referenceIsMirrored },
      out: () => {},
    });
    return { user, reference, display, report };
  }

  it("tracks mirrored frames, and holds the first reference frame in the countdown", async () => {
    const { user, reference, display, report } = await run(false);
    expect(user.seen.every((frame) => frame.mirrored)).toBe(true);
    expect(reference.seen.every((frame) => frame.mirrored)).toBe(true);
    // Space on the first frame: frame 0 is held during the countdown
    expect(reference.seen.map((frame) => frame.id)).toEqual([0, 0, 1]);
    expect(display.framesShown).toBe(4);
    expect(report?.framesRunning).toBe(2);
  });

  it("doesn't mirror a reference that is already mirrored", async () => {
    const { user, reference } = await run(true);
    expect(user.seen.every((frame) => frame.mirrored)).toBe(true);
    expect(reference.seen.every((frame) => !frame.mirrored)).toBe(true);
  });

  it("stops on Esc, and reports nothing if it never started", async () => {
    const display = new RecordingDisplay();
    const printed: string[] = [];
    const report = await runVeenaMatch({
      camera: new ScriptedFrames(50),
      reference: new LoopingFrames(new ScriptedFrames(5)),
      userTracker: new ScriptedTracker([], pool),
      referenceTracker: new ScriptedTracker([], pool),
      frames: fakeFrameOps,
      display,
      keys: new ScriptedKeys({ 2: "Escape" }),
      config: DEFAULT_SETTINGS.veena,
      out: (text) => printed.push(text),
    });
    expect(report).toBeNull();
    expect(display.framesShown).toBe(3);
    expect(printed[0]).toContain("No finger comparison recorded");
  });
});

describe("the hand check", () => {
  it("draws a short trail per fingertip and forgets it when the hand is lost", async () => {
    const display = new RecordingDisplay();
    const oneHand: ScriptedHands = [[2, "Left"]];
    await runHandCheck({
      source: new ScriptedFrames(5),
      tracker: new ScriptedTracker([oneHand, oneHand, oneHand, [], oneHand], pool),
      frames: fakeFrameOps,
      display,
      keys: new KeyQueue(),
      config: { trailLength: 2, maxBendDeg: 120 },
      out: () => {},
    });
    const trailLengths = display.views.map((view) =>
      "trails" in view ? view.trails.Left.Index.length : -1,
    );
    expect(trailLengths).toEqual([1, 2, 2, 0, 1]);
  });
});
