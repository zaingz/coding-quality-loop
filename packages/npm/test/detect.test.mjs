// Host detection tests. Detection powers the default-host suggestion in
// `init`, so wrong answers become surprising defaults. These tests use real
// temp dirs so we exercise the same fs code the CLI runs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { detectHosts, KNOWN_HOSTS } from "../src/detect.mjs";

async function scratch() {
  return await mkdtemp(join(tmpdir(), "cql-detect-"));
}

test("empty dir detects no hosts and no git repo", async () => {
  const t = await scratch();
  const r = await detectHosts(t);
  assert.deepEqual(r.hosts, []);
  assert.equal(r.gitRepo, false);
});

test(".claude/ marks claude-code", async () => {
  const t = await scratch();
  await mkdir(join(t, ".claude"), { recursive: true });
  const r = await detectHosts(t);
  assert.ok(r.hosts.includes("claude-code"));
  assert.ok(r.hints.some((h) => h.includes(".claude")));
});

test("AGENTS.md marks codex", async () => {
  const t = await scratch();
  await writeFile(join(t, "AGENTS.md"), "# agents\n");
  const r = await detectHosts(t);
  assert.ok(r.hosts.includes("codex"));
});

test(".cursor/ marks cursor", async () => {
  const t = await scratch();
  await mkdir(join(t, ".cursor"), { recursive: true });
  const r = await detectHosts(t);
  assert.ok(r.hosts.includes("cursor"));
});

test(".pi/ marks pi", async () => {
  const t = await scratch();
  await mkdir(join(t, ".pi"), { recursive: true });
  const r = await detectHosts(t);
  assert.ok(r.hosts.includes("pi"));
});

test(".git/ toggles gitRepo=true", async () => {
  const t = await scratch();
  await mkdir(join(t, ".git"), { recursive: true });
  const r = await detectHosts(t);
  assert.equal(r.gitRepo, true);
});

test("mixed markers surface all matching hosts", async () => {
  const t = await scratch();
  await mkdir(join(t, ".claude"), { recursive: true });
  await mkdir(join(t, ".codex"), { recursive: true });
  await mkdir(join(t, ".git"), { recursive: true });
  const r = await detectHosts(t);
  assert.ok(r.hosts.includes("claude-code"));
  assert.ok(r.hosts.includes("codex"));
  assert.equal(r.gitRepo, true);
});

test("KNOWN_HOSTS covers all interactive host choices", () => {
  // If someone adds a host to detect.mjs, they must also add it here — this is
  // the list the interactive picker shows.
  for (const h of ["claude-code", "codex", "droid"]) {
    assert.ok(KNOWN_HOSTS.includes(h), `${h} missing from KNOWN_HOSTS`);
  }
  // cursor and pi are advisory rules recipes in examples/, not install targets.
  for (const h of ["cursor", "pi"]) {
    assert.ok(!KNOWN_HOSTS.includes(h), `${h} must not be in KNOWN_HOSTS`);
  }
});

test("package.json mentioning cursor is not a host signal", async () => {
  // Regression: the substring fallback misfired on any package.json that
  // happened to contain the word "cursor" (e.g. a caret/cursor UI dependency).
  const t = await scratch();
  await writeFile(join(t, "package.json"), JSON.stringify({ dependencies: { "cursor-position": "1.0.0" } }));
  const r = await detectHosts(t);
  assert.deepEqual(r.hosts, []);
});
