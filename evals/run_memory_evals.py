#!/usr/bin/env python3
"""Behavioral + function-level eval harness for the memory subsystem.

Mirrors evals/run_evals.py: drives the real CLI via subprocess in a tempdir
and asserts on stdlib module functions. Dependency-free; CI-friendly.

Run: python evals/run_memory_evals.py   (exits non-zero if any case fails)
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date as _date
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


class _sandbox:
    """chdir into tmp and point HOME at it so module-level cmd_* calls resolve
    both the project and the global store inside the tempdir."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp

    def __enter__(self) -> Path:
        self.cwd = os.getcwd()
        self.home = os.environ.get("HOME")
        os.chdir(self.tmp)
        os.environ["HOME"] = str(self.tmp)
        return self.tmp

    def __exit__(self, *exc: object) -> None:
        os.chdir(self.cwd)
        if self.home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.home


def _recall_ns(**overrides: object) -> Namespace:
    base: dict[str, object] = dict(
        goal="", files="", risk="low", budget=None,
        location="checked_in", json=False, bump=False,
    )
    base.update(overrides)
    return Namespace(**base)


def _commit_ns(**overrides: object) -> Namespace:
    base: dict[str, object] = dict(
        record=None, lesson=None, kind="gotcha", scope=None,
        location="checked_in", global_store=False, outcome=None, note="",
    )
    base.update(overrides)
    return Namespace(**base)


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


def case_schema_and_seed_valid(tmp: Path) -> tuple[bool, str]:
    schema = json.loads((ROOT / "assets" / "lesson.schema.json").read_text())
    seed = mem.load_lessons(ROOT / ".quality-loop" / "memory")
    ok = schema.get("type") == "object" and "lesson" in schema.get("properties", {}) and seed == []
    return ok, f"schema_type={schema.get('type')}; seed_count={len(seed)}"


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


def case_cli_recall_readonly_default(tmp: Path) -> tuple[bool, str]:
    """v6: recall is READ-ONLY by default — no hit bump, no lessons.jsonl or
    MEMORY.md rewrite. The working tree stays byte-identical."""
    mem_dir = tmp / ".quality-loop" / "memory"
    _seed(mem_dir)
    before = (mem_dir / "lessons.jsonl").read_bytes()
    code, out, err = run_cli(
        "memory-recall", "--goal", "payment retry", "--files", "src/payments/charge.py",
        "--risk", "high", "--budget", "1500", cwd=str(tmp),
    )
    after = (mem_dir / "lessons.jsonl").read_bytes()
    digest_ok = code == 0 and "Payment retries" in out
    byte_identical = before == after and not (mem_dir / "MEMORY.md").exists()
    hits_zero = all(l["hits"] == 0 for l in mem.load_lessons(mem_dir))
    ok = digest_ok and byte_identical and hits_zero
    return ok, f"code={code}; byte_identical={byte_identical}; hits_zero={hits_zero}; err={err.strip()!r}"


def case_recall_bump_flag(tmp: Path) -> tuple[bool, str]:
    """--bump (the RETROSPECT-time opt-in) restores the hit-count + index write."""
    mem_dir = tmp / ".quality-loop" / "memory"
    _seed(mem_dir)
    with _sandbox(tmp):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mem.cmd_recall(_recall_ns(
                goal="payment retry", files="src/payments/charge.py",
                risk="high", budget=1500, bump=True,
            ))
    payment = next((l for l in mem.load_lessons(mem_dir) if l["lesson"].startswith("Payment retries")), None)
    bumped = payment is not None and payment["hits"] == 1
    index_ok = (mem_dir / "MEMORY.md").is_file()
    ok = rc == 0 and bumped and index_ok and "Payment retries" in buf.getvalue()
    return ok, f"rc={rc}; bumped={bumped}; index_written={index_ok}"


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
    ok = len(rows) == 3 and has_failure and {"failure_mode", "preference", "gotcha"} <= kinds and scoped
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
    # cap test — genuinely distinct lessons (must NOT dedup at 0.92)
    distinct = [
        "always validate input", "use db transactions", "retry with backoff",
        "log correlation ids", "handle timeouts explicitly",
        "prefer immutable data", "avoid god objects", "test edge cases",
        "document public apis", "sanitize user input",
    ]
    many = [mem.normalize_lesson({"lesson": s, "kind": "gotcha"}, "2026-06-27") for s in distinct]
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


