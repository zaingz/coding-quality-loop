/**
 * Deterministic vocabulary list used by the benchmark's synthetic corpus
 * generator. Generated once via a fixed algorithm (consonant-vowel syllable
 * combinations) so it's reproducible without needing an external word list
 * file or network access.
 */

const CONSONANTS = [
  "b", "c", "d", "f", "g", "h", "j", "k", "l", "m",
  "n", "p", "qu", "r", "s", "t", "v", "w", "x", "y", "z",
];
const VOWELS = ["a", "e", "i", "o", "u"];

function buildVocabulary(): string[] {
  const words: string[] = [];
  for (const c1 of CONSONANTS) {
    for (const v1 of VOWELS) {
      for (const c2 of CONSONANTS) {
        const word = c1 + v1 + c2 + VOWELS[(c1.length + v1.length + c2.length) % VOWELS.length];
        words.push(word);
      }
    }
  }
  return words;
}

/** Fixed, deterministic vocabulary of ~2200 pronounceable synthetic words. */
export const WORDS: readonly string[] = Object.freeze(buildVocabulary());
