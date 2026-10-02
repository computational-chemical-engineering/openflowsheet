# Brief — T08 build-first specification: a PTC-qualifying holdup CSTR (V14 b) and compatible warm starts (V13 e)

**To:** `specifier` (design lane). **From:** build lane, 2026-09-29. **Branch:** `wp/T08` (HEAD after this
brief is committed). **Deliverable:** `docs/derivations/T08-build-first-spec.md`, and the machine-readable
pieces listed in §8. Write no production code. Do not commit.

**Budget note.** Frank is near his weekly usage limit. This is the single design-lane pass before a pause.
Be complete but economical: do not re-derive what T04 and K03 already registered; cite them. If one of the
two parts needs a separate `architect` pass (software design you judge out of your remit), say so in the
note and frame that pass's question instead of doing it.

## 1. The question

Specify, so that the build lane can implement and `verdict` can judge without further design, (A) the kinetic
CSTR with holdup that lets T04's **preregistered** PTC-R1 case qualify one PTC family under V14 (b), and
(B) **compatible warm starts** (blueprint §7.4 source 2) so that V13 (e) is met.

## 2. Why the design lane

(A) is a new unit model's residual and derivatives, its PTC mass mapping (route a of blueprint §7.5) and a
qualification comparison whose criterion must not move after the result. (B) touches initialization
policy, the RunManifest and **replay identity**, and possibly the frozen application contract
(ADR 0019). Both are CLAUDE.md design-lane subjects (residuals, derivatives, globalization, replay identity).

## 3. Frank's decisions (2026-09-29) — not open

