#!/usr/bin/env python3
"""Offline fixture tests for the control plane (index, server, ingest, shim).

Everything runs against temp repos and a temp CLAUDE_CONFIG_DIR — the suite
never reads the developer's real ~/.claude or writes outside tempdirs. The one
case that starts a real server does so on an ephemeral port bound to
127.0.0.1 and tears it down before returning.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quality_loop_control as ctl  # noqa: E402

SHIM = ROOT / "hosts" / "claude-code" / "control_plane.py"
QL = ROOT / "scripts" / "quality_loop.py"

PASS = "PASS"
FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_repo(tmp: Path, name: str = "repo") -> Path:
    repo = tmp / name
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    # Fixtures pin dates in early 2026; the real retention default (90 days)
    # would prune them as the calendar advances. Pin a huge window here; the
    # retention case writes its own tighter config.
    (repo / "quality-loop.config.json").write_text(
        json.dumps({"version": "x", "control_plane": {"retention_days": 100000}}),
        encoding="utf-8")
    return repo


def claude_dir(tmp: Path, repo: Path) -> Path:
    """A fake CLAUDE_CONFIG_DIR with a projects dir for `repo`."""
    cdir = tmp / "claude-home"
    proj = cdir / "projects" / ctl.project_slug(repo)
    proj.mkdir(parents=True, exist_ok=True)
    os.environ["CLAUDE_CONFIG_DIR"] = str(cdir)
    return proj


def assistant_line(session: str, uuid: str, ts: str, model: str = "test-model-1",
                   inp: int = 100, out: int = 50, cache_read: int = 0,
                   tools: list | None = None, sidechain: bool = False,
                   agent: str | None = None, msg_id: str | None = None) -> str:
    content = [{"type": "text", "text": "ok"}]
    for tid, tname, tinput in tools or []:
        content.append({"type": "tool_use", "id": tid, "name": tname, "input": tinput})
    line = {
        "type": "assistant", "uuid": uuid, "sessionId": session, "timestamp": ts,
        "cwd": "/tmp/x", "gitBranch": "main", "version": "9.9.9",
        "isSidechain": sidechain,
        "message": {
            # Real hosts write one line PER CONTENT BLOCK, all sharing one
            # message.id and repeating the same usage; msg_id defaults to a
            # per-line id so single-line fixtures behave as one call each.
            "id": msg_id or f"msg-{uuid}",
            "role": "assistant", "model": model, "content": content,
            "usage": {"input_tokens": inp, "output_tokens": out,
                      "cache_read_input_tokens": cache_read,
                      "cache_creation_input_tokens": 0},
        },
    }
    if agent:
        line["agentName"] = agent
    return json.dumps(line)


def user_line(session: str, ts: str, text: str = "", results: list | None = None) -> str:
    content: list = []
    if text:
        content = text  # a plain-string prompt, like real first prompts
    elif results is not None:
        content = [{"type": "tool_result", "tool_use_id": tid, "is_error": err, "content": "x"}
                   for tid, err in results]
    return json.dumps({
        "type": "user", "sessionId": session, "timestamp": ts,
        "message": {"role": "user", "content": content},
    })


def write_transcript(proj: Path, session: str, lines: list[str]) -> Path:
    path = proj / f"{session}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def enabled_config(repo: Path, **extra) -> None:
    block = {"enabled": True, "autostart": False, "retention_days": 100000}
    block.update(extra)
    (repo / "quality-loop.config.json").write_text(
        json.dumps({"version": "x", "control_plane": block}), encoding="utf-8")


def get_json(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8") or "{}")


# ---------------------------------------------------------------------------
# Index cases
# ---------------------------------------------------------------------------

def case_db_init_idempotent(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    conn = ctl.open_db(repo)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    ctl.open_db(repo).close()
    gi = ctl.control_dir(repo) / ".gitignore"
    # Untracked-dir collapse makes `porcelain` output vacuous here; ask git
    # directly whether the DB file is ignored.
    ignored = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", str(ctl.db_path(repo))],
        capture_output=True).returncode == 0
    # A cache written by an older schema revision must be rebuilt, not crash
    # with "no such column" on the first index pass after an upgrade.
    import sqlite3 as sq
    conn = sq.connect(str(ctl.db_path(repo)))
    conn.executescript("DROP TABLE file_state; "
                       "CREATE TABLE file_state(path TEXT PRIMARY KEY, offset INTEGER, mtime REAL); "
                       "PRAGMA user_version=1;")
    conn.commit()
    conn.close()
    stats = ctl.index_all(repo)  # would raise OperationalError without the rebuild
    conn = ctl.open_db(repo)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(file_state)")]
    conn.close()
    ok = (mode == "wal" and version == ctl.SCHEMA_VERSION and gi.read_text() == "*\n"
          and ignored and "head_hash" in cols and stats is not None)
    return ok, f"journal={mode}; user_version={version}; ignored={ignored}; rebuilt_cols={cols}"


def case_transcript_tokens_exact(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "s1", [
        user_line("s1", "2026-01-01T10:00:00Z", text="fix the rounding bug in totals"),
        assistant_line("s1", "u1", "2026-01-01T10:00:05Z", inp=111, out=22, cache_read=1000),
        assistant_line("s1", "u2", "2026-01-01T10:01:00Z", inp=200, out=78, cache_read=2000),
        # One API response, three transcript lines (text + tool_use blocks),
        # identical usage on each: must count ONCE, or totals inflate 3x.
        assistant_line("s1", "u3", "2026-01-01T10:02:00Z", inp=50, out=10, msg_id="msg-shared"),
        assistant_line("s1", "u4", "2026-01-01T10:02:01Z", inp=50, out=10, msg_id="msg-shared"),
        assistant_line("s1", "u5", "2026-01-01T10:02:02Z", inp=50, out=10, msg_id="msg-shared"),
    ])
    stats = ctl.index_all(repo)
    conn = ctl.open_db(repo)
    row = conn.execute("SELECT SUM(input_tokens) i, SUM(output_tokens) o, SUM(cache_read_tokens) c, "
                       "COUNT(*) n, MAX(model) m FROM model_calls").fetchone()
    sess = conn.execute("SELECT * FROM sessions WHERE id='s1'").fetchone()
    conn.close()
    ok = (stats["model_calls"] == 3 and row["n"] == 3
          and row["i"] == 361 and row["o"] == 110 and row["c"] == 3000
          and row["m"] == "test-model-1" and sess["started_at"] == "2026-01-01T10:00:00Z"
          and sess["last_activity_at"] == "2026-01-01T10:02:02Z"
          and sess["title"] == "fix the rounding bug in totals"
          and sess["git_branch"] == "main" and sess["app_version"] == "9.9.9")
    return ok, f"calls={row['n']}; sums=({row['i']},{row['o']},{row['c']}); title={sess['title']!r}"


def case_tool_calls_and_status(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "s1", [
        assistant_line("s1", "u1", "2026-01-01T10:00:00Z", tools=[
            ("t1", "Bash", {"command": "pytest -x"}),
            ("t2", "Read", {"file_path": "/a/b.py"}),
            ("t3", "Write", {"file_path": "/a/c.py"}),
        ]),
        user_line("s1", "2026-01-01T10:00:10Z", results=[("t1", False), ("t2", True)]),
    ])
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    rows = {r["id"]: r for r in conn.execute("SELECT * FROM tool_calls")}
    conn.close()
    ok = (len(rows) == 3 and rows["t1"]["status"] == "ok" and rows["t2"]["status"] == "error"
          and rows["t3"]["status"] == "sent" and rows["t1"]["target"] == "pytest -x"
          and rows["t2"]["target"] == "/a/b.py")
    return ok, f"statuses={[(k, r['status']) for k, r in sorted(rows.items())]}"


def case_incremental_no_duplicates(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    path = write_transcript(proj, "s1", [assistant_line("s1", "u1", "2026-01-01T10:00:00Z")])
    ctl.index_all(repo)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(assistant_line("s1", "u2", "2026-01-01T10:05:00Z") + "\n")
    stats2 = ctl.index_all(repo)
    # Force a full rescan (as after a truncation/reset): dedupe must hold.
    conn = ctl.open_db(repo)
    conn.execute("DELETE FROM file_state WHERE path=?", (str(path),))
    conn.commit()
    conn.close()
    stats3 = ctl.index_all(repo)
    conn = ctl.open_db(repo)
    n = conn.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0]
    conn.close()
    # Subdirectory slugs: work started from repo/sub lands under '<slug>-sub';
    # it must be indexed after a cwd check, while a sibling checkout whose
    # name collides with that slug must NOT be.
    base = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects"
    subdir_proj = base / (ctl.project_slug(repo) + "-sub")
    subdir_proj.mkdir(parents=True)
    sub_line = json.loads(assistant_line("s-sub", "u-sub", "2026-01-03T10:00:00Z"))
    sub_line["cwd"] = str(repo / "sub")
    (subdir_proj / "s-sub.jsonl").write_text(json.dumps(sub_line) + "\n")
    decoy_proj = base / (ctl.project_slug(repo) + "-decoy")
    decoy_proj.mkdir(parents=True)
    decoy_line = json.loads(assistant_line("s-decoy", "u-decoy", "2026-01-03T11:00:00Z"))
    decoy_line["cwd"] = str(tmp / "elsewhere")
    (decoy_proj / "s-decoy.jsonl").write_text(json.dumps(decoy_line) + "\n")
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    subdir_sessions = {r["id"] for r in conn.execute("SELECT id FROM sessions")}
    conn.close()
    sub_ok = "s-sub" in subdir_sessions and "s-decoy" not in subdir_sessions
    # REWRITE the file with different content (changed head): old rows must be
    # purged, not merged — resuming from a stale offset would index garbage.
    time.sleep(0.02)
    write_transcript(proj, "s1", [
        assistant_line("s1", "r1", "2026-02-02T10:00:00Z", inp=7, out=7),
        assistant_line("s1", "r2", "2026-02-02T10:01:00Z", inp=7, out=7),
        assistant_line("s1", "r3", "2026-02-02T10:02:00Z", inp=7, out=7),
    ])
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    after = [r["uuid"] for r in conn.execute("SELECT uuid FROM model_calls ORDER BY uuid")]
    conn.close()
    # Deleted transcript: every derived row must go.
    path.unlink()
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    n_final = conn.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0]
    n_sess = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    conn.close()
    # s-sub (subdir slug, cwd-verified) survives; the s1 transcript's rows and
    # the decoy must both be gone.
    ok = (stats2["model_calls"] == 1 and stats3["model_calls"] == 0 and n == 2
          and sub_ok
          and after == ["msg-r1", "msg-r2", "msg-r3", "msg-u-sub"]
          and n_final == 1 and n_sess == 1)
    return ok, f"incremental=+{stats2['model_calls']}; rescan=+{stats3['model_calls']}; total={n}; subdir_ok={sub_ok}; after_rewrite={after}; after_delete=({n_final},{n_sess})"


def case_malformed_lines_skipped(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "s1", [
        "this is not json {{{",
        '["a", "list", "not", "a", "dict"]',
        assistant_line("s1", "u1", "2026-01-01T10:00:00Z"),
    ])
    stats = ctl.index_all(repo)
    conn = ctl.open_db(repo)
    n = conn.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0]
    conn.close()
    ok = stats["skipped"] == 2 and n == 1
    return ok, f"skipped={stats['skipped']}; indexed={n}"


def case_sidechain_attribution(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "s1", [
        assistant_line("s1", "u1", "2026-01-01T10:00:00Z"),
        assistant_line("s1", "u2", "2026-01-01T10:01:00Z", sidechain=True, agent="explorer", out=999),
    ])
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    rows = ctl.spend(conn, "agent")
    sess = conn.execute("SELECT agent_name FROM sessions WHERE id='s1'").fetchone()
    conn.close()
    by_agent = {r["key"]: r["output_tokens"] for r in rows}
    ok = by_agent.get("explorer") == 999 and "main" in by_agent and sess["agent_name"] == "explorer"
    return ok, f"by_agent={by_agent}; session_agent={sess['agent_name']}"


def case_summary_title_overrides(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "s1", [
        user_line("s1", "2026-01-01T10:00:00Z", text="first prompt"),
        json.dumps({"type": "summary", "summary": "Fixing the rounding bug"}),
    ])
    # s2: machine caveat first (must NOT become the title), then a
    # list-of-text-blocks prompt (the other real transcript shape).
    caveat = json.dumps({"type": "user", "sessionId": "s2", "timestamp": "2026-01-01T11:00:00Z",
                         "message": {"role": "user", "content": "Caveat: the messages below were generated..."}})
    blocks = json.dumps({"type": "user", "sessionId": "s2", "timestamp": "2026-01-01T11:00:01Z",
                         "message": {"role": "user",
                                     "content": [{"type": "text", "text": "block-form prompt"}]}})
    write_transcript(proj, "s2", [caveat, blocks])
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    t1 = conn.execute("SELECT title FROM sessions WHERE id='s1'").fetchone()["title"]
    t2 = conn.execute("SELECT title FROM sessions WHERE id='s2'").fetchone()["title"]
    conn.close()
    ok = t1 == "Fixing the rounding bug" and t2 == "block-form prompt"
    return ok, f"t1={t1!r}; t2={t2!r}"


# ---------------------------------------------------------------------------
# Artifact cases
# ---------------------------------------------------------------------------

def _fixture_record() -> dict:
    return {
        "task_id": "ctl-eval", "goal": "control-plane eval fixture", "status": "done",
        "risk_tier": "medium", "task_class": "medium",
        "commands_run": [{"cmd": "pytest", "class": "unit", "result": "pass", "evidence": "ok"}],
        "minimality_decision": {"rung": "reuse", "reason": "existing helper"},
        "plan": ["edit a.py", "test a.py"],
        "independent_review": {"reviewer": "other-model", "verdict": "approve",
                               "fresh_context": True, "diff_sha256": "0" * 64},
        "review_findings": ["approved"],
        "escalations": [{"step": "IMPLEMENT_SLICE", "from_model": "cheap", "to_model": "strong",
                         "trigger": "verified_failure", "failing_commands": ["pytest"], "attempts": 2}],
        "models_used": [{"role": "implementer", "host": "droid", "model": "cheap", "attempts": 2}],
    }


def case_record_artifacts(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    qdir = repo / ".quality-loop"
    qdir.mkdir()
    rec_path = qdir / "agent-record.json"
    rec_path.write_text(json.dumps(_fixture_record()), encoding="utf-8")
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    kinds = {r["kind"] for r in conn.execute("SELECT kind FROM artifacts")}
    conn.close()
    # mtime-gated re-ingest: change the record, counts must not duplicate
    rec = _fixture_record()
    rec["status"] = "review"
    rec_path.write_text(json.dumps(rec), encoding="utf-8")
    os.utime(rec_path, (time.time() + 5, time.time() + 5))
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    records = [r for r in ctl.list_artifacts(conn, ("record",))]
    conn.close()
    want = {"record", "review", "decision", "plan", "escalation", "models_used"}
    ok = want <= kinds and len(records) == 1 and records[0]["detail"]["status"] == "review"
    return ok, f"kinds={sorted(kinds)}; records={len(records)}; status={records[0]['detail'].get('status')}"


def case_memory_and_progress(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    mem = repo / ".quality-loop" / "memory"
    mem.mkdir(parents=True)
    (mem / "lessons.jsonl").write_text(
        json.dumps({"lesson": "keep diffs small", "kind": "process"}) + "\n"
        + json.dumps({"lesson": "run the smallest check first"}) + "\n", encoding="utf-8")
    (repo / ".quality-loop" / "progress.md").write_text("# Progress\nnext: ship it\n", encoding="utf-8")
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    lessons = ctl.list_artifacts(conn, ("memory",))
    progress = ctl.list_artifacts(conn, ("progress",))
    conn.close()
    ok = (len(lessons) == 2 and lessons[0]["title"] == "keep diffs small"
          and len(progress) == 1 and "ship it" in progress[0]["detail"]["body"])
    return ok, f"lessons={len(lessons)}; progress_body_has_next={'ship it' in (progress[0]['detail']['body'] if progress else '')}"


def case_spend_math_and_prices(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "s1", [
        assistant_line("s1", "u1", "2026-01-01T10:00:00Z", model="alpha-1", inp=1_000_000, out=500_000),
        assistant_line("s1", "u2", "2026-01-02T10:00:00Z", model="alpha-1", inp=1_000_000, out=500_000),
        assistant_line("s1", "u3", "2026-01-02T11:00:00Z", model="beta-2", inp=10, out=10),
    ])
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    prices = {"alpha": {"input_per_mtok": 3.0, "output_per_mtok": 15.0}}
    by_model = {r["key"]: r for r in ctl.spend(conn, "model", prices)}
    by_day = {r["key"]: r for r in ctl.spend(conn, "day", prices)}
    conn.close()
    alpha = by_model["alpha-1"]
    # 2M input @ $3/M + 1M output @ $15/M = 6 + 15 = 21
    # Mixed-model day: only alpha's share is priced (1M in + 0.5M out = 10.5);
    # unpriced beta tokens must not inherit alpha's rate.
    ok = (alpha["cost_usd"] == 21.0 and by_model["beta-2"]["cost_usd"] is None
          and by_day["2026-01-01"]["output_tokens"] == 500_000
          and by_day["2026-01-02"]["output_tokens"] == 500_010
          and by_day["2026-01-02"]["cost_usd"] == 10.5)
    day_out = {k: (v["output_tokens"], v["cost_usd"]) for k, v in by_day.items()}
    return ok, f"alpha_cost={alpha['cost_usd']}; beta_cost={by_model['beta-2']['cost_usd']}; days={day_out}"


# ---------------------------------------------------------------------------
# Server cases
# ---------------------------------------------------------------------------

def _start_server(repo: Path):
    """In-process server on an ephemeral 127.0.0.1 port."""
    from http.server import ThreadingHTTPServer
    import threading
    handler = type("H", (ctl._Handler,), {"root": repo})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, httpd.server_address[1]


def case_api_endpoints(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "s1", [
        user_line("s1", "2026-01-01T10:00:00Z", text="hello"),
        assistant_line("s1", "u1", "2026-01-01T10:00:05Z"),
    ])
    (repo / ".quality-loop").mkdir()
    (repo / ".quality-loop" / "agent-record.json").write_text(json.dumps(_fixture_record()))
    ctl.index_all(repo)
    httpd, port = _start_server(repo)
    try:
        results = {}
        for ep in ("healthz", "api/overview", "api/sessions?limit=5", "api/session?id=s1",
                   "api/spend?by=day", "api/records", "api/memory", "api/events", "api/routing",
                   "api/delegations", "api/task?task_id=ctl-eval", "api/metrics"):
            code, body = get_json(f"http://127.0.0.1:{port}/{ep}")
            results[ep] = code
        detail_code, detail = get_json(f"http://127.0.0.1:{port}/api/session?id=s1")
        bad_by, _ = get_json(f"http://127.0.0.1:{port}/api/spend?by=nope")
        missing, _ = get_json(f"http://127.0.0.1:{port}/api/session?id=ghost")
        bad_limit, _ = get_json(f"http://127.0.0.1:{port}/api/sessions?limit=abc")
        neg_limit_code, neg = get_json(f"http://127.0.0.1:{port}/api/sessions?limit=-1")
        task_no_id, _ = get_json(f"http://127.0.0.1:{port}/api/task")
        task_ghost, _ = get_json(f"http://127.0.0.1:{port}/api/task?task_id=ghost")
    finally:
        httpd.shutdown()
        httpd.server_close()
    ok = (all(code == 200 for code in results.values()) and bad_by == 400 and missing == 404
          and detail["session"]["id"] == "s1" and detail["models"][0]["calls"] == 1
          and bad_limit == 400 and neg_limit_code == 200 and len(neg["sessions"]) == 1
          and task_no_id == 400 and task_ghost == 404)
    return ok, (f"codes={results}; bad_by={bad_by}; missing={missing}; bad_limit={bad_limit}; "
                f"neg_limit_rows={len(neg['sessions'])}; task_no_id={task_no_id}; task_ghost={task_ghost}")


def case_server_read_only_and_local(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    ctl.index_all(repo)
    httpd, port = _start_server(repo)
    try:
        bind_host = httpd.server_address[0]
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/overview",
                                     data=b"{}", method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            post_code = 200
        except urllib.error.HTTPError as err:
            post_code = err.code
        unknown, _ = get_json(f"http://127.0.0.1:{port}/api/definitely-not-a-thing")
        root_code, _ = get_json(f"http://127.0.0.1:{port}/healthz")
        # DNS-rebinding guard: a foreign Host header must be rejected even
        # though the TCP connection itself is loopback.
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/overview",
                                     headers={"Host": "evil.example.com"})
        try:
            urllib.request.urlopen(req, timeout=5)
            rebind_code = 200
        except urllib.error.HTTPError as err:
            rebind_code = err.code
    finally:
        httpd.shutdown()
        httpd.server_close()
    # The fixture binds its own server, so also pin PRODUCTION serve(): the
    # bind host must be the 127.0.0.1 literal (not configurable anywhere).
    src = (ROOT / "scripts" / "quality_loop_control.py").read_text(encoding="utf-8")
    prod_bind = 'ThreadingHTTPServer(("127.0.0.1", port)' in src
    ok = (bind_host == "127.0.0.1" and post_code == 405 and unknown == 404
          and root_code == 200 and rebind_code == 403 and prod_bind)
    return ok, f"bind={bind_host}; post={post_code}; unknown={unknown}; rebind={rebind_code}; prod_bind_literal={prod_bind}"


def case_dashboard_self_contained(tmp: Path) -> tuple[bool, str]:
    page = ROOT / "assets" / "control-plane" / "dashboard.html"
    if not page.is_file():
        return False, "assets/control-plane/dashboard.html missing"
    body = page.read_text(encoding="utf-8")
    external = re.findall(r"https?://[^\s\"'<>]+", body)
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    ctl.index_all(repo)
    httpd, port = _start_server(repo)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as res:
            served = res.read().decode("utf-8")
            code = res.status
    finally:
        httpd.shutdown()
        httpd.server_close()
    ok = (not external and code == 200 and "<title>CQL Control Plane</title>" in served
          and "prefers-color-scheme" in body and 'data-theme="dark"' in body)
    return ok, f"external_refs={external[:3]}; served={code}; themed={'prefers-color-scheme' in body}"


# ---------------------------------------------------------------------------
# Audit-trail cases (v5.1.0: findings, delegations, task timeline, metrics,
# report CLI, tool-target redaction)
# ---------------------------------------------------------------------------

def _deleg_line(task_id: str, role: str, expected: str, ts: str,
                host: str = "droid", model: str = "cheap", brief: str = "do the thing") -> str:
    return json.dumps({"ts": ts, "task_id": task_id, "role": role, "host": host,
                       "model": model, "brief_summary": brief, "expected_agent_name": expected})


def case_findings_first_class(tmp: Path) -> tuple[bool, str]:
    """AC1: findings from ALL THREE channels become first-class `finding`
    artifacts carrying severity + text + reviewer + source: the array form on
    independent_review.findings[] and security_review.findings[], and the
    top-level review_findings[]. A bare-string finding buckets as `unspecified`
    (V4), and the summed artifacts intentionally exceed any single review row's
    per-channel `findings` count (R2)."""
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    rec = _fixture_record()
    # array form on the independent review
    rec["independent_review"] = {"reviewer": "other-model", "verdict": "approve",
                                 "fresh_context": True, "diff_sha256": "0" * 64,
                                 "findings": [{"severity": "high", "text": "unbounded recursion in parser"}]}
    # array form on the security review (distinct reviewer)
    rec["security_review"] = {"reviewer": "sec-model", "verdict": "approve",
                              "fresh_context": True, "diff_sha256": "0" * 64,
                              "findings": [{"severity": "critical", "text": "secret logged in cleartext"}]}
    # top-level channel: one triaged + one bare string (no severity -> unspecified)
    rec["review_findings"] = [
        {"severity": "low", "text": "prefer f-string over concatenation"},
        "reviewer left a note with no severity",
    ]
    (repo / ".quality-loop").mkdir()
    (repo / ".quality-loop" / "agent-record.json").write_text(json.dumps(rec), encoding="utf-8")
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    findings = ctl.list_artifacts(conn, ("finding",))
    reviews = {r["detail"].get("kind"): r for r in ctl.list_artifacts(conn, ("review",))}
    conn.close()
    by_text = {f["detail"]["text"]: f["detail"] for f in findings}
    sources = {f["detail"]["source"] for f in findings}
    sevs = {f["detail"]["severity"] for f in findings}
    ind = by_text.get("unbounded recursion in parser", {})
    sec = by_text.get("secret logged in cleartext", {})
    bare = by_text.get("reviewer left a note with no severity", {})
    ok = (len(findings) == 4
          and sources == {"independent_review", "security_review", "review_findings"}
          and sevs == {"high", "critical", "low", "unspecified"}
          and ind.get("source") == "independent_review"
          and sec.get("source") == "security_review" and sec.get("reviewer") == "sec-model"
          and bare.get("severity") == "unspecified"
          # per-channel row counts (R2): independent row counts review_findings[],
          # security row counts its own findings[]; summed artifacts (4) exceed both.
          and reviews["independent"]["detail"]["findings"] == 2
          and reviews["security"]["detail"]["findings"] == 1)
    return ok, (f"findings={len(findings)}; sources={sorted(sources)}; sevs={sorted(sevs)}; "
                f"ind_src={ind.get('source')}; sec_reviewer={sec.get('reviewer')}; bare_sev={bare.get('severity')}; "
                f"rows=ind:{reviews['independent']['detail']['findings']}/sec:{reviews['security']['detail']['findings']}")


def case_delegations_ledger(tmp: Path) -> tuple[bool, str]:
    """AC2: delegations.jsonl ingests to `delegation` artifacts; a garbage line
    is counted in skipped_lines; re-indexing is idempotent."""
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    qdir = repo / ".quality-loop"
    qdir.mkdir()
    ledger = qdir / "delegations.jsonl"
    ledger.write_text(
        _deleg_line("t-1", "implementer", "impl-agent", "2026-01-01T10:00:00Z") + "\n"
        + "{ this is not json }\n"
        + _deleg_line("t-1", "reviewer", "rev-agent", "2026-01-01T10:30:00Z") + "\n",
        encoding="utf-8")
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    delegs = ctl.list_artifacts(conn, ("delegation",))
    skipped = int(ctl._meta_get(conn, "skipped_lines") or 0)
    conn.close()
    # Re-index without touching the file: mtime-gated, so no new rows / no new skips.
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    delegs2 = ctl.list_artifacts(conn, ("delegation",))
    skipped2 = int(ctl._meta_get(conn, "skipped_lines") or 0)
    conn.close()
    roles = {d["detail"]["role"] for d in delegs}
    ok = (len(delegs) == 2 and roles == {"implementer", "reviewer"}
          and skipped >= 1 and len(delegs2) == 2 and skipped2 == skipped)
    return ok, f"delegs={len(delegs)}; roles={sorted(roles)}; skipped={skipped}; reindex_delegs={len(delegs2)}; skipped2={skipped2}"


def case_delegation_session_join(tmp: Path) -> tuple[bool, str]:
    """AC3: a delegation joins to the session it ran in (agent_name match inside
    the time window) with exact token sums; a non-matching one is `unmatched`."""
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    # The reviewer sub-agent's session, started 5 min after the delegation line.
    write_transcript(proj, "revsess", [
        assistant_line("revsess", "r1", "2026-01-01T10:05:00Z", model="strong",
                       inp=300, out=222, agent="rev-agent", sidechain=True),
        assistant_line("revsess", "r2", "2026-01-01T10:06:00Z", model="strong",
                       inp=100, out=28, agent="rev-agent", sidechain=True),
    ])
    qdir = repo / ".quality-loop"
    qdir.mkdir()
    (qdir / "delegations.jsonl").write_text(
        _deleg_line("t-9", "reviewer", "rev-agent", "2026-01-01T10:00:00Z") + "\n"
        + _deleg_line("t-9", "implementer", "nobody-agent", "2026-01-01T10:00:00Z") + "\n",
        encoding="utf-8")
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    joined = ctl.delegations_with_sessions(conn)
    conn.close()
    matched = next((d for d in joined if d["expected_agent_name"] == "rev-agent"), None)
    unmatched = next((d for d in joined if d["expected_agent_name"] == "nobody-agent"), None)
    ok = (matched and not matched["unmatched"] and matched["session"]["id"] == "revsess"
          and matched["session"]["tokens"]["input_tokens"] == 400
          and matched["session"]["tokens"]["output_tokens"] == 250
          and unmatched and unmatched["unmatched"] and unmatched["session"] is None)
    return ok, (f"matched_sess={matched['session']['id'] if matched and matched['session'] else None}; "
                f"in={matched['session']['tokens']['input_tokens'] if matched and matched['session'] else None}; "
                f"out={matched['session']['tokens']['output_tokens'] if matched and matched['session'] else None}; "
                f"unmatched={bool(unmatched and unmatched['unmatched'])}")


def case_task_timeline(tmp: Path) -> tuple[bool, str]:
    """AC4: task_timeline assembles every artifact kind for a task_id in ts
    order and returns None for an unknown task."""
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    qdir = repo / ".quality-loop"
    qdir.mkdir()
    rec = _fixture_record()
    rec["review_findings"] = [{"severity": "high", "text": "leak"}]
    (qdir / "agent-record.json").write_text(json.dumps(rec), encoding="utf-8")
    (qdir / "delegations.jsonl").write_text(
        _deleg_line("ctl-eval", "implementer", "impl-agent", "2026-01-01T09:00:00Z") + "\n",
        encoding="utf-8")
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    bundle = ctl.task_timeline(conn, "ctl-eval")
    unknown = ctl.task_timeline(conn, "does-not-exist")
    conn.close()
    kinds = {e["kind"] for e in (bundle["timeline"] if bundle else [])}
    ts_list = [str(e["ts"] or "") for e in (bundle["timeline"] if bundle else [])]
    want = {"record", "decision", "plan", "delegation", "escalation", "review", "finding"}
    ok = (bundle is not None and unknown is None and want <= kinds
          and ts_list == sorted(ts_list)
          and len(bundle["findings"]) == 1 and len(bundle["delegations"]) == 1)
    return ok, f"kinds={sorted(kinds)}; ordered={ts_list == sorted(ts_list)}; unknown_is_none={unknown is None}"


def case_loop_metrics(tmp: Path) -> tuple[bool, str]:
    """AC5: loop_metrics computes exact KPIs over indexed artifacts; the
    endpoint returns 200 with all-zero shape on an empty DB."""
    # Empty-DB path first: served 200, zeroed, division-by-zero safe.
    empty = make_repo(tmp, "empty")
    claude_dir(tmp, empty)
    ctl.index_all(empty)
    httpd, port = _start_server(empty)
    try:
        code, m0 = get_json(f"http://127.0.0.1:{port}/api/metrics")
    finally:
        httpd.shutdown(); httpd.server_close()
    zero_ok = (code == 200 and m0["verdict_distribution"] == {}
               and m0["evidence_rate"]["rate_pct"] == 0.0 and m0["escalations"] == 0)
    # Populated path: two records with distinct verdicts + findings + escalations.
    repo = make_repo(tmp, "full")
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "s1", [assistant_line("s1", "u1", "2026-01-01T10:00:00Z", inp=10, out=5)])
    docs = repo / "docs" / "records"
    docs.mkdir(parents=True)
    r1 = _fixture_record()
    r1["task_id"] = "task-a"
    r1["review_findings"] = [{"severity": "high", "text": "x"}, {"severity": "low", "text": "y"}]
    r2 = _fixture_record()
    r2["task_id"] = "task-b"
    r2["independent_review"]["verdict"] = "reject"
    r2["commands_run"] = []  # no evidence for this one
    r2["escalations"] = []
    (docs / "task-a.json").write_text(json.dumps(r1), encoding="utf-8")
    (docs / "task-b.json").write_text(json.dumps(r2), encoding="utf-8")
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    m = ctl.loop_metrics(conn, repo)
    conn.close()
    ok = (zero_ok
          and m["verdict_distribution"].get("approve") == 1
          and m["verdict_distribution"].get("reject") == 1
          and m["findings_by_severity"].get("high") == 1
          and m["findings_by_severity"].get("low") == 1
          and m["escalations"] == 1
          and m["evidence_rate"] == {"records": 2, "with_evidence": 1, "rate_pct": 50.0})
    return ok, f"zero_ok={zero_ok}; verdicts={m['verdict_distribution']}; sev={m['findings_by_severity']}; evidence={m['evidence_rate']}"


def case_control_report_cli(tmp: Path) -> tuple[bool, str]:
    """AC6: control-report emits markdown (goal/verdict/finding/token totals),
    --json parses, and an unknown task exits 2."""
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "revsess", [
        assistant_line("revsess", "r1", "2026-01-01T10:05:00Z", model="strong",
                       inp=300, out=222, agent="rev-agent", sidechain=True),
    ])
    qdir = repo / ".quality-loop"
    qdir.mkdir()
    rec = _fixture_record()
    rec["review_findings"] = [{"severity": "high", "text": "off-by-one in slice bound"}]
    (qdir / "agent-record.json").write_text(json.dumps(rec), encoding="utf-8")
    (qdir / "delegations.jsonl").write_text(
        _deleg_line("ctl-eval", "reviewer", "rev-agent", "2026-01-01T10:00:00Z") + "\n",
        encoding="utf-8")
    ctl.index_all(repo)
    md_code, md_out, _ = run_stdin([sys.executable, str(QL), "control-report",
                                    "--cwd", str(repo), "--task-id", "ctl-eval"], "", repo)
    js_code, js_out, _ = run_stdin([sys.executable, str(QL), "control-report", "--json",
                                    "--cwd", str(repo), "--task-id", "ctl-eval"], "", repo)
    miss_code, _, miss_err = run_stdin([sys.executable, str(QL), "control-report",
                                        "--cwd", str(repo), "--task-id", "no-such"], "", repo)
    parsed_ok = False
    try:
        parsed = json.loads(js_out)
        parsed_ok = parsed["task_id"] == "ctl-eval"
    except (ValueError, KeyError):
        parsed = {}
    ok = (md_code == 0 and js_code == 0 and miss_code == 2
          and "control-plane eval fixture" in md_out
          and "approve" in md_out
          and "off-by-one in slice bound" in md_out
          and "300 in / 222 out" in md_out
          and parsed_ok)
    return ok, (f"md_code={md_code}; js_code={js_code}; miss_code={miss_code}; "
                f"goal={'control-plane eval fixture' in md_out}; finding={'off-by-one in slice bound' in md_out}; "
                f"tokens={'300 in / 222 out' in md_out}; json_ok={parsed_ok}")


def case_tool_target_redaction(tmp: Path) -> tuple[bool, str]:
    """AC7: a secret typed into a tool command is redacted before it is stored
    in tool_calls.target; a benign command is stored verbatim."""
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    # Assemble the fake key from fragments so this fixture line does not itself
    # trip the repo's own added-diff secret scanner; the runtime value is a
    # well-formed sk-live-* key that the redactor must catch.
    prefix = "sk-" "live-"
    fake_key = prefix + "a1B2c3D4e5F6g7H8i9J0"
    write_transcript(proj, "s1", [
        assistant_line("s1", "u1", "2026-01-01T10:00:00Z",
                       tools=[("t1", "Bash", {"command": f"export OPENAI_KEY={fake_key}"})]),
        assistant_line("s1", "u2", "2026-01-01T10:00:10Z",
                       tools=[("t2", "Bash", {"command": "pytest -q tests/unit"})]),
    ])
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    targets = [r["target"] for r in conn.execute(
        "SELECT target FROM tool_calls ORDER BY ts")]
    conn.close()
    joined = "\n".join(targets)
    ok = (fake_key not in joined and prefix not in joined
          and "[REDACTED]" in joined
          and "pytest -q tests/unit" in targets)
    return ok, f"secret_leaked={fake_key in joined}; redacted={'[REDACTED]' in joined}; benign_intact={'pytest -q tests/unit' in targets}"


# ---------------------------------------------------------------------------
# v6.0.0 cases: session_id join, join fixes, droid events, drift canary,
# retention, schema-bump backup, arm-costs
# ---------------------------------------------------------------------------

def case_delegation_direct_session_id(tmp: Path) -> tuple[bool, str]:
    """v6: a ledger row carrying session_id joins directly by id — the fuzzy
    heuristic is skipped even when agent_name and window disagree — and an
    explicit id that is not indexed stays unmatched, never guessed against.
    Direct joins are one-to-one too: a second row carrying the SAME session_id
    is flagged duplicate_session_id and left unmatched (no double-counting)."""
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "workersess", [
        assistant_line("workersess", "w1", "2026-01-05T10:05:00Z", inp=100, out=40, agent="impl-agent"),
    ])
    qdir = repo / ".quality-loop"
    qdir.mkdir()
    # Direct row: wrong agent name, ts years outside any window — id wins anyway.
    direct = json.loads(_deleg_line("t-d", "implementer", "totally-other-agent", "2020-01-01T00:00:00Z"))
    direct["session_id"] = "workersess"
    # Ghost row: agent + window WOULD fuzzy-match workersess, but the explicit
    # (unindexed) id must not be second-guessed by the heuristic.
    ghost = json.loads(_deleg_line("t-d", "reviewer", "impl-agent", "2026-01-05T10:00:00Z"))
    ghost["session_id"] = "ghost-session"
    # Duplicate row: the SAME explicit session_id as the direct row. Only the
    # first (ledger order) may attach; this one is flagged, not double-counted.
    dup = json.loads(_deleg_line("t-d", "validator", "totally-other-agent", "2020-01-02T00:00:00Z"))
    dup["session_id"] = "workersess"
    (qdir / "delegations.jsonl").write_text(
        json.dumps(direct) + "\n" + json.dumps(ghost) + "\n" + json.dumps(dup) + "\n",
        encoding="utf-8")
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    joined = ctl.delegations_with_sessions(conn)
    conn.close()
    d_direct = next(d for d in joined if d["role"] == "implementer")
    d_ghost = next(d for d in joined if d["role"] == "reviewer")
    d_dup = next(d for d in joined if d["role"] == "validator")
    attached = sum(1 for d in joined if d["session"] is not None)
    ok = (not d_direct["unmatched"] and d_direct["session"]["id"] == "workersess"
          and d_direct["session"]["tokens"]["input_tokens"] == 100
          and d_ghost["unmatched"] and d_ghost["session"] is None
          and not d_ghost["unjoinable"]
          and d_dup["unmatched"] and d_dup["session"] is None
          and d_dup["duplicate_session_id"] and not d_direct["duplicate_session_id"]
          and attached == 1)
    return ok, (f"direct={d_direct['session']['id'] if d_direct['session'] else None}; "
                f"ghost_unmatched={d_ghost['unmatched']}; ghost_session={d_ghost['session']}; "
                f"dup_flagged={d_dup['duplicate_session_id']}; attached={attached}")


def case_delegation_unjoinable_ts(tmp: Path) -> tuple[bool, str]:
    """v6 join fix (a): a legacy row whose ts is unparseable is flagged
    `unjoinable` — never a distance-0 best match that steals the session from
    an honest row — and /api/delegations surfaces the count."""
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "rsess", [
        assistant_line("rsess", "r1", "2026-01-05T10:05:00Z", inp=10, out=5, agent="rev-agent"),
    ])
    qdir = repo / ".quality-loop"
    qdir.mkdir()
    # The broken row comes FIRST: under the old code it matched everything at
    # dist 0.0 and stole rsess from the honest second row.
    (qdir / "delegations.jsonl").write_text(
        _deleg_line("t-u", "reviewer", "rev-agent", "not-a-timestamp") + "\n"
        + _deleg_line("t-u", "validator", "rev-agent", "2026-01-05T10:00:00Z") + "\n",
        encoding="utf-8")
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    joined = ctl.delegations_with_sessions(conn)
    conn.close()
    bad = next(d for d in joined if d["role"] == "reviewer")
    good = next(d for d in joined if d["role"] == "validator")
    httpd, port = _start_server(repo)
    try:
        code, body = get_json(f"http://127.0.0.1:{port}/api/delegations")
    finally:
        httpd.shutdown()
        httpd.server_close()
    ok = (bad["unjoinable"] and bad["unmatched"] and bad["session"] is None
          and not good["unmatched"] and good["session"]["id"] == "rsess"
          and code == 200 and body["unjoinable"] == 1)
    return ok, (f"bad_unjoinable={bad['unjoinable']}; good_session="
                f"{good['session']['id'] if good['session'] else None}; api_unjoinable={body.get('unjoinable')}")


def case_delegation_one_to_one(tmp: Path) -> tuple[bool, str]:
    """v6 join fix (b): the fallback join is one-to-one — a session matched by
    a nearer delegation is not double-counted (the next-nearest goes
    unmatched); once a second session exists, each delegation gets its own."""
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "w1", [
        assistant_line("w1", "a1", "2026-01-05T10:10:00Z", inp=11, out=7, agent="worker"),
    ])
    qdir = repo / ".quality-loop"
    qdir.mkdir()
    (qdir / "delegations.jsonl").write_text(
        _deleg_line("t-1", "implementer", "worker", "2026-01-05T10:00:00Z") + "\n"  # 600s from w1
        + _deleg_line("t-2", "implementer", "worker", "2026-01-05T10:09:00Z") + "\n",  # 60s: wins w1
        encoding="utf-8")
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    joined = ctl.delegations_with_sessions(conn)
    conn.close()
    far = next(d for d in joined if d["task_id"] == "t-1")
    near = next(d for d in joined if d["task_id"] == "t-2")
    one_ok = (not near["unmatched"] and near["session"]["id"] == "w1"
              and far["unmatched"] and far["session"] is None)
    # A second worker session appears: both rows now link, one session each.
    write_transcript(proj, "w2", [
        assistant_line("w2", "b1", "2026-01-05T10:01:00Z", inp=3, out=2, agent="worker"),
    ])
    ctl.index_all(repo)
    conn = ctl.open_db(repo)
    joined2 = ctl.delegations_with_sessions(conn)
    conn.close()
    far2 = next(d for d in joined2 if d["task_id"] == "t-1")
    near2 = next(d for d in joined2 if d["task_id"] == "t-2")
    two_ok = (near2["session"] is not None and near2["session"]["id"] == "w1"
              and far2["session"] is not None and far2["session"]["id"] == "w2")
    ok = one_ok and two_ok
    return ok, (f"one_session: near={near['session']['id'] if near['session'] else None}, "
                f"far_unmatched={far['unmatched']}; two_sessions: "
                f"near={near2['session']['id'] if near2['session'] else None}, "
                f"far={far2['session']['id'] if far2['session'] else None}")


def case_droid_runs_are_events(tmp: Path) -> tuple[bool, str]:
    """v6: a droid wrapper run indexes as a 'droid_run' event + tool call —
    never a fabricated 0-token model_calls row that corrupts call totals —
    and re-indexing never duplicates the event."""
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log = tmp / "droid-wrapper.jsonl"
    log.write_text(json.dumps({
        "event": "wrapper_end", "ts": ts, "cwd": str(repo), "session_id": "run-1",
        "model": "glm-5", "mode": "exec", "exit_code": 0, "ok": True,
        "prompt_file": "fix-parser.md"}) + "\n", encoding="utf-8")
    saved = os.environ.get("DROID_WRAPPER_LOG")
    os.environ["DROID_WRAPPER_LOG"] = str(log)
    try:
        stats = ctl.index_all(repo)
        stats2 = ctl.index_all(repo)  # whole-log re-parse must not duplicate
        conn = ctl.open_db(repo)
        n_calls = conn.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0]
        events = conn.execute(
            "SELECT session_id, host, detail FROM events WHERE name='droid_run'").fetchall()
        tool = conn.execute("SELECT tool, status FROM tool_calls").fetchone()
        sess = conn.execute("SELECT host FROM sessions WHERE id='droid:run-1'").fetchone()
        conn.close()
    finally:
        if saved is None:
            os.environ.pop("DROID_WRAPPER_LOG", None)
        else:
            os.environ["DROID_WRAPPER_LOG"] = saved
    detail = json.loads(events[0]["detail"]) if events else {}
    ok = (stats["droid_runs"] == 1 and stats2["droid_runs"] == 0
          and n_calls == 0 and len(events) == 1
          and events[0]["host"] == "droid" and events[0]["session_id"] == "droid:run-1"
          and detail.get("model") == "glm-5" and detail.get("ok") is True
          and sess is not None and sess["host"] == "droid"
          and tool is not None and tool["status"] == "ok")
    return ok, (f"runs=({stats['droid_runs']},{stats2['droid_runs']}); model_calls={n_calls}; "
                f"events={len(events)}; detail={detail}; tool_status={tool['status'] if tool else None}")


def case_zero_usage_canary(tmp: Path) -> tuple[bool, str]:
    """v6 drift canary: a transcript whose usage keys were RENAMED still
    indexes (zeros) but turns the counter nonzero — surfaced via overview,
    /healthz, control-status, and a dashboard banner — instead of silently
    filling the index with confident zeros. '<synthetic>' placeholder turns
    stay exempt."""
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    renamed = json.loads(assistant_line("s1", "u1", "2026-01-05T10:00:00Z"))
    renamed["message"]["usage"] = {"in_tok": 100, "out_tok": 50}  # vendor renamed the keys
    healthy = assistant_line("s1", "u2", "2026-01-05T10:01:00Z", inp=10, out=5)
    synthetic = json.loads(assistant_line("s1", "u3", "2026-01-05T10:02:00Z", inp=0, out=0))
    synthetic["message"]["model"] = "<synthetic>"
    write_transcript(proj, "s1", [json.dumps(renamed), healthy, json.dumps(synthetic)])
    stats = ctl.index_all(repo)
    conn = ctl.open_db(repo)
    ov = ctl.overview(conn)
    conn.close()
    httpd, port = _start_server(repo)
    try:
        hcode, health = get_json(f"http://127.0.0.1:{port}/healthz")
    finally:
        httpd.shutdown()
        httpd.server_close()
    scode, sout, _ = run_stdin([sys.executable, str(QL), "control-status", "--json",
                                "--cwd", str(repo)], "", repo)
    try:
        status = json.loads(sout)
    except ValueError:
        status = {}
    banner = "token counts may be stale" in (
        ROOT / "assets" / "control-plane" / "dashboard.html").read_text(encoding="utf-8")
    ok = (stats["zero_usage"] == 1 and ov["zero_usage_lines"] == 1
          and hcode == 200 and health.get("zero_usage_lines") == 1
          and scode == 0 and status.get("zero_usage_lines") == 1
          and banner)
    return ok, (f"pass_count={stats['zero_usage']}; overview={ov['zero_usage_lines']}; "
                f"healthz={health.get('zero_usage_lines')}; status={status.get('zero_usage_lines')}; "
                f"dashboard_banner={banner}")


def case_retention_prunes_all_tables(tmp: Path) -> tuple[bool, str]:
    """v6: retention_days prunes sessions/model_calls/tool_calls/artifacts/
    events by ONE cutoff — not just events — and pruned rows stay pruned on
    the next pass (the offset cache never re-reads an unchanged file)."""
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    (repo / "quality-loop.config.json").write_text(
        json.dumps({"version": "x", "control_plane": {"retention_days": 30}}), encoding="utf-8")
    old_ts = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    new_ts = datetime.now(timezone.utc).isoformat()
    write_transcript(proj, "old", [
        assistant_line("old", "o1", old_ts, tools=[("t1", "Bash", {"command": "ls"})]),
    ])
    write_transcript(proj, "new", [assistant_line("new", "n1", new_ts)])
    qdir = repo / ".quality-loop"
    qdir.mkdir()
    rec = qdir / "agent-record.json"
    rec.write_text(json.dumps(_fixture_record()), encoding="utf-8")
    old_epoch = time.time() - 40 * 86400  # artifact ts = source mtime -> old
    os.utime(rec, (old_epoch, old_epoch))
    stats = ctl.index_all(repo)
    conn = ctl.open_db(repo)
    sess = {r["id"] for r in conn.execute("SELECT id FROM sessions")}
    n_calls = conn.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0]
    n_tools = conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
    n_arts = conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    conn.close()
    pruned = stats["rows_pruned"]
    ctl.index_all(repo)  # unchanged sources: nothing resurrected
    conn = ctl.open_db(repo)
    sess2 = {r["id"] for r in conn.execute("SELECT id FROM sessions")}
    conn.close()
    ok = (sess == {"new"} and n_calls == 1 and n_tools == 0 and n_arts == 0
          and pruned["sessions"] == 1 and pruned["model_calls"] == 1
          and pruned["tool_calls"] == 1 and pruned["artifacts"] >= 1
          and sess2 == {"new"})
    return ok, (f"sessions={sorted(sess)}; calls={n_calls}; tools={n_tools}; artifacts={n_arts}; "
                f"pruned={pruned}; after_reindex={sorted(sess2)}")


def case_schema_bump_backs_up_events(tmp: Path) -> tuple[bool, str]:
    """v6: a schema-version mismatch exports hook events (the one thing a
    rebuild cannot regenerate) to append-safe events-backup-schema<N>.jsonl
    before deleting the DB."""
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    conn = ctl.open_db(repo)
    conn.execute(
        "INSERT INTO events(session_id, host, ts, name, detail) VALUES(?,?,?,?,?)",
        ("hook-1", "claude-code", "2026-01-05T10:00:00Z", "SessionStart", None))
    conn.execute("PRAGMA user_version=3")  # simulate a cache from schema v3
    conn.commit()
    conn.close()
    conn = ctl.open_db(repo)  # mismatch -> backup, then rebuild
    n_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    backup = ctl.control_dir(repo) / "events-backup-schema3.jsonl"
    rows = ([json.loads(line) for line in backup.read_text(encoding="utf-8").splitlines()]
            if backup.is_file() else [])
    ok = (backup.is_file() and len(rows) == 1 and rows[0]["name"] == "SessionStart"
          and rows[0]["session_id"] == "hook-1"
          and n_events == 0 and version == ctl.SCHEMA_VERSION)
    return ok, (f"backup={backup.is_file()}; rows={len(rows)}; "
                f"rebuilt_events={n_events}; version={version}")


def case_arm_costs_query(tmp: Path) -> tuple[bool, str]:
    """4.2: control-report --arm-costs emits per-session tokens_in/tokens_out/
    duration_sec JSON shaped for a bench results arm; --since filters by last
    activity; an unparseable --since exits 2 naming the fix."""
    repo = make_repo(tmp)
    proj = claude_dir(tmp, repo)
    write_transcript(proj, "recent", [
        assistant_line("recent", "a1", "2026-01-05T10:00:00Z", inp=100, out=40),
        assistant_line("recent", "a2", "2026-01-05T10:10:00Z", inp=50, out=10),
    ])
    write_transcript(proj, "older", [
        assistant_line("older", "b1", "2026-01-01T09:00:00Z", inp=7, out=3),
    ])
    ctl.index_all(repo)
    ctl_py = ROOT / "scripts" / "quality_loop.py"
    code, out, _ = run_stdin([sys.executable, str(ctl_py), "control-report", "--arm-costs",
                              "--cwd", str(repo)], "", repo)
    try:
        data = json.loads(out)
    except ValueError:
        data = {"sessions": [], "totals": {}}
    by_id = {s["session_id"]: s for s in data["sessions"]}
    code2, out2, _ = run_stdin([sys.executable, str(ctl_py), "control-report", "--arm-costs",
                                "--since", "2026-01-03T00:00:00Z", "--cwd", str(repo)], "", repo)
    try:
        data2 = json.loads(out2)
    except ValueError:
        data2 = {"sessions": [], "totals": {}}
    code3, _, err3 = run_stdin([sys.executable, str(ctl_py), "control-report", "--arm-costs",
                                "--since", "yesterday-ish", "--cwd", str(repo)], "", repo)
    recent = by_id.get("recent", {})
    ok = (code == 0 and recent.get("tokens_in") == 150 and recent.get("tokens_out") == 50
          and recent.get("duration_sec") == 600.0
          and data["totals"].get("tokens_in") == 157
          and code2 == 0
          and [s["session_id"] for s in data2["sessions"]] == ["recent"]
          and data2["totals"].get("tokens_out") == 50
          and code3 == 2 and "ISO-8601" in err3)
    return ok, (f"codes=({code},{code2},{code3}); recent=({recent.get('tokens_in')},"
                f"{recent.get('tokens_out')},{recent.get('duration_sec')}); "
                f"totals_in={data['totals'].get('tokens_in')}; "
                f"since_ids={[s['session_id'] for s in data2['sessions']]}; iso_err={'ISO-8601' in err3}")


# ---------------------------------------------------------------------------
# Ingest + shim cases
# ---------------------------------------------------------------------------

def run_stdin(cmd: list[str], stdin: str, cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, input=stdin, text=True, capture_output=True, cwd=str(cwd))
    return proc.returncode, proc.stdout, proc.stderr


def case_ingest_event_roundtrip(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    enabled_config(repo)
    payload = json.dumps({"session_id": "hook-1", "cwd": str(repo), "source": "startup"})
    code, _, err = run_stdin([sys.executable, str(QL), "control-ingest", "--event", "SessionStart",
                              "--cwd", str(repo)], payload, repo)
    code2, _, _ = run_stdin([sys.executable, str(QL), "control-ingest", "--event", "SessionEnd",
                             "--cwd", str(repo)], json.dumps({"session_id": "hook-1"}), repo)
    conn = ctl.open_db(repo)
    events = [r["name"] for r in conn.execute("SELECT name FROM events ORDER BY id")]
    sess = conn.execute("SELECT source, ended_at FROM sessions WHERE id='hook-1'").fetchone()
    conn.close()
    ok = (code == 0 and code2 == 0 and events == ["SessionStart", "SessionEnd"]
          and sess["source"] == "hook" and sess["ended_at"])
    return ok, f"exit=({code},{code2}); events={events}; ended={bool(sess['ended_at']) if sess else None}; err={err.strip()[:80]!r}"


def case_ingest_disabled_noop(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    # No config at all -> disabled; then explicit enabled:false -> still disabled.
    code1, _, _ = run_stdin([sys.executable, str(QL), "control-ingest", "--event", "SessionStart",
                             "--cwd", str(repo)], json.dumps({"session_id": "x"}), repo)
    no_dir = not (repo / ".quality-loop" / "control").exists()
    (repo / "quality-loop.config.json").write_text(json.dumps({"control_plane": {"enabled": False}}))
    code2, _, _ = run_stdin([sys.executable, str(QL), "control-ingest", "--event", "SessionStart",
                             "--cwd", str(repo)], json.dumps({"session_id": "x"}), repo)
    still_no_dir = not (repo / ".quality-loop" / "control").exists()
    # Opt-in holds on the ERROR path too: garbage stdin in a disabled repo
    # must not create the control dir via the error logger.
    code3, _, _ = run_stdin([sys.executable, str(QL), "control-ingest", "--event", "SessionStart",
                             "--cwd", str(repo)], "garbage {{{ not json", repo)
    error_path_clean = not (repo / ".quality-loop" / "control").exists()
    ok = code1 == 0 and code2 == 0 and code3 == 0 and no_dir and still_no_dir and error_path_clean
    return ok, f"exits=({code1},{code2},{code3}); wrote_nothing={no_dir and still_no_dir and error_path_clean}"


def case_ingest_never_breaks(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    enabled_config(repo)
    code, out, err = run_stdin([sys.executable, str(QL), "control-ingest", "--event", "SessionStart",
                                "--cwd", str(repo)], "utter garbage {{{ not json", repo)
    log = ctl.ingest_error_log(repo)
    # Malformed stdin degrades to an empty payload (event still recorded) or a
    # logged error — either way exit code MUST be 0.
    ok = code == 0
    return ok, f"exit={code}; log_exists={log.is_file()}; out={out.strip()[:60]!r}; err={err.strip()[:60]!r}"


def case_shim_disabled_and_guard(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    (repo / "scripts").mkdir()
    for src in (ROOT / "scripts").glob("quality_loop*.py"):
        (repo / "scripts" / src.name).write_bytes(src.read_bytes())
    # Disabled: shim exits 0 and writes nothing.
    code1, _, _ = run_stdin([sys.executable, str(SHIM), "SessionStart"],
                            json.dumps({"cwd": str(repo)}), repo)
    wrote_nothing = not (repo / ".quality-loop" / "control").exists()
    # Enabled + autostart, with a HEALTHY server answering /healthz for this
    # root -> no second spawn (server.log is only created by a spawn attempt).
    ctl.index_all(repo)
    httpd, port = _start_server(repo)
    try:
        enabled_config(repo, autostart=True, port=port)
        ctl._ensure_control_dir(repo)
        state = {"pid": os.getpid(), "port": port, "root": str(repo)}
        ctl.server_state_path(repo).write_text(json.dumps(state))
        code2, _, _ = run_stdin([sys.executable, str(SHIM), "SessionStart"],
                                json.dumps({"cwd": str(repo), "session_id": "s-guard"}), repo)
        no_spawn = not (ctl.control_dir(repo) / "server.log").exists()
    finally:
        httpd.shutdown()
        httpd.server_close()
    conn = ctl.open_db(repo)
    n_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.close()
    # A recycled-but-alive foreign pid with NO responsive server must NOT
    # suppress autostart: _server_running is healthz-based, not pid-based.
    stale = {"pid": os.getpid(), "port": port, "root": str(repo)}
    ctl.server_state_path(repo).write_text(json.dumps(stale))
    code3, out3, _ = run_stdin(
        [sys.executable, "-c",
         "import sys, json; sys.path.insert(0, sys.argv[1]); "
         "import importlib.util; spec = importlib.util.spec_from_file_location('shim', sys.argv[2]); "
         "shim = importlib.util.module_from_spec(spec); spec.loader.exec_module(shim); "
         "from pathlib import Path; print(shim._server_running(Path(sys.argv[3])))",
         str(repo / "scripts"), str(SHIM), str(repo)],
        "", repo)
    stale_not_running = out3.strip() == "False"
    ok = (code1 == 0 and wrote_nothing and code2 == 0 and no_spawn
          and n_events == 1 and code3 == 0 and stale_not_running)
    return ok, f"disabled=({code1},{wrote_nothing}); healthy_no_spawn={no_spawn}; events={n_events}; stale_pid_not_running={stale_not_running}"


def case_shim_autostarts_server(tmp: Path) -> tuple[bool, str]:
    repo = make_repo(tmp)
    claude_dir(tmp, repo)
    (repo / "scripts").mkdir()
    for src in (ROOT / "scripts").glob("quality_loop*.py"):
        (repo / "scripts" / src.name).write_bytes(src.read_bytes())
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    enabled_config(repo, autostart=True, port=port)
    code, _, _ = run_stdin([sys.executable, str(SHIM), "SessionStart"],
                           json.dumps({"cwd": str(repo), "session_id": "s-auto"}), repo)
    health = None
    try:
        for _ in range(40):
            time.sleep(0.25)
            if ctl.server_state_path(repo).is_file():
                try:
                    health, _ = get_json(f"http://127.0.0.1:{port}/healthz")
                    break
                except (urllib.error.URLError, ConnectionError, OSError):
                    continue
    finally:
        state = ctl.server_state(repo)
        if state is None:
            # Slow-start straggler: give it one more beat so a late-arriving
            # server is killed rather than leaked past the eval.
            time.sleep(1.5)
            state = ctl.server_state(repo)
        if state:
            os.kill(int(state["pid"]), 15)
    ok = code == 0 and health == 200
    return ok, f"exit={code}; healthz={health}; port={port}"


# ---------------------------------------------------------------------------
# Config + install cases
# ---------------------------------------------------------------------------

def case_check_config_control_plane(tmp: Path) -> tuple[bool, str]:
    base = json.loads((ROOT / "assets" / "quality-loop.config.example.json").read_text())
    good = tmp / "good.json"
    good.write_text(json.dumps(base))
    code_good, _, _ = run_stdin([sys.executable, str(QL), "check-config", str(good)], "", ROOT)
    bad_cfg = dict(base)
    bad_cfg["control_plane"] = {"enabled": "yes", "port": 80, "prot": 1,
                                "retention_days": 0,
                                "prices": {"m": {"x": -1}, "n": {"input_per_mtok_typo": 3.0}}}
    bad = tmp / "bad.json"
    bad.write_text(json.dumps(bad_cfg))
    code_bad, _, err = run_stdin([sys.executable, str(QL), "check-config", str(bad)], "", ROOT)
    wanted = ["unknown key: 'prot'", "enabled must be a boolean", "port must be an integer",
              "retention_days must be a positive integer", "non-negative number",
              "unknown price key: 'input_per_mtok_typo'"]
    hits = [w for w in wanted if w in err]
    ok = code_good == 0 and code_bad == 1 and len(hits) == len(wanted)
    return ok, f"good={code_good}; bad={code_bad}; matched={len(hits)}/{len(wanted)}"


def case_installer_ships_control_plane(tmp: Path) -> tuple[bool, str]:
    """v6: the control plane is an OPT-IN add-on — a default install copies no
    control module/shim/dashboard and wires no control hooks; only
    --with-control-plane ships and wires the lot."""
    plain = tmp / "plain"
    plain.mkdir()
    code0, _, _ = run_stdin([sys.executable, str(ROOT / "scripts" / "install.py"),
                             "--target", str(plain), "--host", "claude-code"], "", ROOT)
    settings0 = json.loads((plain / ".claude" / "settings.json").read_text())
    default_clean = (not (plain / "scripts" / "quality_loop_control.py").is_file()
                     and not (plain / "hosts" / "claude-code" / "control_plane.py").is_file()
                     and not (plain / "assets" / "control-plane" / "dashboard.html").is_file()
                     and "control_plane.py" not in json.dumps(settings0.get("hooks", {})))
    target = tmp / "target"
    target.mkdir()
    code, out, err = run_stdin([sys.executable, str(ROOT / "scripts" / "install.py"),
                                "--target", str(target), "--host", "claude-code",
                                "--with-control-plane"], "", ROOT)
    settings = json.loads((target / ".claude" / "settings.json").read_text())
    session_end = settings.get("hooks", {}).get("SessionEnd", [])
    start_cmds = json.dumps(settings.get("hooks", {}).get("SessionStart", []))
    ok = (code0 == 0 and default_clean and code == 0
          and (target / "scripts" / "quality_loop_control.py").is_file()
          and (target / "hosts" / "claude-code" / "control_plane.py").is_file()
          and (target / "assets" / "control-plane" / "dashboard.html").is_file()
          and len(session_end) >= 1 and "control_plane.py" in start_cmds)
    return ok, (f"default=(exit={code0}, clean={default_clean}); "
                f"opt_in=(exit={code}, session_end={len(session_end)}); err={err.strip()[:80]!r}")


CASES = [
    ("DB init is idempotent, WAL, and self-gitignored", case_db_init_idempotent),
    ("transcript indexing captures exact tokens, model, title, timestamps", case_transcript_tokens_exact),
    ("tool calls indexed with targets; results set ok/error status", case_tool_calls_and_status),
    ("incremental reindex adds only new lines; full rescan never duplicates", case_incremental_no_duplicates),
    ("malformed transcript lines are counted and skipped, never crash", case_malformed_lines_skipped),
    ("sidechain/subagent calls attributed to their agent", case_sidechain_attribution),
    ("summary line overrides first-prompt session title", case_summary_title_overrides),
    ("records ingest as record/review/decision/plan/escalation/models_used artifacts", case_record_artifacts),
    ("memory lessons and progress ingest as artifacts", case_memory_and_progress),
    ("spend aggregates exactly; user prices yield USD, absent prices yield None", case_spend_math_and_prices),
    ("all API endpoints return valid JSON with correct codes", case_api_endpoints),
    ("server binds 127.0.0.1 only and rejects non-GET with 405", case_server_read_only_and_local),
    ("dashboard is self-contained (no external refs) and served themed", case_dashboard_self_contained),
    ("review findings become first-class finding artifacts with severity", case_findings_first_class),
    ("delegations.jsonl ingests as artifacts; garbage counted; idempotent", case_delegations_ledger),
    ("delegation joins its session with exact tokens; non-match is unmatched", case_delegation_session_join),
    ("task timeline assembles every artifact kind in order; unknown -> None", case_task_timeline),
    ("loop metrics compute exact KPIs; empty DB serves 200 zeros", case_loop_metrics),
    ("control-report emits markdown + json; unknown task exits 2", case_control_report_cli),
    ("tool-call targets redact secrets before storage; benign intact", case_tool_target_redaction),
    ("delegation with session_id joins directly; unindexed never guessed; duplicate id flagged", case_delegation_direct_session_id),
    ("unparseable delegation ts is counted unjoinable, never a dist-0 match", case_delegation_unjoinable_ts),
    ("fallback delegation join is one-to-one; nearest wins, no double count", case_delegation_one_to_one),
    ("droid wrapper runs become droid_run events, not 0-token model calls", case_droid_runs_are_events),
    ("renamed usage keys turn the zero-usage drift canary nonzero everywhere", case_zero_usage_canary),
    ("retention_days prunes every table by one cutoff; no resurrection", case_retention_prunes_all_tables),
    ("schema bump exports hook events to an append-safe backup first", case_schema_bump_backs_up_events),
    ("control-report --arm-costs emits bench-arm cost JSON; --since filters", case_arm_costs_query),
    ("control-ingest records events and SessionEnd closes the session", case_ingest_event_roundtrip),
    ("ingest is a no-op when control_plane is absent or disabled", case_ingest_disabled_noop),
    ("ingest exits 0 on garbage stdin (never breaks a session)", case_ingest_never_breaks),
    ("shim: disabled writes nothing; live pidfile prevents double start", case_shim_disabled_and_guard),
    ("shim autostarts a reachable server when enabled (then torn down)", case_shim_autostarts_server),
    ("check-config accepts a valid control_plane block and names every bad field", case_check_config_control_plane),
    ("installer ships the control plane only with --with-control-plane", case_installer_ships_control_plane),
]


def main() -> int:
    failures = 0
    for name, fn in CASES:
        with tempfile.TemporaryDirectory() as td:
            # Hermetic per case: point every host-side source at the tempdir so
            # the suite never reads the developer's real ~/.claude, ~/.codex,
            # or ~/.factory data (cases that need a source create their own).
            saved = {var: os.environ.get(var) for var in
                     ("CLAUDE_CONFIG_DIR", "CODEX_SESSIONS_DIR", "DROID_WRAPPER_LOG")}
            os.environ["CODEX_SESSIONS_DIR"] = str(Path(td) / "no-codex-sessions")
            os.environ["DROID_WRAPPER_LOG"] = str(Path(td) / "no-droid-log.jsonl")
            try:
                ok, detail = fn(Path(td))
            except Exception as exc:  # noqa: BLE001
                ok, detail = False, f"exception: {exc!r}"
            finally:
                for var, value in saved.items():
                    if value is None:
                        os.environ.pop(var, None)
                    else:
                        os.environ[var] = value
        print(f"[{PASS if ok else FAIL}] {name}\n        {detail}")
        failures += 0 if ok else 1
    print(f"\n{len(CASES) - failures}/{len(CASES)} control-plane eval cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
