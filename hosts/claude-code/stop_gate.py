#!/usr/bin/env python3
"""Stop hook: block premature completion when outcome gates fail.

Closes the silent-evasion vector (GV1): the gate used to fire only at the
self-reported statuses ``package``/``done``, so an agent that finished real work
but never advanced its status could stop entirely ungated.

Decision table (evaluated top to bottom):
  - no record, no real loop state               -> allow (repo may not use the loop;
                                                   a bare install manifest never blocks)
  - no record BUT real loop state present       -> BLOCK (record deleted mid-loop)
    (config, runs/, progress.md, memory/, or a git tombstone of the record)
  - stop_hook_active                            -> allow (never re-block our own stop)
  - record unreadable                           -> BLOCK (corruption must not lift the gate)
  - escalated + non-empty escalation_reason     -> allow (explicit, auditable pause)
  - status in {package, done} + record CLOSED   -> allow (merged/archived record: unchanged
      (== base, no local modifications)            from base with nothing in flight; skips the
                                                   verify umbrella so a cloned/merged done record
                                                   does not re-execute its commands at every Stop)
  - status in {package, done} + fresh last-       -> allow (the SAME diff+status already passed the
      verified marker (diff + status unchanged)    full `verify` umbrella; skip the re-execution as
                                                   a pure latency win — any mismatch or unreadable
                                                   marker runs the umbrella exactly as it would today)
  - status in {package, done}                   -> run `verify` umbrella; block on failure
  - {verify, review, retrospect, reasonless escalated}
      + dirty tree                              -> run `verify-gates`; block on failure
  - intake/explore/plan/implement/iterating     -> allow (mid-work stop)

Rationale for allowing the earlier statuses: a mid-work turn must be able to
stop to ask the user a question. The merge boundary is anchored separately by
CI (`verify --require-terminal`), so the only residual local evasion — parking
at `implement` with a dirty tree — stays visible in the record and is caught on
the PR. It is never silently ungated end-to-end.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from hooklib import json_input, project_root

# Statuses whose stop is gated whenever the working tree carries real changes.
# "escalated" appears here so that escalation WITHOUT a recorded reason gets no
# free pass — the reasoned valve is handled before this set is consulted.
DIRTY_GATED_STATUSES = {"verify", "review", "retrospect", "escalated"}
# Statuses that are always gated (the self-reported completion boundary).
TERMINAL_GATED_STATUSES = {"package", "done"}


def _record_path(root: Path) -> Path | None:
    env = os.environ.get("QUALITY_LOOP_RECORD")
    candidates = [Path(env)] if env else []
    candidates += [root / ".quality-loop" / "agent-record.json", root / "agent-record.json"]
    return next((p for p in candidates if p and p.is_file()), None)


def _record(path: Path) -> dict[str, Any] | None:
    """Parse the record; None means present-but-unreadable, which fails CLOSED.

    A corrupt/undecodable record must block, not traceback: an uncaught
    exception exits non-2 and Claude Code treats that as allow, so one
    corrupted byte would otherwise reopen the silent-evasion vector.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _loop_was_active(root: Path) -> bool:
    """True only on evidence a TASK actually ran and its record then went
    missing: run artifacts, or a git tombstone of a deleted record. Neither the
    bare .quality-loop/ directory (every v6 install writes an install-manifest
    there) NOR the mere presence of quality-loop.config.json is a signal — the
    installer steers every new user into creating that config, so treating it as
    'a task is in flight' would block every record-less stop on a fresh install,
    the exact first-contact trap v6 set out to remove. An evader who deletes a
    real record leaves a tombstone (committed record) or run/progress artifacts;
    a fresh install leaves neither."""
    qdir = root / ".quality-loop"
    if any((qdir / name).exists() for name in ("runs", "progress.md", "memory")):
        return True
    # Deletion tombstone: git still sees a tracked record deleted from the tree.
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--",
             ".quality-loop/agent-record.json", "agent-record.json"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return proc.returncode == 0 and any("D" in line[:2] for line in proc.stdout.splitlines())


