import type {
  DocEntry,
  FieldConfig,
  IndexOptions,
  IndexSnapshot,
  Query,
  SearchOptions,
  SearchResult,
} from "./types.js";
import { analyze, defaultTokenizer, resolveStopwords } from "./tokenizer.js";
import { PostingsStore } from "./postings.js";
import { evaluateQuery, type EngineContext } from "./queryEngine.js";
import { parseQueryString } from "./queryParser.js";
import { buildSnippet } from "./snippet.js";

/** Extract a field's raw text value from a document, coercing per spec rules. */
function extractFieldText(doc: unknown, field: string): string {
  if (typeof doc !== "object" || doc === null) return "";
  const rec = doc as Record<string, unknown>;
  if (!(field in rec)) return "";
  const value = rec[field];
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) {
    return value
      .map((v) => (typeof v === "string" ? v : typeof v === "number" ? String(v) : ""))
      .join(" ");
  }
  return "";
}

function docIdOf<Doc>(doc: Doc, idField: keyof Doc): string {
  const rec = doc as Record<string, unknown>;
  const raw = rec[idField as string];
  if (typeof raw === "string") return raw;
  if (typeof raw === "number") return String(raw);
  throw new TypeError(`Document is missing a valid id field ("${String(idField)}")`);
}

export class SearchIndex<Doc> {
  private readonly fields: Record<string, Required<FieldConfig>>;
  private readonly fieldNames: string[];
  private readonly tokenizerFn: (text: string) => string[];
  private readonly stemmerFn: (token: string) => string;
  private readonly stopwords: Set<string>;
  private readonly idField: keyof Doc;
  private readonly k1: number;
  private readonly b: number;

  private readonly postings: PostingsStore;
  private readonly docStore = new Map<string, Doc>();
  private readonly docOrder: string[] = [];
  /** field -> docId -> raw text, kept for snippet extraction. */
  private readonly rawFieldText = new Map<string, Map<string, string>>();

  constructor(options: IndexOptions<Doc>) {
    this.fields = {};
    for (const [name, cfg] of Object.entries(options.fields)) {
      this.fields[name] = { boost: cfg.boost ?? 1 };
    }
    this.fieldNames = Object.keys(this.fields);
    this.tokenizerFn = options.tokenizer ?? defaultTokenizer;
    this.stemmerFn = options.stemmer ?? ((t: string) => t);
    this.stopwords = resolveStopwords(options.stopwords);
    this.idField = options.idField ?? ("id" as keyof Doc);
    this.k1 = options.k1 ?? 1.2;
    this.b = options.b ?? 0.75;

    this.postings = new PostingsStore(this.fieldNames);
    for (const f of this.fieldNames) {
      this.rawFieldText.set(f, new Map());
    }
  }

  get size(): number {
    return this.docStore.size;
  }

  has(id: string): boolean {
    return this.docStore.has(id);
  }

  private analyzeText(text: string): string[] {
    return analyze(text, this.tokenizerFn, this.stemmerFn, this.stopwords);
  }

  add(doc: Doc): void {
    const id = docIdOf(doc, this.idField);
    if (this.docStore.has(id)) {
      this.removeInternal(id);
    }
    this.docStore.set(id, doc);
    this.docOrder.push(id);
    for (const field of this.fieldNames) {
      this.reindexField(id, doc, field);
    }
  }

  addAll(docs: readonly Doc[]): void {
    for (const doc of docs) this.add(doc);
  }

  remove(id: string): void {
    if (!this.docStore.has(id)) return;
    this.removeInternal(id);
    const idx = this.docOrder.indexOf(id);
    if (idx !== -1) this.docOrder.splice(idx, 1);
  }

  private removeInternal(id: string): void {
    this.postings.removeDoc(id, this.fieldNames);
    for (const field of this.fieldNames) {
      this.rawFieldText.get(field)?.delete(id);
    }
    this.docStore.delete(id);
  }

  update(id: string, patch: Partial<Doc>): void {
    const existing = this.docStore.get(id);
    if (!existing) return;
    const merged = { ...existing, ...patch } as Doc;
    this.docStore.set(id, merged);
    for (const field of Object.keys(patch as object)) {
      if (this.fieldNames.includes(field)) {
        this.reindexField(id, merged, field);
      }
    }
  }

  private reindexField(id: string, doc: Doc, field: string): void {
    const text = extractFieldText(doc, field);
    const tokens = this.analyzeText(text);
    this.postings.indexField(id, field, tokens);
    this.rawFieldText.get(field)?.set(id, text);
  }

  *docs(): IterableIterator<DocEntry<Doc>> {
    for (const id of this.docOrder) {
      const doc = this.docStore.get(id);
      if (doc !== undefined) yield { id, doc };
    }
  }

  terms(): IterableIterator<string> {
    return this.postings.terms();
  }

  docFrequency(term: string): number {
    const analyzed = this.analyzeText(term);
    if (analyzed.length === 0) return 0;
    const tok = analyzed[0];
    return tok !== undefined ? this.postings.docFrequency(tok) : 0;
  }

