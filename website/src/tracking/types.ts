/**
 * Plain data types for tracked hands. No MediaPipe types leave the tracking
 * folder. (Same as src/motion_capture/tracking/types.py.)
 *
 * Converting MediaPipe's results into these objects in one place
 * (tracking/handTracker.ts) means the rest of the program, and its tests,
 * never depend on MediaPipe.
 */

/** The player's own left or right hand. */
export type Side = "Left" | "Right";

// Both hands, in the order they are listed everywhere (panels, reports).
export const SIDES: readonly Side[] = ["Left", "Right"];

// What each hand does on a veena.
export const HAND_ROLES: Readonly<Record<Side, string>> = {
  Left: "fretting",
  Right: "plucking",
};

/** [x, y] as fractions of the image: x = 0 left edge, 1 right; y = 0 TOP, 1 bottom. */
export type Point2 = readonly [number, number];
/** [x, y, z] in metres, measured from roughly the centre of the hand. */
export type Point3 = readonly [number, number, number];

/** One hand as found by the tracker, before we decide which hand it is. */
export interface Detection {
  // 21 points on the image (multiply by the image width/height for pixels)
  readonly imagePoints: readonly Point2[];
  // The same 21 points in 3D (used for angles)
  readonly worldPoints: readonly Point3[];
  // The tracker's own guess, "Left" or "Right" (for a mirrored image)
  readonly label: string;
}

/** A hand once we know whether it is the player's left or right hand. */
export interface Hand {
  readonly side: Side;
  readonly imagePoints: readonly Point2[];
  readonly worldPoints: readonly Point3[];
}

/** What a tracker returns for one frame: only the hands that were found. */
export type HandsBySide = Partial<Record<Side, Hand>>;

/** The hands that were found, Left first. */
export function foundHands(hands: HandsBySide): Hand[] {
  return SIDES.flatMap((side) => {
    const hand = hands[side];
    return hand ? [hand] : [];
  });
}

/** Anything that finds hands in a frame: the MediaPipe tracker, or a fake in tests. */
export interface HandTracking<F> {
  /** The hands in a mirrored frame, by side. */
  process(frame: F): HandsBySide;
}
