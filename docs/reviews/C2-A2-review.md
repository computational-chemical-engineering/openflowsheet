# C2 Amendment 2: design-lane review of the build (WO-C2-A2)

Reviewer: design lane (`reviewer`), 2026-10-23. Scope: `git diff fccaa734..e56f560b` on `wp/C2-A2`, against
`docs/derivations/C2-OpenIDAES-450-split-registration.md` §15 and §9 (SPLIT-A12, A20–A25). One pass, narrow scope.

**Verdict: fix first, in the tests only.** The generator, the writer, `case_facts-v2.json` (`4f5c5a65…`) and
`split.json` (`a556e417…`) are correct as registered and need no change. Two registered assertions do not falsify
the failure each one claims to catch (F1, F2). Both fixes are small test edits that move no pin and no data. They
need no second review: a re-run of `tests/test_c2_openidaes450_split.py` is enough.

## Findings, most severe first

**F1 (must fix): SPLIT-A20 does not catch "a pin that is never checked".** `tests/test_c2_openidaes450_split.py:509`
flips the byte at `len(data)//2` and asserts only `rule == "SPLIT-R13/A2"`. Item 14 raises the same rule. Measured:
that byte is the `i` of `"id"` (giving `"hd"`), so with item 13's SHA-256 comparison deleted
(`c2_openidaes450_split.py:535`), `f1_identities` refuses it with `SPLIT-R13/A2 unit_form` and A20 still passes.
Nothing else pins the comparison: A01 renders `f1.facts.sha256` from the constant, not from the bytes it read.
*Fix:* also assert `exc.label is None` and `gen.F1_FACTS[1] in str(exc)` (the message `… pinned <sha>`), on the
flipped file and on the absent one.

**F2 (should fix): without the archive, nothing shows that the writer's `--check` compares.** SPLIT-A25 (c)
(`:670`) asserts only exit 0 on the good synthetic archive. A writer whose `--check` returned 0 once W1–W5 passed,
without calling `_compare`, would pass (b) and (c). Only (a) catches it, through its `sha256 …` line, and (a) runs
only with the archive, so CI never checks it. The exit-1 path ("differs", §15.2) is never exercised. *Fix:* in
(c), assert `f"OK benchmarks/m06/openidaes450/case_facts-v2.json byte-identical (sha256 {FACTS_V2_SHA256})"` in
stdout. Then add a third synthetic archive that passes W1–W5 but differs, for example the first development
case's first unit id given a suffix such as `_A25` (the writer re-sorts, so the order is irrelevant). Expect exit 1, stdout starting `FAIL`, and no case id.

**N1 (note, ratified): `binding` counts fields.** `c2_openidaes450_split.py:355` gives `<n> field(s)` where §15.4
says `case(s)`. The binding is file-level, so a case count would be meaningless. The build logged this in
`docs/C2_DECISIONS.md`. Accept it. At the next amendment, change §15.4's wording to match.

**N2 (note): item 15 keeps the `unit_source == "units.json"` guard** (`:414`), which §15.4's text omits. The two
behave the same on `F1_STATES`: both cases are `units.json`, which A22 asserts. Leave it.

**N3 (note): A22's independent §6 rule is looser than §6** (`tests/…:579`; the same pattern as A13 at `:273`).
`key.removeprefix("idaes:")` counts a key with no namespace as covering its kind, and §6 does not. Both registered
cases have only `idaes:` keys, so the result is the same. Not worth changing now.

**N4 (note): the writer can leak an id through a traceback.** `w27._load` catches `FileNotFoundError` and decode
errors, but not `IsADirectoryError` or `PermissionError`. A corrupt archive therefore stops the writer
(`c2_openidaes450_facts_v2.py:60`) with a traceback that names `cases/<id>/topology.json` on stderr. That is not
a refusal, and nothing is committed. Optional: catch `OSError` around extraction and refuse with a count.

## Checked and sound

- **The writer follows §15.2.** Its reading rule is WS1's `extract_facts_v2` (`7b5c07f:…m06_w27_registration.py:1381`)
  verbatim, apart from `generator`. It loads W27's module by path and uses only the registered helpers. W1–W5 run in
  order and report counts only. `NOT CHECKED` exits 2. The flags are mutually exclusive and one is required. W27's
  generator, preflight and document have no diff in the range, and A24 pins `REGISTERED_SHA256` for CI.
- **Admission (SPLIT-A09's purpose).** One exact literal entry (13 entries), with no pattern. A23 asserts 224
  held-out ids in the file, using the test's independent draw, so it shares no generator code. A22's expected
  values are recomputed without the generator, and only its `pervap2` negative control calls items 14 and 15, as
  §9 requires. A09 passes over every other tracked file, including the new tests and logs, and the new messages
  name only development ids.
- **Items 13–15.** They run after item 8. A12 deletes the facts key and asserts `SPLIT-R13`, not `/A2`, so that
  order is pinned. Item 14's seven labels are in §15.4's order, and each is reached and asserted by A21 without a
  leak. Item 15 groups the units in file order. A22's `pervap2` edit passes item 14 and is refused by item 15.
  `--check` maps every refusal to exit 2. An absent file is reachable through `read_inputs`. Items 14 and 15 are
  reachable only below the pin, by design.
- **Record.** `split.json` hashes to `a556e417…`, and A12 compares it member by member with blob `17632cea`. The
  `f1` block matches §15.4. `l01_projection.json` keeps `ee940a7e…`, as §15.7 says.
- **Re-run here:** `tests/test_c2_openidaes450_split.py` gave 40 passed, with A25 (a) against the worktree's
  archive copy.

**Not examined:** W27 internals beyond the four helpers; the W27 harness, C9 and L01 suites (not re-run); ruff and
mypy; re-deriving §15.6.
