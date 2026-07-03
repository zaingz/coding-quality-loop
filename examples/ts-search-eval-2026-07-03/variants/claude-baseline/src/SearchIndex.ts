import type {
  FieldConfig,
  IndexSnapshot,
  Query,
  SearchIndexOptions,
  SearchOptions,
  SearchResult,
} from "./types.js";
import { defaultTokenizer, identityStemmer, resolveStopwords } from "./tokenizer.js";
import { parseQueryString } from "./queryParser.js";
import { levenshteinWithinBound } from "./levenshtein.js";

/** Internal posting: positions of a term within a specific doc+field. */
type Postings = Map<string, Map<string, Map<string, number[]>>>;
// term -> field -> docId -> positions[]

interface FieldMatchAccumulator {
  score: number;
  terms: Set<string>;
}

/** Per-document, per-field accumulated match info used during scoring. */
interface DocScoreAccumulator {
  score: number;
  fieldMatches: Map<string, FieldMatchAccumulator>;
}

export class SearchIndex<Doc extends object> {
  private readonly fields: Record<string, Required<FieldConfig>>;
  private readonly tokenizerFn: (text: string) => string[];
  private readonly stopwords: ReadonlySet<string>;
  private readonly stemmerFn: (token: string) => string;
  private readonly idField: string;
  private readonly k1: number;
  private readonly b: number;

  // term -> field -> docId -> positions[]
  private postings: Postings = new Map();
  // docId -> field -> token count
  private fieldLengths: Map<string, Map<string, number>> = new Map();
  // field -> sum of token counts across live docs (for average field length)
  private totalFieldLength: Map<string, number> = new Map();
  // docId -> doc
  private documents: Map<string, Doc> = new Map();
  // insertion order tracking (not strictly required, but useful for determinism/debug)
  private insertionOrder: string[] = [];

  constructor(options: SearchIndexOptions<Doc>) {
    if (!options || !options.fields || Object.keys(options.fields).length === 0) {
      throw new Error("SearchIndex requires at least one field in options.fields");
    }
    const fields: Record<string, Required<FieldConfig>> = {};
    for (const [name, cfg] of Object.entries(options.fields)) {
      fields[name] = { boost: cfg.boost ?? 1 };
    }
    this.fields = fields;
    this.tokenizerFn = options.tokenizer ?? defaultTokenizer;
    this.stopwords = resolveStopwords(options.stopwords);
    this.stemmerFn = options.stemmer ?? identityStemmer;
    this.idField = (options.idField as string | undefined) ?? "id";
    this.k1 = options.k1 ?? 1.2;
    this.b = options.b ?? 0.75;

    for (const fieldName of Object.keys(this.fields)) {
      this.totalFieldLength.set(fieldName, 0);
    }
  }

  // ---------------------------------------------------------------------
  // Basic accessors
  // ---------------------------------------------------------------------

  get size(): number {
    return this.documents.size;
  }

  has(id: string): boolean {
    return this.documents.has(id);
  }

  *docs(): IterableIterator<{ id: string; doc: Doc }> {
    for (const [id, doc] of this.documents) {
      yield { id, doc };
    }
  }

  *terms(): IterableIterator<string> {
    for (const term of this.postings.keys()) {
      yield term;
    }
  }

  docFrequency(term: string): number {
    const processed = this.processTerm(term);
    if (processed === null) return 0;
    const fieldMap = this.postings.get(processed);
    if (!fieldMap) return 0;
    const docIds = new Set<string>();
    for (const docMap of fieldMap.values()) {
      for (const docId of docMap.keys()) {
        docIds.add(docId);
      }
    }
    return docIds.size;
  }

  // ---------------------------------------------------------------------
  // Tokenization helpers
  // ---------------------------------------------------------------------

  /** Tokenize + stem, but keep stopwords (needed for phrase position alignment). */
  private tokenizeKeepStopwords(text: string): string[] {
    return this.tokenizerFn(text).map((t) => this.stemmerFn(t));
  }

