/**
 * What the programs need from frames and video sources, without saying what a
 * frame is. (Same roles as src/motion_capture/video/frames.py and sources.py.)
 *
 * In the browser a frame is a captured picture (see video/browser.ts); in the
 * tests it's a small object naming the frame. The programs only ever move
 * frames around, so the same program code runs in both.
 */

/** Frame operations the programs use: mirror and resize. */
export interface FrameOps<F> {
  /** Width and height in pixels. */
  size(frame: F): { width: number; height: number };
  /** The frame flipped left-to-right (a selfie view). */
  mirror(frame: F): F;
  /** The frame stretched to width x height. */
  resize(frame: F, width: number, height: number): F;
}

/** A webcam or a video: one frame per read(), null when there are no more. */
export interface FrameSource<F> {
  read(): Promise<F | null>;
}

/** A video that starts again from the beginning when it ends (the reference). */
export interface LoopingSource<F> extends FrameSource<F> {
  /** Rewind and return the first frame. */
  restart(): Promise<F>;
}
