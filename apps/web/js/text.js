// Text, numbers and status as the shell shows them (M06 design note §5.5).
//
// `sanitize` replaces the code points the server's projection bounding replaces (§10.4) with
// U+FFFD, so text the browser renders reads as the agents' text reads. `fmt` prints a JSON
// number short or in full, never rounding a value anything compares. `status` and `pill` map a
// status label to its glyph, word and tone: a label the table does not list is a failure tone.

import { h } from "./h.js";

// The table is checked against `openflowsheet.application.projection.FORBIDDEN_RANGES` by
// tests/test_m06_static_scan.py: keep it a literal between the two marker lines.
// BEGIN FORBIDDEN_RANGES
const FORBIDDEN_RANGES = [
  [0x00, 0x08],
  [0x0b, 0x1f],
  [0x7f, 0x9f],
  [0x200b, 0x200d],
  [0x2060, 0x2060],
  [0xfeff, 0xfeff],
  [0x202a, 0x202e],
  [0x2066, 0x2069],
  [0xd800, 0xdfff],
];
// END FORBIDDEN_RANGES

export const REPLACEMENT = "�";

function forbidden(code) {
  for (const [low, high] of FORBIDDEN_RANGES) if (code >= low && code <= high) return true;
  return false;
}

// Every forbidden code point of `text` replaced by U+FFFD, one for one, nothing cut. A string is
// read by code point, so a lone surrogate is replaced and a surrogate pair is kept.
export function sanitize(text) {
  const value = String(text);
  let out = "";
  let changed = false;
  for (const character of value) {
    if (forbidden(character.codePointAt(0))) {
      out += REPLACEMENT;
      changed = true;
    } else {
      out += character;
    }
  }
  return changed ? out : value;
}

export const DASH = "—";

// §5.5: null/undefined → "—"; an integer → String(x); otherwise "short" → 6 significant digits
// with the mantissa's trailing zeros and the exponent's "+" removed, "full" → String(x), the
// shortest text that reads back as the same binary64 (Python's repr spells it the same).
export function fmt(x, mode = "short") {
  if (x === null || x === undefined) return DASH;
  if (typeof x !== "number") return String(x);
  if (Number.isInteger(x) || mode === "full" || !Number.isFinite(x)) return String(x);
  let [mantissa, exponent] = x.toPrecision(6).split("e");
  if (mantissa.includes(".")) mantissa = mantissa.replace(/0+$/, "").replace(/\.$/, "");
  if (exponent === undefined) return mantissa;
  return `${mantissa}e${exponent.replace("+", "")}`;
}

// §5.5's status tones. Green (ok) only for evidence that passed.
const TONES = {
  ok: { glyph: "✓", labels: ["VERIFIED", "PASS", "MATCH"] },
  info: {
    glyph: "◐",
    labels: ["CONVERGED", "READY_FOR_SIMULATION", "queued", "running", "completed", "allowed"],
  },
  warn: {
    glyph: "!",
    labels: ["RELAXED", "UNVERIFIED", "DRAFT", "near_threshold", "cancelled", "timed_out"],
  },
  none: { glyph: "–", labels: ["NOT_RUN"] },
  bad: { glyph: "✕", labels: ["FAILED", "INVALID", "MISMATCH", "FAIL", "failed", "refused"] },
};
const TONE_OF = new Map();
for (const [tone, { labels }] of Object.entries(TONES)) {
  for (const label of labels) TONE_OF.set(label, tone);
}

// `{tone, glyph, word}` of a status label; null/undefined is the "none" tone, and every label
// the table does not list is "bad" (the typed failures are an open list).
export function status(label) {
  if (label === null || label === undefined) {
    return { tone: "none", glyph: TONES.none.glyph, word: "none" };
  }
  const word = String(label);
  const tone = TONE_OF.get(word) ?? "bad";
  return { tone, glyph: TONES[tone].glyph, word };
}

// A status pill: glyph + word + tone, never hue alone.
export function pill(label) {
  const { tone, glyph, word } = status(label);
  return h(
    "span",
    { class: `pill pill-${tone}`, "data-tone": tone },
    h("span", { class: "pill-glyph", "aria-hidden": "true" }, glyph),
    h("span", { class: "pill-word" }, word),
  );
}
