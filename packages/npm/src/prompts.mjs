// Tiny readline-based prompts. Zero deps, no TTY dance beyond what node built-ins do.
// When --yes is set (or stdin isn't a TTY) prompts return their default silently.
import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import { c } from "./report.mjs";

/**
 * @param {object} opts
 * @param {string} opts.question
 * @param {boolean} [opts.default=true]
 * @param {boolean} [opts.assumeYes=false]
 */
export async function confirm({ question, default: def = true, assumeYes = false }) {
  const hint = def ? "Y/n" : "y/N";
  if (assumeYes || !input.isTTY) {
    console.log(`${c.cyan("?")} ${question} ${c.dim(`(${hint})`)} ${c.green(def ? "yes" : "no")}`);
    return def;
  }
  const rl = createInterface({ input, output });
  try {
    const answer = (await rl.question(`${c.cyan("?")} ${question} ${c.dim(`(${hint})`)} `)).trim().toLowerCase();
    if (answer === "") return def;
    return ["y", "yes"].includes(answer);
  } finally {
    rl.close();
  }
}

/**
 * @param {object} opts
 * @param {string} opts.question
 * @param {string[]} opts.choices
 * @param {string} [opts.default]
 * @param {boolean} [opts.assumeYes=false]
 */
export async function select({ question, choices, default: def, assumeYes = false }) {
  const fallback = def ?? choices[0];
  if (assumeYes || !input.isTTY) {
    console.log(`${c.cyan("?")} ${question} ${c.dim(`[${choices.join(", ")}]`)} ${c.green(fallback)}`);
    return fallback;
  }
  console.log(`${c.cyan("?")} ${question}`);
  choices.forEach((choice, i) => {
    const marker = choice === fallback ? c.green(" (default)") : "";
    console.log(`  ${c.dim(`${i + 1}.`)} ${choice}${marker}`);
  });
  const rl = createInterface({ input, output });
  try {
    const raw = (await rl.question(c.dim("  choice (number or name): "))).trim();
    if (raw === "") return fallback;
    const asNumber = Number.parseInt(raw, 10);
    if (Number.isInteger(asNumber) && asNumber >= 1 && asNumber <= choices.length) {
      return choices[asNumber - 1];
    }
    if (choices.includes(raw)) return raw;
    console.log(c.yellow(`  '${raw}' not recognised; using ${fallback}`));
    return fallback;
  } finally {
    rl.close();
  }
}
