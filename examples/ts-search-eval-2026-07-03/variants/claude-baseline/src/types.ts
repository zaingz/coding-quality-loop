/**
 * Public type definitions for the minisearch library.
 */

/** Configuration for a single field in the schema. */
export interface FieldConfig {
  /** Multiplier applied to this field's contribution to the score. Default 1. */
  boost?: number;
}

/** Constructor options for SearchIndex. */
export interface SearchIndexOptions<Doc> {
  /** Field name -> config. Only these fields are indexed. */
  fields: Record<string, FieldConfig>;
  /** Custom tokenizer. Default: unicode-aware word split, lowercased. */
  tokenizer?: (text: string) => string[];
  /** Stopword set, or 'english' (default) or 'none'. */
  stopwords?: Set<string> | "english" | "none";
  /** Custom stemmer. Default: identity function. */
  stemmer?: (token: string) => string;
  /** Field on Doc used as the unique id. Default: 'id'. */
  idField?: keyof Doc;
  /** BM25 k1 parameter. Default 1.2. */
  k1?: number;
  /** BM25 b parameter. Default 0.75. */
  b?: number;
}

/** Structured query forms. */
export type Query =
  | { term: string; field?: string }
  | { phrase: string; field?: string; slop?: number }
  | { prefix: string; field?: string }
  | { fuzzy: string; field?: string; maxEdits?: 1 | 2 }
  | { and: Query[] }
  | { or: Query[] }
  | { not: Query };

/** Options for SearchIndex#search. */
export interface SearchOptions<Doc> {
  limit?: number;
  offset?: number;
  filter?: (doc: Doc) => boolean;
  boostFields?: Record<string, number>;
  snippet?: { field: string; length: number };
}

/** A single search result. */
export interface SearchResult<Doc> {
  id: string;
  doc: Doc;
  score: number;
  matched: { field: string; terms: string[] }[];
  snippet?: string;
}

/** Plain-JSON serializable snapshot of an index's state. */
export interface IndexSnapshot {
  version: 1;
  fields: Record<string, { boost: number }>;
  idField: string;
  k1: number;
  b: number;
  /** term -> field -> docId -> positions[] */
  postings: Record<string, Record<string, Record<string, number[]>>>;
  /** docId -> field -> token count (post-stopword/stem) */
  fieldLengths: Record<string, Record<string, number>>;
  /** field -> total token count across all live docs */
  totalFieldLength: Record<string, number>;
  /** docId -> doc (as stored, JSON-safe) */
  docs: Record<string, unknown>;
  /** insertion order of doc ids, for stability where relevant */
  docOrder: string[];
}
