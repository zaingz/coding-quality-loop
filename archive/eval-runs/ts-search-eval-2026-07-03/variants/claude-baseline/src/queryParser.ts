/**
 * Parses a string query into the structured Query AST.
 *
 * Grammar (informal):
 *   query      := orExpr
 *   orExpr     := andExpr (OR andExpr)*
 *   andExpr    := notExpr (AND? notExpr)*      // implicit AND-adjacency is OR by default per spec;
 *                                                // explicit AND binds andExpr together.
 *   notExpr    := NOT? atom
 *   atom       := '(' orExpr ')' | fieldTerm | phrase | word
 *   fieldTerm  := IDENT ':' (phrase | word)
 *   phrase     := '"' .*? '"'
 *
 * Default operator between adjacent terms (no explicit AND/OR) is OR.
 * Precedence: NOT > AND > OR.
 */

import type { Query } from "./types.js";

type TokenType = "AND" | "OR" | "NOT" | "LPAREN" | "RPAREN" | "PHRASE" | "WORD" | "FIELD";

interface Token {
  type: TokenType;
  value: string;
  field?: string;
}

function lex(input: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  const n = input.length;

  const isSpace = (c: string): boolean => /\s/.test(c);
  // identifier chars for field names: letters/numbers/underscore
  const isIdentChar = (c: string): boolean => /[\p{L}\p{N}_]/u.test(c);

  while (i < n) {
    const c = input[i] as string;

    if (isSpace(c)) {
      i++;
      continue;
    }

    if (c === "(") {
      tokens.push({ type: "LPAREN", value: "(" });
      i++;
      continue;
    }
    if (c === ")") {
      tokens.push({ type: "RPAREN", value: ")" });
      i++;
      continue;
    }

    if (c === '"') {
      let j = i + 1;
      let buf = "";
      while (j < n && input[j] !== '"') {
        buf += input[j];
        j++;
      }
      i = j < n ? j + 1 : j; // skip closing quote if present
      tokens.push({ type: "PHRASE", value: buf });
      continue;
    }

    // read a bare word/ident, possibly field:value or field:"phrase"
    if (isIdentChar(c)) {
      let j = i;
      while (j < n && isIdentChar(input[j] as string)) {
        j++;
      }
      const word = input.slice(i, j);

      if (input[j] === ":" && j + 1 < n) {
        // field prefix
        const fieldName = word;
        let k = j + 1;
        if (input[k] === '"') {
          let m = k + 1;
          let buf = "";
          while (m < n && input[m] !== '"') {
            buf += input[m];
            m++;
          }
          i = m < n ? m + 1 : m;
          tokens.push({ type: "FIELD", value: buf, field: fieldName });
          tokens[tokens.length - 1] = {
            type: "PHRASE",
            value: buf,
            field: fieldName,
          };
          continue;
        } else {
          let m = k;
          while (m < n && isIdentChar(input[m] as string)) {
            m++;
          }
          const fieldVal = input.slice(k, m);
          i = m;
          tokens.push({ type: "FIELD", value: fieldVal, field: fieldName });
          continue;
        }
      }

      const upper = word.toUpperCase();
      if (upper === "AND") {
        tokens.push({ type: "AND", value: word });
      } else if (upper === "OR") {
        tokens.push({ type: "OR", value: word });
      } else if (upper === "NOT") {
        tokens.push({ type: "NOT", value: word });
      } else {
        tokens.push({ type: "WORD", value: word });
      }
      i = j;
      continue;
    }

    // unknown character (punctuation etc.) - skip it
    i++;
  }

  return tokens;
}

class Parser {
  private tokens: Token[];
  private pos = 0;

  constructor(tokens: Token[]) {
    this.tokens = tokens;
  }

  private peek(): Token | undefined {
    return this.tokens[this.pos];
  }

  private next(): Token | undefined {
    return this.tokens[this.pos++];
  }

  parse(): Query | null {
    if (this.tokens.length === 0) {
      return null;
    }
    const q = this.parseOr();
    return q;
  }

