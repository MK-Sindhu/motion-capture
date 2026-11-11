/**
 * MediaPipe's 21 hand landmark points: their numbers and how they connect.
 * (Same as src/motion_capture/geometry/landmarks.py.)
 *
 *         8   12  16  20     <- fingertips
 *         7   11  15  19     <- end joints
 *         6   10  14  18     <- middle joints
 *     4   5    9  13  17     <- knuckles
 *      3
 *       2        (thumb: 1-4)
 *        1
 *            0                <- wrist
 *
 * Every finger has 3 joints. A joint is a triple [a, b, c] of point numbers:
 * the angle is measured AT point b, between the bone towards a and the bone
 * towards c; a straight joint is 180 degrees. Example: [5, 6, 7] is the index
 * finger's middle joint (point 6), between bone 6->5 and bone 6->7.
 */

export const NUM_HAND_LANDMARKS = 21;
export const WRIST = 0;
export const THUMB_IP = 3;
export const THUMB_TIP = 4;
export const INDEX_TIP = 8;
export const MIDDLE_TIP = 12;

// Order matters: reports and panels list the fingers in this order.
export const FINGER_NAMES = ["Thumb", "Index", "Middle", "Ring", "Pinky"] as const;
export type Finger = (typeof FINGER_NAMES)[number];

export type Joint = readonly [number, number, number];

export const FINGER_JOINTS: Readonly<Record<Finger, readonly [Joint, Joint, Joint]>> = {
  Thumb: [
    [0, 1, 2],
    [1, 2, 3],
    [2, 3, 4],
  ],
  Index: [
    [0, 5, 6],
    [5, 6, 7],
    [6, 7, 8],
  ],
  Middle: [
    [0, 9, 10],
    [9, 10, 11],
    [10, 11, 12],
  ],
  Ring: [
    [0, 13, 14],
    [13, 14, 15],
    [14, 15, 16],
  ],
  Pinky: [
    [0, 17, 18],
    [17, 18, 19],
    [18, 19, 20],
  ],
};

export const FINGERTIPS: Readonly<Record<Finger, number>> = {
  Thumb: 4,
  Index: 8,
  Middle: 12,
  Ring: 16,
  Pinky: 20,
};

// The "bones" drawn between points (the same 21 pairs as MediaPipe's
// HAND_CONNECTIONS and the Python version).
// prettier-ignore
export const HAND_CONNECTIONS: readonly (readonly [number, number])[] = [
  // palm
  [0, 1], [0, 5], [5, 9], [9, 13], [13, 17], [0, 17],
  // thumb, index, middle, ring, pinky
  [1, 2], [2, 3], [3, 4],
  [5, 6], [6, 7], [7, 8],
  [9, 10], [10, 11], [11, 12],
  [13, 14], [14, 15], [15, 16],
  [17, 18], [18, 19], [19, 20],
];
