#!/usr/bin/env python3
"""Schema-drift guard: pin assets/agent-record.schema.json's required-field list
against the hand-rolled `check-record` validator in scripts/quality_loop.py.

If either side adds/removes a required field without the other following, the
minimal-valid record stops validating (or a mutant stops failing) and this test
catches the drift. Stdlib unittest + subprocess only.
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
        path.write_text(json.dumps(record))
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
        self.required = json.loads(SCHEMA.read_text())["required"]

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

    def test_required_list_matches_validator(self):
        """The schema's required list must equal the validator's required list.

        This reads the validator's list straight from the source so the two can
        never silently diverge — the intent Item 3's schema-drift guard pins."""
        src = (ROOT / "scripts" / "quality_loop.py").read_text()
        start = src.index("required = [", src.index("def check_record"))
        end = src.index("]", start)
        block = src[start:end]
        validator_fields = [
            line.strip().strip('",')
            for line in block.splitlines()[1:]
            if line.strip().strip('",')
        ]
        self.assertEqual(sorted(validator_fields), sorted(self.required))


if __name__ == "__main__":
    unittest.main()
