# Persistent Per-Project Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent, per-project "lessons" memory to the Coding Quality Loop — a stdlib-only files backend (default, checked-in) behind a backend-agnostic recall/commit/prune contract, plus two documented loop-integrated backends (Honcho, Graphify).

**Architecture:** A new stdlib module `scripts/quality_loop_memory.py` holds all memory logic; `scripts/quality_loop.py` gains four subcommands (`memory-recall`, `memory-commit`, `memory-prune`, `memory-status`) that call it and extends `check-config` to validate a new optional `memory` config block. Lessons live as JSONL in `.quality-loop/memory/` with a ≤40-line auto-loadable `MEMORY.md` index. Honcho (lessons reasoning-recall) and Graphify (code-graph relevance) are documented as `references/` modules the agent drives over MCP/CLI; the files backend is the reference implementation and the only thing tested in dependency-free CI.

**Tech Stack:** Python 3.10+ standard library only (`json`, `re`, `difflib`, `fnmatch`, `hashlib`, `datetime`, `pathlib`, `argparse`, `subprocess`, `tempfile`). No third-party packages anywhere in the default tier.

## Global Constraints

- **Default tier is 100% Python stdlib.** No new runtime dependencies. (README badge: `runtime deps: none`.)
- **Python floor: 3.10+** (matches `SKILL.md` frontmatter `compatibility`).
- **Type-annotated, `from __future__ import annotations`** at the top of every new/edited `.py` (matches `scripts/quality_loop.py`).
- **No pytest.** Tests are behavioral CLI cases in `evals/run_memory_evals.py` (mirror `evals/run_evals.py`: `run_cli` helper, `CASES` list, `tempfile.TemporaryDirectory`, `main()` returns non-zero on any failure) plus function-level asserts via `import quality_loop_memory`.
- **Memory scope = distilled lessons only.** No repo-map-as-memory cache, no `agent-record.json` archive.
- **Writes are manual / advisory.** Do NOT add any new hard gate to `verify-gates`.
- **Anti-bloat:** the only auto-loaded surface is `MEMORY.md` (≤40 lines); recall output respects a hard char budget.
- **Storage:** default `.quality-loop/memory/` (checked-in); `memory.location="local"` → `~/.quality-loop/<project-slug>/`. `graphify-out/` is always gitignored.
- **Single skill package:** Honcho/Graphify ship as `references/*.md` modules, NOT separate `SKILL.md` directories.
- **Lesson kinds enum:** `failure_mode | convention | gotcha | preference`. **Backend enums:** `lessons_store ∈ {files, honcho}`, `graph_relevance ∈ {none, graphify}`, `location ∈ {checked_in, local}`.
- **Commit message footer (every commit):**
  ```
  🤖 Generated with Claude Code
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  ```
- All work lands on branch `feat/per-project-memory` (already created; spec committed there).

---

## File Structure

**Create:**
- `scripts/quality_loop_memory.py` — all memory logic (location, lesson IO, recall/scoring, distillation, prune, index, config validation). One responsibility: the files lessons-store + shared helpers.
- `evals/run_memory_evals.py` — behavioral + function-level eval harness for the memory subsystem.
- `assets/lesson.schema.json` — JSON Schema for one lesson row.
- `.quality-loop/memory/lessons.jsonl` — empty seed (checked-in store).
- `.quality-loop/memory/MEMORY.md` — index stub.
- `references/memory.md` — capability model + backend-agnostic contract + lifecycle wiring.
- `references/memory-honcho.md` — Honcho lessons-store module.
- `references/memory-graphify.md` — Graphify graph-relevance module.
- `.gitignore` already exists; append `graphify-out/`.

**Modify:**
- `scripts/quality_loop.py` — import the memory module; register 4 subparsers; extend `check_config` with the `memory` block.
- `assets/quality-loop.config.example.json` — add a `memory` block.
- `assets/quality-loop.config.schema.json` — describe the `memory` block.
- `SKILL.md` — add "Persistent Project Memory" section + lifecycle references + reference-file list.
- `assets/AGENTS.template.md` — add memory recall/commit commands.
- `README.md` — concise memory subsection.
- `.github/workflows/evals.yml` — run `evals/run_memory_evals.py`.

---

## Task 1: Memory module scaffold — location, lesson IO

**Files:**
- Create: `scripts/quality_loop_memory.py`
- Create: `evals/run_memory_evals.py`

**Interfaces:**
- Produces:
  - `slugify(path: str) -> str`
  - `resolve_memory_dir(location: str = "checked_in", cwd: Path | None = None, home: Path | None = None) -> Path`
  - `lesson_id(text: str) -> str`
  - `LESSON_KINDS: set[str]` = `{"failure_mode","convention","gotcha","preference"}`
  - `normalize_lesson(raw: dict, created: str) -> dict`
  - `load_lessons(mem_dir: Path) -> list[dict]`
  - `append_lesson(mem_dir: Path, lesson: dict) -> None`
  - `save_lessons(mem_dir: Path, lessons: list[dict]) -> None`

- [ ] **Step 1: Create the eval harness skeleton with the first cases**

Create `evals/run_memory_evals.py`:

```python
#!/usr/bin/env python3
"""Behavioral + function-level eval harness for the memory subsystem.

Mirrors evals/run_evals.py: drives the real CLI via subprocess in a tempdir
and asserts on stdlib module functions. Dependency-free; CI-friendly.

Run: python evals/run_memory_evals.py   (exits non-zero if any case fails)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "quality_loop.py"

sys.path.insert(0, str(ROOT / "scripts"))
import quality_loop_memory as mem  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"


def run_cli(*args: str, cwd: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def case_slugify_and_resolve(tmp: Path) -> tuple[bool, str]:
    slug = mem.slugify("/Users/x/workspace/coding-quality-loop")
    checked = mem.resolve_memory_dir("checked_in", cwd=tmp, home=tmp / "home")
    local = mem.resolve_memory_dir("local", cwd=tmp, home=tmp / "home")
    ok = (
        slug == "Users-x-workspace-coding-quality-loop"
        and checked == tmp / ".quality-loop" / "memory"
        and local == (tmp / "home" / ".quality-loop" / mem.slugify(str(tmp.resolve())))
    )
    return ok, f"slug={slug!r}; checked={checked}; local={local}"


def case_lesson_io_roundtrip(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    raw = {"lesson": "Retry on 429 is idempotent here", "kind": "convention", "risk_tier": "medium"}
    row = mem.normalize_lesson(raw, "2026-06-27")
    mem.append_lesson(mem_dir, row)
    # a blank line and a malformed line must be skipped, not crash
    with (mem_dir / "lessons.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("\n")
        fh.write("{not json}\n")
    loaded = mem.load_lessons(mem_dir)
    ok = (
        len(loaded) == 1
        and loaded[0]["lesson"] == raw["lesson"]
        and loaded[0]["id"] == mem.lesson_id(raw["lesson"])
        and loaded[0]["kind"] == "convention"
        and loaded[0]["hits"] == 0
    )
    return ok, f"loaded={loaded}"


CASES = [
    ("slugify + resolve_memory_dir compute correct paths", case_slugify_and_resolve),
    ("lesson append/load round-trips and skips malformed lines", case_lesson_io_roundtrip),
]


def main() -> int:
    failures = 0
    for name, fn in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                ok, detail = fn(Path(td))
            except Exception as exc:  # noqa: BLE001
                ok, detail = False, f"exception: {exc!r}"
        status = PASS if ok else FAIL
        if not ok:
            failures += 1
        print(f"[{status}] {name}\n        {detail}")
    total = len(CASES)
    print(f"\n{total - failures}/{total} memory eval cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the harness to verify it fails**

Run: `python3 evals/run_memory_evals.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'quality_loop_memory'` (or import error), exit non-zero.

- [ ] **Step 3: Create the module with location + lesson IO**

Create `scripts/quality_loop_memory.py`:

```python
#!/usr/bin/env python3
"""Files-backed, stdlib-only lessons memory for the Coding Quality Loop.

The default (and only dependency-free) lessons-store backend. Honcho and
Graphify are documented in references/ and driven by the agent over MCP/CLI;
this module is the reference implementation and the offline eval target.
"""

from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

