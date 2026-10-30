# V03 and E01b — the single `reviewer` pass before the 0.3.0 candidate (design lane)

Reviewer, 2026-10-30. Brief `docs/briefs/V03-review.md`. Read-only over `wp/V03` at `0efa6645` (base `912504d9`) and
`wp/E01b` at `23bfb0cf`. Register ids from R-900.

**Verdict.** `wp/V03`: sound, with **one must-fix** in MR-12 v03's `lca` entry (F-V1, which also rules Q3). It can merge
once F-V1 lands. `wp/E01b`: **sound**. Every corrected number checks against the 3rd edition. Two should-fixes concern
what the tests still pin (F-E1, F-E2). Nothing here blocks the merge.

## What I ran (read-only, scratch scripts, nothing committed)

- W5c re-pin: I bound the three predecessor documents (`git show 912504d9:benchmarks/s11/...`) and the regenerated ones
  through `test_t07_w5c_signatures._structure`. All three predecessors reproduce the old pins. For TH-C1, TH-R1 and GP-M1,
  `revision_sha256` is the only key that differs, so `8c6ddb8a` is confirmed.
- Every code-built revision in W5c's `BUILT` (36 documents, 161 instances of Table R models) agrees with Table R, not
  only the five builders that A30 (d) reads.
- Seider 3rd ed. (licensed copy, read only). Eq. 22.39 prints α1 11.667, and Example 22.10 computes with 11.9052 →
  $79,500. Eq. 22.40 gives α2 0.9228. Eq. 22.58 gives 300.9, and Example 22.13 gives $94,700. The pump (p. 561) and the
  motor (p. 562) are both "indexed to 2006 (CE = 500)". Example 22.6 gives $5,740 and $9,710 with the printed
  coefficients. Example 22.9 gives P_C 9,300 Hp. In the 4th ed., the reciprocating pump's a0 is 7.9361 = 7.8103 +
  ln(567/500), exactly.

## wp/V03 findings

**F-V1 — must fix before the candidate (rules Q3).** `scripts/m07a_evidence_manifest.py:437-442` `MR12_AUDITS_V03["lca"]`
has two defects.
(a) `"check": "scripts/e01_d04_inventory.py"` has no mode. The script's `main()` takes a required mutually-exclusive
group (`--packages|--data|--check`), so the bare command exits 2. At C, step 17c can go one of two ways. It runs the
command as written and fails. Or it runs `--check` under a different id, and then `results.get(audit["check"])` is
`None`. Either way MR-12 v03 fails, and A11/A22 stop WO-6. Spec §9.3 has the same omission.
(b) `"decision": "R-870"` cites the entry on labelling results from restricted LCA tables. That entry is not a licence
decision. The measure only checks that the heading exists, so the wrong citation passes.
Exact changes:
- Spec §9.3, the `lca` bullet becomes: "`lca`: audit E01 design §4.8.4 and WO-B1, inventory `docs/e01-lca-licences.json`,
  decision R-900, check `scripts/e01_d04_inventory.py --check` (E01.A42). *Erratum 2026-10-30 (V03 review, R-900): the
  decision read R-870 and the check had no mode.*"
- `MR12_AUDITS_V03["lca"]`: `"check": "scripts/e01_d04_inventory.py --check"`, `"decision": "R-900"`.
- `tests/test_m07_mr12_extras_v02.py`: `V03_REGISTER = "# Decision register\n\n## R-624 — coolprop\n\n## R-900 — lca\n"`
  and `@pytest.mark.parametrize("decision", ["R-624", "R-900"])`.
- Register **R-900**, below.

**F-V2 — should fix.** ADR 0049's condition is "G1–G9 passing". Its *Met* line, and the 0049 row of the
`docs/V03_DECISIONS.md` table, name G1, G2, G3, G9, G-R3 and G-R7. They do not name G4–G8. The S10-C specification
assigns G3–G8 to S10C.A01–A61 (spec §6), and the manifest has them passing, so the condition holds, but the record does
not show it. Append this to the *Met* line and to the table row: "G3–G8 are the S10-C specification's assertions
S10C.A01–A61 (spec §6), all `pass` in `2aedd250…`." Before writing that sentence, check each of G4–G8 against the
manifest. If any of them has no passing node, spec §6 makes it a stop.

