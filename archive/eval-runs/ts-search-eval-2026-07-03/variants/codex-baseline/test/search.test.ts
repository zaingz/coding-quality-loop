import assert from 'node:assert/strict';
import test from 'node:test';
import { SearchIndex } from '../src/index.js';

type Doc = {
  id: string;
  title?: string;
  body?: string;
  tags?: string[];
  category?: string;
};

function makeIndex() {
  return new SearchIndex<Doc>({
    fields: { title: { boost: 3 }, body: { boost: 1 }, tags: { boost: 2 } },
    stopwords: 'none'
  });
}

test('BM25 ranking favors boosted title matches', () => {
  const index = makeIndex();
  index.addAll([
    { id: 'body', title: 'unrelated', body: 'falcon falcon' },
    { id: 'title', title: 'falcon', body: 'unrelated' }
  ]);
  const results = index.search('falcon', { limit: 10 });
  assert.equal(results[0]?.id, 'title');
  assert.ok((results[0]?.score ?? 0) > (results[1]?.score ?? 0));
});

test('phrase query requires adjacency when slop is zero', () => {
  const index = makeIndex();
  index.addAll([
    { id: 'exact', title: 'quick brown fox' },
    { id: 'gap', title: 'quick red brown fox' }
  ]);
  assert.deepEqual(index.search('"quick brown"').map((r) => r.id), ['exact']);
  assert.deepEqual(index.search({ phrase: 'quick brown', slop: 1 }).map((r) => r.id), ['exact', 'gap']);
});

test('fuzzy search finds terms within edit distance', () => {
  const index = makeIndex();
  index.add({ id: 'us', title: 'color palette' });
  const results = index.search({ fuzzy: 'colour', maxEdits: 1 });
  assert.equal(results[0]?.id, 'us');
});

test('boolean query handles AND with implicit NOT exclusion', () => {
  const index = makeIndex();
  index.addAll([
    { id: 'keep', body: 'a b' },
    { id: 'drop', body: 'a b c' },
    { id: 'missing', body: 'a c' }
  ]);
  assert.deepEqual(index.search('a AND b NOT c', { limit: 10 }).map((r) => r.id), ['keep']);
});

test('unicode tokenizer handles accents and case', () => {
  const index = makeIndex();
  index.add({ id: 'cafe', title: 'Cafe\u0301 搜索 بحث' });
  assert.equal(index.search('café')[0]?.id, 'cafe');
  assert.equal(index.search('CAFÉ')[0]?.id, 'cafe');
  assert.equal(index.search('搜索')[0]?.id, 'cafe');
  assert.equal(index.search('بحث')[0]?.id, 'cafe');
});

test('remove deletes document and orphaned postings', () => {
  const index = makeIndex();
  index.add({ id: 'x', title: 'orphanonly' });
  assert.equal(index.docFrequency('orphanonly'), 1);
  assert.equal(index.remove('x'), true);
  assert.equal(index.has('x'), false);
  assert.equal(index.docFrequency('orphanonly'), 0);
  assert.deepEqual([...index.terms()], []);
});

test('serialization roundtrip preserves search behavior', () => {
  const index = makeIndex();
  index.addAll([
    { id: '1', title: 'alpha beta', tags: ['one'] },
    { id: '2', title: 'beta gamma', tags: ['two'] }
  ]);
  const restored = SearchIndex.fromJSON<Doc>(index.toJSON());
  assert.deepEqual(restored.search('beta', { limit: 10 }).map((r) => r.id), index.search('beta', { limit: 10 }).map((r) => r.id));
  assert.equal(restored.size, 2);
});

test('snippet highlights matched text', () => {
  const index = makeIndex();
  index.add({ id: 's', body: 'the quick brown fox jumps over the lazy dog' });
  const result = index.search('brown', { snippet: { field: 'body', length: 20 } })[0];
  assert.ok(result?.snippet?.includes('<mark>brown</mark>'));
});

test('update reindexes changed field only', () => {
  const index = makeIndex();
  index.add({ id: 'u', title: 'stable title', body: 'old body' });
  assert.equal(index.update('u', { body: 'new body' }), true);
  assert.equal(index.search('old')[0]?.id, undefined);
  assert.equal(index.search('new')[0]?.id, 'u');
  assert.equal(index.search('stable')[0]?.id, 'u');
});

test('edge cases: empty queries, missing fields, prefix, filters, and docs iterator', () => {
  const index = makeIndex();
  assert.deepEqual(index.search('   '), []);
  index.add({ id: '1', title: 'prefixable term', category: 'keep' });
  index.add({ id: '2', title: 'another term', category: 'drop' });
  assert.deepEqual(index.search({ prefix: 'pref' }).map((r) => r.id), ['1']);
  assert.deepEqual(index.search('term', { limit: 10, filter: (doc) => doc.category === 'keep' }).map((r) => r.id), ['1']);
  assert.deepEqual([...index.docs()].map((entry) => entry.id), ['1', '2']);
});
