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
        // A nonzero exit still emits the JSON report; surface its failures
        // instead of a bare exit code so the user sees what to fix.
        let detail = "";
        try {
          const failures = JSON.parse(stdout).failures ?? [];
          if (failures.length > 0) detail = `\n${failures.join("\n")}`;
        } catch {
          // stdout was not JSON; the bare exit code is all we have.
        }
        reject(new Error(`install.py exited with code ${code}${detail}`));
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
 * Reverse a manifest-recorded install via install.py --uninstall.
 * Resolves even on a nonzero exit (e.g. missing manifest) so the caller can
 * show the report; rejects only if the output is unusable.
 * @param {object} opts
 * @param {string} opts.target absolute path
 * @param {boolean} [opts.dryRun]
 * @returns {Promise<{code: number, report: string[]}>}
 */
export async function runUninstall({ target, dryRun = false }) {
  const skillRoot = await resolveSkillRoot();
  const python = resolvePython();
  const installScript = join(skillRoot, "scripts", "install.py");
  const args = [installScript, "--target", target, "--uninstall", "--json"];
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
      try {
        const payload = JSON.parse(stdout);
        resolvePromise({ code: code ?? 1, report: payload.report ?? [] });
      } catch (err) {
        reject(new Error(`Could not parse install.py output as JSON: ${err.message}\n---\n${stdout}`));
      }
    });
  });
}

/**
 * Verify a prior install against its manifest. Read-only, cheap, and
 * host-aware: the manifest records exactly what that host's install wrote,
 * so nothing hand-maintained can drift out of sync with install.py.
 * @param {string} target
 */
export async function checkInstall(target) {
  const manifestRel = ".quality-loop/install-manifest.json";
  const findings = [];
  let manifest;
  try {
    manifest = JSON.parse(await readFile(join(target, manifestRel), "utf8"));
  } catch (err) {
    if (err?.code === "ENOENT") {
      warn(`no install manifest found at ${manifestRel}`);
      info("nothing is recorded to verify — installs before v6.0.0 wrote no manifest. Run `cql init` to (re)install and record one.");
    } else {
      warn(`could not read ${manifestRel}: ${err.message}`);
      info("delete the manifest and run `cql init` to regenerate it.");
    }
    return { findings: [manifestRel], foundHosts: [] };
  }
  // Shape validation: an empty or wrong-shaped manifest ({}, missing host,
  // empty files, traversing paths) must FAIL the check, not read as healthy.
  const SUPPORTED_HOSTS = new Set(["claude-code", "codex", "cursor", "droid", "pi", "git", "github"]);
  const hosts = String(manifest.host ?? "").split(",").filter(Boolean);
  const allFiles = (Array.isArray(manifest.files) ? manifest.files : []).filter(
    (f) => typeof f === "string",
  );
  const isUnsafe = (f) =>
    f.trim() === "" ||
    f.startsWith("/") ||
    /^[A-Za-z]:[\\/]/.test(f) ||
    f.split(/[\\/]+/).includes("..");
  const files = allFiles.filter((f) => !isUnsafe(f));
  const shapeProblems = [];
  if (manifest.version !== 1) {
    shapeProblems.push(`manifest version is ${JSON.stringify(manifest.version ?? null)} (expected 1)`);
  }
  if (hosts.length === 0) {
    shapeProblems.push("manifest records no host");
  }
  for (const h of hosts) {
    if (!SUPPORTED_HOSTS.has(h)) shapeProblems.push(`manifest records unsupported host: ${h}`);
  }
  if (files.length === 0) {
    shapeProblems.push("manifest lists no installed files");
  }
  for (const f of allFiles) {
    if (isUnsafe(f)) shapeProblems.push(`manifest lists an unsafe path (absolute or ..): ${f}`);
  }
  if (shapeProblems.length > 0) {
    for (const p of shapeProblems) warn(p);
    info("the manifest is not a valid install record — run `cql init` to reinstall and regenerate it.");
    findings.push(...shapeProblems);
  }
  let present = 0;
  for (const rel of files) {
    if (await pathExists(join(target, rel))) {
      present++;
    } else {
      warn(`missing ${rel}`);
      findings.push(rel);
    }
  }
  ok(`${present}/${files.length} recorded files present (host${hosts.length === 1 ? "" : "s"}: ${hosts.join(", ") || "unknown"})`);
  const groups = (Array.isArray(manifest.hook_groups) ? manifest.hook_groups : []).filter(
    (g) => g && typeof g.file === "string" && typeof g.key === "string",
  );
  for (const g of groups) {
    let wired = false;
    try {
      const body = await readFile(join(target, g.file), "utf8");
      if (g.key === "managed-section") {
        wired = body.includes("BEGIN coding-quality-loop");
      } else {
        const wiredGroups = JSON.parse(body)?.hooks?.[g.key];
        wired = Array.isArray(wiredGroups) && wiredGroups.length > 0;
      }
    } catch {
      wired = false;
    }
    if (wired) {
      ok(`${g.file} wires ${g.key}`);
    } else {
      warn(`${g.file} no longer wires ${g.key}`);
      findings.push(`${g.file}#${g.key}`);
    }
  }
  return { findings, foundHosts: hosts };
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