def case_cli_status(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    mem.append_lesson(mem_dir, mem.normalize_lesson({"lesson": "be careful here", "kind": "gotcha"}, "2026-06-27"))
    code, out, err = run_cli("memory-status", cwd=str(tmp))
    data = json.loads(out) if code == 0 else {}
    ok = code == 0 and data.get("lesson_count") == 1 and "memory_dir" in data
    return ok, f"code={code}; out={out.strip()!r}; err={err.strip()!r}"


def case_check_config_validates_memory_block(tmp: Path) -> tuple[bool, str]:
    good = mem.validate_memory_config(
        {"lessons_store": "files", "location": "checked_in", "recall_budget_chars": 1500}
    )
    bad = mem.validate_memory_config(
        {"lessons_store": "redis", "location": "cloud", "recall_budget_chars": 0}
    )
    # the shipped example config must validate via the CLI
    code, out, err = run_cli("check-config", str(ROOT / "assets" / "quality-loop.config.example.json"))
    ok = good == [] and len(bad) == 3 and code == 0
    return ok, f"good={good}; bad={bad}; check_config_exit={code}; err={err.strip()!r}"


def case_reference_modules_present(tmp: Path) -> tuple[bool, str]:
    docs = {
        "memory.md": ["recall", "commit", "prune", "lessons_store", "anti-bloat"],
    }
    missing: list[str] = []
    for fname, terms in docs.items():
        path = ROOT / "references" / fname
        text = path.read_text().lower() if path.exists() else ""
        for term in terms:
            if term.lower() not in text:
                missing.append(f"{fname}:{term}")
    return (not missing), (f"missing={missing}" if missing else "all reference modules present")


def case_skill_documents_memory(tmp: Path) -> tuple[bool, str]:
    text = (ROOT / "SKILL.md").read_text().lower()
    must_have = ["persistent project memory", "memory-recall", "memory-commit", "references/memory.md"]
    missing = [m for m in must_have if m not in text]
    return (not missing), (f"missing={missing}" if missing else "SKILL.md documents memory")


def case_index_caps_multiline_lessons(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    rows = [
        mem.normalize_lesson(
            {"lesson": f"line one\nline two\nline three of lesson {i}", "kind": "gotcha"},
            "2026-06-27",
        )
        for i in range(36)
    ]
    mem.write_index(mem_dir, rows)
    lines = (mem_dir / "MEMORY.md").read_text().splitlines()
    single = all("\n" not in r["lesson"] for r in rows)
    ok = len(lines) <= 40 and single
    return ok, f"index_lines={len(lines)}; single_line_lessons={single}"


def case_secrets_redacted_on_commit(tmp: Path) -> tuple[bool, str]:
    rec = {
        "task_id": "s1", "goal": "rotate key", "risk_tier": "high",
        "harness_update": "rotated leaked AWS key AKIAIOSFODNN7EXAMPLE in the deploy script",
        "repo_map": {"likely_files": ["deploy/run.sh"]},
    }
    p = tmp / "rec.json"
    p.write_text(json.dumps(rec))
    code, out, err = run_cli("memory-commit", str(p), cwd=str(tmp))
    body = (tmp / ".quality-loop" / "memory" / "lessons.jsonl").read_text()
    idx = (tmp / ".quality-loop" / "memory" / "MEMORY.md").read_text()
    ok = (
        code == 0
        and "AKIAIOSFODNN7EXAMPLE" not in body
        and "AKIAIOSFODNN7EXAMPLE" not in idx
        and "[REDACTED]" in body
    )
    return ok, f"code={code}; secret_in_store={'AKIAIOSFODNN7EXAMPLE' in body}; err={err.strip()!r}"


def case_recall_path_only_and_keyword_only(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    mem.append_lesson(mem_dir, mem.normalize_lesson(
        {"lesson": "the deploy script needs a rollback step", "kind": "gotcha",
         "risk_tier": "low", "scope_globs": ["deploy/**"], "keywords": []}, "2026-06-27"))
    mem.append_lesson(mem_dir, mem.normalize_lesson(
        {"lesson": "throttle the webhook sender", "kind": "convention",
         "risk_tier": "low", "scope_globs": ["svc/**"], "keywords": ["webhook", "throttle"]}, "2026-06-27"))
    lessons = mem.load_lessons(mem_dir)
    path_only = mem.recall(lessons, "unrelated words entirely", ["deploy/run.sh"], "low", 1500)
    kw_only = mem.recall(lessons, "fix the webhook throttle", ["x/y.py"], "low", 1500)
    ok = (
        len(path_only) == 1 and "rollback step" in path_only[0]["lesson"]
        and len(kw_only) == 1 and "webhook sender" in kw_only[0]["lesson"]
    )
    return ok, f"path_only={[l['lesson'] for l in path_only]}; kw_only={[l['lesson'] for l in kw_only]}"


def case_recall_no_bump(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    mem.append_lesson(mem_dir, mem.normalize_lesson(
        {"lesson": "payment retries must be idempotent", "kind": "failure_mode",
         "risk_tier": "high", "scope_globs": ["src/payments/**"], "keywords": ["retry", "idempotent"]}, "2026-06-27"))
    idx_before = (mem_dir / "MEMORY.md").read_text() if (mem_dir / "MEMORY.md").is_file() else ""
    code, out, err = run_cli(
        "memory-recall", "--goal", "payment retry", "--files", "src/payments/charge.py",
        "--risk", "high", "--no-bump", cwd=str(tmp))
    hits = [l["hits"] for l in mem.load_lessons(mem_dir)]
    idx_after = (mem_dir / "MEMORY.md").read_text() if (mem_dir / "MEMORY.md").is_file() else ""
    ok = code == 0 and hits == [0] and idx_before == idx_after
    return ok, f"code={code}; hits={hits}; index_unchanged={idx_before == idx_after}"


def case_openai_hyphenated_key_redacted(tmp: Path) -> tuple[bool, str]:
    """Regression pin for the review finding: sk-live-<hex> / sk-proj-<hex>
    OpenAI-style keys must not leak into the lessons store OR into the keyword
    tokenizer. This case previously failed on main and shipped a raw key."""
    rec = {
        "task_id": "s2", "goal": "add API key redaction pin", "risk_tier": "medium",
        "harness_update": "The API key sk-live-abcd1234567890abcdef1234567890 must never appear",
        "repo_map": {"likely_files": ["src/config.py"]},
    }
    p = tmp / "rec.json"
    p.write_text(json.dumps(rec))
    code, out, err = run_cli("memory-commit", str(p), cwd=str(tmp))
    body = (tmp / ".quality-loop" / "memory" / "lessons.jsonl").read_text()
    idx = (tmp / ".quality-loop" / "memory" / "MEMORY.md").read_text()
    # Both the raw prefix and the naked hex payload must be gone (keywords used
    # to tokenize the hex fragment even after the lesson text was scrubbed).
    ok = (
        code == 0
        and "sk-live-abcd" not in body and "sk-live-abcd" not in idx
        and "abcd1234567890abcdef1234567890" not in body
        and "abcd1234567890abcdef1234567890" not in idx
        and "[REDACTED]" in body
    )
    return ok, f"code={code}; keyword_leak={'abcd1234567890abcdef1234567890' in body}"


def case_openai_proj_and_test_keys_redacted(tmp: Path) -> tuple[bool, str]:
    """sk-proj-* and sk-test-* variants must be redacted the same way."""
    from quality_loop import redact  # noqa: E402
    proj = "sk-proj-QjP3K9vLmN2xR8fH4tYaB5cD7eG1jK0iL9M6oP2qS4uV"
    test = "sk-test-1234567890abcdefABCDEF_-9876"
    r1 = redact(f"leaked {proj} into a log")
    r2 = redact(f"see {test} in the fixture")
    ok = proj not in r1 and test not in r2 and "[REDACTED]" in r1 and "[REDACTED]" in r2
    return ok, f"r1={r1!r}; r2={r2!r}"


def case_entropy_redaction_catches_obfuscated_secret(tmp: Path) -> tuple[bool, str]:
    """The secondary entropy pass catches long, high-entropy tokens that no
    regex covers, while leaving prose / git SHAs / UUIDs / file paths alone."""
    from quality_loop import redact  # noqa: E402
    obfuscated = "aGVsbG9fdGhpc19pc19hX2Jhc2U2NF9zZWNyZXRfa2V5X3Rva2Vu"  # base64-ish
    sha = "3a4f8e9b12c56d78e0f1a2b3c4d5e6f708192a3b"
    uuid = "01234567-89ab-cdef-0123-456789abcdef"
    path = "python3 scripts/quality_loop.py verify-gates agent-record.json"
    prose = "the rounder rounds ties to even using stdlib decimal"
    r_obf = redact(f"key: {obfuscated}")
    r_sha = redact(f"commit {sha} is fine")
    r_uuid = redact(f"session {uuid} is fine")
    r_path = redact(path)
    r_prose = redact(prose)
    ok = (
        obfuscated not in r_obf and "[REDACTED]" in r_obf
        and sha in r_sha and uuid in r_uuid
        and r_path == path and r_prose == prose
    )
    return ok, f"obf_redacted={obfuscated not in r_obf}; sha_kept={sha in r_sha}; uuid_kept={uuid in r_uuid}; path_kept={r_path == path}; prose_kept={r_prose == prose}"


def case_budget_clamped(tmp: Path) -> tuple[bool, str]:
    mem_dir = tmp / ".quality-loop" / "memory"
    mem.append_lesson(mem_dir, mem.normalize_lesson(
        {"lesson": "some payment lesson here", "kind": "gotcha",
         "risk_tier": "low", "scope_globs": ["src/**"], "keywords": ["payment"]}, "2026-06-27"))
    code, out, err = run_cli(
        "memory-recall", "--goal", "payment", "--files", "src/x.py",
        "--risk", "low", "--budget", "0", cwd=str(tmp))
    ok = code == 0 and out.strip() != ""
    return ok, f"code={code}; out={out.strip()!r}"


def case_global_commit_and_recall(tmp: Path) -> tuple[bool, str]:
    import os
    env = {**os.environ, "HOME": str(tmp)}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "memory-commit", "--lesson",
         "always read migration guides before schema edits", "--kind", "convention", "--global"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp), env=env, check=False,
    )
    code, out, err = proc.returncode, proc.stdout, proc.stderr
    global_dir = tmp / ".quality-loop" / "global"
    global_lessons = mem.load_lessons(global_dir)
    commit_ok = code == 0 and len(global_lessons) == 1 and "migration guides" in global_lessons[0].get("lesson", "")

    project_dir = tmp / ".quality-loop" / "memory"
    mem.append_lesson(project_dir, mem.normalize_lesson(
        {"lesson": "payment retries must be idempotent", "kind": "failure_mode",
         "risk_tier": "high", "scope_globs": ["src/payments/**"], "keywords": ["retry", "idempotent"]}, "2026-06-27"))

    proc2 = subprocess.run(
        [sys.executable, str(SCRIPT), "memory-recall", "--goal", "migration schema retry",
         "--files", "src/payments/charge.py", "--risk", "high", "--budget", "1500", "--no-bump"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp), env=env, check=False,
    )
    code2, out2, err2 = proc2.returncode, proc2.stdout, proc2.stderr
    recall_ok = code2 == 0 and "migration guides" in out2 and "idempotent" in out2 and "[global]" in out2
    return commit_ok and recall_ok, f"commit_code={code}; recall_code={code2}; out={out2.strip()!r}"


def case_global_status_reports(tmp: Path) -> tuple[bool, str]:
    import os
    env = {**os.environ, "HOME": str(tmp)}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "memory-status"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp), env=env, check=False,
    )
    code, out, err = proc.returncode, proc.stdout, proc.stderr
    ok = False
    try:
        data = json.loads(out)
        ok = code == 0 and "global_dir" in data and "global_lesson_count" in data and str(tmp) in data.get("global_dir", "")
    except json.JSONDecodeError:
        ok = False
    return ok, f"exit={code}; has_global_fields={ok}"


