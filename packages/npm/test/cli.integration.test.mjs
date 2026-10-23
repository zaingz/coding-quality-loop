// End-to-end CLI smoke: spawn `node bin/cql.mjs …` and assert on exit code +
// stdout. Uses --dry-run so nothing is written, and skips gracefully on
// machines without a Python 3 interpreter.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cp, copyFile, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const CLI = resolve(HERE, "..", "bin", "cql.mjs");
const REPO = resolve(HERE, "..", "..", "..");
const INSTALL = join(REPO, "scripts", "install.py");

function python(...args) {
  const executable = ["python3", "python"].find((cmd) =>
    spawnSync(cmd, ["-c", "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"], { stdio: "ignore" }).status === 0);
  return spawnSync(executable, args, { encoding: "utf8" });
}

function hasPython() {
  for (const cmd of ["python3", "python"]) {
    const r = spawnSync(cmd, ["-c", "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"], { stdio: "ignore" });
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
  assert.match(out, /inspect it before reinstalling/);
  assert.doesNotMatch(out, /Install looks healthy/);
});

test("check reports non-object manifests without throwing", async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-check-nonobject-"));
  await mkdir(join(target, ".quality-loop"));
  const manifestPath = join(target, ".quality-loop", "install-manifest.json");
  for (const raw of ["null", "[]"]) {
    await writeFile(manifestPath, raw);
    const result = spawnSync(process.execPath, [CLI, "check", "--target", target], { encoding: "utf8" });
    assert.notEqual(result.status, 0);
    assert.match(result.stdout, /must contain a JSON object/);
    assert.doesNotMatch(result.stderr, /TypeError/);
  }
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

test("prepack ships model-neutral agent templates (pins stripped at rest)", async () => {
  const pkgRoot = resolve(HERE, "..");
  const repoRoot = resolve(pkgRoot, "..", "..");
  const src = await readFile(
    join(repoRoot, ".claude", "agents", "quality-loop-context-mapper.md"),
    "utf8",
  );
  // The repo's own agent files carry the operator's activated routing…
  assert.doesNotMatch(src.split("\n---")[0], /model: inherit/);
  const r = spawnSync(process.execPath, [join(pkgRoot, "scripts", "prepack.mjs")], {
    encoding: "utf8",
  });
  assert.equal(r.status, 0, r.stderr);
  // …but the vendored tarball copy is neutral at rest.
  const shipped = await readFile(
    join(pkgRoot, "dist", "skill", ".claude", "agents", "quality-loop-context-mapper.md"),
    "utf8",
  );
  const head = shipped.split("\n---")[0];
  assert.match(head, /model: inherit/);
  assert.doesNotMatch(head, /^effort:/m);
  assert.doesNotMatch(head, /^reasoningEffort:/m);
  assert.match(shipped, /Read-only context mapper/);
});

test("check detects changed runtime and hooks; remove preserves later user edits", { skip: !hasPython() && "Python not on PATH" }, async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-drift-"));
  assert.equal(spawnSync("git", ["init", "-q"], { cwd: target }).status, 0);
  await writeFile(join(target, "AGENTS.md"), "# Existing user instructions\n");
  const init = spawnSync(process.execPath, [CLI, "init", "--yes", "--host", "codex", "--target", target], { encoding: "utf8" });
  assert.equal(init.status, 0, init.stderr);

  const runtime = join(target, "scripts", "quality_loop.py");
  await writeFile(runtime, (await readFile(runtime, "utf8")) + "\n# Later runtime edit\n");
  const hooks = join(target, ".codex", "hooks.json");
  const settings = JSON.parse(await readFile(hooks, "utf8"));
  settings.hooks.PreToolUse = [{ hooks: [{ type: "command", command: "echo unrelated" }] }];
  await writeFile(hooks, JSON.stringify(settings));
  await writeFile(join(target, "AGENTS.md"), (await readFile(join(target, "AGENTS.md"), "utf8")) + "\n# Later user note\n");

  const check = spawnSync(process.execPath, [CLI, "check", "--target", target], { encoding: "utf8" });
  assert.notEqual(check.status, 0);
  assert.match(check.stdout, /changed since install/);
  const remove = spawnSync(process.execPath, [CLI, "remove", "--target", target], { encoding: "utf8" });
  assert.notEqual(remove.status, 0);
  assert.match(await readFile(join(target, "AGENTS.md"), "utf8"), /Later user note/);
  assert.match(await readFile(runtime, "utf8"), /Later runtime edit/);
  assert.ok(await readFile(join(target, ".quality-loop", "install-manifest.json"), "utf8"));
});