- **F1 → build first.** v0.1 is not tagged with V14 (b) recorded FAIL; the holdup CSTR route is built in T08
  (the T08 spec's option (ii), `docs/derivations/T08-release-spec.md` §4.4).
- **F2 → build first.** Warm starts are built in T08 (option (ii), spec §4.3).
- **F3 → the ammonia loop** is the V19/M01 chemistry. Not part of this pass; do not design the ammonia reactor.
- **F4 → approved:** the `t07` identity key may move by substitution only for D2/D3 (spec §6.2). Separate
  from this pass.
- Standing directives: fewest limitations; robustness with recorded fallbacks; "a fallback may change the
  method, never the problem"; no relaxed checks; a failed gate stays failed.
- The outcome of (A) is **not known in advance**. If PTC-R1 does not meet its preregistered criterion, V14 (b)
  stays FAIL and is reported as such. The spec must make that outcome as clean to judge as a pass.

## 4. Current state (excerpts)

### 4.1 V14 (b) criterion — T08 spec §4.4, fixed (R-118)

> A family is qualified for V14 iff **all** hold: (b1) T04 §8.1's criterion, **unchanged**: route (a) holds
> and, on the registered comparison, the set of starts from which PTC reaches the registered root is not
> contained in damped Newton's, under the same contract, tolerances and budgets; (b2) the comparison case —
> its starts, criterion and budgets — was committed before any PTC result on it existed (git order is the
> evidence); (b3) the family is selectable, by a registered policy, on a flowsheet inside the v0.1 envelope
> (§5): a family no supported flowsheet can select is not a v0.1 capability; (b4) SER tested (T04 A19–A22).

> Meeting (b3) needs a kinetic CSTR with holdup as a unit model, its mass-mapping derivation (route a), the
> preregistered comparison, and review: about one to two weeks, outcome not known in advance.

### 4.2 PTC-R1 — T04 spec §8.4 (`docs/derivations/T04-globalization-spec.md:388–392`), preregistered

> **PTC-R1, the exothermic CSTR** (the example blueprint §7.5 cites): the dimensionless first-order
> irreversible reaction in a cooled CSTR (Uppal, Ray and Poore's form with γ → ∞),
> `ẋ₁ = −x₁ + Da (1 − x₁) e^{x₂}`, `Le ẋ₂ = −x₂ + B Da (1 − x₁) e^{x₂} − β x₂`, holdups by the same
> residence-time principle (`M = diag(1, Le)` in dimensionless form), `Da = 0.072`, `B = 8`, `β = 0.3`,
> `Le = 1`: three steady states at `x₂ = 1.050 778, 1.490 217, 5.935 976`, the middle a saddle (eigenvalues
> −0.9227 and +0.2405 of the physical Jacobian), the outer two stable (generator-checked,
> `ref.closed_form.ptc_r1_cstr_preregistered`); starts on the 21 × 21 grid of `[0, 1] × [0, 8]`.
> **Criterion:** as §8.1, plus: PTC never reports the middle (saddle) steady state from a start off its
> stable manifold, and the step matrix's singularity at `Δτ = 1/s₊ = 4.16 θ` (the saddle's unstable rate
> `s₊ = 0.2405/θ`) is registered as the mechanism. The owner is the first package that registers a reactor
> with holdup (v0.2's reactor replacement, or T05 if its conversion reactor gains a holdup); T04 builds
> nothing for it.

T04's existing PTC machinery (T04 spec §6): `M dx/dτ = −F̃`, `PTC_ROW_SIGN` keyed by `row_accumulation`
(`holdup_balance → −1`, `zero_holdup_balance → +1`, `algebraic → +1`); holdup = residence time × phase-resolved
outflow content; energy holdup is the enthalpy content `H = U + PV` at pinned pressure (T04 §6.2); `M` from
`holdup_balance` rows only (ADR 0008 D4.5); θ = 1 s; SER controller and polish (T04 W5); selection by
`SolvePolicy.globalization.eo_core = "ptc"` for every attempt of every region solve except edge 3's recovery
(T04 §6, amended F15); **no automatic path selects PTC**. T04's flash/heater family: derived, not qualified
(18/18 both methods at r = 0.95, PTC 1.9–8.8× costlier; structurally cannot rescue PHS-05). T05 has a
**conversion reactor** (no holdup, no kinetics) in the v0.1 unit library.

### 4.3 V13 (e) — T08 spec §4.3

> (e) **compatible warm starts** (§7.4's second source: a prior run's state offered as an initial candidate
> for a compatible problem, checked like every other candidate). … K02's **warm-start cache** (§6.4, D10:
> property-level hints that are never an exact answer) is a different mechanism and does **not** satisfy (e).

> *Options (F2)* … (ii) build them in T08: an `architect` design note (explicit source — a named prior
> bundle's `solution-state.json` — or automatic from the store; how the source enters the RunManifest and
> replay identity; whether the frozen `Application.solve` needs a sibling operation, which is an ADR 0019
> amendment), then one build increment and a `reviewer` pass: about one week, and it touches replay identity.

Blueprint §7.4: "Use user guesses, compatible warm starts, local model initializers, upstream propagation, and
physical nominals in that order, while checking every candidate. Initializer projection is logged and does not
rewrite fixed specifications."

K03 spec §10.1 (`docs/derivations/K03-solver-spec.md:318`): the initializer chain table; source 2 "compatible
warm start — none in v0.0 (no run history) — recorded absent"; every candidate checked by one traversal,
rejections logged as `initializer_rejected`, `INITIALIZATION_FAILED` lists every rejection. The policy field
`initializer_chain: tuple[str, ...]` (K03 spec :398, :413). K03's manifest carries `unsupported`
`K03.initializer_chain`. T07 hand-on **S-G**: GUESS roles (user guesses) are not bound on the revision path
(envelope L10, backlog B5 "with warm starts if F2 (ii)").

T07 infrastructure available: bundles contain `solution-state.json` (frozen schema `solution-state`); the
store (SQLite) holds runs and bundles per project; `LocalApplication` + one `OPERATIONS` table dispatched by
Python/CLI/HTTP/MCP (ADR 0019, frozen Application four + `JobControl` + `Inspection`); revision runs
(ADR 0020, routes `revision_eo`/`legacy_eo`). Design `docs/design/T07-jobs-and-bindings.md`.

## 5. Constraints and invariants

- Every registered result and identity key stays as registered: K05 minus-`t07` `9a7b4e6d…`, T02 floats
  `9a8a5baf…`, structural `915c97e8…`, keys `t02`…`t06`; `t07` moves only by the approved D2/D3 substitution.
  **With no warm start supplied and no CSTR in the flowsheet, every existing run must be byte-identical.**
- `requirements.lock` must not change (it would demote every registered replay bundle).
- Frozen interfaces (plan §2.1) and schemas (§2.2) change only by ADR; ADR 0019 changes by amendment.
  0021 and 0022 are taken (Proposed); **0023 is the next free ADR number**.
- A warm start may change the **method** (the starting point), never the **problem**: it cannot rewrite fixed
  specifications, bounds or tolerances, and a warm-started root is certified exactly as a cold one.
- Replay: a warm-started run must be reproducible from its bundle alone (the source state must be inside the
  bundle or content-addressed from it) — say which.
- The agent-facing MCP surface: V17 is carried from T07 only if that surface is unchanged (Frank's F5,
  pending). If (B) must change it, say so explicitly and state the smallest change; do not avoid a necessary
  change to protect the carry.
- CSTR components: the v0.1 envelope's property model is SYN-001 (synthetic ideal). A kinetic CSTR inside the
  envelope must use it or a registered extension; the dimensional model must map **exactly** onto PTC-R1's
  dimensionless form so the preregistered case is the one run (b2). The rate law is synthetic, not a real
  chemistry claim.

## 6. Genuinely open — decide these

A1. The kinetic CSTR unit model: states, residual rows and their `row_accumulation` classes, the reaction
    source term, energy balance with cooling (β), the dimensional parameterization that realises
    `Da = 0.072, B = 8, β = 0.3, Le = 1` exactly, derivatives, zero-flow semantics, and its definition of done
    (V12's per-model DoD, as T05).
A2. The flowsheet that exercises it inside the envelope (feed → CSTR → product at minimum), and the registered
    policy by which PTC is selected on it (b3), consistent with "no automatic path selects PTC".
A3. Route (a) for this family: the mapping `M`, `PTC_ROW_SIGN` rows, steady-state equivalence, dimensions,
    reference invariance — reuse T04 §6 wherever it applies unchanged.
A4. The comparison: map T04 §8.4's 21×21 grid, criterion, tolerances and budgets onto the dimensional model
    **without changing them**; if anything in §8.4 is under-determined (e.g. Newton's damping/budget on this
    model, how "reaches the registered root" is decided, the start grid in dimensional coordinates), resolve it
    now, before any result, and say so. Include the saddle clause. State the git-order evidence for (b2).
A5. Independent expected values (twin / closed form) for the three steady states, the saddle eigenvalues and the
    singularity `Δτ = 4.16 θ`; what the build lane must reproduce.
B1. The warm-start source: explicit (named prior run/bundle) vs automatic (store lookup) vs both; the
    **compatibility** test (what makes a prior state compatible: same variable set / structure / component
    list; tolerance on differing specifications?), and what happens on incompatibility (typed rejection,
    next source — never a failure of the run).
B2. Where it enters the chain (§7.4 order, after user guesses), how it is checked (the same traversal check),
    projection logging, and its record in the RunManifest and replay identity (classify every new field
    R0/R1/R2 per ADR 0010 / D20).
B3. The contract surface: a parameter on existing operations or a sibling operation; ADR 0019 amendment text;
    the MCP/HTTP/CLI exposure; the effect on V17's carry.
B4. Whether S-G (GUESS roles on the revision path) is closed with it or stays backlog; recommend.
B5. The V13 (e) judging evidence: which tests show the source is used, rejected when incompatible, and never
    changes the problem (e.g. warm and cold runs reach the same root on registered cases; a warm start from a
    different case is rejected or reaches the certified root; replay of a warm-started bundle MATCHes).

## 7. How it will be verified

The build lane implements; `./scripts/check.sh` (ruff, mypy strict, pytest) and CI on x86-64 and aarch64; the
identity checks above; a `reviewer` pass (it touches residuals, derivatives, globalization and replay
identity); `verdict` judges V13 and V14 against your criteria at the release candidate.

## 8. Deliverable

`docs/derivations/T08-build-first-spec.md` with: Part A (A1–A5) and Part B (B1–B5); numbered falsifiable
assertions (prefix `T08.B…` or another prefix not used in the T08 spec's §9 catalogue); a reference generator
`docs/derivations/scripts/t08_build_first_reference.py` with `--check`, writing
`benchmarks/t08/build_first_reference.yaml` byte-reproducibly (follow `t08_reference.py`'s pattern); ADR 0023
draft(s) (Proposed) for the contract/identity changes, and the text of an ADR 0021 revision reflecting
build-first (F1/F2 answered: D3 no longer carries V13 (e) / V14 (b) as FAIL); register entry text; open
questions with recommended defaults; a build-lane work order in increments with the tests each must pass and
where `reviewer` enters.

## 9. Out of scope

The ammonia/PyMRM reactor (M01), the nonideal property route, the web shell (M06), D1–D3 fixes, the release
candidate mechanics (T08 spec §8), qualifying the flash/heater family (T04 closed it), and any real-chemistry
claim about the CSTR.