def case_one_pool_no_reserved_quota(tmp: Path) -> tuple[bool, str]:
    """v6: ONE ranked pool under ONE budget. Non-matching global lessons no
    longer shrink project recall (the old 60/40 split reserved 40% for global),
    a matching global lesson competes into the same pool with the [global]
    prefix, and an empty global store leaves recall() behavior unchanged."""
    env = {**os.environ, "HOME": str(tmp)}
    project_dir = tmp / ".quality-loop" / "memory"
    for i in range(4):
        mem.append_lesson(project_dir, mem.normalize_lesson(
            {"lesson": f"project convention {i}: validate payment input first",
             "kind": "convention", "risk_tier": "low",
             "scope_globs": ["src/payments/**"], "keywords": ["payment", "validate"]}, "2026-06-27"))
    args = ["memory-recall", "--goal", "payment validate", "--files", "src/payments/x.py",
            "--risk", "low", "--budget", "600"]

    def run() -> tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(tmp), env=env, check=False,
        )
        return proc.returncode, proc.stdout

    code1, out_no_global = run()
    global_dir = tmp / ".quality-loop" / "global"
    mem.append_lesson(global_dir, mem.normalize_lesson(
        {"lesson": "unrelated global advice about kubernetes ingress annotations",
         "kind": "convention", "risk_tier": "low",
         "scope_globs": ["**"], "keywords": ["kubernetes", "ingress"]}, "2026-06-27"))
    code2, out_nonmatching = run()
    unshrunk = code1 == 0 and code2 == 0 and out_no_global == out_nonmatching and "[global]" not in out_nonmatching
    mem.append_lesson(global_dir, mem.normalize_lesson(
        {"lesson": "global rule: validate payment input twice",
         "kind": "convention", "risk_tier": "low",
         "scope_globs": ["**"], "keywords": ["payment", "validate"]}, "2026-06-27"))
    code3, out_merged = run()
    merged = code3 == 0 and "[global]" in out_merged and "validate payment input twice" in out_merged
    lessons = mem.load_lessons(project_dir)
    ids_pool = [l["id"] for l, _ in mem.recall_pool(lessons, [], "payment validate", ["src/payments/x.py"], "low", 600)]
    ids_recall = [l["id"] for l in mem.recall(lessons, "payment validate", ["src/payments/x.py"], "low", 600)]
    ok = unshrunk and merged and ids_pool == ids_recall and len(ids_pool) >= 1
    return ok, f"unshrunk={unshrunk}; merged={merged}; empty_global_unchanged={ids_pool == ids_recall}"


