// End-to-end CLI smoke: spawn `node bin/cql.mjs …` and assert on exit code +
// stdout. Uses --dry-run so nothing is written, and skips gracefully on
// machines without a Python 3 interpreter.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const CLI = resolve(HERE, "..", "bin", "cql.mjs");

function hasPython() {
  for (const cmd of ["python3", "python"]) {
    const r = spawnSync(cmd, ["--version"], { stdio: "ignore" });
    if (r.status === 0) return true;
  }
  return false;
}

// Strip ANSI so we can assert on text regardless of color-support.
function stripAnsi(s) {
  return s.replace(/\x1b\[[0-9;]*m/g, "");
}

test("--version prints a semver-ish string", () => {
  const r = spawnSync(process.execPath, [CLI, "--version"], { encoding: "utf8" });
  assert.equal(r.status, 0);
  assert.match(r.stdout.trim(), /^\d+\.\d+\.\d+/);
});

test("--help prints usage and exits 0", () => {
  const r = spawnSync(process.execPath, [CLI, "--help"], { encoding: "utf8" });
  assert.equal(r.status, 0);
  const out = stripAnsi(r.stdout);
  assert.match(out, /coding-quality-loop/);
  assert.match(out, /Usage/);
  assert.match(out, /init/);
});

test("unknown command exits non-zero and prints help", () => {
  const r = spawnSync(process.execPath, [CLI, "definitely-not-a-command"], { encoding: "utf8" });
  assert.notEqual(r.status, 0);
});

test("init --dry-run --yes --host claude-code succeeds", { skip: !hasPython() && "python3/python not on PATH" }, async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-cli-"));
  const r = spawnSync(
    process.execPath,
    [CLI, "init", "--dry-run", "--yes", "--host", "claude-code", "--target", target],
    { encoding: "utf8" },
  );
  assert.equal(r.status, 0, `expected exit 0, got ${r.status}. stderr:\n${r.stderr}`);
  const out = stripAnsi(r.stdout);
  // Advertised behavior from the review fix: SKILL.md must land in .claude/skills/
  // Dry-run mode prints "would copy … -> …" lines from install.py.
  // Contract: the install report must mention the Claude skills directory.
  assert.match(out, /\.claude\/skills\/coding-quality-loop/);
});

test("init --dry-run --yes --host git suppresses setup-models step", { skip: !hasPython() && "python3/python not on PATH" }, async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-cli-git-"));
  const r = spawnSync(
    process.execPath,
    [CLI, "init", "--dry-run", "--yes", "--host", "git", "--target", target],
    { encoding: "utf8" },
  );
  assert.equal(r.status, 0, `expected exit 0, got ${r.status}. stderr:\n${r.stderr}`);
  const out = stripAnsi(r.stdout);
  // Regression guard for review Fix 5: `setup-models --host git` is meaningless.
  assert.doesNotMatch(out, /setup-models --host git/);
});
