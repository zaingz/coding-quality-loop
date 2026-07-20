#!/usr/bin/env python3
"""Shared primitives for the Coding Quality Loop helper scripts.

This is the leaf module of the helper package: it imports nothing from its
siblings (``quality_loop``, ``quality_loop_memory``, ``quality_loop_reality``,
``quality_loop_routing``), so those modules can all depend on it without a
circular import. It holds the primitives that were previously duplicated or
star-coupled across the package:

  - lifecycle status-set constants (previously magic literals in ~6 sites)
  - one atomic write (previously three near-identical copies)
  - record load/save
  - secret redaction: ``redact`` + ``SECRET_PATTERNS`` + entropy helpers
  - test-weakening / test-path markers
  - one git subprocess wrapper (``git_capture`` non-raising, ``run_git`` raising)
  - ``has_evidence`` and ``_nonempty`` (deliberately different - see below)

Stdlib-only, portable, no network.
"""

from __future__ import annotations

import json
import math as _math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Lifecycle status sets
# ---------------------------------------------------------------------------
# Named once here instead of as repeated magic literals. Derived from the exact
# sets that gate behavior in quality_loop.verify_gates / check_record; changing
# any membership below changes gate behavior, so keep them exact.

# Terminal statuses: the loop is "closed" only here. Also the set the CI
# `verify --require-terminal` flag treats as an acceptably-closed loop.
TERMINAL_STATUSES = {"package", "done"}

# Implementation has begun (or later): the UNDERSTAND/minimality gates apply.
POST_IMPLEMENT_STATUSES = {"implement", "verify", "review", "package", "done", "iterating"}

# minimality_decision is required from the minimality gate onward.
MINIMALITY_REQUIRED_STATUSES = POST_IMPLEMENT_STATUSES | {"minimality_gate", "retrospect"}

# Past INTAKE: acceptance_criteria / verification_plan warnings apply.
POST_INTAKE_STATUSES = {"plan", "minimality_gate", "implement", "verify", "review", "package", "retrospect", "done"}

