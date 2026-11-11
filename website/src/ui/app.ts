/**
 * The page: the two tabs, the setup form, Start / Stop, and running a session.
 * (The website's version of src/motion_capture/cli/main.py: it reads the
 * settings, opens the videos and trackers, runs a program, and always closes
 * everything again.)
 *
 * The page shows live results only: nothing is saved, and there is no summary
 * screen at the end.
 */

import { runHandCheck } from "../apps/handCheck";
import { runVeenaMatch } from "../apps/veenaMatch";
import { type Options, optionsFromQuery, settingsFromOptions } from "../config/loader";
import { DEFAULT_SETTINGS, type Settings } from "../config/settings";
import { MotionCaptureError } from "../errors";
import { HandCheckCanvasDisplay, VeenaCanvasDisplay } from "../rendering/displays";
import { KeyQueue } from "../rendering/keys";
import type { Phase } from "../session/state";
import {
  CameraSource,
  type CanvasFrame,
  canvasFrameOps,
  listCameras,
  LoopingVideoSource,
  VideoFileSource,
} from "../video/browser";
import type { FrameSource } from "../video/frames";

type Mode = "veena" | "hand-check";

// Remembers the chosen camera in this browser (so an iPhone doesn't take over).
const CAMERA_STORAGE_KEY = "motion-capture.camera";

function element<T extends HTMLElement = HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) throw new Error(`The page is missing #${id}`);
  return found as T;
}

function errorMessage(error: unknown): string {
  if (error instanceof MotionCaptureError) return error.message;
  const text = error instanceof Error ? error.message : String(error);
  return `Something went wrong: ${text}`;
}

function storedCamera(): string {
  try {
    return localStorage.getItem(CAMERA_STORAGE_KEY) ?? "";
  } catch {
    // Storage can be blocked (private windows, strict settings); that's fine.
    return "";
  }
}

function rememberCamera(deviceId: string | undefined): void {
  try {
    if (deviceId) localStorage.setItem(CAMERA_STORAGE_KEY, deviceId);
  } catch {
    // Not remembered; the default camera is used next time.
  }
}

