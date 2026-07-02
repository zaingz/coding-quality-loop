#!/usr/bin/env node
// Entry point for `npx coding-quality-loop` / `npx cql`.
// Kept tiny; all logic lives in src/cli.mjs so the entry stays under 20 lines.
import { run } from "../src/cli.mjs";

run(process.argv.slice(2)).then(
  (code) => process.exit(code ?? 0),
  (err) => {
    // Deliberately compact: users care about the message, not the stack.
    // Set DEBUG=1 to see the full stack when reporting bugs.
    const debug = process.env.DEBUG === "1";
    console.error(`\n\u001b[31merror:\u001b[0m ${err?.message ?? err}`);
    if (debug && err?.stack) console.error(err.stack);
    else console.error("(set DEBUG=1 for a full stack trace)");
    process.exit(1);
  },
);
