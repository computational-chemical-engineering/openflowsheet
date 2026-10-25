# S10 brief: a liquid-capable property method for mixtures (design lane, `specifier`)

The package is S10 (provisional id). Branch `wp/S10`, worktree `.claude/worktrees/s10`, from main `8fd7f536`.
Frank, 2026-10-24: "Yes, start the design lane for the liquid mixture properties."

## 1. The question

Scope and specify the project's first liquid-capable property method for mixtures. The answer must state:
- which method;
- which driving cases;
- which data, with its rights;
- the provider contract it meets;
- how phase stability is reported;
- which independent references verify it, and what empirical data validates it;
- which consumers may use it in this package.

Deliver it as an ADR (Proposed) plus a specification with numbered falsifiable assertions and work orders, so the
build lane can implement it without choosing anything scientific.

## 2. Why it matters, and why it is design-lane work

- R01 needs 100+ distinct cases and 25 cross-implementation comparisons (plan l.284). Today the project has no route
  to a realistic liquid mixture:
  - SYN-001 is ideal, with K depending on (T, P) only;
  - `pr-c1-v1` has a liquid phase only for pure NH₃;
  - `pr-lib-v1` is vapour-only;
  - `iapws95-v1` and `coolprop-heos-v1` are pure-fluid and library-only.
- The column refuses every non-SYN-001 provider. That is S03's new refusal S11 (wp/S03,
  `models/syn001/cascade.py:397`), whose message reads "the supported nonideal scope is empty".
- The choice of method, reference state, data and stability policy is scientific semantics (plan §1.3). No test exists
  yet that would catch a wrong choice.

## 3. Authority text

Blueprint `docs/blueprint-v3.1.md`:
- §6.1 (l.193–197): the capability contract. Also: "An excess Gibbs-energy model alone is not a complete property
  package: pure-component references, ideal mixing, caloric terms, phase models, and volume behavior still matter."
  And: "A black-box provider with accurate first derivatives may serve Newton solves."
- §6.2 (l.201–205): "A convenient vapor-pressure correlation and independently selected heat capacities must not be
  labeled fully thermodynamically consistent without checking their relationships." And: "PR/SRK and NRTL/UNIQUAC
  enter through one validated adapter or implementation at a time, driven by cases."
- §6.3 (l.207–224):
  - the formulations;
  - A01, phase-set ownership by the local nonlinear attempt;
  - "General nonideal stability requires appropriate stability analysis, for example tangent-plane-distance
    searches… Report `STABLE_WITHIN_TESTED_SCOPE`, `UNSTABLE`, or `UNKNOWN`." These labels are not implemented
    anywhere today.
- §2.2 (l.58): "selected nonideal vapour–liquid systems after property conformance". Mixtures are not in the deferral
  list at l.62.
- §14.4 (l.591): "One additional validated nonideal property route".

ADR 0022 (`docs/adr/0022-v0.2-real-chemistry-selection.md`):
- l.20, W22: "a cubic EOS (PR or SRK), both phases, with binary interaction parameters from the literature".
- Runner-up: "the methanol–water NRTL case feeds v0.3's columns". Also: "Ethylene glycol… the cheapest nonideal route
  (NRTL)".
- The v0.2 route ended vapour-only. ADR 0026 l.20–24 gives the reason: "IDAES full PR VLE ended on the trivial
  solution… a feed-based stability test misclassifies an NH₃ feed carrying a trace of light gas". D3 set k_ij = 0.
  Related register entries: R-143 (l.3306), R-157, R-160 (l.3735, "no mixture VLE claim"), and V02 deferral N5
  (`docs/V02_DECISIONS.md:250`).

`docs/derivations/S07-spec.md:535` says "Mixtures: out of scope until composition derivatives are measured (blueprint
§6.1)". That sentence is not in the blueprint. Treat it as S07's own deferral.

## 4. Current state (facts from recon, main)

- **The frozen provider protocol** (`docs/interfaces-frozen.md:15`) is describe / evaluate_phase / flash. Changing it
  needs an ADR.
  - The types are in `src/openflowsheet/thermo/__init__.py`: PropertyCapabilities :62, StreamState :105,
    PropertyRequest :133, PropertyResult :150, FlashRequest :174, PropertyProvider :210.
  - Derivatives are requested as named inputs (T, P, n_<c>). An undeclared input returns unsupported.
- **Providers:**
  - `syn001`: `thermo/syn001.py`. Rachford–Rice bisection with Newton at :354. Its limitation reads "no activity or
    fugacity model… no liquid-liquid split".
  - `pr-c1-v1`: `thermo/pr_c1.py`. TP flash at :863, solved by fixed samples and bisection.
  - `pr-lib-v1`: `thermo/pr_lib.py`. Its tangent-plane check uses pure trial phases only (:639), and :728 says "No
    full phase-stability test".
  - `iapws95-v1` and `coolprop-heos-v1`: pure fluids, library-only (ADR 0045, ADR 0046 D9).
