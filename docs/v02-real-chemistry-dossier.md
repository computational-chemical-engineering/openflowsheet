# The v0.2 real-chemistry dossier — C1, the ammonia synthesis loop (draft)

**Status:** draft by the build lane, 2026-10-01 (T08 W3.4), corrected 2026-10-01 (W3.2 redo on the released
reactor code, brief `docs/briefs/T08-W3.2-redo.md`), and brought to the design lane's rulings 2026-10-01 (T08
release spec Amendment R3 8, R-143: H1, H2 and H4, A61's reading, the property method, the pin); its tables brought
in line with Frank's statements of 2026-10-02 (verdict finding G5, brief `docs/briefs/T08-close.md`). **Not reviewed.**
The design lane finalizes the scores and ADR 0022; Frank gives the `needs_frank` statements. Nothing here is a verdict.
**Governs:** `docs/derivations/T08-release-spec.md` §7.1 (the twelve items), §7.2 (rubric), §7.3 (C1), §7.5, §9
T08.A60–A64, §12 Q6–Q7; ADR 0022 (Accepted 2026-10-02). **Selection:** Frank chose C1 (F3, 2026-09-29).
**Evidence (committed):** `benchmarks/t08/v19/c1-reactor.json` (T08.A61, Q6), `c1-provenance.json` (rate law, data,
licences), `c1-idaes.json` (T08.A62, A63, Q7), the scripts that wrote them (`c1_reactor_run.py`, `c1_idaes_loop.py`),
and `tests/test_t08_w3_v19_records.py` (form only; it does not rerun either external model).

Every number below is quoted from those records. "Not determinable from the repository" is a finding, not a gap
in the reading. Statements attributed to Frank are his (2026-10-01, `docs/T08_DECISIONS.md`), recorded with the
pointers he gave; they are not the build lane's findings.

## Provenance of this draft

- **W3.1 was not run** (session DECISION, brief 2026-10-01): re-acquiring OpenIDAES-450 (220 MB) and re-measuring
  C2–C5 served the ranking; Frank chose C1 and no IDAES-450 case covers ammonia (§7.3). The §7.3 facts for C2–C5
  therefore remain *measured but not registered* (FD9). Reversible by running W3.1 later.
- **Correction (2026-10-01).** The first draft audited `a6ee9ef` of a local clone that is on `gitlab/master`, an
  abandoned line with no common ancestor with the released code; those reactor findings are withdrawn
  (`docs/T08_DECISIONS.md`, CORRECTION). This revision rests on the released code only.
- The group repository: **`ammonia_synthesis_reactor` `main` @ `6089593464fc9bc2c0a0cb58e30ad5433ece6332`**
  (2026-09-17, "Wire in the Zenodo code DOIs"), root commit `d2b0033` ("initial public release"), 9 commits, public at
  github.com/computational-chemical-engineering/ammonia_synthesis_reactor. Tag **`v1.1.0`** is its parent `d78fbfb`;
  `6089593` changes only `CITATION.cff`, `README.md` and `src/reactor/archive.py` (DOIs). **The pin is `6089593`,
  the commit measured** (Amendment R3 8 (d)); `d78fbfb` was not run. Code DOI (Zenodo, cited for attribution):
  concept **10.5281/zenodo.22811033**, release v1.1.0 10.5281/zenodo.22811034. Dataset DOI (4TU.ResearchData,
  CC BY 4.0, in curation): **10.4121/e03a6e99-6ddc-4c10-8d92-fb36335cdb43**. Read and run from a fresh clone only;
  the solves ran in a `git archive` export so the pipeline's cache never entered the clone (clean before and after).
- Two separate environments outside this repository, never the project `.venv`: a stdlib venv with the release
  installed by `pip install -e ".[test]"` (`pymrm` 2.5.0 under the release's `pymrm>=2.3.1`, numpy 2.5.3, scipy
  1.18.1, pandas 3.0.6, Python 3.13.5); and an IDAES venv from `spikes/references/idaes-requirements.lock`
  (idaes-pse 2.13.0, Pyomo 6.10.1, Ipopt 3.13.2, extensions 3.4.2 with both release hashes checked).
- Literature facts (Gargiulo et al. 2025, Richard et al. 2024) are facts of the published papers, read from local
  copies for the first draft and carried (`c1-provenance.json` marks them `carried`). The MSc report and the 2D
  manuscript draft are unpublished and not part of the release; whether they may be cited is Frank's.