test("remove blocks on a hook-only edit and leaves the install intact", { skip: !hasPython() && "Python not on PATH" }, async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-hook-edit-"));
  assert.equal(python(INSTALL, "--host", "claude-code", "--target", target, "--json").status, 0);
  const hooksPath = join(target, ".claude", "settings.json");
  const hooks = JSON.parse(await readFile(hooksPath, "utf8"));
  hooks.hooks.Stop[0].hooks[0].statusMessage = "user changed message";
  const edited = JSON.stringify(hooks, null, 2) + "\n";
  await writeFile(hooksPath, edited);
  const remove = spawnSync(process.execPath, [CLI, "remove", "--target", target], { encoding: "utf8" });
  assert.notEqual(remove.status, 0);
  assert.match(remove.stdout, /\.claude\/settings\.json \(changed since install; reconcile even unrelated hook edits before uninstall\)/);
  assert.equal(await readFile(hooksPath, "utf8"), edited);
  assert.equal(existsSync(join(target, "scripts", "quality_loop.py")), true);
  assert.equal(existsSync(join(target, ".quality-loop", "install-manifest.json")), true);
});

test("remove preserves a pre-existing AGENTS.md that matched the template", { skip: !hasPython() && "Python not on PATH" }, async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-agents-match-"));
  const template = await readFile(join(REPO, "assets", "AGENTS.template.md"), "utf8");
  await writeFile(join(target, "AGENTS.md"), template);
  assert.equal(python(INSTALL, "--host", "codex", "--target", target, "--json").status, 0);
  const manifest = JSON.parse(await readFile(join(target, ".quality-loop", "install-manifest.json"), "utf8"));
  assert.ok(manifest.preexisting.includes("AGENTS.md"));
  const remove = python(INSTALL, "--uninstall", "--target", target, "--json");
  assert.equal(remove.status, 0, remove.stdout);
  assert.equal(await readFile(join(target, "AGENTS.md"), "utf8"), template);
});

test("reinstall replaces an older managed Stop group without losing adjacent user hooks", { skip: !hasPython() && "Python not on PATH" }, async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-hook-upgrade-"));
  await mkdir(join(target, ".claude"));
  const old = JSON.parse(await readFile(join(REPO, "hosts", "claude-code", "settings.json"), "utf8"));
  old.hooks.Stop[0].hooks[0].statusMessage = "older release";
  old.hooks.Stop[0].matcher = "project";
  old.hooks.Stop[0].hooks.push({ type: "command", command: "echo keep-in-group" });
  old.hooks.Stop.push({ matcher: "other", hooks: [{ type: "command", command: "echo keep-other-group" }] });
  await writeFile(join(target, ".claude", "settings.json"), JSON.stringify(old));
  const result = python(INSTALL, "--host", "claude-code", "--target", target, "--json");
  assert.equal(result.status, 0, result.stderr);
  const installed = JSON.parse(await readFile(join(target, ".claude", "settings.json"), "utf8"));
  assert.equal(installed.hooks.Stop.filter((g) => JSON.stringify(g).includes("stop_gate.py")).length, 1);
  assert.ok(installed.hooks.Stop.some((g) => g.matcher === "project" && g.hooks.some((h) => h.command === "echo keep-in-group")));
  assert.ok(installed.hooks.Stop.some((g) => g.matcher === "other" && g.hooks.some((h) => h.command === "echo keep-other-group")));
});

