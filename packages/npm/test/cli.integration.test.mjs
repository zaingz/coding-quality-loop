// End-to-end CLI smoke: spawn `node bin/cql.mjs …` and assert on exit code +
// stdout. Uses --dry-run so nothing is written, and skips gracefully on
// machines without a Python 3 interpreter.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
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

function hasGit() {
  return spawnSync("git", ["--version"], { stdio: "ignore" }).status === 0;
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

test("post-install next steps never suggest running the evals (not installed)", { skip: !hasPython() && "python3/python not on PATH" }, async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-cli-steps-"));
  const r = spawnSync(
    process.execPath,
    [CLI, "init", "--dry-run", "--yes", "--host", "claude-code", "--target", target],
    { encoding: "utf8" },
  );
  assert.equal(r.status, 0, `expected exit 0, got ${r.status}. stderr:\n${r.stderr}`);
  assert.doesNotMatch(stripAnsi(r.stdout), /run_evals\.py/);
});

test(
  "init → check → remove leaves a scratch git repo clean",
  { skip: (!hasPython() && "python3/python not on PATH") || (!hasGit() && "git not on PATH") },
  async () => {
    const target = await mkdtemp(join(tmpdir(), "cql-remove-"));
    assert.equal(spawnSync("git", ["init", "-q"], { cwd: target }).status, 0);

    // init --yes wires the chosen host plus the git pre-commit backstop.
    const init = spawnSync(
      process.execPath,
      [CLI, "init", "--yes", "--host", "claude-code", "--target", target],
      { encoding: "utf8" },
    );
    assert.equal(init.status, 0, `init failed. stderr:\n${init.stderr}\nstdout:\n${init.stdout}`);

    // The install manifest records what was written.
    const manifest = JSON.parse(
      await readFile(join(target, ".quality-loop", "install-manifest.json"), "utf8"),
    );
    assert.ok(Array.isArray(manifest.files) && manifest.files.length > 0, "manifest lists files");
    assert.match(manifest.host, /claude-code/);

    // check verifies the manifest and exits 0 on an intact install.
    const check = spawnSync(process.execPath, [CLI, "check", "--target", target], { encoding: "utf8" });
    assert.equal(check.status, 0, `check failed. stdout:\n${stripAnsi(check.stdout)}`);

    // remove reverses the install completely: the working tree ends clean.
    const remove = spawnSync(process.execPath, [CLI, "remove", "--target", target], { encoding: "utf8" });
    assert.equal(remove.status, 0, `remove failed. stdout:\n${stripAnsi(remove.stdout)}\nstderr:\n${remove.stderr}`);
    const status = spawnSync("git", ["status", "--porcelain"], { cwd: target, encoding: "utf8" });
    assert.equal(status.stdout.trim(), "", `expected clean tree after remove, got:\n${status.stdout}`);
  },
);

test(
  "remove leaves a coincidentally-identical pre-existing user file alone",
  { skip: (!hasPython() && "python3/python not on PATH") || (!hasGit() && "git not on PATH") },
  async () => {
    const target = await mkdtemp(join(tmpdir(), "cql-preexist-"));
    assert.equal(spawnSync("git", ["init", "-q"], { cwd: target }).status, 0);
    // The user already has a file byte-identical to one the installer ships.
    const shipped = await readFile(
      resolve(HERE, "..", "..", "..", "assets", "quality-loop.config.example.json"),
      "utf8",
    );
    await mkdir(join(target, "assets"), { recursive: true });
    await writeFile(join(target, "assets", "quality-loop.config.example.json"), shipped);

    const init = spawnSync(
      process.execPath,
      [CLI, "init", "--yes", "--host", "claude-code", "--target", target],
      { encoding: "utf8" },
    );
    assert.equal(init.status, 0, `init failed:\n${init.stderr}`);
    const manifest = JSON.parse(
      await readFile(join(target, ".quality-loop", "install-manifest.json"), "utf8"),
    );
    assert.ok(
      (manifest.preexisting || []).includes("assets/quality-loop.config.example.json"),
      "the coincidental user file is recorded as pre-existing",
    );

    const remove = spawnSync(process.execPath, [CLI, "remove", "--target", target], { encoding: "utf8" });
    assert.equal(remove.status, 0, `remove failed:\n${remove.stderr}`);
    // The user's file must survive uninstall unchanged — we never created it.
    const after = await readFile(join(target, "assets", "quality-loop.config.example.json"), "utf8");
    assert.equal(after, shipped, "pre-existing user file was deleted or altered by uninstall");
  },
);

test("check rejects an empty {} manifest as unhealthy", async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-check-shape-"));
  await mkdir(join(target, ".quality-loop"), { recursive: true });
  await writeFile(join(target, ".quality-loop", "install-manifest.json"), "{}\n");
  const r = spawnSync(process.execPath, [CLI, "check", "--target", target], { encoding: "utf8" });
  assert.notEqual(r.status, 0, `expected non-zero exit, stdout:\n${stripAnsi(r.stdout)}`);
  const out = stripAnsi(r.stdout);
  assert.match(out, /manifest records no host/);
  assert.match(out, /manifest lists no installed files/);
  assert.match(out, /cql init/);
  assert.doesNotMatch(out, /Install looks healthy/);
});

test("check flags unsafe (absolute or ..) manifest paths", async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-check-unsafe-"));
  await mkdir(join(target, ".quality-loop"), { recursive: true });
  await writeFile(
    join(target, ".quality-loop", "install-manifest.json"),
    JSON.stringify({ version: 1, host: "claude-code", files: ["../outside.txt", "/etc/passwd"], hook_groups: [] }),
  );
  const r = spawnSync(process.execPath, [CLI, "check", "--target", target], { encoding: "utf8" });
  assert.notEqual(r.status, 0);
  const out = stripAnsi(r.stdout);
  assert.match(out, /unsafe path/);
  assert.doesNotMatch(out, /Install looks healthy/);
});

test("check without a manifest explains and suggests init", async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-check-empty-"));
  const r = spawnSync(process.execPath, [CLI, "check", "--target", target], { encoding: "utf8" });
  assert.notEqual(r.status, 0);
  const out = stripAnsi(r.stdout);
  assert.match(out, /install-manifest\.json/);
  assert.match(out, /cql init/);
});