  /** Process a single raw query term the same way indexed terms are processed. */
  private processTerm(raw: string): string | null {
    const tokens = this.tokenizerFn(raw);
    if (tokens.length === 0) return null;
    const first = tokens[0] as string;
    if (this.stopwords.has(first)) return null;
    return this.stemmerFn(first);
  }

  /** Process a phrase string into an array of processed tokens (stopwords kept as null-marker skipped). */
  private processPhraseTokens(raw: string): string[] {
    const tokens = this.tokenizerFn(raw);
    return tokens.map((t) => this.stemmerFn(t));
  }

  private extractFieldText(doc: Doc, field: string): string {
    const value = (doc as Record<string, unknown>)[field];
    if (value === undefined || value === null) {
      return "";
    }
    if (Array.isArray(value)) {
      return value.map((v) => String(v)).join(" ");
    }
    if (typeof value === "number" || typeof value === "string" || typeof value === "boolean") {
      return String(value);
    }
    // Undeclared/unsupported shapes are treated as empty (silently ignored).
    return "";
  }

  private getDocId(doc: Doc): string {
    const value = (doc as Record<string, unknown>)[this.idField];
    if (value === undefined || value === null) {
      throw new Error(`Document is missing id field "${this.idField}"`);
    }
    return String(value);
  }

  // ---------------------------------------------------------------------
  // Mutations
  // ---------------------------------------------------------------------

  add(doc: Doc): void {
    const id = this.getDocId(doc);
    if (this.documents.has(id)) {
      this.remove(id);
    }
    this.documents.set(id, doc);
    this.insertionOrder.push(id);

    const fieldLenMap = new Map<string, number>();
    for (const fieldName of Object.keys(this.fields)) {
      const text = this.extractFieldText(doc, fieldName);
      const tokens = this.tokenizeKeepStopwords(text);
      fieldLenMap.set(fieldName, tokens.length);
      this.totalFieldLength.set(
        fieldName,
        (this.totalFieldLength.get(fieldName) ?? 0) + tokens.length
      );

      for (let pos = 0; pos < tokens.length; pos++) {
        const token = tokens[pos] as string;
        if (this.stopwords.has(token)) continue;
        let fieldMap = this.postings.get(token);
        if (!fieldMap) {
          fieldMap = new Map();
          this.postings.set(token, fieldMap);
        }
        let docMap = fieldMap.get(fieldName);
        if (!docMap) {
          docMap = new Map();
          fieldMap.set(fieldName, docMap);
        }
        let positions = docMap.get(id);
        if (!positions) {
          positions = [];
          docMap.set(id, positions);
        }
        positions.push(pos);
      }
    }
    this.fieldLengths.set(id, fieldLenMap);
  }

  addAll(docs: Doc[]): void {
    for (const doc of docs) {
      this.add(doc);
    }
  }

  remove(id: string): void {
    if (!this.documents.has(id)) return;

    const fieldLenMap = this.fieldLengths.get(id);
    if (fieldLenMap) {
      for (const [fieldName, len] of fieldLenMap) {
        this.totalFieldLength.set(
          fieldName,
          (this.totalFieldLength.get(fieldName) ?? 0) - len
        );
      }
    }

    // Remove all postings referencing this doc; clean up orphaned maps.
    const termsToDelete: string[] = [];
    for (const [term, fieldMap] of this.postings) {
      const fieldsToDelete: string[] = [];
      for (const [fieldName, docMap] of fieldMap) {
        if (docMap.has(id)) {
          docMap.delete(id);
          if (docMap.size === 0) {
            fieldsToDelete.push(fieldName);
          }
        }
      }
      for (const f of fieldsToDelete) {
        fieldMap.delete(f);
      }
      if (fieldMap.size === 0) {
        termsToDelete.push(term);
      }
    }
    for (const term of termsToDelete) {
      this.postings.delete(term);
    }

    this.documents.delete(id);
    this.fieldLengths.delete(id);
    this.insertionOrder = this.insertionOrder.filter((x) => x !== id);
  }