# Review evidence is only accepted once the record reaches these states.
REVIEW_READY_STATUSES = {"review", "package", "done"}


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------
SECRET_PATTERNS = [
    re.compile(
        r"(?i)(api[_-]?key|secret|token|password|passwd|pwd|credential|private[_-]?key)"
        r"\s*[:=]\s*['\"][^'\"]{8,}['\"]"
    ),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    # OpenAI hyphenated key families (sk-live-*, sk-proj-*, sk-test-*, sk-svcacct-*).
    # The pre-existing short sk- pattern misses these because its char class
    # excludes hyphens; without this line a hyphenated key slips through the
    # redactor and can be persisted verbatim into the lessons memory (proven
    # in review). Ordering matters: keep this above the shorter sk- fallback
    # only if you tighten that pattern later; the union of both is safe.
    re.compile(r"sk-(?:live|proj|test|svcacct)-[A-Za-z0-9_-]{16,}"),
    # Unquoted assignment - the most common .env/shell/YAML leak shape - with a
    # placeholder guard that skips only obvious stubs (REPLACE_ME / angle-bracket
    # / dollar-brace / example / dummy). It anchors on exact stub words, NOT a
    # 'your_' prefix, so a real-looking value (not a stub) is still flagged.
    re.compile(
        r"(?i)(api[_-]?key|secret|token|password|passwd|pwd|credential|private[_-]?key)\s*[:=]\s*"
        r"(?!['\"]?(?:replace_me|change_me|changeme|placeholder|example|dummy|xxx+|<|\$\{))"
        r"(?!(?:os\.|getattr|self\.|cfg\.|config\.))"
        r"[A-Za-z0-9._~/+=:@_-]{8,}"
    ),
    re.compile(r"(?:sk|rk)_live_[A-Za-z0-9]{16,}"),
    re.compile(r"gh[opusr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ASIA[A-Z0-9]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
]

# Long, high-entropy tokens (>= this many chars) that don't match any regex are
# still likely secrets. 28 is chosen to sit above realistic identifiers/hashes
# users write in prose but below typical secret lengths (32+ hex, 40+ base64).
_ENTROPY_TOKEN_MIN_LEN = 28
_ENTROPY_MIN_BITS = 3.5  # empirical: english words ~3.0, base64/hex secrets ~4.5+
# Split on whitespace, quotes, and common structural punctuation so we score the
# token, not the surrounding syntax. Hyphens/underscores stay inside a token
# because real secrets embed them.
_TOKEN_SPLIT_RE = re.compile(r"[\s\"'`,;<>()\[\]{}]+")
# Recognisably non-secret shapes we should not redact even at high entropy:
# hex-only git SHAs, uuids, semver-ish dotted paths, and file paths.
_HEX_ONLY_RE = re.compile(r"^[0-9a-fA-F]+$")
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _shannon_bits(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    length = len(s)
    return -sum((c / length) * _math.log2(c / length) for c in counts.values())


def _looks_like_identifier(token: str) -> bool:
    """Return True for tokens that are structurally not secrets even if long.

    Keeps false positives out of the entropy scan: git SHAs (hex only), UUIDs,
    and dotted paths (module.paths, files/with/slashes). Real secret shapes
    mix character classes and don't match.
    """
    if _HEX_ONLY_RE.match(token) or _UUID_RE.match(token):
        return True
    if "/" in token or ("." in token and "-" not in token and "_" not in token):
        return True
    return False


def _entropy_redact(text: str) -> str:
    """Redact long, high-entropy tokens the regex list missed.

    Complementary to SECRET_PATTERNS, not a replacement. Regexes catch known
    prefixed shapes; this pass catches obfuscated or novel keys that still
    exhibit the length + entropy signature of a secret.
    """
    def _swap(tok: str) -> str:
        if len(tok) < _ENTROPY_TOKEN_MIN_LEN:
            return tok
        if _looks_like_identifier(tok):
            return tok
        return "[REDACTED]" if _shannon_bits(tok) >= _ENTROPY_MIN_BITS else tok

    # We must preserve the exact separators to keep prose intact, so walk with a
    # finditer-driven rebuild instead of a naive join.
    out: list[str] = []
    idx = 0
    for m in _TOKEN_SPLIT_RE.finditer(text):
        out.append(_swap(text[idx:m.start()]))
        out.append(m.group(0))
        idx = m.end()
    out.append(_swap(text[idx:]))
    return "".join(out)


def redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    # Second pass: entropy scan for obfuscated / unknown-shape secrets. Kept
    # after the regex pass so labeled shapes get the recognisable redaction
    # marker before the generic entropy sweep runs.
    redacted = _entropy_redact(redacted)
    return redacted


# ---------------------------------------------------------------------------
# Gate configuration (quality-loop.config.json — the three deliberate keys)
# ---------------------------------------------------------------------------
# The complete gate-config surface is exactly three keys: "base" (default diff
# base ref), "tests" ({"path_markers": [...]}) and "high_risk_paths" ([...]).
# All three EXTEND the built-in constants — never replace them — and are read
# best-effort: an absent or malformed config degrades to the built-ins.
GATE_CONFIG_NAME = "quality-loop.config.json"


def load_gate_config(cwd: Path | None = None) -> dict[str, Any]:
    """Best-effort read of quality-loop.config.json at ``cwd``; {} when absent
    or unreadable. Gates must keep working with no config at all."""
    path = (cwd or Path.cwd()) / GATE_CONFIG_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def config_base(config: dict[str, Any]) -> str | None:
    """The config "base" ref, or None. Precedence is the caller's job
    (--base flag > QUALITY_LOOP_BASE env > this key > the built-in ladder)."""
    base = config.get("base") if isinstance(config, dict) else None
    if isinstance(base, str) and base.strip():
        return base.strip()
    return None


def test_path_markers(config: dict[str, Any] | None = None) -> tuple[str, ...]:
    """TEST_PATH_MARKERS extended (additively, never replaced) by the config's
    tests.path_markers list."""
    extra: tuple[str, ...] = ()
    if isinstance(config, dict):
        tests = config.get("tests")
        raw = tests.get("path_markers") if isinstance(tests, dict) else None
        if isinstance(raw, list):
            extra = tuple(
                m.strip().lower() for m in raw if isinstance(m, str) and m.strip()
            )
    return TEST_PATH_MARKERS + tuple(m for m in extra if m not in TEST_PATH_MARKERS)


def high_risk_path_extras(config: dict[str, Any] | None = None) -> tuple[str, ...]:
    """Extra high-risk path entries from the config's high_risk_paths list,
    normalized (forward slashes, no trailing slash). Additive only — the
    built-in _HIGH_TIER_* constants in quality_loop_reality always apply."""
    if not isinstance(config, dict):
        return ()
    raw = config.get("high_risk_paths")
    if not isinstance(raw, list):
        return ()
    return tuple(
        p.strip().replace("\\", "/").rstrip("/")
        for p in raw
        if isinstance(p, str) and p.strip().strip("/")
    )


# ---------------------------------------------------------------------------
# Scaffolding paths
# ---------------------------------------------------------------------------
INSTALL_MANIFEST_REL = ".quality-loop/install-manifest.json"


_CQL_SCAFFOLD_EXACT = frozenset({
    ".claude/settings.json", ".codex/hooks.json",
    ".git/hooks/pre-commit", ".pre-commit-config.yaml", "AGENTS.md",
    "SKILL.md",  # drop-in delivery copies the skill to the repo root
})
_CQL_SCAFFOLD_PREFIXES = (
    ".claude/skills/coding-quality-loop/", "hosts/claude-code/", "hosts/codex/",
    "assets/prompts/", "assets/routing/", "assets/control-plane/", "references/",
)


def _is_cql_shipped_shape(path: str) -> bool:
    """True when a path matches the shapes the CQL installer actually ships.
    The manifest is agent-writable checkout data, so membership alone must
    never exempt arbitrary consumer sources (src/, auth/, ...) from the scope
    gate — only paths that look like CQL's own payload qualify."""
    if "quality-loop" in path or "quality_loop" in path:
        return True
    if path in _CQL_SCAFFOLD_EXACT:
        return True
    return any(path.startswith(p) for p in _CQL_SCAFFOLD_PREFIXES)


def install_manifest_paths(cwd: Path | None = None) -> frozenset[str]:
    """Paths the install manifest (scripts/install.py) records as CQL's own
    scaffolding, filtered to CQL's shipped path shapes. Empty when no manifest
    exists.

    Candor note: the manifest records membership only — no content hashes — so
    byte-identity with the shipped copy is NOT checkable here. Two boundaries
    apply instead: the shape filter above (a manifest listing consumer sources
    exempts nothing), and, against a softened gate script, the harness guard
    plus the CI anchor (which runs the action's own pinned scripts — though the
    manifest itself is still checkout data there; see SECURITY.md).
    """
    path = (cwd or Path.cwd()) / INSTALL_MANIFEST_REL
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    if not isinstance(data, dict):
        return frozenset()
    return frozenset(
        f.replace("\\", "/")
        for f in data.get("files") or []
        if isinstance(f, str) and f.strip() and _is_cql_shipped_shape(f.replace("\\", "/"))
    )


def is_scaffolding_path(path: str, manifest: frozenset[str] | None = None) -> bool:
    """Loop scaffolding (the record, .quality-loop/, byte-compiled helpers, and
    — when a ``manifest`` set is supplied — install-manifest-listed files) is
    process output, not "the change," so the diff gates that reason about the
    change's size and scope exclude it. The single implementation for the
    package (previously duplicated byte-identically in quality_loop and
    quality_loop_reality).
    """
    norm = path.replace("\\", "/")
    if norm.startswith(".quality-loop/") or "/.quality-loop/" in norm:
        return True
    if "__pycache__/" in norm or norm.endswith(".pyc"):
        return True
    if norm.split("/")[-1] == "agent-record.json":
        return True
    return bool(manifest) and norm in manifest  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Test-weakening / test-path markers
# ---------------------------------------------------------------------------
# Test-weakening markers: an agent that fixes "green" by skipping/deleting tests
# is gaming the gate. These flag added skip/xfail/.only lines in test files.
# Language coverage: Python/pytest, JS/TS, Go, Rust, Java/JUnit, Ruby/RSpec,
# C#/xUnit+NUnit. Files only count when their PATH matches a test marker, so
# e.g. Rust #[cfg(test)] modules inside src/ stay uncovered (documented in
# references/enforcement-matrix.md).
TEST_PATH_MARKERS = ("test", "spec", "__tests__")
TEST_WEAKENING_PATTERNS = [
    # Python: @skip / @pytest.mark.skip / @mark.skipif / @unittest.skip etc.
    re.compile(r"^\+.*@(?:[\w.]*\.)?(?:skipif|xfail|skip)\b"),
    # JS/TS: .only( / .skip(
    re.compile(r"^\+.*\.(?:only|skip)\s*\("),
    re.compile(r"^\+.*\b(?:it|test|describe)\.skip\b"),
    # Go: t.Skip( / t.SkipNow( / t.Skipf(
    re.compile(r"^\+.*\bt\.Skip(?:Now|f)?\s*\("),
    # Rust: #[ignore] / #[ignore = "reason"]
    re.compile(r"^\+.*#\[\s*ignore\b"),
    # Java/JUnit 5: @Disabled (bare or with a reason)
    re.compile(r"^\+.*@Disabled\b"),
    # Ruby/RSpec: xit/xdescribe/xspecify, or a line-leading skip
    re.compile(r"^\+.*\bx(?:it|describe|specify)\b"),
    re.compile(r"^\+\s*skip\b"),
    # C#: [Ignore] (NUnit/MSTest) / Skip = "reason" (xUnit [Fact(Skip = ...)])
    re.compile(r"^\+.*\[\s*Ignore\b"),
    re.compile(r"^\+.*\bSkip\s*="),
]


# Test-shrinkage counters: deleted test functions and gutted assertions are the
# half of Hard Rule 6 the skip/xfail patterns cannot see (those only match ADDED
# lines). Declarations and assertion lines are counted on both sides of the diff
# and netted at DIFF level, not per file, so a legitimate test move stays green.
_TEST_DECL_RE = re.compile(
    # Python / JS-TS
    r"^\s*(?:async\s+)?def\s+test\w*\s*\(|^\s*(?:it|test|describe)(?:\.each\b[^(]*)?\s*\(\s*['\"`]"
    # Go: func TestXxx(
    r"|^\s*func\s+Test\w*\s*\("
    # Rust: #[test] / #[tokio::test] etc.
    r"|^\s*#\[\s*(?:\w+(?:::\w+)*::)?test\s*\]"
    # Java/JUnit: @Test
    r"|^\s*@Test\b"
    # Ruby/RSpec: it "..." do / specify/scenario/context/describe "..."
    r"|^\s*(?:it|specify|scenario|context|describe)\s+['\"]"
    # C#: [Fact] / [Theory] / [Test] / [TestMethod]
    r"|^\s*\[\s*(?:Fact|Theory|Test|TestMethod)\b"
)
_ASSERTION_LINE_RE = re.compile(
    # Python bare assert; assertEquals(-style calls (Python unittest, Java);
    # JS/Ruby expect(
    r"^\s*assert\b|\bassert\w+\s*\(|\bexpect\s*\("
    # Rust macros: assert!(, assert_eq!(, assert_ne!(, debug_assert!( — the
    # bang defeated the \w+\s*\( pattern above, which is why Rust shrinkage
    # was previously invisible.
    r"|\bassert\w*!\s*\("
    # Go: t.Error(f) / t.Fatal(f) — the assertion idiom of the stdlib.
    r"|\bt\.(?:Error|Fatal)f?\s*\("
    # C#: Assert.Equal( / Assert.True( / ...
    r"|\bAssert\.\w+\s*\("
)


def test_shrinkage_hits(
    patch: str, markers: tuple[str, ...] | None = None
) -> list[str]:
    """Findings when the diff removes more test declarations or assertion lines
    than it adds (deleted test files, gutted assertions).

    Sibling of ``test_weakening_hits``, which only sees ADDED skip/xfail lines.
    Counts are netted across ALL test files in the diff — not per file — so a
    legitimate test MOVE (deleted from one test file, equivalent adds in another
    test file in the same diff) stays silent while a deletion or an
    assertion-gutting still nets negative. ``markers`` defaults to the built-in
    TEST_PATH_MARKERS; callers may pass the config-extended set.
    """
    markers = markers or TEST_PATH_MARKERS
    removed_decls = added_decls = removed_asserts = added_asserts = 0
    files: list[str] = []
    in_test_file = False
    old_path = ""
    for line in patch.splitlines():
        if line.startswith("--- "):
            old_path = line[4:].strip()
            if old_path.startswith(("a/", "b/")):
                old_path = old_path[2:]
            continue
        if line.startswith("+++ "):
            new_path = line[4:].strip()
            if new_path.startswith(("a/", "b/")):
                new_path = new_path[2:]
            current = new_path if new_path != "/dev/null" else old_path
            in_test_file = any(m in current.lower() for m in markers)
            if in_test_file and current not in files:
                files.append(current)
            continue
        if not in_test_file or line.startswith(("---", "+++")):
            continue
        if line.startswith(("+", "-")):
            body = line[1:]
            is_decl = bool(_TEST_DECL_RE.search(body))
            is_assert = not is_decl and bool(_ASSERTION_LINE_RE.search(body))
            if line.startswith("+"):
                added_decls += is_decl
                added_asserts += is_assert
            else:
                removed_decls += is_decl
                removed_asserts += is_assert
    hits: list[str] = []
    listed = ", ".join(files[:5])
    if removed_decls > added_decls:
        hits.append(
            "net test-declaration loss in diff: removed %d, added %d (test files: %s) "
            "— restore the removed tests or add equivalent tests in another test file "
            "in the same diff" % (removed_decls, added_decls, listed)
        )
    if removed_asserts > added_asserts:
        hits.append(
            "net assertion loss in diff: removed %d, added %d (test files: %s) "
            "— restore equivalent assertions; weakening asserts to keep a suite green "
            "is gate-gaming" % (removed_asserts, added_asserts, listed)
        )
    return hits


def test_weakening_hits(
    patch: str, markers: tuple[str, ...] | None = None
) -> list[str]:
    """Test files whose ADDED lines match a test-weakening pattern.

    Scoped per-file: only added lines inside files matching TEST_PATH_MARKERS
    (or the config-extended ``markers``) count. Scanning the whole patch flags
    source that merely *contains* the marker strings — moving these very
    pattern definitions triggered it.
    """
    markers = markers or TEST_PATH_MARKERS
    hits: list[str] = []
    in_test_file = False
    current = ""
    for line in patch.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith(("a/", "b/")):
                path = path[2:]
            current = path
            in_test_file = any(m in path.lower() for m in markers)
            continue
        if in_test_file and line.startswith("+") and not line.startswith("+++"):
            if any(p.search(line) for p in TEST_WEAKENING_PATTERNS) and current not in hits:
                hits.append(current)
    return hits


# ---------------------------------------------------------------------------
# Atomic write + record I/O
# ---------------------------------------------------------------------------

def atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (unique temp file + os.replace).

    The single implementation for the package. A unique temp file per writer
    (mkstemp) means concurrent writers cannot clobber a shared temp path before
    the atomic replace; on any write failure the temp file is removed and the
    real error is surfaced rather than leaked.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_path, path)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        raise


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(data, indent=2) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        raise SystemExit(2)


# ---------------------------------------------------------------------------
# Git subprocess wrapper
# ---------------------------------------------------------------------------

def git_capture(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run git without raising. Returns (returncode, stdout, stderr)."""
    proc = subprocess.run(
        ["git", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_git(args: list[str], cwd: Path | None = None) -> str:
    """Run git, printing redacted stderr and exiting (SystemExit) on failure."""
    code, out, err = git_capture(args, cwd)
    if code != 0:
        print(redact(err.strip()), file=sys.stderr)
        raise SystemExit(code)
    return out


# ---------------------------------------------------------------------------
# Evidence predicates
# ---------------------------------------------------------------------------
# has_evidence and _nonempty are intentionally different and must NOT be merged:
#
#   has_evidence - "is this a real piece of evidence?" Strict: only a non-empty
#     string (a path/handle) or a non-empty object counts. Bare booleans AND
#     numbers are placeholders and never satisfy a shipping gate; lists do not
#     count either. Used on command evidence handles and harness_update.
#
#   _nonempty - "is this field populated at all?" Lenient: non-empty string,
#     non-empty list/dict, OR any int/float (a numeric field value is present).
#     Only bare booleans and None read as empty. Used for the per-group
#     "at least one descriptive field is present" check on inline artifacts.
#
# The divergence is deliberate: a number is not evidence (has_evidence=False)
# but a number is a populated field (_nonempty=True).


def has_evidence(value: Any) -> bool:
    """True only for real evidence: a non-empty path/string or a non-empty object.

    Bare booleans and numbers are placeholders, not evidence, and never satisfy
    a shipping gate.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value)
    return False


def _nonempty(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    if isinstance(value, (int, float)):
        return True
    return False