def _resolve_base_ref(root: Path) -> str | None:
    """The base ref the closed-record check compares against: QUALITY_LOOP_BASE
    when set, else the config `base` key (both are explicit operator choices),
    else the first existing ORIGIN ref (origin/main -> origin/master). Local
    main/master are deliberately NOT closure-eligible: in a solo no-origin repo
    the current branch is trivially byte-identical to itself, which would make
    every committed terminal record 'closed' and skip the umbrella in the one
    environment with no CI anchor. None when nothing resolves, which keeps the
    record 'not closed' so the full gate still runs — a solo author is not a
    teammate on a clone."""
    env = os.environ.get("QUALITY_LOOP_BASE")
    if env:
        return env
    try:
        cfg = json.loads((root / "quality-loop.config.json").read_text(encoding="utf-8"))
        cfg_base = cfg.get("base")
        if isinstance(cfg_base, str) and cfg_base.strip():
            return cfg_base.strip()
    except (OSError, ValueError):
        pass
    for ref in ("origin/main", "origin/master"):
        try:
            proc = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", ref + "^{commit}"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            return None
        if proc.returncode == 0:
            return ref
    return None


def _record_is_closed(root: Path, record: Path) -> bool:
    """True when the terminal-status record is a merged/archived artifact rather
    than an active task: it has NO uncommitted local modifications AND its
    committed content is byte-identical to its content at the resolved base.

    This kills the cloned-repo trap — a teammate who clones a repo whose `done`
    record is already committed and merged would otherwise have the Stop hook
    re-execute every recorded command on a machine that did no work. Any local
    change to the record (dirty), an untracked record, or a record that differs
    from base keeps the full verify-umbrella behavior. Fails to 'not closed'
    (safe: keep gating) whenever git cannot answer."""
    try:
        rel = record.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return False

    def _git(*args: str) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                ["git", "-C", str(root), *args],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            return None

    # 1. No uncommitted modification of the record (tracked + clean). Any output
    #    (untracked '??', modified ' M', staged) means the task is in flight.
    status = _git("status", "--porcelain", "--", rel)
    if status is None or status.returncode != 0 or status.stdout.strip():
        return False
    base = _resolve_base_ref(root)
    if not base:
        return False
    head_blob = _git("show", f"HEAD:{rel}")
    base_blob = _git("show", f"{base}:{rel}")
    if head_blob is None or base_blob is None:
        return False
    if head_blob.returncode != 0 or base_blob.returncode != 0:
        return False
    return head_blob.stdout == base_blob.stdout


def _canonical_diff_sha256(base: str, root: Path) -> str | None:
    """Current canonical diff hash for ``base``, computed by Lane 1's shared
    helper in quality_loop_reality — the SAME hash attest-review, review
    freshness, and the `verify` umbrella use, so the marker written by `verify`
    and the value checked here can never diverge on hash semantics.

    Imported lazily from the record repo's own scripts dir (the copy the gates
    run from), preferring ``canonical_diff_sha256`` and falling back to the
    long-standing ``diff_sha256(..., exclude_record_dir=True)`` it wraps. Any
    failure — module or helper absent, git error, unreadable tree — returns
    None so the caller fails SAFE toward re-running the full umbrella."""
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        import quality_loop_reality as qlr  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - a missing/broken shim must not lift the gate
        return None
    try:
        fn = getattr(qlr, "canonical_diff_sha256", None)
        if callable(fn):
            result = fn(base, root)
        else:
            result = qlr.diff_sha256(base, root, exclude_record_dir=True)
    except (Exception, SystemExit):
        # SystemExit is included on purpose: the reality helper's git wrapper
        # (run_git) exits on a bad/unresolvable base ref. A bare `except
        # Exception` would let that SystemExit escape, the hook would exit
        # non-zero, and Claude Code treats a non-2 exit as ALLOW — the exact
        # unsafe direction. Swallow it and fall through to the full umbrella.
        return None
    return result if isinstance(result, str) and result else None