  update(id: string, patch: Partial<Doc>): void {
    const existing = this.documents.get(id);
    if (!existing) {
      throw new Error(`Cannot update: document with id "${id}" does not exist`);
    }
    const changedFields = new Set(Object.keys(patch));
    const merged: Doc = { ...existing, ...patch };

    // Remove old postings only for changed declared fields, and adjust their length totals.
    const fieldLenMap = this.fieldLengths.get(id);
    for (const fieldName of Object.keys(this.fields)) {
      if (!changedFields.has(fieldName)) continue;

      const oldLen = fieldLenMap?.get(fieldName) ?? 0;
      this.totalFieldLength.set(
        fieldName,
        (this.totalFieldLength.get(fieldName) ?? 0) - oldLen
      );

      const termsToDelete: string[] = [];
      for (const [term, fMap] of this.postings) {
        const docMap = fMap.get(fieldName);
        if (docMap && docMap.has(id)) {
          docMap.delete(id);
          if (docMap.size === 0) {
            fMap.delete(fieldName);
          }
        }
        if (fMap.size === 0) {
          termsToDelete.push(term);
        }
      }
      for (const term of termsToDelete) {
        this.postings.delete(term);
      }
    }

    this.documents.set(id, merged);

    // Re-index changed fields only.
    const newFieldLenMap = fieldLenMap ?? new Map<string, number>();
    for (const fieldName of Object.keys(this.fields)) {
      if (!changedFields.has(fieldName)) continue;

      const text = this.extractFieldText(merged, fieldName);
      const tokens = this.tokenizeKeepStopwords(text);
      newFieldLenMap.set(fieldName, tokens.length);
      this.totalFieldLength.set(
        fieldName,
        (this.totalFieldLength.get(fieldName) ?? 0) + tokens.length
      );

      for (let pos = 0; pos < tokens.length; pos++) {
        const token = tokens[pos] as string;
        if (this.stopwords.has(token)) continue;
        let fMap = this.postings.get(token);
        if (!fMap) {
          fMap = new Map();
          this.postings.set(token, fMap);
        }
        let docMap = fMap.get(fieldName);
        if (!docMap) {
          docMap = new Map();
          fMap.set(fieldName, docMap);
        }
        let positions = docMap.get(id);
        if (!positions) {
          positions = [];
          docMap.set(id, positions);
        }
        positions.push(pos);
      }
    }
    this.fieldLengths.set(id, newFieldLenMap);
  }

  // ---------------------------------------------------------------------
  // Search
  // ---------------------------------------------------------------------

  search(query: string | Query, options: SearchOptions<Doc> = {}): SearchResult<Doc>[] {
    const limit = options.limit ?? 10;
    const offset = options.offset ?? 0;

    let ast: Query | null;
    if (typeof query === "string") {
      ast = parseQueryString(query);
    } else {
      ast = query;
    }

    if (ast === null) {
      return [];
    }

    const accumulators = new Map<string, DocScoreAccumulator>();
    const matchedIds = this.evaluate(ast, accumulators, options.boostFields);

    if (matchedIds === null) {
      return [];
    }

    const results: SearchResult<Doc>[] = [];
    for (const id of matchedIds) {
      const doc = this.documents.get(id);
      if (!doc) continue;
      if (options.filter && !options.filter(doc)) continue;

      const acc = accumulators.get(id);
      const score = acc ? acc.score : 0;
      const matched: { field: string; terms: string[] }[] = [];
      if (acc) {
        for (const [field, m] of acc.fieldMatches) {
          if (m.terms.size > 0) {
            matched.push({ field, terms: Array.from(m.terms).sort() });
          }
        }
      }
      matched.sort((a, c) => a.field.localeCompare(c.field));

      const result: SearchResult<Doc> = {
        id,
        doc,
        score,
        matched,
      };

      if (options.snippet) {
        const snippetText = this.buildSnippet(
          doc,
          options.snippet.field,
          options.snippet.length,
          matched
        );
        if (snippetText !== undefined) {
          result.snippet = snippetText;
        }
      }

      results.push(result);
    }

    results.sort((x, y) => {
      if (y.score !== x.score) return y.score - x.score;
      return x.id < y.id ? -1 : x.id > y.id ? 1 : 0;
    });

    return results.slice(offset, offset + limit);
  }