def case_global_commit_redacts_secrets(tmp: Path) -> tuple[bool, str]:
    import os
    env = {**os.environ, "HOME": str(tmp)}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "memory-commit", "--lesson",
         "use api key AKIAIOSFODNN7EXAMPLE for deploys", "--kind", "convention", "--global"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp), env=env, check=False,
    )
    code, out, err = proc.returncode, proc.stdout, proc.stderr
    body = (tmp / ".quality-loop" / "global" / "lessons.jsonl").read_text()
    ok = code == 0 and "AKIAIOSFODNN7EXAMPLE" not in body and "[REDACTED]" in body
    return ok, f"code={code}; secret_in_store={'AKIAIOSFODNN7EXAMPLE' in body}; err={err.strip()!r}"


def case_recall_scoring_floor(tmp: Path) -> tuple[bool, str]:
    """v6 relevance floor: a single shared token no longer recalls (>=2 token
    overlap OR a scope_glob match required), and generic words like 'tests'
    are stoplisted — 'fix failing tests' recalls nothing from a lesson that
    merely mentions tests once."""
    mem_dir = tmp / ".quality-loop" / "memory"
    mem.append_lesson(mem_dir, mem.normalize_lesson(
        {"lesson": "quarantine flaky integration tests before merging", "kind": "gotcha",
         "risk_tier": "low", "scope_globs": ["ci/**"], "keywords": ["tests"]}, "2026-06-27"))
    mem.append_lesson(mem_dir, mem.normalize_lesson(
        {"lesson": "throttle the webhook sender on retries", "kind": "convention",
         "risk_tier": "low", "scope_globs": ["svc/**"], "keywords": ["webhook", "throttle"]}, "2026-06-27"))
    lessons = mem.load_lessons(mem_dir)
    stoplisted = mem.recall(lessons, "fix failing tests", ["src/app.py"], "low", 1500)
    single_overlap = mem.recall(lessons, "debug the webhook problem", ["src/app.py"], "low", 1500)
    two_tokens = mem.recall(lessons, "debug the webhook throttle", ["src/app.py"], "low", 1500)
    path_only = mem.recall(lessons, "unrelated wording entirely", ["ci/pipeline.yml"], "low", 1500)
    ok = (
        stoplisted == [] and single_overlap == []
        and len(two_tokens) == 1 and "webhook sender" in two_tokens[0]["lesson"]
        and len(path_only) == 1 and "integration tests" in path_only[0]["lesson"]
    )
    return ok, (
        f"stoplisted={len(stoplisted)}; single_overlap={len(single_overlap)}; "
        f"two_tokens={len(two_tokens)}; path_only={len(path_only)}"
    )


