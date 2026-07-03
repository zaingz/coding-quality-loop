export const WORDS: string[] = Array.from({ length: 512 }, (_, i) => {
  const prefixes = ["alpha", "bravo", "cafe", "delta", "echo", "fjord", "gamma", "hazel", "ionic", "juno", "karma", "lumen", "mango", "nova", "orbit", "pixel"];
  const suffixes = ["search", "index", "token", "rank", "field", "query", "phrase", "fuzzy", "unicode", "vector", "memory", "cache", "result", "score", "boost", "filter"];
  return `${prefixes[i % prefixes.length]}${suffixes[Math.floor(i / prefixes.length) % suffixes.length]}${i}`;
});
