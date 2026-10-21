# OpenIDAES-450 development / held-out split — registration (C2)

**Status.** Registered by the design lane (`specifier`), package C2, branch `wp/C2`, 2026-10-21. Requested by Frank
on 2026-10-18 (`docs/briefs/OpenIDAES-split-registration.md`). Register entries R-486…R-494.

**Authority and scope.** This document is the normative text for one thing: which OpenIDAES-450 cases are
*development* cases and which are *held-out* cases, and the rules that keep the held-out cases out of development.
It also registers the successor of W27-R02 (finding F-1, R-474) for classifications made under it (§6). It changes
nothing in the W27 registration, in `coverage.json`, in step 17's carry or in v0.2's released scores. It decides no
v0.3 scope. Rules are `SPLIT-R01…R14`; assertions are `SPLIT-A01…A17` (§9).

**Order of record.** The rules and the seed (§§1–7) were committed before the generator first drew the split. The
results (§8) were added in a later commit. The git history of this file is the evidence of that order.

## 1. Settled by Frank (2026-10-18; binding, restated)

- Split before any OpenIDAES-targeted development. The held-out half is scored only at release gates, reported
  separately, with the development/held-out gap.
- The development half drives gap analysis, unit/property selection, and agent prompt/tool tuning. Feature choices
  cite development cases or a general library goal, never held-out cases.
- The cases exposed by v0.2's W27 campaign count as development cases. These are its 45 drawn cases (their
  transcripts are public) and, per the session brief, its three canaries.
- No gap frequencies (missing units, components or property methods) are computed or written over held-out cases.

## 2. Inputs

**SPLIT-R01 (inputs, pinned).** The split is computed from three committed files only, pinned by SHA-256. It needs no
archive and no network.

