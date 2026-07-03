# Build/test/bench results

## codex-baseline

### npm install
```
(node_modules already present)
```
### npm run build
```

> @eval/minisearch@0.1.0 build
> tsc

```
### npm test
```
  ...
# Subtest: update reindexes changed field only
ok 9 - update reindexes changed field only
  ---
  duration_ms: 0.46146
  ...
# Subtest: edge cases: empty queries, missing fields, prefix, filters, and docs iterator
ok 10 - edge cases: empty queries, missing fields, prefix, filters, and docs iterator
  ---
  duration_ms: 0.440438
  ...
1..10
# tests 10
# suites 0
# pass 10
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 68.325293
```

## codex-cql

### npm install
```
(node_modules already present)
```
### npm run build
```

> @eval/minisearch@0.1.0 build
> tsc

```
### npm test
```
  ...
# Subtest: empty, whitespace, all-stopword, missing fields, filters, pagination, prefix, and nonexistent boosts are safe
ok 12 - empty, whitespace, all-stopword, missing fields, filters, pagination, prefix, and nonexistent boosts are safe
  ---
  duration_ms: 0.497837
  ...
# Subtest: very long documents can be indexed
ok 13 - very long documents can be indexed
  ---
  duration_ms: 9.198387
  ...
1..13
# tests 13
# suites 0
# pass 13
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 99.352964
```

## claude-baseline

### npm install
```
(node_modules already present)
```
### npm run build
```

> @eval/minisearch@1.0.0 build
> tsc

```
### npm test
```
    # Subtest: no snippet field requested means no snippet property set meaningfully
    ok 3 - no snippet field requested means no snippet property set meaningfully
      ---
      duration_ms: 0.267491
      ...
    1..3
ok 14 - Snippets
  ---
  duration_ms: 5.495451
  type: 'suite'
  ...
1..14
# tests 51
# suites 14
# pass 51
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 440.727526
```

## claude-cql

### npm install
```
(node_modules already present)
```
### npm run build
```

> @eval/minisearch@0.1.0 build
> tsc -p tsconfig.json

```
### npm test
```
  ...
# Subtest: unicode: combining characters match precomposed equivalents
ok 61 - unicode: combining characters match precomposed equivalents
  ---
  duration_ms: 0.315117
  ...
# Subtest: unicode: naïve is tokenized as a single word and matched
ok 62 - unicode: naïve is tokenized as a single word and matched
  ---
  duration_ms: 0.285746
  ...
1..62
# tests 62
# suites 0
# pass 62
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 520.179271
```

