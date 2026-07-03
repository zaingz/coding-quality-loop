export type FieldConfig = { boost?: number };

export type StopwordOption = Set<string> | 'english' | 'none';

export type Query =
  | { term: string; field?: string }
  | { phrase: string; field?: string; slop?: number }
  | { prefix: string; field?: string }
  | { fuzzy: string; field?: string; maxEdits?: 1 | 2 }
  | { and: Query[] }
  | { or: Query[] }
  | { not: Query };

export type SearchOptions<Doc extends object> = {
  limit?: number;
  offset?: number;
  filter?: (doc: Doc) => boolean;
  boostFields?: Record<string, number>;
  snippet?: { field: string; length: number };
};

export type SearchResult<Doc extends object> = {
  id: string;
  doc: Doc;
  score: number;
  matched: { field: string; terms: string[] }[];
  snippet?: string;
};

export type SearchIndexOptions<Doc extends object> = {
  fields: Record<string, FieldConfig>;
  tokenizer?: (text: string) => string[];
  stopwords?: StopwordOption;
  stemmer?: (token: string) => string;
  idField?: Extract<keyof Doc, string>;
  k1?: number;
  b?: number;
};

export type SearchIndexSnapshot<Doc extends object> = {
  version: 1;
  options: {
    fields: Record<string, FieldConfig>;
    idField: string;
    k1: number;
    b: number;
    stopwords: 'english' | 'none' | string[];
  };
  docs: Doc[];
};

type FieldStats = {
  length: number;
  termFreqs: Map<string, number>;
  positions: Map<string, number[]>;
};

type Posting = {
  tf: number;
  positions: number[];
};

type EvalHit = {
  score: number;
  matched: Map<string, Set<string>>;
};

type Token =
  | { kind: 'word'; value: string }
  | { kind: 'phrase'; value: string }
  | { kind: 'op'; value: 'AND' | 'OR' | 'NOT' }
  | { kind: 'lparen' }
  | { kind: 'rparen' };

const ENGLISH_STOPWORDS = new Set([
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'but', 'by', 'for', 'from', 'has', 'he', 'in',
  'is', 'it', 'its', 'of', 'on', 'or', 'that', 'the', 'to', 'was', 'were', 'will', 'with'
]);

const WORD_RE = /[\p{L}\p{N}]+/gu;

export function defaultTokenizer(text: string): string[] {
  const normalized = text.normalize('NFC').toLocaleLowerCase();
  const out: string[] = [];
  for (const match of normalized.matchAll(WORD_RE)) {
    out.push(match[0]);
  }
  return out;
}

function stopwordSet(option: StopwordOption | undefined): Set<string> {
  if (option === undefined || option === 'english') return new Set(ENGLISH_STOPWORDS);
  if (option === 'none') return new Set<string>();
  return new Set([...option].map((word) => word.normalize('NFC').toLocaleLowerCase()));
}

function valueToText(value: unknown): string {
  if (value === undefined || value === null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'bigint' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    return value.map((part) => valueToText(part)).filter((part) => part.length > 0).join(' ');
  }
  return '';
}

function getProperty(obj: object, key: string): unknown {
  return Object.prototype.hasOwnProperty.call(obj, key) ? (obj as Record<string, unknown>)[key] : undefined;
}

function setProperty<Doc extends object>(obj: Doc, key: string, value: unknown): Doc {
  const base: Record<string, unknown> = { ...(obj as Record<string, unknown>) };
  base[key] = value;
  return base as Doc;
}

function cloneMapOfSets(source: Map<string, Set<string>>): Map<string, Set<string>> {
  const copy = new Map<string, Set<string>>();
  for (const [field, terms] of source) copy.set(field, new Set(terms));
  return copy;
}

function mergeMatched(target: Map<string, Set<string>>, source: Map<string, Set<string>>): void {
  for (const [field, terms] of source) {
    let bucket = target.get(field);
    if (!bucket) {
      bucket = new Set<string>();
      target.set(field, bucket);
    }
    for (const term of terms) bucket.add(term);
  }
}

function addMatch(hit: EvalHit, field: string, term: string): void {
  let terms = hit.matched.get(field);
  if (!terms) {
    terms = new Set<string>();
    hit.matched.set(field, terms);
  }
  terms.add(term);
}