def _verified_clean(root: Path, status: str, record: Path) -> str | None:
    """When ``.quality-loop/last-verified.json`` proves this exact diff, record
    content, and status already passed the full `verify` umbrella, return its
    ``verified_at`` stamp so the terminal stop can skip re-execution. Returns
    None (run the umbrella) on any missing / unreadable / mismatched marker.

    This is purely a latency optimization: it must never allow a stop the full
    umbrella would have blocked, so every uncertain path falls through to the
    umbrella. Three things must all match:

    - the canonical DIFF hash, recomputed against the marker's own base (a moved
      base ref or any code change forces the umbrella); and
    - the RECORD content hash — load-bearing, because the umbrella verdict
      depends on the record (it re-executes commands_run and checks AC
      coverage) and the record lives under .quality-loop/, which the canonical
      diff EXCLUDES. Without this, a post-verify `record add-evidence` could
      append a failing pass-claim, flip the umbrella to FAIL, yet leave the
      diff hash + status unchanged and be skipped; and
    - the record ``status``.

    Scope, honestly: this only proves nothing changed since a passing verify.
    The marker is a plain file, so like every local gate input it is
    tamper-evident, not a boundary against a forging agent (which could rewrite
    the record it attests anyway). CI never reads the marker and re-executes
    unconditionally — it remains the anchor."""
    marker = root / ".quality-loop" / "last-verified.json"
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    recorded_hash = data.get("diff_sha256")
    recorded_record_hash = data.get("record_sha256")
    base = data.get("base")
    if (data.get("status") != status
            or not isinstance(recorded_hash, str) or not recorded_hash
            or not isinstance(recorded_record_hash, str) or not recorded_record_hash
            or not isinstance(base, str) or not base):
        return None
    try:
        current_record_hash = hashlib.sha256(record.read_bytes()).hexdigest()
    except OSError:
        return None
    if current_record_hash != recorded_record_hash:
        return None
    current = _canonical_diff_sha256(base, root)
    if current is None or current != recorded_hash:
        return None
    verified_at = data.get("verified_at")
    return verified_at if isinstance(verified_at, str) and verified_at else "an earlier verify"