  // ---------------------------------------------------------------------
  // Query evaluation - returns set of matching doc ids, accumulates scores
  // ---------------------------------------------------------------------

  private evaluate(
    query: Query,
    acc: Map<string, DocScoreAccumulator>,
    boostFields: Record<string, number> | undefined
  ): Set<string> | null {
    if ("term" in query) {
      return this.evalTerm(query.term, query.field, acc, boostFields);
    }
    if ("phrase" in query) {
      return this.evalPhrase(query.phrase, query.field, query.slop ?? 0, acc, boostFields);
    }
    if ("prefix" in query) {
      return this.evalPrefix(query.prefix, query.field, acc, boostFields);
    }
    if ("fuzzy" in query) {
      return this.evalFuzzy(query.fuzzy, query.field, query.maxEdits ?? 1, acc, boostFields);
    }
    if ("and" in query) {
      let result: Set<string> | null = null;
      for (const sub of query.and) {
        const subResult = this.evaluate(sub, acc, boostFields);
        const subSet = subResult ?? new Set<string>();
        if (result === null) {
          result = subSet;
        } else {
          const intersected = new Set<string>();
          for (const id of result) {
            if (subSet.has(id)) intersected.add(id);
          }
          result = intersected;
        }
      }
      return result ?? new Set();
    }
    if ("or" in query) {
      const result = new Set<string>();
      for (const sub of query.or) {
        const subResult = this.evaluate(sub, acc, boostFields);
        if (subResult) {
          for (const id of subResult) result.add(id);
        }
      }
      return result;
    }
    if ("not" in query) {
      // NOT is only meaningful combined with other clauses; standalone NOT
      // returns "all docs except matches" so it can be intersected upstream.
      const subAcc = new Map<string, DocScoreAccumulator>();
      const subResult = this.evaluate(query.not, subAcc, boostFields) ?? new Set<string>();
      const all = new Set<string>(this.documents.keys());
      for (const id of subResult) {
        all.delete(id);
      }
      return all;
    }
    return new Set();
  }

  private getFieldBoost(field: string, boostFields: Record<string, number> | undefined): number {
    const base = this.fields[field]?.boost ?? 1;
    const override = boostFields?.[field];
    return override !== undefined ? override : base;
  }

  private targetFields(field: string | undefined): string[] {
    if (field === undefined) {
      return Object.keys(this.fields);
    }
    // nonexistent field name -> no fields to search, matches nothing
    return this.fields[field] ? [field] : [];
  }

  private addScore(
    acc: Map<string, DocScoreAccumulator>,
    docId: string,
    field: string,
    term: string,
    score: number
  ): void {
    let docAcc = acc.get(docId);
    if (!docAcc) {
      docAcc = { score: 0, fieldMatches: new Map() };
      acc.set(docId, docAcc);
    }
    docAcc.score += score;
    let fieldAcc = docAcc.fieldMatches.get(field);
    if (!fieldAcc) {
      fieldAcc = { score: 0, terms: new Set() };
      docAcc.fieldMatches.set(field, fieldAcc);
    }
    fieldAcc.score += score;
    fieldAcc.terms.add(term);
  }

  /** BM25 score contribution for a single term/field/doc combination. */
  private bm25Score(term: string, field: string, docId: string): number {
    const fieldMap = this.postings.get(term);
    if (!fieldMap) return 0;
    const docMap = fieldMap.get(field);
    if (!docMap) return 0;
    const positions = docMap.get(docId);
    if (!positions) return 0;

    const tf = positions.length;
    const docCountWithTerm = docMap.size;
    const totalDocs = this.documents.size;
    if (totalDocs === 0 || docCountWithTerm === 0) return 0;

    // BM25 idf (using the +1 smoothing variant to keep it non-negative for common terms)
    const idf = Math.log(1 + (totalDocs - docCountWithTerm + 0.5) / (docCountWithTerm + 0.5));

    const docFieldLen = this.fieldLengths.get(docId)?.get(field) ?? 0;
    const totalLen = this.totalFieldLength.get(field) ?? 0;
    const avgFieldLen = totalDocs > 0 ? totalLen / totalDocs : 0;
    const denom =
      tf + this.k1 * (1 - this.b + (this.b * docFieldLen) / (avgFieldLen || 1));
    if (denom === 0) return 0;
    const score = idf * ((tf * (this.k1 + 1)) / denom);
    return score;
  }

