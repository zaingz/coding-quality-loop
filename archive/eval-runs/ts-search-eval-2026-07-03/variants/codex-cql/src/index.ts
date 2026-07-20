export type FieldConfig = { boost?: number };
export type FieldConfigMap = Record<string, FieldConfig>;

export type TermQuery = { term: string; field?: string };
export type PhraseQuery = { phrase: string; field?: string; slop?: number };
export type PrefixQuery = { prefix: string; field?: string };
export type FuzzyQuery = { fuzzy: string; field?: string; maxEdits?: 1 | 2 };
export type AndQuery<Doc extends SearchDocument = SearchDocument> = { and: Query<Doc>[] };
export type OrQuery<Doc extends SearchDocument = SearchDocument> = { or: Query<Doc>[] };
export type NotQuery<Doc extends SearchDocument = SearchDocument> = { not: Query<Doc> };
export type Query<Doc extends SearchDocument = SearchDocument> =
  | TermQuery
  | PhraseQuery
  | PrefixQuery
  | FuzzyQuery
  | AndQuery<Doc>
  | OrQuery<Doc>
  | NotQuery<Doc>;

export type SearchOptions<Doc extends SearchDocument> = {
  limit?: number;
  offset?: number;
  filter?: (doc: Doc) => boolean;
  boostFields?: Record<string, number>;
  snippet?: { field: string; length: number };
};

export type SearchResult<Doc extends SearchDocument> = {
  id: string;
  doc: Doc;
  score: number;
  matched: { field: string; terms: string[] }[];
  snippet?: string;
};

export type SearchIndexOptions<Doc extends SearchDocument> = {
  fields: FieldConfigMap;
  tokenizer?: (text: string) => string[];
  stopwords?: Set<string> | "english" | "none";
  stemmer?: (token: string) => string;
  idField?: keyof Doc;
  k1?: number;
  b?: number;
};

export type SearchSnapshot<Doc extends SearchDocument> = {
  version: 1;
  fields: FieldConfigMap;
  idField: string;
  k1: number;
  b: number;
  docs: Doc[];
};

export type SearchDocument = Record<string, unknown>;

type Posting = { tf: number; positions: number[] };
type FieldPostings = Map<string, Posting>;
type TermPostings = Map<string, FieldPostings>;
type InvertedIndex = Map<string, TermPostings>;
type FieldTokenMap = Map<string, string[]>;
type MatchMap = Map<string, Map<string, Set<string>>>;
type EvalState = { scores: Map<string, number>; matches: MatchMap };
type LexToken =
  | { type: "word"; value: string }
  | { type: "phrase"; value: string }
  | { type: "op"; value: "AND" | "OR" | "NOT" }
  | { type: "lparen" }
  | { type: "rparen" };

const DEFAULT_STOPWORDS = new Set([
  "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "if", "in", "into", "is", "it",
  "no", "not", "of", "on", "or", "such", "that", "the", "their", "then", "there", "these", "they", "this",
  "to", "was", "will", "with"
]);

const WORD_RE = /[\p{L}\p{N}\p{M}]+/gu;

export function defaultTokenizer(text: string): string[] {
  const normalized = text.normalize("NFC").toLocaleLowerCase();
  return normalized.match(WORD_RE) ?? [];
}

export class SearchIndex<Doc extends SearchDocument> {
  private readonly fieldConfigs: FieldConfigMap;
  private readonly fieldNames: string[];
  private readonly tokenizer: (text: string) => string[];
  private readonly stemmer: (token: string) => string;
  private readonly stopwords: Set<string>;
  private readonly idField: keyof Doc;
  private readonly k1: number;
  private readonly b: number;
  private readonly documents = new Map<string, Doc>();
  private readonly inverted: InvertedIndex = new Map();
  private readonly docFieldTokens = new Map<string, FieldTokenMap>();
  private readonly fieldLengths = new Map<string, Map<string, number>>();
  private readonly fieldTotalLengths = new Map<string, number>();