def _tree_is_dirty(root: Path) -> bool:
    """Cheap working-tree diff check: any tracked change or untracked (non-ignored)
    file. Mirrors the change set `verify-gates --against-diff` reasons over.

    Fails OPEN (not dirty) when git is broken or absent: a session hook must not
    lock an agent out of stopping because the environment lost git. The merge
    boundary stays anchored by CI, which runs the gates from a pinned copy."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return proc.returncode == 0 and bool(proc.stdout.strip())


# Reused on every gate-failure block so each branch names the same exits.
REMEDY = (
    "Three legitimate ways forward:\n"
    "  1. Keep working — resolve the findings below.\n"
    "  2. Advance to package/done and pass the gates.\n"
    "  3. Set status \"escalated\" with a non-empty escalation_reason for an auditable pause.\n"
)


def _timeout_hint(output: str) -> str:
    """Point at QUALITY_LOOP_TIMEOUT when the failure looks like a timeout."""
    lowered = output.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return (
            "\nIf evidence commands time out because the suite is legitimately slow, set "
            "QUALITY_LOOP_TIMEOUT=<seconds> to raise the per-command timeout and retry."
        )
    return ""


def _run_gates(root: Path, record: Path, terminal: bool) -> tuple[int, str]:
    """Run the gates: terminal statuses get the full `verify` umbrella (evidence
    re-execution + AC coverage included); the dirty-tree branch keeps the faster
    diff-grounded `verify-gates`. `--base` is passed only when QUALITY_LOOP_BASE
    is set, so the script's merge-base auto-resolution applies otherwise. The
    child inherits our env, which forwards QUALITY_LOOP_TIMEOUT when set."""
    cmd = [sys.executable, str(root / "scripts" / "quality_loop.py")]
    cmd += ["verify", str(record)] if terminal else ["verify-gates", str(record), "--against-diff"]
    base = os.environ.get("QUALITY_LOOP_BASE")
    if base:
        cmd += ["--base", base]
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(root),
        check=False,
    )
    output = (proc.stdout + proc.stderr).strip()
    detail = output[:4000]
    if proc.returncode != 0:
        detail += _timeout_hint(output)
    return proc.returncode, detail


def _record_removed_by_committed_teardown(root: Path) -> bool:
    """True only when the live record's absence is COMMITTED teardown (SKILL.md
    PACKAGE: archive to docs/records/, remove the live file), never a mid-loop
    deletion: git must affirmatively report that HEAD does not contain
    .quality-loop/agent-record.json AND that the working tree is clean. Any git
    failure (no git, no HEAD, broken repo) returns False so the missing-record
    block stays — this helper only ever RELAXES toward allowing a stop, so it
    fails closed, unlike _tree_is_dirty which fails open for the opposite
    reason."""
    try:
        in_head = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "--name-only", "HEAD",
             "--", ".quality-loop/agent-record.json"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False,
        )
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return (in_head.returncode == 0 and not in_head.stdout.strip()
            and status.returncode == 0 and not status.stdout.strip())


def _block(reason: str) -> int:
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def main() -> int:
    data = json_input()
    if data.get("stop_hook_active"):
        return 0
    root = project_root(data)
    record = _record_path(root)
    if record is None:
        # A repo that never ran the loop may stop freely. But if real loop
        # state exists without a record, the record was deleted mid-loop —
        # deletion must not lift the gate. (A fresh install's manifest alone
        # is NOT loop state: see _loop_was_active.)
        #
        # One legitimate exception: SKILL.md's PACKAGE teardown archives the
        # record to docs/records/ and REMOVES the live file. When that removal
        # is committed — git works, HEAD does not contain the record path, and
        # the working tree is affirmatively clean — the task is closed, not
        # evaded: the deletion itself survived review/CI. Any git failure or
        # any dirt keeps the block (fail-closed).
        if _loop_was_active(root) and not _record_removed_by_committed_teardown(root):
            return _block(
                "Quality Loop was active here (config or loop state exists) "
                "but no agent record was found — the record may have been deleted mid-loop. Restore it "
                "(e.g. git restore --source=HEAD -- .quality-loop/agent-record.json) or recreate it with "
                "python3 scripts/quality_loop.py init-record --goal \"<goal>\" before stopping. "
                "(A record archived by PACKAGE teardown — removal committed, tree clean — closes freely.)"
            )
        return 0
    parsed = _record(record)
    if parsed is None:
        return _block(
            "Quality Loop record exists but is unreadable (invalid JSON/encoding or not an object). "
            "Repair .quality-loop/agent-record.json before stopping — an unreadable record does not lift the gate."
        )
    status = str(parsed.get("status", ""))
    if status == "escalated":
        reason = parsed.get("escalation_reason")
        if isinstance(reason, str) and reason.strip():
            return 0
        # No recorded reason: the pause is not auditable, so treat it like any
        # other non-terminal status — gated below when the tree is dirty.

    if status in TERMINAL_GATED_STATUSES:
        if _record_is_closed(root, record) and not _tree_is_dirty(root):
            # Merged/archived record AND a clean working tree: this task is
            # CLOSED. Allow the stop and skip the verify umbrella so a cloned/
            # merged `done` record does not re-execute its recorded commands
            # here. The whole-tree check matters: an unchanged committed record
            # with NEW source edits is a fresh task riding a stale record, and
            # must run the full gate, not stop free.
            print(
                "quality-loop: record is at a terminal status, unchanged from the base, and the "
                "working tree is clean — treating the task as CLOSED and allowing the stop "
                "(skipping verify re-execution). A record that differs from base, or any local "
                "modification anywhere in the tree, still runs the full gate.",
                file=sys.stderr,
            )
            return 0
        verified_at = _verified_clean(root, status, record)
        if verified_at is not None:
            # The full `verify` umbrella already passed for this exact diff +
            # status (last-verified.json written by Lane 1's verify on PASS).
            # Skip the re-execution purely to save latency; a mismatch or any
            # unreadable marker fell through to the umbrella above.
            print(
                f"quality-loop: verified clean at {verified_at}; diff + record + status "
                "unchanged — skipping re-execution.",
                file=sys.stderr,
            )
            return 0
        rc, detail = _run_gates(root, record, terminal=True)
        if rc == 0:
            return 0
        cause = ""
        if rc == 2:
            cause = (
                "The verification runner itself failed (exit 2: crash, bad invocation, or missing "
                "scripts/quality_loop.py) — this is an environment problem, not gate findings. "
                "Restore the CQL scripts (run cql init or python3 scripts/install.py), then retry.\n"
            )
        return _block(
            cause
            + "Quality Loop stop gate failed; fix or record an explicit waiver before stopping.\n"
            + REMEDY
            + detail
        )

    if status in DIRTY_GATED_STATUSES and _tree_is_dirty(root):
        rc, detail = _run_gates(root, record, terminal=False)
        if rc == 0:
            return 0
        return _block(
            f"Quality Loop stop gate failed at status '{status}' with a dirty working tree. "
            + REMEDY
            + detail
        )

    # intake/explore/plan/implement/iterating (or verify/review with a clean tree):
    # allow the stop so the agent can pause mid-work to consult the user.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
