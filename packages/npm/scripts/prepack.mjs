#!/usr/bin/env node
// Vendor the skill files into dist/skill/ so the published tarball is
// self-contained. Runs automatically before `npm pack` / `npm publish`.
//
// Copies only what the CLI needs at runtime: scripts/, hosts/, assets/,
// examples/{claude-code,codex,cursor,droid,pi,standalone}/, .claude/,
// SKILL.md, README.md, LICENSE. The evals and the optional control plane
// (assets/control-plane/, scripts/quality_loop_control.py) stay out of the
// tarball — the control plane is an in-repo opt-in add-on.
import { cp, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT = resolve(HERE, "..");
const REPO_ROOT = resolve(PACKAGE_ROOT, "..", "..");
const DIST = join(PACKAGE_ROOT, "dist", "skill");

// Paths are relative to REPO_ROOT. Everything else is left behind.
const INCLUDE = [
  "scripts",
  "hosts",
  "assets",
  "references",
  ".claude",
  "SKILL.md",
  "LICENSE",
  "examples/claude-code",
  "examples/codex",
  "examples/cursor",
  "examples/droid",
  "examples/pi",
  "examples/standalone",
  "examples/walkthrough",
];

// Removed from dist/ after the INCLUDE copy: shipped-by-directory paths that
// must not reach the tarball. The control plane is an optional in-repo add-on
// (`install.py --with-control-plane` from a git clone).
const EXCLUDE = [
  "assets/control-plane",
  "scripts/quality_loop_control.py",
];

async function copyIfExists(rel) {
  const src = join(REPO_ROOT, rel);
  const dest = join(DIST, rel);
  try {
    await cp(src, dest, { recursive: true, force: true });
    return true;
  } catch (err) {
    if (err.code === "ENOENT") return false;
    throw err;
  }
}

// Remove Python bytecode caches. `.npmignore` is ignored when `files` is set
// in package.json, so we strip these directly instead of relying on filters.
async function stripPyCache(root) {
  let stripped = 0;
  async function walk(dir) {
    let entries;
    try {
      entries = await readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === "__pycache__") {
          await rm(full, { recursive: true, force: true });
          stripped++;
        } else {
          await walk(full);
        }
      } else if (entry.name.endsWith(".pyc")) {
        await rm(full, { force: true });
        stripped++;
      }
    }
  }
  await walk(root);
  return stripped;
}

// Shipped templates stay host-neutral at rest: the repo's own agent files may
// carry an operator's activated routing (model:/effort: pins written by
// setup-models), and the tarball must not republish them. Mirrors
// install.py's copy_agent_neutral; only the leading frontmatter is touched.
async function neutralizeAgentPins(agentsDir) {
  let entries;
  try {
    entries = await readdir(agentsDir);
  } catch (err) {
    if (err.code === "ENOENT") return 0;
    throw err;
  }
  let changed = 0;
  for (const name of entries) {
    if (!name.endsWith(".md")) continue;
    const path = join(agentsDir, name);
    const body = await readFile(path, "utf8");
    if (!body.startsWith("---\n")) continue;
    const end = body.indexOf("\n---", 4);
    if (end === -1) continue;
    const head = body
      .slice(0, end + 4)
      .replace(/^model:.*$/m, "model: inherit")
      .replace(/^(?:effort|reasoningEffort):.*\n/gm, "");
    const neutral = head + body.slice(end + 4);
    if (neutral !== body) {
      await writeFile(path, neutral, "utf8");
      changed += 1;
    }
  }
  return changed;
}

async function main() {
  await rm(DIST, { recursive: true, force: true });
  await mkdir(DIST, { recursive: true });
  const copied = [];
  const missing = [];
  for (const rel of INCLUDE) {
    if (await copyIfExists(rel)) copied.push(rel);
    else missing.push(rel);
  }
  for (const rel of EXCLUDE) {
    await rm(join(DIST, rel), { recursive: true, force: true });
  }
  const neutralized = await neutralizeAgentPins(join(DIST, ".claude", "agents"));
  const stripped = await stripPyCache(DIST);
  console.log(`prepack: copied ${copied.length} paths -> dist/skill/ (stripped ${stripped} pycache entries, neutralized ${neutralized} agent pin(s))`);
  copied.forEach((p) => console.log(`  ok  ${p}`));
  if (missing.length > 0) {
    console.warn(`prepack: ${missing.length} paths not found (ok for optional):`);
    missing.forEach((p) => console.warn(`  --  ${p}`));
  }
}

main().catch((err) => {
  console.error("prepack failed:", err);
  process.exit(1);
});