  constructor(options: SearchIndexOptions<Doc>) {
    this.fieldConfigs = { ...options.fields };
    this.fieldNames = Object.keys(options.fields).sort();
    this.tokenizer = options.tokenizer ?? defaultTokenizer;
    this.stemmer = options.stemmer ?? ((token: string) => token);
    this.stopwords = resolveStopwords(options.stopwords ?? "english");
    this.idField = options.idField ?? ("id" as keyof Doc);
    this.k1 = options.k1 ?? 1.2;
    this.b = options.b ?? 0.75;
    for (const field of this.fieldNames) {
      this.fieldTotalLengths.set(field, 0);
    }
  }

  get size(): number {
    return this.documents.size;
  }

  add(doc: Doc): void {
    const id = this.readId(doc);
    if (this.documents.has(id)) {
      this.remove(id);
    }
    this.documents.set(id, doc);
    const tokensByField = new Map<string, string[]>();
    for (const field of this.fieldNames) {
      const tokens = this.tokensForField(doc, field);
      tokensByField.set(field, tokens);
      this.indexField(id, field, tokens);
    }
    this.docFieldTokens.set(id, tokensByField);
  }

  addAll(docs: Doc[]): void {
    for (const doc of docs) this.add(doc);
  }

  remove(id: string): boolean {
    const tokensByField = this.docFieldTokens.get(id);
    if (!tokensByField || !this.documents.has(id)) return false;
    for (const [field, tokens] of tokensByField) {
      this.removeField(id, field, tokens);
    }
    this.docFieldTokens.delete(id);
    this.fieldLengths.delete(id);
    this.documents.delete(id);
    return true;
  }

  update(id: string, patch: Partial<Doc>): boolean {
    const current = this.documents.get(id);
    const tokensByField = this.docFieldTokens.get(id);
    if (!current || !tokensByField) return false;
    const changedFields = this.fieldNames.filter((field) => Object.prototype.hasOwnProperty.call(patch, field));
    const next: Doc = { ...current, ...patch };
    this.documents.set(id, next);
    for (const field of changedFields) {
      const oldTokens = tokensByField.get(field) ?? [];
      this.removeField(id, field, oldTokens);
      const newTokens = this.tokensForField(next, field);
      tokensByField.set(field, newTokens);
      this.indexField(id, field, newTokens);
    }
    return true;
  }

  has(id: string): boolean {
    return this.documents.has(id);
  }

  *docs(): Iterable<{ id: string; doc: Doc }> {
    for (const [id, doc] of this.documents) yield { id, doc };
  }

  *terms(): Iterable<string> {
    const sorted = [...this.inverted.keys()].sort();
    for (const term of sorted) yield term;
  }

  docFrequency(term: string): number {
    const normalizedTerms = this.normalizeText(term);
    const unique = new Set<string>();
    for (const normalized of normalizedTerms) {
      const postings = this.inverted.get(normalized);
      if (!postings) continue;
      for (const fieldPostings of postings.values()) {
        for (const id of fieldPostings.keys()) unique.add(id);
      }
    }
    return unique.size;
  }

  search(query: string | Query<Doc>, options: SearchOptions<Doc> = {}): SearchResult<Doc>[] {
    const parsed = typeof query === "string" ? parseQueryString<Doc>(query) : query;
    if (!parsed) return [];
    const evaluated = this.evaluate(parsed, options);
    const rows: SearchResult<Doc>[] = [];
    for (const [id, score] of evaluated.scores) {
      const doc = this.documents.get(id);
      if (!doc) continue;
      if (options.filter && !options.filter(doc)) continue;
      const matched = this.formatMatches(evaluated.matches.get(id));
      const result: SearchResult<Doc> = { id, doc, score, matched };
      if (options.snippet) {
        result.snippet = this.makeSnippet(doc, options.snippet, matched);
      }
      rows.push(result);
    }
    rows.sort((left, right) => right.score - left.score || left.id.localeCompare(right.id));
    const offset = Math.max(0, options.offset ?? 0);
    const limit = Math.max(0, options.limit ?? 10);
    return rows.slice(offset, offset + limit);
  }