function isQuery(value: unknown): value is Query {
  if (typeof value !== 'object' || value === null) return false;
  const rec = value as Record<string, unknown>;
  return 'term' in rec || 'phrase' in rec || 'prefix' in rec || 'fuzzy' in rec || 'and' in rec || 'or' in rec || 'not' in rec;
}

export class SearchIndex<Doc extends object> {
  private readonly fields: Record<string, FieldConfig>;
  private readonly fieldNames: string[];
  private readonly tokenizer: (text: string) => string[];
  private readonly stopwords: Set<string>;
  private readonly stemmer: (token: string) => string;
  private readonly idField: string;
  private readonly k1: number;
  private readonly b: number;
  private readonly docsById = new Map<string, Doc>();
  private readonly postings = new Map<string, Map<string, Map<string, Posting>>>();
  private readonly fieldStatsByDoc = new Map<string, Map<string, FieldStats>>();
  private readonly fieldTotalLengths = new Map<string, number>();

  constructor(options: SearchIndexOptions<Doc>) {
    this.fields = { ...options.fields };
    this.fieldNames = Object.keys(this.fields).sort();
    this.tokenizer = options.tokenizer ?? defaultTokenizer;
    this.stopwords = stopwordSet(options.stopwords);
    this.stemmer = options.stemmer ?? ((token: string) => token);
    this.idField = options.idField ?? 'id';
    this.k1 = options.k1 ?? 1.2;
    this.b = options.b ?? 0.75;
    for (const field of this.fieldNames) this.fieldTotalLengths.set(field, 0);
  }

  get size(): number {
    return this.docsById.size;
  }

  has(id: string): boolean {
    return this.docsById.has(id);
  }

  add(doc: Doc): void {
    const rawId = getProperty(doc, this.idField);
    if (rawId === undefined || rawId === null || String(rawId).length === 0) {
      throw new Error(`Document is missing id field '${this.idField}'`);
    }
    const id = String(rawId);
    if (this.docsById.has(id)) this.remove(id);
    this.docsById.set(id, doc);
    const perField = new Map<string, FieldStats>();
    for (const field of this.fieldNames) {
      const stats = this.buildFieldStats(valueToText(getProperty(doc, field)));
      perField.set(field, stats);
      this.fieldTotalLengths.set(field, (this.fieldTotalLengths.get(field) ?? 0) + stats.length);
      this.addFieldPostings(id, field, stats);
    }
    this.fieldStatsByDoc.set(id, perField);
  }

  addAll(docs: Iterable<Doc>): void {
    for (const doc of docs) this.add(doc);
  }

  remove(id: string): boolean {
    if (!this.docsById.has(id)) return false;
    const perField = this.fieldStatsByDoc.get(id);
    if (perField) {
      for (const [field, stats] of perField) {
        this.removeFieldPostings(id, field, stats);
        this.fieldTotalLengths.set(field, Math.max(0, (this.fieldTotalLengths.get(field) ?? 0) - stats.length));
      }
      this.fieldStatsByDoc.delete(id);
    }
    this.docsById.delete(id);
    return true;
  }

  update(id: string, patch: Partial<Doc>): boolean {
    const current = this.docsById.get(id);
    if (!current) return false;
    let next = current;
    const changedFields: string[] = [];
    for (const field of this.fieldNames) {
      if (!Object.prototype.hasOwnProperty.call(patch, field)) continue;
      const newValue = getProperty(patch, field);
      if (Object.is(getProperty(current, field), newValue)) continue;
      changedFields.push(field);
      next = setProperty(next, field, newValue);
    }
    for (const key of Object.keys(patch as Record<string, unknown>)) {
      if (key !== this.idField && !this.fieldNames.includes(key)) next = setProperty(next, key, getProperty(patch, key));
    }
    if (changedFields.length === 0) {
      this.docsById.set(id, next);
      return true;
    }
    const perField = this.fieldStatsByDoc.get(id) ?? new Map<string, FieldStats>();
    for (const field of changedFields) {
      const oldStats = perField.get(field);
      if (oldStats) {
        this.removeFieldPostings(id, field, oldStats);
        this.fieldTotalLengths.set(field, Math.max(0, (this.fieldTotalLengths.get(field) ?? 0) - oldStats.length));
      }
      const newStats = this.buildFieldStats(valueToText(getProperty(next, field)));
      perField.set(field, newStats);
      this.fieldTotalLengths.set(field, (this.fieldTotalLengths.get(field) ?? 0) + newStats.length);
      this.addFieldPostings(id, field, newStats);
    }
    this.fieldStatsByDoc.set(id, perField);
    this.docsById.set(id, next);
    return true;
  }