  private evalTerm(
    rawTerm: string,
    field: string | undefined,
    acc: Map<string, DocScoreAccumulator>,
    boostFields: Record<string, number> | undefined
  ): Set<string> {
    const processed = this.processTerm(rawTerm);
    const result = new Set<string>();
    if (processed === null) return result;

    const fields = this.targetFields(field);
    for (const f of fields) {
      const fieldMap = this.postings.get(processed);
      const docMap = fieldMap?.get(f);
      if (!docMap) continue;
      const boost = this.getFieldBoost(f, boostFields);
      for (const docId of docMap.keys()) {
        result.add(docId);
        const s = this.bm25Score(processed, f, docId) * boost;
        this.addScore(acc, docId, f, processed, s);
      }
    }
    return result;
  }

  private evalPrefix(
    rawPrefix: string,
    field: string | undefined,
    acc: Map<string, DocScoreAccumulator>,
    boostFields: Record<string, number> | undefined
  ): Set<string> {
    const tokens = this.tokenizerFn(rawPrefix);
    const result = new Set<string>();
    if (tokens.length === 0) return result;
    const prefix = this.stemmerFn(tokens[0] as string);
    if (prefix.length === 0) return result;

    const fields = this.targetFields(field);
    for (const term of this.postings.keys()) {
      if (!term.startsWith(prefix)) continue;
      const fieldMap = this.postings.get(term);
      if (!fieldMap) continue;
      for (const f of fields) {
        const docMap = fieldMap.get(f);
        if (!docMap) continue;
        const boost = this.getFieldBoost(f, boostFields);
        for (const docId of docMap.keys()) {
          result.add(docId);
          const s = this.bm25Score(term, f, docId) * boost;
          this.addScore(acc, docId, f, term, s);
        }
      }
    }
    return result;
  }

  private evalFuzzy(
    rawTerm: string,
    field: string | undefined,
    maxEdits: 1 | 2,
    acc: Map<string, DocScoreAccumulator>,
    boostFields: Record<string, number> | undefined
  ): Set<string> {
    const tokens = this.tokenizerFn(rawTerm);
    const result = new Set<string>();
    if (tokens.length === 0) return result;
    const target = this.stemmerFn(tokens[0] as string);
    if (target.length === 0) return result;

    const fields = this.targetFields(field);

    for (const term of this.postings.keys()) {
      const dist = levenshteinWithinBound(target, term, maxEdits);
      if (dist === null) continue;
      const fieldMap = this.postings.get(term);
      if (!fieldMap) continue;
      // closer matches score slightly higher via a decay factor
      const fuzzyFactor = 1 / (1 + dist);
      for (const f of fields) {
        const docMap = fieldMap.get(f);
        if (!docMap) continue;
        const boost = this.getFieldBoost(f, boostFields);
        for (const docId of docMap.keys()) {
          result.add(docId);
          const s = this.bm25Score(term, f, docId) * boost * fuzzyFactor;
          this.addScore(acc, docId, f, term, s);
        }
      }
    }
    return result;
  }