## Item statuses (§7.1)

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Chemistry | `met` | §1 below; the release does not state its heat-of-formation source, and by Frank's statement 1 (2026-10-02) M01 takes ΔH_f from an open, cited source, the group database a cross-check only |
| 2 | Component set | `needs_fact` | §2; parameter sources settled by Frank's statements 1 and 4 (2026-10-02): open, cited sources recorded per value by M01; the values and the identifiers are M01's |
| 3 | Loop topology | `met` | §3; c1-idaes.json `loop_skeleton` |
| 4 | Reactor | `met` | §4; c1-reactor.json — `6089593`: the group's suite 69 passed, 3 skipped (not reproduced), 0 failed, which meets T08.A61 (Amendment R3 8 (b, c)); the non-isothermal 1D solve converges; no-membrane runs |
| 5 | Kinetics | `met` (the K_NH₃ discrepancy named) | §5; c1-provenance.json — rate law and data source from the release; λ(q) per Frank. **K_NH₃ discrepancy:** the code's enthalpy term is 7000 cal/mol (29 288 J/mol), Gargiulo 2025 Table 1 prints 29 228 J/mol; Frank's check against Rossetti 2006 is pending (0.35 % effect); `c1-provenance.json` keeps `discrepancy` (Amendment R3 8 (e)) |
| 6 | Nonideal property route | `needs_fact` | §6; c1-idaes.json `pr_flash` — method: **Peng–Robinson with H₂, N₂, Ar, CH₄ vapour-only** (Amendment R3 8 (a)), with the v0.2 dissolved-gas limitation stated; still open: experimental VLE data and a k_ij source |
| 7 | Reference route | `met` (proposed) | §7; c1-idaes.json `representability` — IDAES 2.13 represents the skeleton with the selected method (Amendment R3 8 (a)) |
| 8 | Rights table | `met` | §8 — code MIT; Frank's statements (2026-10-02) settle the property-database row (cross-check only), the 4TU dataset (may be used and referenced) and the MSc report and 2D draft (may be cited); the rights of the property values and of a `k_ij` source are recorded per value by M01 (`needs_fact` rows) |
| 9 | Continuous design decision | `met` (argument) | §9 |
| 10 | Computational cost | `met` | §10; c1-reactor.json `one_1d_solve`, `no_membrane` |
| 11 | What M01 pins | `needs_fact` | §11 — the reactor pin is settled (`6089593`); the K_NH₃ enthalpy term is a pin item, read from Rossetti 2006 itself; the PR parameter set and k_ij are not settled |
| 12 | What the dossier does not establish | `met` | §12 |

### Hard criteria for C1 after these measurements (§7.2; the design lane rules)

H1, H2 and H4 are ruled by the design lane (Amendment R3 8, R-143); H5's inputs are Frank's, settled by his
statements of 2026-10-02 (the verdict at `67c66d9` reads H5 `met`). The "Was" column is history.

| Id | Was (§7.3) | Facts now | Status |
| --- | --- | --- | --- |
| H1 reactor route | `needs_fact` | At `6089593` the group's suite passes (69 of 72; 3 skip on data not shipped), the non-isothermal 1D solve converges with its certificate and element balance, and the 1D model runs without a membrane (all `P0_*` zero): non-isothermal converged in 3.6 s (§4). | `met` — Amendment R3 8 (b, c): A61 is the group's suite (69 passed; the 3 data-guarded skips counted not reproduced) and one converged solve |
| H2 kinetics | `needs_frank` | Rate law: Rossetti et al. 2006, named with its DOI in the release's data header; transcribed in Gargiulo et al. 2025 Eq. (2)/Table 1. λ(q) omitted deliberately (Frank: Weisz–Prater Φ_WP ≤ 0.099, nominal 0.0008; paper Fig. 2). K_NH₃: the code's 7000 cal/mol likely right, Table 1's 29 228 J a transposition (Frank; check against Rossetti 2006 pending, 0.35 %). (§5) | `met` — Amendment R3 8 (e): a published rate law with parameters, compared with experimental data, whichever K_NH₃ transcription is right; which value the code carries is an M01 pin item (§11) |
| H3 needed nonideal route | `met` | PR splits the separator state into vapour and an NH3 liquid (§6). | `met` |
| H4 independent reference | `needs_fact` | IDAES 2.13 builds and solves the skeleton with PR when H2/N2/Ar/CH4 are declared vapour-only; with all five components in both phases the PR flash ends on the trivial solution (§7). | `met` — Amendment R3 8 (a): for C1 "the selected method" is PR with the light gases vapour-only (§6), which IDAES represents; the dissolved-gas limitation is stated in §6 |
| H5 rights | `needs_frank` | Code MIT (`LICENSE`, `pyproject.toml`); the Rossetti CSV names its source and the group's terms; the property database a cross-check only, the 4TU dataset usable and referenced, the MSc report and the 2D draft citable (Frank, 2026-10-02; §8). | `met` — Frank's statements, 2026-10-02 |
| H6 scope | `met` | Steady VLE, no electrolytes, solids, LLE or columns. | `met` |

**Scores.** S7 was provisional 1 ("minutes"). One non-isothermal 1D solve at the group's publication grid
(`num_z = 100`) takes 11.5 s with the membrane and 3.6 s without it, one thread (§10), which is anchor 2
("seconds"). Moving S7 from 1 to 2 raises C1's total from 12 to 13 and does not change the top choice (§7.4's
sensitivity already says no single provisional score does). The design lane re-scores.

---

## 1. Chemistry

N₂ + 3H₂ ⇌ 2NH₃, one reversible reaction, exothermic. Heat of reaction: Gargiulo et al. 2025 Eq. (1),
ΔH₂₉₈ = −92 kJ mol⁻¹ (PDF p.3). In the group model it is not a parameter: species enthalpies are formation
enthalpies plus ideal-gas heat capacity integrated from 298.15 K (`gas_mixture_correlations.py:538`), with
`dH_f(NH3) = −46 120 J/mol` and `dH_f(H2) = dH_f(N2) = 0` in `src/reactor/data/properties_database.json`
(so −92.24 kJ per mol of reaction at 298.15 K). The IDAES skeleton, built on the same `dH_f` and the group's heat
capacities, reports a reactor duty per extent of **−106.7 kJ mol⁻¹ at 673.15 K** (`loop_skeleton.reactor_duty_per_extent_J_mol`).
The source of the database's `dH_f` is not stated in the release; by Frank's statement 1 (2026-10-02) M01 takes ΔH_f
from an open, cited source and uses the database as a cross-check only.

