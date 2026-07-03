/**
 * Iterative Levenshtein edit distance (insert/delete/substitute), O(n*m)
 * time, O(min(n,m)) space. Includes an early-exit bound: once it is
 * established that the distance must exceed `maxDistance`, returns
 * `maxDistance + 1` (the caller only needs to know "exceeds" vs. the exact
 * value near the boundary, and this keeps fuzzy queries fast for long
 * indexed terms in the corpus).
 */
export function levenshteinDistance(a: string, b: string, maxDistance?: number): number {
  if (a === b) return 0;

  const aLen = a.length;
  const bLen = b.length;

  if (maxDistance !== undefined && Math.abs(aLen - bLen) > maxDistance) {
    return maxDistance + 1;
  }

  if (aLen === 0) return bLen;
  if (bLen === 0) return aLen;

  // Ensure `a` is the shorter string to minimize row width.
  let s = a;
  let t = b;
  if (aLen > bLen) {
    s = b;
    t = a;
  }
  const sLen = s.length;
  const tLen = t.length;

  let prevRow = new Array<number>(sLen + 1);
  let currRow = new Array<number>(sLen + 1);
  for (let i = 0; i <= sLen; i++) prevRow[i] = i;

  for (let j = 1; j <= tLen; j++) {
    currRow[0] = j;
    let rowMin = currRow[0];
    const tChar = t.charCodeAt(j - 1);
    for (let i = 1; i <= sLen; i++) {
      const cost = s.charCodeAt(i - 1) === tChar ? 0 : 1;
      const deletion = (prevRow[i] ?? 0) + 1;
      const insertion = (currRow[i - 1] ?? 0) + 1;
      const substitution = (prevRow[i - 1] ?? 0) + cost;
      const val = Math.min(deletion, insertion, substitution);
      currRow[i] = val;
      if (val < rowMin) rowMin = val;
    }
    if (maxDistance !== undefined && rowMin > maxDistance) {
      return maxDistance + 1;
    }
    const tmp = prevRow;
    prevRow = currRow;
    currRow = tmp;
  }

  return prevRow[sLen] ?? Math.max(sLen, tLen);
}
