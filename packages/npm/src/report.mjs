// Minimal ANSI-colored output helpers. Zero deps.
// Colors auto-disable when NO_COLOR is set or stdout is not a TTY.

const isColor = process.stdout.isTTY && !process.env.NO_COLOR;

const wrap = (code) => (s) => (isColor ? `\u001b[${code}m${s}\u001b[0m` : s);

export const c = {
  bold: wrap("1"),
  dim: wrap("2"),
  red: wrap("31"),
  green: wrap("32"),
  yellow: wrap("33"),
  blue: wrap("34"),
  cyan: wrap("36"),
  gray: wrap("90"),
};

export function header(title, subtitle) {
  const line = "─".repeat(Math.max(0, 62 - title.length));
  console.log(`\n${c.bold(c.cyan("┌─ " + title + " " + line + "┐"))}`);
  if (subtitle) console.log(c.cyan("│ ") + subtitle);
  console.log(c.bold(c.cyan("└" + "─".repeat(65) + "┘")));
}

export const ok = (msg) => console.log(`${c.green("\u2713")} ${msg}`);
export const info = (msg) => console.log(`${c.cyan("\u2192")} ${msg}`);
export const warn = (msg) => console.log(`${c.yellow("!")} ${msg}`);
export const fail = (msg) => console.log(`${c.red("\u2717")} ${msg}`);
export const step = (msg) => console.log(c.dim(msg));

export function box(title, lines) {
  console.log(`\n${c.bold(title)}`);
  for (const l of lines) console.log(`  ${l}`);
}
