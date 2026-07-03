/**
 * Unicode-safe tokenizer and stopword handling.
 */

// Matches runs of unicode letters/numbers. \p{L} and \p{N} require the 'u' flag.
// Combining marks (\p{M}) are included so accented characters composed of
// base + combining mark (e.g. "e" + U+0301) are treated as part of the word.
const WORD_RE = /[\p{L}\p{N}\p{M}]+/gu;

/** Default tokenizer: unicode-aware word split, lowercased, NFC-normalized. */
export function defaultTokenizer(text: string): string[] {
  const normalized = text.normalize("NFC").toLowerCase();
  const matches = normalized.match(WORD_RE);
  return matches ? matches : [];
}

// A compact, standard English stopword list.
export const ENGLISH_STOPWORDS: ReadonlySet<string> = new Set([
  "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in",
  "into", "is", "it", "its", "no", "not", "of", "on", "or", "such", "that",
  "the", "their", "then", "there", "these", "they", "this", "to", "was",
  "will", "with", "he", "she", "we", "you", "i", "your", "his", "her", "them",
  "so", "do", "does", "did", "have", "has", "had", "can", "could", "would",
  "should", "may", "might", "shall", "from", "up", "down", "out", "about",
  "than", "too", "very", "just", "been", "being", "am", "were", "which",
  "who", "whom", "what", "when", "where", "why", "how", "all", "each",
  "few", "more", "most", "other", "some", "only", "own", "same",
]);

export function resolveStopwords(
  stopwords: Set<string> | "english" | "none" | undefined
): ReadonlySet<string> {
  if (stopwords === undefined || stopwords === "english") {
    return ENGLISH_STOPWORDS;
  }
  if (stopwords === "none") {
    return new Set();
  }
  return stopwords;
}

export function identityStemmer(token: string): string {
  return token;
}
