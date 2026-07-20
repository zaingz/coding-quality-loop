/**
 * BM25 scoring helpers.
 *
 * idf(term) = ln( (N - df + 0.5) / (df + 0.5) + 1 )   [+1 keeps idf non-negative]
 *
 * termScore = idf * ( tf * (k1 + 1) ) / ( tf + k1 * (1 - b + b * (fieldLen / avgFieldLen)) )
 */
export function idf(totalDocs: number, docFrequency: number): number {
  if (totalDocs === 0) return 0;
  return Math.log((totalDocs - docFrequency + 0.5) / (docFrequency + 0.5) + 1);
}

export function bm25TermScore(params: {
  termFrequency: number;
  docFrequency: number;
  totalDocs: number;
  fieldLength: number;
  avgFieldLength: number;
  k1: number;
  b: number;
}): number {
  const { termFrequency, docFrequency, totalDocs, fieldLength, avgFieldLength, k1, b } = params;
  if (termFrequency <= 0) return 0;
  const theIdf = idf(totalDocs, docFrequency);
  const denomLengthNorm = avgFieldLength > 0 ? fieldLength / avgFieldLength : 1;
  const denominator = termFrequency + k1 * (1 - b + b * denomLengthNorm);
  if (denominator === 0) return 0;
  return theIdf * ((termFrequency * (k1 + 1)) / denominator);
}
