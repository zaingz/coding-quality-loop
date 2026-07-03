import type { Query } from "./types.js";
import type { PostingsStore } from "./postings.js";
import { bm25TermScore } from "./bm25.js";
import { levenshteinDistance } from "./levenshtein.js";

export interface EngineContext {
  postings: PostingsStore;
  fieldNames: readonly string[];
  fieldBoosts: Record<string, number>;
  totalDocs: number;
  k1: number;
  b: number;
  /** All live doc ids, used as the universe for NOT queries. */
  allDocIds: ReadonlySet<string>;
  /** Analyze (tokenize+stopword+stem) a raw string the same way indexing does. */
  analyze: (text: string) => string[];
}

/** Per-doc accumulated match info. */
export interface DocMatch {
  score: number;
  /** field -> set of matched terms (surface tokens) */
  matchedByField: Map<string, Set<string>>;
}

type MatchMap = Map<string, DocMatch>;

function ensureDoc(map: MatchMap, docId: string): DocMatch {
  let m = map.get(docId);
  if (!m) {
    m = { score: 0, matchedByField: new Map() };
    map.set(docId, m);
  }
  return m;
}

function addMatch(map: MatchMap, docId: string, field: string, term: string, score: number): void {
  const m = ensureDoc(map, docId);
  m.score += score;
  let set = m.matchedByField.get(field);
  if (!set) {
    set = new Set();
    m.matchedByField.set(field, set);
  }
  set.add(term);
}

function fieldsToSearch(ctx: EngineContext, explicitField?: string): string[] {
  if (explicitField !== undefined) {
    return ctx.fieldNames.includes(explicitField) ? [explicitField] : [];
  }
  return [...ctx.fieldNames];
}

function scoreTermInField(ctx: EngineContext, term: string, field: string): MatchMap {
  const result: MatchMap = new Map();
  const docs = ctx.postings.getDocsForTerm(term, field);
  const df = ctx.postings.docFrequencyInField(term, field);
  const avgLen = ctx.postings.averageFieldLength(field);
  const boost = ctx.fieldBoosts[field] ?? 1;
  for (const [docId, positions] of docs) {
    const tf = positions.length;
    const fieldLen = ctx.postings.fieldLength(field, docId);
    const raw = bm25TermScore({
      termFrequency: tf,
      docFrequency: df,
      totalDocs: ctx.totalDocs,
      fieldLength: fieldLen,
      avgFieldLength: avgLen,
      k1: ctx.k1,
      b: ctx.b,
    });
    addMatch(result, docId, field, term, raw * boost);
  }
  return result;
}

function evalTerm(ctx: EngineContext, term: string, field?: string): MatchMap {
  const analyzed = ctx.analyze(term);
  if (analyzed.length === 0) return new Map();
  const merged: MatchMap = new Map();
  for (const f of fieldsToSearch(ctx, field)) {
    for (const tok of analyzed) {
      const partial = scoreTermInField(ctx, tok, f);
      mergeSum(merged, partial);
    }
  }
  return merged;
}

function evalPrefix(ctx: EngineContext, prefix: string, field?: string): MatchMap {
  const analyzed = ctx.analyze(prefix);
  const prefixToken = analyzed.length > 0 ? analyzed[0] : prefix.toLowerCase();
  if (prefixToken === undefined || prefixToken.length === 0) return new Map();
  const merged: MatchMap = new Map();
  for (const f of fieldsToSearch(ctx, field)) {
    const matchingTerms = ctx.postings.termsWithPrefix(prefixToken);
    for (const term of matchingTerms) {
      const partial = scoreTermInField(ctx, term, f);
      mergeSum(merged, partial);
    }
  }
  return merged;
}

function evalFuzzy(ctx: EngineContext, word: string, maxEdits: number, field?: string): MatchMap {
  const analyzed = ctx.analyze(word);
  const target = analyzed.length > 0 ? analyzed[0] : word.toLowerCase();
  if (target === undefined || target.length === 0) return new Map();
  const merged: MatchMap = new Map();
  for (const f of fieldsToSearch(ctx, field)) {
    for (const term of ctx.postings.terms()) {
      const dist = levenshteinDistance(target, term, maxEdits);
      if (dist <= maxEdits) {
        const partial = scoreTermInField(ctx, term, f);
        mergeSum(merged, partial);
      }
    }
  }
  return merged;
}