  private evalPhrase(
    rawPhrase: string,
    field: string | undefined,
    slop: number,
    acc: Map<string, DocScoreAccumulator>,
    boostFields: Record<string, number> | undefined
  ): Set<string> {
    const phraseTokens = this.processPhraseTokens(rawPhrase);
    const result = new Set<string>();
    if (phraseTokens.length === 0) return result;
    // Filter out tokens that are pure stopwords for lookups, but keep original
    // positions/order so relative offsets stay correct.
    if (phraseTokens.length === 1) {
      return this.evalTerm(phraseTokens[0] as string, field, acc, boostFields);
    }

    const fields = this.targetFields(field);

    for (const f of fields) {
      // Find candidate docs: intersection of docs containing all non-stopword phrase terms in this field.
      const termDocMaps: (Map<string, number[]> | undefined)[] = phraseTokens.map((t) => {
        if (this.stopwords.has(t)) return undefined;
        return this.postings.get(t)?.get(f);
      });

      // If every term is a stopword, nothing to match on.
      const nonStopIndices: number[] = [];
      for (let idx = 0; idx < phraseTokens.length; idx++) {
        if (!this.stopwords.has(phraseTokens[idx] as string)) nonStopIndices.push(idx);
      }
      if (nonStopIndices.length === 0) continue;

      // Candidate doc ids: intersect docMaps of non-stopword terms.
      let candidateIds: Set<string> | null = null;
      for (const idx of nonStopIndices) {
        const docMap = termDocMaps[idx];
        const ids = docMap ? new Set(docMap.keys()) : new Set<string>();
        if (candidateIds === null) {
          candidateIds = ids;
        } else {
          const intersected = new Set<string>();
          for (const id of candidateIds) {
            if (ids.has(id)) intersected.add(id);
          }
          candidateIds = intersected;
        }
      }
      if (!candidateIds || candidateIds.size === 0) continue;

      const boost = this.getFieldBoost(f, boostFields);

      for (const docId of candidateIds) {
        const proximity = this.computePhraseProximity(phraseTokens, f, docId, slop);
        if (proximity === null) continue; // doesn't satisfy slop constraint
        result.add(docId);

        // Score: sum of BM25 for each distinct term, weighted by proximity closeness.
        let termScoreSum = 0;
        const seenTerms = new Set<string>();
        for (const idx of nonStopIndices) {
          const t = phraseTokens[idx] as string;
          if (seenTerms.has(t)) continue;
          seenTerms.add(t);
          termScoreSum += this.bm25Score(t, f, docId);
        }
        // proximity: 0 means exact adjacency (best); scale factor decays with distance.
        const proximityFactor = 1 / (1 + proximity);
        const s = termScoreSum * boost * proximityFactor;
        for (const t of seenTerms) {
          this.addScore(acc, docId, f, t, s / seenTerms.size);
        }
      }
    }

    return result;
  }

  /**
   * Determines whether the phrase (with allowed slop) occurs in the given field/doc,
   * and returns a "proximity distance" measure (0 = perfectly adjacent in order) or
   * null if no valid alignment exists within the slop budget.
   *
   * Slop semantics: the total displacement from perfectly-consecutive positions,
   * allowing terms to be out of exact adjacency by up to `slop` positions overall.
   * With slop=0, terms must appear in exact consecutive order (accounting for
   * skipped stopwords in the phrase, which are treated as wildcards of width 1).
   */
  private computePhraseProximity(
    phraseTokens: string[],
    field: string,
    docId: string,
    slop: number
  ): number | null {
    // Build list of position arrays for each token in phrase order.
    // For stopword tokens (no postings), treat as "wildcard": any position works,
    // so we don't constrain that slot directly but still count it in offset math.
    const positionLists: (number[] | null)[] = phraseTokens.map((t) => {
      if (this.stopwords.has(t)) return null; // wildcard
      const docMap = this.postings.get(t)?.get(field);
      const positions = docMap?.get(docId);
      return positions ?? [];
    });

    // If any non-wildcard slot has zero positions, phrase cannot match.
    for (const list of positionLists) {
      if (list !== null && list.length === 0) return null;
    }

    // Try every starting position from the first non-wildcard term's positions,
    // offset-adjusted to slot 0, and check alignment.
    let firstConcreteIdx = -1;
    for (let i = 0; i < positionLists.length; i++) {
      if (positionLists[i] !== null) {
        firstConcreteIdx = i;
        break;
      }
    }
    if (firstConcreteIdx === -1) return null; // all wildcards, shouldn't happen (checked above)

    const firstPositions = positionLists[firstConcreteIdx] as number[];
    let best: number | null = null;

    for (const anchorPos of firstPositions) {
      const basePos = anchorPos - firstConcreteIdx; // expected slot-0 position
      let totalDisplacement = 0;
      let valid = true;

      for (let slot = 0; slot < positionLists.length; slot++) {
        const expectedPos = basePos + slot;
        const list = positionLists[slot];
        if (list === null || list === undefined) {
          // wildcard slot: no constraint, contributes 0 displacement
          continue;
        }
        // find position in `list` closest to expectedPos
        let closest = Infinity;
        for (const p of list) {
          const d = Math.abs(p - expectedPos);
          if (d < closest) closest = d;
        }
        if (closest === Infinity) {
          valid = false;
          break;
        }
        totalDisplacement += closest;
      }

      if (valid && totalDisplacement <= slop) {
        if (best === null || totalDisplacement < best) {
          best = totalDisplacement;
        }
      }
    }

    return best;
  }

