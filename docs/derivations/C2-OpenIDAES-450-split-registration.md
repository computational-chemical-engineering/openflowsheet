# OpenIDAES-450 development / held-out split — registration (C2)

**Status.** Registered by the design lane (`specifier`), package C2, branch `wp/C2`, 2026-10-21. Requested by Frank
on 2026-10-18 (`docs/briefs/OpenIDAES-split-registration.md`). Register entries R-486…R-494.

**Authority and scope.** This document is the normative text for one thing: which OpenIDAES-450 cases are
*development* cases and which are *held-out* cases, and the rules that keep the held-out cases out of development.
It also registers the successor of W27-R02 (finding F-1, R-474) for classifications made under it (§6). It changes
nothing in the W27 registration, in `coverage.json`, in step 17's carry or in v0.2's released scores. It decides no
v0.3 scope. Rules are `SPLIT-R01…R14`; assertions are `SPLIT-A01…A25` (§9; A18–A19 added by Amendment 1,
A20–A25 by Amendment 2).

**Amendments.** Amendment 1 (2026-10-22, R-555, §14): a re-taken `coverage.json` is read at its pinned content.
Amendment 2 (2026-10-23, R-581, R-582, §15): the F-1 facts file `case_facts-v2.json`, its writer, its admission under
SPLIT-R10, and `f1.status` `facts_committed`.

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

*Amended 2026-10-22 (Amendment 1, §14).* The pin of `coverage.json` pins the content the draw reads. When the working
copy has moved on, that content is read from git history, and the working copy must keep the pinned read fields.

*Amended 2026-10-23 (Amendment 2, §15).* The draw still reads these three files only. The `f1` block of the record
also reads a fourth pinned file, `benchmarks/m06/openidaes450/case_facts-v2.json` (strict pin `4f5c5a65…`, not a
draw input), and for SPLIT-R14 item 14 it reads `case_id` and `topology_kinds` of every case of `case_facts.json`.
The generator still needs no archive and no network.

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