  toJSON(): SearchSnapshot<Doc> {
    return {
      version: 1,
      fields: { ...this.fieldConfigs },
      idField: String(this.idField),
      k1: this.k1,
      b: this.b,
      docs: [...this.documents.values()]
    };
  }

  static fromJSON<Doc extends SearchDocument>(
    snapshot: SearchSnapshot<Doc>,
    options: Omit<SearchIndexOptions<Doc>, "fields" | "idField" | "k1" | "b"> & Partial<Pick<SearchIndexOptions<Doc>, "fields" | "idField" | "k1" | "b">> = {}
  ): SearchIndex<Doc> {
    const index = new SearchIndex<Doc>({
      ...options,
      fields: options.fields ?? snapshot.fields,
      idField: options.idField ?? (snapshot.idField as keyof Doc),
      k1: options.k1 ?? snapshot.k1,
      b: options.b ?? snapshot.b
    });
    index.addAll(snapshot.docs);
    return index;
  }

  private readId(doc: Doc): string {
    const value = doc[this.idField];
    if (value === undefined || value === null) {
      throw new Error(`Document id field ${String(this.idField)} is missing`);
    }
    return String(value);
  }

  private tokensForField(doc: Doc, field: string): string[] {
    const value = doc[field];
    return this.normalizeText(valueToText(value));
  }

  private normalizeText(text: string): string[] {
    const tokens: string[] = [];
    for (const raw of this.tokenizer(text)) {
      const normalized = this.stemmer(raw.normalize("NFC").toLocaleLowerCase());
      if (normalized.length > 0 && !this.stopwords.has(normalized)) tokens.push(normalized);
    }
    return tokens;
  }

  private indexField(id: string, field: string, tokens: string[]): void {
    const fieldLengthByDoc = getOrCreateMap(this.fieldLengths, id);
    fieldLengthByDoc.set(field, tokens.length);
    this.fieldTotalLengths.set(field, (this.fieldTotalLengths.get(field) ?? 0) + tokens.length);
    const positionsByTerm = new Map<string, number[]>();
    tokens.forEach((term, position) => {
      const positions = positionsByTerm.get(term) ?? [];
      positions.push(position);
      positionsByTerm.set(term, positions);
    });
    for (const [term, positions] of positionsByTerm) {
      const termPostings = getOrCreateMap(this.inverted, term);
      const fieldPostings = getOrCreateMap(termPostings, field);
      fieldPostings.set(id, { tf: positions.length, positions });
    }
  }

  private removeField(id: string, field: string, tokens: string[]): void {
    const fieldLengthByDoc = this.fieldLengths.get(id);
    const oldLength = fieldLengthByDoc?.get(field) ?? tokens.length;
    if (fieldLengthByDoc) {
      fieldLengthByDoc.delete(field);
      if (fieldLengthByDoc.size === 0) this.fieldLengths.delete(id);
    }
    this.fieldTotalLengths.set(field, Math.max(0, (this.fieldTotalLengths.get(field) ?? 0) - oldLength));
    for (const term of new Set(tokens)) {
      const termPostings = this.inverted.get(term);
      const fieldPostings = termPostings?.get(field);
      fieldPostings?.delete(id);
      if (fieldPostings && fieldPostings.size === 0) termPostings?.delete(field);
      if (termPostings && termPostings.size === 0) this.inverted.delete(term);
    }
  }