function evalPhrase(ctx: EngineContext, phrase: string, slop: number, field?: string): MatchMap {
  const tokens = ctx.analyze(phrase);
  if (tokens.length === 0) return new Map();
  const merged: MatchMap = new Map();

  for (const f of fieldsToSearch(ctx, field)) {
    if (tokens.length === 1) {
      const tok = tokens[0];
      if (tok === undefined) continue;
      mergeSum(merged, scoreTermInField(ctx, tok, f));
      continue;
    }

    // Candidate docs: intersection of docs containing every token in this field.
    const firstTok = tokens[0];
    if (firstTok === undefined) continue;
    let candidates: Set<string> | undefined;
    for (const tok of tokens) {
      const docs = ctx.postings.getDocsForTerm(tok, f);
      const docSet = new Set(docs.keys());
      candidates = candidates === undefined ? docSet : intersect(candidates, docSet);
      if (candidates.size === 0) break;
    }
    if (!candidates || candidates.size === 0) continue;

    const avgLen = ctx.postings.averageFieldLength(f);
    const boost = ctx.fieldBoosts[f] ?? 1;

    for (const docId of candidates) {
      const positionLists = tokens.map((tok) => ctx.postings.getPositions(tok, f, docId) ?? []);
      const bestGap = bestPhraseWindow(positionLists, slop);
      if (bestGap === undefined) continue; // no valid window within slop

      // Base score: sum of BM25 term scores for the phrase's tokens (in this field).
      const df0 = ctx.postings.docFrequencyInField(tokens[0] ?? "", f);
      const fieldLen = ctx.postings.fieldLength(f, docId);
      let base = 0;
      for (const tok of tokens) {
        const df = ctx.postings.docFrequencyInField(tok, f);
        const tf = (ctx.postings.getPositions(tok, f, docId) ?? []).length;
        base += bm25TermScore({
          termFrequency: tf,
          docFrequency: df || df0,
          totalDocs: ctx.totalDocs,
          fieldLength: fieldLen,
          avgFieldLength: avgLen,
          k1: ctx.k1,
          b: ctx.b,
        });
      }
      // Proximity bonus: closer windows (smaller gap relative to the
      // minimal possible gap of tokens.length - 1) score higher.
      const minGap = tokens.length - 1;
      const proximityBonus = 1 / (1 + Math.max(0, bestGap - minGap));
      const score = base * (1 + proximityBonus) * boost;

      for (const tok of tokens) addMatch(merged, docId, f, tok, 0);
      const m = ensureDoc(merged, docId);
      m.score += score;
    }
  }

  return merged;
}

/**
 * Find the minimum-span window across the given per-token position lists
 * such that positions are non-decreasing in token order and the total gap
 * (last - first) is <= (tokens.length - 1 + slop). Returns the minimal gap
 * found, or undefined if no valid in-order window exists within slop.
 *
 * Implementation: for slop 0 this reduces to checking exact consecutive
 * positions (p, p+1, p+2, ...). For slop > 0 we allow extra spacing.
 */
function bestPhraseWindow(positionLists: number[][], slop: number): number | undefined {
  if (positionLists.some((list) => list.length === 0)) return undefined;
  const first = positionLists[0];
  if (first === undefined) return undefined;

  let best: number | undefined;

  for (const startPos of first) {
    let prev = startPos;
    let ok = true;
    for (let i = 1; i < positionLists.length; i++) {
      const list = positionLists[i];
      if (list === undefined) {
        ok = false;
        break;
      }
      // Find the smallest position in `list` that is > prev (in-order) and
      // within the allowed per-step slop, preferring the closest one.
      const expected = prev + 1;
      let candidate: number | undefined;
      for (const p of list) {
        if (p >= expected && p - expected <= slop) {
          if (candidate === undefined || p < candidate) candidate = p;
        }
      }
      if (candidate === undefined) {
        ok = false;
        break;
      }
      prev = candidate;
    }
    if (ok) {
      const gap = prev - startPos;
      if (best === undefined || gap < best) best = gap;
    }
  }

  return best;
}

function intersect(a: Set<string>, b: Set<string>): Set<string> {
  const out = new Set<string>();
  const [small, large] = a.size <= b.size ? [a, b] : [b, a];
  for (const v of small) {
    if (large.has(v)) out.add(v);
  }
  return out;
}