**SPLIT-R07 (the record).** The generator writes `benchmarks/m06/openidaes450/split.json` (schema
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
build lane provides that filter (§11 Q-3). Until it exists, development reads only `benchmarks/m06/openidaes450/split.json`, `sample.json`, the
W27 run directories and the development rows that a script prints after filtering by `benchmarks/m06/openidaes450/split.json#/development`.

Mechanical consumers compute the held-out list in memory: the generator, the SPLIT-A09 test, and release-gate
scorers. They never print a held-out id. A failure message identifies a held-out id by the first 12 hex digits of
`sha256(id)`.

*Amended 2026-10-23 (Amendment 2, §15).* (a) admits one more file, by exact path: the post-split F-1 facts file
`benchmarks/m06/openidaes450/case_facts-v2.json`. `ALL_CASE_FILES` then holds thirteen exact paths. The F-1 facts
writer (`docs/derivations/scripts/c2_openidaes450_facts_v2.py`) is a mechanical consumer: it reads every case and
prints no case id. The filter rule above applies to `case_facts-v2.json` as to every file of (a).

**SPLIT-R11 (contamination).** If a held-out case is exposed after the split, the split is not redrawn and the case
is not moved. Exposure means it is named outside SPLIT-R10's allowlist, or a development agent reads its content.
The case is recorded in `benchmarks/m06/openidaes450/split.json#/contaminated` as `sha256(id)` (hex) with the date and the cause, by an amendment
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

*Amended 2026-10-22 (Amendment 1, §14).* A re-take of `coverage.json` that keeps every row's `case_id`, `family` and
`class` is not a change under this rule: the draw reads the pinned content from git history. A re-take that changes
any of them is refused (`SPLIT-R12/A1`) and is this rule's amendment trigger.

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

Until then `benchmarks/m06/openidaes450/split.json#/f1/status` is `"awaiting_facts"`. The generator verifies the status: it refuses if any case
in `case_facts.json` already carries `topology_units`.

*Amended 2026-10-23 (Amendment 2, §15).* The facts are written by a C2-owned script,
`docs/derivations/scripts/c2_openidaes450_facts_v2.py`, not by a stage of W27's generator, which stays byte-unchanged.
`case_facts-v2.json` is committed, pinned by the generator, and checked against `case_facts.json`. `f1.status` is
`"facts_committed"`. The refusal on `topology_units` in `case_facts.json` is kept: W27's file never gains it.

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
memory and compares the result byte for byte with the committed `benchmarks/m06/openidaes450/split.json`. The generator refuses to emit, with
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

*Amended 2026-10-22 (Amendment 1, §14).* Item 1 applies to the content the draw reads: for `coverage.json` that is
the working copy if it has the pinned SHA-256, and otherwise git blob `PINNED_BLOBS["coverage"]`, whose SHA-256 must
equal the pin. Two refusals are added:

11. the working copy of `coverage.json` has moved on and its read fields differ from the pinned content's
    (`SPLIT-R12/A1`; the message gives counts only);
12. the working copy of `coverage.json` has moved on and the pinned content cannot be read from git history
    (`SPLIT-R01/A1`; no fallback to the working copy).

*Amended 2026-10-23 (Amendment 2, §15).* Item 8 is kept. Three refusals are added, all about
`case_facts-v2.json`; their text is in §15.4:

13. the file is absent, or its SHA-256 differs from its pin (`SPLIT-R13/A2`; no fallback to `awaiting_facts`);
14. the file is inconsistent with `case_facts.json` (`SPLIT-R13/A2`; the message gives counts only);
15. the unit-level F-1 states differ from the registered ones (`SPLIT-R13`).

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
| SPLIT-A02 | One changed byte in the `coverage.json` content the draw reads is refused (Amendment 1: the content `read_inputs` returns, not the working copy) | `SPLIT-R01/R12` refusal | a silent re-split on an archive change |
| SPLIT-A03 | development ∪ held-out ∪ excluded = the 450, pairwise disjoint; development ∪ held-out = frame | sizes (225, 224, 1), frame 449, excluded = {`watertap_metab`} | a dropped or double-assigned case |
| SPLIT-A04 | exposed = sample ∪ canaries ∪ the 17 named; exposed ⊆ development | 65 = 45 + 3 + 17; sources counted per kind | an exposed case in held-out (Frank's rule) |
| SPLIT-A05 | an independent re-implementation gives the same development ids and the same commitment | equal | a generator that drifts from this text |
| SPLIT-A06 | per stratum: `target = ⌊n/2⌋ + [odd_rank even]`, `held_out = min(target, n − exposed)`, `development = n − held_out`, `shortfall = target − held_out`; with no shortfall, \|n − 2·held_out\| ≤ 1; `odd_rank` is 0…8 over the odd strata only; \|2·Σtarget − 449\| ≤ 1 | Σtarget 225; the only shortfall is `pareto\|COMPONENT_UNAVAILABLE` (1, 1, 1) | a wrong rounding, a lost alternation, a compensation across strata |
| SPLIT-A07 | `held_out_ids()` equals the independent held-out set, and its commitment equals the record's | equal | a scorer reading a different set from the committed one |
| SPLIT-A08 | `seed_text` is the registered string; `rank("case","x")` equals `sha256(seed ‖ 0x00 ‖ "case" ‖ 0x00 ‖ "x")` and differs from `rank("order","x")` | equal / different | a changed seed, separator or purpose |
| SPLIT-A09 | No held-out id appears as a whole token in any tracked file (`.gz` decompressed) outside SPLIT-R10's allowlist, except a contaminated id in the files its entry names; more than 1000 files are scanned | no hit; a failure names only `sha256(id)[:12]` | a held-out leak (SPLIT-R10). The non-vanishing state was observed at the first draw (§8.3) |
| SPLIT-A10 | The record names no held-out id and has no `reasons`, `units`, `components` or `packages` key | none | gap data, or held-out ids, entering the record |
| SPLIT-A11 | The strata are (family, class) of `coverage.json` minus `ARTIFACT_INCOMPLETE`; `strata_basis` is `W27-R02` | 17 strata whose *n* equal an independent recount | strata taken from another classification |
| SPLIT-A12 | (amended by Amendment 2) `f1.status` is `facts_committed`. No case of `case_facts.json` has `topology_units`; adding one makes the generator refuse (item 8, checked before items 13–15). Parsed as JSON, the record equals the record at git blob `17632cea3ac9e3ebe23076bade2fc6bf9c29948c` (SHA-256 `ee940a7e…`, R-486) in every member except `f1`, and `f1` differs | `facts_committed`; `SPLIT-R13` refusal; equal outside `f1` | applying R02-F1 without its facts; keeping "awaiting" after they arrive; an amendment that moves the draw, the commitment or the development ids |
| SPLIT-A13 | Kind-level R02-F1 adds nothing to `blind_synthesized_hda_flash` (its coverage row keeps exactly one unit reason, `PressureChanger`) and exactly `SkeletonUnitModel` to `official_idaes_skeleton_pervaporation` | {} and {`SkeletonUnitModel`} | W27-A08 restated (the vanishing state) next to F-1's hidden unit (the non-vanishing state); a wrong boundary set or a missing fallback changes one of them |
| SPLIT-A14 | Each mutant changes the held-out commitment: purpose `"order"`, odd strata all rounded down, exposure not forced | three different digests | a commitment that cannot tell the rule from its slips |
| SPLIT-A15 | Inconsistent inputs are refused: a named id that is no case (R14.3); a named id outside the frame (R14.3); a changed `sample.json#/excluded` (R14.4); different id sets (R14.2) | the named refusal | a placeholder success on bad input |
| SPLIT-A16 | `contaminated` holds exactly the §8.3 entry; it is a held-out case; the headline is held-out − 1 | one entry (`c87ac13adc32…`), headline 223 | contamination dropped, or moved into development |
| SPLIT-A17 | `--check`'s output names no held-out id | none | a debug print leaking held-out ids |
| SPLIT-A18 | (Amendment 1) git blob `PINNED_BLOBS["coverage"]` has the pinned SHA-256 and 450 rows, and the working copy's (`case_id`, `family`, `class`) multiset equals it. A working copy whose snapshot fields moved yields the pinned bytes and the committed record byte for byte, with the pinned `coverage_snapshot`. A working copy that has the pin is used without reading history | equal; identical bytes; history not read | a re-take breaking the split, or moving the record's provenance to the latest build; the unmoved state (no history read) is asserted beside the moved one |
| SPLIT-A19 | (Amendment 1, negative controls) one development case's `class` changed; its `family` changed; its row removed; a row added: each is refused. Without history (not a repository; an absent object) the refusal is explicit, and a blob with the wrong SHA-256 is refused | `SPLIT-R12/A1` with counts (removed, added, changed) = (0,0,1), (0,0,1), (1,0,0), (0,1,0), duplicate rows 0, and no case id in the message; `SPLIT-R01/A1`; `SPLIT-R01/R12` | a drift check that is never reached, compares the wrong fields, or leaks an id; silence read as success when history is missing |
| SPLIT-A20 | (Amendment 2) The committed `case_facts-v2.json` has the pinned SHA-256, and `f1.facts` names its path, that SHA-256, schema `openidaes450-case-facts-v2` and the writer's path. Git blob `7b0686e195ae6685fa1b0738a3dbbd674d21cc02` (WS1's file at `7b5c07f`, reachable from `main`) has SHA-256 `57d43acb…`. The two files are byte-identical after their first `\n`, and their first lines parse to objects that differ at `source.generator` only. One changed byte in the file is refused; so is an absent file. Without history the test fails naming the object; it does not skip | `4f5c5a65fe1b310e04b7e311464e4d87ba90ed4bfa7a90c240cde397cd0114ef`; `57d43acbee1c0952e43c0a5410783fd0dba8c1a4b4e38a74e31f8b57cbb33494`; tail SHA-256 `fb0e0fe31c6cd42d294e916ff87fd0038af03406d7ff6474dcd3930a5645724d`; `source.generator` `docs/derivations/scripts/m06_w27_registration.py` → `docs/derivations/scripts/c2_openidaes450_facts_v2.py`; `SPLIT-R13/A2` twice | a re-extraction that drifts from the content WS1 measured from the archive; a pin that is never checked; a missing file read as "awaiting" |
| SPLIT-A21 | (Amendment 2, negative controls) The committed pair passes item 14. Seven edits of the file, made in memory below the pin check, each to the first development case (`blind_synthesized_anaerobic_digester_unit`, four units): (1) its first unit's kind set to `A21Kind`, a kind no case has; (2) the case removed; (3) its first two units swapped; (4) a copy of its last unit appended; (5) `source.case_facts_v1_sha256` set to 64 zeros; (6) an extra key `x` on the case; (7) its first unit's `id` set to the integer 7 | refused `SPLIT-R13/A2` with the label (1) `kind_sets`, (2) `case_ids`, (3) `unit_order`, (4) `unit_ids`, (5) `binding`, (6) `case_keys`, (7) `unit_form`; no message holds any of the 450 case ids as a whole token | an identity that is never reached, that checks the wrong field, that is shadowed by another one, or that leaks an id |
| SPLIT-A22 | (Amendment 2) The unit-level F-1 states: `f1.unit_level_states` as registered; the kinds of its keys equal `f1.kind_level_states` case by case; the test recomputes them from both facts files by §6's rule, sharing no code with the generator; the skeleton case has exactly six topology units. Renaming `pervap` to `pervap2` in memory, below the pin check, passes item 14 and is refused by item 15 | `blind_synthesized_hda_flash`: `{}`; `official_idaes_skeleton_pervaporation`: `{"topology:SkeletonUnitModel": ["pervap"]}`; `SPLIT-R13` | F-1's hidden unit named wrongly or not at all; the vanishing state (`{}`) beside the non-vanishing one. Independent source for `pervap`: `docs/reviews/W27-verdict-83f825d.md` l.362 names it as the case's sixth topology unit, of kind `SkeletonUnitModel` |
| SPLIT-A23 | (Amendment 2) `ALL_CASE_FILES` is the twelve paths of SPLIT-R10 (a), unchanged, plus `benchmarks/m06/openidaes450/case_facts-v2.json`: 13 distinct entries, none containing `*`, `?` or `[` or ending in `/`, each a tracked regular file. The whole-token scan of `case_facts-v2.json` alone finds exactly `split.json#/held_out/count` distinct held-out ids | 13; 224 | an entry wider than one file; an entry that is not needed; a facts file that lost held-out rows. A09 (no hit outside the allowlist) is the vanishing state beside this one |
| SPLIT-A24 | (Amendment 2, needs no archive) Every file in `benchmarks.m06.w27.preflight.REGISTERED_SHA256` has its pinned SHA-256 (three files; true on `main` at `948944f3`) | equal | v0.2's W27 generator, document or `registration.json` changed, caught in CI where W27's P2 skips without the archive (the WS1 failure) |
| SPLIT-A25 | (Amendment 2, the writer) (a) With the archive, `python -I docs/derivations/scripts/c2_openidaes450_facts_v2.py --check` exits 0; without it the test is skipped with the reason `pinned archive absent`, and a skip counts as not checked. (b) Always: `--check --archive <empty dir>` exits 2, stdout starts `NOT CHECKED:`, and the committed file is unchanged. (c) Always, a regression and not a validation: a synthetic archive in a temporary directory, `cases/<case_id>/topology.json` = `{"units": <that case's topology_units>}` for every case of the file, gives `--check` exit 0; the same archive with the first development case's first unit's kind set to `A25Kind` gives exit 2, and the output holds no case id | (a) 0 or skip; (b) 2 and `NOT CHECKED:`; (c) 0, then 2 | a writer that cannot reproduce the committed bytes; silence read as success without the archive; self-claims that are never reached |

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
- **Amendment 1 does not establish** that a re-take's other fields (reasons, units, components, packages, versions)
  are unchanged, or that they matter to nothing else. It says only that the split does not read them. It does not make
  the split reproducible from a checkout without history once `coverage.json` has moved on; that case is refused.
  It does not cover `case_facts.json` or `sample.json`, which keep the strict pin.
- **Amendment 2 does not establish** which archive the writer read. `source.archive_sha256` is copied from
  `provenance.json`; the writer does not hash the archive. The evidence that the content is the archive W27 read is
  the kind-set identity with `case_facts.json` and the pinned output (§15.6). The kind-set identity checks two codings
  of one reading rule against each other; it is not an independent validation of the topology ids. Of those ids only
  `pervap` has an independent source (SPLIT-A22). The split generator does not check `source.access_report_sha256`
  (the writer's `--check` does). Amendment 2 applies R02-F1 to no case beyond the two registered states, and says
  nothing about R02-F1's effect on any held-out case. SPLIT-A25 (c) is a regression of the writer's canonical form,
  not a validation of its reading of real `topology.json` files.
- **What the Amendment 2 session read.** WS1's file, in memory: identities over all 450 cases (booleans and failure
  counts), the number of held-out ids it holds (224, SPLIT-A23), and the topology units of the two development cases
  of SPLIT-A13 and of the first development case (SPLIT-A21). It printed no held-out id, and it counted no unit or
  kind over held-out cases.

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
    `benchmarks/m06/openidaes450/split.json#/development/case_ids`.
  - Acceptance: its output holds no held-out id (the SPLIT-A09 token check) and exactly the development rows.
- **Q-4 (needs a fact).** Is R02-F1's class-name fallback right? This is measured on the workstation's next facts run,
  on development cases only (§6).
  - Default: the fallback, as registered.
  - *Amended 2026-10-23 (Amendment 2).* The measurement needs no archive: (i) and (ii) are kind-level, from
    `case_facts.json` (`units[].topology_kind`, `topology_kinds`), filtered to development rows first. It stays open
    on its default; it is a build-lane measurement whenever R02-F1 is first applied.
- **Q-5 (needs Frank's preference; Amendment 1).** Should a `class` change in a re-take refuse? The first capability
  that makes a unit or component available will reclassify cases, and SPLIT-R12/A1 will then refuse until an
  amendment records the change. The strata are fixed at the draw either way (SPLIT-R13), so the split itself is safe
  under both answers.
  - Default: refuse, as SPLIT-R12 registers ("the amendment records the changed field"). The amendment gives counts,
    and names held-out cases by `sha256(id)[:12]` only.
  - Alternative: refuse only on a changed `case_id` set or `family`, and leave class changes to release-gate scoring.
    Revisit at the first class-changing re-take.
- **Q-6 (needs a fact; Amendment 2).** Does the writer reproduce `4f5c5a65…` from the real archive? The measurement
  is SPLIT-A25 (a), run once on the workstation.
  - Default: the committed file may first be made from WS1's blob with `source.generator` substituted (§15.6 gives
    the command); SPLIT-A20 ties it to that blob. SPLIT-A25 (a) stays *not checked* until it runs, and the branch
    does not merge before it passes. If it fails, stop and report: the pin is not moved, this document is amended.

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
- DECISION D-11 (amended by the build lane, 2026-10-21): where the record lives → `benchmarks/m06/openidaes450/split.json`,
  W27's adaptation directory, because U14's W27-A71 (R-194, R-467) confines every tracked `benchmarks/` path naming
  `openidaes` to it; the first choice, `benchmarks/c2/openidaes450_split.json`, failed CI run 39688818107. The bytes are
  unchanged. Alternative: a U14 amendment. Reversible by: that amendment and a move with the generator constant.

- DECISION D-12 (Amendment 1, 2026-10-22): a re-taken `coverage.json` → read at its pinned content from git
  history (by blob id); the working copy must keep every row's `case_id`, `family` and `class`; no history means an
  explicit refusal. `case_facts.json` and `sample.json` keep the strict pin. Alternative: re-pin at every re-take, a
  committed frozen copy, or a read-field digest pin (§14). Reversible by: an amendment.

- DECISION D-13 (Amendment 2, 2026-10-23): who writes `case_facts-v2.json` → a C2-owned script,
  `docs/derivations/scripts/c2_openidaes450_facts_v2.py`, reusing W27's reading helpers by import; W27's generator
  stays byte-unchanged. Alternative: WS1's `facts-v2` stage in W27's generator with a W27 re-pin; a stage in C9's
  version 2 generator; a stage in the split generator (§15.2). Reversible by: an amendment moving the writer (the
  file's `source.generator` and its pin move with it).
- DECISION D-14 (Amendment 2, 2026-10-23): how SPLIT-A09 admits it → one exact path added to `ALL_CASE_FILES`;
  `f1.status` becomes `facts_committed`; the generator pins the file and checks it against `case_facts.json`.
  Alternative: a `heldout/` path; a development/held-out pair of files; a pattern entry (§15.3). Reversible by: an
  amendment.

## 13. Register entries

R-486 (the split and its record), R-487 (strata on W27-R02), R-488 (exposure), R-489 (seed), R-490 (protection and
contamination), R-491 (re-split policy), R-492 (R02-F1), R-493 (dynamic and incomplete cases), R-494 (non-claims and
the second-suite requirement). R-555 (Amendment 1: a re-taken pinned input is read at its pinned content).
R-581 (Amendment 2: the F-1 facts writer is C2's own script; W27's generator unchanged), R-582 (Amendment 2:
`case_facts-v2.json` admitted by exact path, pinned and checked; `f1.status` `facts_committed`).

## 14. Amendment 1 (2026-10-22; R-555): a re-taken pinned input

**Trigger.** C7 re-took W27's `coverage.json` at `0.3.0.dev0` (`f85fcd7`), as G14 requires at every version bump
(`docs/C7_DECISIONS.md`). Only `package_version`, `snapshot.git_commit` and `snapshot_sha256` moved. The file's
SHA-256 became `aa89cdd6…` against the pin `b69626c7…`, so the generator refused under SPLIT-R12 and SPLIT-A01, A07 and
A17 failed. Eleven commits have written this file so far. Re-takes recur at every version bump and every merge build.

**Ruling: read the pinned content from history, and check the read fields of the working copy.**
- **Pinned content.** If the working copy of `coverage.json` has the pinned SHA-256, the generator reads it.
  Otherwise it reads git blob `dea968a285c0243b582db19f1ef9fec1c21c2867`. That is the file's content at `0fcf1ad`,
  the content the draw was made from. The bytes must have the pinned SHA-256 (refusal `SPLIT-R01/R12`). The blob id
  only locates the content; the SHA-256 remains the pin.
- **Read-field check.** The working copy's multiset of (`case_id`, `family`, `class`) over `rows` must equal the pinned
  content's. If it does not, the generator refuses with `SPLIT-R12/A1`. The message gives counts only (removed,
  added, changed, duplicate rows) and names no case. That refusal is SPLIT-R12's amendment trigger, and SPLIT-R12's
  removed, changed and added cases apply. Row order is not checked, because the draw does not depend on it: strata
  are keyed and sorted, and candidates are ranked.
- **Unsupported.** If the working copy has moved on and the blob cannot be read (no git, not a repository, a shallow
  clone, an absent object), the generator refuses with `SPLIT-R01/A1`. It never falls back to the working copy. CI
  checks out with full history (`fetch-depth: 0`, `.github/workflows/ci.yml:81,161`).
- **Scope.** Only `coverage.json` is covered. `case_facts.json` and `sample.json` are not re-taken (§6: W27's
  `case_facts.json` is never rewritten), and they keep the strict refusal. Reading a pinned blob of `case_facts.json`
  would also hide the arrival of `topology_units` from SPLIT-R13's fact check.
- **The record is unchanged.** `inputs.coverage.sha256` and `coverage_snapshot` (`48db2d3…`, `211cf4f1…`) describe
  the content the split was drawn from, not the latest re-take. `split.json` is byte-identical: SHA-256
  `ee940a7ee2c6a2128f12fdc25c4e9906ff66607a5ce4e0bb975c00a935adf6cd` (R-486), commitment unchanged.

**Why this candidate.**
- It is the only candidate that keeps the record, its SHA-256 and its provenance fixed through every future re-take.
- It needs no design pass at a version bump. Re-pinning would need an amendment and a register entry at every bump,
  and each one would attest in prose that the read fields are unchanged. The generator here checks it at every run.
- The bytes the draw read stay reproducible and are still checked against the original pin.

**Rejected.**
- *(b) Re-pin at each re-take.* The record (`inputs.coverage.sha256`, `coverage_snapshot`) changes at every bump. Its
  `coverage_snapshot` would then name a build the split was not drawn at. The recurring prose attestation could also
  absorb a real class change unnoticed.
- *(c1) A committed frozen copy of the pinned file.* It duplicates a 2.5 MB all-case file holding held-out rows, which
  SPLIT-R10's allowlist and W27-A71's path rule would both have to admit.
- *(c2) A pin of the read-field projection instead of the file.* It needs no git. But the record reads
  `coverage_snapshot` from the file, so the record would change at every re-take unless the snapshot were frozen as
  constants, and the draw's original bytes would no longer be checked.

**Cost accepted.** A checkout without history cannot regenerate the split once `coverage.json` has moved on. It gets
an explicit refusal.

**Evidence.** Generator `--check` is byte-identical with the working copy at `aa89cdd6…`. SPLIT-A18 and A19 are in
`tests/test_c2_openidaes450_split.py`. A class-changing re-take is open as Q-5 (§11).

## 15. Amendment 2 (2026-10-23; R-581, R-582): the F-1 facts file, its writer and its admission

### 15.1 Trigger and scope

**Trigger.** WS1 (2026-10-22, `docs/C7_DECISIONS.md`, parked branch `wp/WS1-f1` at `7b5c07f`, reachable from `main`)
wrote `case_facts-v2.json` from the real archive with a `facts-v2` stage added to W27's generator
(`docs/derivations/scripts/m06_w27_registration.py`). WS1 reported 450 cases, 3,725 topology units, SHA-256
`57d43acb…`, and every case's kind set equal to its `topology_kinds`. The v1 `facts --check` and the split `--check`
stayed byte-identical. The full gate then failed exactly two registered assertions:
- SPLIT-A09: the file names every held-out id and is neither in `ALL_CASE_FILES` nor under a `heldout` segment;
- W27's P2 (`tests/test_m06_w27_harness.py:314`): the stage changed the generator's SHA-256, which
  `benchmarks/m06/w27/preflight.py` pins (`REGISTERED_SHA256`).

**Scope.** This amendment decides (a) which script writes the file and (b) how SPLIT-R10 admits it. It then sets
`f1.status` and what the generator checks. It changes SPLIT-R10 (a), SPLIT-R13's facts paragraph, SPLIT-R14
(items 13–15) and SPLIT-A12, and it adds SPLIT-A20…A25. It changes nothing in the draw, the held-out set or its
commitment, the development ids, the strata, the contamination list, `coverage.json`, `case_facts.json`, `sample.json`,
v0.2's W27 registration (document, `registration.json`, generator, preflight pins) or C9's W27 version 2.

### 15.2 Ruling (a): the writer is C2's own script

**Script.** `docs/derivations/scripts/c2_openidaes450_facts_v2.py`, run from the repository root as
`python -I docs/derivations/scripts/c2_openidaes450_facts_v2.py --emit | --check [--archive DIR]`. Exactly one of
`--emit` and `--check` is required. `--archive` defaults to W27's `ARCHIVE_DIR`
(`evidence/M06/W27/artifacts/extracted/OpenIDAES-450-demo`). The archive is untrusted data: the script reads
`cases/<id>/topology.json` only, as JSON, and imports or executes nothing from the archive.

**Reuse without edit.** The script loads `docs/derivations/scripts/m06_w27_registration.py` by file path
(`importlib.util.spec_from_file_location`; under `-I` no script directory is on `sys.path`). It uses `_load`,
`dump_facts`, `_sha256_file`, `_write`, `_compare`, `ACCESS_JSON`, `FACTS_JSON`, `PROVENANCE_JSON` and `ARCHIVE_DIR`
from it, and edits nothing in it. That module is SHA-256-pinned by W27's preflight, so it is a stable dependency.
It imports under `python -I` (done at authoring, §15.6).

**Reading rule.** WS1's `extract_facts_v2` at `7b5c07f`, verbatim except for `source.generator`:
- case names are the sorted directory names under `<archive>/cases`;
- for each case, `topo = _load(<archive>/cases/<name>/topology.json)`, replaced by `{}` unless it is a dict;
- its units are the dict entries of `topo.get("units") or []`, each mapped to
  `{"id": str(u.get("id")), "kind": str(u.get("kind"))}` and sorted by `(id, kind)`;
- the document is `{"schema": "openidaes450-case-facts-v2", "source": {"access_report_sha256":
  _sha256_file(ACCESS_JSON), "archive_sha256": provenance.json#/archive/sha256, "case_facts_v1_sha256":
  _sha256_file(FACTS_JSON), "generator": "docs/derivations/scripts/c2_openidaes450_facts_v2.py"}, "cases":
  [{"case_id", "topology_units"}, …]}`, serialized by `dump_facts`.

This is the reading v1's `extract_facts` applies to the same list (`m06_w27_registration.py:1304`) before it records
`topology_kinds` (l.1337).

**Self-claims.** The script refuses to emit or check, with exit 2, writing nothing, and with a message that gives
counts only and names no case, when:
- W1: the archive's case directories are not `access_report.json`'s 450 ids;
- W2: `case_facts.json` does not have its SPLIT-R01 pin `0ca8cffa…`;
- W3: the case-id list differs from `case_facts.json`'s;
- W4: some case's kind set differs from its `topology_kinds`;
- W5: some case repeats a unit id.

**Unsupported is a result.** Without `<archive>/cases`, both modes print
`NOT CHECKED: archive absent at <DIR>; case_facts-v2.json is not verified (run scripts/m06_w27_acquire.py)`, exit 2
and write nothing. No path exits 0 without having compared.

**Output.** `--emit` writes `benchmarks/m06/openidaes450/case_facts-v2.json` and nothing else. The script prints only
`_write`'s and `_compare`'s lines (path and SHA-256) and its refusals. Exit codes: 0 written or identical; 1 differs or
missing (`--check`); 2 refused or not checked.

**Why this candidate.** It moves no pinned file. Every W27 pin and C9's version 2 stay as they are. It keeps the facts
with the rule that needs them (SPLIT-R13 is this registration's). It keeps archive reading (`python -I`) out of the
split generator, which runs with `PYTHONPATH=src` and needs no archive. Its cost is one changed field: the writer's
path in `source.generator`. The cases block is WS1's, bit for bit, and SPLIT-A20 checks that against history.

**Rejected.**
- *(a1) WS1's stage in W27's generator, with a re-pin.* It is the only candidate that keeps `57d43acb…`. But it changes
  `REGISTERED_SHA256[GENERATOR]`, and the preflight's rule is that the re-pin goes in an amendment of
  `M06-W27-registration.md`, which moves the `DOCUMENT` pin too. Frank's L01-Q1 answer is that v0.2's W27 stays
  unchanged. P2 at HEAD would then describe a generator v0.2's campaign did not run. It is not the least change.
- *(a2) A stage in C9's `w27_registration_v2.py`.* That generator holds the next release's W27v2 rules, which do not
  include R02-F1. Its `--check` runs without the archive. A stage there would tie C2's fact to the next release's
  registration and change a file `registration_v2.json` names. Its own `source.generator` would change the bytes too.
- *(a3) A stage in the split generator.* It changes the same field. It would put an archive reader into the file whose
  premise (SPLIT-R01) is that it needs none.

### 15.3 Ruling (b): admission by one exact path

`ALL_CASE_FILES` gains exactly `benchmarks/m06/openidaes450/case_facts-v2.json`, which makes thirteen exact paths
(SPLIT-R10 (a), amended). There is no pattern and no directory.

**Narrowness.** One exact path, like each existing entry. The file holds every case id by construction. SPLIT-A23
asserts that it holds exactly the held-out count of held-out ids, so the entry is needed and stands for nothing else.
SPLIT-A09 still scans every other tracked file.

**Protection unchanged.** Development reads the file only through SPLIT-R10's development filter (§11 Q-3). SPLIT-R09
applies: nothing computes unit or kind frequencies over its held-out rows. The writer and the split generator read
every row in memory and print no case id.

**Rejected.**
- *(b1) A path under a `heldout/` segment.* It needs no allowlist change. But SPLIT-R10 (b) is for release-gate outputs
  of held-out rows. This file holds the development facts that development work needs, and §6 placed it next to W27's
  `case_facts.json`.
- *(b2) A development file and a held-out file.* That is two pins and WS1's bytes lost. Release-gate R02-F1 needs both
  halves anyway, and the filter rule already governs every file of (a).
- *(b3) A pattern entry (`case_facts*.json`).* It would admit future files that nobody registered.

### 15.4 The record's `f1` block, and what `--check` verifies

**Status.** `f1.status` becomes `facts_committed`. That means the facts SPLIT-R13 needs are committed, pinned and
consistent with `case_facts.json`. R02-F1 is still applied to no case beyond the two registered states: the split
makes no classification. `lacking` is removed. The block becomes:

```json
"f1": {
  "boundary_kinds": ["Feed", "Product"],
  "facts": {
    "path": "benchmarks/m06/openidaes450/case_facts-v2.json",
    "schema": "openidaes450-case-facts-v2",
    "sha256": "4f5c5a65fe1b310e04b7e311464e4d87ba90ed4bfa7a90c240cde397cd0114ef",
    "writer": "docs/derivations/scripts/c2_openidaes450_facts_v2.py"
  },
  "kind_level_states": {"blind_synthesized_hda_flash": [], "official_idaes_skeleton_pervaporation": ["SkeletonUnitModel"]},
  "rule": "SPLIT-R13 (R02-F1)",
  "status": "facts_committed",
  "unit_level_states": {
    "blind_synthesized_hda_flash": {},
    "official_idaes_skeleton_pervaporation": {"topology:SkeletonUnitModel": ["pervap"]}
  }
}
```

Every other member of the record is unchanged. The rendered record (the generator's `render`) has SHA-256
`a556e417a8063dbf06242890667e7f5bd4056128cea552c49a81bf40c9cd755c` (25,115 bytes; §15.6).

**Generator.** The pin is a new constant `F1_FACTS = (path, "4f5c5a65…")`, with `F1_SCHEMA`, `F1_WRITER` and
`F1_UNIT_STATES`. It is not in `INPUTS`: the draw's inputs stay three. The file is read from the working copy under a
strict pin with no history fallback, because only an amendment re-takes it. The F-1 checks run in this order:
item 8, then 13, 14 and 15. Item 8 stays first so that SPLIT-A12's negative control reaches it. Item 14 must be
callable below the pin so that SPLIT-A21 and A22 reach it; the build lane chooses the mechanism.

- **Item 13.** The file is absent, or its SHA-256 is not `F1_FACTS`'s: `SPLIT-R13/A2`.
- **Item 14.** Identities with `case_facts.json`, checked in this order, each with a label. A failure raises
  `SPLIT-R13/A2 <label>: <n> case(s)` and names no case.
  1. `binding`: `schema` = `openidaes450-case-facts-v2`; `source` has exactly the four keys;
     `source.case_facts_v1_sha256` = the SPLIT-R01 pin; `source.archive_sha256` = `case_facts.json#/source/archive_sha256`;
     `source.generator` = the writer's path.
  2. `case_ids`: the list of `case_id` equals `case_facts.json`'s list, in order.
  3. `case_keys`: every case has exactly the keys `case_id` and `topology_units`.
  4. `unit_form`: every unit is an object with exactly the keys `id` and `kind`, both strings.
  5. `unit_order`: every case's list equals its copy sorted by `(id, kind)`. Ties pass here and are caught by 6.
  6. `unit_ids`: no case repeats an id.
  7. `kind_sets`: every case's set of kinds equals its `topology_kinds`.
- **Item 15.** For each case *c* of `F1_STATES`, *covered(c)* is as in §6, from `case_facts.json`'s `units`. The added
  kinds are (*c*'s kinds in `case_facts-v2.json`) − `BOUNDARY_KINDS` − *covered(c)*. Each added kind *k* gives
  `"topology:<k>"` → the ids of *c*'s units of kind *k*, in file order. The generator refuses (`SPLIT-R13`) unless the
  added kinds equal the kind-level state (from `topology_kinds`) and the groups equal `F1_UNIT_STATES[c]`. The groups are
  recorded as `unit_level_states`.

### 15.5 Assertions

SPLIT-A12 is amended, and SPLIT-A20…A25 are added (§9's table), in `tests/test_c2_openidaes450_split.py`. All are
exact. SPLIT-A25 (a) is gated on the archive with the convention W27's tests use (`ARCHIVE_PRESENT`); its skip is
reported as not checked.

### 15.6 Expected values and their derivation

| Quantity | Value | Source |
| --- | --- | --- |
| WS1's file, blob `7b0686e195ae6685fa1b0738a3dbbd674d21cc02` | SHA-256 `57d43acbee1c0952e43c0a5410783fd0dba8c1a4b4e38a74e31f8b57cbb33494`, 170,683 bytes | WS1's archive run (`7b5c07f`) |
| `case_facts-v2.json` as C2's writer emits it | SHA-256 `4f5c5a65fe1b310e04b7e311464e4d87ba90ed4bfa7a90c240cde397cd0114ef`, 170,687 bytes, 452 lines | WS1's file with `source.generator` substituted, re-serialized by `dump_facts` |
| Both files after the first `\n` (the cases block) | SHA-256 `fb0e0fe31c6cd42d294e916ff87fd0038af03406d7ff6474dcd3930a5645724d`, 170,284 bytes | identical in both |
| `split.json` before, blob `17632cea3ac9e3ebe23076bade2fc6bf9c29948c` | SHA-256 `ee940a7ee2c6a2128f12fdc25c4e9906ff66607a5ce4e0bb975c00a935adf6cd`, 24,705 bytes | R-486 |
| `split.json` after | SHA-256 `a556e417a8063dbf06242890667e7f5bd4056128cea552c49a81bf40c9cd755c`, 25,115 bytes | the record before with `f1` replaced by §15.4's block |

Both derivations were run at authoring from the repository root and print the digests above:

```
python -I - <<'PY'
import hashlib, importlib.util, json, subprocess
w = importlib.util.spec_from_file_location("w27", "docs/derivations/scripts/m06_w27_registration.py")
m = importlib.util.module_from_spec(w); w.loader.exec_module(m)
old = subprocess.run(["git", "cat-file", "blob", "7b0686e195ae6685fa1b0738a3dbbd674d21cc02"],
                     capture_output=True, check=True).stdout
d = json.loads(old); assert m.dump_facts(d) == old
d["source"]["generator"] = "docs/derivations/scripts/c2_openidaes450_facts_v2.py"
new = m.dump_facts(d)
print(*(hashlib.sha256(b).hexdigest() for b in (old, new, new.split(b"\n", 1)[1])))
PY
```

The second derivation reads blob `17632cea…`, sets `f1` to §15.4's block (with `kind_level_states` carried over), and
renders it with `json.dumps(record, sort_keys=True, indent=2, ensure_ascii=False) + "\n"`.

**Measured at authoring.** WS1's file round-trips through `dump_facts`, and its `source.access_report_sha256` equals
HEAD's `access_report.json`. On the substituted file, item 14's seven identities hold; item 15 gives the registered
states; each SPLIT-A21 edit is refused with its registered label; and the `pervap2` edit of SPLIT-A22 passes item 14
and fails item 15. The file holds 224 held-out ids, and the first development case has four units. Items 14 and 15
and SPLIT-A20…A23 make these executable. The `access_report.json` binding is checked by the writer's `--check`.

### 15.7 What moves, and what does not

**Moves.**
- `ALL_CASE_FILES` gains one entry.
- The split generator gains the pins, items 13–15 and the new `f1` block.
- `split.json` changes in `f1` only (`ee940a7e…` → `a556e417…`).
- New: the writer, `case_facts-v2.json`, and the test changes (A12 amended, A20–A25 added).
- `docs/derivations/scripts/l01_projection.json#/inputs` keeps `split.json` at `ee940a7e…`. L01 read only
  `development.case_ids`, which do not change. No test or CI step runs `l01_projection.py --check` (grep at
  authoring), and its recorded `coverage.json` digest already differs from HEAD after C7's re-take. Re-emitting it is
  L01's business, not this amendment's.

**Does not move.** v0.2's W27 files and `preflight.REGISTERED_SHA256` (SPLIT-A24); `coverage.json`;
`case_facts.json`; `sample.json`; the held-out set and its commitment; the development ids; the strata;
`contaminated`; C9's version 2 files.

### 15.8 Work order WO-C2-A2 (build lane, `opus-engineer`; branch from `main`)

1. Do not re-apply `7b5c07f` (it edits W27's generator). Lift its `extract_facts_v2` and the facts branch of `main`
   into `docs/derivations/scripts/c2_openidaes450_facts_v2.py`, per §15.2 (import by path, W1–W5, `NOT CHECKED`).
2. Workstation: `python -I … --emit` from the archive must give SHA-256 `4f5c5a65…`. If it does not, stop and report
   (Q-6); do not re-pin. Without the archive, write the file by §15.6's command; A25 (a) stays not checked.
3. `c2_openidaes450_split.py`: add the path to `ALL_CASE_FILES`; add `F1_FACTS`, `F1_SCHEMA`, `F1_WRITER`,
   `F1_UNIT_STATES`; add items 13–15 after item 8 (item 14 reachable below the pin); write §15.4's `f1` block.
4. `--emit` the split: `split.json` SHA-256 must be `a556e417…`, and `--check` must exit 0.
5. `tests/test_c2_openidaes450_split.py`: amend A12; add A20–A25 as §9 states them (A22 and A23 share no generator code).
6. Run the C2 tests, `test_m06_w27_harness.py` (P2 with the archive), `test_c9_w27_v2.py`, `test_l01_records.py`,
   ruff and mypy. W27's v1 `facts --check` must stay byte-identical.
7. Log the commands and digests in `docs/C2_DECISIONS.md`, and mark WS1 item 4 unblocked in `docs/C7_DECISIONS.md`.
   Status `tested` only. The branch merges after A25 (a) passes and the design-lane review.
