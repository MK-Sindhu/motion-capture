/**
 * Frames, the webcam and video files in the browser.
 * (The website's version of src/motion_capture/video/sources.py.)
 *
 * A frame is a picture copied from a <video> onto a canvas, plus two notes on
 * how to use it: whether it is mirrored and what size to show it at. Mirroring
 * and resizing only change the notes; the picture is flipped and stretched
 * when it is drawn (by the tracker or the display). That avoids copying every
 * picture several times per frame.
 */

import { CameraError, VideoError } from "../errors";
import type { FrameOps, FrameSource, LoopingSource } from "./frames";

export interface CanvasFrame {
  // The picture as the camera / video delivered it
  readonly picture: HTMLCanvasElement;
  // Draw it flipped left-to-right (selfie view)?
  readonly mirrored: boolean;
  // Draw it at this size, in pixels
  readonly width: number;
  readonly height: number;
}

export const canvasFrameOps: FrameOps<CanvasFrame> = {
  size: (frame) => ({ width: frame.width, height: frame.height }),
  mirror: (frame) => ({ ...frame, mirrored: !frame.mirrored }),
  resize: (frame, width, height) => ({ ...frame, width, height }),
};

/** Draw a frame with its top-left corner at (x, y), flipped if it is mirrored. */
export function drawFrame(
  context: CanvasRenderingContext2D,
  frame: CanvasFrame,
  x = 0,
  y = 0,
): void {
  context.save();
  if (frame.mirrored) {
    // Move to the frame's right edge and flip the x axis: drawing then runs
    // from right to left, which mirrors the picture.
    context.translate(x + frame.width, y);
    context.scale(-1, 1);
    context.drawImage(frame.picture, 0, 0, frame.width, frame.height);
  } else {
    context.drawImage(frame.picture, x, y, frame.width, frame.height);
  }
  context.restore();
}

/** Copy the <video>'s current picture onto `canvas`. */
function capture(video: HTMLVideoElement, canvas: HTMLCanvasElement): CanvasFrame {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;
  canvas.getContext("2d")?.drawImage(video, 0, 0, width, height);
  return { picture: canvas, mirrored: false, width, height };
}

/** Resolves when the <video> shows its next new picture. */
function nextVideoFrame(video: HTMLVideoElement): Promise<void> {
  return new Promise((resolve) => {
    if ("requestVideoFrameCallback" in video) {
      video.requestVideoFrameCallback(() => resolve());
    } else {
      // Older browsers: check again at the next screen refresh.
      requestAnimationFrame(() => resolve());
    }
  });
}

/** Resolves when `event` happens on `target` (once). */
function once(target: EventTarget, event: string): Promise<void> {
  return new Promise((resolve) => target.addEventListener(event, () => resolve(), { once: true }));
}

/** Rejects after `ms` milliseconds, so a stuck video can't freeze the page. */
function timeout(ms: number, message: string): Promise<never> {
  return new Promise((_, reject) => setTimeout(() => reject(new VideoError(message)), ms));
}

/**
 * A <video> element that is playing but not visible. (It sits in the page,
 * transparent, because some browsers stop decoding videos that aren't.)
 */
function hiddenVideo(): HTMLVideoElement {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.setAttribute("aria-hidden", "true");
  video.style.cssText =
    "position:fixed;left:0;top:0;width:2px;height:2px;opacity:0;pointer-events:none";
  document.body.append(video);
  return video;
}

async function loadVideoFile(video: HTMLVideoElement, file: File): Promise<string> {
  const url = URL.createObjectURL(file);
  video.src = url;
  try {
    await Promise.race([
      once(video, "loadeddata"),
      once(video, "error").then(() => {
        throw new VideoError(
          `Cannot open video: ${file.name} (is it a video file the browser can play?)`,
        );
      }),
    ]);
  } catch (error) {
    URL.revokeObjectURL(url);
    video.remove();
    throw error;
  }
  return url;
}

// ---------------------------------------------------------------- webcam

/** A camera the browser can use. */
export interface CameraInfo {
  readonly deviceId: string;
  readonly label: string;
}

/** The cameras on this computer. (Names only appear once the camera is allowed.) */
export async function listCameras(): Promise<CameraInfo[]> {
  if (!navigator.mediaDevices?.enumerateDevices) return [];
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices
    .filter((device) => device.kind === "videoinput")
    .map((device, i) => ({ deviceId: device.deviceId, label: device.label || `Camera ${i + 1}` }));
}

function cameraErrorMessage(error: unknown): string {
  const name = error instanceof DOMException ? error.name : "";
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Camera access was blocked. Allow the camera for this site (the camera icon in the address bar) and try again.";
    case "NotFoundError":
      return "No camera was found. Connect one, or choose 'A recorded video' instead.";
    case "OverconstrainedError":
      return "The chosen camera isn't available. Pick another camera and try again.";
    case "NotReadableError":
    case "AbortError":
      return "The camera is busy or blocked by the system. Close other apps using it and try again.";
    default:
      return `Cannot open the camera: ${error instanceof Error ? error.message : String(error)}`;
  }
}

