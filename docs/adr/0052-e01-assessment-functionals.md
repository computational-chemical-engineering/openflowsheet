# ADR 0052 — Cost and life-cycle impact as differentiable assessment functionals outside the compiled problem (package E01)

**Status:** **Proposed, 2026-10-27** (design lane, `architect`; register R-850…R-862). It becomes **Accepted** when:
- E01's evidence manifest is `tested`, with gates G1–G9 of the design note passing;
- the `reviewer` has passed tracks A and B and the integration WO against the design note.

**Date:** 2026-10-27
**Author:** design lane (`architect`), brief `docs/briefs/E01-cost-lca-design.md`.
**Normative text:** `docs/derivations/E01-design.md`.
**Amends:**
- the frozen schema list (`docs/interfaces-frozen.md` §2): two new schemas; one optional property each in
  `study.schema.json` and `optimization-report.schema.json`;
- ADR 0032 D1, for the NLP adapter only: the gray box may carry outputs (assessment functionals and their
  admissibility rows). A new verification check V7 is added to D3.

No `Protocol`, quantity kind, check category or tolerance changes. No registered result moves.

**Affected requirements:** blueprint §10 ("TEA/LCA remain assessment adapters with currency year, location, factors,
uncertainty, and provenance"), [A06] (the NLP bridge), D01 (reuse established libraries), D04 (licensing and data
rights), D14 (assessment evidence distinct from verification and validation).
**Affected packages:** E01 implements it. M03 (ADR 0031, 0032) is extended additively. M05 (ADR 0038) is unchanged,
and assessment objectives there are refused. The PrISMa package consumes it.

## Context

Frank (2026-10-27): "I want cost estimation and LCA available, because these are input in process optimization
studies."

Cost and impact must be usable as objectives and constraints with exact derivatives. They must carry provenance and an
accuracy statement. They must not disturb the simulation, its certificate or its replay identity.

## Decision

**D1. Post-solve functionals.** Every cost, size and impact quantity is an explicit function `y = G(x, d; θ, ρ)` of a
verified state `x`, the pinned inputs and decisions `d`, the assessment parameters `θ` and a held regime `ρ`. It is
never a row or variable of a `CompiledProblem`.
- In the M03 NLP, `y` enters as PyNumero gray-box outputs with the exact Jacobian `∂G/∂(x, d)`.
- In reduced space, `dJ/dp = ∂J/∂p + ∇ₓJ·X` with M03's factorization (forward or adjoint).

**D2. One source, the existing compiler.** Functionals are `RowBuilder`s against `Algebra`. A set of them compiles as a
`ProblemSpec` whose rows are the outputs, through the unchanged `ParametricTwin`. `compile/reference.py` is the float
reference. Nothing under `compile/` changes, and the functional spec is never solved or certified.

**D3. Regimes, never smoothing.** Parallel units, minimum size, correlation pieces, service, utility, controlling stage
and controlling dimension are held regimes with admissibility inequalities. A selection rule picks them at a state; a
study holds them. Inside its admissible set each regime is the exact cost of a realisable design. `max`, `min`, `abs`,
`ceil` and smoothing are excluded from functionals. Zero-flow regimes are verified at the candidate (V7).

**D4. ΔT_lm by Underwood's cube-root mean.** Deviation from the exact log mean: +0.38 % at ratio 10, +2.56 % at 50,
exact at ratio 1. It is reported per exchanger.

**D5. Forms in code, coefficients in data.**
- Shipped coefficients: `sslw-idaes-v1` (Seider et al. 3rd ed., transcribed from IDAES-PSE's BSD-licensed `SSLW.py`,
  notice retained, a `source_line` per number).
- `power-law-v1` carries user data and quotes. A quote overrides one item.
- Turton is not shipped.

**D6. Public indices.** Shipped: BLS PPI WPU11, Eurostat PPI NACE C28 (euro area) and Federal Reserve G.5A exchange
rates. CEPCI values are never shipped, but users may supply them. Escalation is in the source currency, then conversion
at the target year's annual rate, then the location factor.

**D7. LCA as a frozen linear map.** `h = Q·a(x) + C·b(x)`.
- `Q` (unit scores) and `C` (direct factors) are hash-pinned tables.
- The Brightway adapter (optional extra `lca`: `bw2data`, `bw2calc`) builds them offline from the user's project.
- Brightway never runs in a solve, an optimization or a replay.

**D8. Data rights.**
- Shipped: IPCC AR6 GWP100 direct factors; a synthetic test background; a USLCI GWP100 table only if its CC0/US
  public-domain licence is recorded.
- Not shipped: EF 3.1 factors (the JRC130796 report is CC BY 4.0, but the workbook's terms are unconfirmed and it needs
  flow mapping); anything derived from ecoinvent.
- A table with `redistribution: forbidden` appears in reports, bundles and fixtures by id and sha256 only.

**D9. Study naming and schemas.**
- Studies name `assessment:<output_id>` in NLP objectives and constraints and in sensitivity outputs.
- New: `schemas/assessment.schema.json` and `schemas/assessment-report.schema.json`.
- Optional `assessment` property in `study.schema.json` (top level) and `optimization-report.schema.json`
  (`formulation`).

**D10. Scope cuts with typed refusals.**
- Trust-region assessment objectives: `UNSUPPORTED(ASSESSMENT_OUTPUT_IN_TRF)`.
- Assessment parameters as decisions: `UNSUPPORTED(ASSESSMENT_PARAMETER_DECISION)`.
- Not in E01: the NLP host over revision flowsheets and the CLI/HTTP/MCP bindings.

**Evidence class.** Every assessment report states its AACE class and range, a first-order uncertainty, its defaulted
inputs, its limitations and the sentence: "Assessment evidence … not numerical verification … not empirical
validation." Totals that depend on an unsupported, unexcluded item are `null`.

## Rejected alternatives

- *Cost and impact as rows in F.* It changes the identity and the certificate scope of every assessed flowsheet. Cost
  domain errors would fail simulations, regimes would break regularity, and re-costing would need a re-solve.
- *Appending `y − G = 0` to the twin's equality set.* The equality set would then diverge from the simulation's kept
  rows that V2 and V5 compare.
- *FD gradients* (R-010).
- *IDAES, BioSTEAM or OpenPyTEA as dependencies.* A second hand-authored flowsheet model (A06, R-003), or functions
  that are not algebra-generic.
- *Smoothing.* It biases the value and gives gradients of a function that is not the cost.
- *The epigraph reformulation.* It needs proof of monotonicity per study.
- *The exact LMTD as an opaque block.* It adds a black box, which would become a TR `ExternalFunction`.
- *Brightway in the loop.* `A⁻¹` is constant, and Brightway would become a runtime dependency.
- *Shipping CEPCI, Turton, EF 3.1 or ecoinvent-derived data.* Their rights are not established.

## Migration impact

None for existing documents, runs, certificates, bundles or fixtures. The M03 adapter is bit-identical when no
assessment output is named. Tests that pin bytes of the two edited schemas or of `pyproject.toml`, if any, are amended
on purpose, citing this ADR.

## Acceptance evidence

Design note §6:
- identity: G1, G9;
- the functional core and derivative oracle: G2;
- hand-calculated and IDAES-independent cost expectations: G3, G4;
- synthetic-background hand values and an independent Brightway foreground calculation: G5;
- sensitivities against FD of certified re-solves, and an M03 NLP with a TAC objective verified V1–V7: G6;
- schemas, rights and D04 inventory: G7;
- the full gate and CI on both architectures: G8.
