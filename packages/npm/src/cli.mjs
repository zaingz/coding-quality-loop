// CLI dispatcher. Parses argv by hand (no yargs/commander) to keep zero deps
// and shave ~200ms off cold start.
import { resolve } from "node:path";
import { detectHosts, KNOWN_HOSTS } from "./detect.mjs";
import { confirm, select } from "./prompts.mjs";
import { runInstall, checkInstall, readSkillVersion } from "./install.mjs";
import { c, header, info, ok, warn, fail, box } from "./report.mjs";

const HELP = `
${c.bold("coding-quality-loop")} — one-command installer for the Coding Quality Loop skill.

${c.bold("Usage")}
  npx coding-quality-loop init              interactive install (auto-detects host)
  npx coding-quality-loop init --yes        accept all defaults (non-interactive)
  npx coding-quality-loop init --host <h>   install for a specific host
  npx coding-quality-loop init --dry-run    preview without writing files
  npx coding-quality-loop add <host>        add wiring for one host to an existing project
  npx coding-quality-loop check             verify a prior install is intact
  npx coding-quality-loop --version         print version
  npx coding-quality-loop --help            show this help

${c.bold("Hosts")}
  claude-code, codex, cursor, droid, pi, git, github

${c.bold("Examples")}
  npx coding-quality-loop init
  npx coding-quality-loop init --host claude-code --yes
  npx coding-quality-loop add git
  npx cql check

Docs: https://github.com/zaingz/coding-quality-loop
`.trim();

export function parseArgs(argv) {
  const args = { _: [], flags: {} };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const [key, inline] = a.slice(2).split("=");
      if (inline !== undefined) {
        args.flags[key] = inline;
      } else if (argv[i + 1] && !argv[i + 1].startsWith("-")) {
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
    const preferred = detected[0] ?? "claude-code";
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
  const steps = [];
  let n = 1;
  if (showSetupModels) {
    steps.push(`${n++}. ${c.bold("Set your models:")}   python3 scripts/quality_loop.py setup-models --host ${modelRoutedHost}`);
  }
  steps.push(`${n++}. ${c.bold("Try it out:")}        ${invokeExample}`);
  if (host !== "git" && host !== "github") {
    steps.push(`${n++}. ${c.bold("Run the evals:")}     python3 evals/run_evals.py`);
  }
  steps.push(``);
  steps.push(c.dim(`Docs: https://github.com/zaingz/coding-quality-loop#quickstart-60-seconds`));
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
  if (result.foundHosts.length === 0) {
    warn("No host wiring found — run `cql init`");
    return 1;
  }
  ok("Install looks healthy.");
  return 0;
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
    default:
      fail(`Unknown command: ${cmd}`);
      console.log(HELP);
      return 1;
  }
}