test("v1 and malformed manifests block install before writes", { skip: !hasPython() && "Python not on PATH" }, async () => {
  const target = await mkdtemp(join(tmpdir(), "cql-v1-"));
  const cmd = [INSTALL, "--host", "claude-code", "--target", target, "--json"];
  assert.equal(python(...cmd).status, 0);
  const manifestPath = join(target, ".quality-loop", "install-manifest.json");
  const legacy = JSON.parse(await readFile(manifestPath, "utf8"));
  legacy.version = 1;
  delete legacy.file_hashes;
  await writeFile(manifestPath, JSON.stringify(legacy));
  const installedRuntime = await readFile(join(target, "scripts", "quality_loop.py"));
  const upgrade = python(...cmd);
  assert.notEqual(upgrade.status, 0);
  assert.match(JSON.parse(upgrade.stdout).failures[0], /v1.*no file checksums/);
  assert.match(JSON.parse(upgrade.stdout).failures[0], /Preserve .*install-manifest\.json/);
  assert.doesNotMatch(JSON.parse(upgrade.stdout).failures[0], /install-manifest\.v1\.json/);
  assert.equal((await readFile(manifestPath, "utf8")), JSON.stringify(legacy));
  assert.deepEqual(await readFile(join(target, "scripts", "quality_loop.py")), installedRuntime);
  const check = spawnSync(process.execPath, [CLI, "check", "--target", target], { encoding: "utf8" });
  assert.notEqual(check.status, 0);
  assert.match(check.stdout, /Preserve .*install-manifest\.json/);
  assert.doesNotMatch(check.stdout, /install-manifest\.v1\.json/);
  const remove = spawnSync(process.execPath, [CLI, "remove", "--target", target], { encoding: "utf8" });
  assert.notEqual(remove.status, 0);
  assert.match(remove.stdout, /v1.*no file checksums/);
  assert.deepEqual(await readFile(join(target, "scripts", "quality_loop.py")), installedRuntime);

  const bad = await mkdtemp(join(tmpdir(), "cql-bad-manifest-"));
  await mkdir(join(bad, ".quality-loop"));
  await writeFile(join(bad, ".quality-loop", "install-manifest.json"), "{invalid");
  const blocked = python(INSTALL, "--host", "claude-code", "--target", bad, "--json");
  assert.notEqual(blocked.status, 0);
  assert.match(JSON.parse(blocked.stdout).failures[0], /cannot read/);
  assert.equal(existsSync(join(bad, "scripts")), false);
});

