# Memory backend: Graphify (graph_relevance = graphify)

Graphify is an optional **graph-relevance** amplifier — NOT a lessons store. When enabled it
builds an incremental code knowledge graph and lets the loop (a) produce a better CONTEXT MAP
and (b) widen lesson recall from literal path matches to graph-related entities.

## Install (opt-in; heavy deps isolated here)

`uv tool install graphifyy` (CLI command is `graphify`). Its dependencies (numpy, networkx,
tree-sitter parsers) live only in this optional path; the default tier never imports them.

## Build (CONTEXT MAP)

`graphify . --update` (incremental via SHA256 + stat cache). Output goes to the gitignored
`graphify-out/` directory (configurable via `memory.graphify.out_dir`).

## Query (budgeted)

`graphify query "<goal>"` or the MCP tools `get_neighbors` / `god_nodes` / `shortest_path`
with a token budget (`memory.graphify.token_budget`, default 2000). Use results to populate
the agent record's `repo_map` fields (`entry_points`, `likely_files`, `callers_checked`).

## Relevance amplification

Map the task's changed files to graph neighbors / community, then pass that widened file set to
`memory-recall` so lessons tagged to related code surface, not just literal path matches.

## Caveats

Graphify community IDs are not stable across re-runs (Leiden); anchor any lesson scope on
stable entity labels, not community IDs. Treat the graph as a regenerable cache. The upstream
license is unverified — adapter isolation keeps this off the dependency-free core regardless.
