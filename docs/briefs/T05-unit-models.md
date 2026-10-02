# Brief — T05 specification: the v0.1 unit-model families

**To:** `specifier` (design lane)
**From:** the session (build lane), 2026-09-25
**Branch:** `wp/T05`, from `main` at the T04 merge (`279b2eb` or later)
**Deliverable:** a specification, an ADR if any frozen interface or provider capability changes,
reference values and a work order — §8. Commit on `wp/T05`, staging named paths only; messages end
with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01QMQnXcFna3j5D6Ai9Ja9AE`.

## 1. The question

What exactly are the equations, specifications, degrees of freedom, validity domains, failure modes
and derivative declarations of the six T05 unit models? The models are:
- general PH flash;
- conversion reactor;
- component separator;
- valve;
- liquid pump;
- one two-stream heat exchanger.

What registered cases, with independent expected values and numbered falsifiable assertions,
constitute each model's "definition of done" (gate V12)? The answer must let the build lane implement
each model as a manifest-declared native equation model, like K02's six, without deciding any
equation, sign, reference state or domain.

## 2. Why it needs the design lane

The plan's lane column for T05 is *Build / Design*: the build lane implements and leads, but the
schedule review is explicit that the models need "design-approved equations first"
(`docs/v0.1-schedule-review.md:31`). The lane rule (plan §1.3) gives the design lane:
- unit/state/zero-flow semantics and sign conventions;
- reference states;
- every derivation.

Each model needs all three. A wrong sign convention in a pump or exchanger, or a heat of reaction
under a reference state that disagrees with the provider's, is silent. It balances in its own
bookkeeping and is wrong against every external reference T06 will compare with.

## 3. Current state (verbatim where it binds)

**Plan §4.3 T05 row** (`docs/implementation-plan.md:243`): *"T02: general PH flash, conversion
reactor, component separator, valve, liquid pump, one two-stream heat exchanger."*
- Acceptance: *"Each model's contract, limiting/failure tests, balance and derivative evidence; at
  least one coupled case per family."*
- Gate **V12**: *"Required unit library with per-model definition of done"* (owner T05).
- Plan v0.1 scope: *"Core models: network units, heater/cooler, TP/PH flash, component separator,
  conversion reactor, simple valve and liquid pump, one two-stream exchanger formulation. Equilibrium
  reactors and elaborate equipment modes are deferred unless already needed by a case."*
- Plan §3.2 on SYN-001's mixer: *"restricted, in v0.0, to the subcooled-liquid domain with a typed
  failure outside it; general PH support is T05."*
- K02: *"Do not implement a general PH flash in v0.0."*

**Blueprint.**
- §6.2: *"Start with TP flash, then bracketed PH flash on supported single/two-phase regions. For
  ideal VLE, use a safeguarded Rachford–Rice solve, explicit single-phase endpoints, and
  zero-component handling."*
- §5.3: *"A replacement checks ports, components, conserved quantities, reference states,
  boundary-condition meaning, degrees of freedom, derivatives, and validity. Matching the label
  'reactor' is insufficient."*
- §6.1: *"Require the capabilities used by a unit, not a universal tier."*
- §7.2 [A02]: cross-unit specifications promote to an EO region; no nested SM loops.

**The unit-model pattern K02 established** (`src/process_runtime/models/syn001/`).
- Each unit is a dataclass with `model_id`, `ports()`, `declared_equations()`, `manifest()` and
  `contribute(wiring, components) → Contribution`. There is no base class.
- Every `DeclaredEquation` carries:
  - `equation_id`, `statement`, `dependencies`;
  - `conditional_class` (`unconditional` / `phase_conditional`);
  - `accumulation` (ADR 0008 D3: `algebraic`, `zero_holdup_balance`, or `holdup_balance` with a
    named holdup and its dimension);
  - `dimension` and `source`.
- The heater and flash share the TP-state kernel (`tp_state.py`) and the lifted two-phase split.
  Lifted variables are named after the **stream** (R-008), and property blocks are deduplicated by
  block id.
- The residual convention for balance rows is `F_row = inflow − outflow + sources` (ADR 0008 D3.3),
  with duty positive into the unit (ADR 0001).

**The property provider** (`thermo/__init__.py`; protocol frozen at P01, `docs/interfaces-frozen.md` §1).
- The provider interface is `describe()`, `evaluate_phase(PropertyRequest)` and `flash(FlashRequest)`.
- `FlashRequest.specification` already exists and defaults to `"TP"`.
- The SYN-001 provider (`thermo/syn001.py:80-110`) declares:
  - `flashes=("TP",)` and `properties=("h", "lnK")`;
  - first-order derivatives in T and P;
  - domain T ∈ [280, 440] K, P ∈ [5e4, 2e5] Pa;
  - the limitation *"TP flash only; no PH flash in v0.0 (plan §3.2)."*
  - It refuses any other specification as `unsupported`.
- The SYN-001 thermodynamics (plan §3, `docs/derivations/SYN-001.md`):
  - `h_i^L = c_p(T − T_r) + v_i(P − P_r)`, `h_i^V = c_p(T − T_r) + L_i`;
  - `L = (25 000, 30 000, 35 000)` J/mol;
  - ideal K-values with a Poynting-type `v_i(P − P_r)/(RT)` term.
- Liquid molar volume `v_i` is in the liquid enthalpy, so a pump's work follows from `h`. There are
  **no formation enthalpies**: with components A, B, C sharing one `c_p` and a zero liquid reference,
  any A → B reaction has zero liquid-phase heat of reaction under today's reference convention.

**What T02–T04 leave to T05, or constrain for it.**
- T02 A02: a region containing a unit without EO derivatives must fail with a capability error, not
  a nested loop.
- ADR 0005 (the phase-attempt contract) governs every phase-selecting unit.
- ADR 0010: PTC's `M` pattern is read from `holdup_balance` manifests.
- K04: every `CONVERGED` solve is certified against its bound declaration.
- The open K04 follow-up F9 (the fresh-flash tolerances at two-phase lifted streams) will bite any
  new two-phase unit's certificates. Know that it exists; do not resolve it here.

**Tests and evidence precedent.**
- K02: `tests/test_k02_{unit_models,heater_flash,mixer,flowsheet,syn001_provider}.py`.
- K02's manifest (`evidence/K02/1baaf03…`) covers ports, equation structure and accumulation,
  derivatives, initialization, validity, and closure against 20-digit references.
- The spec precedents with independent twins are T03 and T04:
  `docs/derivations/T0{3,4}-*-spec.md` with `docs/derivations/scripts/t0{3,4}_reference.py`.

## 4. Measured facts — do not re-derive

- The SYN-001 provider supports TP only; a PH request is refused `unsupported` today.
- The mixer's thermal closure is a bracketed scalar solve restricted to subcooled liquid.
- All five registered SYN-001 variants solve and certify, with the recycle-invariance metamorphic
  check (plan §3).
- The flowsheet has 49 rows × 47 variables.
- The A02 revisions show a freed outlet specification with a promoted downstream target working
  end-to-end (T02 A25; T04 A30).

## 5. Already decided — not open

- **Native equation models** (blueprint §5.1), declared by manifest, with every equation carrying an
  ADR 0008 accumulation declaration. There are no opaque models in T05.
- **State `nTP-v1`**, zero-flow semantics and sign conventions (ADR 0001).
- Units cannot see the flowsheet. Structural redundancy is eliminated centrally (R-011), never
  inside a unit.
- Lifted two-phase variables are named after the stream (R-008). Phase-selecting units follow ADR
  0005.
- Cross-unit specifications promote to EO (A02). Equilibrium reactors and elaborate equipment modes
  are out of v0.1.
- Frozen interfaces and schemas change only by ADR.
- No placeholder success paths: an unsupported specification or domain is a typed refusal.

## 6. Genuinely open — what you decide

1. **PH flash.** Is it a provider capability (`flashes` gains `"PH"`), a unit-level formulation (the
   TP kernel plus an enthalpy row with T free), or both?
   - Decide: the bracketing, single-phase endpoints, zero components and the regime-aware
     derivatives.
   - Decide: whether SYN-001's mixer is generalized onto it, and how existing SYN-001 results stay
     bit-identical.
   - Decide: which provider or interface changes need an ADR.
2. **Conversion reactor.**
   - Stoichiometry and the key-component conversion specification.
   - The heat of reaction, under which reference convention. SYN-001 has no formation enthalpies, so
     decide whether T05 adds synthetic formation data (an ADR and a new reference convention) or
     registers a thermoneutral reactor honestly.
   - Isothermal vs adiabatic vs duty-specified modes; the domain of conversion; and the phase of the
     outlet (TP-state outlet like the heater?).
3. **Component separator.** Split-fraction specification per component; outlet T/P and phase
   treatment; the energy row; its degrees of freedom and zero-flow outlets.
4. **Valve.** An isenthalpic pressure drop requires PH. Decide the specification (outlet P or ΔP),
   the direction constraint and flashing across the valve.
5. **Liquid pump.** Its work from `h` (the `v_i(P − P_r)` term), efficiency, and the refusal of a
   vapour or two-phase inlet (a typed failure), with the sign of shaft work.
6. **Two-stream heat exchanger.**
   - One formulation for v0.1: duty-coupled with a specification (outlet T, duty or approach), or
     UA–LMTD, with a temperature-cross refusal.
   - The two sides' phase changes, degrees of freedom, and how it enters a recycle (a coupled case).
7. **Per-model definition of done (V12).**
   - The contract: ports, equations, parameters and DOF.
   - Limiting cases: zero flow, single component, the domain edges, conversion 0/1, and the
     split fraction at 0 or 1.
   - Failure tests, and balance and derivative evidence.
   - At least one coupled case per family, i.e. inside a flowsheet (e.g. a SYN-001 extension), with
     independent expected values.
8. **Registered cases and the registry.** Families and classes, which cases enter T06's success
   denominator, and independent references. Decide whether SYN-001 grows new variants or a new
   synthetic family is registered.
9. **Anything that touches K04.** The checks a certificate needs for each new unit's balances and
   specifications (a pump's shaft work, a reactor's extent). Say what the verifier must add. The
   build lane implements it.

Where a question turns on a preference only Frank holds (scope, a public name, chemistry data), give
a recommended default and proceed (T03/T04's pattern).

## 7. How the answer will be verified

As in T03 and T04:
- An **independent twin**, `docs/derivations/scripts/t05_reference.py`, in multi-precision,
  importing nothing from `process_runtime`/`benchmarks` (checked by AST).
- It emits `benchmarks/t05/reference_values.yaml` byte-identically on re-run, with `--check`
  self-checks. The YAML's SHA-256 goes in the spec header.
- Each registered number carries a margin argument showing it sits far above the 53-bit floor.
  T04's rulings (F13–F15) showed that tolerances set below that floor cost a review round. State
  each tolerance's floor argument up front.
- The build lane implements against numbered assertions `T05.A00…`.
  `scripts/t05_evidence_manifest.py` measures each in process against the YAML. R0 fields go into
  the K05 identity document for the CI pair. `reviewer` reviews.
- Existing SYN-001 results (K02–T04 fixtures and manifests) must remain bit-identical unless you
  explicitly re-register them, with the reason.

## 8. Deliverable shape

1. `docs/derivations/T05-unit-models-spec.md`. For each model: its equations with signs and
   reference states, specification and DOF table, accumulation declarations, derivative
   declarations, validity domain, typed failures, and initializer. Then the registered cases, the
   assertion catalogue with the authority of each expected value, what is not established, open
   questions with defaults, and a **work order** (W0 measurements flagged).
2. `docs/derivations/scripts/t05_reference.py` and `benchmarks/t05/reference_values.yaml`.
3. An ADR (next free number, **0011**) if a frozen interface, a schema, the provider capabilities
   or the SYN-001 reference convention changes. It states the migration and the bit-identity
   evidence for existing results.
4. `docs/decision-register.md` entries (next free id after R-035) for each choice with a plausible
   rejected alternative.
5. The registry entries you want. The build lane writes the YAML revisions.

## 9. Out of scope

- Equilibrium and kinetic reactors, and elaborate equipment modes (plan: deferred).
- Real chemistry and property data (T08/v0.2).
- Entropy/PS flash (blueprint §6.2: only when equipment needs it; state it if the pump or valve
  does).
- Resolving K04 F9.
- T06's case count and robustness generators.
- Performance at plant size.
- Human numerical and process-modelling sign-off.