  // orExpr := andExpr (OR andExpr)*
  // Bare adjacency between andExpr groups (no explicit OR token) also means OR,
  // per the spec's default-operator rule. We detect this by checking whether the
  // next token can start a new atom (WORD/PHRASE/FIELD/LPAREN/NOT) and, if so,
  // treat it as an implicit OR continuation rather than stopping.
  private parseOr(): Query | null {
    const parts: Query[] = [];
    const first = this.parseAnd();
    if (first) parts.push(first);

    for (;;) {
      const t = this.peek();
      if (!t) break;

      if (t.type === "OR") {
        this.next();
        const rhs = this.parseAnd();
        if (rhs) parts.push(rhs);
        continue;
      }

      if (t.type === "RPAREN" || t.type === "AND") {
        break;
      }

      if (
        t.type === "WORD" ||
        t.type === "PHRASE" ||
        t.type === "FIELD" ||
        t.type === "LPAREN" ||
        t.type === "NOT"
      ) {
        // Implicit OR: another andExpr follows with no explicit connector.
        const rhs = this.parseAnd();
        if (rhs) parts.push(rhs);
        continue;
      }

      break;
    }

    if (parts.length === 0) return null;
    if (parts.length === 1) return parts[0] as Query;
    return { or: parts };
  }

  // andExpr := notExpr ((AND notExpr) | notExpr-adjacent-treated-as-OR)*
  // Per spec, default operator is OR; explicit AND binds tighter than OR.
  // We implement: a run of notExpr connected ONLY by explicit AND forms one AND group.
  // Bare adjacency (no operator) also defaults to OR, so we stop the AND run
  // and let parseOr's loop treat the next atom as a new OR-part... but without
  // an explicit OR token, we must still combine them. To satisfy "default OR",
  // adjacency without operator is equivalent to explicit OR.
  private parseAnd(): Query | null {
    const parts: Query[] = [];
    const first = this.parseNot();
    if (first) parts.push(first);

    for (;;) {
      const t = this.peek();
      if (t && t.type === "AND") {
        this.next();
        const rhs = this.parseNot();
        if (rhs) parts.push(rhs);
      } else if (t && t.type === "NOT") {
        // Implicit AND before a NOT clause, e.g. "a AND b NOT c" parses
        // "b NOT c" as "b" followed directly by "NOT c"; the NOT clause
        // binds into the same AND group as the preceding term(s).
        const rhs = this.parseNot();
        if (rhs) parts.push(rhs);
      } else {
        break;
      }
    }

    if (parts.length === 0) return null;
    if (parts.length === 1) return parts[0] as Query;
    return { and: parts };
  }

  // notExpr := NOT? atom
  private parseNot(): Query | null {
    const t = this.peek();
    if (t && t.type === "NOT") {
      this.next();
      const atom = this.parseAtom();
      if (!atom) return null;
      return { not: atom };
    }
    return this.parseAtom();
  }

  private parseAtom(): Query | null {
    const t = this.peek();
    if (!t) return null;

    if (t.type === "LPAREN") {
      this.next();
      const inner = this.parseOr();
      const closing = this.peek();
      if (closing && closing.type === "RPAREN") {
        this.next();
      }
      return inner;
    }

    if (t.type === "PHRASE") {
      this.next();
      const q: Query = t.field
        ? { phrase: t.value, field: t.field }
        : { phrase: t.value };
      return q;
    }

    if (t.type === "FIELD") {
      this.next();
      return { term: t.value, field: t.field };
    }

    if (t.type === "WORD") {
      this.next();
      return { term: t.value };
    }

    // AND/OR/NOT/RPAREN in unexpected position: skip to avoid infinite loop
    this.next();
    return null;
  }
}

/**
 * Parses a query string into structured Query AST.
 * Adjacent terms without an explicit operator default to OR.
 * Returns null for empty/whitespace-only input.
 */
export function parseQueryString(input: string): Query | null {
  const trimmed = input.trim();
  if (trimmed.length === 0) {
    return null;
  }
  const tokens = lex(trimmed);
  if (tokens.length === 0) {
    return null;
  }
  const parser = new Parser(tokens);
  return parser.parse();
}