function mergeSum(target: MatchMap, source: MatchMap): void {
  for (const [docId, info] of source) {
    const dst = ensureDoc(target, docId);
    dst.score += info.score;
    for (const [field, terms] of info.matchedByField) {
      let set = dst.matchedByField.get(field);
      if (!set) {
        set = new Set();
        dst.matchedByField.set(field, set);
      }
      for (const t of terms) set.add(t);
    }
  }
}

function mergeUnion(a: MatchMap, b: MatchMap): MatchMap {
  const out: MatchMap = new Map();
  mergeSum(out, a);
  mergeSum(out, b);
  return out;
}

function mergeIntersect(a: MatchMap, b: MatchMap): MatchMap {
  const out: MatchMap = new Map();
  for (const [docId, infoA] of a) {
    const infoB = b.get(docId);
    if (!infoB) continue;
    const merged: DocMatch = { score: infoA.score + infoB.score, matchedByField: new Map() };
    for (const [field, terms] of infoA.matchedByField) {
      merged.matchedByField.set(field, new Set(terms));
    }
    for (const [field, terms] of infoB.matchedByField) {
      let set = merged.matchedByField.get(field);
      if (!set) {
        set = new Set();
        merged.matchedByField.set(field, set);
      }
      for (const t of terms) set.add(t);
    }
    out.set(docId, merged);
  }
  return out;
}

function evalNot(ctx: EngineContext, inner: MatchMap): MatchMap {
  const out: MatchMap = new Map();
  for (const docId of ctx.allDocIds) {
    if (!inner.has(docId)) {
      out.set(docId, { score: 0, matchedByField: new Map() });
    }
  }
  return out;
}

/**
 * Evaluate a Query AST, returning a map of docId -> accumulated score +
 * matched terms per field.
 *
 * NOT is handled specially when it appears as a top-level AND operand
 * (subtractive) vs. as a bare/OR operand (universe-complement), matching
 * common search-engine semantics: `a AND NOT b` subtracts b from a's
 * results rather than requiring a full-universe complement combined via
 * intersection (equivalent result, but subtractive avoids materializing
 * the whole universe when possible).
 */
export function evaluateQuery(ctx: EngineContext, query: Query): MatchMap {
  if ("term" in query) return evalTerm(ctx, query.term, query.field);
  if ("phrase" in query) return evalPhrase(ctx, query.phrase, query.slop ?? 0, query.field);
  if ("prefix" in query) return evalPrefix(ctx, query.prefix, query.field);
  if ("fuzzy" in query) return evalFuzzy(ctx, query.fuzzy, query.maxEdits ?? 1, query.field);

  if ("and" in query) {
    if (query.and.length === 0) return new Map();
    // Separate NOT operands for subtractive handling.
    const positiveTerms: Query[] = [];
    const negativeTerms: Query[] = [];
    for (const sub of query.and) {
      if ("not" in sub) negativeTerms.push(sub.not);
      else positiveTerms.push(sub);
    }
    let acc: MatchMap | undefined;
    if (positiveTerms.length === 0) {
      // AND of only NOTs: complement of the union of negatives.
      let negUnion: MatchMap = new Map();
      for (const neg of negativeTerms) negUnion = mergeUnion(negUnion, evaluateQuery(ctx, neg));
      acc = evalNot(ctx, negUnion);
    } else {
      for (const sub of positiveTerms) {
        const m = evaluateQuery(ctx, sub);
        acc = acc === undefined ? m : mergeIntersect(acc, m);
        if (acc.size === 0) break;
      }
    }
    for (const neg of negativeTerms) {
      if (!acc || acc.size === 0) break;
      const negMatches = evaluateQuery(ctx, neg);
      const filtered: MatchMap = new Map();
      for (const [docId, info] of acc) {
        if (!negMatches.has(docId)) filtered.set(docId, info);
      }
      acc = filtered;
    }
    return acc ?? new Map();
  }

  if ("or" in query) {
    let acc: MatchMap = new Map();
    for (const sub of query.or) {
      acc = mergeUnion(acc, evaluateQuery(ctx, sub));
    }
    return acc;
  }

  if ("not" in query) {
    const inner = evaluateQuery(ctx, query.not);
    return evalNot(ctx, inner);
  }

  return new Map();
}
