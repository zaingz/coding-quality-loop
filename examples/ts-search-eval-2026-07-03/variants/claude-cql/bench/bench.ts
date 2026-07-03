import { performance } from "node:perf_hooks";
import { SearchIndex } from "../src/SearchIndex.js";
import { mulberry32, randInt, pick } from "./rng.js";
import { VOCABULARY, TAG_VOCABULARY } from "./words.js";

interface BenchDoc {
  id: string;
  title: string;
  body: string;
  tags: string[];
}

const SEED = 42;
const CORPUS_SIZE = 10_000;

function generateCorpus(): BenchDoc[] {
  const rng = mulberry32(SEED);
  const docs: BenchDoc[] = [];
  for (let i = 0; i < CORPUS_SIZE; i++) {
    const titleWordCount = randInt(rng, 3, 9); // 3-8 words
    const bodyWordCount = randInt(rng, 50, 501); // 50-500 words
    const tagCount = randInt(rng, 0, 6); // 0-5 tags

    const titleWords: string[] = [];
    for (let w = 0; w < titleWordCount; w++) titleWords.push(pick(rng, VOCABULARY));

    const bodyWords: string[] = [];
    for (let w = 0; w < bodyWordCount; w++) bodyWords.push(pick(rng, VOCABULARY));

    const tags: string[] = [];
    const usedTags = new Set<string>();
    for (let t = 0; t < tagCount; t++) {
      const tag = pick(rng, TAG_VOCABULARY);
      if (!usedTags.has(tag)) {
        usedTags.add(tag);
        tags.push(tag);
      }
    }

    docs.push({
      id: `doc-${i}`,
      title: titleWords.join(" "),
      body: bodyWords.join(" "),
      tags,
    });
  }
  return docs;
}

interface Percentiles {
  count: number;
  total_ms: number;
  p50_us: number;
  p99_us: number;
}

function summarize(samplesUs: number[]): Percentiles {
  const sorted = [...samplesUs].sort((a, b) => a - b);
  const p50 = percentile(sorted, 0.5);
  const p99 = percentile(sorted, 0.99);
  const totalUs = samplesUs.reduce((a, b) => a + b, 0);
  return {
    count: samplesUs.length,
    total_ms: round(totalUs / 1000),
    p50_us: round(p50),
    p99_us: round(p99),
  };
}

function percentile(sortedAsc: number[], p: number): number {
  if (sortedAsc.length === 0) return 0;
  const idx = Math.min(sortedAsc.length - 1, Math.floor(p * sortedAsc.length));
  return sortedAsc[idx] ?? 0;
}

function round(n: number): number {
  return Math.round(n * 100) / 100;
}

function timeQuery(fn: () => void): number {
  const start = performance.now();
  fn();
  const end = performance.now();
  return (end - start) * 1000; // convert ms -> us
}

function main(): void {
  const rng = mulberry32(SEED + 1); // separate stream for query generation

  const corpus = generateCorpus();

  const index = new SearchIndex<BenchDoc>({
    fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 } },
  });

  const buildStart = performance.now();
  index.addAll(corpus);
  const buildEnd = performance.now();

  const memoryEstimateBytes = JSON.stringify(index.toJSON()).length;

  // --- Workload ---
  const singleTermSamples: number[] = [];
  for (let i = 0; i < 1000; i++) {
    const term = pick(rng, VOCABULARY);
    singleTermSamples.push(timeQuery(() => index.search({ term })));
  }

  const orTwoSamples: number[] = [];
  for (let i = 0; i < 500; i++) {
    const t1 = pick(rng, VOCABULARY);
    const t2 = pick(rng, VOCABULARY);
    orTwoSamples.push(
      timeQuery(() => index.search({ or: [{ term: t1 }, { term: t2 }] })),
    );
  }

  const andTwoSamples: number[] = [];
  for (let i = 0; i < 500; i++) {
    const t1 = pick(rng, VOCABULARY);
    const t2 = pick(rng, VOCABULARY);
    andTwoSamples.push(
      timeQuery(() => index.search({ and: [{ term: t1 }, { term: t2 }] })),
    );
  }

  const phraseSamples: number[] = [];
  for (let i = 0; i < 200; i++) {
    const t1 = pick(rng, VOCABULARY);
    const t2 = pick(rng, VOCABULARY);
    phraseSamples.push(timeQuery(() => index.search({ phrase: `${t1} ${t2}` })));
  }

  const fuzzySamples: number[] = [];
  for (let i = 0; i < 100; i++) {
    const base = pick(rng, VOCABULARY);
    // Introduce a single-character edit to force a "close but not exact" query.
    const pos = randInt(rng, 0, base.length);
    const mutated = base.slice(0, pos) + "x" + base.slice(pos + 1);
    fuzzySamples.push(timeQuery(() => index.search({ fuzzy: mutated, maxEdits: 1 })));
  }

  const summary = {
    index_build_ms: round(buildEnd - buildStart),
    index_size_docs: index.size,
    index_memory_estimate_kb: round(memoryEstimateBytes / 1024),
    queries: {
      single_term: summarize(singleTermSamples),
      or_two: summarize(orTwoSamples),
      and_two: summarize(andTwoSamples),
      phrase: summarize(phraseSamples),
      fuzzy_edit1: summarize(fuzzySamples),
    },
  };

  console.log(JSON.stringify(summary, null, 2));
}

main();
