#!/usr/bin/env python3
"""Host adapter protocol for driven mode.

Adapters are intentionally subprocess+JSON only. The orchestrator owns gates and
verification; hosts only produce proposed updates or human relay prompts.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass
class HostResult:
    ok: bool
    text: str
    data: dict[str, Any]


class HostAdapter(Protocol):
    def available(self) -> bool: ...

    def spawn(self, prompt: str, tool_policy: str, cwd: Path, model: str | None = None) -> HostResult: ...


class FakeHostAdapter:
    def __init__(self, fixture: dict[str, Any] | None = None) -> None:
        self.fixture = fixture or {}
        self.calls: list[dict[str, str]] = []

    def available(self) -> bool:
        return True

    def spawn(self, prompt: str, tool_policy: str, cwd: Path, model: str | None = None) -> HostResult:
        self.calls.append({"prompt": prompt, "tool_policy": tool_policy, "model": model or ""})
        updates = self.fixture.get("record_updates", {})
        return HostResult(True, json.dumps(updates), updates if isinstance(updates, dict) else {})


class ManualHostAdapter:
    def available(self) -> bool:
        return True

    def spawn(self, prompt: str, tool_policy: str, cwd: Path, model: str | None = None) -> HostResult:
        return HostResult(True, prompt, {"manual_prompt": prompt, "tool_policy": tool_policy})


class SubprocessHostAdapter:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def available(self) -> bool:
        return shutil.which(self.kind) is not None

    def spawn(self, prompt: str, tool_policy: str, cwd: Path, model: str | None = None) -> HostResult:
        if self.kind == "claude":
            cmd = ["claude", "-p", prompt]
        elif self.kind == "codex":
            cmd = ["codex", "exec", prompt]
        else:
            return HostResult(False, f"unknown host: {self.kind}", {})
        if model:
            cmd.extend(["--model", model])
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(cwd), check=False)
        text = proc.stdout.strip() or proc.stderr.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {"text": text}
        return HostResult(proc.returncode == 0, text, data if isinstance(data, dict) else {"value": data})


def load_adapter(name: str, fixture: dict[str, Any] | None = None) -> HostAdapter:
    if name == "fake":
        return FakeHostAdapter(fixture)
    if name == "manual":
        return ManualHostAdapter()
    if name in {"claude", "codex"}:
        return SubprocessHostAdapter(name)
    raise ValueError(f"unknown host adapter: {name}")