## 2. Component set

| Component | Elements | Molar mass (kg/mol) | Parameter source | Role |
| --- | --- | --- | --- | --- |
| H₂ | H₂ | 0.002015 | group `properties_database.json` | reactant |
| N₂ | N₂ | 0.028 (note: not 0.0280134) | group `properties_database.json` | reactant |
| NH₃ | N H₃ | 0.017021 | group `properties_database.json` | product |
| Ar | Ar | 0.039948 | IDAES 2.13 `examples/ASU_PR.py` (cites RPP4) | inert (purge) |
| CH₄ | C H₄ | 0.016043 | IDAES 2.13 `examples/HC_PR.py` (cites RPP4) | inert (purge) |

ComponentRecords (identifiers such as CAS/InChI, `rights`) are not written here; they are M01 work, and their
`rights` field depends on §8. Identifiers: `needs_fact` (taken from a cited source when the records are written,
not typed from memory). Parameter rights: settled by Frank's statements 1 and 4 (2026-10-02; §8). The elemental balance (N, H) becomes meaningful for
the first time: the IDAES skeleton closes it to ≤ 2.4 × 10⁻⁸ mol/s on 1.5 mol/s of H.

## 3. Loop topology (fixed, for the v0.2 journey)

Fresh feed → mixer (with recycle) → preheater → reactor → cooler → high-pressure flash (liquid NH₃ product) →
vapour → purge splitter → recycle. Built and solved headless in IDAES (§7). Units not in v0.1's library:

- **the PyMRM reactor** — an out-of-process adapter (M02); v0.1 has only a conversion reactor and the kinetic CSTR;
- **the PR flash** — v0.1's flash runs on SYN-001's provider; a cubic provider with root selection is new phase logic;
- **a recycle compressor** — avoidable with the zero-pressure-drop loop convention the skeleton uses (every unit
  dP = 0, the mixer's outlet pressure fixed). The group reactor has an Ergun pressure drop, so a real loop needs
  either a compressor or a convention that absorbs the drop (M01's decision, ADR 0022 D2).

## 4. Reactor

| Field | Value |
| --- | --- |
| Repository | `ammonia_synthesis_reactor`, github.com/computational-chemical-engineering/ammonia_synthesis_reactor (MIT) |
| Commit read and run | `main` @ `6089593` (2026-09-17); tag `v1.1.0` = parent `d78fbfb` (DOI wiring only between them) |
| PyMRM | declared `pymrm>=2.3.1` in `pyproject.toml`; measured with 2.5.0 (MIT; package metadata) |
| Models | `MembraneReactor` (2D axisymmetric), `MembraneReactor1D` plain (`membrane_reactor_1d`) and with a concentration-polarization closure (`membrane_reactor_1d_corrected`); pseudo-transient Newton; paper pipeline `reactor.paper` with per-case convergence certificates |
| Equations reference | the accompanying paper (DOI pending, README) and Gargiulo et al. 2025 (1D PBMR, CC BY); no equation document is tracked in the repository |
| Group regression reference | the pytest suite `tests/` (6 modules, 72 tests), each test with its own assertion tolerance (e.g. `rtol = 1e-12` on the 1D membrane-coupling conservation identity, `tests/test_1d_models.py:41`, `:98`); `main` has no stored-field regression harness |

**T08.A61 — the group's suite at `6089593`.** `python -m pytest tests/ -q` in the separate environment: **72
collected, 69 passed, 3 skipped, 0 failed** (pytest 3.9 s). The three skips are the suite's own `skipif` guards on data that
is generated or archived, not shipped: `test_cp_closure.py:57` needs the publication-tier closure fit written by the
2D publication sweep (`results/paper/publication/screened_cp_fit.json`, ~80 min of 2D solves); `test_paper_pipeline.py:115`
and `:127` need the earlier study's archive `Dataset_paper/` (git-ignored). Frank states the suite as 72 tests; on a
fresh clone 69 run. **A61's reading (Amendment R3 8 (b, c)):** the group's "own regression reference" is its pytest
suite at the pin, and "the group's regression tolerance" is each test's own; 69 passed, 0 failed, 3 skipped by the
suite's own guards on inputs the release does not ship **meets A61**, with the three counted *not reproduced*. No
test solves a full reactor or compares a solved field with stored values; the solved-case reference is the published
dataset (4TU, in curation), with its SHA-256 manifest and `reactor.paper.dataset.verify`. That comparison is not
part of A61: its use awaits Frank's rights statement (§8), and a solved-case comparison with published results is
validation evidence M01 owns, not selection feasibility.

**One non-isothermal 1D solve.** Case `G2 — GHSV sweep_1000` of the 52-case table (`data/inputs/cases_to_run.xlsx`;
r = 0.03 m, 80 bar, 623 K, H₂/N₂ = 2, one membrane, L = 1 m), publication grid (`num_z = 100`), through the group's
own `reactor.paper.runner.run_case_1d` (cold start `DT_INIT_1D = 1e-6`, `SOLVER_1D`, KPI-drift certificate,
element-balance check): **converged** (185 steps, absolute residual 9.7 × 10⁻⁴ against 10⁻³), certificate drift 0,
element balance ok (H 3.2 × 10⁻⁴, N 3.6 × 10⁻⁴ relative, against the group's 10⁻³). X_H₂ 40.0 %, NH₃ recovery
96.7 %, ΔT_max 304.9 K. Identical outlets across three repeats.

**Frank's statements on `main`** (pointers his; the lines are quoted verbatim from `6089593` in
`c1-reactor.json` `quoted_lines`): `lambda_mem` is evaluated at T at every call site (`membrane_reactor_1d.py:688`,
`membrane_reactor_1d_corrected.py:866`, `membrane_reactor.py:2073`, `:2077`); the 52-case publication sweep is
non-isothermal with per-case certificates and `element_balance_ok` in each `kpis.json`. **A genuine defect on `main`
(his, logged by the group for its next version; not patched now because of the DOI/curation):**
`reactor/paper/validation.py:103`'s "membrane-free" Rossetti validation sets `cfg.Perm_NH3` (a removed field,
`config.py:51` is the commented-out declaration) and `cfg.Nm` (never read), so the `P0_*` permeances stay live;
worst effect 0.26 % on outlet NH₃, no reported number changes. The build lane's reading of the quoted lines agrees:
`build_rossetti_config` assigns no `P0_*`, and `Nm` is only stored by the 1D models (`membrane_reactor_1d.py:172`,
`membrane_reactor_1d_corrected.py:179`).

**Q6 — no membrane: it runs.** With every permeance pre-factor zero (`P0_H2 = P0_N2 = P0_NH3 = 0`; `Perm_NH3` is a
removed field) no species crosses the membrane (membrane transfer exactly 0) and the model is a packed bed; the
permeate tube remains a heat exchanger in the non-isothermal run. Same case, same pipeline entry point:

| Thermal | Cold start `dt_init` | Outcome | Solve (s) | y_NH₃ out | Element balance (H, N rel.) |
| --- | --- | --- | --- | --- | --- |
| non-isothermal | 1e-6 (pipeline) | converged, certified | 3.6 | 0.1040 (ΔT_max 135.3 K) | 4.8 × 10⁻⁴, 1.2 × 10⁻⁴ |
| isothermal 623 K | 1e-6 (pipeline) | failed (residual 11.9, 400 steps) | 9.0 | — | — |
| isothermal 623 K | 1e-3 (the group's isothermal start, `ROSSETTI_DT_INIT`) | failed (residual 11.8) | 8.6 | — | — |
| isothermal 623 K | 1e-2 | converged, certified | 0.48 | 0.2703 | 8.3 × 10⁻⁴, 2.1 × 10⁻⁴ |

Limiting check: at 623 K and 80 bar the group's own rate law vanishes at y_NH₃ = 0.3211 (its
`AmmoniaSynthesisKinetics`), above the isothermal outlet 0.2703. The isothermal runs are outside the pipeline's
use (every paper case is non-isothermal); a scan outside the record (dt_init 10⁻⁶…1) put the boundary between 10⁻³
(fails, negative outlet flows) and 3 × 10⁻³ (converges, y_NH₃ 0.2700). The group's acceptance test rejects the
failed states — they are not silently wrong — but M01 must check acceptance and never take an unaccepted state.
Q6's default (M01 writes a plain packed bed if the 1D model cannot run without a membrane) is not needed.

**Boundary mapping sketch (inlet `(n, T, P)` → outlet).** The group's configuration takes the inlet molar flow
`F_ret_in`, inlet composition `y_ret_in` and inlet temperature `T_ret_in`, and the **outlet** pressure `p_ret_out`
(the Ergun drop determines the inlet pressure). The process simulator's unit contract gives the inlet pressure. M01
must either invert for `p_ret_out` (a scalar solve around the reactor) or neglect the drop; the case tables are
written in GHSV, which maps to `F_ret_in` through the catalyst volume (`reactor/paper/case_setup.py:114`
`calculate_flows`; outlet pressure `p_ret_out` at `:463`). The
outlet is the axial face flows at `z = L`, temperature and pressure. **DOF:** geometry, catalyst (ρ_c, D_cat, ε,
d_p), permeance parameters (zero for the packed bed), wall/heat transfer correlations, and the four boundary values.

**Reference-state compatibility with ADR 0011.** The group's enthalpy is a formation datum on the ideal gas at
298.15 K (`dH_f` + ∫c_p), which is the kind of datum ADR 0011 D2 requires of a reacting unit. ADR 0011's registered
reaction-consistent set is `{"SYN-001-ref-v1"}`; adding the ammonia datum is a new design-lane decision.

## 5. Kinetics

From `c1-provenance.json` (pointers there; "carried" marks facts of the published papers, read for the first draft):

- **Rate law:** Rossetti, Pernicone, Ferrero, Forni, *Ind. Eng. Chem. Res.* 45 (2006) 4150–4155,
  doi:10.1021/ie051398g (Ru/C), a Temkin-type rate with an adsorption term. The release names it, with the DOI, in the
  header of its kinetics dataset and in `reactor/paper/validation.py`; the kinetics module cites nothing. Carried:
  transcribed in Gargiulo et al. 2025 Eq. (2) and Table 1. The code at `6089593` (`ammonia_synthesis_kinetics.py`)
  has the constants compared with that transcription: k_f = 9.02 × 10⁸ exp(−23 000 cal/mol / RT) (`:239`),
  K_H₂ (`:261`), every exponent (`:329–383`), K_a, the H₂, N₂, NH₃ fugacity-coefficient correlations and the
  catalyst-volume conversion (`:193`).
- **λ(q) — omitted deliberately (Frank).** The published form evaluates activities from a fractional conversion with
  fitted feed-ratio parameters and multiplies by λ(q) (1 at H₂/N₂ = 3, 3 at 1.5); the code uses local partial
  pressures times fugacity coefficients and has no λ(q). Frank: deliberate, justified by the Weisz–Prater scan (worst
  Φ_WP 0.099, nominal 0.0008; `validation/weisz_prater_scan.json`, an output of `reactor.paper.validation.weisz_prater_scan`)
  and the paper's Fig. 2.
- **K_NH₃ (Frank).** The code's enthalpy term is 7000 cal/mol (= 29 288 J/mol, `:266`); Gargiulo 2025 Table 1 prints
  29 228 J/mol (carried). Frank: the code's value is likely right and 29 228 a transposition; 0.35 % relative effect
  at Rossetti Test 1; he is checking it against Rossetti et al. 2006. `c1-provenance.json` keeps the finding as a
  `discrepancy` until that check is recorded.
- **Comparison with experimental data:** the release re-solves every experimental point with the isothermal,
  membrane-free 1D model for the paper's Figures 3/4/S.6 (`reactor.paper.validation`; Frank's 0.26 % defect, §4,
  concerns that validation). Carried: Gargiulo 2025 §3.1 validates against 16 of these tests (mean absolute error,
  parity plot, Figs. 3–4).
