// CLI dispatcher. Parses argv by hand (no yargs/commander) to keep zero deps
// and shave ~200ms off cold start.
import { resolve, join } from "node:path";
import { existsSync } from "node:fs";
import { detectHosts, KNOWN_HOSTS } from "./detect.mjs";
import { confirm, select } from "./prompts.mjs";
import { runInstall, runUninstall, checkInstall, readSkillVersion } from "./install.mjs";
import { c, header, info, ok, warn, fail, box } from "./report.mjs";

const HELP = `
${c.bold("coding-quality-loop")} — one-command installer for the Coding Quality Loop skill.

${c.bold("Usage")}
  npx coding-quality-loop init              interactive install (auto-detects host)
  npx coding-quality-loop init --yes        accept all defaults (non-interactive)
  npx coding-quality-loop init --host <h>   install for a specific host
  npx coding-quality-loop init --dry-run    preview without writing files
  npx coding-quality-loop add <host>        add wiring for one host to an existing project
  npx coding-quality-loop check             verify a prior install against its manifest
  npx coding-quality-loop remove            uninstall: remove manifest-listed files, reverse hook wiring
  npx coding-quality-loop --version         print version
  npx coding-quality-loop --help            show this help

${c.bold("Hosts")}
  claude-code, codex, droid, git, github
  (cursor and pi: advisory rules recipes live in the repo's examples/ — no runtime install)

${c.bold("Examples")}
  npx coding-quality-loop init
  npx coding-quality-loop init --host claude-code --yes
  npx coding-quality-loop add git
  npx cql check

Docs: https://github.com/zaingz/coding-quality-loop
`.trim();

// Flags that take a value. Everything else is boolean, so a boolean flag can
// never swallow the token after it (`cql --dry-run check` must run `check`).
const VALUE_FLAGS = new Set(["host", "target"]);

export function parseArgs(argv) {
  const args = { _: [], flags: {} };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const [key, inline] = a.slice(2).split("=");
      if (inline !== undefined) {
        args.flags[key] = inline;
      } else if (VALUE_FLAGS.has(key) && argv[i + 1] !== undefined && !argv[i + 1].startsWith("-")) {
        args.flags[key] = argv[i + 1];
        i++;
      } else {
        args.flags[key] = true;
      }
    } else if (a === "-h") {
      args.flags.help = true;
    } else if (a === "-v") {
      args.flags.version = true;
    } else {
      args._.push(a);
    }
  }
  return args;
}

