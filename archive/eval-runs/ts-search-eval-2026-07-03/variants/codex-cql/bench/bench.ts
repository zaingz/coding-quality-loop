import { SearchIndex, type Query, type SearchDocument } from "../src/index.js";
import { WORDS } from "./words.js";

type BenchDoc = SearchDocument & { id: string; title: string; body: string; tags: string[] };
type QuerySummary = { count: number; total_ms: number; p50_us: number; p99_us: number };

function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state += 0x6D2B79F5;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function pick(rng: () => number): string {
  return WORDS[Math.floor(rng() * WORDS.length)] ?? WORDS[0] ?? "word";
}

function words(rng: () => number, count: number): string {
  const out: string[] = [];
  for (let i = 0; i < count; i += 1) out.push(pick(rng));
  return out.join(" ");
}

function generateCorpus(): BenchDoc[] {
  const rng = mulberry32(42);
  const docs: BenchDoc[] = [];
  for (let i = 0; i < 10_000; i += 1) {
    const titleCount = 3 + Math.floor(rng() * 6);
    const bodyCount = 50 + Math.floor(rng() * 451);
    const tagCount = Math.floor(rng() * 6);
    const tags: string[] = [];
    for (let j = 0; j < tagCount; j += 1) tags.push(pick(rng));
    docs.push({ id: String(i).padStart(5, "0"), title: words(rng, titleCount), body: words(rng, bodyCount), tags });
  }
  return docs;
}

function percentile(values: number[], p: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[index] ?? 0;
}

function measure(count: number, makeQuery: (i: number) => string | Query<BenchDoc>, index: SearchIndex<BenchDoc>): QuerySummary {
  const durations: number[] = [];
  const started = performance.now();
  for (let i = 0; i < count; i += 1) {
    const q = makeQuery(i);
    const before = performance.now();
    if (typeof q === "string") index.search(q, { limit: 10 });
    else index.search(q, { limit: 10 });
    durations.push((performance.now() - before) * 1000);
  }
  return {
    count,
    total_ms: Math.round((performance.now() - started) * 100) / 100,
    p50_us: Math.round(percentile(durations, 50)),
    p99_us: Math.round(percentile(durations, 99))
  };
}

function typo(word: string): string {
  return word.length > 2 ? `${word.slice(0, -1)}x` : `${word}x`;
}

const corpus = generateCorpus();
const index = new SearchIndex<BenchDoc>({ fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 } } });
const buildStart = performance.now();
index.addAll(corpus);
const buildMs = performance.now() - buildStart;
const memoryKb = Math.round(Buffer.byteLength(JSON.stringify(index.toJSON()), "utf8") / 1024);

const summary = {
  index_build_ms: Math.round(buildMs * 100) / 100,
  index_size_docs: index.size,
  index_memory_estimate_kb: memoryKb,
  queries: {
    single_term: measure(1000, (i) => WORDS[i % WORDS.length] ?? "word", index),
    or_two: measure(500, (i) => `${WORDS[i % WORDS.length] ?? "word"} OR ${WORDS[(i + 17) % WORDS.length] ?? "term"}`, index),
    and_two: measure(500, (i) => `${WORDS[i % WORDS.length] ?? "word"} AND ${WORDS[(i + 17) % WORDS.length] ?? "term"}`, index),
    phrase: measure(200, (i) => ({ phrase: `${WORDS[i % WORDS.length] ?? "word"} ${WORDS[(i + 1) % WORDS.length] ?? "term"}`, slop: 2 }), index),
    fuzzy_edit1: measure(100, (i) => ({ fuzzy: typo(WORDS[i % WORDS.length] ?? "word"), maxEdits: 1 }), index)
  }
};

console.log(JSON.stringify(summary, null, 2));
