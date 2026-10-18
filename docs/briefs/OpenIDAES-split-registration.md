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
