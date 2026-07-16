#!/usr/bin/env python3
"""Unit tests for pure transcript/rollout parsers in quality_loop_control.py.

These functions are imported and exercised directly — no refactor or split of
the module. Stdlib unittest only.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quality_loop_control as ctl  # noqa: E402


class TestProjectSlug(unittest.TestCase):
    def test_non_alnum_replaced_with_dash(self):
        self.assertEqual(ctl.project_slug(Path("/home/user/my.repo")), "-home-user-my-repo")


class TestRedactTargetAndSummary(unittest.TestCase):
    def test_redact_target_truncates(self):
        out = ctl._redact_target("x" * (ctl.TARGET_MAX + 50))
        self.assertEqual(len(out), ctl.TARGET_MAX)

    def test_redact_target_redacts_secret(self):
        out = ctl._redact_target("ghp_" + "A" * 36)
        self.assertIn("[REDACTED]", out)

    def test_summarize_prefers_first_present_key(self):
        self.assertEqual(
            ctl._summarize_tool_input("Bash", {"command": "ls -la"}), "ls -la"
        )

    def test_summarize_file_path_wins_over_command(self):
        self.assertEqual(
            ctl._summarize_tool_input("Edit", {"file_path": "a.py", "command": "x"}),
            "a.py",
        )

    def test_summarize_non_dict_is_empty(self):
        self.assertEqual(ctl._summarize_tool_input("Bash", "nope"), "")

    def test_summarize_no_known_keys_is_empty(self):
        self.assertEqual(ctl._summarize_tool_input("Bash", {"other": "v"}), "")


class TestFirstText(unittest.TestCase):
    def test_plain_string(self):
        self.assertEqual(ctl._first_text("hello"), "hello")

    def test_text_block_in_list(self):
        content = [{"type": "text", "text": "hi"}, {"type": "image"}]
        self.assertEqual(ctl._first_text(content), "hi")

    def test_no_text_block(self):
        self.assertEqual(ctl._first_text([{"type": "image"}]), "")

    def test_other_type_is_empty(self):
        self.assertEqual(ctl._first_text(42), "")


class TestCleanTitle(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(ctl._clean_title("a   b\n c"), "a b c")

    def test_skips_machine_wrapper(self):
        self.assertEqual(ctl._clean_title("<hook output>"), "")

    def test_skips_caveat(self):
        self.assertEqual(ctl._clean_title("Caveat: local command"), "")

    def test_truncates_to_title_max(self):
        self.assertEqual(len(ctl._clean_title("z" * (ctl.TITLE_MAX + 20))), ctl.TITLE_MAX)


class TestAsInt(unittest.TestCase):
    def test_int_passes_through(self):
        self.assertEqual(ctl._as_int(7), 7)

    def test_bool_is_zero(self):
        self.assertEqual(ctl._as_int(True), 0)

    def test_string_is_zero(self):
        self.assertEqual(ctl._as_int("5"), 0)

    def test_float_is_zero(self):
        self.assertEqual(ctl._as_int(3.2), 0)


class TestCodexSessionId(unittest.TestCase):
    def test_extracts_uuid_from_stem(self):
        p = Path("rollout-2024-01-01-12345678-1234-1234-1234-123456789abc.jsonl")
        self.assertEqual(ctl._codex_session_id(p), "12345678-1234-1234-1234-123456789abc")

    def test_falls_back_to_stem(self):
        p = Path("rollout-no-uuid.jsonl")
        self.assertEqual(ctl._codex_session_id(p), "rollout-no-uuid")


class TestCodexMeta(unittest.TestCase):
    def test_valid_session_meta(self):
        line = json.dumps({"type": "session_meta", "payload": {"cwd": "/x"}}).encode()
        self.assertEqual(ctl._codex_meta(line), {"cwd": "/x"})

    def test_wrong_type_is_none(self):
        line = json.dumps({"type": "other", "payload": {}}).encode()
        self.assertIsNone(ctl._codex_meta(line))

    def test_invalid_json_is_none(self):
        self.assertIsNone(ctl._codex_meta(b"not json"))

    def test_payload_not_dict_is_none(self):
        line = json.dumps({"type": "session_meta", "payload": []}).encode()
        self.assertIsNone(ctl._codex_meta(line))


class TestCodexLineage(unittest.TestCase):
    def test_top_level_parent_and_nickname_role(self):
        meta = {"parent_thread_id": "p1", "agent_nickname": "Sol", "agent_role": "reviewer"}
        self.assertEqual(ctl._codex_lineage(meta), ("p1", "Sol (reviewer)"))

    def test_nested_thread_spawn(self):
        meta = {"source": {"subagent": {"thread_spawn": {"parent_thread_id": "p2", "agent_role": "impl"}}}}
        self.assertEqual(ctl._codex_lineage(meta), ("p2", "impl"))

    def test_empty_meta(self):
        self.assertEqual(ctl._codex_lineage({}), (None, None))

    def test_nickname_only(self):
        self.assertEqual(ctl._codex_lineage({"agent_nickname": "Sol"}), (None, "Sol"))


class TestPriceFor(unittest.TestCase):
    def test_longest_key_match_wins(self):
        prices = {"claude": {"input_per_mtok": 1.0}, "claude-opus": {"input_per_mtok": 5.0}}
        self.assertEqual(ctl._price_for("claude-opus-4", prices), {"input_per_mtok": 5.0})

    def test_no_match_is_none(self):
        self.assertIsNone(ctl._price_for("gpt-4", {"claude": {"input_per_mtok": 1.0}}))

    def test_empty_model_is_none(self):
        self.assertIsNone(ctl._price_for(None, {"claude": {}}))


class TestCost(unittest.TestCase):
    def test_no_rates_is_none(self):
        self.assertIsNone(ctl._cost({"input_tokens": 100}, None))

    def test_computes_rounded_cost(self):
        row = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
        rates = {"input_per_mtok": 3.0, "output_per_mtok": 15.0}
        self.assertEqual(ctl._cost(row, rates), 18.0)

    def test_missing_columns_default_zero(self):
        self.assertEqual(ctl._cost({}, {"input_per_mtok": 3.0}), 0.0)


class TestFindingParts(unittest.TestCase):
    def test_dict_with_severity_and_text(self):
        self.assertEqual(
            ctl._finding_parts({"severity": "high", "text": "leak"}), ("high", "leak")
        )

    def test_dict_alternate_keys(self):
        self.assertEqual(
            ctl._finding_parts({"level": "low", "message": "m"}), ("low", "m")
        )

    def test_bare_string_is_unspecified(self):
        self.assertEqual(ctl._finding_parts("just text"), ("unspecified", "just text"))

    def test_dict_missing_text_is_empty(self):
        self.assertEqual(ctl._finding_parts({"severity": "info"}), ("info", ""))


class TestRoleForAgent(unittest.TestCase):
    def test_main_is_main(self):
        self.assertEqual(ctl._role_for_agent("main", {}), "main")

    def test_none_is_main(self):
        self.assertEqual(ctl._role_for_agent(None, {}), "main")

    def test_known_agent_maps_to_role(self):
        self.assertEqual(ctl._role_for_agent("reviewer", {"reviewer": {}}), "reviewer")

    def test_unknown_agent_is_other(self):
        self.assertEqual(ctl._role_for_agent("mystery", {"reviewer": {}}), "other")


if __name__ == "__main__":
    unittest.main()