  // ---------------------------------------------------------------------
  // Snippet generation
  // ---------------------------------------------------------------------

  private buildSnippet(
    doc: Doc,
    field: string,
    length: number,
    matched: { field: string; terms: string[] }[]
  ): string | undefined {
    const text = this.extractFieldText(doc, field);
    if (text.length === 0) return undefined;

    const fieldMatch = matched.find((m) => m.field === field);
    const matchTerms = fieldMatch ? new Set(fieldMatch.terms) : new Set<string>();

    // Tokenize with positions (character offsets) so we can mark matches inline.
    const WORD_RE = /[\p{L}\p{N}\p{M}]+/gu;
    const normalized = text.normalize("NFC");
    const lowerNormalized = normalized.toLowerCase();

    type TokenSpan = { start: number; end: number; token: string };
    const spans: TokenSpan[] = [];
    let match: RegExpExecArray | null;
    WORD_RE.lastIndex = 0;
    while ((match = WORD_RE.exec(lowerNormalized)) !== null) {
      spans.push({ start: match.index, end: match.index + match[0].length, token: this.stemmerFn(match[0]) });
    }

    if (spans.length === 0) {
      // no tokens at all - just return a truncated excerpt, no marks
      return normalized.slice(0, length);
    }

    // Find first span index that matches a query term.
    let matchSpanIdx = -1;
    if (matchTerms.size > 0) {
      for (let i = 0; i < spans.length; i++) {
        if (matchTerms.has((spans[i] as TokenSpan).token)) {
          matchSpanIdx = i;
          break;
        }
      }
    }

    let windowStart: number;
    if (matchSpanIdx === -1) {
      // No match in this field - return excerpt from the start (per spec: snippet
      // on a field that doesn't contain the match should still return something reasonable).
      windowStart = 0;
    } else {
      const matchCharPos = (spans[matchSpanIdx] as TokenSpan).start;
      windowStart = Math.max(0, matchCharPos - Math.floor(length / 2));
    }

    let windowEnd = Math.min(normalized.length, windowStart + length);
    // Adjust windowStart if we hit the end early
    if (windowEnd - windowStart < length) {
      windowStart = Math.max(0, windowEnd - length);
    }

    // Build the excerpt with <mark> tags around matched tokens that fall in the window.
    let resultStr = "";
    let cursor = windowStart;
    for (const span of spans) {
      if (span.end <= windowStart) continue;
      if (span.start >= windowEnd) break;

      const spanStart = Math.max(span.start, windowStart);
      const spanEnd = Math.min(span.end, windowEnd);

      if (spanStart > cursor) {
        resultStr += normalized.slice(cursor, spanStart);
      }

      const originalText = normalized.slice(spanStart, spanEnd);
      if (matchTerms.has(span.token)) {
        resultStr += `<mark>${originalText}</mark>`;
      } else {
        resultStr += originalText;
      }
      cursor = spanEnd;
    }
    if (cursor < windowEnd) {
      resultStr += normalized.slice(cursor, windowEnd);
    }

    const prefix = windowStart > 0 ? "…" : "";
    const suffix = windowEnd < normalized.length ? "…" : "";
    return prefix + resultStr + suffix;
  }