  private evaluate(query: Query<Doc>, options: SearchOptions<Doc>): EvalState {
    if ("term" in query) return this.evaluateTerm(query.term, query.field, options);
    if ("phrase" in query) return this.evaluatePhrase(query.phrase, query.field, query.slop ?? 0, options);
    if ("prefix" in query) return this.evaluatePrefix(query.prefix, query.field, options);
    if ("fuzzy" in query) return this.evaluateFuzzy(query.fuzzy, query.field, query.maxEdits ?? 2, options);
    if ("and" in query) return this.evaluateAnd(query.and, options);
    if ("or" in query) return this.evaluateOr(query.or, options);
    return this.evaluateNot(query.not, options);
  }

  private evaluateTerm(termText: string, field: string | undefined, options: SearchOptions<Doc>): EvalState {
    const tokens = this.normalizeText(termText);
    if (tokens.length === 0) return emptyState();
    const states = tokens.map((token) => this.evaluateSingleTerm(token, field, options, token));
    return this.evaluateOrStates(states);
  }

  private evaluateSingleTerm(term: string, field: string | undefined, options: SearchOptions<Doc>, matchedTerm: string): EvalState {
    const state = emptyState();
    const postings = this.inverted.get(term);
    if (!postings) return state;
    for (const selectedField of this.selectedFields(field)) {
      const fieldPostings = postings.get(selectedField);
      if (!fieldPostings) continue;
      for (const [id, posting] of fieldPostings) {
        const score = this.bm25(term, selectedField, id, posting.tf, options.boostFields);
        addScore(state, id, score);
        addMatch(state, id, selectedField, matchedTerm);
      }
    }
    return state;
  }

  private evaluatePrefix(prefixText: string, field: string | undefined, options: SearchOptions<Doc>): EvalState {
    const prefixes = this.normalizeText(prefixText);
    if (prefixes.length === 0) return emptyState();
    const states: EvalState[] = [];
    for (const prefix of prefixes) {
      for (const term of this.inverted.keys()) {
        if (term.startsWith(prefix)) states.push(this.evaluateSingleTerm(term, field, options, term));
      }
    }
    return this.evaluateOrStates(states);
  }

  private evaluateFuzzy(text: string, field: string | undefined, maxEdits: 1 | 2, options: SearchOptions<Doc>): EvalState {
    const tokens = this.normalizeText(text);
    if (tokens.length === 0) return emptyState();
    const states: EvalState[] = [];
    for (const queryTerm of tokens) {
      for (const term of this.inverted.keys()) {
        if (Math.abs(term.length - queryTerm.length) > maxEdits) continue;
        if (levenshteinAtMost(queryTerm, term, maxEdits) <= maxEdits) {
          states.push(this.evaluateSingleTerm(term, field, options, term));
        }
      }
    }
    return this.evaluateOrStates(states);
  }

  private evaluatePhrase(text: string, field: string | undefined, slop: number, options: SearchOptions<Doc>): EvalState {
    const phraseTerms = this.normalizeText(text);
    if (phraseTerms.length === 0) return emptyState();
    if (phraseTerms.length === 1) return this.evaluateSingleTerm(phraseTerms[0] ?? "", field, options, phraseTerms[0] ?? "");
    const state = emptyState();
    for (const id of this.documents.keys()) {
      for (const selectedField of this.selectedFields(field)) {
        const tokens = this.docFieldTokens.get(id)?.get(selectedField) ?? [];
        const proximity = phraseProximity(tokens, phraseTerms, slop);
        if (proximity === null) continue;
        let score = 0;
        for (const term of phraseTerms) {
          const posting = this.inverted.get(term)?.get(selectedField)?.get(id);
          if (posting) score += this.bm25(term, selectedField, id, posting.tf, options.boostFields);
        }
        score *= 1 + 1 / (1 + proximity);
        addScore(state, id, score);
        for (const term of phraseTerms) addMatch(state, id, selectedField, term);
      }
    }
    return state;
  }