  search(query: string | Query, options: SearchOptions<Doc> = {}): SearchResult<Doc>[] {
    const ast = typeof query === "string" ? parseQueryString(query) : query;
    if (ast === undefined) return [];

    const boostFields: Record<string, number> = {};
    for (const [name, cfg] of Object.entries(this.fields)) {
      boostFields[name] = cfg.boost;
    }
    if (options.boostFields) {
      for (const [name, mult] of Object.entries(options.boostFields)) {
        const current = boostFields[name];
        if (current !== undefined) {
          boostFields[name] = current * mult;
        }
        // Nonexistent field name in boostFields: silently ignored (no throw).
      }
    }

    const ctx: EngineContext = {
      postings: this.postings,
      fieldNames: this.fieldNames,
      fieldBoosts: boostFields,
      totalDocs: this.docStore.size,
      k1: this.k1,
      b: this.b,
      allDocIds: new Set(this.docStore.keys()),
      analyze: (text: string) => this.analyzeText(text),
    };

    const matches = evaluateQuery(ctx, ast);

    let results: SearchResult<Doc>[] = [];
    for (const [id, info] of matches) {
      const doc = this.docStore.get(id);
      if (doc === undefined) continue;
      // Every entry in `matches` is already a legitimate match produced by
      // evaluateQuery (including NOT-query results, which legitimately have
      // score 0 and no matched terms) — no additional filtering needed here.
      const matched = [...info.matchedByField.entries()].map(([field, terms]) => ({
        field,
        terms: [...terms],
      }));
      results.push({ id, doc, score: info.score, matched });
    }

    results.sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
    });

    if (options.filter) {
      results = results.filter((r) => options.filter?.(r.doc) ?? true);
    }

    const offset = options.offset ?? 0;
    const limit = options.limit ?? 10;
    results = results.slice(offset, offset + limit);

    if (options.snippet) {
      const { field, length } = options.snippet;
      for (const r of results) {
        const rawText = this.rawFieldText.get(field)?.get(r.id) ?? "";
        const matchedTerms = r.matched.find((m) => m.field === field)?.terms ?? [];
        r.snippet = buildSnippet(rawText, matchedTerms, length);
      }
    }

    return results;
  }

  toJSON(): IndexSnapshot {
    const fields: Record<string, { boost: number }> = {};
    for (const [name, cfg] of Object.entries(this.fields)) fields[name] = { boost: cfg.boost };

    const docsOut: Record<string, unknown> = {};
    for (const [id, doc] of this.docStore) docsOut[id] = doc;

    const fieldLengths: Record<string, Record<string, number>> = {};
    const rawFieldText: Record<string, Record<string, string>> = {};
    for (const field of this.fieldNames) {
      fieldLengths[field] = {};
      rawFieldText[field] = {};
      for (const id of this.docOrder) {
        const len = this.postings.fieldLength(field, id);
        if (len > 0) fieldLengths[field][id] = len;
        const raw = this.rawFieldText.get(field)?.get(id);
        if (raw !== undefined) rawFieldText[field][id] = raw;
      }
    }

    const postingsOut: Record<string, Record<string, Record<string, number[]>>> = {};
    for (const term of this.postings.terms()) {
      const fieldMap: Record<string, Record<string, number[]>> = {};
      for (const field of this.fieldNames) {
        const docMap = this.postings.getDocsForTerm(term, field);
        if (docMap.size === 0) continue;
        const docsForField: Record<string, number[]> = {};
        for (const [id, positions] of docMap) docsForField[id] = positions;
        fieldMap[field] = docsForField;
      }
      if (Object.keys(fieldMap).length > 0) postingsOut[term] = fieldMap;
    }

    return {
      version: 1,
      idField: String(this.idField),
      fields,
      k1: this.k1,
      b: this.b,
      docs: docsOut,
      docOrder: [...this.docOrder],
      fieldLengths,
      rawFieldText,
      postings: postingsOut,
    };
  }

  static fromJSON<Doc>(
    snapshot: IndexSnapshot,
    options?: Pick<IndexOptions<Doc>, "tokenizer" | "stemmer" | "stopwords">,
  ): SearchIndex<Doc> {
    const fieldsConfig: Record<string, FieldConfig> = {};
    for (const [name, cfg] of Object.entries(snapshot.fields)) fieldsConfig[name] = { boost: cfg.boost };

    const index = new SearchIndex<Doc>({
      fields: fieldsConfig,
      tokenizer: options?.tokenizer,
      stemmer: options?.stemmer,
      stopwords: options?.stopwords,
      idField: snapshot.idField as keyof Doc,
      k1: snapshot.k1,
      b: snapshot.b,
    });

    for (const id of snapshot.docOrder) {
      const doc = snapshot.docs[id] as Doc;
      index.docStore.set(id, doc);
    }
    index.docOrder.push(...snapshot.docOrder);

    for (const field of index.fieldNames) {
      const lengths = snapshot.fieldLengths[field] ?? {};
      const rawMap = snapshot.rawFieldText[field] ?? {};
      const rawStore = index.rawFieldText.get(field);
      if (rawStore) {
        for (const [id, text] of Object.entries(rawMap)) rawStore.set(id, text);
      }
      void lengths; // field lengths are reconstructed via postings below
    }

    // Rebuild postings directly from the snapshot (exact restoration,
    // avoids re-tokenizing which could differ if caller doesn't supply the
    // same tokenizer/stemmer as the original index).
    for (const [term, fieldMap] of Object.entries(snapshot.postings)) {
      for (const [field, docMap] of Object.entries(fieldMap)) {
        for (const [docId, positions] of Object.entries(docMap)) {
          index.postings.restorePosting(term, field, docId, positions);
        }
      }
    }
    // Restore field lengths precisely (in case a field was indexed but has
    // no postings, e.g., a field with only stopwords).
    for (const field of index.fieldNames) {
      const lengths = snapshot.fieldLengths[field] ?? {};
      for (const [id, len] of Object.entries(lengths)) {
        index.postings.restoreFieldLength(field, id, len);
      }
    }

    return index;
  }
}
