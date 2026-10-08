// M06 WO-5: text, numbers and status pills (design note §5.5).

import { test } from "node:test";
import assert from "node:assert/strict";

import { DASH, fmt, pill, REPLACEMENT, sanitize, status } from "../../apps/web/js/text.js";
import { textOf } from "../../apps/web/js/h.js";

test("sanitize replaces each forbidden code point one for one and keeps the rest", () => {
  assert.equal(sanitize("plain text, \n and \t kept"), "plain text, \n and \t kept");
  assert.equal(sanitize("a\u0000b\u0008c\u000bd\u001fe\u007ff\u009fg"), "a�b�c�d�e�f�g");
  assert.equal(sanitize("​‌‍⁠﻿"), REPLACEMENT.repeat(5));
  assert.equal(sanitize("‪‫‬‭‮"), REPLACEMENT.repeat(5));
  assert.equal(sanitize("⁦⁧⁨⁩"), REPLACEMENT.repeat(4));
  assert.equal(sanitize("x‮evil"), "x�evil");
  // A lone surrogate is replaced; a pair (an astral code point) is kept.
  assert.equal(sanitize("a\ud800b\udfffc"), "a�b�c");
  assert.equal(sanitize("\u{1F600}"), "\u{1F600}");
  // The neighbours of every range are kept.
  assert.equal(sanitize("\u0009\u000a   ‎⁡⁥⁪﻾＀"), "\u0009\u000a   ‎⁡⁥⁪﻾＀");
  assert.equal(sanitize("<img src=x onerror=alert(1)>").length, 28);
});

test("fmt: null is a dash, integers exact, short is 6 significant digits, full round-trips", () => {
  assert.equal(fmt(null), DASH);
  assert.equal(fmt(undefined), DASH);
  assert.equal(fmt(0), "0");
  assert.equal(fmt(2104), "2104");
  assert.equal(fmt(-338), "-338");
  assert.equal(fmt(31487.641739605908), "31487.6");
  assert.equal(fmt(31487.641739605908, "full"), "31487.641739605908");
  assert.equal(fmt(0.5), "0.5");
  assert.equal(fmt(0.95), "0.95");
  assert.equal(fmt(1e-7), "1e-7");
  assert.equal(fmt(1.2345678e-12), "1.23457e-12");
  assert.equal(fmt(123456789.5), "1.23457e8");
  assert.equal(fmt(-0.000123456789), "-0.000123457");
  assert.equal(fmt(101325.25), "101325");
  assert.equal(fmt(298.15), "298.15");
  for (const x of [0.1, 1 / 3, 2 ** -1074, 1.7976931348623157e308, 6.02214076e23]) {
    assert.equal(Number(fmt(x, "full")), x);
  }
});

test("status: every listed label has its tone; unlisted labels are failures", () => {
  const expected = {
    VERIFIED: "ok", PASS: "ok", MATCH: "ok",
    CONVERGED: "info", READY_FOR_SIMULATION: "info", queued: "info", running: "info",
    completed: "info", allowed: "info",
    RELAXED: "warn", UNVERIFIED: "warn", DRAFT: "warn", near_threshold: "warn",
    cancelled: "warn", timed_out: "warn",
    NOT_RUN: "none",
    FAILED: "bad", INVALID: "bad", MISMATCH: "bad", FAIL: "bad", failed: "bad", refused: "bad",
    HOMOTOPY_STALLED: "bad", BOUND_BLOCKED: "bad", "something new": "bad", verified: "bad",
  };
  for (const [label, tone] of Object.entries(expected)) {
    assert.equal(status(label).tone, tone, label);
    assert.equal(status(label).word, label);
  }
  assert.deepEqual(status(null), { tone: "none", glyph: "–", word: "none" });
  assert.equal(status("VERIFIED").glyph, "✓");
  assert.equal(status("CONVERGED").glyph, "◐");
  assert.equal(status("RELAXED").glyph, "!");
  assert.equal(status("FAILED").glyph, "✕");
});

test("a pill carries glyph, word and tone, never hue alone", () => {
  for (const label of ["VERIFIED", "CONVERGED", "RELAXED", "NOT_RUN", "FAILED", "x", null]) {
    const tree = pill(label);
    const { tone, glyph, word } = status(label);
    assert.equal(tree.t, "span");
    assert.equal(tree.p.class, `pill pill-${tone}`);
    assert.equal(tree.p["data-tone"], tone);
    assert.equal(textOf(tree), glyph + word);
    assert.ok(textOf(tree).includes(glyph) && textOf(tree).includes(word));
  }
});
