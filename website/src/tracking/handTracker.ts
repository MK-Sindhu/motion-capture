/**
 * The MediaPipe hand tracker: the only file that loads MediaPipe.
 * (The website's version of src/motion_capture/tracking/hands.py.)
 *
 * MediaPipe runs inside the browser as WebAssembly, using the graphics card
 * when it can. Its program files and the hand model are served by this site
 * itself (scripts/fetch-mediapipe-assets.mjs puts them in public/), so no
 * video or picture ever leaves the visitor's computer.
 */

import { FilesetResolver, HandLandmarker } from "@mediapipe/tasks-vision";

import type { TrackerSettings } from "../config/settings";
import { drawFrame, type CanvasFrame } from "../video/browser";
import { toDetections } from "./detections";
import assets from "./mediapipe-assets.json";
import { assignSides } from "./sides";
import type { HandsBySide, HandTracking } from "./types";

// The site's base address ("/" on Vercel), so the files are found on any host.
const BASE = import.meta.env.BASE_URL;

// Loading MediaPipe's WebAssembly takes a moment, so it's done once per page.
let vision: ReturnType<typeof FilesetResolver.forVisionTasks> | null = null;

function loadVision(): ReturnType<typeof FilesetResolver.forVisionTasks> {
  vision ??= FilesetResolver.forVisionTasks(`${BASE}${assets.wasmDir}`);
  return vision;
}

/**
 * Finds up to two hands in each frame of ONE video.
 *
 * In video mode MediaPipe follows hands from one frame to the next, which is
 * faster and steadier than searching every frame from scratch. That also
 * means each video needs its own tracker.
 */
export class MediaPipeHandTracker implements HandTracking<CanvasFrame> {
  // MediaPipe is given exactly the picture the program means: mirrored if the
  // frame is mirrored, at the frame's size.
  private readonly canvas = document.createElement("canvas");
  private readonly context: CanvasRenderingContext2D;
  // MediaPipe needs a later time (in ms) for every frame
  private lastTimestamp = -1;

  private constructor(private readonly landmarker: HandLandmarker) {
    const context = this.canvas.getContext("2d");
    if (!context) throw new Error("This browser can't draw on a canvas");
    this.context = context;
  }

  static async create(settings: TrackerSettings): Promise<MediaPipeHandTracker> {
    const fileset = await loadVision();
    const options = (delegate: "GPU" | "CPU") => ({
      baseOptions: { modelAssetPath: `${BASE}${assets.model.path}`, delegate },
      runningMode: "VIDEO" as const,
      numHands: settings.maxNumHands,
      minHandDetectionConfidence: settings.minDetectionConfidence,
      minTrackingConfidence: settings.minTrackingConfidence,
    });
    try {
      return new MediaPipeHandTracker(
        await HandLandmarker.createFromOptions(fileset, options("GPU")),
      );
    } catch (gpuError) {
      // Some computers or browsers can't use the graphics card; the processor works everywhere.
      console.warn("Hand tracker: graphics card not available, using the processor", gpuError);
      return new MediaPipeHandTracker(
        await HandLandmarker.createFromOptions(fileset, options("CPU")),
      );
    }
  }

  process(frame: CanvasFrame): HandsBySide {
    if (this.canvas.width !== frame.width) this.canvas.width = frame.width;
    if (this.canvas.height !== frame.height) this.canvas.height = frame.height;
    drawFrame(this.context, frame);
    const timestamp = Math.max(performance.now(), this.lastTimestamp + 1);
    this.lastTimestamp = timestamp;
    const result = this.landmarker.detectForVideo(this.canvas, timestamp);
    return assignSides(toDetections(result));
  }

  close(): void {
    this.landmarker.close();
  }
}