**F-V3 — note.** WO-6 owns two things: the producer of `step17/rc-step17c.json` (`checks[].id` = command, provenance
commit = C), and calling `mr12_extras_v03`, which is in `MEASURES` but not in `SPECS`. If the record is missing, the
measure fails, so it fails safe.

**F-V4 — note.** ADR 0054 / spec §9.4 claim that "no committed record pins the nine digests". That claim missed the
indirect W5c pins. The re-pin is correct, as checked above. A31 (b) does not exercise much for the 17 corpus documents
that come back `Unbound` before roles could matter. A31 (a), together with the surrogate-bound W5c structures (only
`revision_sha256` moves), covers that gap.

**Sound (checked):** D-1 and D-4. Every `src/` construction of Wilson goes through `packaged_path`, and identity is by
bytes (`data_sha256`), never by path. D-2 and D-3 have per-file SHA-256 pins and three controls each. The ADR 0054
schema/test/table chain A28–A31, with its controls. The `rc-coolprop` job: it fails safe on an empty module list, on a
non-zero exit and on any skip. The ADR 0001 D5 item 5 / `interfaces-frozen.md` F-1 transcription. The L-S11-3 and
attribution texts match §10.4.

## Rulings on V03's open questions

- **Q1 — confirmed: the default stands.** R-883 (spec §9.1 Amendment 1, and the texts of A12 and A19 (d)) already
  settles it: the binder and the verifier pass `packaged_path(RECORDS_PATH)`, and the no-argument constructors stay
  checkout-only. No new entry is needed. Close Q1 with "ruled by R-883".
- **Q2 — confirmed: no erratum needed.** Register **R-901**, below.
- **Q3 — ruled: cite R-900, not R-870 or R-857.** R-857 left the licences "to be confirmed at pinned versions, WO-B1",
  so citing it would cite an unconfirmed premise. See F-V1.

## wp/E01b findings

**Exchanger-intercept rule (R-895 rule 2): sound.** The book contradicts itself (Eq. 22.39 against Example 22.10), and
the offset is uniform: +0.2382 on all four α1, which is ln(500/394) truncated. The 4th ed. corroborates it. The rule is
scoped to the four intercepts, and the kept values equal the CE-500 numbers the book actually computes with. A further
check, in favour of R-897's fixed-head α2 0.9228: with IDAES's 0.8228, a fixed-head exchanger would cost 1.14× a
floating-head one at 1,000 ft², and 1.81× at 12,000 ft². With 0.9228 the ratio is 0.57–0.71×, close to the U-tube's
0.62–0.76×.

**CE 500 relabel (R-896, Q-B11): stands. Note for the Q-B11 record.** In the book's own pump example (S = 12,420), the
4th-ed. centrifugal refit is $8,380 at CE 567 against $5,740 at CE 500. That is 1.46×, closer to 567/394 (1.44) than to
567/500 (1.13). The ratio proves nothing on its own: the gear-pump (0.48–0.74×) and motor (0.72–1.18×) refits show that
these are new fits, not re-indexes. The evidence that decides it is the reciprocating pump's exact ln(567/500) shift,
together with Example 22.6. Add this to Q-B11's evidence, so that a later reader does not take the 1.46 for a proof of
CE 394.

**R-890 motor coupling: sound.** The compressor's S(N)/κ_W equals the drive's electricity to rel 1e-15. The drive's
capex is 0.0, and the drive inherits N (`test_e01_a_contributor.py::test_th_c2_complete_cost_and_a22`). η_m beyond
1,500 hp is an extrapolation, and the note says so. The loader's 3× argument holds: η_m increases below about 6,400 hp,
so the bound is conservative.

**F-E1 — should fix (needs a decision; I would record it now and add a variant after 0.3.0).** Under M1 (R-898), every
P2 capital row is floored. E01.A18 makes a floor's ∂C_P/∂x ≡ 0, so P2's capital term in `tac` is constant within the
regime. A33–A36 still pass, but they no longer show anything about capital sensitivities through the optimizer. Add this
to S12b's E01b limitation and to the E01 envelope row for P2: "Since R-898 every P2 capital row is floored, so P2's
optimization exercises operating cost only; no registered NLP case carries a capital row in a `units:N` regime." P2 is
not resized (§9.7).

