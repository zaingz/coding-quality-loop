#!/usr/bin/env python3
"""Schema-drift guard: pin `assets/agent-record.schema.json`'s required-field
list against the hand-rolled validator behind `check-record`.

The repo carries two validators for one record shape — the JSON Schema consumers
read, and `record_validation_issues()` (v6.x: shared by `check-record` and the
`record` mutation verbs). If either side adds or drops a required field without
the other following, the minimal valid record stops validating, a mutant stops
failing, or the two required lists diverge — and one of these tests fails.

Stdlib `unittest` + `subprocess` only. Run with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "quality_loop.py"
SCHEMA = ROOT / "assets" / "agent-record.schema.json"

sys.path.insert(0, str(ROOT / "scripts"))

import quality_loop as ql  # noqa: E402

_MISSING_PREFIX = "missing required field: "


def minimal_valid_record() -> dict:
    """A record satisfying every required field, at the earliest lifecycle state
    (intake) so no post-INTAKE warnings fire."""
    return {
        "task_id": "t-1",
        "goal": "do the thing",
        "acceptance_criteria": ["works"],
        "constraints": [],
        "non_goals": [],
        "assumptions": [],
        "risk_tier": "low",
        "verification_plan": ["unit"],
        "status": "intake",
    }


def run_check(record: dict) -> int:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "agent-record.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "check-record", str(path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    return proc.returncode


class TestSchemaDrift(unittest.TestCase):
    def setUp(self):
        self.required = json.loads(SCHEMA.read_text(encoding="utf-8"))["required"]

    def test_minimal_record_passes(self):
        self.assertEqual(run_check(minimal_valid_record()), 0)

    def test_removing_any_required_field_fails(self):
        for field in self.required:
            with self.subTest(field=field):
                record = minimal_valid_record()
                del record[field]
                self.assertEqual(
                    run_check(record), 1, f"check-record should reject missing {field!r}"
                )

    def test_validator_required_set_equals_schema_required_set(self):
        """The validator's own missing-field errors must name exactly the schema's
        required list — checked by BEHAVIOR (an empty record), not by scraping the
        source, so the guard survives the validator moving between functions."""
        errors, _warnings = ql.record_validation_issues({})
        reported = {
            err[len(_MISSING_PREFIX):] for err in errors if err.startswith(_MISSING_PREFIX)
        }
        self.assertEqual(reported, set(self.required))

    def test_schema_declares_no_extra_required_properties(self):
        """Every required field must also be a declared property of the schema."""
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertTrue(set(self.required) <= set(schema["properties"]))


if __name__ == "__main__":
    unittest.main()