- **Data domain:** that of the dataset (next bullet). The kinetics were fitted only at H₂/N₂ = 1.5 and 3.
- **Dataset:** `data/inputs/ammonia_synthesis_data_rossetti_et_al.csv`, in the release since its root commit. Its
  header states that the group transcribed it from Rossetti et al. 2006 (DOI given), only so the kinetics verification
  is reproducible, that the original is to be cited, and that the `GHSV_*` columns hold the **NH₃ outlet mole
  fraction [vol %] at that space velocity [h⁻¹]**: 19 test conditions, 125 points (tests 1–4, 7, 8, 10, 11, 13,
  15–24). Which table or figure of Rossetti et al. was transcribed is not stated. (§7.3 said 18 conditions; the
  file has 19.)

## 6. Nonideal property route (W22 "needed")

| Field | Value |
| --- | --- |
| Method | **Peng–Robinson, with H₂, N₂, Ar and CH₄ declared vapour-only** — the liquid is NH₃ alone (IDAES's `HC_PR` convention; Amendment R3 8 (a)). The group's own reactor model already uses PR for mixture properties (`reactor/gas_mixture_correlations.py:5`, `:36`). M01's provider and its reference use the same convention, so v0.2's comparison is like for like |
| Parameters | T_c, P_c, ω for H₂, N₂, NH₃ from the group database (source not stated); Ar, CH₄ from IDAES's example sets citing RPP4; **k_ij = 0 for every pair** (no source for the H–N–Ar–CH₄–NH₃ pairs in either repository) |
| Ideal-gas c_p | the group's DIPPR-107 coefficients (H₂, N₂, NH₃); RPP4 (Ar, CH₄) |
| Domain exercised | 100 bar; 268.15 K (separator) and 673.15 K (reactor inlet) |
| Conformance reference | independent implementation: IDAES 2.13 (this dossier, §7); experimental high-pressure NH₃–H₂–N₂ VLE data: **not identified** (`needs_fact`) |
| What the provider must supply | fugacity coefficients of both phases, enthalpy departures, and the phase split with the light gases in the vapour only; cubic root selection per phase is an M01 derivation item. Trivial-solution avoidance for a multicomponent liquid is not needed in v0.2 (full PR VLE is not the route, §7) |

The kinetics' own fugacity coefficients are separate correlations (Table 1 of Gargiulo 2025), not PR; M01 decides
whether the reactor keeps them or takes PR's. At the IDAES separator state PR gives vapour fugacity coefficients
H₂ 1.045, N₂ 0.949, NH₃ 0.626, Ar 0.907, CH₄ 0.840 and the liquid NH₃ coefficient 0.0385.

**v0.2 limitation — dissolved light gases.** With H₂, N₂, Ar and CH₄ vapour-only, none dissolves in the liquid NH₃:
the purge is the inerts' only exit, and NH₃ product purity and dissolved-gas losses are not represented. Their effect
on the reactor-inlet-temperature decision (§9) is not measured. Full PR VLE with every component in both phases was
rejected as the method: no acquired tool represents it (IDAES ends on the trivial solution or unbounded, §7), so it
would have no independent reference.

## 7. Reference route

IDAES 2.13.0 in a separate environment (pins in Provenance). Records: `c1-idaes.json`. No number is compared with
anything (T08.A62 "no comparison claimed").

**T08.A62 — PR flash at two states (100 bar).** Compositions are illustrative loop compositions chosen for the smoke.

| Representation | Reactor inlet, 673.15 K | Separator, 268.15 K |
| --- | --- | --- |
| H₂, N₂, Ar, CH₄ vapour-only (IDAES's `HC_PR` convention), SmoothVLE | optimal; single-phase vapour (liquid fraction 1.9 × 10⁻¹³) | optimal; vapour fraction 0.8897, liquid pure NH₃, y_NH₃ = K_NH₃ = 0.0615 |
| same, CubicComplementarityVLE | initialization failed, solve infeasible | optimal; K_NH₃ = 0.0574 — its equilibrium temperature ends at 266.24 K, not 268.15 K |
| all five in both phases (full PR VLE), SmoothVLE | optimal on the **trivial solution** (all K = 1, phase fractions arbitrary) | initialization overflow; solve unbounded on the trivial solution |

Halving the Psat estimate that IDAES uses only to initialize bubble/dew temperatures changes the primary route's
answers by ≤ 2.2 × 10⁻¹⁶ (`psat_independence`).

**T08.A63 — the skeleton**, built headless and solved once: fresh feed 1 mol/s (H₂:N₂ = 3, 1 % Ar + CH₄) at 100 bar;
heater to 673.15 K; `StoichiometricReactor` with 25 % per-pass N₂ conversion; cooler to 268.15 K; adiabatic flash;
10 % purge; recycle; zero dP. DOF 0 after releasing the tear guess; Ipopt **optimal**. Recycle 2.286 mol/s, liquid
NH₃ 0.365 mol/s, purge 0.254 mol/s, element balances ≤ 2.4 × 10⁻⁸ mol/s.

**Q7 — a custom rate law: yes, demonstrated once.** An IDAES `CSTR` with the group's rate law as a user `rate_form`
(activities = PR vapour fugacities in bar, not the group's correlations), 1 L, isothermal at the reactor-inlet state:
optimal, N₂ conversion 0.0145. A PFR was not built.

**Representability table** (`c1-idaes.json` `representability`): feed, recycle mixer, preheater, stoichiometric
reactor, kinetic reactor (CSTR, user rate form), cooler, HP separator with vapour-only light gases, purge and recycle
closure — **Y**; HP separator with full PR VLE — **N** (trivial solution, above); equilibrium reactor and recycle
compressor — **not built** (the former needs a user K_eq class; the latter is avoided by the zero-dP convention).

**H4 (Amendment R3 8 (a)):** the vapour-only representation is C1's selected method (§6), and IDAES 2.13 represents
the skeleton with it — both flash states and the loop skeleton `optimal`, separator K_NH₃ 0.0615 — so H4 is `met`.
**Independent reactor data:** the Rossetti dataset (§5) is the kinetics' empirical anchor; no independent loop case
exists.

## 8. Rights table (T08.A64)

Mode per ADR 0006: **A** = the project declares a dependency the user installs; **C** = replay bundles record the item
by reference and hash, never embed it. No item below is vendored.

| Item | Source | Licence or permission | Scope | Mode | Attribution | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Group reactor code `ammonia_synthesis_reactor` | GitHub `computational-chemical-engineering/ammonia_synthesis_reactor`, `main` @ `6089593` (v1.1.0 = `d78fbfb`); Zenodo 10.5281/zenodo.22811033 | **MIT** (`LICENSE`; `pyproject.toml` `license = "MIT"`; `CITATION.cff`) | run out of process as the M01 reactor | A/C by reference (not vendored) | I. Gargiulo, E.A.J.F. Peters (`LICENSE`, `CITATION.cff`); cite the Zenodo DOI | met |
| `pymrm` 2.5.0 (release requires `>=2.3.1`) | PyPI | MIT (package metadata) | reactor numerics, in the reactor's own environment | A (user installs) / C | E.A.J.F. Peters (maintainer) | met |
| Group paper dataset | 4TU.ResearchData, doi 10.4121/e03a6e99-6ddc-4c10-8d92-fb36335cdb43 | CC BY 4.0 as stated (`README.md`, `archive.py:71`); deposit in curation | solved-case reference for the reactor (not used by M01 so far) | C by reference | the dataset DOI | met — may be used and referenced (Frank, 2026-10-02) |
| Rossetti et al. dataset (CSV) | release `data/inputs/ammonia_synthesis_data_rossetti_et_al.csv`, transcribed by the group from Rossetti et al. 2006 (header) | third-party measurements, not covered by the code's MIT (`README.md` "Data"); the group's terms: cite the original publication | kinetics validation | C by reference | Rossetti et al. 2006, doi 10.1021/ie051398g | met |
| Group property database | release `src/reactor/data/properties_database.json` | the file is under the release's MIT; the coefficients' sources are not stated | cross-check only of M01's property values (Frank, 2026-10-02); its values enter no ComponentRecord and no certified record | not conveyed (a cross-check) | sources not stated | met — cross-check only (Frank, 2026-10-02) |
| `chemicals` / `thermo` (M01's first retrieval source) | PyPI `chemicals` 1.5.2, `thermo` 0.6.1 (single maintainer) | code MIT (PyPI metadata, read 2026-10-02); each value's data provenance is its primary reference | retrieval of Tc, Pc, ω, c_p, ΔH_f for M01's records (Frank, 2026-10-02); never a runtime dependency of the certified path | not conveyed (a retrieval tool; M01 records each value with its primary reference) | per value, the primary reference M01 records | `needs_fact` for M01 (per-value data provenance) |
| CoolProp / Cantera (M01's cross-check) | PyPI `CoolProp` 8.0.0, `cantera` 3.2.0 | code: CoolProp MIT, Cantera BSD-3-Clause (PyPI metadata, read 2026-10-02); each value's data provenance is its primary reference | cross-check of the retrieved values (Frank, 2026-10-02: CoolProp or Cantera) | not conveyed (a cross-check tool) | per value, as M01 records | `needs_fact` for M01 (which tool, and per-value data provenance) |
| Rate law (equations and parameters) | Rossetti et al. 2006; implemented in the release's MIT code; transcribed in Gargiulo et al. 2025 Table 1 | published equations; the implementation is MIT | re-implemented in M01 or run in the reactor, with citation | A (project code) / C | Rossetti et al. 2006; Gargiulo et al. 2025 | met |
| Gargiulo et al. 2025 | Int. J. Hydrogen Energy 166 (2025) 150995, doi 10.1016/j.ijhydene.2025.150995 | CC BY (TU/e repository copy) | provenance reading only | not conveyed | cited | met |
| Richard et al. 2024 | Int. J. Hydrogen Energy 73 (2024) 462–474, doi 10.1016/j.ijhydene.2024.06.041 | journal copyright | provenance reading only | not conveyed | cited | met |
| Simpelaar MSc report; the group's 2D manuscript draft | unpublished; not part of the release | none stated | provenance reading only | not conveyed | cited where used | met — may be cited (Frank, 2026-10-02) |
| Third-party data in the release not used by M01 (`s1_diffusivity_chapman.csv`) and the group's own membrane measurements (`permeation_exp_measured_fig5.csv`) | release `data/inputs/` | third-party: cite the original (header, `README.md`); the group's own outputs: MIT | none for M01 (SI Fig. S.1; membrane permeances are zero in the packed bed) | not conveyed | per header | met |
| IDAES 2.13.0 (+ Pyomo) | PyPI, `spikes/references/idaes-requirements.lock` | BSD (docs/reference-environments.md) | independent reference only, separate environment | not conveyed (not a dependency) | IDAES | met |
| IDAES extensions 3.4.2 (Ipopt, default linear solver) | IDAES GitHub release, hash-checked | mixed; HSL solvers not open source (docs/reference-environments.md §4.2) | reference runs only | not conveyed | IDAES / COIN-OR / HSL | met for this scope |
| Ar, CH₄ parameters (IDAES examples) | IDAES `ASU_PR.py`, `HC_PR.py` | BSD code; values cite RPP4 (book) and NIST | reference smoke | not conveyed | IDAES; Reid–Prausnitz–Poling | met for the smoke (Frank, 2026-10-02); `needs_fact` for M01 records (from the same open, cited source as the other property values) |
| k_ij | none used: `k_ij = 0` for every pair, a modelling choice of the T08 smoke runs (W3.3; `benchmarks/t08/v19/c1_idaes_loop.py`, `c1-idaes.json` `binary_interaction`); M01 must select and cite a source | none needed: no third-party value is used (`0` is the project's own choice) | the T08 V19 IDAES smoke runs only (§6, §7); no M01 record | the project's (a literal in its own script; nothing conveyed) | none (no source used) | `needs_fact` for M01 (select and cite a k_ij source) |
| This project's scripts and records under `benchmarks/t08/v19/` | this repository | the project's own | evidence | the project's | — | met |

## 9. The continuous design decision

The reactor inlet temperature (§7.3): for an exothermic reversible reaction an equilibrium reactor favours ever-lower
temperature, while a kinetic reactor has an interior optimum, so reactor fidelity changes the decision qualitatively;
the alternative is the purge fraction. The group's 2D manuscript draft reported the interior optimum in its (membrane) reactor: "the best productivity in
the tested window occurs at 573 K", falling at 673 and 723 K (read for the first draft from the unpublished draft,
not part of the release; citing it is Frank's). The release's case table carries the temperature sweeps (G5, G6:
548–698 K) that would show it.
Not yet demonstrated on the loop — M01/M07 work.

## 10. Computational cost at design-loop resolution

One 1D solve at `6089593`, case `G2 — GHSV sweep_1000`, the group's publication grid (`num_z = 100`) and 1D solver
settings, cold start, one thread, through `reactor.paper.runner.run_case_1d`: **11.5 s** non-isothermal with the
membrane (12.0, 11.5, 10.7 s; the whole call with certificate and cache write 12.0 s median; identical outlets
across repeats); **3.6 s** non-isothermal without the membrane; 0.48 s isothermal without the membrane when it
converges (§4). Repeat runs of the record on this shared machine moved single timings by up to ~20 % (3.0 vs 3.6 s
for the no-membrane solve). The 2D model was not timed here; the release's README gives ~80 min for the 52-case 2D
publication sweep on a desktop CPU (the group's figure). One reactor solve is seconds: S7 = 2 by its anchor.

## 11. What M01 pins, and its known invalid requests

**Pins:** the reactor at `6089593` (`main`, the commit measured — Amendment R3 8 (d); tag `v1.1.0` = `d78fbfb`
differs in `CITATION.cff`, `README.md` and `src/reactor/archive.py` and was not run — if M01 prefers the tag it re-runs
A61 there, about 20 s; Zenodo concept DOI 10.5281/zenodo.22811033 for attribution) — the group logs the
`validation.py:103` defect for its next version, which M01 would pin afresh; `pymrm` at an exact version (measured
with 2.5.0; the release only bounds it below, `>=2.3.1`); the configuration (all `P0_*` zero, `num_z`, the group's 1D
solver settings and acceptance with its certificate); the kinetics variant as implemented (§5), with **the K_NH₃
enthalpy term read from Rossetti et al. 2006 itself** (the code's 7000 cal/mol against Gargiulo 2025 Table 1's
29 228 J/mol, §5; Amendment R3 8 (e)); the property route of §6 (PR, light gases vapour-only). Still open: the PR
parameter set and k_ij (`needs_fact`).

**Known invalid requests:** H₂/N₂ outside the fitted 1.5 and 3 (the parameters are fitted only there); temperatures
outside 370–460 °C and pressures outside 50–100 bar (the data domain); a feed with zero NH₃ (the rate has a_NH₃^−0.25;
the group regularizes with an activity floor `A_SMALL = 1e-4` bar and feeds a 10⁻⁹ NH₃ trace in its paper cases,
`settings.TRACE_NH3`); an unaccepted solver state (the isothermal no-membrane runs of §4 fail from small cold-start
steps — the group's acceptance rejects them, and M01 must too); an inlet-pressure
specification without the outlet-pressure inversion (§4); a liquid carrying dissolved H₂, N₂, Ar or CH₄ (full PR
VLE is outside v0.2's route, §6).

## 12. What this dossier does not establish

- No validation: no model number here is compared with experimental data or with another model. The IDAES numbers
  are smoke evidence of representability, and the reactor numbers are the group model's own outputs.
- No reference values: none of the states, compositions or loop specifications is registered.
- Not that the group's kinetics are correct. K_NH₃ rests on Frank's statement until his check against Rossetti et
  al. 2006 is recorded.
- Not that the group's solved cases are reproduced: the suite has no solved-field comparison, and the published
  dataset (4TU) was not compared (§4).
- Not the per-value rights of the property values, the `k_ij` source or VLE data M01 will choose (the `needs_fact`
  rows of §8).
- Not the full PR VLE with dissolved gases in IDAES, nor DWSIM's behaviour (not tried).
- Not that the vapour-only convention is adequate for v0.2's design decision (unmeasured; stated as a limitation, §6).
- Not the three data-guarded tests of the group's suite (counted *not reproduced*, §4).
- Not the C2–C5 facts of §7.3 (W3.1 not run).
- Not the scores: those are the design lane's (ADR 0022).

## Questions for Frank

Answered on 2026-10-01 and recorded above: the code licence (MIT), the pin (`main` @ `6089593`), λ(q), K_NH₃ (pending
his check against Rossetti 2006), and the Rossetti dataset's source and unit (now in its header). Questions 1–3
were answered on 2026-10-02 (next section); question 4 is still his:

1. **Property database:** the sources of its coefficients (T_c, P_c, ω, c_p, viscosity, conductivity, dH_f).
2. **The group's paper dataset (4TU):** its permitted use while the deposit is in curation.
3. May the unpublished MSc report (Simpelaar) and the 2D manuscript draft be cited as provenance?
4. **K_NH₃:** the outcome of the check against Rossetti et al. 2006, when done.

## Frank's statements, 2026-10-02 (they settle the `needs_frank` items above)

Recorded by the build lane from Frank's answers in session. The tables above carry these outcomes since 2026-10-02
(verdict finding G5); the H table's "Was" column keeps the earlier status words as history.

1. **Property database (items 1, 2, 8; H5).** *"For v0.2, M01 takes Tc, Pc, ω, c_p and ΔH_f from open, cited sources
   and records each value with its primary reference in the project's own component records; `chemicals`/`thermo`
   serves as the first retrieval source, cross-checked against an institutionally backed source (CoolProp or
   Cantera); the group database is a cross-check, not a source."* (Frank: "I agree".) The group database's
   undocumented coefficients therefore enter no certified record; the provider interface M01 defines is
   source-neutral, so further open sources (CoolProp, Cantera, NIST `teqp`, Clapeyron.jl, IDAES packages) can be
   added later without touching certified records.
2. **4TU dataset** (doi 10.4121/e03a6e99-6ddc-4c10-8d92-fb36335cdb43): may be used and referenced (Frank).
3. **Simpelaar MSc report and the group's 2D manuscript draft:** may be cited (Frank).
4. **Ar, CH₄ PR parameters from IDAES's examples (RPP4, NIST):** fine for the smoke runs (Frank); for M01's records
   they come from the same open, cited source as item 1.

Status after these statements: items 1, 2 and 8 and H2/H5 have no remaining `needs_frank` input; items 2, 6 and 11
are `needs_fact` (M01 work: per-value property sources and identifiers, VLE data and a `k_ij` source, the PR
parameter set). *(Corrected 2026-10-02, G5: this sentence named items 6 and 7; the item table has 7 `met (proposed)`
and 11 `needs_fact`.)*

## Frank's statement, 2026-10-06

5. **K_NH₃ (item 5, §11; question 4).** *"For K_NH3 use the code's value."* M01 pins the code's enthalpy term at
   `6089593`, 7000 cal/mol (29 288 J/mol, `exp(-8.3/R + 7000/RT)` with R in cal). This is Frank's decision; the
   check against Rossetti et al. 2006 itself was **not** performed, so §12's "K_NH₃ rests on Frank's statement"
   stands, and Gargiulo 2025 Table 1's 29 228 J/mol stays recorded as a discrepancy (0.35 %), not as resolved.
   Register R-152.
