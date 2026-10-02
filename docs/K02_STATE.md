# K02 — campaign state

**Rewritten in place, never appended.** A position, not a diary. History is in
`docs/K02_DECISIONS.md` (append-only) and in the git log.

| | |
| --- | --- |
| Objective | Property-provider plumbing, the two caches, and the six SYN-001 unit models (plan §4.2 row K02) |
| Branch | `wp/K02`, merged and pushed to `main` at each milestone per Frank's standing instruction |
| Gate | `PATH=.venv/bin:$PATH ./scripts/check.sh` — **green at 1017 tests** (645 when K02 began) |
| Lead | Opus. **Fable review complete** (`docs/reviews/K02-review.md`); three must-fixes and five should-fixes acted on |
| Manifest | `evidence/K02/1baaf03…/manifest.json`, `tested`. 19 pass, 1 unsupported, 1 not applicable |

## Where we are now

**K02 is functionally complete.** Five milestones merged:

1. **The PropertyProvider contract** — blueprint §6.1 as a checklist, every field required, no
   status value meaning "extrapolated".
2. **The SYN-001 provider** — a separate transcription from `benchmarks/syn001/oracle.py`.
3. **The two caches** — `ExactPropertyCache` and `WarmStartCache`, which returns a `FlashGuess`
   and deliberately not a `FlashResult`. 12 of 12 mutations caught.
4. **The six unit models** — feed, sink, splitter, the shared TP-state kernel with heater and
   flash, and the mixer. Each carries a declaration re-transcribed from P01's manifest and
   compared against it field by field, a set of residual rows, and a causal evaluator.
5. **The flowsheet** — all six wired together, assembled into one 47-variable, 49-row
   `CompiledProblem`, and traversed sequentially to produce the tear residual.

### The numbers that matter

Worst over all five registered variants, against Fable's 20-digit references:

| | Measured | Registered tolerance |
| --- | --- | --- |
| Tear residual `R(t*)` | **3.6e-15** mol/s | 3.1e-8 |
| `R(s t*)` vs `(1-r)(1-s) t*` | **1.1e-14** relative | — (derived, not registered) |
| Heater and flash duties | **1.8e-9** W | 1.01e-3 |
| Mixer outlet temperature | **5.7e-14** K | 1e-6 |
| Overall component balance | **1.6e-15** mol/s | 3.1e-8 |
| `Q_h + Q_f` vs products − feed | **1.2e-10** W | 1.01e-3 |
| Every assembled row at the reference solution | **5.5e-12** | 1.01e-3 |
| Compiled vs float route | **0.0** | — |
| ADR 0008 D4.3 | `HEAT-mole` **+0.5**, `MIX-mole` **−0.5**, exact | exact |
| Mutations caught | **80 of 80** across five sweeps (14, 22, 15, 14, 15); **12 of 12** earlier for the caches | — |

### What the Fable review changed

Three must-fixes, each verified independently before acting, each real:

1. **The heater's lifted equilibrium rows were never evaluated at a two-phase state.** Every
   reference-state test used the nominal variant, where `S3.V` is zero and the row is identically
   zero *for any K at all* — dropping the K-value entirely passed 1003 of 1003 tests. Now
   parametrised over all five variants, three of which have a two-phase heater outlet.
2. **The mixer's admissibility bound was extensive and admitted a wrong number.** A 45%-vapour
   inlet at 1e-8 mol/s slipped under a watts bound and the mixer returned `ok`, `LIQUID`, outlet
   **330.0 K where the true closure gives 393.9 K**. The criterion is now the enthalpy gap divided
   by `dH/dT` against the registered **1e-6 K**, shared by the heater and the mixer.
3. **The label carried pinned inputs**, violating ADR 0008 D4.1's "`model_version` identifies
   equation structure and backend form only" and overflowing ADR 0002's 64-character cap at an
   unremarkable parameterization.

