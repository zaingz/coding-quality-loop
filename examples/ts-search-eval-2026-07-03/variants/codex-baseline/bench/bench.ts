import { SearchIndex } from '../src/index.js';
import { WORDS } from './words.js';

type BenchDoc = { id: string; title: string; body: string; tags: string[] };
type QueryStats = { count: number; total_ms: number; p50_us: number; p99_us: number };

type BenchSummary = {
  index_build_ms: number;
  index_size_docs: number;
  index_memory_estimate_kb: number;
  queries: Record<'single_term' | 'or_two' | 'and_two' | 'phrase' | 'fuzzy_edit1', QueryStats>;
};

function mulberry32(seed: number): () => number {
  let t = seed >>> 0;
  return () => {
    t += 0x6D2B79F5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function int(rng: () => number, min: number, max: number): number {
  return Math.floor(rng() * (max - min + 1)) + min;
}

function pick(rng: () => number): string {
  return WORDS[int(rng, 0, WORDS.length - 1)] ?? WORDS[0];
}

function words(rng: () => number, count: number): string[] {
  const out: string[] = [];
  for (let i = 0; i < count; i += 1) out.push(pick(rng));
  return out;
}

function generateDocs(): BenchDoc[] {
  const rng = mulberry32(42);
  const docs: BenchDoc[] = [];
  for (let i = 0; i < 10_000; i += 1) {
    const title = words(rng, int(rng, 3, 8)).join(' ');
    const body = words(rng, int(rng, 50, 120)).join(' ');
    const tags = words(rng, int(rng, 0, 5));
    docs.push({ id: String(i).padStart(5, '0'), title, body, tags });
  }
  return docs;
}

function nowMs(): number {
  return Number(process.hrtime.bigint()) / 1_000_000;
}

function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[idx] ?? 0;
}

function measure(count: number, run: (i: number) => void): QueryStats {
  const samplesUs: number[] = [];
  const startAll = nowMs();
  for (let i = 0; i < count; i += 1) {
    const start = nowMs();
    run(i);
    samplesUs.push((nowMs() - start) * 1000);
  }
  const total = nowMs() - startAll;
  return {
    count,
    total_ms: Math.round(total * 1000) / 1000,
    p50_us: Math.round(percentile(samplesUs, 50)),
    p99_us: Math.round(percentile(samplesUs, 99))
  };
}

function mutateOne(word: string): string {
  const chars = [...word];
  if (chars.length === 0) return 'x';
  chars[0] = chars[0] === 'x' ? 'y' : 'x';
  return chars.join('');
}

const docs = generateDocs();
const index = new SearchIndex<BenchDoc>({
  fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 } },
  stopwords: 'none'
});

const memoryBeforeBuild = process.memoryUsage().heapUsed;
const buildStart = nowMs();
index.addAll(docs);
const indexBuildMs = nowMs() - buildStart;
const memoryAfterBuild = process.memoryUsage().heapUsed;
const vocab = [...index.terms()];

const singleTerms = Array.from({ length: 1000 }, (_v, i) => vocab[(i * 37) % vocab.length] ?? 'missing');
const orPairs = Array.from({ length: 500 }, (_v, i) => [vocab[(i * 17) % vocab.length] ?? 'a', vocab[(i * 29 + 7) % vocab.length] ?? 'b'] as const);
const andPairs = Array.from({ length: 500 }, (_v, i) => [vocab[(i * 23) % vocab.length] ?? 'a', vocab[(i * 31 + 11) % vocab.length] ?? 'b'] as const);
const phrases = docs.slice(0, 200).map((doc) => doc.body.split(' ').slice(5, 7).join(' '));
const fuzzyTerms = Array.from({ length: 100 }, (_v, i) => mutateOne(vocab[(i * 41) % vocab.length] ?? 'term'));

const queries = {
  single_term: measure(1000, (i) => {
    index.search(singleTerms[i] ?? 'missing', { limit: 10 });
  }),
  or_two: measure(500, (i) => {
    const pair = orPairs[i] ?? ['a', 'b'];
    index.search(`${pair[0]} OR ${pair[1]}`, { limit: 10 });
  }),
  and_two: measure(500, (i) => {
    const pair = andPairs[i] ?? ['a', 'b'];
    index.search(`${pair[0]} AND ${pair[1]}`, { limit: 10 });
  }),
  phrase: measure(200, (i) => {
    index.search({ phrase: phrases[i] ?? 'a b', slop: 0 }, { limit: 10 });
  }),
  fuzzy_edit1: measure(100, (i) => {
    index.search({ fuzzy: fuzzyTerms[i] ?? 'x', maxEdits: 1 }, { limit: 10 });
  })
};

const summary: BenchSummary = {
  index_build_ms: Math.round(indexBuildMs * 1000) / 1000,
  index_size_docs: index.size,
  index_memory_estimate_kb: Math.max(1, Math.round(Math.max(0, memoryAfterBuild - memoryBeforeBuild) / 1024)),
  queries
};

console.log(JSON.stringify(summary, null, 2));