LESSON_KINDS = {"failure_mode", "convention", "gotcha", "preference"}
RISK_TIERS = {"low", "medium", "high"}
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def slugify(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-")


def resolve_memory_dir(
    location: str = "checked_in",
    cwd: Path | None = None,
    home: Path | None = None,
) -> Path:
    cwd = cwd or Path.cwd()
    home = home or Path.home()
    if location == "local":
        return home / ".quality-loop" / slugify(str(cwd.resolve()))
    return cwd / ".quality-loop" / "memory"


def lesson_id(text: str) -> str:
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:12]


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text or "") if len(w) > 2}


def normalize_lesson(raw: dict[str, Any], created: str) -> dict[str, Any]:
    text = str(raw.get("lesson", "")).strip()
    kind = raw.get("kind") if raw.get("kind") in LESSON_KINDS else "gotcha"
    risk = raw.get("risk_tier") if raw.get("risk_tier") in RISK_TIERS else "low"
    hits_raw = raw.get("hits", 0)
    hits = 0 if isinstance(hits_raw, bool) else int(hits_raw) if isinstance(hits_raw, int) else 0
    return {
        "id": raw.get("id") or lesson_id(text),
        "created": raw.get("created") or created,
        "source_task_id": str(raw.get("source_task_id", "")),
        "kind": kind,
        "risk_tier": risk,
        "scope_globs": [str(g) for g in raw.get("scope_globs", []) if str(g).strip()],
        "keywords": [str(k).lower() for k in raw.get("keywords", []) if str(k).strip()],
        "lesson": text,
        "hits": hits,
    }


def load_lessons(mem_dir: Path) -> list[dict[str, Any]]:
    path = mem_dir / "lessons.jsonl"
    if not path.is_file():
        return []
    lessons: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and str(obj.get("lesson", "")).strip():
            lessons.append(obj)
    return lessons


