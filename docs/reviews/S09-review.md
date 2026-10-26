# S09 — independent review (design lane, `reviewer`), 2026-10-26

Branch `wp/S09`, range `390e0af5..293cb19b` (WO-S09-1 to WO-S09-3). Brief `docs/briefs/S09-review.md`. Spec
`docs/derivations/S09-spec.md` §0–§18 (Amendment 1 included). Read: `docs/S09_BUILD_DECISIONS.md`; the harness diff
`c2589694..fd38124d`; the harness's solve path, profile reader, rules 2 and 2c, outer loop, rerun, margin and provenance
(`spikes/references/s09_qualify_biosteam.py`); the classifier's view, rules 1–2d, readbacks, selection, margin and
`classify` (`scripts/s09_reference_comparison.py`); the A03, A05, A08–A11 and A18 tests; records and `comparison.json`
by scripted reads.

Ran no test suite (the build log's 125 + 308 passed are not repeated here). Scratch probes, not committed:
(a) RC1's selected run with one stage flow set to NaN, through the classifier's `rule2`; (b) products against stage
outlets, and inlets against stage inlets, in all 38 profiles (19 selected runs, 19 reruns); (c) each stage's liquid and
vapour stream temperature against the stage's T; (d) BioSTEAM–twin and ours–twin distances per pair from
`comparison.json`; (e) the spike's function names against the harness's; (f) which installed packages import numpoly;
(g) the records' wall times.

## Verdict

**Sound, with one should-fix and no must-fix.** The blindness was real and held. The L2(c) loop meets its six conditions
on every record, and the accuracy rerun is implemented exactly as §18.4(b) fixes it. An L2(c) `AGREE` rests on the same
evidence as an L1 `AGREE`. The harness's checks are load-bearing where the spec says they are: B3 rejects inside-out on
the RC3 and RC4 families, and B4 alone rejects simultaneous correction on 9 of the 19 pairs. The one defect is a NaN
that the classifier's B3 can drop (F1). It affects no committed value. Counts: must-fix 0, should-fix 1, note 6. Spec
rulings are in Amendment 2 (§19, R-751 and R-752). No registered value, threshold, setting or input changes.

## Findings

**F1 — should fix. The classifier's B3 drops a NaN.** `scripts/s09_reference_comparison.py:324`:
`b3 = r.copy_abs() if r.is_nan() or b3.is_nan() else max(b3, abs(r))`. Once `b3` is NaN, the next finite residual
replaces it. *Scenario:* probe (a). In RC1's selected run, stage 0's first inlet flow of A is set to NaN, which is the
first value B3 reads. B3's maximum becomes 3e-16 and rule 2 passes. A missing flow (`_finite` gives NaN) behaves the same
way. The module promises the opposite ("a check that reads it then fails, never passes"). *Backstops:* an internal NaN
flow also enters that stage's x or y, and B4 keeps a NaN. A NaN registered quantity cannot pass rule 4. No false-`AGREE`
path was found, and every committed B3 is finite (≤ 2e-16 mol/s). *Fix:* use B4's form (`:345`),
`b3 = Decimal("NaN") if r.is_nan() or b3.is_nan() else max(b3, abs(r))`, and add §19.5's A09 mutation. `comparison.json`
must then recompute byte-identically (A13). The harness's float `max()` has the same order dependence
(`s09_qualify_biosteam.py:647`, `:681`; `t06_fixtures.py:296`): a NaN survives only if it comes first. The harness is
frozen with the records, the classifier is authoritative, and so the harness is recorded here, not changed (§19.3).

**F2 — note. B5's energy closure is an identity.** By §5.6 each stage's duty is (Σ outlet H − Σ inlet H)/3.6 over the
stage's own streams (`s09_qualify_biosteam.py:456–470`). Every internal stream is one stage's outlet and another's
inlet, so Σ duties equals Σ product H − Σ inlet H exactly, and the residual is rounding (RC6: 6.8e-12 W; §6.6's floor:
1.4e-11 W). The row checks stream bookkeeping, which B3 already covers. Energy convergence is fully covered without it:
- every stage without an end specification, a "none" end's stage included, by rule 2c's adiabatic duty;
- a duty-specified stage by rule 2d's residual on its computed duty (RC3 family);
- an end stage with `Reflux`, `Boilup` or `Flow` carries no energy equation.

WO-S09-3's choice to sum every stage's duty is accepted. Summing the end duties only gives Σ intermediate duties, which
rule 2c already bounds stage by stage. Neither form adds evidence. Ruled in §19.1.

**F3 — note. The selection cross-check lives only in a test.** `classify` (`:830`) classifies the recorded
`selected_rung` and reports the recomputed one beside it. Only A18's test (`tests/test_s09_references.py:666`) requires
them equal. Likewise `|g| ≤ ytol` is checked by A08, not by the classifier's selection. A rung that failed only
`final_residual` would therefore show up as a selection mismatch, and the same test would catch it. The consequence is
bounded: two passing rungs differ by under 0.1 tolerance, or path dependence fires. All 19 agree. *Optional hardening:*
`compute()` refuses a mismatch on an available record. Leave `classify()` as it is, so that A09–A11's per-pair mutations
stay valid.

**F4 — note. Nothing ties the products to the stage outlets.** The registered `top[c]` and `bottom[c]` come from
`profile.products`. B3 reads `stages[].out_mol_per_s`. A harness that recorded a product from a stale stream would pass
B3 and B5. Probe (b): products and inlets equal the stage streams exactly in all 38 profiles. A10's rerun mutation and
A11's path mutation (`shift_product`) rely on this gap to leave rule 2 unchanged. No change for S09. If the classifier is
reused, add an integrity assertion in `view` that raises, rather than a rule.

**F5 — note, blindness disclosure.** `s09_cases.json` is a registered input of the blind harness. Its claim strings
carry two values derived from the twin: C4 "243.292 tolerances (Q_reboiler)" (line 672) and C6 "T_max 397.3721 K"
(line 685). Neither can steer the result. Selection is mechanical, C5 fixes the loop's answer, and the size of a
discrimination plus one temperature say nothing about where the tool converges. Added to §9.1's exposure statement
(§19.4), for D19.

**F6 — note, provenance.** `harness.head` and `scripts_clean_at_head` are taken at assembly
(`s09_qualify_biosteam.py:1590`), not in each case process. Run 2's records are not committed. A16 proves the order of
the commits, not the order of authorship. The records depend on `fd38124d` because of two facts:
- the run is deterministic (A17);
- the diff `c2589694..fd38124d` contains exactly §18.6 items 2–4 (read here).

The timeline is plausible. One run's case wall times sum to 182 s, shared over 6 jobs, inside 01:33:28 → 01:38:14. For
later packages, stamp the head and the clean state into each case record.

**F7 — note. B4's closed form changes a label.** With K from SYN-001's closed form, a Psat mapping error fires B4
(rule 2, `reference_accuracy`) before `property_mapping` (rule 2c, `semantics`). The classification is `NOT_COMPARABLE`
either way. The harness, which uses the tool's Psat, would have labelled the same error 2c. Accepted (§19.2(a)).

## Rulings on the brief's §4 items

**1. Blindness: real.**
- The 2b harness diff contains the amendment items only.
- No spike code was reused. Of the spike's function names, only `build` recurs, and it is generic.
- The harness imports biosteam, flexsolve, `s09_biosteam_syn001` and `t06_fixtures`, and nothing else.
- `s03_cases.json` carries no twin value (`1.2341` is absent).
- The records (`95643b4c`) precede the classifier's first commit (`94a9d0c0`). Nothing under `spikes/references/` and no
  record changed after `95643b4c`.
- dev0–dev3 were not reused. Amendment 1's rerun change can move availability only.

The runs also confirm it independently. RC4's L2(c) root, x = 1.234190189274101, matches the twin's reflux ratio
1.23419018 (S03 §3.1) to all nine digits the twin gives, and the loop reached it from the generic starts 1 and 2.
Disclosures: F5, F6, and WO-S09-3's one-ulp reflux reading. That reading changed the classifier after values had been
seen, at 1e-16 relative. It cannot change a classification, and the build log discloses it.

**2. The L2(c) loop.**

*The six conditions hold on every record:*
- C1: each evaluation is a fresh build through P1–P4.
- C2: one end and one specification. The classifier's `native()` makes L2(c) admissible independently, because
  `expected_specifications` raises outside it.
- C3: A08 checks the starts, the expansion and the solver's arguments.
- C4: the final |g| is at most ytol, and the rule 2d residual is recomputed.
- C5 holds by the argument the spec gives.
- C6: every evaluation is recorded.

*The rerun* is exactly §18.4(b)'s: one evaluation, at the same binary64 x and at 1e-9. Both A08 and the classifier's
`rerun_settings` check it, and the read-back of x is exact.

*Strength.* An L2(c) `AGREE` stands on the same evidence as an L1 `AGREE`:
- the harness's own MESH checks: B3 per stage and component, B4 per stage, and the adiabatic duty;
- every registered specification, recomputed from the record by S03's function, with the harness's independent
  `spec_value` as a second implementation.

So the accepted state solves the registered model, whatever native handle held it. The loop adds only its stopping
error, ≤ 0.005 tolerance under S03 §17.4. The measurements agree: the BioSTEAM–twin distance is ≤ 1.0e-5 tolerance at
L2(c) (RC4 1.0e-5, RC5 5.0e-7, RC6 1.7e-6, RC7 7.9e-7) and ≤ 4.6e-6 at L1. L2(c) differs from L1 in what it shows about
the tool's capability, not in accuracy: BioSTEAM does not express these specifications natively. The verdict and the X31
table must therefore keep the level per pair, as `comparison.json` does.

**3. The harness's convergence checks.**
- *B2* follows §18.3 and is recomputed per rung from the raw counters. The identity test for "fsolve ran" worked: B2
  passed on the 9 pairs where R3 fails only B4.
- *B3 and B4 are load-bearing.* Without B4, R3 would have entered the path-dependence set on 9 pairs.
- *B5's component balance* is meaningful. Its energy row is F2.
- *No selected record has a one-phase stage.*
- *Temperatures.* Stream temperatures equal the stage's T in every selected profile (probe c), so B4 and the duties use
  the same T.
- *Property readback.* It is recomputed against `s09_cases.json`. The latent, cp and datum items are the harness's
  differences, not raw h^V and h^L. That is enough: duties at P_r agree with the twin to ≤ 1e-5 tolerance, and PC-LB's
  tool-model distance is 3.6e-7 tolerance. A datum or latent-heat error would not survive either.
- F1 is the one defect.

**4. Build choices, all accepted.**
- B4 from the closed form: F7, §19.2(a).
- B5 summing every duty: F2, §19.1.
- Rule 2c's order: it changes labels only.
- Margin rows in the twin's tolerance: this is §6.4's form for the classifier. They differ from the harness's by
  ≤ 2.1e-4 relative.
- The WO-S09-2b change to the specification row (each specification against its own kind's θ_k): this is §18.4(c)'s
  wording. The earlier form mixed kinds.

**5. Open items.**
- *numpoly: no change* (§19.2(d)). In this environment only chaospy imports numpoly. Neither biosteam, thermosteam nor
  flexsolve imports it, so it is off the column path. The sdist is pinned by hash, and the compiled bytes depend on the
  host.
- *A04 is met as registered.* The file half covers the lock, the hashes and §9's two builds. The record half shows 19
  fingerprints equal to §9's. The gate never builds a tool, so the identity of the two builds is a recorded
  measurement, as it was in S03.

**6. Do the tests verify what they claim?** Yes for A05, A09–A18, with these limits:
- *No non-finite mutation exists:* F1, now §19.5.
- *A17* compares against run 2's hashes as the assembler computed them, because run 2 is not committed. That is
  acceptable as registered.
- *A08* checks the record's description of the solver call. The harness is the only witness of the call itself.
- *A10's +0.01 Pa* goes on a product pressure. This is legitimate: a stage pressure enters B4's K, so B4 fires first.
  A tool that really ran at a wrong pressure would record that pressure consistently, and rule 2c would catch it.

## For the verdict (observations, not findings)

- Every compared pair's BioSTEAM–twin distance is ≤ 1.0e-5 tolerance.
- The larger worst ratios (RC6 `bottom[A]` 0.0202, the RC3 family 0.0017–0.0035) are our side's distance to the twin,
  which S03 already carries.
- PC-LB: 243.3 tolerances, with a tool-model distance of 3.6e-7 tolerance against PC-LI's. PC-P: 175.9 tolerances.

## Not examined

- BioSTEAM's and thermosteam's source: the spec's line citations were taken as given.
- S03's shared functions (`specification_values`, `movement`, `rule4`, `tolerance`), beyond their call sites.
- `inspection()` and the Q-X answers.
- The A06 and A07 tests.
- The manifest generator.
- The build script.

## Merge conditions

- F1 fixed, with §19.5's A09 mutation.
- A13 byte-identical.
- The manifest regenerated, with `scripts/s09_evidence_manifest.py`'s `amendments()` reading §19.5 as well as §18.5
  (today it parses §18.5 only).
- A19 (the verdict document) present.

The package status stays `implemented`. This review does not set `reviewed`.
