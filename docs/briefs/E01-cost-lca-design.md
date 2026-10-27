# E01 brief: cost estimation and life-cycle assessment as general, differentiable capabilities (design lane, `architect`)

Branch `wp/E01`, worktree `.claude/worktrees/e01`, from `main` `5c8f6006`. S11 (the binding package: water/IAPWS-95,
CoolProp pure fluids, Wilson γ–φ selectable in flowsheets; `thermal.*` heater/valve/mixer/flash/pump/compressor/turbine; the
distillation column as a flowsheet unit) is being finished on `wp/S11` and will merge before E01 is built. Design against
`main` plus S11's design notes (`wp/S11`: `docs/derivations/S11-design.md`, `S11-units-design.md`; read them with
`git show wp/S11:<path>` — do not edit that branch).

## 1. The question

**Frank, 2026-10-27:** "I want cost estimation and LCA available, because these are input in process optimization studies."
Design the package that makes capital/operating cost and life-cycle impact first-class quantities of a flowsheet, so that an
optimization study can use them as objective or constraint, with the ADR(s) it needs and work orders for two engineers in
parallel (disjoint files), tested once at the end (Frank: batch, then test once).

What must come back: where cost and impact live (model quantities with rows/derivatives in the compiled problem, versus
post-solve functionals with adjoint/sensitivity derivatives — decide, with the trade-off for the existing NLP bridge and the
trust-region framework); how equipment sizing is derived from the solved state (exchanger area from duty and ΔT_lm with a
stated U, column diameter/height from flows and stages, compressor/pump/turbine from power, vessels from residence time) and
which sizing inputs are user parameters; the cost-provider interface (registered correlation sets; a user quote overriding one
item; provenance: currency, year, location, cost index, source, AACE accuracy class, uncertainty range); the cost index
(public, e.g. US PPI series; CEPCI is magazine-owned — do not ship its values by default); operating cost (utilities, raw
materials, labour/maintenance factors) and the annualisation (CRF, discount rate, lifetime); the LCA interface (inventory per
unit of each stream/utility crossing the boundary; impact = characterisation × inventory; linear, exact derivatives; Brightway
as the engine behind an adapter; a pluggable background database: free data shipped, ecoinvent via the user's licence, never
redistributed; EF 3.x characterisation factors — verify their licence); how non-smooth parts (minimum sizes, number of
parallel units, material of construction, correlation validity ranges) are represented without lying to a gradient optimizer
(typed limitations, smooth admissible region, or discrete study variables); the verification (hand calculations and an
independent Brightway calculation as registered expectations; no self-generated output as validation); numbered assertions;
the identity statement (nothing registered moves).

## 2. Why it needs the architect

It adds a new kind of provider and new quantities that cross the flowsheet, the compiled problem, the verifier/certificate and
the optimization bridge; it likely touches frozen interfaces (`docs/interfaces-frozen.md`: Study, OptimizationReport schemas,
M01–M04 row) and the dependency/licence inventory (Brightway, data files). A wrong shape is expensive to undo.

## 3. Current state (read these, narrowly)

- Blueprint `docs/blueprint-v3.1.md`: line ~125 (Study: objectives, constraints), ~425 (process adjoints), ~435–447 (NLP
  bridge; gray-box adapter [A06]; trust-region; "TEA/LCA remain assessment adapters with currency year, location, factors,
  uncertainty, and provenance"), D13, D14.
- Optimization code: `src/openflowsheet/studies/` — `study.py`, `nlp/{formulation,verification,closure,greybox}.py` (M03 spec
  §8, ADR 0032: the NLP bridge; optimizer only with the `nlp` extra), `trust_region/` (M04 spec), `sensitivity.py`.
- Specs: `docs/derivations/M04-spec.md`; M03's spec and ADRs 0031/0032; `docs/interfaces-frozen.md` (§ M01–M04 row and the
  M03 schema note near line 90).
- Prior survey (Frank's question, 2026-10-27): open cost correlation sets — Turton (CAPCOST), Seider/Seader/Lewin/Widagdo,
  Towler & Sinnott, Woods (bare-module), NETL QGESS and baseline reports (capture plants, CO₂ compression); open
  implementations — IDAES costing (BSD; SSLW + NETL power-plant costing), BioSTEAM TEA (`.venv-biosteam` exists in worktree
  `s09`), OpenPyTEA (MIT, SoftwareX 2026), ECO-ANA, carbatpy. LCA — Brightway 2.5 / Activity Browser, openLCA; free LCI: US
  Federal LCA Commons (USLCI, eLCI), Agribalyse; ecoinvent licensed. First consumer: the PrISMa rework
  (`docs/briefs/PrISMa-scoping.md`: Woods bare-module CAPEX with Aspen ACCE base costs; € 2019; 8 % discount; nCAC = CCC/(1−CC);
  EF 3.0 + ecoinvent 3.8; functional unit 1 kg CO₂ captured).

## 4. Already decided, not open

- Frank's directives: as few limitations as possible; unimplemented capability returns an explicit unsupported result; batch,
  then test once; at most two agents at a time.
- Reuse established libraries behind adapters (blueprint D01); never vendor licensed data; licences of every new dependency and
  data file audited (blueprint D04) before it ships.
- Cost and impact estimates are assessment evidence, distinct from numerical verification and from empirical validation
  (blueprint D14); every report states its accuracy class and uncertainty.
- No change to a registered numerical result; an identity gate as S08/S10-C/S11 did.
- Register from the next free id after S11's (S11 used R-800…R-842; check `git show wp/S11:docs/decision-register.md` tail and
  `main`'s; start E01 at **R-850**). Next ADR after S11's 0050/0051: **0052**.

## 5. Genuinely open (decide each; a default where it turns on Frank's preference)

1. In-problem quantities versus post-solve functionals (and their derivatives).
2. Which correlation set(s) ship first, and the sizing model per unit family.
3. The cost index and its data source/licence.
4. LCA engine dependency (Brightway as an optional extra, like CoolProp) and the shipped free background data.
5. How an optimization study names a cost/impact objective or constraint (Study schema change → ADR).
6. Verification expectations for cost and LCA.
7. Scope for the first build: which unit families get cost and inventory on day one (the S11 set at least).

## 6. Out of scope

Detailed vendor-grade estimating; dynamic/cyclic units (adsorption cycles are the PrISMa package's); the PrISMa case itself;
GUI.

## 7. Deliverable

`docs/derivations/E01-design.md` (decisions with rejected alternatives, the interfaces, sizing models, cost and LCA
formulations, provenance/uncertainty, assertions, identity gate, work orders split into two parallel tracks with file
ownership, risks with defaults); ADR `docs/adr/0052-…md` (Proposed), more only if needed; register entries from R-850; a
docs-only commit on `wp/E01` including this brief. Do not push. Report in at most 20 lines.