/** The webcam. read() waits for the camera's next picture. */
export class CameraSource implements FrameSource<CanvasFrame> {
  private readonly canvas = document.createElement("canvas");
  private stopped = false;
  private readonly ended: Promise<void>;

  private constructor(
    private readonly stream: MediaStream,
    private readonly video: HTMLVideoElement,
  ) {
    const track = stream.getVideoTracks()[0];
    // The camera was unplugged or switched off by the system
    this.ended = track ? once(track, "ended") : Promise.resolve();
    void this.ended.then(() => {
      this.stopped = true;
    });
  }

  /** Open a camera (null = the browser's default) at about `resolution`. */
  static async open(
    deviceId: string | null,
    resolution: readonly [number, number],
  ): Promise<CameraSource> {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      throw new CameraError("The camera only works on a secure page (https://) or on localhost.");
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
          width: { ideal: resolution[0] },
          height: { ideal: resolution[1] },
        },
      });
    } catch (error) {
      throw new CameraError(cameraErrorMessage(error));
    }
    const video = hiddenVideo();
    video.srcObject = stream;
    await video.play();
    const settings = stream.getVideoTracks()[0]?.getSettings();
    console.info(`Camera opened at ${settings?.width}x${settings?.height}`);
    return new CameraSource(stream, video);
  }

  /** The id of the camera actually in use (to remember the choice). */
  get deviceId(): string | undefined {
    return this.stream.getVideoTracks()[0]?.getSettings().deviceId;
  }

  async read(): Promise<CanvasFrame | null> {
    if (this.stopped) return null;
    await Promise.race([nextVideoFrame(this.video), this.ended]);
    if (this.stopped || this.video.videoWidth === 0) return null;
    return capture(this.video, this.canvas);
  }

  close(): void {
    this.stopped = true;
    for (const track of this.stream.getTracks()) track.stop();
    this.video.srcObject = null;
    this.video.remove();
  }
}

// ---------------------------------------------------------------- video files

/**
 * A recorded video of YOUR hands, used instead of the webcam (the Python
 * version's --video). It plays at normal speed; read() returns each new
 * picture, and null at the end.
 */
export class VideoFileSource implements FrameSource<CanvasFrame> {
  private readonly canvas = document.createElement("canvas");
  private readonly ended: Promise<void>;

  private constructor(
    private readonly video: HTMLVideoElement,
    private readonly url: string,
  ) {
    this.ended = once(video, "ended");
  }

  static async open(file: File): Promise<VideoFileSource> {
    const video = hiddenVideo();
    const url = await loadVideoFile(video, file);
    await video.play();
    return new VideoFileSource(video, url);
  }

  async read(): Promise<CanvasFrame | null> {
    if (this.video.ended) return null;
    await Promise.race([nextVideoFrame(this.video), this.ended]);
    if (this.video.ended) return null;
    return capture(this.video, this.canvas);
  }

  close(): void {
    this.video.pause();
    this.video.removeAttribute("src");
    this.video.load();
    this.video.remove();
    URL.revokeObjectURL(this.url);
  }
}

/**
 * The reference video: it plays in a loop, at normal speed, and can be
 * rewound and paused on its first picture (the countdown).
 */
export class LoopingVideoSource implements LoopingSource<CanvasFrame> {
  private readonly canvas = document.createElement("canvas");
  // The first picture, kept separately: it is shown during the whole countdown
  private readonly firstPictureCanvas = document.createElement("canvas");

  private constructor(
    private readonly video: HTMLVideoElement,
    private readonly url: string,
    readonly name: string,
  ) {}

  /** sound: play the reference's sound too (off by default, like the Python version). */
  static async open(file: File, { sound = false } = {}): Promise<LoopingVideoSource> {
    const video = hiddenVideo();
    video.loop = true;
    video.muted = !sound;
    const url = await loadVideoFile(video, file);
    return new LoopingVideoSource(video, url, file.name);
  }

  /** The picture showing now (starting playback if it is paused). */
  async read(): Promise<CanvasFrame | null> {
    if (this.video.error) throw new VideoError(`Cannot read reference video: ${this.name}`);
    if (this.video.paused) await this.video.play();
    return capture(this.video, this.canvas);
  }

  /** Rewind, stay paused on the first picture, and return it. */
  async restart(): Promise<CanvasFrame> {
    this.video.pause();
    const seeked = once(this.video, "seeked");
    this.video.currentTime = 0;
    await Promise.race([seeked, timeout(5000, `Cannot rewind reference video: ${this.name}`)]);
    return capture(this.video, this.firstPictureCanvas);
  }

  close(): void {
    this.video.pause();
    this.video.removeAttribute("src");
    this.video.load();
    this.video.remove();
    URL.revokeObjectURL(this.url);
  }
}
