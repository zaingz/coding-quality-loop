# Decision Log

| # | Decision | Why (alternatives rejected) | Reversible? |
|---|---|---|---|
| 1 | Vanilla HTML/CSS/ES modules, zero deps | Requirement: minimal deps. A framework/bundler (React/Vite) adds toolchain weight for a single static page. Rejected rungs justified in plan. | yes |
| 2 | Seeded `mulberry32` RNG + real generator | Satisfies BOTH "generator" and "deterministic tests" with one mechanism; avoids shipping a static puzzle table that can't prove generality. | yes |
| 3 | MRV (fewest-candidates) backtracking | Naive first-empty backtracking hung on sparse boards during uniqueness counting. MRV is standard, small, and makes solve/count fast (~8ms). | yes |
| 4 | `solve()` rejects boards with pre-existing conflicts | Contradictory givens are unsolvable by definition; guarding up front is correct AND avoids a pathological deep search. | yes |
| 5 | Node built-in `node:test` (no Jest/Mocha) | Stdlib test runner covers needs with zero install; aligns with minimality non-negotiable. | yes |
| 6 | Clue floor by difficulty (easy 45 / medium 36 / hard 30) | Predictable difficulty; well above the 17-clue uniqueness floor so generation stays fast and reliably unique. | yes |
| 7 | Uniqueness enforced during cell removal | Removing a clue is committed only if `countSolutions(.,2)===1`, guaranteeing a single solution. | yes |
