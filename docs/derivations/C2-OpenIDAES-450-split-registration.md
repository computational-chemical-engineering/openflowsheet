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
| W27 coverage (W27-R02 basis) | `benchmarks/m06/openidaes450/coverage.json` | `b69626c7e908218e70f8726534a00c964674b2cbda7f582c8650ed939e48e3ba` | `rows[].case_id`, `rows[].family`, `rows[].class` |
| W27 case facts | `benchmarks/m06/openidaes450/case_facts.json` | `0ca8cffa146865971dd2a2d445b699cf484965cc052f7f37d8f6554c669e38f7` | `cases[].case_id`; and for SPLIT-A13 only `unit_source`, `units[].key`, `units[].topology_kind`, `topology_kinds` of the two cases named there; the key set of every case (SPLIT-R13's fact check) |
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
generator. Its completeness at `f397467` is checked by SPLIT-A09, which finds no held-out id in any committed file
outside the allowlist.

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

**SPLIT-R07 (the record).** The generator writes `benchmarks/openidaes450_split/split.json` (schema
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
(a) the file is one of the twelve pre-split all-case data files listed in the generator (`ALL_CASE_FILES`): the six
under `benchmarks/m06/openidaes450/` that hold every case, `runs/w27-m07-83f825d/coverage.json`, and M07's six
`rc/step17/{at-c,at-cw,coverage-at-C}.json.gz`; or
(b) the file's path has a directory segment named `heldout`. Release-gate outputs that carry held-out rows go there.

Development agents do not open the files of (a) or (b) except through a filter that drops non-development rows. The
build lane provides that filter (§11 Q-3). Until it exists, development reads only `split.json`, `sample.json`, the
W27 run directories and the development rows that a script prints after filtering by `split.json#/development`.

Mechanical consumers compute the held-out list in memory: the generator, the SPLIT-A09 test, and release-gate
scorers. They never print a held-out id. A failure message identifies a held-out id by the first 12 hex digits of
`sha256(id)`.

**SPLIT-R11 (contamination).** If a held-out case is exposed after the split, the split is not redrawn and the case
is not moved. Exposure means it is named outside SPLIT-R10's allowlist, or a development agent reads its content.
The case is recorded in `split.json#/contaminated` as `sha256(id)` (hex) with the date and the cause, by an amendment
to this registration and a register entry. It stays held-out, is scored at release gates, and is reported in a
separate line, outside the held-out headline. Deleting the mention to make SPLIT-A09 pass is not a remedy. The
contamination is recorded, and SPLIT-A09 then tolerates that id. Today the list is empty.

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

Until then `split.json#/f1/status` is `"awaiting_facts"`. The generator verifies the status: it refuses if any case
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
memory and compares the result byte for byte with the committed `split.json`. The generator refuses to emit, with
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
9. the record would contain a held-out id, or any key named `reasons`, `units`, `components` or `packages`.
