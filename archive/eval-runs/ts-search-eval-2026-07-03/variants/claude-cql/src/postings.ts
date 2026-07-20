/**
 * Inverted-index postings store: term -> field -> docId -> positions[].
 *
 * Owns per-field document length tracking (for BM25) and exposes cleanup
 * that removes orphaned entries (empty docId maps, empty field maps, empty
 * term entries) so terms()/docFrequency() never report stale data after a
 * remove/update.
 *
 * Performance note: `clearField` must only touch the terms that the
 * (docId, field) pair actually used previously, not scan the whole
 * vocabulary. A reverse index (`docFieldTerms`) tracks exactly that set so
 * clearing/re-indexing a single doc/field stays O(terms in that field for
 * that doc), independent of total corpus vocabulary size.
 */
export class PostingsStore {
  /** term -> field -> docId -> sorted token positions within that field */
  private readonly index = new Map<string, Map<string, Map<string, number[]>>>();
  /** field -> docId -> token count (for BM25 field length / avg length) */
  private readonly fieldLengths = new Map<string, Map<string, number>>();
  /** field -> total token count across all live docs (for avg length) */
  private fieldTotalLength = new Map<string, number>();
  /** field -> number of docs that have a non-empty value for that field */
  private fieldDocCount = new Map<string, number>();
  /** field -> docId -> set of terms currently indexed for that (docId, field) */
  private readonly docFieldTerms = new Map<string, Map<string, Set<string>>>();

  constructor(fieldNames: readonly string[]) {
    for (const f of fieldNames) {
      this.fieldLengths.set(f, new Map());
      this.fieldTotalLength.set(f, 0);
      this.fieldDocCount.set(f, 0);
      this.docFieldTerms.set(f, new Map());
    }
  }

  /** Index the given tokens for (docId, field), replacing any prior entry for that field/doc. */
  indexField(docId: string, field: string, tokens: readonly string[]): void {
    this.clearField(docId, field);

    if (tokens.length === 0) return;

    const perTermPositions = new Map<string, number[]>();
    tokens.forEach((tok, pos) => {
      let arr = perTermPositions.get(tok);
      if (!arr) {
        arr = [];
        perTermPositions.set(tok, arr);
      }
      arr.push(pos);
    });

    for (const [term, positions] of perTermPositions) {
      let fieldMap = this.index.get(term);
      if (!fieldMap) {
        fieldMap = new Map();
        this.index.set(term, fieldMap);
      }
      let docMap = fieldMap.get(field);
      if (!docMap) {
        docMap = new Map();
        fieldMap.set(field, docMap);
      }
      docMap.set(docId, positions);
    }

    const usedTerms = this.docFieldTerms.get(field);
    if (usedTerms) {
      usedTerms.set(docId, new Set(perTermPositions.keys()));
    }

    const lengths = this.fieldLengths.get(field);
    if (lengths) {
      lengths.set(docId, tokens.length);
      this.fieldTotalLength.set(field, (this.fieldTotalLength.get(field) ?? 0) + tokens.length);
      this.fieldDocCount.set(field, (this.fieldDocCount.get(field) ?? 0) + 1);
    }
  }

  /** Remove all postings for (docId, field), cleaning up orphaned term/field entries. */
  clearField(docId: string, field: string): void {
    const lengths = this.fieldLengths.get(field);
    if (lengths && lengths.has(docId)) {
      const prevLen = lengths.get(docId) ?? 0;
      this.fieldTotalLength.set(field, (this.fieldTotalLength.get(field) ?? 0) - prevLen);
      this.fieldDocCount.set(field, Math.max(0, (this.fieldDocCount.get(field) ?? 0) - 1));
      lengths.delete(docId);
    }

    const usedTerms = this.docFieldTerms.get(field);
    const prevTerms = usedTerms?.get(docId);
    if (!prevTerms || prevTerms.size === 0) {
      usedTerms?.delete(docId);
      return;
    }

    // Only touch the specific terms this (docId, field) previously used —
    // O(terms used by this doc/field), not O(total vocabulary).
    for (const term of prevTerms) {
      const fieldMap = this.index.get(term);
      if (!fieldMap) continue;
      const docMap = fieldMap.get(field);
      if (!docMap) continue;
      docMap.delete(docId);
      if (docMap.size === 0) {
        fieldMap.delete(field);
      }
      if (fieldMap.size === 0) {
        this.index.delete(term);
      }
    }
    usedTerms?.delete(docId);
  }

