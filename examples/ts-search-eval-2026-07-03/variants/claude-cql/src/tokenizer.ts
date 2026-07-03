import type { StopwordsOption } from "./types.js";

/**
 * Default English stopword list. Small, fixed, curated set — no external
 * dataset or dependency (zero-runtime-dependency constraint).
 */
const ENGLISH_STOPWORDS: readonly string[] = [
  "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in",
  "into", "is", "it", "no", "not", "of", "on", "or", "such", "that", "the",
  "their", "then", "there", "these", "they", "this", "to", "was", "will",
  "with",
];

/**
 * Resolve a StopwordsOption into a concrete Set<string>.
 */
export function resolveStopwords(option: StopwordsOption | undefined): Set<string> {
  if (option === undefined || option === "english") {
    return new Set(ENGLISH_STOPWORDS);
  }
  if (option === "none") {
    return new Set();
  }
  return option;
}

/**
 * Default unicode-aware tokenizer. Splits on runs of Unicode letters/numbers
 * (\p{L}\p{N}), lowercases, and NFC-normalizes so combining-character
 * sequences match their precomposed equivalents (e.g. "cafe\u0301" ~ "café").
 */
export function defaultTokenizer(text: string): string[] {
  const normalized = text.normalize("NFC").toLowerCase();
  const matches = normalized.match(/[\p{L}\p{N}]+/gu);
  return matches ? matches : [];
}

/**
 * Tokenize text with the given tokenizer, stemmer, and stopwords, producing
 * the final list of index/query tokens (stopwords removed, stemmer applied).
 */
export function analyze(
  text: string,
  tokenizer: (text: string) => string[],
  stemmer: (token: string) => string,
  stopwords: Set<string>,
): string[] {
  const raw = tokenizer(text);
  const out: string[] = [];
  for (const tok of raw) {
    const normalizedTok = tok.normalize("NFC").toLowerCase();
    if (stopwords.has(normalizedTok)) continue;
    out.push(stemmer(normalizedTok));
  }
  return out;
}