**F-E2 — should fix.** Every shipped entry is now at CE 500, the set's basis. So `sets.py:565` gives `ratio == 1.0` for
every shipped entry, and `test_e01_a_cost.py:601` asserts exactly that. With A44's CE-394 check retired (the
orchestrator's ruling, which I confirm as a registered move, not a loosened check), nothing exercises an entry basis
that differs from the set basis. An inverted ratio would pass. Add one constructed control: a copy of the set with
`pump.index_basis.value` = 394. Assert `ratio == 500/394`, assert that each pump form's C_P is the shipped C_P × 500/394
to rel 1e-15, and assert that the motor is unchanged. The control is synthetic, not a shipped number.

**Sound (checked):** the six corrections (rows 1, 14, 16, 18, 30, 38) against the copy. The A44 ruling (with F-E2). The
floor boundaries in D-B1.

## Register entries (exact text)

**R-900 — MR-12 v03's `lca` entry: the decision is WO-B1/D04's licence audit, and the check is `scripts/e01_d04_inventory.py --check` (V03 spec §9.3 erratum)**

| | |
| --- | --- |
| Date | 2026-10-30 |
| Decided by | design lane (`reviewer`), V03 review (Q3) |
| Normative text | V03 spec §9.3 (erratum); `scripts/m07a_evidence_manifest.py` `MR12_AUDITS_V03["lca"]` |
| Evidence | R-870 decides how results from restricted LCA tables are labelled, not the extra's licences. R-857 leaves the Brightway licences "to be confirmed at pinned versions, WO-B1". `docs/E01B_DECISIONS.md` D04 records them in `docs/e01-lca-licences.json`, judged by `scripts/e01_d04_inventory.py --check` (E01.A42). The script requires one of `--packages`, `--data`, `--check`, so the bare command exits 2 |
| Affected packages | V03 (WO-3, WO-6 step 17c); E01 |

**Decision.** The `lca` extra's licences are accepted on WO-B1/D04's audit. The user installs the extra from PyPI, and
nothing of it is redistributed. Every distribution in `benchmarks/e01/brightway/lca-pip.lock` has a row with its licence
files and a passing verdict, held by E01.A42. This confirms R-857's licence premise at the pinned versions. MR-12 v03's
`lca` entry cites R-900, and its check is `scripts/e01_d04_inventory.py --check`.

**Rejected.** *Cite R-870*: it decides something else. *Cite R-857*: it left the licences unconfirmed.

**R-901 — V03 D-2 and D-3 (T08.A32, S10.A28) are confirmed as amendments under R-617's and R-616's rules; no erratum**

| | |
| --- | --- |
| Date | 2026-10-30 |
| Decided by | design lane (`reviewer`), V03 review (Q2) |
| Normative text | `tests/test_t08_w2_inventory.py` (`0977e3aa`); `tests/test_s10_provider.py::test_a28_…` (`9bd23e9a`) |
| Evidence | Each admitted file is pinned by SHA-256, with its own NOTICE strings and three controls each (the pre-Wilson NOTICE, changed bytes, one appended byte). S10's `PACKAGED` entries equal V03 spec §9.1's two files exactly, and at least 20 other S10 files are asserted absent |
| Affected packages | T08, S10, V03 |

**Decision.** T08.A32 admits Wilson's two files under R-617's attributed-data rule, and S10.A28 is inverted for the
§9.1 ship set as S05.A26 was for R-616. Both amendments stand as committed.

**Rejected.** *An erratum per assertion*: it would restate R-880's ship set twice and add no check.

## Not examined

The CHANGELOG phrases (A18 is checked at C). The body of WO-1's engine diff (I relied on A03 and the 18-run `diff -r`).
The bodies of `test_v03_wilson_ship.py` and `test_v03_v0_3_gate.py`. E01b's forms and loader beyond the compressor and
the motor. The transcription in `seider3.yaml` (A49), and the IDAES cross-check (A15). The docs site.
