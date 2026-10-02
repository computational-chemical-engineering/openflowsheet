# Review brief — K02: the property layer, the caches, and the six SYN-001 unit models

**To:** `fable-reviewer`
**From:** Opus 5, 2026-09-20
**Branch:** `wp/K02`, merged and pushed to `main` through `d70f784`
**Gate:** `PATH=.venv/bin:$PATH ./scripts/check.sh` — green, **997 tests**
**Evidence:** `evidence/K02/d70f7847f1f8119d2254dbd4bdb5d72bc183b19a/manifest.json` — `tested`,
16 pass, 1 unsupported, 1 not applicable, `review.numerical` and `review.process_model` `pending`

---

## 1. What was built, and against what

K02's deliverable (plan §4.2): *"SYN-001 provider and feed/product/mixer/heater/flash/splitter;
exact cache and separate warm-start cache."* Acceptance evidence: *"Nominal, single-phase,
zero-flow, cache on/off and perturbed-input tests; documented phase properties and
initialization."* Package constraint (§4.2): *"heater and flash share one TP-state kernel (§3.2).
The mixer outlet closure is restricted to the subcooled-liquid domain with a typed failure
outside it. Do not implement a general PH flash in v0.0."*

There was **no Fable design pass** for the unit models, deliberately. The equations are not
K02's to choose: `docs/derivations/SYN-001.md` §4 states them, **ADR 0008 D3.5** fixes every
row's accumulation kind in a normative table, and P01's six `ModelManifest` documents in
`tests/fixtures/schemas/model_manifest/valid/` fix the ports, statements, dependencies, domains
and limitations. Project CLAUDE.md puts "unit-model implementation from Fable-approved equations"
in Opus's lane. **This review is the one Fable pass for the package.**

New modules, all under `src/process_runtime/`:

| Path | What it is |
| --- | --- |
| `models/__init__.py` | The `UnitModel` contract, manifest emission, id conventions, `assemble` |
| `models/syn001/tp_state.py` | The shared TP-state kernel: procedural, plus its lifted EO form |
| `models/syn001/blocks.py` | `LnKBlock` and `EnthalpyFlowBlock` |
| `models/syn001/{feed,sink,splitter,heater,flash,mixer}.py` | The six models |
| `models/syn001/flowsheet.py` | The seven-stream flowsheet, `spec()` and `traverse()` |
| `compile/reference.py` | A float evaluator for a `ProblemSpec`'s rows. **Not a backend** |
| `thermo/{__init__,syn001,cache}.py` | Contract, provider and caches (earlier in the package) |

## 2. The measurements

Worst over all five registered variants, against Fable's 20-digit
`benchmarks/syn001/reference_values.yaml`, at the tolerances ADR 0001 D6 registers for SYN-001:

| Check | Measured | Tolerance |
| --- | --- | --- |
| Tear residual `R(t*) = G(t*) − t*` | 3.6e-15 mol/s | 3.1e-8 |
| Heater and flash duties | 1.8e-9 W | 1.01e-3 |
| Mixer outlet temperature | 5.7e-14 K | 1e-6 |
| Vapour product component flows | 1.4e-15 mol/s | 3.1e-8 |
| Fresh feed = vapour product + purge | 1.6e-15 mol/s | 3.1e-8 |
| `Q_h + Q_f` = products − fresh feed | 1.2e-10 W | 1.01e-3 |
| Recycle invariance across r | 2.7e-15 | 3.1e-8 / 1e-10 |
| Every assembled row at the reference solution | 5.5e-12 | 1.01e-3 |
| Compiled residual vs the float route | **0.0** | — |
| `R(s t*)` vs `(1−r)(1−s) t*`, s ∈ [0, 4] | 1.1e-14 relative | — |
| ADR 0008 D4.3 | `HEAT-mole` **+0.5**, `MIX-mole` **−0.5** | exact |
| Cache on vs off | bit-identical; warm pass reached the provider **0** times | — |

Mutation sweeps: **14 + 22 + 15 + 14 = 65 of 65** caught for the unit models, after seven
survivors across the four passes exposed six real test gaps (listed in `docs/K02_DECISIONS.md`).
The caches were swept earlier at 12 of 12.

## 3. The decisions I most want challenged

**(a) The heater's two-phase outlet is lifted, not solved inside a block.** Three of the five
registered variants have a two-phase heater outlet, so `HEAT-duty` needs the enthalpy of a stream
whose split is not a flowsheet variable. I lifted the split into `S3.vap.i`, `S3.liq.i`, `S3.V`,
`S3.L` with the equilibrium form P02 already uses — `v_i L − K_i l_i V` — plus five
unit-authored `algebraic` lifting rows. The alternative was an opaque block running an inner
Rachford–Rice solve and returning the implicit derivative of blueprint §5.1.

