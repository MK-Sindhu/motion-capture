/**
 * The few numpy operations the Python version uses, done the same way here so
 * both versions produce the same numbers (to the last digit where possible).
 */

// numpy sums blocks of up to 128 numbers with 8 running totals.
const PAIRWISE_BLOCK = 128;

/**
 * Sum like numpy does (`np.sum` / `np.mean`): "pairwise" summation.
 *
 * Adding floating-point numbers one by one rounds a little at every step, so
 * the order matters in the last digits. numpy adds long lists in a particular
 * order (8 running totals, then halves of the list); copying that order means
 * a mean over many frames comes out exactly as in Python.
 */
export function pairwiseSum(values: readonly number[], start = 0, count?: number): number {
  const n = count ?? values.length - start;
  const at = (i: number): number => values[start + i] as number;
  if (n < 8) {
    let sum = 0;
    for (let i = 0; i < n; i++) sum += at(i);
    return sum;
  }
  if (n <= PAIRWISE_BLOCK) {
    const r = [at(0), at(1), at(2), at(3), at(4), at(5), at(6), at(7)];
    let i = 8;
    for (; i < n - (n % 8); i += 8) {
      for (let j = 0; j < 8; j++) r[j] = (r[j] as number) + at(i + j);
    }
    const [r0, r1, r2, r3, r4, r5, r6, r7] = r as [
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
    ];
    let sum = r0 + r1 + (r2 + r3) + (r4 + r5 + (r6 + r7));
    for (; i < n; i++) sum += at(i);
    return sum;
  }
  // Split in two (at a multiple of 8) and add the two halves' sums.
  let half = Math.floor(n / 2);
  half -= half % 8;
  return pairwiseSum(values, start, half) + pairwiseSum(values, start + half, n - half);
}

/** The average, like `np.mean` (numpy starts the sum from 0.0). */
export function mean(values: readonly number[]): number {
  return (0 + pairwiseSum(values)) / values.length;
}

/** Keep a value within [low, high], like `np.clip`. */
export function clip(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high);
}

// Exactly numpy's constant: 180 / pi, worked out once.
const DEGREES_PER_RADIAN = 180 / Math.PI;

/** Radians to degrees, like `np.degrees`. */
export function degrees(radians: number): number {
  return radians * DEGREES_PER_RADIAN;
}
