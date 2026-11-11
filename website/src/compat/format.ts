/**
 * Write numbers the way Python's f-strings do, so the website's report text
 * matches the Python version's character for character.
 */

/**
 * `value` with `digits` decimals, like Python's f"{value:.{digits}f}".
 *
 * JavaScript's toFixed() and Python round the same way except for exact ties:
 * 62.5 rounded to a whole number is "63" in JavaScript but "62" in Python,
 * which rounds ties to the even digit. This handles that case.
 */
export function fixed(value: number, digits: number): string {
  if (Number.isNaN(value)) return "nan";
  if (!Number.isFinite(value)) return value > 0 ? "inf" : "-inf";
  const rounded = value.toFixed(digits);
  if (Math.abs(value) >= 1e21) return rounded;

  // toFixed(100) writes out the exact value stored in the computer (every
  // floating-point number is a finite decimal), so a tie is easy to spot:
  // the digits after the ones we keep are "5" followed only by zeros.
  const exact = Math.abs(value).toFixed(100);
  const dot = exact.indexOf(".");
  const rest = exact.slice(dot + 1 + digits);
  if (/^50*$/.test(rest)) {
    const kept = exact.slice(0, digits > 0 ? dot + 1 + digits : dot);
    const lastDigit = Number(kept[kept.length - 1]);
    // Even last digit: Python rounds down (keeps it); odd: up, like toFixed.
    if (lastDigit % 2 === 0) return (value < 0 ? "-" : "") + kept;
  }
  return rounded;
}

/** fixed(), padded on the left to `width` characters, like f"{value:5.1f}". */
export function fixedWidth(value: number, digits: number, width: number): string {
  return fixed(value, digits).padStart(width);
}