- **Phase logic:** `orchestrator/phase_contract.py` (ADR 0005), `attempts.py`, `region.py`, `roots.py`,
  `splits.py`. The C1 phase reading is in `models/c1/phase.py`.
- **Component data:** `benchmarks/m01/components.yaml` (5 records) and `benchmarks/l01/components.yaml` (9 records).
  - Each record has Tc, Pc, ω, ΔHf, ideal-gas cp, identifiers and a rights block.
  - There are no vapour pressures, no liquid volumes and no binary interaction parameters anywhere in the repository.
- **Rights lessons (C12, `docs/C12_DECISIONS.md`):**
  - Six sources are unresolved.
  - CAS RNs "license is required" (`docs/l01-rights-check.md:50`).
  - Frank keeps `pr-lib-v1` unshipped.
  - The clean-up plan is to take constants from primary papers. F-4 (open): dropping CAS RNs removes W27's identity key.
- **Consumers:**
  - C1 units: `models/c1/*`.
  - SYN-001 units: `models/syn001/*`, among them flash, ph_flash, heater, column and cascade.
  - Frank chose "library only for now" for S05/S07 (Q-8). Binding them into flowsheets is a separate queued package.
- **Reference tools** (`docs/reference-environments.md`): IDAES 2.13.0 and DWSIM 9.0.5, both rebuilt and working
  today.
  - For T06 they used IDAES Ideal EoS and DWSIM Raoult's law. "Neither tool shares a property package or correlation
    with this project".
  - The docs do not say whether either tool's NRTL, UNIQUAC, Wilson or liquid-root cubic is usable. A blind
    qualification would settle it, as in S03.
  - S03 found that tool-internal solver conditioning decides availability, and pre-registered the ladders before any
    comparison.

## 5. What is open (decide each, with reasons)

1. **The method.** One route first, per §6.2. The options include:
   - (a) γ–φ with an excess-Gibbs model (NRTL, UNIQUAC or Wilson), an ideal-gas vapour, a pure-liquid reference from a
     vapour-pressure correlation, and caloric terms that are consistent with each other;
   - (b) a cubic EOS liquid regime with k_ij, whose earlier blockers are recorded in ADR 0026.
   Weigh scientific risk, data and rights availability, the stability burden, the reference-tool support and R01's
   needs.
2. **Driving cases.** At least one flash and one column case. The candidates noted earlier are methanol–water
   (ADR 0022) and ethylene glycol. Should an azeotrope be included? LLE is in or out? Multi-component?
3. **Data and rights.** The sources for pure-component constants, vapour pressure, liquid volume, caloric terms and
   binary parameters, with a rights check before anything is shipped (the C12 precedent). Separate validation data
   (published VLE) from model parameters.
4. **The contract.** Whether the frozen protocol suffices as it is:
   - composition derivatives (n_<c>) to first order;
   - the reference convention against SYN-001's;
   - the uncertainty and provenance fields;
   - the domain and refusals.
5. **Stability.** What S10 implements of §6.3's labels: a tangent-plane-distance search scope over phase sets, and
   what `STABLE_WITHIN_TESTED_SCOPE` means operationally.
6. **References and validation.**
   - Independent implementations (IDAES and/or DWSIM, blind qualification with pre-registered ladders), which give
     numerical verification.
   - Published data, which gives empirical validation and is reported separately.
   - Tolerances derived, as T06 and S03 derive them.
7. **Consumers in this package.**
   - Flash and PH flash, the column (relaxing S11 for this provider), or library-only first.
   - Admission to flowsheets (`SELECTABLE_BASES`) is a scope question. Frank chose library-only for S05/S07, so state
     it as a question for Frank with a recommended default rather than deciding it.
8. **Package split and work orders**, each about 150k context. Say which pieces need the `architect` (for example a
   stability search or flash algorithm), and which can be `opus-engineer` or `sonnet-implementer` work.

## 6. Constraints

- Do not re-plan the project or reopen settled ADRs. A departure from blueprint or plan needs an ADR, which this
  package will have anyway.
- No placeholder success paths; unsupported is explicit.
- Self-generated values are regression fixtures, not validation.
- Exact property caches key on exact canonical inputs.
- Residual and Jacobian describe the same function.
- Nothing ships before its data rights are vetted.

## 7. Deliverable

- `docs/adr/00NN-s10-liquid-mixture-property-method.md`, Proposed, using the next free ADR number.
- `docs/derivations/S10-spec.md`: the decisions with reasons, registered cases, assertions, tolerances, a data and
  rights table, work orders, and open questions with recommended defaults. Phrase Frank's questions in plain words.
- Register entries after the current last R-number on main (R-627).
- A docs-only commit on wp/S10, staging named paths. Do not push. Report in at most 30 lines.

Note: S03 (wp/S03) has register entries R-628…R-643 that are not on main yet. Start S10's entries at R-700 to avoid
a numbering clash, and say so in the register header line.

## 8. Out of scope

Electrolytes, solids, polymers, assays and rate-based columns (blueprint l.62); transport properties; binding
S05/S07; the third reference tool (S09); one-phase column sections (S08).
