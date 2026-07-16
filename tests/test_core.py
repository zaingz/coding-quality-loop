#!/usr/bin/env python3
"""Unit tests for pure primitives in scripts/quality_loop_core.py.

Stdlib unittest only. Run with: python -m unittest discover tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quality_loop_core as qlcore  # noqa: E402


class TestRedact(unittest.TestCase):
    def test_labeled_quoted_secret_redacted(self):
        out = qlcore.redact('api_key = "ghp_' + "A" * 36 + '"')
        self.assertIn("[REDACTED]", out)
        self.assertNotIn("ghp_", out)

    def test_github_token_prefix_redacted(self):
        out = qlcore.redact("token ghp_" + "B" * 30 + " here")
        self.assertIn("[REDACTED]", out)

    def test_hyphenated_openai_key_redacted(self):
        out = qlcore.redact("sk-live-" + "C" * 24)
        self.assertIn("[REDACTED]", out)

    def test_placeholder_stub_not_redacted(self):
        out = qlcore.redact("api_key = REPLACE_ME")
        self.assertNotIn("[REDACTED]", out)

    def test_plain_prose_untouched(self):
        text = "the quick brown fox jumped over the lazy dog"
        self.assertEqual(qlcore.redact(text), text)

    def test_git_sha_not_redacted_by_entropy(self):
        sha = "a" * 40  # hex-only, identifier shape
        self.assertNotIn("[REDACTED]", qlcore.redact(sha))

    def test_high_entropy_token_redacted(self):
        # 28+ chars, mixed classes, no identifier shape -> entropy sweep
        tok = "Zx9Qw3Ab7Kd2Mn8Rt5Vc1Bh6Lp4Ns"
        self.assertIn("[REDACTED]", qlcore.redact(tok))


class TestShannonBits(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(qlcore._shannon_bits(""), 0.0)

    def test_uniform_string_is_zero(self):
        self.assertEqual(qlcore._shannon_bits("aaaa"), 0.0)

    def test_two_symbols_is_one_bit(self):
        self.assertAlmostEqual(qlcore._shannon_bits("ab"), 1.0)


class TestLooksLikeIdentifier(unittest.TestCase):
    def test_hex_only(self):
        self.assertTrue(qlcore._looks_like_identifier("deadbeef1234"))

    def test_uuid(self):
        self.assertTrue(
            qlcore._looks_like_identifier("12345678-1234-1234-1234-123456789abc")
        )

    def test_path(self):
        self.assertTrue(qlcore._looks_like_identifier("src/module/file.py"))

    def test_dotted_path(self):
        self.assertTrue(qlcore._looks_like_identifier("module.sub.name"))

    def test_mixed_secret_shape_is_not_identifier(self):
        self.assertFalse(qlcore._looks_like_identifier("Zx9Qw3Ab-7Kd2_Mn8"))


class TestHasEvidence(unittest.TestCase):
    def test_nonempty_string(self):
        self.assertTrue(qlcore.has_evidence("pytest: 1 passed"))

    def test_whitespace_string_is_false(self):
        self.assertFalse(qlcore.has_evidence("   "))

    def test_nonempty_dict(self):
        self.assertTrue(qlcore.has_evidence({"k": "v"}))

    def test_empty_dict_is_false(self):
        self.assertFalse(qlcore.has_evidence({}))

    def test_bool_is_false(self):
        self.assertFalse(qlcore.has_evidence(True))

    def test_number_is_false(self):
        self.assertFalse(qlcore.has_evidence(5))

    def test_list_is_false(self):
        self.assertFalse(qlcore.has_evidence(["a"]))


class TestNonempty(unittest.TestCase):
    def test_nonempty_string(self):
        self.assertTrue(qlcore._nonempty("x"))

    def test_whitespace_string_is_false(self):
        self.assertFalse(qlcore._nonempty("  "))

    def test_nonempty_list(self):
        self.assertTrue(qlcore._nonempty([1]))

    def test_empty_list_is_false(self):
        self.assertFalse(qlcore._nonempty([]))

    def test_number_is_true(self):
        self.assertTrue(qlcore._nonempty(0))

    def test_bool_is_false(self):
        self.assertFalse(qlcore._nonempty(False))

    def test_none_is_false(self):
        self.assertFalse(qlcore._nonempty(None))


class TestTestWeakeningHits(unittest.TestCase):
    # Marker literals are assembled at runtime so this test file does not itself
    # trip the diff-audit test-weakening scanner (which reads added source lines).
    PY_SKIP = "@pytest.mark." + "skip"
    JS_SKIP = "it." + "skip"

    def test_added_skip_in_test_file_flagged(self):
        patch = (
            "+++ b/tests/test_foo.py\n"
            f"+{self.PY_SKIP}\n"
            "+def test_bar():\n"
        )
        self.assertEqual(qlcore.test_weakening_hits(patch), ["tests/test_foo.py"])

    def test_skip_in_source_file_not_flagged(self):
        patch = f"+++ b/src/app.py\n+{self.PY_SKIP}\n"
        self.assertEqual(qlcore.test_weakening_hits(patch), [])

    def test_jest_only_flagged(self):
        patch = f"+++ b/src/__tests__/a.spec.js\n+{self.JS_SKIP}('x', () => {{}})\n"
        self.assertEqual(qlcore.test_weakening_hits(patch), ["src/__tests__/a.spec.js"])

    def test_clean_test_file_no_hits(self):
        patch = "+++ b/tests/test_ok.py\n+def test_ok():\n+    assert True\n"
        self.assertEqual(qlcore.test_weakening_hits(patch), [])


class TestStatusConstants(unittest.TestCase):
    def test_terminal_statuses(self):
        self.assertEqual(qlcore.TERMINAL_STATUSES, {"package", "done"})

    def test_post_implement_subset_of_minimality_required(self):
        self.assertTrue(
            qlcore.POST_IMPLEMENT_STATUSES <= qlcore.MINIMALITY_REQUIRED_STATUSES
        )

    def test_review_ready_within_post_intake_plus_terminal(self):
        self.assertTrue(qlcore.TERMINAL_STATUSES <= qlcore.REVIEW_READY_STATUSES)


class TestJsonIO(unittest.TestCase):
    def test_write_then_load_roundtrip(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nested" / "rec.json"
            data = {"a": 1, "b": ["x", "y"]}
            qlcore.write_json(path, data)
            self.assertEqual(qlcore.load_json(path), data)

    def test_atomic_write_leaves_no_temp(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "f.txt"
            qlcore.atomic_write_text(path, "hello")
            self.assertEqual(path.read_text(), "hello")
            leftovers = [p.name for p in Path(td).iterdir() if p.name != "f.txt"]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
