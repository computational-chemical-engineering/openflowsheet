# OpenIDAES-450 development / held-out split — registration (design lane, `specifier`)

**Requested by Frank, 2026-10-18.** Run at the 0.2.0 cut, after M07 merges into main and **before any scope that
targets OpenIDAES coverage is decided**. No spend. v0.2's W27 stays exactly as registered.

## The question
Register a seeded split of OpenIDAES-450 into a development set and a held-out set, and the rules that keep the
held-out set out of development, so that later coverage and agent scores can show generalisation rather than fit.

## Settled (Frank, 2026-10-18)
- Split before any OpenIDAES-targeted development; the held-out half is scored only at release gates, reported
  separately, with the development/held-out gap.
- Development half drives gap analysis, unit/property selection and agent prompt/tool tuning. Feature choices cite
  development cases or a general library goal, never held-out cases.
- Cases exposed by v0.2's W27 campaign (its 45 drawn cases; transcripts public) count as development cases.

## Facts
- Coverage `benchmarks/m06/openidaes450/coverage.json` (snapshot `2f35e9b`): 450 = 367 UNIT_UNAVAILABLE,
  65 NOT_STEADY_STATE_SIMULATION, 17 COMPONENT_UNAVAILABLE, 1 ARTIFACT_INCOMPLETE; 0 CANDIDATE. 384 steady and complete.
  Families: idaes 188, watertap 158, prommis 25, gtep 21, reflo 19, mvo 18, dispatches 11, reaktoro 6, pareto 4.
- Disclosure: on 2026-10-18 the session computed gap frequencies (missing units, components, property methods) over
  all 450 cases (in chat, not committed). No development used them.
- W27 registration `docs/derivations/M06-W27-registration.md` §6 (seeded draw), §16 (non-claims).

## Open (decide, with reasons)
Split ratio (default ~50/50); stratification (default family × blocking class); seed source fixed before the draw;
treatment of dynamic and incomplete cases; how the held-out set is protected (public data: a recorded rule, e.g.
held-out case ids not read by development agents, plus a hash commitment); re-split policy if the archive changes;
the non-claim that both halves share the same 9 families (an independent second suite is needed for broader claims).

## Deliverable
A registration document under `docs/derivations/`, a generator with `--check` writing the split JSON, register
entries, and assertions for a build-lane test. ≤ 200-word report.

## Session brief (cloud, 2026-10-21; package C2, branch `wp/C2`)

Added by the build lane for the cloud run. Frank's settled rules above are unchanged.

**Facts with anchors** (all committed; the archive is absent in a cloud session and must not be fetched)
- `benchmarks/m06/openidaes450/case_facts.json` (schema `w27-case-facts-v1`, 450 cases): each case has
  `family`, `units` (each with `key`, `names`, and `topology_kind` when its short name matches a topology id),
  `unit_source` (`units.json` | `topology.json` | `none`), `topology_kinds` (all kinds incl. Feed/Product),
  `steady_state`, `solve_dynamic`, `files_missing`, `in_full82`. Producer: `facts` stage of
  `docs/derivations/scripts/m06_w27_registration.py` (needs the archive; `_unit_facts` at :1085-1123 is W27-R02).
- The R02 rule text: `docs/derivations/M06-W27-registration.md:109-116`. Seeded SHA-256 draw idiom (no RNG):
  same file §6, `:327-358` (W27-R26…R31); implementation `benchmarks/m06/w27/sample.py:27-140`.
- Runtime classifier: `benchmarks/m06/w27/coverage.py` (`unit_aliases` :60, `_unit_reasons` :245,
  `classify_case` :445, `coverage_document` :531). Committed coverage `benchmarks/m06/openidaes450/coverage.json`
  (schema `w27-coverage-v1`, 450 rows, `class`, `family`, `reasons`).
- W27's exposed cases: `benchmarks/m06/openidaes450/runs/w27-m07-83f825d/sample.json` (`cases`, 45) and its
  three canaries (`canaries`). Frank: these count as development.
- R-474 (`docs/decision-register.md:9792-9830`) and M07 spec §22.4 (`docs/derivations/M07-spec.md:1545-1567`):
  F-1's recommended default (topology units whose kind no `units.json` entry has; marked; W27-A08 keeps exactly one
  unit reason; the split states which R02 its strata use).
- Register numbering for this package: **R-486…R-494** (other cloud packages hold later ranges).

**Exit test**
1. A registration under `docs/derivations/` (split rules, F-1/R02 rule, protection rule, re-split policy, non-claims,
   numbered assertions).
2. A generator under `docs/derivations/scripts/` with `--emit`/`--check`, needing no archive and no network, writing
   the split JSON under `benchmarks/` from committed files only; `--check` byte-identical.
3. Register entries R-486… appended to `docs/decision-register.md`.
4. Assertions for a build-lane test listed with ids (the build lane writes the test; the agent may write it too if
   it is pure file checks).
5. If the F-1 rule needs a fact `case_facts.json` lacks, say exactly which, register the rule for the workstation's
   next `facts` run, and choose (DECISION line) how the split's strata treat R02 meanwhile. Do not block the split.

**Out of scope.** Downloading or reading the archive; computing or recording gap frequencies (units, components,
property methods) over held-out cases; changing W27's registration or `coverage.json`; any v0.3 scope.

**Agent rules.** Context cap about 120k; at the cap commit, write a handoff of ≤ 30 lines to
`docs/briefs/C2-handoff.md`, stop. Report ≤ 150 words. Choices you can defend: one `DECISION:` line each, logged
in `docs/C2_DECISIONS.md`. Questions only Frank can answer: `docs/FRANK_QUESTIONS.md`, with your default.
