# Brief — M01 specification: the ammonia loop's real chemistry, pinned

**To:** `specifier` (design lane). **From:** the session (build lane), 2026-10-06. **Branch:** `wp/M01` from `main`.
**Plan row (v1.2 §4.4, binding):** *M01 — T08: pin the selected PyMRM reactor and one required nonideal property
route; derive process boundary mappings. Acceptance: model/source/data rights, numerical refinement evidence,
ports/DOF/reference-state compatibility, known invalid requests.* Lane: Design / Build. Gates fed: **W22** ("one
validated needed nonideal property route") and the M01 half of **W21** ("PyMRM boundary/accuracy/execution and
provenance"; M02 does execution).

## 1. The question

Write M01's authority documents — the derivations, the ADR(s) and the test specification with numbered falsifiable
assertions and machine-readable reference values — so that the build lane can implement (a) a Peng–Robinson property
provider with H₂, N₂, Ar, CH₄ vapour-only and an NH₃-only liquid, (b) the five component records from open cited
sources, and (c) the boundary mapping between OpenFlowsheet's process state and the group's PyMRM ammonia reactor,
and so that a verdict can later judge W22 and M01's part of W21 from the evidence alone.

## 2. Why it needs the design lane

Plan §1.3: derivations, phase logic, reference states and benchmark registration are design-led. Cubic root
selection is new phase logic (ADR 0022 Consequences); the reactor boundary decides the reference-state and
elemental-balance semantics every later package (M02–M07) inherits; the conformance criteria decide what "validated"
means for W22. A wrong choice here propagates through the whole v0.2 critical path M01→M02→M04→M05→M07.

## 3. Current state (read these; the digest is curated for you)

- **Recon digest of the code you build on:** `docs/briefs/M01-recon-digest.md` — the property-provider interface,
  component records, flash and phase-contract code, the verifier's fresh flash, the unit library, model registration
  and identity, dependencies, binding register entries, test patterns. Excerpts with `file:line`.
- **The selection and its evidence:** `docs/v02-real-chemistry-dossier.md` (read whole: ~39 KB; §§4–7, 11, 12 and
  Frank's statements are the core), `docs/adr/0022-v0.2-real-chemistry-selection.md`, records
  `benchmarks/t08/v19/c1-reactor.json`, `c1-provenance.json`, `c1-idaes.json`.
- **Conventions you must respect:** ADR 0001 (state `nTP-v1`, units, zero flow, sign and reference conventions),
  ADR 0011 (formation datum; reactors balance total enthalpy; PH closure in the unit layer), ADR 0005 / 0012
  (phase-attempt contract v2, saturation band, `ZERO_FLOW`), ADR 0013 (verifier's fresh flash at its projection),
  ADR 0008 (no time at the evaluation boundary; `accumulation` declarations), ADR 0019/0020 (application contract —
  frozen), ADR 0023 (the kinetic CSTR, the closest existing reactor pattern).

## 4. Constraints and invariants

- **Existing identities do not move.** SYN-001's structural hash, the K05 identity document and every registered T06
  corpus value must be reproduced bit for bit after M01's code lands; a new provider is additive. If your design needs
  an identity move, say so explicitly — it needs Frank's approval (as R-148/R-149).
- Frozen interfaces (plan §2.1) and schemas (§2.2) change only by ADR; prefer additive widening. The deferred schema
  `$id` move (R-149, "later, by ADR") may ride on M01's first schema change if you judge it cheap; otherwise leave it.
- Residual and Jacobian paths describe the same function at the same state; exact caches key on exact canonical
  inputs; no quantized state on the exact path.
- No placeholder success: an unsupported request (dossier §11's list) returns an explicit unsupported/invalid result.
- Correctness fixtures need an analytic or independent expectation; self-generated outputs are regressions only.
- The group's reactor code is used **by reference, never vendored** (ADR 0022); it runs out of process (M02).
- Performance envelope: one 1D reactor solve is seconds (dossier §10: 3.6 s no membrane, `num_z = 100`).

## 5. Already decided — do not reopen

- Chemistry C1, the ammonia synthesis loop; components H₂, N₂, NH₃, Ar, CH₄ (ADR 0022, R-120, R-145).
- Property method: **Peng–Robinson with H₂, N₂, Ar, CH₄ vapour-only**, liquid NH₃ alone (T08 Amendment R3 8 (a),
  R-143). Full PR VLE with dissolved gases is rejected for v0.2 (no independent reference represents it; dossier §6, §7).
  The dissolved-gas limitation is stated, not fixed.
- Reactor: `ammonia_synthesis_reactor` `main` @ `6089593464fc9bc2c0a0cb58e30ad5433ece6332` (MIT), the 1D model with
  all `P0_*` zero (no membrane); `pymrm` pinned exactly (measured with 2.5.0). Kinetics as implemented (dossier §5).
- **K_NH₃: the code's value, 7000 cal/mol (29 288 J/mol)** — Frank, 2026-10-06, R-152. Not checked against Rossetti
  2006; records must not claim it was.
- Property sources (Frank, 2026-10-02, dossier statement 1): T_c, P_c, ω, c_p, ΔH_f from open, cited sources, each
  value recorded with its primary reference in the project's own component records; `chemicals`/`thermo` the first
  retrieval source, cross-checked against an institutionally backed source (CoolProp or Cantera); the group
  database a cross-check only; the provider interface source-neutral.
- The 4TU dataset (doi 10.4121/e03a6e99-6ddc-4c10-8d92-fb36335cdb43) may be used and referenced; the Simpelaar MSc
  report and the group's 2D draft may be cited.
- Independent reference tool: IDAES 2.13 in a separate environment (`spikes/references/idaes-requirements.lock`);
  its `HC_PR` vapour-only convention represents the method (dossier §7).

## 6. Genuinely open — decide these

1. **Root selection and phase logic** for the vapour-only-light-gases PR provider: which cubic root per phase, how
   the phase split is posed (the liquid is pure NH₃, so the equilibrium is one condition, f_NH₃^V = f_NH₃^L), how it
   enters phase contract v2 (regimes, saturation band, dormancy), and the adversarial cases (near-critical, single
   real root, liquid-root absent, trivial-solution traps).
2. **Enthalpy and reference state:** PR departure functions on top of the ideal-gas c_p and ΔH_f from §5's sources;
   compatibility with ADR 0011's formation datum and the existing total-enthalpy reactor balance.
3. **k_ij:** a cited literature source for the pairs that matter (with vapour-only light gases, only vapour-phase
   mixing uses them), or a justified k_ij = 0 with its stated effect.
4. **W22's "validated":** what conformance evidence suffices — against IDAES at registered states, against pure-NH₃
   saturation from an independent source (e.g. CoolProp's reference EOS), and against published high-pressure
   NH₃–H₂–N₂ VLE data if a usable set exists (identify candidates; the dossier found none). If no VLE dataset is
   usable, say what W22 can and cannot claim.
5. **The boundary mapping:** ports, DOF and units between `nTP-v1` streams and the reactor's inputs/outputs; the
   reference-state translation; the N and H elemental balance check; NH₃ trace feed (`TRACE_NH3`, `A_SMALL`);
   the reactor's Ergun pressure drop versus the loop — **a recycle compressor or a zero-pressure-drop convention**
   (ADR 0022 D2 left this to M01); whether the reactor keeps its own fugacity correlations or takes PR's.
6. **Numerical refinement evidence** for the reactor (W21): grid study over `num_z`, the acceptance (the group's
   certificate), what tolerance the coupled loop needs from the reactor's outputs.
7. **Known invalid requests** (dossier §11's list, made precise and testable).
8. **The M01/M02 boundary:** what M01 must implement versus what M02's execution adapter owns (timeouts, caching,
   noise, frozen versions, promotion). A synthetic stand-in for the reactor, testable without PyMRM, is allowed and
   probably needed for the in-repo gate.
9. Whether `chemicals`/`thermo`/CoolProp become runtime dependencies or are record-authoring/test-time tools only
   (session default: the values live in the project's records with citations; the libraries are not runtime
   dependencies of the solver). Licences of anything added must be recorded (ADR 0006).

## 7. Already tried and rejected (measured, T08)

- Full PR VLE (all five components in both phases) in IDAES: SmoothVLE optimal on the **trivial solution**
  (all K = 1) at the reactor inlet; initialization overflow and unbounded at the separator.
- CubicComplementarityVLE with the vapour-only convention: initialization failed at the reactor inlet; at the
  separator it ends at 266.24 K instead of 268.15 K (K_NH₃ 0.0574 vs SmoothVLE's 0.0615).
- The group property database as a source: its coefficients are undocumented (Frank: cross-check only).
- The first reactor audit at `a6ee9ef` (a dead `gitlab/master` line) — withdrawn; only `6089593` counts.
- At the IDAES separator state (100 bar, 268.15 K) PR gives vapour φ: H₂ 1.045, N₂ 0.949, NH₃ 0.626, Ar 0.907,
  CH₄ 0.840, liquid NH₃ φ 0.0385 (dossier §6) — a cross-check value, not registered.

## 8. How the answer will be verified

The repository gate `./scripts/check.sh` (ruff, mypy strict, pytest; ~6900 tests) must stay green with existing
identities unchanged. Your assertions become tests and evidence-manifest checks (`evidence/M01/<commit>/manifest.json`,
`status: tested` before merge). External conformance runs (IDAES, the reactor) happen in separate environments
outside the project venv, recorded by script and hash as T08 did. A `reviewer` pass on the implementation follows;
a `verdict` judges W22/W21 at v0.2's gate.

## 9. Deliverable

On branch `wp/M01` (commit with messages naming M01, ending with the two attribution lines below; stage named paths
only; do not push):
- `docs/derivations/M01-spec.md` — derivations (PR provider, root selection, departure functions, phase logic, the
  boundary mapping, the elemental balance), numbered assertions `M01.Axx` each with tolerance and independent
  expectation, the adversarial cases, known invalid requests, the evidence-manifest catalogue, **work orders** for the
  build lane (ordered, each with its acceptance tests), and a section *what M01 does not establish*.
- ADR(s) from **0026** for any decision a future session could reverse (at least: the provider and phase logic; the
  boundary convention), status Proposed; register entries from **R-154** in `docs/decision-register.md`.
- Machine-readable reference values under `benchmarks/m01/` where you register them, each with provenance.
- A short list of **questions for Frank** — only value judgements or rights, each with your default.

Attribution lines for commits:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GsDmvQLNcSrnTKTqHXyPD2
```

## 10. Out of scope

M02's execution adapter mechanics (beyond the interface contract M01 fixes); M03–M05 (sweeps, sensitivities,
surrogates, optimization); the web shell; full PR VLE with dissolved gases; columns; DWSIM. Do not re-score or
re-select the chemistry. Do not write production code.
