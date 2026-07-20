/**
 * Fixed, deterministic vocabulary used to synthesize the benchmark corpus.
 * Generated once from a small set of syllables via a deterministic
 * combination method (no external word list / dependency), then frozen as a
 * literal array so the vocabulary itself never changes between runs.
 */
function generateVocabulary(): string[] {
  const consonants = ["b", "c", "d", "f", "g", "h", "j", "k", "l", "m", "n", "p", "r", "s", "t", "v", "w", "z"];
  const vowels = ["a", "e", "i", "o", "u"];
  const words = new Set<string>();

  // Deterministic nested-loop combination of 2-syllable (CVCV) words.
  for (const c1 of consonants) {
    for (const v1 of vowels) {
      for (const c2 of consonants) {
        for (const v2 of vowels) {
          words.add(c1 + v1 + c2 + v2);
        }
      }
    }
  }

  // Add 3-syllable (CVCVCV) words for a much larger, more realistic
  // vocabulary — keeps average document frequency per term low enough for
  // representative query benchmarking, mirroring a real natural-language
  // corpus rather than a tiny closed vocabulary.
  for (const c1 of consonants) {
    for (const v1 of vowels) {
      for (const c2 of consonants) {
        for (const v2 of vowels) {
          for (const c3 of consonants.slice(0, 6)) {
            words.add(c1 + v1 + c2 + v2 + c3 + v1);
            if (words.size >= 20000) return [...words];
          }
        }
      }
    }
  }

  return [...words];
}

export const VOCABULARY: readonly string[] = Object.freeze(generateVocabulary());

export const TAG_VOCABULARY: readonly string[] = Object.freeze(
  VOCABULARY.slice(0, 40).map((w) => `tag-${w}`),
);
