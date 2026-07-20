/**
 * Benchmark harness for @eval/minisearch.
 *
 * Generates a deterministic synthetic corpus of 10,000 documents (seeded
 * Mulberry32 RNG, seed=42), indexes them, runs a fixed query workload, and
 * prints a JSON performance summary.
 *
 * Run with: `npm run build && node dist/bench/bench.js`
 * (or `node --experimental-strip-types bench/bench.ts` on Node 22.6+)
 */

import { SearchIndex } from "../src/index.js";
import { WORDS } from "./words.js";

// ---------------------------------------------------------------------------
// Deterministic RNG: Mulberry32
// ---------------------------------------------------------------------------
function mulberry32(seed: number): () => number {
  let a = seed;
  return function (): number {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rng = mulberry32(42);

function randInt(min: number, max: number): number {
  return Math.floor(rng() * (max - min + 1)) + min;
}

function pickWord(): string {
  const idx = Math.floor(rng() * WORDS.length);
  return WORDS[idx] as string;
}

function randomWords(count: number): string[] {
  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    out.push(pickWord());
  }
  return out;
}

// ---------------------------------------------------------------------------
// Synthetic corpus generation
// ---------------------------------------------------------------------------
interface BenchDoc {
  id: string;
  title: string;
  body: string;
  tags: string[];
}

const CORPUS_SIZE = 10000;

function generateCorpus(): BenchDoc[] {
  const docs: BenchDoc[] = [];
  for (let i = 0; i < CORPUS_SIZE; i++) {
    const titleWordCount = randInt(3, 8);
    const bodyWordCount = randInt(50, 500);
    const tagCount = randInt(0, 5);

    const title = randomWords(titleWordCount).join(" ");
    const body = randomWords(bodyWordCount).join(" ");
    const tags = randomWords(tagCount);

    docs.push({
      id: `doc-${i}`,
      title,
      body,
      tags,
    });
  }
  return docs;
}

// ---------------------------------------------------------------------------
// Timing helpers
// ---------------------------------------------------------------------------
function percentile(sortedValues: number[], p: number): number {
  if (sortedValues.length === 0) return 0;
  const idx = Math.min(
    sortedValues.length - 1,
    Math.floor((p / 100) * sortedValues.length)
  );
  return sortedValues[idx] as number;
}

interface QueryStats {
  count: number;
  total_ms: number;
  p50_us: number;
  p99_us: number;
}

function runTimedQueries(
  label: string,
  count: number,
  fn: (i: number) => void
): QueryStats {
  const durationsUs: number[] = new Array(count);
  const start = process.hrtime.bigint();
  for (let i = 0; i < count; i++) {
    const qStart = process.hrtime.bigint();
    fn(i);
    const qEnd = process.hrtime.bigint();
    durationsUs[i] = Number(qEnd - qStart) / 1000; // ns -> us
  }
  const end = process.hrtime.bigint();
  const totalMs = Number(end - start) / 1_000_000;

  const sorted = durationsUs.slice().sort((a, b) => a - b);
  void label;
  return {
    count,
    total_ms: round2(totalMs),
    p50_us: round2(percentile(sorted, 50)),
    p99_us: round2(percentile(sorted, 99)),
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

// ---------------------------------------------------------------------------
// Rough memory estimate for the index (postings + doc storage), in KB.
// This walks the serialized JSON snapshot size as a proxy for memory use,
// which is a reasonable, dependency-free approximation.
// ---------------------------------------------------------------------------
function estimateMemoryKb(index: SearchIndex<BenchDoc>): number {
  const snapshot = index.toJSON();
  const json = JSON.stringify(snapshot);
  // 2 bytes/char as a rough approximation of V8's internal UTF-16 string storage,
  // which is a closer proxy for in-memory footprint than raw byte length of JSON.
  const bytes = json.length * 2;
  return Math.round(bytes / 1024);
}

// ---------------------------------------------------------------------------
// Main benchmark run
// ---------------------------------------------------------------------------
function main(): void {
  const corpus = generateCorpus();

  const index = new SearchIndex<BenchDoc>({
    fields: {
      title: { boost: 3 },
      body: { boost: 1 },
      tags: { boost: 2 },
    },
  });

  const buildStart = process.hrtime.bigint();
  index.addAll(corpus);
  const buildEnd = process.hrtime.bigint();
  const indexBuildMs = round2(Number(buildEnd - buildStart) / 1_000_000);

  // Precompute query term pools deterministically from the same RNG stream
  // (continuing on from corpus generation for full determinism given seed=42).
  const singleTermQueries: string[] = [];
  for (let i = 0; i < 1000; i++) {
    singleTermQueries.push(pickWord());
  }

  const orTwoQueries: [string, string][] = [];
  for (let i = 0; i < 500; i++) {
    orTwoQueries.push([pickWord(), pickWord()]);
  }

  const andTwoQueries: [string, string][] = [];
  for (let i = 0; i < 500; i++) {
    andTwoQueries.push([pickWord(), pickWord()]);
  }

  const phraseQueries: string[] = [];
  for (let i = 0; i < 200; i++) {
    phraseQueries.push(randomWords(2).join(" "));
  }

  const fuzzyQueries: string[] = [];
  for (let i = 0; i < 100; i++) {
    const word = pickWord();
    // introduce a single-character edit distance-1 mutation
    const pos = randInt(0, word.length - 1);
    const mutated =
      word.slice(0, pos) + String.fromCharCode(97 + randInt(0, 25)) + word.slice(pos + 1);
    fuzzyQueries.push(mutated);
  }

  const singleTermStats = runTimedQueries("single_term", singleTermQueries.length, (i) => {
    index.search({ term: singleTermQueries[i] as string }, { limit: 10 });
  });

  const orTwoStats = runTimedQueries("or_two", orTwoQueries.length, (i) => {
    const [a, b] = orTwoQueries[i] as [string, string];
    index.search({ or: [{ term: a }, { term: b }] }, { limit: 10 });
  });

  const andTwoStats = runTimedQueries("and_two", andTwoQueries.length, (i) => {
    const [a, b] = andTwoQueries[i] as [string, string];
    index.search({ and: [{ term: a }, { term: b }] }, { limit: 10 });
  });

  const phraseStats = runTimedQueries("phrase", phraseQueries.length, (i) => {
    index.search({ phrase: phraseQueries[i] as string }, { limit: 10 });
  });

  const fuzzyStats = runTimedQueries("fuzzy_edit1", fuzzyQueries.length, (i) => {
    index.search({ fuzzy: fuzzyQueries[i] as string, maxEdits: 1 }, { limit: 10 });
  });

  const memoryKb = estimateMemoryKb(index);

  const summary = {
    index_build_ms: indexBuildMs,
    index_size_docs: index.size,
    index_memory_estimate_kb: memoryKb,
    queries: {
      single_term: singleTermStats,
      or_two: orTwoStats,
      and_two: andTwoStats,
      phrase: phraseStats,
      fuzzy_edit1: fuzzyStats,
    },
  };

  console.log(JSON.stringify(summary, null, 2));
}

main();
