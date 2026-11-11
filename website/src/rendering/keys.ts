/**
 * The keys the programs react to: Esc stops, Space starts the countdown.
 * (The website's version of poll_key() in src/motion_capture/rendering/window.py.)
 *
 * The page's buttons press the same keys, so a phone without a keyboard works too.
 */

export type Key = "Escape" | "Space";

/** Where a program asks, once per frame, "was a key pressed?". */
export interface Keys {
  /** The next key pressed since the last poll, or null. */
  poll(): Key | null;
}

/** Keys pressed on the page (or by its buttons), handed out one per poll. */
export class KeyQueue implements Keys {
  private readonly pressed: Key[] = [];

  press(key: Key): void {
    this.pressed.push(key);
  }

  poll(): Key | null {
    return this.pressed.shift() ?? null;
  }

  clear(): void {
    this.pressed.length = 0;
  }
}
