# V02 alpha gate review: `scripts/v0_2_gate.py` (WO-2), with WO-1, WO-3, WO-4 and WO-7, against the V02 alpha release spec, ADR 0028, R-238 and R-239

**Reviewer:** design lane, `reviewer` (Claude Opus 5.5), 2026-10-09.

**Reviewed at:** `wp/V02-alpha-gate` = `c35c50b`. The range is `e3703bb..c35c50b`: 5 commits and 15 files. The
specification is the one at `e3703bb`.

**Read against:**
- spec §§3–5, §7, §8.2–8.3, §9, §10 (A00–A24, A42, A53) and §15;
- ADR 0028, R-238 and R-239;
- the v0.1 machinery it mirrors: `scripts/v0_1_gate.py`, ADR 0021 D2 and R-151;
- `docs/RELEASING.md` and `.github/workflows/release.yml`.

**Run here:** nothing; the review was read-only. The brief's numbers are taken as reported:
- `check.sh` 7861 passed, 52 skipped;
- 104 gate tests;
- 11 mutations, each caught;
- the dry `t08_dist.py` at `0.2.0a1`.

**Confirmed by reading git:**
- `scripts/v0_1_gate.py`, `scripts/t08_rc.py` and `tests/test_t08_w4_v0_1_gate.py` have empty diffs.
- `docs/adr/0021-…` and `docs/reviews/T08-verdicts.md` are unchanged since `PUBLIC_ROOT`.
- Both of M01's `tested` manifests are at ancestors of `main`.
- M02's ADRs on `wp/M02` are numbered 0033–0035, as `required_adrs` assumes.

---

## 1. Verdict

**Sound for `0.2.0a1` as specified. There is no must-fix.**

- **It fails closed.** The gate refuses on every one of §7.3's twelve items (§2).
- **Nothing is relaxed relative to `v0_1_gate.py`.** Every shared rule is imported or copied unchanged, and each departure
  is stricter:
  - inputs are read at the candidate;
  - `--rc` is required;
  - the verdict document's `C` must equal `--rc`;
  - the D3 acceptance must start with `accepted` and be dated on or after `Judged`;
  - exactly one D3 table is read, not every table with that column;
  - the version must fullmatch the gate set's pattern, not prefix-match it;
  - M01 and M02 manifests are required at ancestors of `C`.

**Records the spec would not accept that still pass.** Two gaps in the spec's own rules let such a record satisfy
the gate. Both need a design-lane decision:
- **F1:** Table T4's cell rule admits a chosen alternative written after the word "accepted".
- **F2:** Frank's per-release answers for `0.2.0a1` would be reused, unread, for `0.2.0a2`.

**Implementation and test findings:**
- **F3:** `build()` has a latent fail-open: `differences=None` skips D2.4.
- **F4:** six refusal paths have no test of their own, the build lane's choices 3 and 5 among them.

**Release mechanics.** The PEP 440 handling in `release.yml` and `changelog_section.py` is safe for the 0.1 line (F6).

---

## 2. Fail-closed, item by item (§7.3)

Line numbers are those of `scripts/v0_2_gate.py` at `c35c50b`.

| §7.3 item | Code | Fails closed | Test |
| --- | --- | --- | --- |
| 1. Coverage | `fullmatch` over the registry, 156–161; early return, 633–643 | yes. More than one covering set raises (exit 2) | A01 (Table T1, 18 rows) |
| 2. Same version | 682–685 | yes | A02 (i)–(iii) |
| 3. D2.1 | 580–589: no gate, no verdict, a non-verdict word, no row, ledger ≠ document | yes | A04 (g); `test_a04_a_missing_ledger_gate_or_verdict_is_refused` |
| 4. D2.2 | 594–595 | yes | A04 (f) |
| 5. D2.3 | 596–613: unlisted, not an acceptance, or dated before `Judged` | yes | A04 (b)–(e), (h) |
| 6. D2.4 | 686–687; `main` always computes the differences, 906 | yes from `main`; **not from `build(differences=None)`** (F3) | A07; A12 on a scratch repository |
| 7. RC record | 391–431, the v0.1 grammar over steps 1–12 | yes | A08 |
| 8. M07a manifest | 452–467 | yes | A09 (a), (b) |
| 9. M01, M02 at ancestors | 468–496; `C` absent always refuses | yes | A09 (c)–(e) |
| 10. Envelope | 507–519 | yes | A10 |
| 11. Frank's answers | 369–384: no table, two tables, no row, two rows, not an acceptance | yes, **subject to T4's rule (F1) and to cross-release reuse (F2)** | A05 (9 states) |
| 12. ADRs | 526–547: 0 or 2 files, no status line, not Accepted | yes | A11 |
| Malformed verdict document | 233–304, then `ValueError`, exit 2 (909–911) | yes | A03 (17 states) |

