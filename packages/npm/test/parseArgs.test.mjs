// Argv parser tests. The CLI is hand-rolled (zero deps), so this parser has to
// stay simple and correct. These tests pin the shapes the rest of the code
// relies on.
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseArgs } from "../src/cli.mjs";

test("bare command sets positional", () => {
  const a = parseArgs(["init"]);
  assert.deepEqual(a._, ["init"]);
  assert.deepEqual(a.flags, {});
});

test("boolean flag with no value", () => {
  const a = parseArgs(["init", "--yes"]);
  assert.equal(a.flags.yes, true);
});

test("flag with =value inline", () => {
  const a = parseArgs(["init", "--host=claude-code"]);
  assert.equal(a.flags.host, "claude-code");
});

test("flag with space-separated value", () => {
  const a = parseArgs(["init", "--host", "codex"]);
  assert.equal(a.flags.host, "codex");
});

test("multiple flags parse independently", () => {
  const a = parseArgs(["init", "--host", "pi", "--dry-run", "--yes"]);
  assert.equal(a.flags.host, "pi");
  assert.equal(a.flags["dry-run"], true);
  assert.equal(a.flags.yes, true);
});

test("-h short flag maps to help", () => {
  const a = parseArgs(["-h"]);
  assert.equal(a.flags.help, true);
});

test("-v short flag maps to version", () => {
  const a = parseArgs(["-v"]);
  assert.equal(a.flags.version, true);
});

test("subcommand + positional arg", () => {
  const a = parseArgs(["add", "git"]);
  assert.deepEqual(a._, ["add", "git"]);
});

test("--target with a leading dot value is treated as a value, not a flag", () => {
  // Our parser only treats the *next* argv as a value if it doesn't start with
  // a dash. Passing a value that starts with "." (e.g. ".") is valid.
  const a = parseArgs(["init", "--target", "."]);
  assert.equal(a.flags.target, ".");
});
