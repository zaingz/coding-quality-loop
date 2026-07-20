/**
 * Extract a snippet of `length` characters from `rawText` centered on the
 * first occurrence of any of `matchTerms` (case-insensitive, unicode-aware
 * word matching), wrapping matches in <mark>...</mark>. If no match term is
 * found in the text, returns a plain leading excerpt (no <mark>), so callers
 * requesting a snippet on a field that doesn't contain the match never
 * throw and still get a usable result.
 */
export function buildSnippet(rawText: string, matchTerms: readonly string[], length: number): string {
  if (rawText.length === 0) return "";

  const normalized = rawText.normalize("NFC");
  const lower = normalized.toLowerCase();

  // Find all occurrences of any match term as a whole word, earliest first.
  let firstIndex = -1;
  let firstLen = 0;
  const uniqueTerms = Array.from(new Set(matchTerms.map((t) => t.normalize("NFC").toLowerCase()))).filter(
    (t) => t.length > 0,
  );

  const occurrences: Array<{ start: number; len: number }> = [];
  if (uniqueTerms.length > 0) {
    const wordRe = /[\p{L}\p{N}]+/gu;
    let m: RegExpExecArray | null;
    while ((m = wordRe.exec(lower)) !== null) {
      const word = m[0];
      if (uniqueTerms.includes(word)) {
        occurrences.push({ start: m.index, len: word.length });
        if (firstIndex === -1) {
          firstIndex = m.index;
          firstLen = word.length;
        }
      }
    }
  }

  let start: number;
  if (firstIndex === -1) {
    start = 0;
  } else {
    const half = Math.floor(length / 2);
    start = Math.max(0, firstIndex + Math.floor(firstLen / 2) - half);
  }
  let end = Math.min(normalized.length, start + length);
  // Slide window left if we hit the end early and there's room on the left.
  if (end - start < length) {
    start = Math.max(0, end - length);
  }

  const windowOccurrences = occurrences.filter((o) => o.start >= start && o.start + o.len <= end);

  let result = "";
  let cursor = start;
  for (const occ of windowOccurrences) {
    if (occ.start < cursor) continue;
    result += normalized.slice(cursor, occ.start);
    result += "<mark>" + normalized.slice(occ.start, occ.start + occ.len) + "</mark>";
    cursor = occ.start + occ.len;
  }
  result += normalized.slice(cursor, end);

  const prefix = start > 0 ? "…" : "";
  const suffix = end < normalized.length ? "…" : "";
  return prefix + result + suffix;
}
