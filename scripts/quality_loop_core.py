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
# Test-weakening / test-path markers
# ---------------------------------------------------------------------------
# Test-weakening markers: an agent that fixes "green" by skipping/deleting tests
# is gaming the gate. These flag added skip/xfail/.only lines in test files.
TEST_PATH_MARKERS = ("test", "spec", "__tests__")
TEST_WEAKENING_PATTERNS = [
    # Match @skip / @pytest.mark.skip / @mark.skipif / @unittest.skip etc.
    re.compile(r"^\+.*@(?:[\w.]*\.)?(?:skipif|xfail|skip)\b"),
    re.compile(r"^\+.*\.(?:only|skip)\s*\("),
    re.compile(r"^\+.*\b(?:it|test|describe)\.skip\b"),
]


def test_weakening_hits(patch: str) -> list[str]:
    """Test files whose ADDED lines match a test-weakening pattern.

    Scoped per-file: only added lines inside files matching TEST_PATH_MARKERS
    count. Scanning the whole patch flags source that merely *contains* the
    marker strings — moving these very pattern definitions triggered it.
    """
    hits: list[str] = []
    in_test_file = False
    current = ""
    for line in patch.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith(("a/", "b/")):
                path = path[2:]
            current = path
            in_test_file = any(m in path.lower() for m in TEST_PATH_MARKERS)
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


# ---------------------------------------------------------------------------
# Field-shape validators
# ---------------------------------------------------------------------------
# The record checker repeats the same isinstance -> errors.append idiom dozens
# of times. These collapse the three regular shapes into one call each; each
# returns whether the field was valid so a caller can gate nested validation on
# it. Messages are fixed strings the eval suite pins byte-for-byte, so any new
# call site must produce a label whose message reads correctly.

def require_str(errors: list[str], value: Any, label: str) -> bool:
    """True iff ``value`` is a non-empty string; else append the standard error."""
    if isinstance(value, str) and value.strip():
        return True
    errors.append(f"{label} must be a non-empty string")
    return False


def require_list(errors: list[str], value: Any, label: str) -> bool:
    """True iff ``value`` is a list; else append the standard "must be an array" error."""
    if isinstance(value, list):
        return True
    errors.append(f"{label} must be an array")
    return False


def require_number(errors: list[str], value: Any, label: str, *, minimum: float = 0) -> bool:
    """True iff ``value`` is a real number >= ``minimum``; else append the error.

    Booleans are rejected (a bool is not a number here). Emits the "must be a
    number" message for the wrong type and "must be >= {minimum}" below range.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{label} must be a number")
        return False
    if value < minimum:
        errors.append(f"{label} must be >= {minimum}")
        return False
    return True


def require_bool_or_null(errors: list[str], value: Any, label: str) -> bool:
    """True iff ``value`` is None or a bool; else append "{label} must be a boolean"."""
    if value is None or isinstance(value, bool):
        return True
    errors.append(f"{label} must be a boolean")
    return False


def require_str_or_null(errors: list[str], value: Any, label: str) -> bool:
    """True iff ``value`` is None or a str; else append "{label} must be a string or null"."""
    if value is None or isinstance(value, str):
        return True
    errors.append(f"{label} must be a string or null")
    return False


# ---------------------------------------------------------------------------
# Delegation ledger: brief-size advisory
# ---------------------------------------------------------------------------
# An oversized delegation brief is a soft signal (context bloat, unfocused
# hand-off), never a hard failure: the char ceiling is advisory. Both
# verify-gates and control-report read the same default and per-entry sizing so
# the two surfaces cannot drift.
BRIEF_CHAR_LIMIT_DEFAULT = 4000


def brief_char_limit(config: Any) -> int:
    """Advisory delegation-brief char ceiling from ``config.delegation.brief_char_limit``.

    Falls back to :data:`BRIEF_CHAR_LIMIT_DEFAULT` when unset or malformed. Never
    raises — a bad config downgrades to the default, it does not break a gate.
    """
    if isinstance(config, dict):
        section = config.get("delegation")
        if isinstance(section, dict):
            val = section.get("brief_char_limit")
            if isinstance(val, int) and not isinstance(val, bool) and val > 0:
                return val
    return BRIEF_CHAR_LIMIT_DEFAULT


def brief_entry_chars(entry: Any) -> int:
    """Recorded brief size for a delegation entry.

    Prefers an explicit non-negative ``brief_chars`` (the orchestrator can log
    the true brief length even when only a truncated ``brief_summary`` is kept);
    else falls back to ``len(brief_summary)``. Unknown shapes score 0.
    """
    if isinstance(entry, dict):
        chars = entry.get("brief_chars")
        if isinstance(chars, int) and not isinstance(chars, bool) and chars >= 0:
            return chars
        summary = entry.get("brief_summary")
        if isinstance(summary, str):
            return len(summary)
    return 0