**Other exceptions.** Some failures do not raise `ValueError`: a YAML error in the ledger or envelope, a ledger entry
without `required_evidence`, a bad `--candidate`. Each ends in a traceback and exit 1, not 2. No YES line is printed,
so `release.yml` refuses. This is fail-closed, and only the exit code is imprecise.

---

## 3. Findings

### F1 — should-fix, **needs a decision** (spec T4): the cell rule counts a chosen alternative as an acceptance of the default

**Evidence.** `acceptance_date` (310–321) implements Table T4 exactly: the bare cell, lower-cased, starts with
`accepted` and contains a date. So each of these cells returns a date and passes item 11:
- `accepted (i), 2026-10-12`;
- `accepted alternative (ii), 2026-10-12`;
- `accepted only for local use, 2026-10-12` (as an M02 N1 answer).

The gate then proposes the tag under `v0.2-alpha-gate-v1`. But §7.3 item 11 says that a chosen alternative refuses, and
§3.3 says that any answer but the default first amends the spec, to gate set `v2` for alternative (i).

"accepted (i)" is a plausible way for Frank to answer N3. The same rule governs the D3 cell for V14 (b).

**Secondary.** `DATE` (100) has no boundaries, so `accepted, 2026-10-123` is read as 2026-10-12. v0.1's `DATE` had
`\b`, and this file's own `JUDGED_VALUE` has `(?![0-9])`.

**Fix.** Amend T4's rule; the code follows in one line. The bare, lower-cased cell must match
`accepted[\s,;:]*(\d{4}-\d{2}-\d{2})(?![0-9])` at its start, so the date comes right after the word.
- T4's three `yes` rows stay `yes`, and its five `no` rows stay `no`.
- Add three `no` rows: `accepted (i), 2026-10-12`, `accepted alternative (ii), 2026-10-12` and
  `accepted, 2026-10-123`.

I would take this route. The alternative is to keep the rule and have `RELEASING.md` tell Frank to write exactly
`accepted, <date>`, which relies on the writer.

### F2 — should-fix before any `0.2.0a2`, **needs a decision** (spec §7.2 item 3): per-release answers are not tied to a release

**Evidence.**
- The gate set covers `0.2.0aN` (Table T1: `a2` and `a10` are `yes`).
- `policy()` (350–385) reads ADR 0028's two tables whatever the version.
- `GateSet` (108–132) has no version key for them. The headings "for 0.2.0a1" are not read.

D3 rows are protected, because a new verdict brings a new `Judged` date. The decisions rows are not. R-238 calls
N3, the V17 carry and M02 N1 "Frank's per-release answers", yet `0.2.0a2` would be proposable on the three answers
given for `0.2.0a1`. The V17 carry in particular names the links of `0.2.0a1`'s surface. This cannot happen for `0.2.0a1`
itself.

**Fix options:**
- **(a)** Apply D3's date rule to the decisions cells too: each must be dated on or after `Judged`. It is minimal and
  uniform, and §9.2 step 6 already has Frank record all four answers after the verdict.
- **(b)** Read each table only under a heading that names the version being cut.
- **(c)** Narrow `covers` to `0\.2\.0a1` until an `a2` is designed. This changes Table T1.

I would take (a).

### F3 — should-fix (implementation): `build()` treats `differences=None` as "equal to C"

