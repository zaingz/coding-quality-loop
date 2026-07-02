#!/usr/bin/env python3
"""Eval harness for the Honcho lessons-store adapter.

Covers three contracts:

  1. Missing SDK / missing config -> transparent fallback to files backend.
     No exception, exit 0, files-backend output is what the user sees.
  2. Configured Honcho with a fake in-process SDK -> commit dual-writes to
     files AND to the fake session; recall pulls the tagged messages back and
     re-ranks them with the same scorer the files backend uses.
  3. Boundary redaction: even if a caller sneaks an unredacted secret past
     `normalize_lesson`, the Honcho commit path re-runs `redact()` before
     egress so the raw token never leaves the process.

Dependency-free (no real Honcho SDK); injects a fake `honcho` module into
sys.modules so the lazy import inside the adapter picks it up. Mirrors the
existing evals/run_memory_evals.py style.

Run: python3 evals/run_honcho_evals.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "quality_loop.py"
sys.path.insert(0, str(ROOT / "scripts"))

PASS = "PASS"
FAIL = "FAIL"


# ------------------------------------------------------------------------------
# Fake Honcho SDK
# ------------------------------------------------------------------------------
# We install this module under `sys.modules["honcho"]` before the adapter's lazy
# import runs. It records every posted message so tests can assert dual-write.


class _FakeSession:
    def __init__(self, name: str) -> None:
        self.name = name
        self.messages: list[dict] = []

    def add_messages(self, msgs):
        self.messages.extend(list(msgs))

    def search(self, query: str):
        # Simplest useful behavior: return everything we have; the adapter
        # re-ranks with the shared scorer so this is faithful to the contract.
        return list(self.messages)


class _FakePeer:
    def __init__(self, peer_id: str, sessions: dict) -> None:
        self.peer_id = peer_id
        self._sessions = sessions

    def session(self, name: str) -> _FakeSession:
        return self._sessions.setdefault(name, _FakeSession(name))


class _FakeHoncho:
    _sessions: dict = {}

    def __init__(self, workspace_id: str, api_key: str | None = None, base_url: str | None = None) -> None:
        # Real Honcho SDK accepts api_key as an optional kwarg; keyless local
        # mode omits it entirely. Mirror that here so we can assert on presence.
        self.api_key = api_key
        self.workspace_id = workspace_id
        self.base_url = base_url

    def peer(self, peer_id: str) -> _FakePeer:
        return _FakePeer(peer_id, _FakeHoncho._sessions)


def _install_fake_honcho() -> None:
    module = types.ModuleType("honcho")
    module.Honcho = _FakeHoncho  # type: ignore[attr-defined]
    sys.modules["honcho"] = module
    # Reset shared session state between cases so each test is independent.
    _FakeHoncho._sessions = {}


def _uninstall_fake_honcho() -> None:
    sys.modules.pop("honcho", None)


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------


def _write_config(tmp: Path, use_honcho: bool) -> Path:
    cfg = {
        "memory": {
            "lessons_store": "honcho" if use_honcho else "files",
            "honcho": {"workspace_id": "ws-test", "peer_id": "peer-test", "session_template": "ql-lessons"},
        }
    }
    path = tmp / "ql.config.json"
    path.write_text(json.dumps(cfg))
    return path


def _write_record(tmp: Path, lesson_text: str) -> Path:
    record = {
        "task_id": "t-honcho",
        "goal": "test honcho adapter",
        "risk_tier": "medium",
        "harness_update": lesson_text,
    }
    path = tmp / "record.json"
    path.write_text(json.dumps(record))
    return path


def _run_cli(tmp: Path, *args: str, env: dict | None = None) -> tuple[int, str, str]:
    import os
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(tmp),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, **(env or {})},
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ------------------------------------------------------------------------------
# Cases
# ------------------------------------------------------------------------------


def case_missing_sdk_falls_back_to_files(tmp: Path) -> tuple[bool, str]:
    """No honcho module installed; adapter must degrade silently to files."""
    _uninstall_fake_honcho()
    cfg = _write_config(tmp, use_honcho=True)
    rec = _write_record(tmp, "Prefer stdlib decimal over binary float for rounding")
    rc1, out1, err1 = _run_cli(tmp, "memory-commit", str(rec), "--config", str(cfg),
                                env={"HONCHO_API_KEY": "fake"})
    rc2, out2, err2 = _run_cli(tmp, "memory-recall", "--goal", "rounding decimal",
                                "--config", str(cfg), env={"HONCHO_API_KEY": "fake"})
    ok = rc1 == 0 and rc2 == 0 and "decimal" in out2 and "SDK not installed" in err2
    return ok, f"rc1={rc1} rc2={rc2}; out2={out2!r}; err2={err2.strip()!r}"


def case_honcho_dual_write(tmp: Path) -> tuple[bool, str]:
    """With the fake SDK, commit must write to files AND to Honcho session.

    We invoke commit/recall in-process (not via CLI subprocess) so the fake
    module in sys.modules is visible to the adapter's lazy import.
    """
    _install_fake_honcho()
    # Re-import in a clean module state to pick up any code changes.
    for mod in ("quality_loop", "quality_loop_memory", "quality_loop_honcho"):
        sys.modules.pop(mod, None)
    import quality_loop_honcho as adapter  # noqa: E402
    import quality_loop_memory as qlmem     # noqa: E402

    mem_dir = tmp / ".quality-loop" / "memory"
    mem_dir.mkdir(parents=True)
    row = qlmem.normalize_lesson(
        {"lesson": "Retry on 429 idempotent", "kind": "convention", "risk_tier": "medium",
         "scope_globs": ["src/**"], "keywords": ["retry", "429"], "source_task_id": "t1"},
        "2026-07-02",
    )
    qlmem.append_lesson(mem_dir, row)

    backend = adapter.HonchoBackend({
        "lessons_store": "honcho",
        "honcho": {"workspace_id": "ws-test", "peer_id": "peer-test"},
    })
    # Prime the adapter's env-derived api_key without touching the process env
    # for the whole suite.
    backend.cfg["api_key"] = "fake-key"
    backend.client, backend.error = adapter._client(backend.cfg)
    if not backend.available:
        return False, f"backend not available: {backend.error!r}"
    posted = backend.commit([row])
    recalled = backend.recall("retry 429", ["src/api.py"], "medium", 1500)
    ok = (
        posted == 1
        and len(recalled) == 1
        and recalled[0]["lesson"] == "Retry on 429 idempotent"
        and recalled[0]["kind"] == "convention"
        and recalled[0]["risk_tier"] == "medium"
    )
    _uninstall_fake_honcho()
    return ok, f"posted={posted}; recalled={recalled}"


def case_boundary_redaction_before_egress(tmp: Path) -> tuple[bool, str]:
    """A caller passes an unredacted lesson to commit(); adapter must redact
    before posting to Honcho. This is the defense-in-depth check."""
    _install_fake_honcho()
    for mod in ("quality_loop", "quality_loop_memory", "quality_loop_honcho"):
        sys.modules.pop(mod, None)
    import quality_loop_honcho as adapter  # noqa: E402

    backend = adapter.HonchoBackend({
        "lessons_store": "honcho",
        "honcho": {"workspace_id": "ws-test", "peer_id": "peer-test"},
    })
    backend.cfg["api_key"] = "fake-key"
    backend.client, backend.error = adapter._client(backend.cfg)
    if not backend.available:
        return False, f"backend not available: {backend.error!r}"

    # Deliberately bypass normalize_lesson to simulate a caller mistake.
    dirty = {
        "id": "abc",
        "created": "2026-07-02",
        "source_task_id": "t2",
        "kind": "convention",
        "risk_tier": "high",
        "scope_globs": ["**"],
        "keywords": ["sk-live-abcd1234567890abcdef1234567890", "api", "key"],
        "lesson": "Do not commit sk-live-abcd1234567890abcdef1234567890",
        "hits": 0,
    }
    backend.commit([dirty])

    # Inspect the fake session.
    sessions = adapter._client.__globals__["sys"].modules["honcho"].Honcho._sessions
    posted_messages = []
    for sess in sessions.values():
        posted_messages.extend(sess.messages)
    egressed = json.dumps(posted_messages)
    ok = (
        "sk-live-abcd" not in egressed
        and "abcd1234567890abcdef1234567890" not in egressed
        and "[REDACTED]" in egressed
    )
    _uninstall_fake_honcho()
    return ok, f"egressed={egressed[:200]}..."


def case_local_mode_needs_no_api_key(tmp: Path) -> tuple[bool, str]:
    """A self-hosted Honcho at localhost with AUTH_USE_AUTH=false accepts
    keyless connections. The adapter must build a client with no api_key kwarg
    when the base_url is local and no HONCHO_API_KEY is set."""
    _install_fake_honcho()
    for mod in ("quality_loop", "quality_loop_memory", "quality_loop_honcho"):
        sys.modules.pop(mod, None)
    # Force env to be empty for this case so we exercise the true zero-config path.
    import os
    saved = os.environ.pop("HONCHO_API_KEY", None)
    try:
        import quality_loop_honcho as adapter  # noqa: E402
        backend = adapter.HonchoBackend({
            "lessons_store": "honcho",
            "honcho": {"workspace_id": "ws-local", "peer_id": "peer-local",
                       "base_url": "http://localhost:8000"},
        })
        ok = (
            backend.available
            and backend.cfg["api_key"] == ""
            and backend.cfg["base_url"] == "http://localhost:8000"
            and backend.client is not None
            # Fake SDK captures kwargs on init; api_key must NOT have been sent.
            and getattr(backend.client, "api_key", None) is None
        )
        detail = f"available={backend.available}; error={backend.error!r}; api_key={getattr(backend.client, 'api_key', 'MISSING')!r}"
    finally:
        if saved is not None:
            os.environ["HONCHO_API_KEY"] = saved
        _uninstall_fake_honcho()
    return ok, detail


def case_cloud_url_without_key_refuses(tmp: Path) -> tuple[bool, str]:
    """Safety rail: a non-local base_url with no api_key must NOT connect.

    Prevents accidentally shipping a keyless request to api.honcho.dev (which
    would 401 in prod but could leak lesson content in a misconfigured proxy).
    """
    _install_fake_honcho()
    for mod in ("quality_loop", "quality_loop_memory", "quality_loop_honcho"):
        sys.modules.pop(mod, None)
    import os
    saved = os.environ.pop("HONCHO_API_KEY", None)
    try:
        import quality_loop_honcho as adapter  # noqa: E402
        backend = adapter.HonchoBackend({
            "lessons_store": "honcho",
            "honcho": {"workspace_id": "ws", "peer_id": "peer",
                       "base_url": "https://api.honcho.dev"},
        })
        ok = (
            not backend.available
            and backend.error is not None
            and "HONCHO_API_KEY not set" in backend.error
            and "managed Honcho requires" in backend.error
        )
        detail = f"available={backend.available}; error={backend.error!r}"
    finally:
        if saved is not None:
            os.environ["HONCHO_API_KEY"] = saved
        _uninstall_fake_honcho()
    return ok, detail


def case_client_accepts_raw_cfg(tmp: Path) -> tuple[bool, str]:
    """Regression: `_client` used to KeyError on a raw honcho config block
    because it assumed keys populated by `_resolve_config`. Direct callers
    (docs, ad-hoc scripts, tests) should not have to know about that internal
    coupling. Feeding `_client` a bare `{'workspace_id': ..., 'peer_id': ...}`
    must succeed under the same zero-config local defaults."""
    _install_fake_honcho()
    for mod in ("quality_loop", "quality_loop_memory", "quality_loop_honcho"):
        sys.modules.pop(mod, None)
    import os
    saved_key = os.environ.pop("HONCHO_API_KEY", None)
    saved_url = os.environ.pop("HONCHO_BASE_URL", None)
    try:
        import quality_loop_honcho as adapter  # noqa: E402
        # Bare cfg: no base_url, no api_key, only ids. Must not raise.
        client, err = adapter._client({"workspace_id": "w", "peer_id": "p"})
        ok_zero = client is not None and err is None and getattr(client, "api_key", None) is None
        # And bare cfg with a cloud URL must still refuse keyless.
        client2, err2 = adapter._client({
            "workspace_id": "w", "peer_id": "p", "base_url": "https://api.honcho.dev"
        })
        ok_refuse = client2 is None and err2 is not None and "managed Honcho" in err2
        # And a raw cfg missing ids returns the correct error, not KeyError.
        client3, err3 = adapter._client({})
        ok_missing = client3 is None and err3 is not None and "workspace_id" in err3
        ok = ok_zero and ok_refuse and ok_missing
        detail = f"zero_ok={ok_zero} refuse_ok={ok_refuse} missing_ok={ok_missing} err={err!r}"
    finally:
        if saved_key is not None:
            os.environ["HONCHO_API_KEY"] = saved_key
        if saved_url is not None:
            os.environ["HONCHO_BASE_URL"] = saved_url
        _uninstall_fake_honcho()
    return ok, detail


def case_files_only_when_config_omits_honcho(tmp: Path) -> tuple[bool, str]:
    """No config passed / lessons_store != honcho -> files backend, no notice."""
    _uninstall_fake_honcho()
    rec = _write_record(tmp, "Prefer deletion when possible")
    rc1, _, err1 = _run_cli(tmp, "memory-commit", str(rec))
    rc2, out2, err2 = _run_cli(tmp, "memory-recall", "--goal", "deletion")
    ok = rc1 == 0 and rc2 == 0 and "honcho" not in err1.lower() and "honcho" not in err2.lower() and "deletion" in out2
    return ok, f"rc1={rc1} rc2={rc2}; err1={err1!r}; err2={err2!r}"


# ------------------------------------------------------------------------------
# Driver
# ------------------------------------------------------------------------------


CASES = [
    ("missing sdk falls back to files", case_missing_sdk_falls_back_to_files),
    ("honcho dual-write & recall", case_honcho_dual_write),
    ("boundary redaction before egress", case_boundary_redaction_before_egress),
    ("local self-hosted mode needs no api key", case_local_mode_needs_no_api_key),
    ("cloud base_url without api key refuses to connect", case_cloud_url_without_key_refuses),
    ("_client accepts raw config without KeyError", case_client_accepts_raw_cfg),
    ("files-only when config omits honcho", case_files_only_when_config_omits_honcho),
]


def main() -> int:
    failures = 0
    for label, fn in CASES:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            try:
                ok, detail = fn(tmp)
            except Exception as exc:
                ok, detail = False, f"exception: {exc!r}"
        status = PASS if ok else FAIL
        if not ok:
            failures += 1
        print(f"{status}: {label}  {detail}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