  // ---------------------------------------------------------------------
  // Serialization
  // ---------------------------------------------------------------------

  toJSON(): IndexSnapshot {
    const fieldsOut: Record<string, { boost: number }> = {};
    for (const [name, cfg] of Object.entries(this.fields)) {
      fieldsOut[name] = { boost: cfg.boost };
    }

    const postingsOut: IndexSnapshot["postings"] = {};
    for (const [term, fieldMap] of this.postings) {
      const fieldsRecord: Record<string, Record<string, number[]>> = {};
      for (const [field, docMap] of fieldMap) {
        const docsRecord: Record<string, number[]> = {};
        for (const [docId, positions] of docMap) {
          docsRecord[docId] = positions.slice();
        }
        fieldsRecord[field] = docsRecord;
      }
      postingsOut[term] = fieldsRecord;
    }

    const fieldLengthsOut: Record<string, Record<string, number>> = {};
    for (const [docId, fMap] of this.fieldLengths) {
      const rec: Record<string, number> = {};
      for (const [field, len] of fMap) {
        rec[field] = len;
      }
      fieldLengthsOut[docId] = rec;
    }

    const totalFieldLengthOut: Record<string, number> = {};
    for (const [field, total] of this.totalFieldLength) {
      totalFieldLengthOut[field] = total;
    }

    const docsOut: Record<string, unknown> = {};
    for (const [id, doc] of this.documents) {
      docsOut[id] = doc;
    }

    return {
      version: 1,
      fields: fieldsOut,
      idField: this.idField,
      k1: this.k1,
      b: this.b,
      postings: postingsOut,
      fieldLengths: fieldLengthsOut,
      totalFieldLength: totalFieldLengthOut,
      docs: docsOut,
      docOrder: this.insertionOrder.slice(),
    };
  }

  static fromJSON<Doc extends object>(
    snapshot: IndexSnapshot,
    options?: Pick<SearchIndexOptions<Doc>, "tokenizer" | "stopwords" | "stemmer">
  ): SearchIndex<Doc> {
    const fieldsForCtor: Record<string, FieldConfig> = {};
    for (const [name, cfg] of Object.entries(snapshot.fields)) {
      fieldsForCtor[name] = { boost: cfg.boost };
    }

    const index = new SearchIndex<Doc>({
      fields: fieldsForCtor,
      idField: snapshot.idField as keyof Doc,
      k1: snapshot.k1,
      b: snapshot.b,
      tokenizer: options?.tokenizer,
      stopwords: options?.stopwords,
      stemmer: options?.stemmer,
    });

    // Restore documents
    for (const id of snapshot.docOrder) {
      const doc = snapshot.docs[id] as Doc;
      index.documents.set(id, doc);
      index.insertionOrder.push(id);
    }
    // In case docOrder is incomplete/missing entries, ensure all docs present.
    for (const [id, doc] of Object.entries(snapshot.docs)) {
      if (!index.documents.has(id)) {
        index.documents.set(id, doc as Doc);
        index.insertionOrder.push(id);
      }
    }

    // Restore field lengths
    for (const [docId, fMap] of Object.entries(snapshot.fieldLengths)) {
      const m = new Map<string, number>();
      for (const [field, len] of Object.entries(fMap)) {
        m.set(field, len);
      }
      index.fieldLengths.set(docId, m);
    }

    // Restore total field lengths
    for (const [field, total] of Object.entries(snapshot.totalFieldLength)) {
      index.totalFieldLength.set(field, total);
    }

    // Restore postings
    for (const [term, fieldsRecord] of Object.entries(snapshot.postings)) {
      const fieldMap = new Map<string, Map<string, number[]>>();
      for (const [field, docsRecord] of Object.entries(fieldsRecord)) {
        const docMap = new Map<string, number[]>();
        for (const [docId, positions] of Object.entries(docsRecord)) {
          docMap.set(docId, positions.slice());
        }
        fieldMap.set(field, docMap);
      }
      index.postings.set(term, fieldMap);
    }

    return index;
  }
}
