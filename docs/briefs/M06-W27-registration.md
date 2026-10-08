# Brief — M06 WO-15: the W27 registration (OpenIDAES-450 adaptation)

**To:** `specifier` (design lane). **From:** the session (build lane), 2026-10-08. **Branch:** `wp/M06-w27`.
**Gate:** W27 ("external agent benchmark adaptation attempted; inaccessible assets disclosed"). The registration
has to exist, committed, **before any agent run** (blueprint §11.4; design note §9 Tier 1).

## 1. The question

Write `docs/derivations/M06-W27-registration.md` (plus a machine-readable companion under
`benchmarks/m06/openidaes450/`), pre-registering everything WO-16 implements and WO-17 runs. That means:
- the three semantic maps:
  - IDAES unit class → OpenFlowsheet model, or unavailable;
  - component availability;
  - property-route availability;
- the class precedence and reason rules for the coverage classifier;
- the stratified sample (seed, strata, allocation);
- the prompt template and footer;
- the final-answer schema;
- the per-run scoring rules with their tolerances;
- the reported quantities with their bounds;
- the claims and non-claims.

A `verdict` agent must be able to judge W27 later from the campaign record and this document alone.

## 2. Why the design lane

The design note says so: the maps are semantic judgements (§9 Tier 0 item 3). Scoring "false verification" and
"wrong limitation" decides what the benchmark claims. Registration before data is what keeps the campaign honest.

## 3. Inputs (read these)

- `docs/design/M06-web-shell.md` §9 (W27, whole; the G13 row was amended on this branch at `4ee514d`), §11 rows
  G13–G16, §13 (non-claims).
- `benchmarks/m06/openidaes450/provenance.json` and `access_report.json` (`e268ed8`).
  - The archive is pinned: 220 802 919 bytes, SHA-256 `6d42c02f…4526`, extracted under the git-ignored
    `evidence/M06/W27/artifacts/`. Regenerate it with `scripts/m06_w27_acquire.py` if absent.
  - Counts reproduce the audit: 450 cases; 425 pass / 24 fail / 1 absent; full82 = 82 (WaterTAP 41, IDAES 20,
    PrOMMiS 20, DISPATCHES 1).
  - Families: IDAES 188, WaterTAP 158, PrOMMiS 25, grid 21, REFLO 19, MVO 18, DISPATCHES 11, Reaktoro 6,
    PARETO 4.
  - Model types: native IDAES 237, original reduced 163, new reduced demo 11, grid opt. 21, design opt. 17,
    dynamic 1.
  - Ten inaccessible assets, all absent.
- The audit: `git show study/openidaes450:docs/openidaes450-audit.md`.
- Blueprint §11.4 (`docs/blueprint-v3.1.md` ~L477): adapted subsets report coverage and never inherit the headline
  score; report completion, false verification, unauthorized actions, semantic error rate and cost separately.
- The V17 precedent you are adapting:
  - `docs/derivations/T07-v17-tasks-spec.md`;
  - the harness, scorer and preflight in `benchmarks/t07/v17/` (`harness.py`, `scorer.py`, `preflight.py`);
  - V17's open finding: `run.json` lacked the lock hash and the interpreter environment.
- OpenFlowsheet's model registry today: the `list_models` operation (`openflowsheet` CLI or
  `application/local.py`). Also the unit models in `src/openflowsheet/units/` and the component records. At 0.1.x
  the components are SYN-001's only; M01 adds H₂, N₂, NH₃, Ar, CH₄ and a Peng–Robinson route in v0.2 (in
  progress on `wp/M01`).

## 4. Already decided, not open

- **Spend is approved** (Frank, 2026-10-08): Tier 1 default, 45 runs, about USD 15–45, preceded by 3 canaries;
  k = 1.
- **Agent model** (Frank, 2026-10-06, M06 F2):
  - use the most recent model available at campaign time, pinned by exact model ID and recorded;
  - this is not V17's `claude-sonnet-5`;
  - state in the registration that direct comparability with `v17-c2` is lost;
  - the rest of `v17-c2`'s configuration stands unless you argue otherwise: effort high, `--max-turns 60`,
    1800 s wall, USD 5 guard, MCP tools only, operator isolation, pinned Claude Code version.
- **The run outcome classes, as §9 lists them:** `CORRECT_BUILD | CORRECT_LIMITATION | WRONG_LIMITATION |
  WRONG_BUILD | AGENT_FALSE_VERIFICATION | SYSTEM_FALSE_VERIFICATION | INFRASTRUCTURE_FAILURE`.
- **System false verification must be 0;** a non-zero count is a defect report.
- **The precedence order:** `ARTIFACT_INCOMPLETE > NOT_STEADY_STATE_SIMULATION > UNIT_UNAVAILABLE > COMPONENT_UNAVAILABLE
  > PROPERTY_ROUTE_UNAVAILABLE > CANDIDATE`, with every applicable reason recorded.
- **When it runs:** Tier 0 is re-run at M07 against the v0.2 candidate, and the campaign runs there too. Write the
  maps so they are re-evaluated mechanically against the registry at that time. Do not hard-code today's
  registry; register the rule, and the registry document's SHA-256 is recorded per evaluation.
- **No headline score,** and no comparison with CRAFTS's success rates.

## 5. Genuinely open — decide these

1. **The maps.** How an IDAES unit class maps to an OpenFlowsheet model, including the rule for partial matches
   (for example, an IDAES Flash with an energy option the OpenFlowsheet unit lacks). How a component is judged
   available. How a property package is judged available. Where the case data are insufficient: the property
   package class is often only in `sources/`, so give an explicit rule rather than a guess.
2. **The sample:**
   - seeded stratification;
   - all `CANDIDATE` cases first;
   - the largest-remainder allocation with at least one per family of ≥ 4 cases;
   - what happens if there are more than 45 `CANDIDATE` cases, or none;
   - whether the 24 residual-check failures are excluded or flagged.
3. **The prompt.** The template and the footer. The untrusted-data envelope. The final-answer schema
   `{status, revision_id, job_id, limitation, claims}`, made precise.
4. **Scoring:**
   - what a "correct limitation" is (the typed limitation must match the registered coverage reason — define the
     equivalence);
   - stream-value tolerances against `streams.csv` for `CANDIDATE` builds;
   - how unauthorized effects are read from `list_audit` (ADR 0019 Amendment 3, approved) and the store export;
   - how infrastructure failures are counted.
5. **Reporting:** one-sided 95% Clopper–Pearson bounds, which terms are gated and which are only reported, and
   the cost.

## 6. Deliverable

- `docs/derivations/M06-W27-registration.md`, with numbered, falsifiable registration items.
- `benchmarks/m06/openidaes450/registration.json`, holding the maps, sample seed, strata, tolerances and schema,
  in machine-readable form.
- If you can compute it now, the sample itself drawn against today's coverage as a dry illustration, clearly
  marked "not the campaign sample". The campaign sample is drawn at M07.
- A "Work orders for WO-16" section.
- Any decision-register entries: take **R-176…R-179**.

Commit on `wp/M06-w27`.

## 7. Out of scope

Implementing the classifier, harness or scorer (WO-16). Running anything that costs money. The web shell. Any
change to the application contract.