*My reasoning:* plan §4.2 requires the heater and flash to share one TP-state kernel, and the
flash's split is lifted in the Fable-authored P02 spec, so the heater's should be too; and
blueprint §5.1 warns that "a derivative through an incompletely converged algorithm is not
automatically the derivative of the intended model". *What I am unsure about:* whether adding
eight variables and eight rows per two-phase-capable unit is the right trade for K03's solver,
and whether the lifted form's spurious roots (V = L = 0) will bite there.

**(b) The mixer gates on enthalpy rather than on a phase label.** The registered recycle is the
flash's own saturated liquid, so `Σ z_i K_i` = **1.0000000000000002** in double precision and the
provider — correctly, by its registered classification order — calls it `TWO_PHASE` with
β = 1.3e-17, while the 20-digit reference registers `recycle_phase_signature: LIQUID`. A
label check rejects the **nominal** variant. So the mixer admits a stream as liquid when its
liquid enthalpy differs from its true TP-state enthalpy by less than ADR 0001 D6's **registered**
energy tolerance: the saturated recycle misses by 6e-13 W, an equimolar feed at 347.45 K misses
by 29.4 W and is refused.

*What I want judged:* whether using a registered energy tolerance as a phase-admissibility
criterion is sound, or whether this is a relaxed check wearing a registered number's clothes.
This is the single decision in K02 I am least certain of.

**(c) The property package reaches identity through the label.** ADR 0008 D4.1 left the thirteen
SYN-001 constants hashed by nothing. They cannot enter `constants_sha256`, which hashes pinned
inputs and those are floats, so the flowsheet label now names the provider id and twelve hex
digits of each of its two declared hashes, and they reach `model_version` that way. *Is the label
the right carrier, or does this want an ADR amending D4.1?*

**(d) Causal sensitivities all stay `unavailable`.** P01 declared every derivative `unavailable`
because nothing was implemented. K02 implements the models and still exposes no sensitivity
interface, so `d(recycle.n)/d(inlet.n)` stays `unavailable` even though the splitter is linear
and the answer is literally `r`. Only a new `residuals / free_variables / ad` entry is added.
*Too conservative?*

## 4. Three findings I am handing forward rather than fixing

1. **The registered tear initializer is outside the v0.0 mixer's domain.** Derivation §9
   registers `recycle_i = r F_i`, and plan §3.2 fixes that stream at the flash temperature. At
   r = 0.5 that is an **equimolar stream at 360 K**, above its 347.44 K bubble point
   (`sum_zK_fresh` = 1.3837 in the reference's own values). The mixer refuses it, so a damped
   Newton started there fails on its first residual evaluation. I did not loosen the mixer.
   **Does the registered initializer need amending, or is this squarely K03's §7.4 problem?**

2. **The declared rows over-determine the pressure network by two.** Seven pressure variables,
   nine declared pressure rows: `FLASH-P` imposes the specification on its own inlet as well as
   both outlets while the chain upstream already fixes it, and the recycle loop closes the
   network. Every one of those rows is in a manifest. I assembled them as declared.
   **Is that the right call, or should a unit elide a row it can see is redundant?**

3. **The saturated-recycle classification** above will reach K03's phase-attempt controller,
   where the decision is about which active set to try rather than about an enthalpy, so the
   mixer's remedy does not transfer.

## 5. What I would most like you to look at

- **The equilibrium row's behaviour at a vanished phase.** `v_i L − K_i l_i V` is exact at V = 0
  and at L = 0, which is three of the five variants, but the row is then satisfied by a whole
  family of states. Is that a problem K03 inherits, and should K02 say more about it?
- **The bracket argument in the mixer** (`models/syn001/mixer.py`, module docstring): I claim
  `[min T_in, max T_in]` brackets the closure for *any* provider whose liquid enthalpy increases
  with temperature, given all inlets admissible-as-liquid. Is the claim as general as I state it?
- **Whether `R(s t*) = (1−r)(1−s) t*`** is derived correctly in `docs/K02_DECISIONS.md`. It
  measures at 1.1e-14 across four variants and eight scale factors, and I want the derivation
  checked rather than the numbers trusted.
- **Whether `tested` is the right status** for the six manifests and whether `implemented` is
  right for D08 and D10 (both name a later package whose half does not exist).

## 6. What not to spend time on

- Packaging, lint, typing, CI, the schema machinery — all Opus's and all green.
- The canonicalization and identity encoding: ADR 0002, already reviewed and applied.
- The backend choice: ADR 0003, closed.
- Restating that SYN-001 is synthetic. Every manifest and the evidence limitations say so.
- Solving the tear. Plan §4.2 gives that to K03 and the evidence records it `not_applicable`.

## 7. Deliverable

A review note at `docs/reviews/K02-review.md` with: must-fix defects, should-fix items,
observations, and an explicit verdict on decisions (a)–(d) and findings 1–3. Do not set
`review.numerical` or `review.process_model` in any manifest — human sign-off is recorded
separately and is not an agent's to claim.
