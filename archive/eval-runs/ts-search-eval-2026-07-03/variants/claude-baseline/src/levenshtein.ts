/**
 * Levenshtein edit distance with early exit once distance exceeds maxEdits.
 * Operates over unicode code points (not UTF-16 code units) for correctness
 * with astral-plane characters; adequate for our tokenized word inputs.
 */
export function levenshteinWithinBound(
  a: string,
  b: string,
  maxEdits: number
): number | null {
  if (Math.abs(a.length - b.length) > maxEdits) {
    return null;
  }
  if (a === b) {
    return 0;
  }

  const al = a.length;
  const bl = b.length;

  // Standard DP with row-by-row bound pruning.
  let prevRow = new Array<number>(bl + 1);
  let curRow = new Array<number>(bl + 1);
  for (let j = 0; j <= bl; j++) {
    prevRow[j] = j;
  }

  for (let i = 1; i <= al; i++) {
    curRow[0] = i;
    let rowMin = curRow[0];
    const aChar = a[i - 1];
    for (let j = 1; j <= bl; j++) {
      const cost = aChar === b[j - 1] ? 0 : 1;
      const deletion = (prevRow[j] as number) + 1;
      const insertion = (curRow[j - 1] as number) + 1;
      const substitution = (prevRow[j - 1] as number) + cost;
      const val = Math.min(deletion, insertion, substitution);
      curRow[j] = val;
      if (val < rowMin) {
        rowMin = val;
      }
    }
    if (rowMin > maxEdits) {
      return null;
    }
    const tmp = prevRow;
    prevRow = curRow;
    curRow = tmp;
  }

  const result = prevRow[bl] as number;
  return result <= maxEdits ? result : null;
}