test("linked worktree Git preflight leaves target untouched", { skip: !hasGit() && "git not on PATH" }, async () => {
  const parent = await mkdtemp(join(tmpdir(), "cql-worktree-"));
  const repo = join(parent, "repo");
  const worktree = join(parent, "worktree");
  await mkdir(repo);
  assert.equal(spawnSync("git", ["init", "-q"], { cwd: repo }).status, 0);
  await writeFile(join(repo, "README.md"), "fixture\n");
  assert.equal(spawnSync("git", ["add", "README.md"], { cwd: repo }).status, 0);
  assert.equal(spawnSync("git", ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-q", "-m", "initial"], { cwd: repo }).status, 0);
  assert.equal(spawnSync("git", ["worktree", "add", "-q", worktree], { cwd: repo }).status, 0);
  const result = spawnSync(process.execPath, [CLI, "init", "--yes", "--host", "claude-code", "--target", worktree], { encoding: "utf8" });
  assert.notEqual(result.status, 0);
  assert.match(result.stdout, /shared storage/);
  assert.equal(existsSync(join(worktree, "scripts")), false);
  assert.equal(existsSync(join(worktree, ".quality-loop")), false);
  const direct = python(INSTALL, "--host", "git", "--target", worktree, "--json");
  assert.notEqual(direct.status, 0);
  assert.match(JSON.parse(direct.stdout).failures[0], /shared hook/);
  assert.equal(existsSync(join(worktree, "scripts")), false);
  assert.equal(existsSync(join(worktree, ".quality-loop")), false);
});

test("prepack fails when a required skill input is missing", async () => {
  const fixture = await mkdtemp(join(tmpdir(), "cql-prepack-missing-"));
  const scriptDir = join(fixture, "packages", "npm", "scripts");
  await mkdir(scriptDir, { recursive: true });
  const script = join(scriptDir, "prepack.mjs");
  await copyFile(join(REPO, "packages", "npm", "scripts", "prepack.mjs"), script);
  const result = spawnSync(process.execPath, [script], { encoding: "utf8" });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /required package inputs missing:.*SKILL\.md/s);
});

test("prepack rejects a missing imported Python helper inside scripts/", async () => {
  const fixture = await mkdtemp(join(tmpdir(), "cql-prepack-helper-"));
  const script = join(fixture, "packages", "npm", "scripts", "prepack.mjs");
  await mkdir(dirname(script), { recursive: true });
  await copyFile(join(REPO, "packages", "npm", "scripts", "prepack.mjs"), script);
  // Recreate all top-level inputs so this specifically tests the nested file.
  for (const rel of [
    "scripts", "hosts", "assets", "references", ".claude", ".claude-plugin",
    "skills/test-integrity-gate", "SKILL.md", "LICENSE",
    "examples/claude-code", "examples/codex", "examples/cursor",
    "examples/droid", "examples/pi", "examples/standalone", "examples/walkthrough",
  ]) {
    const dest = join(fixture, rel);
    await mkdir(dirname(dest), { recursive: true });
    await cp(join(REPO, rel), dest, { recursive: true });
  }
  await rm(join(fixture, "scripts", "quality_loop_memory.py"));
  const result = spawnSync(process.execPath, [script], { encoding: "utf8" });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /required runtime files missing: scripts\/quality_loop_memory\.py/);
  await copyFile(join(REPO, "packages", "npm", "package.json"), join(fixture, "packages", "npm", "package.json"));
  const packed = spawnSync("npm", ["pack", "--offline", "--pack-destination", fixture], {
    cwd: join(fixture, "packages", "npm"),
    env: { ...process.env, npm_config_cache: join(fixture, "npm-cache") },
    encoding: "utf8",
  });
  assert.notEqual(packed.status, 0);
  assert.match(packed.stderr, /required runtime files missing: scripts\/quality_loop_memory\.py/);
});

test("offline tarball install runs the installed Python CLI", { skip: !hasPython() && "Python 3.10+ not on PATH" }, async () => {
  const fixture = await mkdtemp(join(tmpdir(), "cql-tarball-cli-"));
  const pkgRoot = join(REPO, "packages", "npm");
  const npmEnv = { ...process.env, npm_config_cache: join(fixture, "npm-cache") };
  const packed = spawnSync("npm", ["pack", "--offline", "--silent", "--pack-destination", fixture], {
    cwd: pkgRoot, env: npmEnv, encoding: "utf8",
  });
  assert.equal(packed.status, 0, packed.stderr);
  const tarball = join(fixture, packed.stdout.trim().split(/\r?\n/).at(-1));
  const consumer = join(fixture, "consumer");
  await mkdir(consumer);
  const installed = spawnSync("npm", [
    "install", "--offline", "--no-audit", "--no-fund", "--ignore-scripts", "--prefix", consumer, tarball,
  ], { env: npmEnv, encoding: "utf8" });
  assert.equal(installed.status, 0, installed.stderr);
  const cli = join(consumer, "node_modules", "coding-quality-loop", "bin", "cql.mjs");
  const target = join(fixture, "target");
  await mkdir(target);
  const init = spawnSync(process.execPath, [cli, "init", "--yes", "--host", "claude-code", "--target", target], {
    encoding: "utf8",
  });
  assert.equal(init.status, 0, init.stderr);
  const runtime = python("-B", join(target, "scripts", "quality_loop.py"), "--help");
  assert.equal(runtime.status, 0, runtime.stderr);
  assert.match(runtime.stdout, /usage:/i);
});