**Evidence.** Line 686 is `if differences:`.
- `main` never passes `None` for a covered version (906), so no YES today depends on it.
- `build` is the API that WO-9's A52 (c) test and M07 will call. v0.1's CHANGELOG test calls
  `v0_1_gate.build(..., differences=None)`, and there `None` was safe only because `rc=None` refused on its own.
- A caller who copies that pattern here gets `tag_may_be_proposed: True` with D2.4 never checked.

**Fix.** Make the parameter `Sequence[str]` (never `None`), or add the reason "tree check (D2.4) not run" when it is
`None`. Add one test state.

### F4 — should-fix (tests): six refusal paths have no test of their own

The suite would still pass if any of these were dropped:

1. **Choice 3 in isolation.** A04 (d)'s shaped row changes both the first cell and the acceptance cell, so restoring
   v0.1's prefix `CLAUSE.match` at line 364 leaves A04 (d) green: the cell fails T4 anyway.
   - Add `| V14 (b) one PTC family | … | accepted, 2026-10-12 | … |` → refused.
2. Two tables with a `Frank's acceptance` column (358–361).
3. Two tables with a `Frank's answer` column (370–372).
4. A D3 clause listed twice (366–367), and a decisions row doubled (378–379).
5. `**Judged:**` twice (243).
6. An acceptance whose first date is not a calendar date, such as `accepted, 2026-02-30` (318–321).

Each is one state on the passing fixture.

### F5 — note: two inputs are read from the working tree, and why that is harmless

`resolve_rc` and `tree_record_of`, imported from v0.1, read `release/rc-trees/` from the checkout
(`v0_1_gate.py` 564–572 and 605), not at the candidate as §7.2 says of every input.

This cannot produce a YES. The record matters only when `C` is absent, and then `manifest_problems` always refuses
(468–474; A09 (e)).

Say so in the module docstring, so that a later change that lets `C`-absent pass the ancestry check re-reads this.

### F6 — note: the 0.1 line under the new version step

`release.yml` line 72 now admits `0.1.ZaN`, `0.1.ZbN` and `0.1.ZrcN`. `v0_1_gate.py`'s `V0_1_LINE.match` covers them by
design ("and its pre-releases such as `C`'s", lines 123–124).

**This is not a relaxation.** A YES for, say, `0.1.2rc1` still needs:
- D2.4 equal to `67c66d9`'s;
- every v0.1 record.

So no new code can ship on the 0.1 line.

**What is new.** A pre-release label that nobody designed becomes publishable. `0.1.1rc1` would sort below the
published `0.1.1`.

**If Frank wants it closed:** a sentence in `RELEASING.md` ("the 0.1 line takes no pre-releases") is enough. The v0.1
gate must not be edited.

**The rest of the mechanics are correct:**
- `changelog_section.py` treats final tags exactly as before: the heading rule is identical.
- Its `\s` boundary keeps `## v0.2.0a10` apart from `v0.2.0a1`.
- `--prerelease` follows the version.
- The YES grep (`-qxF`) is exact.
- A forgotten `rc` (`67c66d9`) is refused. The first refusal it meets is in fact the verdict document's `C` (exit 2),
  not the version reason that `RELEASING.md` names. Either way it is refused.

### F7 — note, for M07: `CLAUSE` is module-level

`CLAUSE` (98), `HEADERS` and `ENVELOPE` are module constants, and `CLAUSE` hard-codes V11–V20, W21 and W22. When M07's
`v0.2-gate-v1` claims W23–W27, its W23 FAIL rows would be rejected as malformed unless `CLAUSE` is derived from the
set's claimed gates.

### F8 — note: WO-7's probe (see also §5)

- **Stricter than A42.** `TYPED` omits A42's fourth admissible outcome, "a typed refusal naming the schema version".
  If M02's ADR 0033–0035 schema changes make the v0.1.1 bundle refused, widen the test to that outcome; the spec does
  not change.
- **Provenance.** That the fixture was written at `v0.1.1` is stated in the docstring's recipe, and the bundle itself
  carries no package version. This is the same standard as T08.A35, and it is reproducible.
