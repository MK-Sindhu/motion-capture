/**
 * Stand-ins for the camera, video, tracker, display and keyboard, so the
 * programs run in tests without a browser. They match the fakes the Python
 * version uses to build tests/fixtures/parity-cases.json (tests/parity_cases.py).
 */

import type { HandCheckDisplay, HandCheckView } from "../src/apps/handCheck";
import type { VeenaDisplay, VeenaView } from "../src/apps/veenaMatch";
import type { Key, Keys } from "../src/rendering/keys";
import type { Report } from "../src/scoring/report";
import { assignSides } from "../src/tracking/sides";
import type { Detection, HandsBySide, HandTracking, Point2, Point3 } from "../src/tracking/types";
import type { FrameOps, FrameSource, LoopingSource } from "../src/video/frames";

/** A frame in the tests: which frame it is, and how it has been changed. */
export interface FakeFrame {
  readonly id: number;
  readonly mirrored: boolean;
  readonly width: number;
  readonly height: number;
}

export const fakeFrameOps: FrameOps<FakeFrame> = {
  size: (frame) => ({ width: frame.width, height: frame.height }),
  mirror: (frame) => ({ ...frame, mirrored: !frame.mirrored }),
  resize: (frame, width, height) => ({ ...frame, width, height }),
};

/** Frames 0, 1, 2, ... (64 x 48 pixels, like the Python fakes), then null. */
export class ScriptedFrames implements FrameSource<FakeFrame> {
  position = 0;

  constructor(
    readonly count: number,
    private readonly onRead?: () => void,
  ) {}

  async read(): Promise<FakeFrame | null> {
    if (this.position >= this.count) return null;
    const frame = { id: this.position, mirrored: false, width: 64, height: 48 };
    this.position += 1;
    this.onRead?.();
    return frame;
  }

  rewind(): void {
    this.position = 0;
  }
}

/** Loops a ScriptedFrames, like the Python LoopingVideo. */
export class LoopingFrames implements LoopingSource<FakeFrame> {
  constructor(private readonly source: ScriptedFrames) {}

  async read(): Promise<FakeFrame | null> {
    let frame = await this.source.read();
    if (frame === null) {
      this.source.rewind();
      frame = await this.source.read();
    }
    return frame;
  }

  async restart(): Promise<FakeFrame> {
    this.source.rewind();
    const frame = await this.source.read();
    if (frame === null) throw new Error("Cannot read reference video: scripted frames");
    return frame;
  }
}

/** A synthetic hand from the fixture: 21 world points and 21 image points. */
export interface PoolHand {
  readonly world: readonly Point3[];
  readonly image: readonly Point2[];
}

/** [pool hand number, MediaPipe's label] for every hand in a frame. */
export type ScriptedHands = readonly (readonly [number, string])[];

/** Returns the scripted hands of whichever frame it is shown. */
export class ScriptedTracker implements HandTracking<FakeFrame> {
  readonly seen: FakeFrame[] = [];

  constructor(
    private readonly script: readonly ScriptedHands[],
    private readonly pool: readonly PoolHand[],
  ) {}

  process(frame: FakeFrame): HandsBySide {
    this.seen.push(frame);
    const detections: Detection[] = (this.script[frame.id] ?? []).map(([hand, label]) => {
      const pooled = this.pool[hand] as PoolHand;
      return { imagePoints: pooled.image, worldPoints: pooled.world, label };
    });
    return assignSides(detections);
  }
}

/** Presses `keys[n]` on the n-th poll (0 = first), like the Python HeadlessWindow. */
export class ScriptedKeys implements Keys {
  private polls = 0;

  constructor(private readonly keys: Readonly<Record<number, Key>> = {}) {}

  poll(): Key | null {
    const key = this.keys[this.polls] ?? null;
    this.polls += 1;
    return key;
  }
}

/** Remembers what it was asked to show. */
export class RecordingDisplay implements VeenaDisplay<FakeFrame>, HandCheckDisplay<FakeFrame> {
  framesShown = 0;
  readonly views: (VeenaView<FakeFrame> | HandCheckView<FakeFrame>)[] = [];
  finalReport: Report | null = null;

  show(view: VeenaView<FakeFrame> | HandCheckView<FakeFrame>): void {
    this.framesShown += 1;
    this.views.push(view);
  }

  showFinal(_view: VeenaView<FakeFrame>, report: Report): void {
    this.framesShown += 1;
    this.finalReport = report;
  }
}

/** A clock that only moves when told to. */
export class FakeClock {
  constructor(public now = 100) {}

  readonly read = (): number => this.now;

  advance(seconds: number): void {
    this.now += seconds;
  }
}

/** Collects what a program writes, with a newline after each piece (like print()). */
export function captureOutput(): { out: (text: string) => void; text: () => string } {
  const pieces: string[] = [];
  return { out: (text) => pieces.push(`${text}\n`), text: () => pieces.join("") };
}

/** Where `actual` differs from `expected`, numbers within `tolerance` (as in Python). */
export function differences(
  expected: unknown,
  actual: unknown,
  tolerance: number,
  path = "",
): string[] {
  if (typeof expected === "number" && typeof actual === "number") {
    return Math.abs(expected - actual) <= tolerance ? [] : [`${path}: ${actual} != ${expected}`];
  }
  if (Array.isArray(expected) && Array.isArray(actual)) {
    if (expected.length !== actual.length) {
      return [`${path}: length ${actual.length} != ${expected.length}`];
    }
    return expected.flatMap((e, i) => differences(e, actual[i], tolerance, `${path}[${i}]`));
  }
  if (isObject(expected) && isObject(actual)) {
    const keysE = Object.keys(expected);
    const keysA = Object.keys(actual);
    if (keysE.join(",") !== keysA.join(",")) {
      return [`${path}: keys ${JSON.stringify(keysA)} != ${JSON.stringify(keysE)}`];
    }
    return keysE.flatMap((k) => differences(expected[k], actual[k], tolerance, `${path}.${k}`));
  }
  return Object.is(expected, actual) ? [] : [`${path}: ${String(actual)} != ${String(expected)}`];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