def append_lesson(mem_dir: Path, lesson: dict[str, Any]) -> None:
    mem_dir.mkdir(parents=True, exist_ok=True)
    with (mem_dir / "lessons.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(lesson, sort_keys=True) + "\n")


def save_lessons(mem_dir: Path, lessons: list[dict[str, Any]]) -> None:
    mem_dir.mkdir(parents=True, exist_ok=True)
    path = mem_dir / "lessons.jsonl"
    tmp = path.with_name("lessons.jsonl.tmp")
    tmp.write_text(
        "".join(json.dumps(l, sort_keys=True) + "\n" for l in lessons),
        encoding="utf-8",
    )
    os.replace(tmp, path)
```

- [ ] **Step 4: Run the harness to verify it passes**

Run: `python3 evals/run_memory_evals.py`
Expected: PASS for both cases; `2/2 memory eval cases passed`; exit 0.

- [ ] **Step 5: Byte-compile**

Run: `python3 -m py_compile scripts/*.py evals/*.py`
Expected: no output, exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/quality_loop_memory.py evals/run_memory_evals.py
git commit -m "$(printf 'feat: memory module scaffold (location + lesson IO)\n\n🤖 Generated with Claude Code\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 2: Lesson schema asset + seed store + gitignore

**Files:**
- Create: `assets/lesson.schema.json`
- Create: `.quality-loop/memory/lessons.jsonl`
- Create: `.quality-loop/memory/MEMORY.md`
- Modify: `.gitignore`
- Modify: `evals/run_memory_evals.py` (add schema-validity case)

**Interfaces:**
- Consumes: nothing new.
- Produces: a committed, valid `assets/lesson.schema.json` and a seeded empty store.

- [ ] **Step 1: Add a case asserting the schema file is valid JSON and the seed store loads empty**

In `evals/run_memory_evals.py`, add this case function above `CASES`:

```python
def case_schema_and_seed_valid(tmp: Path) -> tuple[bool, str]:
    schema = json.loads((ROOT / "assets" / "lesson.schema.json").read_text())
    seed = mem.load_lessons(ROOT / ".quality-loop" / "memory")
    ok = schema.get("type") == "object" and "lesson" in schema.get("properties", {}) and seed == []
    return ok, f"schema_type={schema.get('type')}; seed_count={len(seed)}"
```

Add to `CASES`:

```python
    ("lesson.schema.json is valid and the seed store loads empty", case_schema_and_seed_valid),
```

- [ ] **Step 2: Run the harness to verify the new case fails**

Run: `python3 evals/run_memory_evals.py`
Expected: FAIL on the new case — `FileNotFoundError` for `assets/lesson.schema.json`.

- [ ] **Step 3: Create the schema, seed store, and gitignore entry**

Create `assets/lesson.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Coding Quality Loop Lesson",
  "type": "object",
  "required": ["id", "created", "kind", "risk_tier", "lesson"],
  "properties": {
    "id": {"type": "string", "minLength": 1},
    "created": {"type": "string", "minLength": 1},
    "source_task_id": {"type": "string"},
    "kind": {"type": "string", "enum": ["failure_mode", "convention", "gotcha", "preference"]},
    "risk_tier": {"type": "string", "enum": ["low", "medium", "high"]},
    "scope_globs": {"type": "array", "items": {"type": "string"}},
    "keywords": {"type": "array", "items": {"type": "string"}},
    "lesson": {"type": "string", "minLength": 1},
    "hits": {"type": "integer", "minimum": 0}
  },
  "additionalProperties": true
}
```

Create `.quality-loop/memory/lessons.jsonl` as an empty file (zero bytes):

```bash
mkdir -p .quality-loop/memory && : > .quality-loop/memory/lessons.jsonl
```

Create `.quality-loop/memory/MEMORY.md`:

```markdown
# Project Memory (index)

0 lesson(s). Recall detail with: python3 scripts/quality_loop.py memory-recall.
```

Append to `.gitignore` (it currently contains `__pycache__/`):

```gitignore
graphify-out/
.quality-loop/memory/lessons.jsonl.tmp
```

- [ ] **Step 4: Run the harness to verify it passes**

Run: `python3 evals/run_memory_evals.py`
Expected: PASS for all three cases; `3/3 memory eval cases passed`.

- [ ] **Step 5: Commit**

```bash
git add assets/lesson.schema.json .quality-loop/memory/lessons.jsonl .quality-loop/memory/MEMORY.md .gitignore evals/run_memory_evals.py
git commit -m "$(printf 'feat: lesson schema, seed store, gitignore graphify-out\n\n🤖 Generated with Claude Code\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 3: Recall scoring, selection, and digest

**Files:**
- Modify: `scripts/quality_loop_memory.py`
- Modify: `evals/run_memory_evals.py`

**Interfaces:**
- Consumes: `_tokens`, `LESSON_KINDS` from Task 1.
- Produces:
  - `score_lesson(lesson: dict, goal_tokens: set[str], files: list[str], risk: str) -> float`
  - `recall(lessons: list[dict], goal: str, files: list[str], risk: str, budget_chars: int) -> list[dict]`
  - `render_line(lesson: dict) -> str`
  - `format_digest(lessons: list[dict], budget_chars: int) -> str`

- [ ] **Step 1: Add recall ranking + budget cases**

In `evals/run_memory_evals.py`, add above `CASES`:

```python
def _seed(mem_dir: Path) -> None:
    rows = [
        {"lesson": "Payment retries must be idempotent", "kind": "failure_mode",
         "risk_tier": "high", "scope_globs": ["src/payments/**"], "keywords": ["retry", "idempotent"]},
        {"lesson": "No new dependencies in this repo without justification", "kind": "convention",
         "risk_tier": "medium", "scope_globs": ["**"], "keywords": ["dependency"]},
        {"lesson": "The CSS build step is flaky on CI", "kind": "gotcha",
         "risk_tier": "low", "scope_globs": ["web/**"], "keywords": ["css", "build"]},
    ]
    for r in rows:
        mem.append_lesson(mem_dir, mem.normalize_lesson(r, "2026-06-01"))


def case_recall_ranks_and_is_deterministic(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    _seed(mem_dir)
    lessons = mem.load_lessons(mem_dir)
    out1 = mem.recall(lessons, "fix payment retry bug", ["src/payments/charge.py"], "high", 1500)
    out2 = mem.recall(lessons, "fix payment retry bug", ["src/payments/charge.py"], "high", 1500)
    top_is_payment = out1 and out1[0]["lesson"].startswith("Payment retries")
    deterministic = [l["id"] for l in out1] == [l["id"] for l in out2]
    # an unrelated query returns nothing (only positive scores survive)
    none_out = mem.recall(lessons, "translate the homepage to French", ["i18n/fr.po"], "low", 1500)
    ok = bool(top_is_payment) and deterministic and none_out == []
    return ok, f"top={out1[0]['lesson'] if out1 else None!r}; det={deterministic}; none={none_out}"


def case_recall_respects_budget(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    _seed(mem_dir)
    lessons = mem.load_lessons(mem_dir)
    # tiny budget: at most one line of digest, hard-capped
    selected = mem.recall(lessons, "dependency retry css", ["src/payments/x.py", "web/y.css"], "medium", 40)
    digest = mem.format_digest(selected, 40)
    ok = len(digest) <= 40 and len(selected) >= 1
    return ok, f"digest_len={len(digest)}; selected={len(selected)}; digest={digest!r}"
```

Add to `CASES`:

```python
    ("recall ranks by relevance, is deterministic, drops non-matches", case_recall_ranks_and_is_deterministic),
    ("recall + digest respect the hard char budget", case_recall_respects_budget),
```

- [ ] **Step 2: Run the harness to verify the new cases fail**

Run: `python3 evals/run_memory_evals.py`
Expected: FAIL on the two new cases — `AttributeError: module 'quality_loop_memory' has no attribute 'recall'`.

- [ ] **Step 3: Implement scoring, recall, and digest in the module**

Append to `scripts/quality_loop_memory.py`:

```python
def score_lesson(lesson: dict[str, Any], goal_tokens: set[str], files: list[str], risk: str) -> float:
    score = 0.0
    kw = {str(k).lower() for k in lesson.get("keywords", [])} | _tokens(lesson.get("lesson", ""))
    if goal_tokens and kw:
        score += 2.0 * len(goal_tokens & kw)
    for glob in lesson.get("scope_globs", []):
        if glob == "**":
            score += 0.5  # repo-wide lessons are weakly relevant to any file set
            break
        if any(fnmatch.fnmatch(f, glob) for f in files):
            score += 3.0
            break
    if risk and lesson.get("risk_tier") == risk:
        score += 1.0
    score += min(int(lesson.get("hits", 0)), 5) * 0.1
    return score


def render_line(lesson: dict[str, Any]) -> str:
    return f"- [{lesson.get('kind', '?')}/{lesson.get('risk_tier', '?')}] {str(lesson.get('lesson', '')).strip()}"


def recall(
    lessons: list[dict[str, Any]],
    goal: str,
    files: list[str],
    risk: str,
    budget_chars: int,
) -> list[dict[str, Any]]:
    goal_tokens = _tokens(goal)
    scored = [(score_lesson(l, goal_tokens, files, risk), l) for l in lessons]
    scored = [(s, l) for s, l in scored if s > 0]
    scored.sort(key=lambda sl: (-sl[0], str(sl[1].get("id", ""))))
    selected: list[dict[str, Any]] = []
    used = 0
    for _, l in scored:
        line_len = len(render_line(l)) + 1
        if selected and used + line_len > budget_chars:
            break
        selected.append(l)
        used += line_len
    return selected


def format_digest(lessons: list[dict[str, Any]], budget_chars: int) -> str:
    if not lessons:
        return "No prior lessons matched."
    body = "\n".join(render_line(l) for l in lessons)
    if len(body) > budget_chars:
        body = body[:budget_chars].rstrip()
    return body
```

- [ ] **Step 4: Run the harness to verify it passes**

Run: `python3 evals/run_memory_evals.py`
Expected: PASS for all cases; `5/5 memory eval cases passed`.

- [ ] **Step 5: Commit**

```bash
git add scripts/quality_loop_memory.py evals/run_memory_evals.py
git commit -m "$(printf 'feat: lesson recall scoring, selection, and budgeted digest\n\n🤖 Generated with Claude Code\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 4: Index regeneration + `memory-recall` CLI (with hits bump)

**Files:**
- Modify: `scripts/quality_loop_memory.py`
- Modify: `scripts/quality_loop.py`
- Modify: `evals/run_memory_evals.py`

**Interfaces:**
- Consumes: `recall`, `format_digest`, `load_lessons`, `save_lessons`, `render_line`.
- Produces:
  - `write_index(mem_dir: Path, lessons: list[dict], max_lines: int = 40) -> None`
  - `bump_hits(mem_dir: Path, ids: list[str]) -> None`
  - `cmd_recall(args) -> int`  (in the memory module; takes `args.goal, args.files, args.risk, args.budget, args.location, args.json`)
  - In `quality_loop.py`: a `memory-recall` subparser dispatching to `quality_loop_memory.cmd_recall`.

- [ ] **Step 1: Add a CLI recall case (digest output + hits bump + index ≤40 lines)**

In `evals/run_memory_evals.py`, add above `CASES`:

```python
def case_cli_recall_bumps_hits_and_index(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    _seed(mem_dir)
    code, out, err = run_cli(
        "memory-recall", "--goal", "payment retry", "--files", "src/payments/charge.py",
        "--risk", "high", "--budget", "1500", cwd=str(tmp),
    )
    digest_ok = code == 0 and "Payment retries" in out
    after = {l["id"]: l for l in mem.load_lessons(mem_dir)}
    payment = next((l for l in after.values() if l["lesson"].startswith("Payment retries")), None)
    bumped = payment is not None and payment["hits"] == 1
    index = (mem_dir / "MEMORY.md").read_text().splitlines()
    index_ok = (mem_dir / "MEMORY.md").is_file() and len(index) <= 40
    ok = digest_ok and bumped and index_ok
    return ok, f"code={code}; bumped={bumped}; index_lines={len(index)}; err={err.strip()!r}"
```

Add to `CASES`:

```python
    ("memory-recall prints a digest, bumps hits, and writes a <=40-line index", case_cli_recall_bumps_hits_and_index),
```

- [ ] **Step 2: Run the harness to verify it fails**

Run: `python3 evals/run_memory_evals.py`
Expected: FAIL — the `memory-recall` subcommand does not exist yet (`argparse` error / non-zero exit).

- [ ] **Step 3: Add `write_index`, `bump_hits`, and `cmd_recall` to the module**

Append to `scripts/quality_loop_memory.py`:

```python
def write_index(mem_dir: Path, lessons: list[dict[str, Any]], max_lines: int = 40) -> None:
    mem_dir.mkdir(parents=True, exist_ok=True)
    ranked = sorted(
        lessons,
        key=lambda x: (int(x.get("hits", 0)), str(x.get("created", ""))),
        reverse=True,
    )
    header = [
        "# Project Memory (index)",
        "",
        f"{len(lessons)} lesson(s). Recall detail with: python3 scripts/quality_loop.py memory-recall.",
        "",
    ]
    body_budget = max(max_lines - len(header), 0)
    body = [render_line(l) for l in ranked[:body_budget]]
    (mem_dir / "MEMORY.md").write_text("\n".join(header + body) + "\n", encoding="utf-8")


def bump_hits(mem_dir: Path, ids: list[str]) -> None:
    idset = set(ids)
    lessons = load_lessons(mem_dir)
    for l in lessons:
        if l.get("id") in idset:
            l["hits"] = int(l.get("hits", 0)) + 1
    save_lessons(mem_dir, lessons)
    write_index(mem_dir, lessons)


def _split_files(value: str | None) -> list[str]:
    return [f.strip() for f in (value or "").split(",") if f.strip()]


def cmd_recall(args: Any) -> int:
    mem_dir = resolve_memory_dir(args.location)
    lessons = load_lessons(mem_dir)
    selected = recall(lessons, args.goal or "", _split_files(args.files), args.risk, args.budget)
    if selected:
        bump_hits(mem_dir, [str(l.get("id", "")) for l in selected])
    if args.json:
        print(json.dumps(selected, indent=2))
    else:
        print(format_digest(selected, args.budget))
    return 0
```

- [ ] **Step 4: Register the `memory-recall` subparser in `quality_loop.py`**

In `scripts/quality_loop.py`, add the import near the other imports (after `from typing import Any`):

```python
import quality_loop_memory as qlmem
```

In `main()`, after the `p_eval` block and before `args = parser.parse_args()`, add:

```python
    p_mrecall = sub.add_parser("memory-recall", help="Recall relevant prior lessons (budget-capped)")
    p_mrecall.add_argument("--goal", default="")
    p_mrecall.add_argument("--files", default="")
    p_mrecall.add_argument("--risk", choices=sorted(RISK_TIERS), default="low")
    p_mrecall.add_argument("--budget", type=int, default=1500)
    p_mrecall.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_mrecall.add_argument("--json", action="store_true")
    p_mrecall.set_defaults(func=qlmem.cmd_recall)
```

- [ ] **Step 5: Run the harness to verify it passes**

Run: `python3 evals/run_memory_evals.py`
Expected: PASS for all cases; `6/6 memory eval cases passed`.

- [ ] **Step 6: Verify the existing suites still pass**

Run: `python3 -m py_compile scripts/*.py evals/*.py && python3 evals/run_evals.py`
Expected: byte-compile clean; `26/26 eval cases passed`.

- [ ] **Step 7: Commit**

```bash
git add scripts/quality_loop_memory.py scripts/quality_loop.py evals/run_memory_evals.py
git commit -m "$(printf 'feat: memory-recall CLI with index regen and hit-count curation\n\n🤖 Generated with Claude Code\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 5: Distillation + `memory-commit` CLI

**Files:**
- Modify: `scripts/quality_loop_memory.py`
- Modify: `scripts/quality_loop.py`
- Modify: `evals/run_memory_evals.py`

**Interfaces:**
- Consumes: `normalize_lesson`, `append_lesson`, `load_lessons`, `write_index`, `_tokens`, `load_json` (from `quality_loop`).
- Produces:
  - `artifact_text(value: Any) -> str`
  - `files_to_globs(files: list[str]) -> list[str]`
  - `distill_record(record: dict, created: str, override_lesson: str | None = None, override_kind: str | None = None, override_scope: list[str] | None = None) -> list[dict]`
  - `cmd_commit(args) -> int` (uses `args.record, args.lesson, args.kind, args.scope, args.location`)
  - In `quality_loop.py`: a `memory-commit` subparser.

- [ ] **Step 1: Add distillation + CLI commit cases**

In `evals/run_memory_evals.py`, add above `CASES`:

```python
def case_distill_record(tmp: Path) -> tuple[bool, str]:
    record = {
        "task_id": "t-42",
        "goal": "Fix checkout retry double-charge",
        "risk_tier": "high",
        "repeated_failure": True,
        "harness_update": {"type": "test", "change": "added idempotency regression test for retries"},
        "minimality_decision": {"rung": "reuse", "reason": "existing retry helper already guards this"},
        "review_findings": ["fresh-context review: watch for partial writes on timeout"],
        "repo_map": {"likely_files": ["src/payments/charge.py:do_charge"], "entry_points": []},
    }
    rows = mem.distill_record(record, "2026-06-27")
    kinds = {r["kind"] for r in rows}
    has_failure = any("idempotency regression" in r["lesson"] and r["kind"] == "failure_mode" for r in rows)
    scoped = all(any(g.startswith("src/payments") for g in r["scope_globs"]) for r in rows)
    ok = len(rows) >= 2 and has_failure and "preference" in kinds and scoped
    return ok, f"rows={len(rows)}; kinds={kinds}; has_failure={has_failure}; scoped={scoped}"


def case_cli_commit_writes_and_dedups(tmp: Path) -> tuple[bool, str]:
    record = {
        "task_id": "t-7", "goal": "Harden upload path", "risk_tier": "medium",
        "harness_update": "Validate content-type before streaming uploads",
        "minimality_decision": {"rung": "stdlib", "reason": "mimetypes covers it"},
        "repo_map": {"likely_files": ["src/upload/handler.py"]},
    }
    rec_path = tmp / "agent-record.json"
    rec_path.write_text(json.dumps(record))
    code1, out1, err1 = run_cli("memory-commit", str(rec_path), cwd=str(tmp))
    code2, _, _ = run_cli("memory-commit", str(rec_path), cwd=str(tmp))  # idempotent
    lessons = mem.load_lessons(tmp / ".quality-loop" / "memory")
    ids = [l["id"] for l in lessons]
    ok = code1 == 0 and code2 == 0 and len(ids) == len(set(ids)) and len(lessons) >= 1
    return ok, f"code1={code1}; code2={code2}; count={len(lessons)}; err={err1.strip()!r}"
```

Add to `CASES`:

```python
    ("distill_record turns a record into scoped, kind-tagged lessons", case_distill_record),
    ("memory-commit writes lessons and is idempotent (dedup by id)", case_cli_commit_writes_and_dedups),
```

- [ ] **Step 2: Run the harness to verify the new cases fail**

Run: `python3 evals/run_memory_evals.py`
Expected: FAIL — `AttributeError: ... 'distill_record'`.

- [ ] **Step 3: Implement distillation + `cmd_commit` in the module**

Append to `scripts/quality_loop_memory.py`:

```python
def artifact_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts = [
            str(v).strip()
            for v in value.values()
            if isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip()
        ]
        return "; ".join(parts)
    return ""


def files_to_globs(files: list[str]) -> list[str]:
    globs: list[str] = []
    for f in files:
        directory = "/".join(f.split("/")[:-1])
        glob = (directory + "/**") if directory else f
        if glob and glob not in globs:
            globs.append(glob)
    return globs or ["**"]


def _make_row(
    lesson: str, kind: str, risk: str, scope: list[str], task_id: str
) -> dict[str, Any]:
    return {
        "lesson": lesson,
        "kind": kind,
        "risk_tier": risk,
        "scope_globs": scope,
        "keywords": sorted(_tokens(lesson))[:12],
        "source_task_id": task_id,
    }


def _record_files(record: dict[str, Any]) -> list[str]:
    files: list[str] = []
    repo_map = record.get("repo_map") or {}
    for key in ("likely_files", "entry_points"):
        for entry in repo_map.get(key, []) or []:
            path = str(entry).split(":")[0].strip()
            if path and path not in files:
                files.append(path)
    return files


def distill_record(
    record: dict[str, Any],
    created: str,
    override_lesson: str | None = None,
    override_kind: str | None = None,
    override_scope: list[str] | None = None,
) -> list[dict[str, Any]]:
    risk = record.get("risk_tier") if record.get("risk_tier") in RISK_TIERS else "low"
    task_id = str(record.get("task_id", ""))
    goal = str(record.get("goal", "")).strip()
    scope = override_scope or files_to_globs(_record_files(record))
    raw_rows: list[dict[str, Any]] = []

    if override_lesson and override_lesson.strip():
        raw_rows.append(_make_row(override_lesson.strip(), override_kind or "gotcha", risk, scope, task_id))
    else:
        harness = artifact_text(record.get("harness_update"))
        if harness:
            kind = "failure_mode" if record.get("repeated_failure") else "convention"
            raw_rows.append(_make_row(harness, kind, risk, scope, task_id))
        decision = record.get("minimality_decision") or {}
        reason = str(decision.get("reason", "")).strip()
        if reason:
            rung = decision.get("rung", "")
            raw_rows.append(
                _make_row(f"Prefer rung '{rung}': {reason}", "preference", risk, scope, task_id)
            )
        for finding in record.get("review_findings", []) or []:
            text = finding if isinstance(finding, str) else artifact_text(finding)
            text = str(text).strip()
            if text and "approv" not in text.lower():
                raw_rows.append(_make_row(f"Review note: {text}", "gotcha", risk, scope, task_id))

    return [normalize_lesson(r, created) for r in raw_rows if str(r.get("lesson", "")).strip()]


def cmd_commit(args: Any) -> int:
    record = json.loads(Path(args.record).read_text(encoding="utf-8"))
    mem_dir = resolve_memory_dir(args.location)
    created = date.today().isoformat()
    override_scope = [args.scope] if getattr(args, "scope", None) else None
    rows = distill_record(
        record, created,
        override_lesson=getattr(args, "lesson", None),
        override_kind=getattr(args, "kind", None),
        override_scope=override_scope,
    )
    if not rows:
        print(
            "no lesson distilled (record has no harness_update/minimality/review and no --lesson)",
            file=sys.stderr,
        )
        return 1
    existing = load_lessons(mem_dir)
    existing_ids = {l.get("id") for l in existing}
    added = 0
    for row in rows:
        if row["id"] in existing_ids:
            continue
        append_lesson(mem_dir, row)
        existing.append(row)
        existing_ids.add(row["id"])
        added += 1
    write_index(mem_dir, existing)
    print(f"committed {added} lesson(s) to {mem_dir / 'lessons.jsonl'}")
    return 0
```

Add `import sys` to the module's import block (top of file, with the other stdlib imports).

- [ ] **Step 4: Register the `memory-commit` subparser in `quality_loop.py`**

In `main()`, after the `memory-recall` block:

```python
    p_mcommit = sub.add_parser("memory-commit", help="Distill an agent record into durable lessons")
    p_mcommit.add_argument("record")
    p_mcommit.add_argument("--lesson", help="Commit this exact lesson instead of distilling the record")
    p_mcommit.add_argument("--kind", choices=sorted(qlmem.LESSON_KINDS), default="gotcha")
    p_mcommit.add_argument("--scope", help="Override scope glob, e.g. 'src/payments/**'")
    p_mcommit.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_mcommit.set_defaults(func=qlmem.cmd_commit)
```

- [ ] **Step 5: Run the harness to verify it passes**

Run: `python3 evals/run_memory_evals.py`
Expected: PASS for all cases; `8/8 memory eval cases passed`.

- [ ] **Step 6: Commit**

```bash
git add scripts/quality_loop_memory.py scripts/quality_loop.py evals/run_memory_evals.py
git commit -m "$(printf 'feat: memory-commit distills agent records into durable lessons\n\n🤖 Generated with Claude Code\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 6: Prune + `memory-prune` CLI

**Files:**
- Modify: `scripts/quality_loop_memory.py`
- Modify: `scripts/quality_loop.py`
- Modify: `evals/run_memory_evals.py`

**Interfaces:**
- Consumes: `load_lessons`, `save_lessons`, `write_index`.
- Produces:
  - `prune(lessons: list[dict], max_n: int = 200, max_age_days: int = 365, now: date | None = None) -> list[dict]`
  - `cmd_prune(args) -> int` (uses `args.max, args.max_age_days, args.location`)
  - In `quality_loop.py`: a `memory-prune` subparser.

- [ ] **Step 1: Add prune cases (dedup + age-out + cap)**

In `evals/run_memory_evals.py`, add above `CASES`:

```python
from datetime import date as _date  # add near the top imports if not present


def case_prune_dedups_ages_and_caps(tmp: Path) -> tuple[bool, str]:
    base = [
        {"lesson": "Payment retries must be idempotent", "kind": "failure_mode",
         "risk_tier": "high", "created": "2026-06-20", "hits": 3},
        {"lesson": "Payment retries must be idempotent!", "kind": "failure_mode",
         "risk_tier": "high", "created": "2026-06-21", "hits": 0},  # near-duplicate -> dropped
        {"lesson": "Old never-recalled note", "kind": "gotcha",
         "risk_tier": "low", "created": "2020-01-01", "hits": 0},   # aged + 0 hits -> dropped
    ]
    lessons = [mem.normalize_lesson(r, "2026-06-27") for r in base]
    pruned = mem.prune(lessons, max_n=200, max_age_days=365, now=_date(2026, 6, 27))
    texts = [l["lesson"] for l in pruned]
    ok = (
        "Payment retries must be idempotent" in texts
        and "Payment retries must be idempotent!" not in texts
        and "Old never-recalled note" not in texts
    )
    # cap test
    many = [mem.normalize_lesson({"lesson": f"distinct lesson number {i}", "kind": "gotcha"}, "2026-06-27") for i in range(10)]
    capped = mem.prune(many, max_n=4, max_age_days=3650, now=_date(2026, 6, 27))
    ok = ok and len(capped) == 4
    return ok, f"pruned={texts}; capped={len(capped)}"


def case_cli_prune(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    for r in [
        {"lesson": "alpha lesson here", "kind": "gotcha"},
        {"lesson": "alpha lesson here", "kind": "gotcha"},  # exact dup id -> file has 2 lines? no, append twice
    ]:
        mem.append_lesson(mem_dir, mem.normalize_lesson(r, "2026-06-27"))
    code, out, err = run_cli("memory-prune", cwd=str(tmp))
    remaining = mem.load_lessons(mem_dir)
    ok = code == 0 and len(remaining) == 1
    return ok, f"code={code}; remaining={len(remaining)}; out={out.strip()!r}; err={err.strip()!r}"
```

Add to `CASES`:

```python
    ("prune dedups near-duplicates, ages out 0-hit stale, and caps", case_prune_dedups_ages_and_caps),
    ("memory-prune collapses duplicates on disk", case_cli_prune),
```

- [ ] **Step 2: Run the harness to verify the new cases fail**

Run: `python3 evals/run_memory_evals.py`
Expected: FAIL — `AttributeError: ... 'prune'`.

- [ ] **Step 3: Implement `prune` + `cmd_prune` in the module**

Append to `scripts/quality_loop_memory.py`:

```python
def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def prune(
    lessons: list[dict[str, Any]],
    max_n: int = 200,
    max_age_days: int = 365,
    now: date | None = None,
) -> list[dict[str, Any]]:
    now = now or date.today()
    fresh: list[dict[str, Any]] = []
    for l in lessons:
        created = _parse_date(l.get("created"))
        if created and int(l.get("hits", 0)) == 0 and (now - created).days > max_age_days:
            continue
        fresh.append(l)
    deduped: list[dict[str, Any]] = []
    for l in sorted(fresh, key=lambda x: (-int(x.get("hits", 0)), str(x.get("created", "")))):
        text = str(l.get("lesson", ""))
        if any(
            difflib.SequenceMatcher(None, text, str(k.get("lesson", ""))).ratio() >= 0.92
            for k in deduped
        ):
            continue
        deduped.append(l)
    deduped.sort(key=lambda x: (int(x.get("hits", 0)), str(x.get("created", ""))), reverse=True)
    return deduped[:max_n]


def cmd_prune(args: Any) -> int:
    mem_dir = resolve_memory_dir(args.location)
    lessons = load_lessons(mem_dir)
    kept = prune(lessons, max_n=args.max, max_age_days=args.max_age_days)
    save_lessons(mem_dir, kept)
    write_index(mem_dir, kept)
    print(f"pruned {len(lessons) - len(kept)} lesson(s); {len(kept)} remain")
    return 0
```

- [ ] **Step 4: Register the `memory-prune` subparser in `quality_loop.py`**

In `main()`, after the `memory-commit` block:

```python
    p_mprune = sub.add_parser("memory-prune", help="Dedup + cap the lessons ledger")
    p_mprune.add_argument("--max", type=int, default=200)
    p_mprune.add_argument("--max-age-days", type=int, default=365)
    p_mprune.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_mprune.set_defaults(func=qlmem.cmd_prune)
```

- [ ] **Step 5: Run the harness to verify it passes**

Run: `python3 evals/run_memory_evals.py`
Expected: PASS for all cases; `10/10 memory eval cases passed`.

- [ ] **Step 6: Commit**

```bash
git add scripts/quality_loop_memory.py scripts/quality_loop.py evals/run_memory_evals.py
git commit -m "$(printf 'feat: memory-prune dedups, ages out, and caps the ledger\n\n🤖 Generated with Claude Code\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 7: `memory-status` CLI + config validation + `check-config` wiring

**Files:**
- Modify: `scripts/quality_loop_memory.py`
- Modify: `scripts/quality_loop.py`
- Modify: `assets/quality-loop.config.example.json`
- Modify: `assets/quality-loop.config.schema.json`
- Modify: `evals/run_memory_evals.py`

**Interfaces:**
- Consumes: `load_lessons`, `resolve_memory_dir`.
- Produces:
  - `count_kinds(lessons: list[dict]) -> dict[str, int]`
  - `validate_memory_config(memory: Any) -> list[str]`
  - `cmd_status(args) -> int` (uses `args.location`)
  - In `quality_loop.py`: a `memory-status` subparser, and a `memory`-block check inside `check_config`.

- [ ] **Step 1: Add status + config-validation cases**

In `evals/run_memory_evals.py`, add above `CASES`:

```python
def case_cli_status(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    mem.append_lesson(mem_dir, mem.normalize_lesson({"lesson": "be careful here", "kind": "gotcha"}, "2026-06-27"))
    code, out, err = run_cli("memory-status", cwd=str(tmp))
    data = json.loads(out) if code == 0 else {}
    ok = code == 0 and data.get("lesson_count") == 1 and "memory_dir" in data
    return ok, f"code={code}; out={out.strip()!r}; err={err.strip()!r}"


def case_check_config_validates_memory_block(tmp: Path) -> tuple[bool, str]:
    good = mem.validate_memory_config(
        {"lessons_store": "files", "graph_relevance": "none", "location": "checked_in", "recall_budget_chars": 1500}
    )
    bad = mem.validate_memory_config(
        {"lessons_store": "redis", "graph_relevance": "neo4j", "location": "cloud", "recall_budget_chars": 0}
    )
    # the shipped example config must validate via the CLI
    code, out, err = run_cli("check-config", str(ROOT / "assets" / "quality-loop.config.example.json"))
    ok = good == [] and len(bad) == 4 and code == 0
    return ok, f"good={good}; bad={bad}; check_config_exit={code}; err={err.strip()!r}"
```

Add to `CASES`:

```python
    ("memory-status reports the store location and counts", case_cli_status),
    ("validate_memory_config + check-config accept/reject the memory block", case_check_config_validates_memory_block),
```

- [ ] **Step 2: Run the harness to verify the new cases fail**

Run: `python3 evals/run_memory_evals.py`
Expected: FAIL — `AttributeError: ... 'validate_memory_config'` / missing `memory-status`.

- [ ] **Step 3: Implement `count_kinds`, `validate_memory_config`, `cmd_status` in the module**

Append to `scripts/quality_loop_memory.py`:

```python
def count_kinds(lessons: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for l in lessons:
        kind = str(l.get("kind", "?"))
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def validate_memory_config(memory: Any) -> list[str]:
    if not isinstance(memory, dict):
        return ["memory must be an object"]
    errors: list[str] = []
    if memory.get("lessons_store", "files") not in {"files", "honcho"}:
        errors.append("memory.lessons_store must be 'files' or 'honcho'")
    if memory.get("graph_relevance", "none") not in {"none", "graphify"}:
        errors.append("memory.graph_relevance must be 'none' or 'graphify'")
    if memory.get("location", "checked_in") not in {"checked_in", "local"}:
        errors.append("memory.location must be 'checked_in' or 'local'")
    budget = memory.get("recall_budget_chars", 1500)
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        errors.append("memory.recall_budget_chars must be a positive integer")
    return errors


def cmd_status(args: Any) -> int:
    mem_dir = resolve_memory_dir(args.location)
    lessons = load_lessons(mem_dir)
    print(json.dumps({
        "memory_dir": str(mem_dir),
        "exists": (mem_dir / "lessons.jsonl").is_file(),
        "location": args.location,
        "lesson_count": len(lessons),
        "kinds": count_kinds(lessons),
    }, indent=2))
    return 0
```

- [ ] **Step 4: Register `memory-status` and wire `check_config`**

In `scripts/quality_loop.py` `main()`, after the `memory-prune` block:

```python
    p_mstatus = sub.add_parser("memory-status", help="Show memory store location and lesson counts")
    p_mstatus.add_argument("--location", choices=["checked_in", "local"], default="checked_in")
    p_mstatus.set_defaults(func=qlmem.cmd_status)
```

In `check_config(args)`, immediately before the final `if errors:` block:

```python
    memory = config.get("memory")
    if memory is not None:
        errors.extend(qlmem.validate_memory_config(memory))
```

- [ ] **Step 5: Add the `memory` block to the example config**

In `assets/quality-loop.config.example.json`, add this top-level key (after `"routing_defaults": { ... }`, as a sibling):

```json
  "memory": {
    "lessons_store": "files",
    "graph_relevance": "none",
    "location": "checked_in",
    "recall_budget_chars": 1500,
    "honcho": {"workspace_id": null, "peer_id": null, "session_template": null, "target_peer": null},
    "graphify": {"out_dir": "graphify-out", "token_budget": 2000}
  }
```

(Remember to add the comma after the `routing_defaults` object so the JSON stays valid.)

- [ ] **Step 6: Describe the `memory` block in the config schema**

In `assets/quality-loop.config.schema.json`, inside `"properties"`, add a sibling to `"routing_defaults"`:

```json
    "memory": {
      "type": "object",
      "properties": {
        "lessons_store": {"type": "string", "enum": ["files", "honcho"]},
        "graph_relevance": {"type": "string", "enum": ["none", "graphify"]},
        "location": {"type": "string", "enum": ["checked_in", "local"]},
        "recall_budget_chars": {"type": "integer", "minimum": 1},
        "honcho": {"type": "object"},
        "graphify": {"type": "object"}
      },
      "additionalProperties": true
    }
```

(Add the comma after the preceding property so the JSON stays valid.)

- [ ] **Step 7: Run all suites**

Run:
```bash
python3 -m py_compile scripts/*.py evals/*.py
python3 evals/run_memory_evals.py
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json
python3 evals/run_evals.py
```
Expected: `12/12 memory eval cases passed`; `config ok`; `9/9 eval cases passed`; `26/26 eval cases passed`.

- [ ] **Step 8: Commit**

```bash
git add scripts/quality_loop_memory.py scripts/quality_loop.py assets/quality-loop.config.example.json assets/quality-loop.config.schema.json evals/run_memory_evals.py
git commit -m "$(printf 'feat: memory-status + memory config block validation\n\n🤖 Generated with Claude Code\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 8: Reference modules (contract + Honcho + Graphify)

**Files:**
- Create: `references/memory.md`
- Create: `references/memory-honcho.md`
- Create: `references/memory-graphify.md`
- Modify: `evals/run_memory_evals.py` (docs-presence lint)

**Interfaces:**
- Consumes: nothing (documentation).
- Produces: three reference docs whose presence/keywords are linted (mirrors `case_repeated_mistake_retrospective` in `evals/run_evals.py`).

- [ ] **Step 1: Add a docs-presence lint case**

In `evals/run_memory_evals.py`, add above `CASES`:

```python
def case_reference_modules_present(tmp: Path) -> tuple[bool, str]:
    docs = {
        "memory.md": ["recall", "commit", "prune", "lessons_store", "graph_relevance", "anti-bloat"],
        "memory-honcho.md": ["workspace", "peer", "add_messages_to_session", "query_conclusions", "privacy"],
        "memory-graphify.md": ["graphify", "graph-relevance", "token_budget", "context map"],
    }
    missing: list[str] = []
    for fname, terms in docs.items():
        path = ROOT / "references" / fname
        text = path.read_text().lower() if path.exists() else ""
        for term in terms:
            if term.lower() not in text:
                missing.append(f"{fname}:{term}")
    return (not missing), (f"missing={missing}" if missing else "all reference modules present")
```

Add to `CASES`:

```python
    ("memory reference modules exist with required content", case_reference_modules_present),
```

- [ ] **Step 2: Run the harness to verify it fails**

Run: `python3 evals/run_memory_evals.py`
Expected: FAIL on the new case — files do not exist; `missing=[...]`.

- [ ] **Step 3: Write `references/memory.md`**

Create `references/memory.md` with this content:

```markdown
# Persistent Project Memory

The Coding Quality Loop is stateless across tasks unless this memory layer is on.
Memory holds **distilled lessons only** — crisp conclusions (failure modes, conventions,
gotchas, preferences), never transcripts or diffs. It is read on demand into a hard budget
and written when a lesson is worth keeping. It is advisory: it never replaces tests, review,
or the runtime gates.

## Two capabilities (one interface)

| Capability | What it does | Backends | Default |
|---|---|---|---|
| `lessons_store` | persist + recall lessons | `files`, `honcho` | `files` |
| `graph_relevance` | widen recall + feed CONTEXT MAP from a code graph | `none`, `graphify` | `none` |

Select via `assets/quality-loop.config.example.json` -> `memory`. A missing or offline
adapter degrades to `files` / `none`; a task never blocks on memory infrastructure.

## The contract (backend-agnostic)

- **recall(goal, files, risk, budget)** -> a budget-capped, relevance-scoped digest of prior
  lessons. Files backend: `python3 scripts/quality_loop.py memory-recall --goal "..."
  --files a,b --risk medium --budget 1500`.
- **commit(record | --lesson)** -> distills `harness_update`, `minimality_decision`, and
  `review_findings` from an agent record into lesson rows. Files backend:
  `python3 scripts/quality_loop.py memory-commit agent-record.json`.
- **prune()** -> dedup + age-out + cap. Files backend:
  `python3 scripts/quality_loop.py memory-prune`.

## Storage

- Default (checked-in): `.quality-loop/memory/lessons.jsonl` + a <=40-line `MEMORY.md`
  index (the only surface a host may auto-load).
- Override (machine-local): `memory.location="local"` -> `~/.quality-loop/<project-slug>/`.
- `graphify-out/` is always gitignored (regenerable cache, not memory).

## Lifecycle wiring (manual, advisory)

- CONTEXT MAP: if `graph_relevance="graphify"`, build/query the graph for the map (see
  `memory-graphify.md`).
- INTAKE / CONTEXT MAP: run `recall` and consider the digest. Recommended, not gated.
- RETROSPECTIVE: run `commit` when a lesson is worth keeping. `verify-gates` stays advisory
  about memory — there is no new hard block.

## Anti-bloat rules

Retrieval, never stuffing. Only the <=40-line `MEMORY.md` auto-loads. Recall is
relevance-scoped (keyword + path-glob + risk) and hard-capped by budget. Store conclusions,
not history. Prune periodically. Hit-counts curate: recalled lessons rise, unused ones age out.

See `memory-honcho.md` and `memory-graphify.md` for the optional backends.
```

- [ ] **Step 4: Write `references/memory-honcho.md`**

Create `references/memory-honcho.md`:

```markdown
# Memory backend: Honcho (lessons_store = honcho)

Honcho is an optional, reasoning-based lessons store. It is **agent-driven over MCP** — a
stdlib script cannot call MCP, so the loop drives Honcho's tools per this module. It does not
change the loop's contract; it implements `recall` and `commit` for lessons.

## Configuration

`memory.honcho` in the config is fully driven by you, so the adapter slots into whatever
Honcho governance already exists (e.g. a workspace whose rules forbid creating new peer IDs):

- `workspace_id` — the Honcho workspace for this project.
- `peer_id` — the peer the lessons are attributed to / queried about (never invent one if the
  workspace forbids it).
- `session_template` — naming for the session, e.g. `ql-<repo>-lessons`.
- `target_peer` — optional, when modelling one peer's view of another.

## recall (INTAKE / CONTEXT MAP)

Use the cheap retrieval path first: `search` (raw records) or `query_conclusions` scoped to
`peer_id` / `workspace_id`. Use `chat` (reasoning over the representation) only when needed —
it costs an LLM call. Keep the injected digest within the same budget as the files backend.

## commit (RETROSPECTIVE)

Write one compact `add_messages_to_session` pair (user request + verified outcome) with
metadata `{repo, task_id, risk, files, verdict}`. This mirrors the completion-record shape
Honcho already stores in practice. Run `schedule_dream` at most weekly or per milestone for
consolidation — never per task.

## Privacy

The Honcho managed cloud egresses distilled lessons to a third party. Disclose this at config
time. For sensitive IP, use a self-hosted Honcho or the default `files` backend. Never store
secrets, tokens, or raw sensitive logs as lessons.
```

- [ ] **Step 5: Write `references/memory-graphify.md`**

Create `references/memory-graphify.md`:

```markdown
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
```

- [ ] **Step 6: Run the harness to verify it passes**

Run: `python3 evals/run_memory_evals.py`
Expected: PASS for all cases; `13/13 memory eval cases passed`.

- [ ] **Step 7: Commit**

```bash
git add references/memory.md references/memory-honcho.md references/memory-graphify.md evals/run_memory_evals.py
git commit -m "$(printf 'docs: memory contract + Honcho and Graphify backend modules\n\n🤖 Generated with Claude Code\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 9: Wire memory into SKILL.md, AGENTS template, and README

**Files:**
- Modify: `SKILL.md`
- Modify: `assets/AGENTS.template.md`
- Modify: `README.md`
- Modify: `evals/run_memory_evals.py` (SKILL.md presence lint)

**Interfaces:**
- Consumes: the reference modules from Task 8.
- Produces: the loop's instructions referencing memory recall/commit and the new reference files.

- [ ] **Step 1: Add a SKILL.md presence lint case**

In `evals/run_memory_evals.py`, add above `CASES`:

```python
def case_skill_documents_memory(tmp: Path) -> tuple[bool, str]:
    text = (ROOT / "SKILL.md").read_text().lower()
    must_have = ["persistent project memory", "memory-recall", "memory-commit", "references/memory.md"]
    missing = [m for m in must_have if m not in text]
    return (not missing), (f"missing={missing}" if missing else "SKILL.md documents memory")
```

Add to `CASES`:

```python
    ("SKILL.md documents the persistent memory step", case_skill_documents_memory),
```

- [ ] **Step 2: Run the harness to verify it fails**

Run: `python3 evals/run_memory_evals.py`
Expected: FAIL on the new case — `missing=['persistent project memory', 'memory-recall', ...]`.

- [ ] **Step 3: Add the "Persistent Project Memory" section to SKILL.md**

In `SKILL.md`, insert this section immediately after the `### RETROSPECTIVE / SKILL UPDATE`
subsection and before `## Hard Rules`:

```markdown
### PERSISTENT PROJECT MEMORY (optional, advisory)

Across tasks, the loop can keep a small per-project ledger of **distilled lessons** —
failure modes, conventions, gotchas, and preferences — so a lesson learned once is recalled
later instead of relearned. It is retrieval, not context stuffing: only a <=40-line
`MEMORY.md` index may auto-load, and recall is budget-capped and relevance-scoped.

- **Recall at INTAKE / CONTEXT MAP** (recommended, not gated):
  `python3 scripts/quality_loop.py memory-recall --goal "<goal>" --files a,b,c --risk medium --budget 1500`
  Consider the returned lessons before mapping the change.
- **Commit at RETROSPECTIVE** (manual; you decide it is worth keeping):
  `python3 scripts/quality_loop.py memory-commit agent-record.json`
  Distills `harness_update`, `minimality_decision`, and notable `review_findings` into lesson
  rows under `.quality-loop/memory/`.
- **Prune periodically:** `python3 scripts/quality_loop.py memory-prune`.

Writes are advisory — `verify-gates` adds no new hard block. Optional backends (`honcho` for
reasoning recall, `graphify` for code-graph relevance) plug in via the config `memory` block
and degrade to the dependency-free files backend when absent. See `references/memory.md`,
`references/memory-honcho.md`, and `references/memory-graphify.md`.
```

- [ ] **Step 4: Add the reference files to the "Additional References" list in SKILL.md**

In `SKILL.md`, in the `## Additional References` list, add these bullets after the
`references/reviewer-checklists.md` line:

```markdown
- `references/memory.md`: persistent per-project lessons memory — capability model, the
  backend-agnostic recall/commit/prune contract, storage, lifecycle wiring, and anti-bloat rules.
- `references/memory-honcho.md` and `references/memory-graphify.md`: optional loop-integrated
  memory backends (Honcho reasoning recall; Graphify code-graph relevance).
```

- [ ] **Step 5: Add memory commands to the AGENTS template**

In `assets/AGENTS.template.md`, add a short section near the end (before any closing notes):

```markdown
## Project memory (optional, advisory)

- Recall prior lessons before mapping a change:
  `python3 scripts/quality_loop.py memory-recall --goal "<goal>" --files <changed,files> --risk <low|medium|high>`
- Commit a durable lesson at retrospective:
  `python3 scripts/quality_loop.py memory-commit agent-record.json`
- Lessons live in `.quality-loop/memory/`. Writes are advisory; never store secrets as lessons.
```

- [ ] **Step 6: Add a README subsection**

In `README.md`, add this subsection at the end of the "What it enforces — and what it
deliberately does *not*" section (or as a new `### Persistent project memory` block under it):

```markdown
### Persistent project memory (optional)

The loop can keep a tiny per-project ledger of **distilled lessons** (failure modes,
conventions, gotchas) in `.quality-loop/memory/`, recalled on demand into a hard budget at
INTAKE and written at retrospective — so a lesson learned once is not relearned. It is
retrieval, not context stuffing: only a <=40-line index auto-loads. The default backend is
stdlib-only and checked-in; optional `honcho` (reasoning recall) and `graphify` (code-graph
relevance) backends plug in via config and degrade gracefully to files. Writes are advisory —
it adds no new hard gate. See [`references/memory.md`](references/memory.md).
```

- [ ] **Step 7: Run the harness to verify it passes**

Run: `python3 evals/run_memory_evals.py`
Expected: PASS for all cases; `14/14 memory eval cases passed`.

- [ ] **Step 8: Verify the retrospective docs-lint in the existing suite still passes**

Run: `python3 evals/run_evals.py`
Expected: `26/26 eval cases passed` (the existing `case_repeated_mistake_retrospective` still finds its required signals in SKILL.md).

- [ ] **Step 9: Commit**

```bash
git add SKILL.md assets/AGENTS.template.md README.md evals/run_memory_evals.py
git commit -m "$(printf 'docs: wire persistent memory into SKILL, AGENTS template, README\n\n🤖 Generated with Claude Code\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 10: CI wiring + full-suite verification + version bump

**Files:**
- Modify: `.github/workflows/evals.yml`
- Modify: `SKILL.md` (frontmatter `metadata.version`)
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: CI that runs the memory harness; a version bump recording the feature.

- [ ] **Step 1: Add the memory harness to CI**

In `.github/workflows/evals.yml`, add a step after the "Run behavioral eval harness" step:

```yaml
      - name: Run memory eval harness
        run: python3 evals/run_memory_evals.py
```

(The existing `python3 -m py_compile scripts/*.py evals/*.py` step already covers the new
module and harness — no change needed there.)

- [ ] **Step 2: Bump the version and changelog**

In `SKILL.md` frontmatter, change `version: "1.3.2"` to `version: "1.4.0"`.

In `CHANGELOG.md`, add a new top entry:

```markdown
## 1.4.0

- Add an optional, advisory **persistent per-project memory** layer: a stdlib-only files
  lessons-store (default, checked-in to `.quality-loop/memory/`) behind a backend-agnostic
  `memory-recall` / `memory-commit` / `memory-prune` / `memory-status` CLI.
- Document two optional loop-integrated backends: `honcho` (reasoning-based lessons recall)
  and `graphify` (code-graph relevance), selectable via the config `memory` block, degrading
  gracefully to the files backend.
- Memory is retrieval-not-stuffing: only a <=40-line `MEMORY.md` index auto-loads; recall is
  budget-capped and relevance-scoped. Writes are advisory (no new hard gate).
- New offline eval harness `evals/run_memory_evals.py` pins recall determinism/budget, commit
  distillation, prune, config validation, and docs presence; wired into CI.
```

- [ ] **Step 3: Run the entire proof suite end to end**

Run:
```bash
python3 -m py_compile scripts/*.py evals/*.py
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json
python3 evals/run_evals.py
python3 evals/run_memory_evals.py
```
Expected, in order: clean compile; `config ok`; `9/9 eval cases passed`; `26/26 eval cases passed`; `14/14 memory eval cases passed`.

- [ ] **Step 4: End-to-end smoke test (recall what was committed)**

Run (in a throwaway temp dir to avoid touching the repo's seed store):
```bash
tmp=$(mktemp -d); cd "$tmp"
python3 /Users/zainzafar/workspace/coding-quality-loop/scripts/quality_loop.py memory-commit /dev/stdin <<'JSON'
{"task_id":"smoke","goal":"fix payment retry double charge","risk_tier":"high","harness_update":"retries must be idempotent","repeated_failure":true,"repo_map":{"likely_files":["src/payments/charge.py"]}}
JSON
python3 /Users/zainzafar/workspace/coding-quality-loop/scripts/quality_loop.py memory-recall --goal "payment retry" --files src/payments/charge.py --risk high
cd - && rm -rf "$tmp"
```
Expected: commit prints `committed 1 lesson(s)`; recall prints a line containing `retries must be idempotent`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/evals.yml SKILL.md CHANGELOG.md
git commit -m "$(printf 'chore: run memory evals in CI; bump to 1.4.0\n\n🤖 Generated with Claude Code\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 11: Self-review against the spec + open PR

**Files:** none (review + integration).

- [ ] **Step 1: Re-read the spec's success criteria and confirm each**

Open `docs/superpowers/specs/2026-06-27-per-project-memory-design.md` §16 and verify:
- zero new runtime deps (grep the new module for non-stdlib imports — there are none);
- a lesson committed in one invocation is recalled in the next (Task 10 Step 4 proves it);
- switching `lessons_store` / `graph_relevance` in config changes behavior without editing
  `SKILL.md` or eval cases (the contract is config-driven; confirm by inspection);
- `MEMORY.md` stays <=40 lines and recall respects its budget (cases in Tasks 4 and 3).

- [ ] **Step 2: Confirm the whole branch is green**

Run:
```bash
python3 -m py_compile scripts/*.py evals/*.py && \
python3 scripts/quality_loop.py check-config assets/quality-loop.config.example.json && \
python3 scripts/quality_loop.py eval-cases evals/cases --config assets/quality-loop.config.example.json && \
python3 evals/run_evals.py && \
python3 evals/run_memory_evals.py
```
Expected: all suites pass; overall exit 0.

- [ ] **Step 3: Open the PR**

```bash
git push -u origin feat/per-project-memory
gh pr create --title "Persistent per-project memory (files core + Honcho/Graphify backends)" --body "$(cat <<'EOF'
Adds an optional, advisory persistent per-project memory layer to the Coding Quality Loop.

- Stdlib-only files lessons-store (default, checked-in to `.quality-loop/memory/`) behind a
  backend-agnostic `memory-recall` / `memory-commit` / `memory-prune` / `memory-status` CLI.
- Two optional loop-integrated backends documented in `references/`: Honcho (reasoning recall)
  and Graphify (code-graph relevance), selected via the config `memory` block, degrading to files.
- Retrieval-not-stuffing: only a <=40-line `MEMORY.md` index auto-loads; recall is budget-capped.
- New offline harness `evals/run_memory_evals.py` (14 cases) wired into CI; existing 9/9 + 26/26 stay green.

Design: `docs/superpowers/specs/2026-06-27-per-project-memory-design.md`
Plan: `docs/superpowers/plans/2026-06-27-per-project-memory.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Report the PR URL and the final suite counts to the user.**

---

## Self-Review (plan author)

**Spec coverage:** §4 architecture → Tasks 1,4–8; §5 store/schema → Tasks 1,2; §6 CLI → Tasks 4–7; §7 backends → Task 8; §8 lifecycle wiring → Task 9; §9 config → Task 7; §10 anti-bloat (≤40-line index, budget) → Tasks 3,4; §11 portability (CLI-over-dir) → inherent in module design; §12 files-touched → all tasks; §13 evals → Tasks 1–9 + Task 10 CI; §16 success criteria → Task 11. No uncovered requirement.

**Placeholder scan:** every code/test step contains complete code; no TBD/TODO/"similar to". JSON-edit steps name the exact anchor key and warn about commas.

**Type/name consistency:** module functions referenced in later tasks (`recall`, `format_digest`, `write_index`, `bump_hits`, `distill_record`, `prune`, `validate_memory_config`, `cmd_recall/commit/prune/status`, `save_lessons`, `load_lessons`, `normalize_lesson`, `append_lesson`) are each defined once and used with matching signatures. `quality_loop_memory` is imported as `qlmem` in `quality_loop.py` and as `mem` in the harness — consistent within each file.