- **aarch64 is unconfirmed.** By the brief, `--rerun`'s `MATCH` has been run only on x86-64, but RC step 1 runs
  `check.sh` on `ubuntu-24.04-arm` too. T08.A45's cross-architecture `MATCH` makes a pass there the expectation. Confirm
  it on CI before `C_α`.

---

## 4. Rulings on the build lane's choices

1. **Importing `resolve_rc` and `tree_record_of` from v0.1. Accepted.**
   - Both depend only on `RC_TREES` and `TREES`, which ADR 0028 D2 and R-151 share.
   - `tree_differences`, which is on WO-2's list, already calls `tree_record_of`.
   - Copies could drift where A13's byte-identity check cannot see them.
   - WO-2's list illustrates a principle, and these meet the principle. See F5's caveat.
2. **`--rc` required, with no default. Accepted.**
   - This is stricter than v0.1. v0.2 has no counterpart of v0.1's "newest `tested` T08 manifest", and a default would
     let a local run judge the wrong `C`.
   - `release.yml` always passes `--rc`, and an empty value exits 2.
   - WO-9's A52 (c) test must pass `--rc C_α`, taken from the M07a manifest.
3. **A D3 row counts only if its first cell is exactly a clause. Accepted.**
   - The spec says "each row's first cell is a clause".
   - The rule can only remove acceptances, so it fails closed.
   - It is untested in isolation (F4.1).
4. **A missing row refused as "no row …"; pending or an alternative refused with the spec's wording. Accepted.**
   - §7.3 item 11's wording is for an answer that fails the cell rule, and a missing row is no answer.
   - A05 asks only that the refusal name the item, and it does, for all nine states.
5. **Refusing doubled tables, rows, ADR files and `Judged` dates, and non-calendar dates. Accepted.**
   - Each refusal fails closed.
   - None refuses a record of the form ADR 0028 holds.
   - Only the doubled ADR file has a test (F4).
6. **WO-4 reads ADR 0021 and the envelope at `PUBLIC_ROOT`. Accepted, and right.**
   - The v0.1.0 table is a function of all four inputs, and a release record is reproduced from the release's own
     inputs.
   - Today ADR 0021 and `T08-verdicts.md` are unchanged since `PUBLIC_ROOT`.
   - The envelope feeds only problems, never the markdown.
   - So the change is inert now and protective later.
   - The negative control bites through V14. Its W21 and W22 edits are inert, because v0.1's `GATES` is V11–V20; this
     is harmless.

## 5. Ruling on A42: is `replay --rerun` the intended reading?

**Yes.**

1. A42 lists `exact_replay` and `compatible_reproduction` `MATCH` among its outcomes. Only a rerun can produce them.
   Plain `replay` never reruns: R-131 makes it exit 0 on `NOT_RUN` without `--rerun`. A reading without `--rerun`
   would leave two of A42's outcomes unreachable.
2. `inspected_archived_results` `NOT_RUN`, the outcome for a later lock, is reachable with `--rerun` too.
3. It is the stronger probe: it re-solves the v0.1.1 problem at `C_α` and compares. T08.A35 was judged on plain
   `replay` only because the v0.0.0 lock differed and nothing could rerun.

**The plain-replay result.** Plain `replay` gives `compatible_reproduction` `NOT_RUN` ("no rerun was supplied"). That
is a typed report, and recording it without judging it, as the test does, is right. A `MISMATCH` fails, which is also
right.

**Design-lane follow-up.** Amend A42 in one line: "`C_α`'s `replay --rerun` returns …; plain `replay`'s
`compatible_reproduction` `NOT_RUN` with its reason is recorded, not judged". Then the verdict agent cannot read the
plain result as a FAIL of V11 (e).

## 6. Not examined

- `docs/derivations/scripts/v02a_reference.py` itself; only its inclusion in WO-1's parametrization.
- The v0.1.1 fixture beyond its manifest fields and pinned hashes.
- Any aarch64 behaviour.
- WO-5 to WO-11.

**One item for WO-5.** Spec MR-2 and §5.3 require Frank's V17 carry to name every link of the chain. Neither this gate
(A05 checks only the cell rule) nor anything in this range checks that the ADR 0028 row names R-192, R-234 and any
later link. It must be part of WO-5's chain test or the verdict's reading.