  private evaluateAnd(queries: Query<Doc>[], options: SearchOptions<Doc>): EvalState {
    if (queries.length === 0) return emptyState();
    let state = this.evaluate(queries[0] as Query<Doc>, options);
    for (const query of queries.slice(1)) {
      const next = this.evaluate(query, options);
      state = intersectStates(state, next);
    }
    return state;
  }

  private evaluateOr(queries: Query<Doc>[], options: SearchOptions<Doc>): EvalState {
    return this.evaluateOrStates(queries.map((query) => this.evaluate(query, options)));
  }

  private evaluateOrStates(states: EvalState[]): EvalState {
    const merged = emptyState();
    for (const state of states) mergeStateInto(merged, state);
    return merged;
  }

  private evaluateNot(query: Query<Doc>, options: SearchOptions<Doc>): EvalState {
    const excluded = this.evaluate(query, options).scores;
    const state = emptyState();
    for (const id of this.documents.keys()) {
      if (!excluded.has(id)) state.scores.set(id, 0);
    }
    return state;
  }

  private selectedFields(field: string | undefined): string[] {
    if (field !== undefined) return this.fieldConfigs[field] ? [field] : [];
    return this.fieldNames;
  }

  private bm25(term: string, field: string, id: string, tf: number, boostOverrides: Record<string, number> | undefined): number {
    const df = this.fieldDocFrequency(term, field);
    if (df === 0 || this.size === 0) return 0;
    const idf = Math.log(1 + (this.size - df + 0.5) / (df + 0.5));
    const length = this.fieldLengths.get(id)?.get(field) ?? 0;
    const avgLength = (this.fieldTotalLengths.get(field) ?? 0) / Math.max(1, this.size);
    const norm = tf + this.k1 * (1 - this.b + this.b * (length / Math.max(1, avgLength)));
    const boost = boostOverrides?.[field] ?? this.fieldConfigs[field]?.boost ?? 1;
    return idf * ((tf * (this.k1 + 1)) / norm) * boost;
  }

  private fieldDocFrequency(term: string, field: string): number {
    return this.inverted.get(term)?.get(field)?.size ?? 0;
  }

  private formatMatches(matches: Map<string, Set<string>> | undefined): { field: string; terms: string[] }[] {
    if (!matches) return [];
    return [...matches.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([field, terms]) => ({ field, terms: [...terms].sort() }));
  }

  private makeSnippet(doc: Doc, config: { field: string; length: number }, matched: { field: string; terms: string[] }[]): string {
    const text = valueToText(doc[config.field]);
    const length = Math.max(0, config.length);
    if (text.length === 0 || length === 0) return "";
    const fieldTerms = matched.find((entry) => entry.field === config.field)?.terms ?? matched.flatMap((entry) => entry.terms);
    const uniqueTerms = [...new Set(fieldTerms)].filter((term) => term.length > 0);
    const pattern = uniqueTerms.length > 0 ? new RegExp(`(${uniqueTerms.map(escapeRegex).join("|")})`, "giu") : null;
    const first = pattern ? text.search(pattern) : -1;
    const start = first >= 0 ? Math.max(0, first - Math.floor(length / 2)) : 0;
    const excerpt = text.slice(start, start + length);
    if (!pattern) return excerpt;
    return excerpt.replace(pattern, "<mark>$1</mark>");
  }
}

function resolveStopwords(input: Set<string> | "english" | "none"): Set<string> {
  if (input === "none") return new Set();
  if (input === "english") return new Set(DEFAULT_STOPWORDS);
  return new Set([...input].map((word) => word.normalize("NFC").toLocaleLowerCase()));
}

function valueToText(value: unknown): string {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.map((item) => valueToText(item)).join(" ");
  return "";
}

function getOrCreateMap<K, V>(outer: Map<K, Map<string, V>>, key: K): Map<string, V>;
function getOrCreateMap<K, V>(outer: Map<K, Map<string, V>>, key: K): Map<string, V> {
  let inner = outer.get(key);
  if (!inner) {
    inner = new Map<string, V>();
    outer.set(key, inner);
  }
  return inner;
}