  search(query: string | Query, options: SearchOptions<Doc> = {}): SearchResult<Doc>[] {
    const trimmed = typeof query === 'string' ? query.trim() : query;
    if (typeof trimmed === 'string' && trimmed.length === 0) return [];
    const parsed = typeof query === 'string' ? parseQuery(query) : query;
    if (!parsed) return [];
    const hits = this.evaluate(parsed, options.boostFields ?? {});
    const rows: SearchResult<Doc>[] = [];
    for (const [id, hit] of hits) {
      const doc = this.docsById.get(id);
      if (!doc) continue;
      if (options.filter && !options.filter(doc)) continue;
      const matched = [...hit.matched]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([field, terms]) => ({ field, terms: [...terms].sort() }));
      const base: SearchResult<Doc> = { id, doc, score: hit.score, matched };
      if (options.snippet) {
        const snippet = this.makeSnippet(doc, matched, options.snippet.field, options.snippet.length);
        if (snippet !== undefined) rows.push({ ...base, snippet });
        else rows.push(base);
      } else {
        rows.push(base);
      }
    }
    rows.sort((a, b) => (b.score === a.score ? a.id.localeCompare(b.id) : b.score - a.score));
    const offset = Math.max(0, options.offset ?? 0);
    const limit = Math.max(0, options.limit ?? 10);
    return rows.slice(offset, offset + limit);
  }

  *docs(): IterableIterator<{ id: string; doc: Doc }> {
    const ids = [...this.docsById.keys()].sort();
    for (const id of ids) {
      const doc = this.docsById.get(id);
      if (doc) yield { id, doc };
    }
  }

  *terms(): IterableIterator<string> {
    for (const term of [...this.postings.keys()].sort()) yield term;
  }

  docFrequency(term: string): number {
    const normalized = this.normalizeText(term);
    if (normalized.length === 0) return 0;
    return this.docFrequencyNormalized(normalized[0] ?? '');
  }

  toJSON(): SearchIndexSnapshot<Doc> {
    return {
      version: 1,
      options: {
        fields: { ...this.fields },
        idField: this.idField,
        k1: this.k1,
        b: this.b,
        stopwords: this.stopwordsEqualEnglish() ? 'english' : this.stopwords.size === 0 ? 'none' : [...this.stopwords].sort()
      },
      docs: [...this.docsById.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, doc]) => doc)
    };
  }

  static fromJSON<Doc extends object>(snapshot: SearchIndexSnapshot<Doc>, options: Partial<SearchIndexOptions<Doc>> = {}): SearchIndex<Doc> {
    if (snapshot.version !== 1) throw new Error(`Unsupported snapshot version ${snapshot.version}`);
    const init: SearchIndexOptions<Doc> = {
      fields: options.fields ?? snapshot.options.fields,
      stopwords: options.stopwords ?? (Array.isArray(snapshot.options.stopwords) ? new Set(snapshot.options.stopwords) : snapshot.options.stopwords),
      idField: options.idField ?? (snapshot.options.idField as Extract<keyof Doc, string>),
      k1: options.k1 ?? snapshot.options.k1,
      b: options.b ?? snapshot.options.b
    };
    if (options.tokenizer !== undefined) init.tokenizer = options.tokenizer;
    if (options.stemmer !== undefined) init.stemmer = options.stemmer;
    const index = new SearchIndex<Doc>(init);
    index.addAll(snapshot.docs);
    return index;
  }

  private buildFieldStats(text: string): FieldStats {
    const tokens = this.normalizeText(text);
    const termFreqs = new Map<string, number>();
    const positions = new Map<string, number[]>();
    tokens.forEach((token, pos) => {
      termFreqs.set(token, (termFreqs.get(token) ?? 0) + 1);
      const arr = positions.get(token);
      if (arr) arr.push(pos);
      else positions.set(token, [pos]);
    });
    return { length: tokens.length, termFreqs, positions };
  }

  private normalizeText(text: string): string[] {
    const normalized = text.normalize('NFC');
    const rawTokens = this.tokenizer(normalized);
    const out: string[] = [];
    for (const token of rawTokens) {
      const lower = token.normalize('NFC').toLocaleLowerCase();
      if (lower.length === 0 || this.stopwords.has(lower)) continue;
      const stemmed = this.stemmer(lower);
      if (stemmed.length > 0 && !this.stopwords.has(stemmed)) out.push(stemmed);
    }
    return out;
  }

  private addFieldPostings(id: string, field: string, stats: FieldStats): void {
    for (const [term, tf] of stats.termFreqs) {
      let byField = this.postings.get(term);
      if (!byField) {
        byField = new Map<string, Map<string, Posting>>();
        this.postings.set(term, byField);
      }
      let byDoc = byField.get(field);
      if (!byDoc) {
        byDoc = new Map<string, Posting>();
        byField.set(field, byDoc);
      }
      byDoc.set(id, { tf, positions: [...(stats.positions.get(term) ?? [])] });
    }
  }

  private removeFieldPostings(id: string, field: string, stats: FieldStats): void {
    for (const term of stats.termFreqs.keys()) {
      const byField = this.postings.get(term);
      if (!byField) continue;
      const byDoc = byField.get(field);
      if (!byDoc) continue;
      byDoc.delete(id);
      if (byDoc.size === 0) byField.delete(field);
      if (byField.size === 0) this.postings.delete(term);
    }
  }

  private evaluate(query: Query, boosts: Record<string, number>): Map<string, EvalHit> {
    if ('term' in query) return this.evalTerm(query.term, query.field, boosts);
    if ('phrase' in query) return this.evalPhrase(query.phrase, query.field, query.slop ?? 0, boosts);
    if ('prefix' in query) return this.evalPrefix(query.prefix, query.field, boosts);
    if ('fuzzy' in query) return this.evalFuzzy(query.fuzzy, query.field, query.maxEdits ?? 2, boosts);
    if ('and' in query) return this.evalAnd(query.and, boosts);
    if ('or' in query) return this.evalOr(query.or, boosts);
    return this.evalNot(query.not, boosts);
  }

  private evalTerm(text: string, field: string | undefined, boosts: Record<string, number>): Map<string, EvalHit> {
    const terms = this.normalizeText(text);
    const out = new Map<string, EvalHit>();
    for (const term of terms) this.accumulateTerm(out, term, field, boosts, 1);
    return out;
  }

  private evalPrefix(prefix: string, field: string | undefined, boosts: Record<string, number>): Map<string, EvalHit> {
    const normalized = this.normalizeText(prefix)[0];
    const out = new Map<string, EvalHit>();
    if (!normalized) return out;
    for (const term of this.postings.keys()) {
      if (term.startsWith(normalized)) this.accumulateTerm(out, term, field, boosts, 0.9);
    }
    return out;
  }

  private evalFuzzy(text: string, field: string | undefined, maxEdits: 1 | 2, boosts: Record<string, number>): Map<string, EvalHit> {
    const normalized = this.normalizeText(text)[0];
    const out = new Map<string, EvalHit>();
    if (!normalized) return out;
    for (const term of this.postings.keys()) {
      const distance = levenshtein(normalized, term, maxEdits);
      if (distance <= maxEdits) this.accumulateTerm(out, term, field, boosts, 0.75 / (1 + distance));
    }
    return out;
  }

  private evalPhrase(text: string, field: string | undefined, slop: number, boosts: Record<string, number>): Map<string, EvalHit> {
    const terms = this.normalizeText(text);
    const out = new Map<string, EvalHit>();
    if (terms.length === 0) return out;
    if (terms.length === 1) return this.evalTerm(terms[0] ?? '', field, boosts);
    const candidateFields = field ? (this.fieldNames.includes(field) ? [field] : []) : this.fieldNames;
    for (const fieldName of candidateFields) {
      let candidateIds: Set<string> | undefined;
      for (const term of terms) {
        const byDoc = this.postings.get(term)?.get(fieldName);
        if (!byDoc) {
          candidateIds = new Set<string>();
          break;
        }
        const ids = new Set(byDoc.keys());
        if (candidateIds === undefined || ids.size < candidateIds.size) {
          const previous = candidateIds;
          candidateIds = ids;
          if (previous) {
            for (const id of [...candidateIds]) if (!previous.has(id)) candidateIds.delete(id);
          }
        } else {
          for (const id of [...candidateIds]) if (!ids.has(id)) candidateIds.delete(id);
        }
        if (candidateIds.size === 0) break;
      }
      if (!candidateIds || candidateIds.size === 0) continue;
      for (const id of candidateIds) {
        const stats = this.fieldStatsByDoc.get(id)?.get(fieldName);
        if (!stats) continue;
        const positionLists: number[][] = [];
        let allPresent = true;
        for (const term of terms) {
          const positions = stats.positions.get(term);
          if (!positions || positions.length === 0) {
            allPresent = false;
            break;
          }
          positionLists.push(positions);
        }
        if (!allPresent) continue;
        const bestSlop = phraseSlop(positionLists);
        if (bestSlop === undefined || bestSlop > slop) continue;
        let hit = out.get(id);
        if (!hit) {
          hit = { score: 0, matched: new Map<string, Set<string>>() };
          out.set(id, hit);
        }
        const multiplier = 2 + 1 / (1 + bestSlop);
        for (const term of terms) {
          hit.score += this.bm25(term, fieldName, id, boosts) * multiplier;
          addMatch(hit, fieldName, term);
        }
      }
    }
    return out;
  }

  private evalAnd(children: Query[], boosts: Record<string, number>): Map<string, EvalHit> {
    if (children.length === 0) return new Map<string, EvalHit>();
    let current: Map<string, EvalHit> | undefined;
    for (const child of children) {
      const next = this.evaluate(child, boosts);
      if (current === undefined) {
        current = next;
        continue;
      }
      const merged = new Map<string, EvalHit>();
      for (const [id, hit] of current) {
        const other = next.get(id);
        if (!other) continue;
        const matched = cloneMapOfSets(hit.matched);
        mergeMatched(matched, other.matched);
        merged.set(id, { score: hit.score + other.score, matched });
      }
      current = merged;
      if (current.size === 0) break;
    }
    return current ?? new Map<string, EvalHit>();
  }

  private evalOr(children: Query[], boosts: Record<string, number>): Map<string, EvalHit> {
    const out = new Map<string, EvalHit>();
    for (const child of children) {
      const hits = this.evaluate(child, boosts);
      for (const [id, hit] of hits) {
        const existing = out.get(id);
        if (existing) {
          existing.score += hit.score;
          mergeMatched(existing.matched, hit.matched);
        } else {
          out.set(id, { score: hit.score, matched: cloneMapOfSets(hit.matched) });
        }
      }
    }
    return out;
  }

  private evalNot(child: Query, boosts: Record<string, number>): Map<string, EvalHit> {
    const excluded = this.evaluate(child, boosts);
    const out = new Map<string, EvalHit>();
    for (const id of this.docsById.keys()) {
      if (!excluded.has(id)) out.set(id, { score: 0, matched: new Map<string, Set<string>>() });
    }
    return out;
  }

  private accumulateTerm(out: Map<string, EvalHit>, term: string, field: string | undefined, boosts: Record<string, number>, multiplier: number): void {
    const byField = this.postings.get(term);
    if (!byField) return;
    const fields = field ? (this.fieldNames.includes(field) ? [field] : []) : this.fieldNames;
    for (const fieldName of fields) {
      const byDoc = byField.get(fieldName);
      if (!byDoc) continue;
      for (const id of byDoc.keys()) {
        let hit = out.get(id);
        if (!hit) {
          hit = { score: 0, matched: new Map<string, Set<string>>() };
          out.set(id, hit);
        }
        hit.score += this.bm25(term, fieldName, id, boosts) * multiplier;
        addMatch(hit, fieldName, term);
      }
    }
  }

  private bm25(term: string, field: string, id: string, boosts: Record<string, number>): number {
    const byDoc = this.postings.get(term)?.get(field);
    const posting = byDoc?.get(id);
    if (!posting) return 0;
    const fieldStats = this.fieldStatsByDoc.get(id)?.get(field);
    const dl = fieldStats?.length ?? 0;
    const avgdl = this.averageFieldLength(field);
    const df = this.docFrequencyNormalized(term);
    if (df === 0) return 0;
    const idf = Math.log(1 + (this.size - df + 0.5) / (df + 0.5));
    const denom = posting.tf + this.k1 * (1 - this.b + this.b * (avgdl === 0 ? 0 : dl / avgdl));
    const fieldBoost = boosts[field] ?? this.fields[field]?.boost ?? 1;
    return idf * ((posting.tf * (this.k1 + 1)) / denom) * fieldBoost;
  }

  private averageFieldLength(field: string): number {
    if (this.size === 0) return 0;
    return (this.fieldTotalLengths.get(field) ?? 0) / this.size;
  }

  private docFrequencyNormalized(term: string): number {
    const byField = this.postings.get(term);
    if (!byField) return 0;
    const ids = new Set<string>();
    for (const byDoc of byField.values()) for (const id of byDoc.keys()) ids.add(id);
    return ids.size;
  }

  private makeSnippet(doc: Doc, matched: { field: string; terms: string[] }[], field: string, length: number): string | undefined {
    const text = valueToText(getProperty(doc, field));
    if (text.length === 0) return undefined;
    const targetTerms = new Set(matched.filter((m) => m.field === field).flatMap((m) => m.terms));
    const safeLength = Math.max(1, length);
    const ranges: { start: number; end: number }[] = [];
    for (const match of text.normalize('NFC').matchAll(WORD_RE)) {
      const word = match[0];
      const start = match.index;
      if (start === undefined) continue;
      const normalized = this.normalizeText(word)[0];
      if (normalized && targetTerms.has(normalized)) ranges.push({ start, end: start + word.length });
    }
    const first = ranges[0];
    const center = first ? Math.floor((first.start + first.end) / 2) : Math.min(text.length, Math.floor(safeLength / 2));
    const start = Math.max(0, Math.min(text.length, center - Math.floor(safeLength / 2)));
    const end = Math.min(text.length, start + safeLength);
    let snippet = text.slice(start, end);
    const localRanges = ranges
      .map((r) => ({ start: r.start - start, end: r.end - start }))
      .filter((r) => r.end > 0 && r.start < snippet.length)
      .map((r) => ({ start: Math.max(0, r.start), end: Math.min(snippet.length, r.end) }))
      .sort((a, b) => b.start - a.start);
    for (const r of localRanges) snippet = `${snippet.slice(0, r.start)}<mark>${snippet.slice(r.start, r.end)}</mark>${snippet.slice(r.end)}`;
    if (start > 0) snippet = `…${snippet}`;
    if (end < text.length) snippet = `${snippet}…`;
    return snippet;
  }

  private stopwordsEqualEnglish(): boolean {
    if (this.stopwords.size !== ENGLISH_STOPWORDS.size) return false;
    for (const word of ENGLISH_STOPWORDS) if (!this.stopwords.has(word)) return false;
    return true;
  }
}