def case_outcome_commit_and_brief_lines(tmp: Path) -> tuple[bool, str]:
    """memory-commit --outcome writes a kind=outcome row with provenance,
    rejects unknown outcomes, and outcome_lines renders the newest row as
    'last shipped: <outcome> — <note>' for the session brief. Outcome rows are
    shipped-status feedback, never recallable advice."""
    with _sandbox(tmp):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc1 = mem.cmd_commit(_commit_ns(outcome="reverted", note="rolled back after prod 500s"))
            rc_bad = mem.cmd_commit(_commit_ns(outcome="exploded", note="nope"))
            rc2 = mem.cmd_commit(_commit_ns(outcome="clean", note="shipped with green gates"))
    rows = mem.load_lessons(tmp / ".quality-loop" / "memory")
    outc = [r for r in rows if r.get("kind") == "outcome"]
    reverted = next((r for r in outc if r.get("outcome") == "reverted"), None)
    prov = (
        reverted is not None
        and isinstance(reverted.get("source"), dict)
        and reverted["source"].get("task_id") == "manual"
    )
    lines = mem.outcome_lines(rows)
    line_ok = (
        len(lines) == 2
        and lines[0] == "last shipped: clean — shipped with green gates"
        and lines[1].startswith("prior: reverted — rolled back")
    )
    not_recalled = mem.recall(rows, "rolled back after prod 500s green gates", [], "low", 1500) == []
    ok = rc1 == 0 and rc2 == 0 and rc_bad == 1 and len(outc) == 2 and prov and line_ok and not_recalled
    return ok, (
        f"rcs=({rc1},{rc_bad},{rc2}); outcome_rows={len(outc)}; provenance={prov}; "
        f"lines={lines}; not_recalled={not_recalled}"
    )