function emptyState(): EvalState {
  return { scores: new Map(), matches: new Map() };
}

function addScore(state: EvalState, id: string, score: number): void {
  state.scores.set(id, (state.scores.get(id) ?? 0) + score);
}

function addMatch(state: EvalState, id: string, field: string, term: string): void {
  const fields = getOrCreateMap(state.matches, id);
  let terms = fields.get(field);
  if (!terms) {
    terms = new Set<string>();
    fields.set(field, terms);
  }
  terms.add(term);
}

function mergeStateInto(target: EvalState, source: EvalState): void {
  for (const [id, score] of source.scores) addScore(target, id, score);
  for (const [id, fields] of source.matches) {
    for (const [field, terms] of fields) {
      for (const term of terms) addMatch(target, id, field, term);
    }
  }
}

function intersectStates(left: EvalState, right: EvalState): EvalState {
  const result = emptyState();
  for (const [id, leftScore] of left.scores) {
    const rightScore = right.scores.get(id);
    if (rightScore === undefined) continue;
    result.scores.set(id, leftScore + rightScore);
    const leftMatches = left.matches.get(id);
    const rightMatches = right.matches.get(id);
    if (leftMatches) {
      for (const [field, terms] of leftMatches) for (const term of terms) addMatch(result, id, field, term);
    }
    if (rightMatches) {
      for (const [field, terms] of rightMatches) for (const term of terms) addMatch(result, id, field, term);
    }
  }
  return result;
}