function lex(input: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  while (i < input.length) {
    const ch = input[i];
    if (!ch || /\s/u.test(ch)) {
      i += 1;
      continue;
    }
    if (ch === '(') {
      tokens.push({ kind: 'lparen' });
      i += 1;
      continue;
    }
    if (ch === ')') {
      tokens.push({ kind: 'rparen' });
      i += 1;
      continue;
    }
    if (ch === '"') {
      let j = i + 1;
      let value = '';
      while (j < input.length && input[j] !== '"') {
        value += input[j] ?? '';
        j += 1;
      }
      tokens.push({ kind: 'phrase', value });
      i = j < input.length ? j + 1 : j;
      continue;
    }
    let j = i;
    let value = '';
    while (j < input.length) {
      const c = input[j];
      if (!c || /\s/u.test(c) || c === '(' || c === ')') break;
      if (c === '"') break;
      value += c;
      j += 1;
    }
    const upper = value.toLocaleUpperCase();
    if (upper === 'AND' || upper === 'OR' || upper === 'NOT') tokens.push({ kind: 'op', value: upper });
    else tokens.push({ kind: 'word', value });
    i = j;
  }
  return tokens;
}

function parseQuery(input: string): Query | undefined {
  const parser = new Parser(lex(input));
  return parser.parse();
}

