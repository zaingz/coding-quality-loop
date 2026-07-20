// Host detection: scan a target directory for signals that identify which
// coding-agent host is in use. Returns detected host names in priority order
// so the CLI can preselect the right default.
import { access } from "node:fs/promises";
import { join } from "node:path";

async function exists(p) {
  try {
    await access(p);
    return true;
  } catch {
    return false;
  }
}

/**
 * @param {string} target absolute path to the project root
 * @returns {Promise<{hosts: string[], hints: string[], gitRepo: boolean}>}
 */
export async function detectHosts(target) {
  const hosts = new Set();
  const hints = [];

  // Order below determines priority when we pick a default.
  if (await exists(join(target, ".claude"))) {
    hosts.add("claude-code");
    hints.push(".claude/ directory");
  }
  // Some Claude Code projects rely on a root CLAUDE.md without .claude/.
  if (await exists(join(target, "CLAUDE.md"))) {
    hosts.add("claude-code");
    hints.push("CLAUDE.md");
  }
  if (await exists(join(target, "AGENTS.md"))) {
    // AGENTS.md is Codex's convention; if Claude Code was already detected we
    // keep both and let the user pick.
    hosts.add("codex");
    hints.push("AGENTS.md");
  }
  if (await exists(join(target, ".codex"))) {
    hosts.add("codex");
    hints.push(".codex/ directory");
  }
  if (await exists(join(target, ".cursor"))) {
    hosts.add("cursor");
    hints.push(".cursor/ directory");
  }
  if (await exists(join(target, ".factory"))) {
    hosts.add("droid");
    hints.push(".factory/ directory");
  }
  if (await exists(join(target, ".pi"))) {
    hosts.add("pi");
    hints.push(".pi/ directory");
  }

  const gitRepo = await exists(join(target, ".git"));

  return {
    hosts: Array.from(hosts),
    hints,
    gitRepo,
  };
}

// Hosts the interactive picker offers. cursor and pi are deliberately absent:
// they are advisory rules recipes in examples/ with no runtime install.
export const KNOWN_HOSTS = [
  "claude-code",
  "codex",
  "droid",
];