A method failure of mine is recorded with them: my first confirmation of (1) used a pattern that
no longer matched the formatted source, so the mutation was never written and the run proved
nothing — and I repeated the error confirming the fix. Every mutation script now asserts the
substitution landed.

### Four findings handed forward

1. **The registered tear initializer is outside the v0.0 mixer's domain.** Derivation §9's
   `recycle_i = r F_i` at the flash temperature is equimolar at 360 K, above its 347.44 K bubble
   point, so a damped Newton started there fails on its first residual evaluation. **K03**
   (blueprint §7.4 initialization and homotopy).
2. **The registered recycle is saturated.** `sum z_i K_i` = 1.0000000000000002 in double
   precision, so the provider says `TWO_PHASE` with β = 1.3e-17 where the 20-digit reference says
   `LIQUID`. The mixer gates on enthalpy for that reason. **K03's** phase-attempt controller meets
   the same boundary, where the decision is about an active set rather than an enthalpy.
3. **The declared rows over-determine the pressure network by two.** Seven pressure variables,
   nine declared pressure rows. Every one is in a manifest; K02 assembles them as declared.
   **K03/T01** structural analysis (blueprint §7.2).
4. **The lifted equilibrium admits the classical trivial solutions.** Every `v_i = 0` and every
   `l_i = 0` satisfy `v_i L - K_i l_i V` identically. Measured: at the once-through variant's
   two-phase heater outlet the all-liquid split leaves **thirteen of fourteen heater rows at
   exactly 0.0**, and a solver free to choose `Q` closes the fourteenth at a duty **8237.85 W**
   below the true one. No residual can exclude it. **K03** — initialization on the physical
   branch plus a final phase-admissibility check (blueprint §6.3, §7.1).

## Next action

**K02 is done.** The next package is **K03** (physical scales before initialization; damped Newton
on the analytic and flash recycle residuals; bounded line search and phase attempts — plan §4.2),
whose *Model* column is Fable / Opus, so the scaling and globalization policy is Fable's to
specify before implementation.

Two items left deliberately undone, each recorded in the evidence limitations:

- **The duplicated row builders (review S4).** Six builders appear in two to four modules, and the
  M1 defect hid behind that duplication. Consolidation changes no numerics but touches every unit,
  and this repository does not change numerics while changing structure, so it belongs in its own
  commit proved bit-identical. A good opening move for K03.
- **Amending derivation §9's tear initializer (review finding 1).** The reviewer's call is to
  register `t⁰ = G(0)`, which is in-domain for every r, and said they would apply it as a separate
  Fable commit. It is a Fable-authored derivation and not mine to change.

## Gates and their current numbers

| Gate | Now |
| --- | --- |
| `scripts/check.sh` | green, 997 tests |
| SYN-001 tear residual at the reference recycle | 3.6e-15 mol/s, five variants |
| SYN-001 duties vs the 20-digit references | 1.8e-9 W, five variants |
| ADR 0008 D4.3 | discharged, both values exact |
| G00 (three-component process, all v0.0 units, one numerical tear) | **units and residual done; the tear is not solved** — K03 |
| Second platform (G05) | **not run** — K05 owns it |
| CI | **has never executed** |

## Open decisions, with their defaults

| # | Question | Default taken |
| --- | --- | --- |
| 1 | `PropertyCapabilities` schema | Still deferred. Nothing in K02 serializes one, and the rule is that a schema arrives when a document carries its object |
| 2 | Are the six manifests `tested`? | **Yes.** Implemented, and exercised by the gate against independent 20-digit references at every registered variant. `manifest_document` now refuses to write `reviewed` or `released` at all |
| 3 | D08 and D10 requirement status | **`implemented`, not `tested`.** Both name a later package (M01 real-provider conformance, M02 cache under a real solve) whose half does not exist; calling them `tested` would claim that work |
| 4 | Where the SYN-001 physical constants reach identity | Through the **label**, hence `model_version` — `constants_sha256` hashes the pinned inputs and those are floats. Closes the K02 half of ADR 0008 D4.1 |