class Parser {
  private pos = 0;
  constructor(private readonly tokens: Token[]) {}

  parse(): Query | undefined {
    const query = this.parseOr();
    return query;
  }

  private parseOr(): Query | undefined {
    const children: Query[] = [];
    const first = this.parseAnd();
    if (first) children.push(first);
    while (!this.done()) {
      if (this.matchOp('OR')) {
        const next = this.parseAnd();
        if (next) children.push(next);
        continue;
      }
      if (this.startsAtomButNotNot()) {
        const next = this.parseAnd();
        if (next) children.push(next);
        continue;
      }
      break;
    }
    if (children.length === 0) return undefined;
    return children.length === 1 ? children[0] : { or: children };
  }

  private parseAnd(): Query | undefined {
    const children: Query[] = [];
    const first = this.parseUnary();
    if (first) children.push(first);
    while (!this.done()) {
      if (this.matchOp('AND')) {
        const next = this.parseUnary();
        if (next) children.push(next);
        continue;
      }
      if (this.peekOp('NOT')) {
        const next = this.parseUnary();
        if (next) children.push(next);
        continue;
      }
      break;
    }
    if (children.length === 0) return undefined;
    return children.length === 1 ? children[0] : { and: children };
  }

  private parseUnary(): Query | undefined {
    if (this.matchOp('NOT')) {
      const child = this.parseUnary();
      return child ? { not: child } : undefined;
    }
    return this.parsePrimary();
  }