def case_provenance_and_unattributed_marker(tmp: Path) -> tuple[bool, str]:
    """Rows written by memory-commit carry source {task_id, git_author?};
    recall output marks rows lacking provenance as [unattributed] and leaves
    attributed rows unmarked."""
    mem_dir = tmp / ".quality-loop" / "memory"
    mem.append_lesson(mem_dir, mem.normalize_lesson(
        {"lesson": "legacy payment lesson on idempotent retries", "kind": "gotcha",
         "risk_tier": "low", "scope_globs": ["src/payments/**"], "keywords": ["payment", "retries"]},
        "2026-06-01"))
    rec = {
        "task_id": "t-9", "goal": "harden retries", "risk_tier": "low",
        "harness_update": "guard payment retries with idempotency keys",
        "repo_map": {"likely_files": ["src/payments/charge.py"]},
    }
    p = tmp / "rec.json"
    p.write_text(json.dumps(rec))
    code, out, err = run_cli("memory-commit", str(p), cwd=str(tmp))
    rows = mem.load_lessons(mem_dir)
    committed = next((r for r in rows if "idempotency keys" in r.get("lesson", "")), None)
    prov_ok = committed is not None and committed.get("source", {}).get("task_id") == "t-9"
    code2, out2, err2 = run_cli(
        "memory-recall", "--goal", "payment retries idempotency",
        "--files", "src/payments/charge.py", cwd=str(tmp),
    )
    legacy_lines = [ln for ln in out2.splitlines() if "legacy payment" in ln]
    committed_lines = [ln for ln in out2.splitlines() if "idempotency keys" in ln]
    marked = bool(legacy_lines) and "[unattributed]" in legacy_lines[0]
    unmarked = bool(committed_lines) and "[unattributed]" not in committed_lines[0]
    ok = code == 0 and code2 == 0 and prov_ok and marked and unmarked
    return ok, f"commit={code}; provenance={prov_ok}; legacy_marked={marked}; committed_unmarked={unmarked}"


def case_prune_flags_stale_candidates(tmp: Path) -> tuple[bool, str]:
    """memory-prune prints (never deletes) lessons whose scope_globs match zero
    files in the current tree as stale candidates."""
    mem_dir = tmp / ".quality-loop" / "memory"
    (tmp / "keep").mkdir()
    (tmp / "keep" / "x.py").write_text("pass\n")
    mem.append_lesson(mem_dir, mem.normalize_lesson(
        {"lesson": "stale scope lesson about the old payments dir", "kind": "gotcha",
         "risk_tier": "low", "scope_globs": ["src/payments/**"], "created": "2026-07-01"}, "2026-07-01"))
    mem.append_lesson(mem_dir, mem.normalize_lesson(
        {"lesson": "live scope note for the keep module", "kind": "convention",
         "risk_tier": "low", "scope_globs": ["keep/**"], "created": "2026-07-01"}, "2026-07-01"))
    code, out, err = run_cli("memory-prune", cwd=str(tmp))
    remaining = mem.load_lessons(mem_dir)
    stale_lines = [ln for ln in out.splitlines() if "stale candidate" in ln]
    flagged = any("old payments dir" in ln for ln in stale_lines)
    live_not_flagged = not any("keep module" in ln for ln in stale_lines)
    ok = code == 0 and len(remaining) == 2 and flagged and live_not_flagged
    return ok, (
        f"code={code}; remaining={len(remaining)}; flagged={flagged}; "
        f"live_not_flagged={live_not_flagged}; out={out.strip()!r}"
    )


