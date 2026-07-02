// Delegate the actual file copying + host wiring to the bundled Python
// install.py, which is the same script the repo ships. This keeps the Node
// layer as a thin UX shell and means the two installers (CLI and repo-local)
// can never disagree.
import { spawn, spawnSync } from "node:child_process";
import { access, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";
import { c, info, ok, warn } from "./report.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
// dist/skill is populated at prepack time. During local development it may
// point at the repo root (see resolveSkillRoot below).
const PACKAGE_ROOT = resolve(HERE, "..");
const DIST_SKILL = join(PACKAGE_ROOT, "dist", "skill");

async function pathExists(p) {
  try {
    await access(p);
    return true;
  } catch {
    return false;
  }
}

/**
 * Locate the vendored skill files. In a published tarball this is dist/skill.
 * During local development we fall back to the repo root (two levels up from
 * packages/npm/), so the CLI is runnable without a prepack step.
 */
export async function resolveSkillRoot() {
  if (await pathExists(join(DIST_SKILL, "scripts", "install.py"))) {
    return DIST_SKILL;
  }
  const repoRoot = resolve(PACKAGE_ROOT, "..", "..");
  if (await pathExists(join(repoRoot, "scripts", "install.py"))) {
    return repoRoot;
  }
  throw new Error(
    "Skill files not found. Expected dist/skill/ (published) or the repo root (local dev).",
  );
}

/**
 * Pick a python3 binary. Prefers `python3`, falls back to `python`.
 */
export function resolvePython() {
  for (const candidate of ["python3", "python"]) {
    const probe = spawnSync(candidate, ["--version"], { stdio: "ignore" });
    if (probe.status === 0) return candidate;
  }
  throw new Error(
    "Python 3 is required but was not found on PATH. Install from https://www.python.org/downloads/ and re-run.",
  );
}

/**
 * @param {object} opts
 * @param {string} opts.host
 * @param {string} opts.target absolute path
 * @param {boolean} [opts.dryRun]
 * @returns {Promise<{code: number, report: string[], hostsInstalled: string[]}>}
 */
export async function runInstall({ host, target, dryRun = false }) {
  const skillRoot = await resolveSkillRoot();
  const python = resolvePython();
  const installScript = join(skillRoot, "scripts", "install.py");

  const args = [installScript, "--target", target, "--host", host, "--json"];
  if (dryRun) args.push("--dry-run");

  info(`Running ${c.dim(`${python} ${args.map((a) => (a.includes(" ") ? `"${a}"` : a)).join(" ")}`)}`);

  return await new Promise((resolvePromise, reject) => {
    const child = spawn(python, args, { stdio: ["ignore", "pipe", "inherit"] });
    let stdout = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`install.py exited with code ${code}`));
        return;
      }
      try {
        const payload = JSON.parse(stdout);
        resolvePromise({
          code,
          report: payload.report ?? [],
          hostsInstalled: payload.hosts_installed ?? [],
          footer: payload.footer ?? [],
        });
      } catch (err) {
        reject(new Error(`Could not parse install.py output as JSON: ${err.message}\n---\n${stdout}`));
      }
    });
  });
}

/**
 * Verify a prior install is intact. Read-only, cheap.
 * @param {string} target
 */
export async function checkInstall(target) {
  const findings = [];
  const checks = [
    { path: "scripts/quality_loop.py", label: "core script" },
    { path: "assets/quality-loop.config.example.json", label: "example config" },
  ];
  for (const { path, label } of checks) {
    if (await pathExists(join(target, path))) {
      ok(`${label}: ${path}`);
    } else {
      warn(`missing ${label}: ${path}`);
      findings.push(path);
    }
  }
  const hosts = [
    { path: ".claude/settings.json", label: "Claude Code hooks" },
    { path: ".codex/hooks.json", label: "Codex hooks" },
    { path: ".cursor/rules", label: "Cursor rules" },
    { path: ".factory/droids", label: "Droid droids" },
    { path: ".pi/settings.json", label: "Pi settings" },
    { path: ".pre-commit-config.yaml", label: "git pre-commit" },
  ];
  const foundHosts = [];
  for (const { path, label } of hosts) {
    if (await pathExists(join(target, path))) {
      ok(`${label} wired at ${path}`);
      foundHosts.push(label);
    }
  }
  if (foundHosts.length === 0) {
    warn("no host wiring detected — run `cql init` to set up");
  }
  return { findings, foundHosts };
}

/**
 * Read the vendored version to display in --version. Falls back to the
 * package.json version if the skill CHANGELOG can't be read.
 */
export async function readSkillVersion() {
  try {
    const pkg = JSON.parse(
      await readFile(join(PACKAGE_ROOT, "package.json"), "utf8"),
    );
    return pkg.version;
  } catch {
    return "unknown";
  }
}