  /** Remove all postings for a doc across all fields. */
  removeDoc(docId: string, fieldNames: readonly string[]): void {
    for (const field of fieldNames) {
      this.clearField(docId, field);
    }
  }

  /** Positions of `term` in `field` for `docId`, or undefined if absent. */
  getPositions(term: string, field: string, docId: string): number[] | undefined {
    return this.index.get(term)?.get(field)?.get(docId);
  }

  /** All docIds (with positions) containing `term` in `field`. */
  getDocsForTerm(term: string, field: string): ReadonlyMap<string, number[]> {
    return this.index.get(term)?.get(field) ?? new Map();
  }

  /** Number of distinct docs containing `term` in any field (document frequency). */
  docFrequency(term: string): number {
    const fieldMap = this.index.get(term);
    if (!fieldMap) return 0;
    const docs = new Set<string>();
    for (const docMap of fieldMap.values()) {
      for (const docId of docMap.keys()) docs.add(docId);
    }
    return docs.size;
  }

  /** Document frequency of `term` restricted to `field`. */
  docFrequencyInField(term: string, field: string): number {
    return this.index.get(term)?.get(field)?.size ?? 0;
  }

  /** All unique indexed terms. */
  terms(): IterableIterator<string> {
    return this.index.keys();
  }

  /** All terms that begin with `prefix` (for prefix queries). */
  termsWithPrefix(prefix: string): string[] {
    const out: string[] = [];
    for (const term of this.index.keys()) {
      if (term.startsWith(prefix)) out.push(term);
    }
    return out;
  }

  /** Token length of `field` for `docId` (0 if absent). */
  fieldLength(field: string, docId: string): number {
    return this.fieldLengths.get(field)?.get(docId) ?? 0;
  }

  /** Average token length of `field` across all live docs that have it (0 if none). */
  averageFieldLength(field: string): number {
    const count = this.fieldDocCount.get(field) ?? 0;
    if (count === 0) return 0;
    return (this.fieldTotalLength.get(field) ?? 0) / count;
  }

  /** Number of live docs with a non-empty value for `field`. */
  fieldDocumentCount(field: string): number {
    return this.fieldDocCount.get(field) ?? 0;
  }

  /**
   * Restore a single (term, field, docId) posting directly from a
   * serialized snapshot, bypassing tokenization. Used only by
   * SearchIndex.fromJSON to reconstruct exact prior state. Does not touch
   * field-length bookkeeping (see restoreFieldLength).
   */
  restorePosting(term: string, field: string, docId: string, positions: readonly number[]): void {
    let fieldMap = this.index.get(term);
    if (!fieldMap) {
      fieldMap = new Map();
      this.index.set(term, fieldMap);
    }
    let docMap = fieldMap.get(field);
    if (!docMap) {
      docMap = new Map();
      fieldMap.set(field, docMap);
    }
    docMap.set(docId, [...positions]);

    const usedTerms = this.docFieldTerms.get(field);
    if (usedTerms) {
      let set = usedTerms.get(docId);
      if (!set) {
        set = new Set();
        usedTerms.set(docId, set);
      }
      set.add(term);
    }
  }

  /**
   * Restore field-length bookkeeping for (field, docId) directly from a
   * serialized snapshot. Used only by SearchIndex.fromJSON.
   */
  restoreFieldLength(field: string, docId: string, length: number): void {
    let lengths = this.fieldLengths.get(field);
    if (!lengths) {
      lengths = new Map();
      this.fieldLengths.set(field, lengths);
    }
    if (!lengths.has(docId)) {
      this.fieldTotalLength.set(field, (this.fieldTotalLength.get(field) ?? 0) + length);
      this.fieldDocCount.set(field, (this.fieldDocCount.get(field) ?? 0) + 1);
    }
    lengths.set(docId, length);
  }
}
