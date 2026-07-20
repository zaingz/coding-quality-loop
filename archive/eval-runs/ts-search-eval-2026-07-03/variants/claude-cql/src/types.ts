/**
 * Public types for the @eval/minisearch library.
 */

/** Configuration for a single indexed field. */
export interface FieldConfig {
  /** Multiplier applied to this field's contribution to the score. Default 1. */
  boost?: number;
}

/** Stopword configuration: a custom set, the built-in English list, or none. */
export type StopwordsOption = Set<string> | "english" | "none";

/** Options accepted by the SearchIndex constructor. */
export interface IndexOptions<Doc> {
  /** Declared searchable fields and their boosts. */
  fields: Record<string, FieldConfig>;
  /** Tokenizer function. Default: unicode-aware word split, lowercased. */
  tokenizer?: (text: string) => string[];
  /** Stopwords to exclude from indexing/query terms. Default: 'english'. */
  stopwords?: StopwordsOption;
  /** Stemmer applied to each token after tokenizing. Default: identity. */
  stemmer?: (token: string) => string;
  /** Field of Doc used as the document id. Default: 'id'. */
  idField?: keyof Doc;
  /** BM25 k1 parameter. Default 1.2. */
  k1?: number;
  /** BM25 b parameter. Default 0.75. */
  b?: number;
}

/** A leaf term query. */
export interface TermQuery {
  term: string;
  field?: string;
}

/** A phrase query; slop is the maximum allowed gap between consecutive terms (0 = exact adjacency). */
export interface PhraseQuery {
  phrase: string;
  field?: string;
  slop?: number;
}

/** A prefix query: matches any indexed token starting with `prefix`. */
export interface PrefixQuery {
  prefix: string;
  field?: string;
}

/** A fuzzy query: matches indexed tokens within Levenshtein distance maxEdits. */
export interface FuzzyQuery {
  fuzzy: string;
  field?: string;
  maxEdits?: 1 | 2;
}

/** Logical AND of sub-queries. */
export interface AndQuery {
  and: Query[];
}

/** Logical OR of sub-queries. */
export interface OrQuery {
  or: Query[];
}

/** Logical negation of a sub-query. */
export interface NotQuery {
  not: Query;
}

/** A structured query: exactly one of the following shapes. */
export type Query =
  | TermQuery
  | PhraseQuery
  | PrefixQuery
  | FuzzyQuery
  | AndQuery
  | OrQuery
  | NotQuery;

/** Snippet request options. */
export interface SnippetOptions {
  field: string;
  length: number;
}

/** Options accepted by SearchIndex#search. */
export interface SearchOptions<Doc> {
  limit?: number;
  offset?: number;
  filter?: (doc: Doc) => boolean;
  boostFields?: Record<string, number>;
  snippet?: SnippetOptions;
}

/** A single match description within a result. */
export interface MatchedField {
  field: string;
  terms: string[];
}

/** A single search result. */
export interface SearchResult<Doc> {
  id: string;
  doc: Doc;
  score: number;
  matched: MatchedField[];
  snippet?: string;
}

/** A (docId, doc) pair as returned by SearchIndex#docs(). */
export interface DocEntry<Doc> {
  id: string;
  doc: Doc;
}

/** Plain-JSON serializable snapshot of an index's internal state. */
export interface IndexSnapshot {
  version: 1;
  idField: string;
  fields: Record<string, { boost: number }>;
  k1: number;
  b: number;
  /** Raw stored docs, keyed by id, as plain JSON values. */
  docs: Record<string, unknown>;
  /** Order of insertion of currently-live doc ids (for deterministic iteration). */
  docOrder: string[];
  /** Per-field per-doc token length (for BM25 avg field length). */
  fieldLengths: Record<string, Record<string, number>>;
  /** Per-field raw text used for snippet extraction. */
  rawFieldText: Record<string, Record<string, string>>;
  /** Inverted index: term -> field -> docId -> positions[]. */
  postings: Record<string, Record<string, Record<string, number[]>>>;
}