export function startApp(): void {
  const ui = {
    tabs: {
      veena: element<HTMLButtonElement>("tab-veena"),
      "hand-check": element<HTMLButtonElement>("tab-hand-check"),
    } satisfies Record<Mode, HTMLButtonElement>,
    setup: element("setup"),
    referenceFile: element<HTMLInputElement>("reference-file"),
    referenceName: element("reference-name"),
    referenceMirrored: element<HTMLInputElement>("reference-mirrored"),
    referenceSound: element<HTMLInputElement>("reference-sound"),
    cameraField: element("camera-field"),
    cameraDevice: element<HTMLSelectElement>("camera-device"),
    userFileField: element("user-file-field"),
    userFile: element<HTMLInputElement>("user-file"),
    userFileName: element("user-file-name"),
    threshold: element<HTMLInputElement>("opt-threshold"),
    countdown: element<HTMLInputElement>("opt-countdown"),
    startFrames: element<HTMLInputElement>("opt-start-frames"),
    trailLength: element<HTMLInputElement>("opt-trail-length"),
    maxBend: element<HTMLInputElement>("opt-max-bend"),
    resolution: element<HTMLSelectElement>("opt-resolution"),
    start: element<HTMLButtonElement>("start"),
    begin: element<HTMLButtonElement>("begin"),
    stop: element<HTMLButtonElement>("stop"),
    status: element("status"),
    canvas: element<HTMLCanvasElement>("view"),
    placeholder: element("placeholder"),
  };

  let mode: Mode = location.hash === "#hand-check" ? "hand-check" : "veena";
  let running = false;
  const keys = new KeyQueue();

  // ---------------------------------------------------------------- helpers

  function showStatus(text: string, kind: "info" | "error" = "info"): void {
    ui.status.textContent = text;
    ui.status.classList.toggle("error", kind === "error");
  }

  function fillForm(settings: Settings): void {
    ui.threshold.value = String(settings.veena.angleThresholdDeg);
    ui.countdown.value = String(settings.veena.countdownSec);
    ui.startFrames.value = String(settings.veena.startGestureFrames);
    ui.referenceMirrored.checked = settings.veena.referenceIsMirrored;
    ui.trailLength.value = String(settings.handCheck.trailLength);
    ui.maxBend.value = String(settings.handCheck.maxBendDeg);
    const resolution = settings.camera.resolution.join("x");
    if (![...ui.resolution.options].some((option) => option.value === resolution)) {
      ui.resolution.add(new Option(resolution.replace("x", " × "), resolution));
    }
    ui.resolution.value = resolution;
  }

  /** The form's values, named like the page-link options. */
  function formOptions(): Options {
    return {
      threshold: ui.threshold.value,
      countdown: ui.countdown.value,
      "start-frames": ui.startFrames.value,
      "reference-mirrored": ui.referenceMirrored.checked ? "true" : "false",
      "trail-length": ui.trailLength.value,
      "max-bend": ui.maxBend.value,
      resolution: ui.resolution.value,
    };
  }

  function sourceKind(): "camera" | "file" {
    const checked = document.querySelector<HTMLInputElement>('input[name="source"]:checked');
    return checked?.value === "file" ? "file" : "camera";
  }

  function setMode(next: Mode): void {
    mode = next;
    for (const [name, tab] of Object.entries(ui.tabs)) {
      tab.setAttribute("aria-selected", String(name === mode));
    }
    ui.setup.setAttribute("aria-labelledby", ui.tabs[mode].id);
    for (const part of document.querySelectorAll<HTMLElement>("[data-mode]")) {
      part.hidden = part.dataset.mode !== mode;
    }
    history.replaceState(null, "", `${location.pathname}${location.search}#${mode}`);
  }

  function showSource(): void {
    const fromFile = sourceKind() === "file";
    ui.cameraField.hidden = fromFile;
    ui.userFileField.hidden = !fromFile;
  }

  function setRunning(isRunning: boolean): void {
    running = isRunning;
    ui.start.disabled = isRunning;
    ui.stop.disabled = !isRunning;
    ui.begin.hidden = true;
    for (const control of ui.setup.querySelectorAll<HTMLInputElement | HTMLSelectElement>(
      "fieldset input, fieldset select, .settings input, .settings select",
    )) {
      control.disabled = isRunning;
    }
    for (const tab of Object.values(ui.tabs)) tab.disabled = isRunning;
  }

  async function refreshCameras(): Promise<void> {
    const cameras = await listCameras().catch(() => []);
    const wanted = ui.cameraDevice.value || storedCamera();
    ui.cameraDevice.replaceChildren(new Option("Default camera", ""));
    for (const camera of cameras) ui.cameraDevice.add(new Option(camera.label, camera.deviceId));
    if (cameras.some((camera) => camera.deviceId === wanted)) ui.cameraDevice.value = wanted;
  }

  // The status line follows the session's stage (the canvas shows it too).
  let lastPhase: Phase | null = null;
  function onPhase(phase: Phase): void {
    ui.begin.hidden = phase !== "waiting";
    if (phase === lastPhase) return;
    lastPhase = phase;
    if (phase === "waiting") showStatus("Show a thumbs up (or press Space) to start comparing.");
    else if (phase === "countdown") showStatus("Hands on the veena…");
    else showStatus("Comparing live. Press Esc (or Stop) when you're done.");
  }

  // ---------------------------------------------------------------- a session

  async function start(): Promise<void> {
    if (running) return;
    let settings: Settings;
    try {
      settings = settingsFromOptions(formOptions());
    } catch (error) {
      showStatus(`Settings: ${errorMessage(error)}`, "error");
      return;
    }
    const referenceFile = ui.referenceFile.files?.[0];
    if (mode === "veena" && !referenceFile) {
      showStatus("Choose the reference video first.", "error");
      return;
    }
    const fromFile = sourceKind() === "file";
    const userFile = ui.userFile.files?.[0];
    if (fromFile && !userFile) {
      showStatus("Choose the video of your hands first.", "error");
      return;
    }

    setRunning(true);
    keys.clear();
    lastPhase = null;
    // So Space doesn't also "click" a focused button
    (document.activeElement as HTMLElement | null)?.blur();

    // Everything opened is closed again at the end, even after an error.
    const opened: { close(): void }[] = [];
    const keep = <T extends { close(): void }>(thing: T): T => {
      opened.push(thing);
      return thing;
    };

    try {
      // Same order as the Python version: reference, your video, then trackers.
      let reference: LoopingVideoSource | null = null;
      if (mode === "veena" && referenceFile) {
        showStatus("Opening the reference video…");
        reference = keep(
          await LoopingVideoSource.open(referenceFile, { sound: ui.referenceSound.checked }),
        );
      }

      let source: FrameSource<CanvasFrame>;
      if (fromFile && userFile) {
        showStatus("Opening your video…");
        source = keep(await VideoFileSource.open(userFile));
      } else {
        showStatus("Opening the camera… (allow it if the browser asks)");
        const camera = keep(
          await CameraSource.open(ui.cameraDevice.value || null, settings.camera.resolution),
        );
        rememberCamera(camera.deviceId);
        source = camera;
      }

      showStatus("Loading the hand tracker… (about 20 MB the first time)");
      // Loaded only now, so the page itself opens quickly.
      const { MediaPipeHandTracker } = await import("../tracking/handTracker");
      const userTracker = keep(await MediaPipeHandTracker.create(settings.tracker));

      ui.placeholder.hidden = true;
      ui.canvas.hidden = false;
      const log = (text: string): void => console.info(text);

      if (reference) {
        const referenceTracker = keep(await MediaPipeHandTracker.create(settings.tracker));
        await runVeenaMatch({
          camera: source,
          reference,
          userTracker,
          referenceTracker,
          frames: canvasFrameOps,
          display: new VeenaCanvasDisplay(ui.canvas, onPhase),
          keys,
          config: settings.veena,
          out: log,
        });
      } else {
        showStatus("Tracking live. Press Esc (or Stop) when you're done.");
        await runHandCheck({
          source,
          tracker: userTracker,
          frames: canvasFrameOps,
          display: new HandCheckCanvasDisplay(ui.canvas),
          keys,
          config: settings.handCheck,
          out: log,
        });
      }
      showStatus("Stopped. Press Start to go again.");
    } catch (error) {
      console.error(error);
      showStatus(errorMessage(error), "error");
    } finally {
      for (const thing of opened.reverse()) {
        try {
          thing.close();
        } catch (error) {
          console.warn("Closing failed", error);
        }
      }
      setRunning(false);
      // Camera names become available once the camera has been allowed.
      void refreshCameras();
    }
  }

  // ---------------------------------------------------------------- events

  ui.tabs.veena.addEventListener("click", () => setMode("veena"));
  ui.tabs["hand-check"].addEventListener("click", () => setMode("hand-check"));
  for (const radio of document.querySelectorAll<HTMLInputElement>('input[name="source"]')) {
    radio.addEventListener("change", showSource);
  }
  ui.referenceFile.addEventListener("change", () => {
    ui.referenceName.textContent = ui.referenceFile.files?.[0]?.name ?? "No video chosen";
  });
  ui.userFile.addEventListener("change", () => {
    ui.userFileName.textContent = ui.userFile.files?.[0]?.name ?? "No video chosen";
  });
  ui.cameraDevice.addEventListener("change", () => rememberCamera(ui.cameraDevice.value));
  ui.start.addEventListener("click", () => void start());
  ui.stop.addEventListener("click", () => keys.press("Escape"));
  ui.begin.addEventListener("click", () => keys.press("Space"));

  document.addEventListener("keydown", (event) => {
    if (!running) return;
    if (event.key === "Escape") {
      event.preventDefault();
      keys.press("Escape");
    } else if (event.code === "Space" || event.key === " ") {
      event.preventDefault();
      keys.press("Space");
    }
  });

  // ---------------------------------------------------------------- start up

  try {
    fillForm(settingsFromOptions(optionsFromQuery(location.search)));
  } catch (error) {
    fillForm(DEFAULT_SETTINGS);
    showStatus(`The link's settings were ignored: ${errorMessage(error)}`, "error");
  }
  setMode(mode);
  showSource();
  void refreshCameras();
}
