/**
 * Mulberry32 seeded PRNG. Deterministic: same seed -> same sequence, on any
 * platform (32-bit integer arithmetic only).
 */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return function next(): number {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Pick a random integer in [min, max) using the given RNG function. */
export function randInt(rng: () => number, min: number, max: number): number {
  return Math.floor(rng() * (max - min)) + min;
}

/** Pick a random element from an array using the given RNG function. */
export function pick<T>(rng: () => number, arr: readonly T[]): T {
  const idx = Math.floor(rng() * arr.length);
  const item = arr[Math.min(idx, arr.length - 1)];
  if (item === undefined) throw new Error("pick: array is empty");
  return item;
}