async function commandInit(args) {
  const assumeYes = Boolean(args.flags.yes);
  const dryRun = Boolean(args.flags["dry-run"]);
  const target = resolve(String(args.flags.target ?? process.cwd()));

  header(
    `Coding Quality Loop v${await readSkillVersion()}`,
    "Make your AI coding agent ship changes you can trust.",
  );

  const { hosts: detected, hints, gitRepo } = await detectHosts(target);
  if (detected.length > 0) {
    ok(`Detected host${detected.length > 1 ? "s" : ""}: ${c.bold(detected.join(", "))} ${c.dim(`(${hints.join(", ")})`)}`);
  } else {
    info("No existing host wiring detected.");
  }
  ok(`Target: ${c.bold(target)}`);
  ok(`Git repo: ${gitRepo ? "yes" : c.yellow("no (git backstop will be skipped)")}`);

  let host = args.flags.host;
  if (!host) {
    const options = [...KNOWN_HOSTS, "all"];
    // Detection may surface hosts the picker no longer offers (cursor/pi are
    // advisory recipes now); only preselect a host we can actually install.
    const preferred = detected.find((h) => options.includes(h)) ?? "claude-code";
    host = await select({
      question: "Which host should the loop wire up?",
      choices: options,
      default: preferred,
      assumeYes,
    });
  }

  const wireGit = gitRepo && await confirm({
    question: "Also wire the git pre-commit backstop (recommended)?",
    default: true,
    assumeYes,
  });

  console.log("");
  info(`Installing loop for ${c.bold(host)}${dryRun ? c.yellow(" (dry run)") : ""}...`);
  const primary = await runInstall({ host, target, dryRun });
  primary.report.forEach((line) => ok(line));

  let git = null;
  if (wireGit && host !== "git" && host !== "all") {
    console.log("");
    info(`Installing git pre-commit hook${dryRun ? c.yellow(" (dry run)") : ""}...`);
    git = await runInstall({ host: "git", target, dryRun });
    git.report.forEach((line) => ok(line));
  }

  console.log("");
  const invokeExample = {
    "claude-code": 'claude "Use the coding-quality-loop skill to fix a small bug"',
    codex: 'codex "Follow the Coding Quality Loop in AGENTS.md to fix a small bug"',
    cursor: 'in chat: @coding-quality-loop fix the retry bug',
    droid: 'droid exec "Follow the Coding Quality Loop to fix a small bug"',
    pi: '/skill:coding-quality-loop fix a small bug with verification evidence',
    all: 'pick your host, then follow its example',
    git: 'git commit — pre-commit will now block staged diff-audit findings',
    github: 'the composite action is wired in .github/workflows/quality-loop.yml',
  }[host] ?? 'see README';

  // `setup-models` is model-router config and is only meaningful for LLM-driven
  // hosts. `git` and `github` are deterministic hook installers; suggesting
  // `setup-models --host git` would just error. Skip that step for those.
  const modelRoutedHost = host === "all" ? "claude-code" : host;
  const showSetupModels = host !== "git" && host !== "github";
  // Every command printed here must exit 0 on a fresh install of this host.
  const steps = [];
  let n = 0;
  // Step 0 — commit the install so the ~59 installed files stay out of the
  // task diff (an uncommitted install pollutes every scope/diff gate until it
  // lands). Same wording as scripts/install.py's footer.
  steps.push(`${n++}. ${c.bold("Commit the install:")} git add -A && git commit -m "chore: install coding-quality-loop"`);
  if (showSetupModels) {
    const hasRootConfig = existsSync(join(target, "quality-loop.config.json"));
    if (hasRootConfig) {
      steps.push(`${n++}. ${c.bold("Check your config:")}  quality-loop.config.json exists — make sure model_routing.host is set`);
    } else {
      // Set model_routing.host to the detected host so cross-family review
      // enforcement actually activates (kept in sync with scripts/install.py).
      steps.push(`${n++}. ${c.bold("Create your config:")} cp assets/quality-loop.config.example.json quality-loop.config.json, then set model_routing.host to "${modelRoutedHost}" so cross-family review enforcement activates`);
    }
    steps.push(`${n++}. ${c.bold("Set your models:")}    python3 scripts/quality_loop.py setup-models --host ${modelRoutedHost}`);
  }
  steps.push(`${n++}. ${c.bold("Try it out:")}         ${invokeExample}`);
  // Merge-base anti-evasion and helper-integrity are CI-anchored, so a local
  // install alone does not enforce them — point at the GitHub Action.
  steps.push(`${n++}. ${c.bold("Wire the CI anchor:")} add the GitHub Action (action.yml / hosts/github/quality-loop-example.yml) — merge-base anti-evasion and helper integrity are enforced in CI`);
  steps.push(``);
  steps.push(c.dim(`Docs: https://github.com/zaingz/coding-quality-loop#quickstart`));
  box("Next steps:", steps);
  return 0;
}

async function commandAdd(args) {
  const host = args._[1];
  if (!host) {
    fail("Missing host. Usage: cql add <host>");
    console.log(`Available hosts: ${KNOWN_HOSTS.join(", ")}, git, github`);
    return 1;
  }
  const target = resolve(String(args.flags.target ?? process.cwd()));
  const dryRun = Boolean(args.flags["dry-run"]);
  header(`Add ${host}`, `Target: ${target}`);
  const result = await runInstall({ host, target, dryRun });
  result.report.forEach((line) => ok(line));
  return 0;
}

async function commandCheck(args) {
  const target = resolve(String(args.flags.target ?? process.cwd()));
  header("Check", `Target: ${target}`);
  const result = await checkInstall(target);
  console.log("");
  if (result.findings.length > 0) {
    warn(`${result.findings.length} missing item${result.findings.length === 1 ? "" : "s"} — run \`cql init\` to fix`);
    return 1;
  }
  ok("Install looks healthy.");
  return 0;
}

async function commandRemove(args) {
  const target = resolve(String(args.flags.target ?? process.cwd()));
  const dryRun = Boolean(args.flags["dry-run"]);
  header(`Remove${dryRun ? " (dry run)" : ""}`, `Target: ${target}`);
  const result = await runUninstall({ target, dryRun });
  console.log("");
  result.report.forEach((line) => (result.code === 0 ? ok(line) : warn(line)));
  return result.code === 0 ? 0 : 1;
}

export async function run(argv) {
  const args = parseArgs(argv);
  if (args.flags.help || args._[0] === "help") {
    console.log(HELP);
    return 0;
  }
  if (args.flags.version) {
    console.log(await readSkillVersion());
    return 0;
  }
  const cmd = args._[0] ?? "init";
  switch (cmd) {
    case "init":
      return commandInit(args);
    case "add":
      return commandAdd(args);
    case "check":
      return commandCheck(args);
    case "remove":
      return commandRemove(args);
    default:
      fail(`Unknown command: ${cmd}`);
      console.log(HELP);
      return 1;
  }
}
