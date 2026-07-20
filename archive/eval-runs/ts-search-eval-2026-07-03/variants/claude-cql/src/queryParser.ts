import type { Query } from "./types.js";

/**
 * Recursive-descent parser for the boolean query string grammar:
 *
 *   query      := orExpr
 *   orExpr     := andExpr ( "OR" andExpr )*            // default operator is OR
 *   andExpr    := notExpr ( ("AND")? notExpr )*         // adjacency implies AND... actually OR (see below)
 *   notExpr    := "NOT" notExpr | atom
 *   atom       := "(" orExpr ")" | phrase | fieldTerm | term
 *   phrase     := '"' ... '"'
 *   fieldTerm  := IDENT ":" (phrase | term)
 *   term       := IDENT
 *
 * Precedence (highest to lowest): NOT > AND > OR.
 * Default operator between adjacent atoms with no explicit connector is OR,
 * per the spec ("Default operator: OR").
 */

type TokenType = "AND" | "OR" | "NOT" | "LPAREN" | "RPAREN" | "COLON" | "PHRASE" | "WORD" | "EOF";

interface Token {
  type: TokenType;
  value: string;
}

function tokenize(input: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  const n = input.length;

  while (i < n) {
    const ch = input[i];

    if (ch !== undefined && /\s/u.test(ch)) {
      i++;
      continue;
    }

    if (ch === "(") {
      tokens.push({ type: "LPAREN", value: "(" });
      i++;
      continue;
    }
    if (ch === ")") {
      tokens.push({ type: "RPAREN", value: ")" });
      i++;
      continue;
    }
    if (ch === ":") {
      tokens.push({ type: "COLON", value: ":" });
      i++;
      continue;
    }
    if (ch === '"') {
      let j = i + 1;
      let value = "";
      while (j < n && input[j] !== '"') {
        value += input[j];
        j++;
      }
      tokens.push({ type: "PHRASE", value });
      i = j + 1; // skip closing quote if present
      continue;
    }

    // word: run of non-space, non-paren, non-colon, non-quote characters
    let j = i;
    let value = "";
    while (j < n) {
      const c = input[j];
      if (c === undefined) break;
      if (/\s/u.test(c) || c === "(" || c === ")" || c === ":" || c === '"') break;
      value += c;
      j++;
    }
    i = j;
    if (value.length === 0) {
      // Shouldn't happen, but avoid infinite loop.
      i++;
      continue;
    }
    const upper = value.toUpperCase();
    if (upper === "AND") tokens.push({ type: "AND", value });
    else if (upper === "OR") tokens.push({ type: "OR", value });
    else if (upper === "NOT") tokens.push({ type: "NOT", value });
    else tokens.push({ type: "WORD", value });
  }

  tokens.push({ type: "EOF", value: "" });
  return tokens;
}

class Parser {
  private pos = 0;
  constructor(private readonly tokens: Token[]) {}

  private peek(): Token {
    return this.tokens[this.pos] ?? { type: "EOF", value: "" };
  }

  private advance(): Token {
    const tok = this.peek();
    this.pos++;
    return tok;
  }

  parseQuery(): Query | undefined {
    if (this.peek().type === "EOF") return undefined;
    const q = this.parseOr();
    return q;
  }

  private parseOr(): Query | undefined {
    const terms: Query[] = [];
    const first = this.parseAnd();
    if (first) terms.push(first);
    for (;;) {
      const t = this.peek().type;
      if (t === "OR") {
        this.advance();
        const next = this.parseAnd();
        if (next) terms.push(next);
        continue;
      }
      // Implicit OR: another atom starts here with no explicit connector
      // (default operator is OR, per spec).
      if (t === "WORD" || t === "PHRASE" || t === "LPAREN") {
        const next = this.parseAnd();
        if (next) terms.push(next);
        continue;
      }
      break;
    }
    if (terms.length === 0) return undefined;
    if (terms.length === 1) return terms[0];
    return { or: terms };
  }

  private parseAnd(): Query | undefined {
    const nots: Query[] = [];
    const first = this.parseNot();
    if (first) nots.push(first);
    for (;;) {
      const t = this.peek().type;
      if (t === "AND") {
        this.advance();
        const next = this.parseNot();
        if (next) nots.push(next);
        continue;
      }
      // A bare NOT continues the same conjunctive clause ("a AND b NOT c"
      // means "a AND b AND (NOT c)"), matching the spec's example
      // literally. Only WORD/PHRASE/LPAREN start a *new* atom joined by the
      // default implicit OR; NOT does not.
      if (t === "NOT") {
        const next = this.parseNot();
        if (next) nots.push(next);
        continue;
      }
      // No explicit AND/NOT/RPAREN/EOF: an adjacent atom means implicit OR,
      // per spec default operator. Stop AND-collection here; let parseOr's
      // loop pick it up as a separate OR term.
      if (t === "WORD" || t === "PHRASE" || t === "LPAREN") {
        break;
      }
      break;
    }
    if (nots.length === 0) return undefined;
    if (nots.length === 1) return nots[0];
    return { and: nots };
  }

  private parseNot(): Query | undefined {
    if (this.peek().type === "NOT") {
      this.advance();
      const inner = this.parseNot();
      if (!inner) return undefined;
      return { not: inner };
    }
    return this.parseAtom();
  }

  private parseAtom(): Query | undefined {
    const tok = this.peek();

    if (tok.type === "LPAREN") {
      this.advance();
      const inner = this.parseOr();
      if (this.peek().type === "RPAREN") this.advance();
      return inner;
    }

    if (tok.type === "PHRASE") {
      this.advance();
      // Support field:"phrase"
      return { phrase: tok.value };
    }

    if (tok.type === "WORD") {
      this.advance();
      // Look ahead for field prefix: WORD COLON (WORD | PHRASE)
      if (this.peek().type === "COLON") {
        this.advance();
        const valueTok = this.peek();
        if (valueTok.type === "PHRASE") {
          this.advance();
          return { phrase: valueTok.value, field: tok.value };
        }
        if (valueTok.type === "WORD") {
          this.advance();
          return { term: valueTok.value, field: tok.value };
        }
        // field: followed by nothing usable — treat field name alone as a term.
        return { term: tok.value };
      }
      return { term: tok.value };
    }

    return undefined;
  }
}

/**
 * Parse a boolean query string into a structured Query AST.
 * Returns undefined for an empty/whitespace-only query.
 */
export function parseQueryString(input: string): Query | undefined {
  const trimmed = input.trim();
  if (trimmed.length === 0) return undefined;
  const tokens = tokenize(trimmed);
  const parser = new Parser(tokens);
  return parser.parseQuery();
}