def case_recall_budget_from_config(tmp: Path) -> tuple[bool, str]:
    """memory.recall_budget_chars supplies the recall budget when --budget is
    not passed; an explicit --budget (module or CLI) always wins."""
    mem_dir = tmp / ".quality-loop" / "memory"
    for i in range(4):
        mem.append_lesson(mem_dir, mem.normalize_lesson(
            {"lesson": f"payment validation lesson number {i} with plenty of padding text",
             "kind": "convention", "risk_tier": "low",
             "scope_globs": ["src/payments/**"], "keywords": ["payment", "validation"]}, "2026-06-27"))
    config = tmp / "quality-loop.config.json"
    ns = dict(goal="payment validation", files="src/payments/x.py", risk="low")

    def lines_for(budget: object) -> tuple[int, int]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mem.cmd_recall(_recall_ns(budget=budget, **ns))
        return rc, len(buf.getvalue().strip().splitlines())

    with _sandbox(tmp):
        config.write_text(json.dumps({"memory": {"recall_budget_chars": 80}}))
        rc1, small = lines_for(None)
        config.write_text(json.dumps({"memory": {"recall_budget_chars": 5000}}))
        rc2, large = lines_for(None)
        rc3, flag_wins = lines_for(80)
    code4, out4, _ = run_cli(
        "memory-recall", "--goal", "payment validation", "--files", "src/payments/x.py",
        "--budget", "80", cwd=str(tmp),
    )
    cli_flag_wins = code4 == 0 and len(out4.strip().splitlines()) == 1
    ok = rc1 == rc2 == rc3 == 0 and small == 1 and large == 4 and flag_wins == 1 and cli_flag_wins
    return ok, (
        f"config80_lines={small}; config5000_lines={large}; "
        f"module_flag_lines={flag_wins}; cli_flag_wins={cli_flag_wins}"
    )


def case_config_location_end_to_end(tmp: Path) -> tuple[bool, str]:
    """memory.location: "local" in the root config routes every documented
    memory command — commit, recall, status — and init-record's preview to the
    machine-local store with NO --location flag, and the checked-in store is
    never created. Round-2 review (2026-07-23) caught the half-wiring this
    pins: only init-record's preview honored the config, so configured-local
    repos committed lessons to a store recall never read. An explicit
    --location still wins over the config."""
    with _sandbox(tmp) as root:
        (root / "quality-loop.config.json").write_text(
            json.dumps({"memory": {"location": "local"}}), encoding="utf-8"
        )
        lesson = "Half-cent rounding fixes must replay red-green on the shared rounding path"
        code_c, _, err_c = run_cli("memory-commit", "--lesson", lesson, "--kind", "gotcha")
        local_store = (
            Path(os.environ["HOME"]) / ".quality-loop"
            / mem.slugify(str(root.resolve())) / "lessons.jsonl"
        )
        checked_in = root / ".quality-loop" / "memory" / "lessons.jsonl"
        committed_local = code_c == 0 and local_store.is_file() and not checked_in.exists()

        code_s, out_s, _ = run_cli("memory-status")
        try:
            status = json.loads(out_s)
        except json.JSONDecodeError:
            status = {}
        status_local = code_s == 0 and status.get("location") == "local" and status.get("lesson_count") == 1

        code_r, out_r, _ = run_cli(
            "memory-recall", "--goal", "fix half-cent rounding on the shared rounding path"
        )
        recalled = code_r == 0 and "Half-cent rounding fixes" in out_r

        code_i, out_i, _ = run_cli(
            "init-record", "--goal",
            "Fix half-cent rounding in totals on the shared rounding path",
            "--risk-tier", "low",
        )
        preview = code_i == 0 and "Half-cent rounding fixes" in out_i

        # brief reads the configured local store too: the record init-record
        # just created carries the half-cent goal, so its lessons section must
        # recall the local lesson — and an explicit checked_in override on
        # brief must not see it (round-3 review: every rewired entry point
        # needs its own pin).
        code_b, out_b, _ = run_cli("brief", "--cwd", str(root))
        brief_local = code_b == 0 and "Half-cent rounding fixes" in out_b
        code_bo, out_bo, _ = run_cli("brief", "--cwd", str(root), "--location", "checked_in")
        brief_override = code_bo == 0 and "Half-cent rounding fixes" not in out_bo

        # memory-prune (no flag) must mutate only the configured local store:
        # the lesson survives the prune there and the checked-in store is
        # still never created.
        code_p, _, _ = run_cli("memory-prune")
        pruned_local = (
            code_p == 0 and local_store.is_file()
            and "Half-cent rounding fixes" in local_store.read_text(encoding="utf-8")
            and (local_store.parent / "MEMORY.md").is_file()
            and not checked_in.exists()
        )

        # Explicit flag still wins: checked_in recall must NOT see the lesson.
        code_e, out_e, _ = run_cli(
            "memory-recall", "--goal",
            "fix half-cent rounding on the shared rounding path",
            "--location", "checked_in",
        )
        override_wins = code_e == 0 and "Half-cent rounding fixes" not in out_e
    ok = (committed_local and status_local and recalled and preview
          and brief_local and brief_override and pruned_local and override_wins)
    return ok, (
        f"committed_local={committed_local}; status_local={status_local}; recalled={recalled}; "
        f"preview={preview}; brief_local={brief_local}; brief_override={brief_override}; "
        f"pruned_local={pruned_local}; override_wins={override_wins}; commit_err={err_c.strip()[:80]!r}"
    )


