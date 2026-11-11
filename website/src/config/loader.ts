/**
 * Build the final Settings: defaults < page link (?threshold=25...) < form.
 * (The website's version of src/motion_capture/config/loader.py.)
 *
 * The option names are the Python command's flags without the "--":
 *
 *   resolution=1280x720    camera.resolution
 *   threshold=25           veena.angleThresholdDeg
 *   countdown=5            veena.countdownSec
 *   start-frames=3         veena.startGestureFrames
 *   reference-mirrored=1   veena.referenceIsMirrored (1/true/yes or 0/false/no)
 *   trail-length=10        handCheck.trailLength
 *   max-bend=120           handCheck.maxBendDeg
 *
 * Other link parameters are ignored (links often carry extra ones).
 */

import { ConfigError } from "../errors";
import { DEFAULT_SETTINGS, type Settings, validateSettings } from "./settings";

/** The options, as text, e.g. { threshold: "25" } (from the link or the form). */
export type Options = Readonly<Record<string, string>>;

export const OPTION_NAMES = [
  "resolution",
  "threshold",
  "countdown",
  "start-frames",
  "reference-mirrored",
  "trail-length",
  "max-bend",
] as const;
export type OptionName = (typeof OPTION_NAMES)[number];

function number(name: string, text: string): number {
  const value = Number(text.trim());
  if (text.trim() === "" || !Number.isFinite(value)) {
    throw new ConfigError(`${name} must be a number, got '${text}'`);
  }
  return value;
}

function wholeNumber(name: string, text: string): number {
  const value = number(name, text);
  if (!Number.isInteger(value)) {
    throw new ConfigError(`${name} must be a whole number, got '${text}'`);
  }
  return value;
}

function yesNo(name: string, text: string): boolean {
  const value = text.trim().toLowerCase();
  if (["", "1", "true", "yes", "on"].includes(value)) return true;
  if (["0", "false", "no", "off"].includes(value)) return false;
  throw new ConfigError(`${name} must be true or false, got '${text}'`);
}

/** Parse "1280x720" into [1280, 720] (same rule as the Python --resolution flag). */
export function parseResolution(text: string): [number, number] {
  const parts = text.trim().toLowerCase().split("x");
  const [width, height] = parts.map((p) => Number(p));
  if (
    parts.length !== 2 ||
    !Number.isInteger(width) ||
    !Number.isInteger(height) ||
    parts.some((p) => p.trim() === "")
  ) {
    throw new ConfigError(`expected WIDTHxHEIGHT, e.g. 1280x720, got '${text}'`);
  }
  return [width as number, height as number];
}

/** Settings from the defaults with `options` applied, checked. */
export function settingsFromOptions(options: Options, base: Settings = DEFAULT_SETTINGS): Settings {
  const has = (name: OptionName): boolean => options[name] !== undefined;
  const get = (name: OptionName): string => options[name] as string;
  const settings: Settings = {
    camera: {
      resolution: has("resolution") ? parseResolution(get("resolution")) : base.camera.resolution,
    },
    tracker: base.tracker,
    veena: {
      angleThresholdDeg: has("threshold")
        ? number("threshold", get("threshold"))
        : base.veena.angleThresholdDeg,
      countdownSec: has("countdown")
        ? number("countdown", get("countdown"))
        : base.veena.countdownSec,
      startGestureFrames: has("start-frames")
        ? wholeNumber("start-frames", get("start-frames"))
        : base.veena.startGestureFrames,
      referenceIsMirrored: has("reference-mirrored")
        ? yesNo("reference-mirrored", get("reference-mirrored"))
        : base.veena.referenceIsMirrored,
    },
    handCheck: {
      trailLength: has("trail-length")
        ? wholeNumber("trail-length", get("trail-length"))
        : base.handCheck.trailLength,
      maxBendDeg: has("max-bend") ? number("max-bend", get("max-bend")) : base.handCheck.maxBendDeg,
    },
  };
  return validateSettings(settings);
}

/** The options found in a page link's query string ("?threshold=25&..."). */
export function optionsFromQuery(query: string): Options {
  const params = new URLSearchParams(query);
  const options: Record<string, string> = {};
  for (const name of OPTION_NAMES) {
    const value = params.get(name);
    if (value !== null) options[name] = value;
  }
  return options;
}

/** The options that differ from the defaults, to put in a shareable link. */
export function optionsFromSettings(settings: Settings): Record<OptionName, string | null> {
  const d = DEFAULT_SETTINGS;
  const differs = (a: unknown, b: unknown): boolean => JSON.stringify(a) !== JSON.stringify(b);
  return {
    resolution: differs(settings.camera.resolution, d.camera.resolution)
      ? settings.camera.resolution.join("x")
      : null,
    threshold: differs(settings.veena.angleThresholdDeg, d.veena.angleThresholdDeg)
      ? String(settings.veena.angleThresholdDeg)
      : null,
    countdown: differs(settings.veena.countdownSec, d.veena.countdownSec)
      ? String(settings.veena.countdownSec)
      : null,
    "start-frames": differs(settings.veena.startGestureFrames, d.veena.startGestureFrames)
      ? String(settings.veena.startGestureFrames)
      : null,
    "reference-mirrored": differs(settings.veena.referenceIsMirrored, d.veena.referenceIsMirrored)
      ? String(settings.veena.referenceIsMirrored)
      : null,
    "trail-length": differs(settings.handCheck.trailLength, d.handCheck.trailLength)
      ? String(settings.handCheck.trailLength)
      : null,
    "max-bend": differs(settings.handCheck.maxBendDeg, d.handCheck.maxBendDeg)
      ? String(settings.handCheck.maxBendDeg)
      : null,
  };
}