  private parsePrimary(): Query | undefined {
    const token = this.peek();
    if (!token) return undefined;
    if (token.kind === 'lparen') {
      this.pos += 1;
      const child = this.parseOr();
      if (this.peek()?.kind === 'rparen') this.pos += 1;
      return child;
    }
    if (token.kind === 'word' || token.kind === 'phrase') {
      this.pos += 1;
      if (token.kind === 'word' && token.value.endsWith(':')) {
        const field = token.value.slice(0, -1);
        const next = this.peek();
        if (next?.kind === 'word' || next?.kind === 'phrase') {
          this.pos += 1;
          return next.kind === 'phrase' ? { phrase: next.value, field } : { term: next.value, field };
        }
        return { term: token.value };
      }
      if (token.kind === 'word') {
        const split = token.value.indexOf(':');
        if (split > 0 && split < token.value.length - 1) {
          return { term: token.value.slice(split + 1), field: token.value.slice(0, split) };
        }
        return { term: token.value };
      }
      return { phrase: token.value };
    }
    return undefined;
  }

  private startsAtomButNotNot(): boolean {
    const token = this.peek();
    if (!token) return false;
    if (token.kind === 'op') return false;
    return token.kind === 'word' || token.kind === 'phrase' || token.kind === 'lparen';
  }