function tokenizeQuery(input: string): LexToken[] {
  const tokens: LexToken[] = [];
  let i = 0;
  while (i < input.length) {
    const char = input[i];
    if (!char || /\s/u.test(char)) { i += 1; continue; }
    if (char === "(") { tokens.push({ type: "lparen" }); i += 1; continue; }
    if (char === ")") { tokens.push({ type: "rparen" }); i += 1; continue; }
    if (char === '"') {
      const end = input.indexOf('"', i + 1);
      const phraseEnd = end >= 0 ? end : input.length;
      tokens.push({ type: "phrase", value: input.slice(i + 1, phraseEnd) });
      i = end >= 0 ? end + 1 : input.length;
      continue;
    }
    let j = i;
    while (j < input.length && !/\s|\(|\)|"/u.test(input[j] ?? "")) j += 1;
    const word = input.slice(i, j);
    if (word === "AND" || word === "OR" || word === "NOT") tokens.push({ type: "op", value: word });
    else tokens.push({ type: "word", value: word });
    i = j;
  }
  return tokens;
}

function parseQueryString<Doc extends SearchDocument>(input: string): Query<Doc> | null {
  const tokens = tokenizeQuery(input);
  if (tokens.length === 0) return null;
  let position = 0;

  const peek = (): LexToken | undefined => tokens[position];
  const consume = (): LexToken | undefined => tokens[position++];
  const startsPrimary = (token: LexToken | undefined): boolean => token?.type === "word" || token?.type === "phrase" || token?.type === "lparen" || (token?.type === "op" && token.value === "NOT");

  const parseOr = (): Query<Doc> | null => {
    const parts: Query<Doc>[] = [];
    const first = parseAnd();
    if (first) parts.push(first);
    while (true) {
      const token = peek();
      if (token?.type === "op" && token.value === "OR") {
        consume();
        const next = parseAnd();
        if (next) parts.push(next);
        continue;
      }
      if (startsPrimary(token) && !(token?.type === "op" && token.value === "NOT")) {
        const next = parseAnd();
        if (next) parts.push(next);
        continue;
      }
      break;
    }
    if (parts.length === 0) return null;
    return parts.length === 1 ? parts[0] as Query<Doc> : { or: parts };
  };

  const parseAnd = (): Query<Doc> | null => {
    const parts: Query<Doc>[] = [];
    const first = parseNot();
    if (first) parts.push(first);
    while (true) {
      const token = peek();
      if (token?.type === "op" && token.value === "AND") {
        consume();
        const next = parseNot();
        if (next) parts.push(next);
        continue;
      }
      if (token?.type === "op" && token.value === "NOT") {
        const next = parseNot();
        if (next) parts.push(next);
        continue;
      }
      break;
    }
    if (parts.length === 0) return null;
    return parts.length === 1 ? parts[0] as Query<Doc> : { and: parts };
  };

  const parseNot = (): Query<Doc> | null => {
    const token = peek();
    if (token?.type === "op" && token.value === "NOT") {
      consume();
      const child = parseNot();
      return child ? { not: child } : null;
    }
    return parsePrimary();
  };

  const parsePrimary = (): Query<Doc> | null => {
    const token = consume();
    if (!token) return null;
    if (token.type === "lparen") {
      const child = parseOr();
      if (peek()?.type === "rparen") consume();
      return child;
    }
    if (token.type === "rparen") return null;
    if (token.type === "phrase") return { phrase: token.value };
    if (token.type === "op") return { term: token.value.toLocaleLowerCase() };
    const split = splitFieldPrefix(token.value);
    if (split.remainder.length > 0) return withOptionalField({ term: split.remainder }, split.field);
    const next = consume();
    if (next?.type === "phrase") return withOptionalField({ phrase: next.value }, split.field);
    if (next?.type === "word") return withOptionalField({ term: next.value }, split.field);
    if (next) position -= 1;
    return { term: token.value };
  };

  return parseOr();
}

function withOptionalField<T extends TermQuery | PhraseQuery>(query: T, field: string | undefined): T {
  if (field === undefined) return query;
  return { ...query, field };
}

function splitFieldPrefix(word: string): { field?: string; remainder: string } {
  const colon = word.indexOf(":");
  if (colon <= 0) return { remainder: word };
  const field = word.slice(0, colon);
  const remainder = word.slice(colon + 1);
  return { field, remainder };
}

function phraseProximity(tokens: string[], phraseTerms: string[], slop: number): number | null {
  let best: number | null = null;
  const starts: number[] = [];
  tokens.forEach((token, index) => { if (token === phraseTerms[0]) starts.push(index); });
  for (const start of starts) {
    let previous = start;
    let totalGap = 0;
    let matched = true;
    for (let i = 1; i < phraseTerms.length; i += 1) {
      const wanted = phraseTerms[i];
      let found = -1;
      for (let pos = previous + 1; pos < tokens.length; pos += 1) {
        if (tokens[pos] === wanted) { found = pos; break; }
      }
      if (found < 0) { matched = false; break; }
      totalGap += found - previous - 1;
      previous = found;
    }
    if (matched && totalGap <= slop) best = best === null ? totalGap : Math.min(best, totalGap);
  }
  return best;
}

function levenshteinAtMost(left: string, right: string, maxEdits: number): number {
  const a = [...left];
  const b = [...right];
  if (Math.abs(a.length - b.length) > maxEdits) return maxEdits + 1;
  let previous = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i += 1) {
    const current = [i];
    let rowMin = current[0] ?? i;
    for (let j = 1; j <= b.length; j += 1) {
      const substitution = (previous[j - 1] ?? 0) + (a[i - 1] === b[j - 1] ? 0 : 1);
      const insertion = (current[j - 1] ?? 0) + 1;
      const deletion = (previous[j] ?? 0) + 1;
      const value = Math.min(substitution, insertion, deletion);
      current[j] = value;
      rowMin = Math.min(rowMin, value);
    }
    if (rowMin > maxEdits) return maxEdits + 1;
    previous = current;
  }
  return previous[b.length] ?? maxEdits + 1;
}

function escapeRegex(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