CASES = [
    ("slugify + resolve_memory_dir compute correct paths", case_slugify_and_resolve),
    ("lesson append/load round-trips and skips malformed lines", case_lesson_io_roundtrip),
    ("lesson.schema.json is valid and the seed store loads empty", case_schema_and_seed_valid),
    ("recall ranks by relevance, is deterministic, drops non-matches", case_recall_ranks_and_is_deterministic),
    ("recall + digest respect the hard char budget", case_recall_respects_budget),
    ("memory-recall is read-only by default: working tree stays byte-identical", case_cli_recall_readonly_default),
    ("memory-recall --bump (RETROSPECT opt-in) bumps hits and rewrites the index", case_recall_bump_flag),
    ("distill_record turns a record into scoped, kind-tagged lessons", case_distill_record),
    ("memory-commit writes lessons and is idempotent (dedup by id)", case_cli_commit_writes_and_dedups),
    ("prune dedups near-duplicates, ages out 0-hit stale, and caps", case_prune_dedups_ages_and_caps),
    ("memory-prune collapses duplicates on disk", case_cli_prune),
    ("memory-status reports the store location and counts", case_cli_status),
    ("validate_memory_config + check-config accept/reject the memory block", case_check_config_validates_memory_block),
    ("memory reference modules exist with required content", case_reference_modules_present),
    ("SKILL.md documents the persistent memory step", case_skill_documents_memory),
    ("MEMORY.md stays <=40 lines even with multi-line lesson text", case_index_caps_multiline_lessons),
    ("secrets in a committed record are redacted before persistence", case_secrets_redacted_on_commit),
    ("recall fires on path-only and keyword-only matches (OR contract)", case_recall_path_only_and_keyword_only),
    ("memory-recall --no-bump leaves hits and index unchanged", case_recall_no_bump),
    ("memory-recall clamps a non-positive --budget", case_budget_clamped),
    ("OpenAI hyphenated key (sk-live-*) is redacted from lessons + keywords", case_openai_hyphenated_key_redacted),
    ("sk-proj-* and sk-test-* variants are redacted", case_openai_proj_and_test_keys_redacted),
    ("entropy pass catches obfuscated secrets, spares SHAs/UUIDs/paths/prose", case_entropy_redaction_catches_obfuscated_secret),
    ("global store: --global commits and recall merges project + global", case_global_commit_and_recall),
    ("memory-status reports the global store fields", case_global_status_reports),
    ("one pool: non-matching global lessons no longer shrink project recall", case_one_pool_no_reserved_quota),
    ("global commit redacts secrets before persistence", case_global_commit_redacts_secrets),
    ("scoring floor: >=2 token overlap or scope match required; 'tests' stoplisted", case_recall_scoring_floor),
    ("memory-commit --outcome writes provenance-stamped outcome rows for the brief", case_outcome_commit_and_brief_lines),
    ("provenance: committed rows carry source; recall marks [unattributed]", case_provenance_and_unattributed_marker),
    ("memory-prune flags stale-scope lessons as candidates without deleting", case_prune_flags_stale_candidates),
    ("recall_budget_chars config wired: config default honored, --budget wins", case_recall_budget_from_config),
    ("memory.location config wired end-to-end: commit/recall/status/init-record share the local store", case_config_location_end_to_end),
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