  private matchOp(value: 'AND' | 'OR' | 'NOT'): boolean {
    if (this.peekOp(value)) {
      this.pos += 1;
      return true;
    }
    return false;
  }

  private peekOp(value: 'AND' | 'OR' | 'NOT'): boolean {
    const token = this.peek();
    return token?.kind === 'op' && token.value === value;
  }

  private peek(): Token | undefined {
    return this.tokens[this.pos];
  }

  private done(): boolean {
    return this.pos >= this.tokens.length || this.peek()?.kind === 'rparen';
  }
}

function phraseSlop(positionLists: number[][]): number | undefined {
  const first = positionLists[0];
  if (!first) return undefined;
  let best: number | undefined;
  for (const start of first) {
    let prev = start;
    let total = 0;
    let ok = true;
    for (let i = 1; i < positionLists.length; i += 1) {
      const positions = positionLists[i];
      if (!positions) {
        ok = false;
        break;
      }
      const next = positions.find((pos) => pos > prev);
      if (next === undefined) {
        ok = false;
        break;
      }
      total += next - prev - 1;
      prev = next;
    }
    if (ok) best = best === undefined ? total : Math.min(best, total);
  }
  return best;
}

function levenshtein(a: string, b: string, max: number): number {
  const aa = [...a];
  const bb = [...b];
  if (Math.abs(aa.length - bb.length) > max) return max + 1;
  let prev = Array.from({ length: bb.length + 1 }, (_unused, i) => i);
  for (let i = 1; i <= aa.length; i += 1) {
    const current = [i];
    let rowMin = current[0] ?? 0;
    for (let j = 1; j <= bb.length; j += 1) {
      const cost = aa[i - 1] === bb[j - 1] ? 0 : 1;
      const del = (prev[j] ?? 0) + 1;
      const ins = (current[j - 1] ?? 0) + 1;
      const sub = (prev[j - 1] ?? 0) + cost;
      const val = Math.min(del, ins, sub);
      current[j] = val;
      rowMin = Math.min(rowMin, val);
    }
    if (rowMin > max) return max + 1;
    prev = current;
  }
  return prev[bb.length] ?? max + 1;
}

export const englishStopwords = new Set(ENGLISH_STOPWORDS);

export function parseSearchQuery(query: string): Query | undefined {
  return parseQuery(query);
}

export function isStructuredQuery(value: unknown): value is Query {
  return isQuery(value);
}