| Input | Path | SHA-256 | Fields read |
| --- | --- | --- | --- |
| W27 coverage (W27-R02 basis) | `benchmarks/m06/openidaes450/coverage.json` | `b69626c7e908218e70f8726534a00c964674b2cbda7f582c8650ed939e48e3ba` | `rows[].case_id`, `rows[].family`, `rows[].class`; `snapshot.git_commit`, `snapshot_sha256` (recorded) |
| W27 case facts | `benchmarks/m06/openidaes450/case_facts.json` | `0ca8cffa146865971dd2a2d445b699cf484965cc052f7f37d8f6554c669e38f7` | `cases[].case_id`, `source.archive_sha256` (recorded); and for SPLIT-A13 only `unit_source`, `units[].key`, `units[].topology_kind`, `topology_kinds` of the two cases named there; the key set of every case (SPLIT-R13's fact check) |
| W27 sample | `benchmarks/m06/openidaes450/runs/w27-m07-83f825d/sample.json` | `33f146ece4fec078b8a464059f27d7256439941d6340de214352efb37b1a92bf` | `cases`, `canaries`, `excluded` |

The generator reads no `reasons`, `units`, `components` or `packages` field of `coverage.json`. Stratification needs
only the class. If any input's SHA-256 differs from the pin, the generator refuses (SPLIT-R12).

## 3. The split

**SPLIT-R02 (frame).** The frame is the 450 cases minus those whose `coverage.json` class is `ARTIFACT_INCOMPLETE`.
The excluded cases are in neither half and are listed by id. Dynamic cases (`NOT_STEADY_STATE_SIMULATION`) are in the
frame. They are part of what the suite measures, because correct limitation reporting is scored, and dynamic support
is a plausible later goal whose held-out evidence should exist from the start.

**SPLIT-R03 (strata).** A stratum is a pair (family, class), where both values are read from `coverage.json` as
committed. The strata therefore use **W27-R02 as registered**, not the F-1 rule of §6. Its key is the string
`family + "|" + class`.

**SPLIT-R04 (exposed cases are development).** A case is *exposed*, and therefore a development case, if it is:
(a) in `sample.json#/cases` (45); (b) in `sample.json#/canaries` (3); or (c) one of the 17 cases below. Each of the 17
is named in a committed file, other than the all-case data files of SPLIT-R10, at commit `f397467` (the commit this
registration starts from). A case named there has had its content read and discussed by development: registered test
states, classifier tests, stubs, specs and reviews. Each row gives the first file in path order that names the case.

| Case | First named in (at `f397467`) |
| --- | --- |
| `blind_synthesized_hda_flash` | `docs/derivations/M06-W27-registration.md` (W27-A08) |
| `blind_synthesized_methanol_recycle` | `docs/derivations/T08-release-spec.md` |
| `dispatches_nuclear_double_loop` | `docs/reviews/W27-verdict-83f825d.md` (F-1) |
| `idaes_feed_flash` | `benchmarks/m06/w27/stubs.py` |
| `idaes_ngcc_soec` | `docs/derivations/M06-W27-registration.md` |
| `idaes_temperature_swing_adsorption` | `docs/reviews/W27-verdict-83f825d.md` (F-1) |
| `official_btx_flash_canary` | `docs/derivations/M06-W27-registration.md` |
| `official_idaes_eg_pfr_flowsheet` | `docs/derivations/M06-W27-registration.md` |
| `official_idaes_eg_stoichiometric_flowsheet` | `docs/derivations/M06-W27-registration.md` |
| `official_idaes_smr_equilibrium_flowsheet` | `docs/derivations/M06-W27-registration.md` |
| `official_idaes_smr_gibbs_flowsheet` | `docs/derivations/M06-W27-registration.md` |
| `pareto_produced_water_network` | `docs/derivations/M06-W27-registration.md` |
| `variant_hda_once_through_single_flash` | `docs/derivations/M06-W27-registration.md` |
| `variant_idaes_ammonia_synthesis_intercool_condense` | `docs/derivations/M06-W27-registration.md` |
| `variant_idaes_hx_ntu_e60_a80` | `benchmarks/m06/w27/stubs.py` |
| `variant_idaes_iapws_pump_dp200k_eff75` | `docs/derivations/M06-W27-registration.md` (W27-A07) |
| `variant_methanol_water_nrtl_partial_condensation` | `docs/derivations/M06-W27-registration.md` |

Matching is by whole token: a case id counts as named only where it is a maximal run of `[A-Za-z0-9_]`, so
`watertap_adm1` is not matched inside a longer id. The one excluded case (`watertap_metab`, `ARTIFACT_INCOMPLETE`) is
also named, in `sample.json#/excluded`. It is outside the frame and in neither half. The list is frozen in the
generator. Its completeness is checked at every commit by SPLIT-A09, which finds no held-out id in any committed
file outside the allowlist (bar §8.3's recorded contamination).

**SPLIT-R05 (seed and ranks).** The seed is fixed before the draw. It is not a free choice: it embeds the full hash
of the brief commit, which the build lane made before this session began.

`seed_text = "OpenIDAES-450-split-v1/f39746770dd7f3f1ad96f75dbac8d29b4deef4f7"` (UTF-8).

`rank(purpose, id) = sha256(seed_text ‖ 0x00 ‖ purpose ‖ 0x00 ‖ id)` is the lowercase hex digest, and ranking is
by ascending digest. This is W27-R29's idiom: no RNG library is used, so the ranks are byte-reproducible. The
purposes are `"stratum"`, `"case"` and `"added"`.

**SPLIT-R06 (allocation).** For a stratum *s* with *N* frame cases, of which *E* are exposed:
- Order the strata with odd *N* by ascending `rank("stratum", key)` and number them 0, 1, 2, … (`odd_rank`).
- The target held-out count is `T = ⌊N/2⌋ + 1` if *N* is odd and `odd_rank` is even, and `T = ⌊N/2⌋` otherwise.
  The odd strata thus alternate between rounding up and down, so the frame-wide target is within one case of half.
- The held-out count is `H = min(T, N − E)`. The shortfall is `T − H`. A shortfall is positive exactly when exposure
  takes more than `N − T` of the stratum.
- The held-out cases are the first *H* **unexposed** cases of the stratum by ascending `rank("case", case_id)`.
  Every other case of the stratum, exposed or not, is a development case.

No compensation happens across strata: a shortfall stays in its stratum and is recorded.

**SPLIT-R07 (the record).** The generator writes `benchmarks/c2/openidaes450_split.json` (schema
`openidaes450-split-v1`), canonical JSON (sorted keys, two-space indent, UTF-8, trailing newline). It holds:
- the seed text and the hash idiom;
- the pinned inputs with their SHA-256, the archive SHA-256 from `case_facts.json#/source`, and the snapshot
  `git_commit` and `snapshot_sha256` from `coverage.json`;
- the strata basis (`"W27-R02"`);
- the excluded ids;
- the exposed ids with the source of each;
- the development ids (in clear);
- the held-out count and **commitment** only;
- the per-stratum table (`family`, `class`, `n`, `exposed`, `odd_rank` or null, `target`, `held_out`, `development`,
  `shortfall`);
- the totals;
- the `contaminated` list (SPLIT-R11);
- the F-1 status (SPLIT-R13).

Held-out ids do not appear in it.

The commitment is `sha256` of the UTF-8 string formed by the sorted held-out ids, each followed by `"\n"`. Anyone
can recompute the held-out list from the committed inputs and these rules (`held_out_ids()` in the generator), and
check it against the commitment. The commitment pins the list against silent change. It does not hide the list
(§10).

## 4. Use and protection

**SPLIT-R08 (use).** Development cases drive gap analysis, unit and property selection, and agent prompt and tool
tuning. A feature choice cites development case ids or a general library goal, never a held-out case. The held-out
half is scored only at release gates. It is reported separately from the development half and next to it, with the
development/held-out gap. The release registration that scores it decides what is scored (§11 Q-1).

**SPLIT-R09 (no held-out gap frequencies).** Nothing may compute, record or quote a frequency of missing units,
components, property methods or blocking reasons over held-out cases, or over any set that contains them (the 450,
the frame). A release-gate score may report held-out *class counts* and the scored outcomes. It may not report
which units, components or methods are missing in held-out cases.

**SPLIT-R10 (where held-out ids may appear).** A held-out id may appear in a committed file only if:
(a) the file is one of the twelve pre-split all-case data files listed in the generator (`ALL_CASE_FILES`): the five
at the top of `benchmarks/m06/openidaes450/` that hold every case (`access_report`, `case_facts`, `coverage`,
`dry_illustration`, `registration`), `runs/w27-m07-83f825d/coverage.json`, and M07's six
`rc/step17/{at-c,at-cw,coverage-at-C}.json.gz`; or
(b) the file's path has a directory segment named `heldout`. Release-gate outputs that carry held-out rows go there.

Development agents do not open the files of (a) or (b) except through a filter that drops non-development rows. The
build lane provides that filter (§11 Q-3). Until it exists, development reads only `openidaes450_split.json`, `sample.json`, the
W27 run directories and the development rows that a script prints after filtering by `openidaes450_split.json#/development`.

Mechanical consumers compute the held-out list in memory: the generator, the SPLIT-A09 test, and release-gate
scorers. They never print a held-out id. A failure message identifies a held-out id by the first 12 hex digits of
`sha256(id)`.

**SPLIT-R11 (contamination).** If a held-out case is exposed after the split, the split is not redrawn and the case
is not moved. Exposure means it is named outside SPLIT-R10's allowlist, or a development agent reads its content.
The case is recorded in `openidaes450_split.json#/contaminated` as `sha256(id)` (hex) with the date and the cause, by an amendment
to this registration and a register entry. It stays held-out, is scored at release gates, and is reported in a
separate line, outside the held-out headline. Deleting the mention to make SPLIT-A09 pass is not a remedy. The
contamination is recorded, and SPLIT-A09 then tolerates that id, in the files the entry names only.

*Amended at the first draw (2026-10-21).* The list holds one entry (§8.3). The text above was written expecting it
to be empty.

## 5. Re-split policy

**SPLIT-R12 (no re-draw; archive changes).** The split is drawn once. A case keeps its half for as long as this
registration stands. If any pinned input changes, the generator refuses to emit, names the file and points to this
rule. The change is then handled by an amendment, not a re-draw:
- **Removed case:** dropped from its half and recorded. No other case moves.
- **Changed case** (same id, different content): it keeps its half. The amendment records the changed field.
- **Added case,** including a repaired `ARTIFACT_INCOMPLETE` case: if it was exposed before its assignment
  (SPLIT-R04's sense), it is a development case. Otherwise it is held-out iff the first hex digit of
  `rank("added", id)` is in `0…7`, and development otherwise.
- **New family, or a re-based archive** (a new suite version): a new registration. Broader claims need an
  independent second suite (§10).

A full re-split needs a new registration, a new seed and a register entry stating that v1's held-out evidence is
void. The recommended default is never; prefer an independent suite.

## 6. W27-R02 and F-1 under this registration

**SPLIT-R13 (the R02 successor, "R02-F1"; R-474's default, made precise).** It governs every OpenIDAES-450
classification made under this registration: development gap analysis, and release-gate scoring of either half. It
does not govern the strata of SPLIT-R03, which are fixed at the draw and never re-derived. A reclassification moves
no case between halves.

For a case whose `unit_source` is `units.json`, the units are W27-R02's units together with one unit group per
topology kind *k* such that:
- *k* is the `kind` of some unit in `topology.json#/units`;
- *k* is not a boundary kind (`BOUNDARY_KINDS = {"Feed", "Product"}`); and
- *k* is not *covered*. A kind is covered if some W27-R02 unit group of the case has `topology_kind == k`, or has a
  key whose subject (the text after `idaes:`) equals *k*. The second condition is the class-name fallback for an
  entry whose name matches no topology id.

Each added group is keyed `topology:<k>`. Its `names` are the ids of the case's topology units of kind *k*, and it
carries `from_topology: true`. A reason built from it carries `source=topology` in its detail. Cases whose
`unit_source` is `topology.json` or `none` are unchanged.

**Facts this needs that `case_facts.json` lacks.**
- `case_facts.json` (schema `w27-case-facts-v1`) records, for a `units.json` case, only the *set* of topology kinds
  (`topology_kinds`). It does not record the topology units' ids, and has no per-kind ids. So an added group cannot be
  named, and W27-R40's aliases cannot include its ids.
- The fact needed is `topology_units: [{"id", "kind"}]` for every case, sorted by id. The workstation's facts stage
  already reads it (`m06_w27_registration.py:1087`, `by_id`).
- The workstation's next `facts` run writes it to a **new** file, `case_facts-v2.json` (schema
  `openidaes450-case-facts-v2`), next to W27's. W27's `case_facts.json` is not rewritten: `coverage.json` pins its
  SHA-256.

Until then `openidaes450_split.json#/f1/status` is `"awaiting_facts"`. The generator verifies the status: it refuses if any case
in `case_facts.json` already carries `topology_units`.

**The state R02-F1 must keep (W27-A08, restated).** At kind level, the facts above suffice to check two cases, both
exposed (development):
- `blind_synthesized_hda_flash`: every non-boundary topology kind is covered, so R02-F1 adds no group. The case keeps
  exactly one unit reason, `PressureChanger`. Its internal `fs.F101.split` is still not a unit.
- `official_idaes_skeleton_pervaporation` (run 26): R02-F1 adds exactly one group, kind `SkeletonUnitModel`. This is
  F-1's hidden unit.

SPLIT-A13 asserts both: the vanishing state and the non-vanishing one.

**Open fact (needs a fact; §11 Q-4).** It is not yet known whether the class-name fallback suppresses a true
omission, or the topology_kind-only rule adds false groups. On the workstation's next facts run, measure over
**development cases only**:
- (i) the number of `units.json` cases with a group carrying no `topology_kind`; and
- (ii) for each variant (with fallback, without), the number of development cases that gain a group, and the added
  kinds.

The recommended default is the fallback, as registered above.

## 7. Generator

**SPLIT-R14 (generator and refusals).** `docs/derivations/scripts/c2_openidaes450_split.py`, run as
`PYTHONPATH=src python docs/derivations/scripts/c2_openidaes450_split.py --emit | --check`. `--check` regenerates in
memory and compares the result byte for byte with the committed `openidaes450_split.json`. The generator refuses to emit, with
exit code 2 and a message that names the violated rule and never a held-out id, when:
1. an input's SHA-256 differs from its pin (SPLIT-R01/R12);
2. the case-id sets of `coverage.json` and `case_facts.json` differ, or either has duplicate ids;
3. an exposed id is not a case id, or lies outside the frame;
4. the sample's `excluded` differs from the frame's excluded cases;
5. a partition identity fails: development ∪ held-out ∪ excluded is the 450, pairwise disjoint; every stratum has
   `held_out + development = n`, `held_out = min(target, n − exposed)` and `shortfall = target − held_out`; or the
   frame-wide target is not within one of half the frame;
6. an exposed case is in the held-out set;
7. a mutated rule gives the same commitment as the registered one. The mutants are: purpose `"order"` instead of
   `"case"`; all odd strata rounded down; and exposure not forced. Each mutant must change the held-out set, so the
   commitment is shown to distinguish the rule from its likeliest slips;
8. the F-1 fact check of SPLIT-R13 fails, or SPLIT-A13's two kind-level states do not hold;
9. the record would contain a held-out id, or any key named `reasons`, `units`, `components` or `packages`;
10. a `contaminated` entry is not the hash of a held-out case (SPLIT-R11).

## 8. Results (first draw, 2026-10-21; commit `c0649a7`)

### 8.1 Sizes

| Quantity | Value |
| --- | --- |
| Cases / frame / excluded | 450 / 449 / 1 (`watertap_metab`, `ARTIFACT_INCOMPLETE`) |
| Exposed (forced development) | 65 = 45 sample + 3 canaries + 17 named |
| **Development** | **225** |
| **Held-out** | **224**. The headline is **223**: one case is contaminated (§8.3) |
| Strata / odd strata | 17 / 9 |
| Frame-wide target held-out | 225 = ⌈449/2⌉ |
| Shortfall | 1, in stratum `pareto\|COMPONENT_UNAVAILABLE` (*n* = 1, and its one case is exposed) |
| Held-out commitment | `08b81669d5e15c4d1e9d99a0bca2b458ea5d46cfe71a521d32c3fba33daaea91` |
| Record SHA-256 | given by register entry R-486 |

### 8.2 Strata (W27-R02 classes)

UU = `UNIT_UNAVAILABLE`, NSS = `NOT_STEADY_STATE_SIMULATION`, CU = `COMPONENT_UNAVAILABLE`.

| Family | Class | *n* | exposed | odd_rank | target | held-out | development | shortfall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dispatches | NSS | 7 | 1 | 7 | 3 | 3 | 4 | 0 |
| dispatches | UU | 4 | 1 | – | 2 | 2 | 2 | 0 |
| gtep | NSS | 21 | 2 | 4 | 11 | 11 | 10 | 0 |
| idaes | CU | 16 | 6 | – | 8 | 8 | 8 | 0 |
| idaes | NSS | 7 | 0 | 8 | 4 | 4 | 3 | 0 |
| idaes | UU | 165 | 28 | 3 | 82 | 82 | 83 | 0 |
| mvo | NSS | 18 | 3 | – | 9 | 9 | 9 | 0 |
| pareto | CU | 1 | 1 | 0 | 1 | 0 | 1 | 1 |
| pareto | NSS | 1 | 1 | 5 | 0 | 0 | 1 | 0 |
| pareto | UU | 2 | 0 | – | 1 | 1 | 1 | 0 |
| prommis | NSS | 2 | 1 | – | 1 | 1 | 1 | 0 |
| prommis | UU | 23 | 2 | 6 | 12 | 12 | 11 | 0 |
| reaktoro | UU | 6 | 1 | – | 3 | 3 | 3 | 0 |
| reflo | NSS | 1 | 0 | 2 | 1 | 1 | 0 | 0 |
| reflo | UU | 18 | 2 | – | 9 | 9 | 9 | 0 |
| watertap | NSS | 8 | 0 | – | 4 | 4 | 4 | 0 |
| watertap | UU | 149 | 16 | 1 | 74 | 74 | 75 | 0 |

These are class counts, which coverage.json already publishes for all 450 cases. The table contains no frequency of
missing units, components or methods (SPLIT-R09).

### 8.3 Contamination found at the first draw (SPLIT-R11 applied to this document)

SPLIT-A09 failed at the first draw. A held-out id appeared in this registration. SPLIT-R04's text, committed before
the draw (`0211372`), used it as the example of whole-token matching. At that time nobody knew which half it would
fall in. No content of the case was read, but the name says what kind of model it is. Under SPLIT-R11 it is recorded
as contaminated:
- `sha256(id)` begins `c87ac13adc32`;
- the cause is recorded;
- the one file allowed to name it is this one.

It stays held-out, is scored at release gates, and is reported outside the headline. The mention is kept, not
deleted. The generator refuses if a contamination entry is not a held-out case.

*Lesson, binding on later amendments.* Prose in this repository names only development or excluded cases. An example
id is chosen from the exposed list.

## 9. Assertions (for the build-lane test; implemented in `tests/test_c2_openidaes450_split.py`)

**Tolerances.** Every assertion is exact. The quantities are integers, id strings and SHA-256 digests. No floating
point is involved, so there is no roundoff floor, and any difference is a defect.

**Where the expected values come from.**
- The validation is the identities and an independent re-implementation of SPLIT-R02…R06. The test writes it from
  this text and shares no code with the generator.
- The sizes (225/224/1/65) and the commitment are regression values from the first draw. They pin the draw; they
  do not validate it.

| Id | Assertion | Expected | Why this state, and what it catches |
| --- | --- | --- | --- |
| SPLIT-A01 | Regenerating from the committed inputs gives the committed record byte for byte (`--check`) | exit 0, identical bytes | catches drift in the generator, the inputs or the canonical form |
| SPLIT-A02 | One changed byte in `coverage.json` is refused | `SPLIT-R01/R12` refusal | a silent re-split on an archive change |
| SPLIT-A03 | development ∪ held-out ∪ excluded = the 450, pairwise disjoint; development ∪ held-out = frame | sizes (225, 224, 1), frame 449, excluded = {`watertap_metab`} | a dropped or double-assigned case |
| SPLIT-A04 | exposed = sample ∪ canaries ∪ the 17 named; exposed ⊆ development | 65 = 45 + 3 + 17; sources counted per kind | an exposed case in held-out (Frank's rule) |
| SPLIT-A05 | an independent re-implementation gives the same development ids and the same commitment | equal | a generator that drifts from this text |
| SPLIT-A06 | per stratum: `target = ⌊n/2⌋ + [odd_rank even]`, `held_out = min(target, n − exposed)`, `development = n − held_out`, `shortfall = target − held_out`; with no shortfall, \|n − 2·held_out\| ≤ 1; `odd_rank` is 0…8 over the odd strata only; \|2·Σtarget − 449\| ≤ 1 | Σtarget 225; the only shortfall is `pareto\|COMPONENT_UNAVAILABLE` (1, 1, 1) | a wrong rounding, a lost alternation, a compensation across strata |
| SPLIT-A07 | `held_out_ids()` equals the independent held-out set, and its commitment equals the record's | equal | a scorer reading a different set from the committed one |
| SPLIT-A08 | `seed_text` is the registered string; `rank("case","x")` equals `sha256(seed ‖ 0x00 ‖ "case" ‖ 0x00 ‖ "x")` and differs from `rank("order","x")` | equal / different | a changed seed, separator or purpose |
| SPLIT-A09 | No held-out id appears as a whole token in any tracked file (`.gz` decompressed) outside SPLIT-R10's allowlist, except a contaminated id in the files its entry names; more than 1000 files are scanned | no hit; a failure names only `sha256(id)[:12]` | a held-out leak (SPLIT-R10). The non-vanishing state was observed at the first draw (§8.3) |
| SPLIT-A10 | The record names no held-out id and has no `reasons`, `units`, `components` or `packages` key | none | gap data, or held-out ids, entering the record |
| SPLIT-A11 | The strata are (family, class) of `coverage.json` minus `ARTIFACT_INCOMPLETE`; `strata_basis` is `W27-R02` | 17 strata whose *n* equal an independent recount | strata taken from another classification |
| SPLIT-A12 | `f1.status` is `awaiting_facts`, and no case has `topology_units`; adding one makes the generator refuse | `SPLIT-R13` refusal | applying R02-F1 without its facts, or keeping "awaiting" after they arrive |
| SPLIT-A13 | Kind-level R02-F1 adds nothing to `blind_synthesized_hda_flash` (its coverage row keeps exactly one unit reason, `PressureChanger`) and exactly `SkeletonUnitModel` to `official_idaes_skeleton_pervaporation` | {} and {`SkeletonUnitModel`} | W27-A08 restated (the vanishing state) next to F-1's hidden unit (the non-vanishing state); a wrong boundary set or a missing fallback changes one of them |
| SPLIT-A14 | Each mutant changes the held-out commitment: purpose `"order"`, odd strata all rounded down, exposure not forced | three different digests | a commitment that cannot tell the rule from its slips |
| SPLIT-A15 | Inconsistent inputs are refused: a named id that is no case (R14.3); a named id outside the frame (R14.3); a changed `sample.json#/excluded` (R14.4); different id sets (R14.2) | the named refusal | a placeholder success on bad input |
| SPLIT-A16 | `contaminated` holds exactly the §8.3 entry; it is a held-out case; the headline is held-out − 1 | one entry (`c87ac13adc32…`), headline 223 | contamination dropped, or moved into development |
| SPLIT-A17 | `--check`'s output names no held-out id | none | a debug print leaking held-out ids |

## 10. What this registration does not establish

- **No claim beyond OpenIDAES-450's population.** Both halves draw on the same nine families and the same archive
  authors and generators, and many cases are variants of one another. A development/held-out gap measures
  generalisation *within* this suite. A claim about other flowsheet populations needs an independent second suite.
- **No secrecy.** Anyone can recompute the split from public inputs and a public seed. The commitment pins the
  held-out list; it does not hide it. W27's `coverage.json` publishes every case's blocking reasons, held-out cases
  included. Protection is the recorded rules (SPLIT-R08…R11) and the leak guard (SPLIT-A09). It is not access
  control.
- **The leak guard covers committed files only.** It cannot see an agent reading held-out rows of the all-case files
  or of the archive, or ids in chat that was never committed.
- **Exposure is complete only with respect to committed files at `f397467`.** Disclosure: on 2026-10-18 a session
  computed gap frequencies over all 450 cases, in chat. They were not committed, and no development used them (the
  brief). The held-out half is therefore not unseen by that session.
- **Build-lane disclosure (2026-10-21, this cloud session, before the draw).** While preparing briefs, the build
  lane printed, in-session and uncommitted, the eight most frequent unavailable components over all 450 rows of
  W27's `coverage.json` (H2O, CO2, NaCl, O2, benzene, toluene, CO, an unidentified `solute`). These are
  all-case counts, not development counts; L01 must not use them and re-derives its priorities from the
  development half alone.
- **What this session read.** This session read the families and classes of all cases, scanned committed files for
  case-id tokens, and read the unit facts of the two exposed cases of SPLIT-A13. It computed nothing else per
  held-out case.
- **Strata are a balance device, not a classification claim.** They use W27-R02's classes. A case that R02-F1 would
  reclassify sits in its R02 stratum. Other covariates are not balanced and no balance is claimed for them:
  `in_full82`, `model_type`, `unit_source`, the residual check.
- **No claim about R02-F1's effect on any held-out case.** R02-F1 is registered, not applied. Its kind-level check
  covers two development cases only.
- **The sizes are not optimal in any sense,** and the 225/224 numbers are regression values, not validation.

## 11. Open questions (each with a recommended default; work proceeds on the default)

- **Q-1 (needs Frank's preference).** What does a release gate score on the held-out half?
  - Default: the coverage classification of every held-out case under R02-F1 (no spend), reported beside the
    development half with the gap.
  - An agent campaign over held-out cases happens only when a release registration registers one. It draws from the
    held-out half with its own seed.
  - Logged in `docs/FRANK_QUESTIONS.md`.
- **Q-2 (needs Frank's preference).** Should the 17 named cases (SPLIT-R04 (c)) count as development? Frank's rule
  named only W27's drawn cases.
  - Default: yes (DECISION D-6). Reversing it needs a v2 registration before any held-out score is reported.
  - Logged in `docs/FRANK_QUESTIONS.md`.
- **Q-3 (build lane, has a test).** The development filter of SPLIT-R10.
  - Default: a script that writes an all-case file's development rows to stdout, filtered by
    `openidaes450_split.json#/development/case_ids`.
  - Acceptance: its output holds no held-out id (the SPLIT-A09 token check) and exactly the development rows.
- **Q-4 (needs a fact).** Is R02-F1's class-name fallback right? This is measured on the workstation's next facts run,
  on development cases only (§6).
  - Default: the fallback, as registered.

## 12. Decisions (also in `docs/C2_DECISIONS.md`)

- DECISION D-1: split ratio → per-stratum halves; odd strata alternate up and down by stratum rank; no compensation
  across strata. Alternative: a global largest-remainder allocation, or 60/40. Reversible by: a v2 registration
  before any held-out score is reported.
- DECISION D-2: which R02 the strata use → W27-R02 as committed in `coverage.json`. Using R02-F1 needs facts that are
  absent, and would mean computing unit availability for held-out cases. Alternative: R02-F1 classes. Reversible by:
  a v2 registration (the strata are fixed at the draw).
- DECISION D-3: seed source → a fixed string embedding the full hash of the brief commit (`f397467…`), committed
  before the draw. Alternative: the archive's SHA-256, or a free string. Reversible by: a v2 registration.
- DECISION D-4: dynamic cases → in the frame as their own class strata. Alternative: exclude them. Reversible by: a
  v2 registration.
- DECISION D-5: incomplete cases → excluded from both halves and listed; a repaired one is an added case under
  SPLIT-R12. `watertap_metab` is already named, so it would be development. Alternative: assign now. Reversible by:
  an amendment.
- DECISION D-6: what counts as exposed → W27's 45 cases and 3 canaries, plus the 17 cases named in committed non-data
  files at `f397467`. Alternative: only the 48. Reversible by: a v2 registration before any held-out score is
  reported.
- DECISION D-7: protection → recorded rules; held-out ids never in clear outside the allowlist; the record carries a
  commitment; a leak-guard test. Alternative: list the held-out ids in clear, with a rule alone. Reversible by:
  adding the ids to the record (one-way).
- DECISION D-8: re-split policy → never redraw; changes go by amendment (removed, changed and added cases);
  added cases take a seeded per-case coin. Alternative: redraw on every archive change. Reversible by: a new
  registration.
- DECISION D-9: F-1 → registered as R02-F1 with a class-name fallback. Its facts (`topology_units`) wait for the
  workstation, in a new `case_facts-v2.json`. Alternative: the topology_kind-only rule, or a flag. Reversible by: an
  amendment after Q-4's measurement.
- DECISION D-10: the contamination found at the first draw → recorded under SPLIT-R11. The mention is kept and the
  headline is 223. Alternative: edit the example out and say nothing, which SPLIT-R11 forbids. Reversible by: none
  needed.
- DECISION D-11: where the record lives → `benchmarks/c2/openidaes450_split.json`, by the package-id convention of
  `benchmarks/`. Alternative: next to W27's data. Reversible by: a move together with the generator constant.

## 13. Register entries

R-486 (the split and its record), R-487 (strata on W27-R02), R-488 (exposure), R-489 (seed), R-490 (protection and
contamination), R-491 (re-split policy), R-492 (R02-F1), R-493 (dynamic and incomplete cases), R-494 (non-claims and
the second-suite requirement).
