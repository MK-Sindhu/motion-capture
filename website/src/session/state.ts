/**
 * The stages of a matching session: waiting -> countdown -> running.
 * (Same as src/motion_capture/session/state.py.)
 *
 *   waiting    the reference loops; waiting for a thumbs up (or Space)
 *   countdown  the reference is rewound and held still for `countdownSec`
 *              seconds while the player puts their hand back on the veena
 *   running    frames are compared and scored
 *
 * The clock is passed in, so tests can move time forward without waiting.
 */

export type Phase = "waiting" | "countdown" | "running";

/** Returns the current time in seconds (only differences matter). */
export type Clock = () => number;

/** The real clock: seconds since the page opened, never jumps backwards. */
export const monotonicSeconds: Clock = () => performance.now() / 1000;

export class Session {
  phase: Phase = "waiting";
  // Clock time at which the countdown finishes
  private countdownEnd = 0;

  constructor(
    readonly countdownSec: number,
    private readonly clock: Clock = monotonicSeconds,
  ) {}

  /** Start counting down (thumbs up or Space seen). Only valid while waiting. */
  startCountdown(): void {
    if (this.phase !== "waiting") {
      throw new Error(`cannot start the countdown while ${this.phase}`);
    }
    this.phase = "countdown";
    this.countdownEnd = this.clock() + this.countdownSec;
  }

  /** Switch countdown to running once time is up; return the phase. */
  tick(): Phase {
    if (this.phase === "countdown" && this.clock() >= this.countdownEnd) {
      this.phase = "running";
    }
    return this.phase;
  }

  /** Seconds until the countdown ends (0 if not counting down). */
  secondsLeft(): number {
    if (this.phase !== "countdown") return 0;
    return Math.max(0, this.countdownEnd - this.clock());
  }
}
