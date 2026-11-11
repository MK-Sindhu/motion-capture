/**
 * Errors the page shows to the user as a short message (the Python version
 * prints them as "error: ..."). Same names as src/motion_capture/errors.py.
 */

export class MotionCaptureError extends Error {
  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

/** A setting has a wrong value (from the settings form or the page link). */
export class ConfigError extends MotionCaptureError {}

/** The webcam can't be opened (no permission, no camera, in use, ...). */
export class CameraError extends MotionCaptureError {}

/** A video file can't be opened or read. */
export class VideoError extends MotionCaptureError {}
