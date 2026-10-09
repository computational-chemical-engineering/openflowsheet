# Decision register

What was chosen, what was rejected, and why. One entry per decision a later session could
plausibly undo — especially one that departs from the obvious or textbook option.

**This file is not a diary.** Entries are short and stable: the decision, the rejected alternative,
the reason, the date, and a pointer to where the evidence and the normative text live. Narrative
belongs in `docs/progress.md`; normative content belongs in the ADRs and the derivations.

**How to use it.** Read the entry before changing anything it covers. Reversing a registered
decision takes a new, explicit decision recorded here, with what changed to justify it — never a
silent flip because the alternative looked natural on the day. The failure this file exists to
prevent is a later session picking the textbook-standard option because nothing in front of it said
the project had already rejected that option on purpose.

`docs/adr/` remains the normative authority. This register is the index that makes the ADRs
findable by the question they answer rather than by their number.

---

## R-001 — Transient extension: neutralize the lock-in points now, keep dynamics deferred

| | |
| --- | --- |
| Date | 2026-09-16 |
| Decided by | Frank Peters, after an architectural assessment by the Opus session |
| Normative text | `docs/adr/0008-transient-extension-readiness.md` |
| Brief | `docs/briefs/ADR-0008-transient-readiness.md` |
| Affected packages | K01, K02, K03, T04, T07 (and any package introducing a unit model; the first transient package) |

**Decision.** Dynamics stay deferred per blueprint §2.2. But the three provisions that would make a
later transient capability a *refactor* rather than an *extension* are fixed now, while `src/` is
561 lines and no unit model exists: (P-1) that time never reaches an evaluation — a time-varying
specification arrives as a pinned input; (P-2) what the `state_sha256` identity hash covers; (P-3)
that a unit model declares its own accumulation slot per conservation row rather than receiving a
centrally assigned mass matrix. ADR 0008 carries the rulings and the exact normative text.

**As ruled.** P-1 adopted-modified — the proposed `EvaluationContext.time` field was *rejected*;
the concern is closed by freezing the context's field set and the three method arities in an
executable test instead. P-2 adopted: the hash covers exactly the dense `x`, in `variable_ids`
order, after signed-zero normalization, and nothing else. P-3 adopted and made precise: a required
per-equation `accumulation` declaration in `ModelManifest` with three kinds and no default, plus
the balance-row sign convention `F_row = inflow − outflow + sources`. ADR 0008 carries four open
questions with recommended defaults (Q1–Q4). **Q1 — is the SYN-001 heater a holdup unit? —
was answered by Frank on 2026-09-16: yes.** The registered `holdup_balance` classification
therefore stands unchanged; Q1 is closed. Q2–Q4 are discharged by K01 and T04.

**Rejected alternative.** Defer all three with the rest of dynamics, and revisit when a transient
capability is actually scheduled.

**Reason.** The cost of P-3 in particular rises with every unit model written and is near zero
today; retrofitting an accumulation slot later means reopening every unit model. Blueprint D07
already requires an explicit equation-to-variable mapping and mass matrix for PTC, and plan
`docs/implementation-plan.md:255` already commits the first PTC family to the *physical holdup*
qualification route (a) rather than the artificial route (b). So the accumulation structure is a
v0.1 obligation regardless; the decision is only whether each unit owns its share of it. Making
that ownership explicit also discharges D07's "no generic diagonal-magnitude recipe is trusted by
default".

**What this does not establish.** It adds no dynamic capability, commits the project to none, and
relaxes no release gate. Blueprint §2.2 stands; a transient capability still requires its own ADR.

**Amendment 1 (2026-09-26; normative text: ADR 0008 "Amendment 1"; brief `docs/briefs/ADR-0008-A1-transient-readiness.md`).** Re-examined at ~37 000 lines against C1–C8 and two added candidates. **Adopted now:** the manifests' energy holdup stays the internal energy `U`, and the rigid SYN-001 vessels' dynamic energy rows are their steady rows; R-032's enthalpy content is a PTC pseudo-holdup no physical-time integrator may use (tests U1, U2); T04 finding F2's proposal to relabel the manifests "enthalpy content" is declined. **Constraint on T07 (J1–J3, J5 binding; J4, J6 recommended):** job outputs are a list of typed references, output events stream before the job ends, the operation is a closed request discriminator, and consumers ignore artifact and event kinds they do not know. **Registered for the first transient package, no code now:** holdup states in `x` in conservative form, so the physical mass matrix is a constant selection and `U = Σ_π H^π − P V` is an algebraic row; a dynamic unit is a separate model id sharing kernels, with the steady modules and kernels gated unchanged; property `v`, consistent with `h` and `lnK`, in a new provider, with `u = h − P v` formed in the unit layer; non-reversing pressure-driven flow in nTP-v1, liquid-full incompressible vessels being index 2; a phase change inside a step is an event; an explicit row→holdup-column map, absent when empty. **Excluded pending an ADR amending U1:** an isobaric free-volume vessel holding `H`. **Rejected:** a `dynamic` mode on the steady models; a `schedule` member now; a differential marker on variables; the `M(x) ẋ` form for physical time. No schema, Protocol, fixture or digest changed.

**Watch for.** A future session implementing PTC's `M` as a central diagonal recipe over the
assembled system. That is the specific regression this entry exists to prevent.

---

## R-003 — `CompiledProblem` backend: CasADi 3.8.0

| | |
| --- | --- |
| Date | 2026-09-17 |
| Decided by | Fable 5.1 (`fable-verdict`), applying plan §4.1's P03 decision rule to the P02 and P03 evidence |
| Normative text | `docs/adr/0003-compiled-problem-backend.md` |
| Brief | `docs/briefs/P03-backend-verdict.md` |
| Affected packages | K01, K02, K03, K05, M03, T08 |

**Decision.** `CompiledProblem` compiles to CasADi 3.8.0 through the P02 `casadi.Callback` + `MX`
composition, pinned, with the linear solve staying in SciPy SuperLU (D03) and no CasADi
`Linsol`/`nlpsol` plugin on any default path. K01 inherits eight obligations (ADR 0003 D5): ordering
by name in CCS, callback sparsity declaration, JVP/VJP as negotiated exact capabilities, Hessian
reported absent through opaque callbacks (never zeros), callback call accounting, ADR 0008 D4, no
backend import in the orchestrator, no vendored wheel bytes.

**Rejected alternative.** Pyomo 6.10.1 / PyNumero / ASL. Passes correctness and sparse composition;
fails installability as a pinned dependency (`AmplInterface.available()` `False` after
`pip install`; needs cmake, C and C++ compilers, setuptools; `build-extensions` exits 1); 2.5×
slower per Newton iteration at the boundary, 34× slower import, 28× slower compile, 2.4× resident
set at n = 17; no JVP/VJP; no inlined form; needs a row-sign adapter and a name permutation. Also
rejected: "neither", and treating METIS 4.0 as failing CasADi's distributability.

**Reason.** Hard criteria first: installability separates the routes on the measured platform.
Independently, the measured comparison favours CasADi and the tie-break clause would also. The
n = 17 Jacobian ratio is a point, not a scaling result, and the verdict does not rest on
extrapolating it.

**What this does not establish.** A synthetic 17-variable composition test; not a solver result, not
a real-flowsheet benchmark, not scaling, not empirical validation, not second-order capability, not
the second K05 platform, not human review, not the right to vendor the wheel.

**Watch for.** A session reviving the Pyomo route as a "fallback", enabling a CasADi plugin in the
METIS closure on a default path, changing the pin without refreshing the [A10] audit, or citing
ADR 0003 D2.1 as a scaling result. Reversal only by a new ADR naming which of triggers T1–T5 fired.

---

## R-004 — Distribution: pinned dependency and replay by reference; vendored bytes closed pending the METIS remedy

| | |
| --- | --- |
| Date | 2026-09-17 |
| Decided by | Fable 5.1 (`fable-verdict`); D3 (LGPL reading) and D2 (METIS disposition) flagged for Frank as Q1 and Q2. **Both now answered by Frank Peters: Q1 on 2026-09-17 (the LGPL is allowed), Q2 on 2026-09-22 (the default stands; R4 and R5 are not pursued).** No file changed for either — each records an answer, not a new decision |
| Normative text | `docs/adr/0006-distribution-data-rights.md` |
| Brief | `docs/briefs/P03-backend-verdict.md`; evidence `docs/p03-binary-audit.md` §1–§6 |
| Affected packages | K01, K03, K05, M03, T08 |

**Decision.** Mode A (source + `casadi==3.8.0` fetched from PyPI by the installer) is permitted with
an LGPL-3.0-or-later notice statement and pin discipline; mode C (replay bundles) references the
wheel by hash and never embeds it; mode B (container, installer, offline bundle, mirror) is not
permitted with the unmodified wheel until `libcoinmetis.so*` (918 624 B, METIS 4.0,
no-redistribution notice) is pruned from that artifact, the eight unresolved-notice objects
(5 723 463 B) are resolved, and a notice bundle from the wheel's 81 notices ships beside the bytes.
No default execution path may load any object in the METIS closure — a use restriction, not only a
redistribution one. K01 adds the notice statement; T08 owns the refresh and any mode-B bundle.

**Q1 — does blueprint §15's "no GPL-licensed components" line exclude the LGPL-3.0-or-later
`_casadi.so` closure? — was answered by Frank on 2026-09-17: no, the LGPL is allowed.** The
recommended default therefore stands, D3's reading is confirmed rather than provisional, and
**ADR 0003 trigger T4 can no longer fire on the LGPL ground**. No file changed as a result. It is an
interpretation of §15, not an amendment: the blueprint is untouched and its recorded hash still
matches. D3.2(3) still binds — going beyond CasADi's Python API re-opens D3 in a new ADR. **Q2, the
METIS disposition, remains open** with R1 applied as its default. Q1 is closed.

**Rejected alternative.** Treating METIS as a blocker for CasADi (over-reaction; would select a
route that fails installability); treating it as irrelevant because the route never loads it
(blueprint §15 forbids reading dormancy as permission); asserting toolchain-runtime terms from
general knowledge; adding the `LICENSE` file or relicensing the core to simplify D3.

**Reason.** The project ships none of the wheel's bytes in the mode the architecture uses; the
restrictive object is outside the route's `DT_NEEDED` closure; the vendored-mode remedy is a
three-file deletion, recorded in order with verification.

**What this does not establish.** No assertion of the project's own rights; not a legal opinion;
clears no unresolved item; opens no mode B; one platform, one date; not a supply-chain guarantee;
data rights beyond "unknown rights are not redistributable" are K02/M01/T08's.

**Watch for.** A session committing or publishing wheel bytes (a wheelhouse, a Docker image with the
unmodified wheel), embedding the wheel in a replay bundle, or enabling a CasADi plugin on a default
path without re-running reachability against `libcoinmetis`.

---

## R-005 — The core licence is Apache-2.0, not MIT

| | |
| --- | --- |
| Date | 2026-09-17 (the choice itself predates this entry; blueprint v3.1 §15 and D04 already record it) |
| Decided by | Frank Peters. Recorded, not decided, by the Opus session |
| Normative text | `docs/blueprint-v3.1.md` §15 and requirement D04. There is no ADR and none is needed: the blueprint already carries the decision |
| Affected packages | K01 (package metadata and notice statement), T08 (release-time licensing), R01–R02 |

**Decision.** The project's own core is licensed **Apache-2.0**. This entry exists because the
blueprint recorded the *choice* and nowhere recorded the *reason*, which is exactly the condition
under which a later session substitutes the more obvious option.

**Rejected alternative.** MIT. Also rejected: BSD-3-Clause, which shares MIT's gap.

**Reason.** Three, in order of weight.

1. **The patent grant.** Apache-2.0 §3 is an express patent licence from every contributor, with a
   retaliation clause. MIT has none — at best an implied licence whose scope is jurisdiction-
   dependent. For most software this is theoretical; here it is not. The code embodies process-
   engineering *methods* (PTC continuation, phase-attempt control, qualification routes), the field
   is patent-dense, and contributors are likely to arrive from companies and universities with
   active portfolios. §3 also runs the other way: industrial legal review of an open-source
   dependency is markedly easier with Apache-2.0 than MIT, which matters for a project whose stated
   references are industrial process simulators (D19).
2. **The NOTICE mechanism (§4).** The project already needs a conventional place for third-party
   attribution — the CasADi LGPL statement at K01 (ADR 0006 D5.1) and T08's mode-B notice bundle.
   Apache-2.0 supplies the convention; under MIT it would have to be invented. §4(b)'s
   modification-notice requirement also fits a project whose premise is explicit provenance.
3. **§5 contribution terms, §6 trademark non-grant, and §7–8's substantially fuller warranty and
   liability disclaimers** than MIT's single sentence. The last is not incidental for software whose
   outputs may inform equipment sizing.

**What MIT would have bought, and why it was not enough.** Brevity, and GPLv2 compatibility, which
Apache-2.0 lacks. The second is inert here: blueprint §15 already forbids GPL components in the
default install, so combination with GPLv2 code is not a path the project is keeping open. The real
ongoing cost of Apache-2.0 is the NOTICE obligation, which ADR 0006 D5 shows the project incurs
regardless because of CasADi.

**What this does not establish.** It does **not** assert that the project holds the rights to
distribute its contributions under Apache-2.0 — that confirmation and the copyright line are
Frank's, and the `LICENSE` file is deliberately still absent while `pyproject.toml` declares the
licence (blueprint §15; `docs/progress.md` "Notes for Frank" 2). It is not legal advice, and it says
nothing about the licences of dependencies, which are ADR 0006's.

**Watch for.** A session adding a `LICENSE` file on its own initiative, relicensing to MIT or
BSD-3-Clause for "simplicity", or dropping the `NOTICE` file as unused once K01 creates it.

---

## R-006 — Identity hashes encode IEEE-754 bytes, not `%.17g` text

| | |
| --- | --- |
| Date | 2026-09-18 |
| Decided by | Frank Peters, on the recommendation of the Fable review of K01 |
| Normative text | `docs/adr/0002-canonicalization-and-schemas.md` **D1 (ratified 2026-09-18)**. The implementation is `src/process_runtime/canonical.py`; the reasoning is in its module docstring |
| Brief | `docs/briefs/K01-implementation-review.md` §3 doubt 3 |
| Affected packages | K01 (done), K04, K05 (replay bundles store these digests), T08 |

**Decision.** `state_sha256` and `constants_sha256` are SHA-256 over the **big-endian IEEE-754
binary64 bytes** of the ordered values, signed zero normalized. `ENCODING_ID` is `ieee754-be-v1`.

**Rejected alternative.** The P02 composition specification §10.4 text encoding — `%.17g`,
comma-joined, UTF-8 — which K01 first promoted precisely because it was already fixed and had two
independent implementations agreeing on it.

**Reason.** Two, in order of weight.

1. **A text encoding puts an implementation-defined formatter inside replay identity.** `%g` is
   C's; its trailing-zero stripping, exponent-digit count and infinity and NaN spellings are not
   fixed across languages, and Rust, JavaScript and Fortran have no `%g` at all. A replay bundle
   whose identity depends on how one C library prints a double is portable only by luck. This
   argument does not depend on problem size.
2. **It is slower, by 30–38× measured.** The hash runs twice per Newton iteration: 48.3 ms against
   1.6 ms at n = 1e5, 6.7 ms against 0.2 ms at n = 1e4. This is the weaker argument and is recorded
   as such — the release horizon's flowsheets are tens to low hundreds of variables, where the
   difference is immaterial, and ADR 0003 D2.2's own reasoning warns against extrapolating to
   scales not in view.

**What did not change.** The identity *semantics*. Both encodings are injective over finite
doubles, both normalize signed zero, both make order and length participate, and neither quantizes.
`tests/test_adr_0008_transient_readiness.py` H1–H6 now run against **both** implementations, so
every D2 rule is pinned on each. One difference is recorded rather than left to be discovered: the
text form printed every NaN as `nan` and so collided all payloads, while the byte form distinguishes
them — not load-bearing, because a state containing a NaN is `invalid_trial_state` and is never
reported `ok`.

**Why now.** Nothing is released, so this regenerated fixtures instead of migrating stored hashes.
**That window closes at K04/K05**, when replay bundles begin storing digests; after that the same
change is a migration.

**What this does not establish.** ADR 0002 has still not been written, and it — not this entry — is
the authority. When it is written it must also state what the digest does *not* cover: the digest is
of the **anonymous ordered vector of values**, no name is hashed, so `constants_sha256` identifies a
pinned-input vector only together with a `model_version` that pins `parameter_ids`, and
`state_sha256` likewise with `variable_ids`. Nothing currently enforces that obligation on whatever
assigns `model_version`.

**Watch for.** A session comparing a digest across `ENCODING_ID` values, or the legacy
`p02_10_4_text`/`legacy_p02_hash` being deleted as dead code, when they are the live evidence that
the artifacts under `spikes/p02/results/` can still be checked. *(The third watch item — ADR 0002
being written without the anonymity clause — is discharged: ADR 0002 D2 closes it by mechanism.)*

---

## R-007 — The mixer admits an inlet on an enthalpy criterion, not on a phase label

> **Amended 2026-09-25 by R-055 (ADR 0012 D8):** a stream refused by this criterion is admitted when it is temperature-degenerate (bubble and dew temperatures both within 1e-6 K of its temperature); the reported gap is then that distance. The refusal path only; every registered refusal is ≥ 14 K from degenerate.

| | |
| --- | --- |
| Date | 2026-09-20 |
| Decided by | Opus 5, during K02. **Referred to the Fable review of K02 for judgement** |
| Normative text | `src/process_runtime/models/syn001/mixer.py`, module docstring and `_liquid_enthalpy` |
| Evidence | `docs/K02_DECISIONS.md`, "The mixer gates on enthalpy, not on a phase label"; `tests/test_k02_mixer.py` |
| Affected packages | K02 (done), K03 (its phase-attempt controller meets the same boundary) |

**Decision (revised 2026-09-20 after the Fable review of K02).** A stream may be written as a
single phase when doing so would misplace the outlet temperature by less than the **temperature**
tolerance ADR 0001 D6 registers for SYN-001 (`1e-6 K`) — that is, when
`|H_true - H_single| / (dH_single/dT) <= 1e-6 K`. The test lives in
`tp_state.single_phase_admissible` and the heater and the mixer share it.

**Superseded first version, recorded because the failure is instructive.** The bound was
originally on the enthalpy gap itself, in watts, against the registered *energy* tolerance. That
is an **extensive bound on an intensive question**: it passes whenever the throughput is small
enough. Measured by the review — at 1e-8 mol/s a 45%-vapour inlet carries 3.8e-4 W of latent heat,
slips under the 1.01e-3 W bound, and the mixer returned `ok`, `LIQUID`, outlet **330.0 K** where
the true liquid closure gives **393.9 K**. A plausible wrong number, which is the one thing this
repository is built to refuse. At nominal throughput the old bound was already 2.18e-6 K, twice
the registered temperature tolerance.

**Rejected alternative.** Gate on the phase signature, which is the obvious reading of plan §3.2's
"restricted to the subcooled-liquid domain" and of blueprint §6.3's "final phase admissibility
check".

**Reason for gating on enthalpy at all, which survives the revision.** A phase-*label* check
**rejects the nominal registered variant.** The SYN-001 recycle is the
flash's own liquid at the flash temperature, so it sits exactly on its bubble point; in double
precision `sum_i z_i K_i` evaluates to `1.0000000000000002` and the provider — correctly, by its
registered classification order — returns `TWO_PHASE` with a vapour fraction of `1.3e-17`. Fable's
20-digit reference registers the same stream `recycle_phase_signature: LIQUID`, and its
`H_recycle_W` is the liquid enthalpy. Both are right at their own precision.

The criterion chosen tests the quantity that can actually produce a wrong number, against a number
the project already registered, rather than inventing an epsilon for a phase boundary. The
saturated recycle misses by ~6e-13 W; an equimolar feed at 347.45 K, just above its 347.44118 K
bubble point, misses by 29.4 W and is refused. A test pins that discriminating case so the bound
cannot drift.

**Also rejected.** Using the *true* two-phase enthalpy for the inlets. More accurate in isolation,
but `MIX-energy`'s blocks compute the single-phase liquid enthalpy, and an evaluator that disagreed
with its own residual by 6e-13 W would break the rule that matters more: residual and evaluator
describe the same function at the same state.

**What this does not establish.** That the criterion generalizes. It is stated for SYN-001, using a
tolerance registered for SYN-001 only, in a unit whose manifest id is `syn001.adiabatic_mixer`.

**Watch for.** A later session widening the bound, or reintroducing a label check because it reads
more naturally, without reading this entry. Also: **the remedy does not transfer to K03**, whose
phase-attempt controller must decide which active set to try at the same boundary, and that is not
a question about an enthalpy.

---

## R-008 — A two-phase stream's split is lifted into variables, not solved inside a block

| | |
| --- | --- |
| Date | 2026-09-20 |
| Decided by | Opus 5, during K02, following the formulation Fable fixed for P02 |
| Normative text | `src/process_runtime/models/syn001/tp_state.py`, `lift_two_phase_stream` |
| Evidence | `docs/derivations/P02-composition-spec.md` lines 80–134; `docs/K02_DECISIONS.md` |
| Affected packages | K02 (done), K03 (solves the resulting system), T04, T05 |

**Decision.** Where a unit needs the enthalpy of a stream that may be two-phase — the SYN-001
heater's outlet — the phase split is lifted into free variables `<stream>.vap.i`,
`<stream>.liq.i`, `<stream>.V`, `<stream>.L`, with the equilibrium written division-free as
`v_i L - K_i l_i V` and five unit-authored `algebraic` lifting rows. The lifted variables are named
after the **stream**, so the unit that produces it and the unit that reads it name the same
variables and the same property blocks.

**Rejected alternative.** An opaque `PropertyBlock` that runs an inner Rachford–Rice solve and
returns the implicit derivative of blueprint §5.1. That keeps the assembled row count equal to the
21 the manifests declare.

**Reason.** Plan §4.2 requires the heater and the flash to share one TP-state kernel, and the
flash's split is lifted in the Fable-authored P02 specification, so the heater's should be too.
The rejected route puts a Newton solve inside every residual evaluation and gives a one-sided
derivative at the phase boundary; blueprint §5.1 warns in its own words that "a derivative through
an incompletely converged algorithm is not automatically the derivative of the intended model".
The division-free form is also exact at an absent component and at a vanished phase, which is
three of the five registered variants, where a mole-fraction form cannot be written at all
(ADR 0001 D3.2).

**Why the row count is not a violation.** ADR 0008 D3.5's 21 rows are *manifest declarations*, and
assertion M3 counts the manifests, not the assembled system
(`tests/test_adr_0008_transient_readiness.py:255`). D4.4 explicitly contemplates rows the assembly
authors itself and requires them to be declared `algebraic` explicitly, which these are.

**Watch for.** The lifted form admits the classical **trivial solutions** of the flash equations:
every `v_i = 0` (so `V = 0`), and every `l_i = 0` (so `L = 0`). These satisfy `v_i L - K_i l_i V`
*identically*, whatever the feed and whatever the K-values. They are not the dormant stream —
`V = L = 0` is a legitimate answer for a stream with no flow, and an earlier version of this entry
confused the two, which the Fable review of K02 corrected.

Measured: at the once-through variant's genuinely two-phase heater outlet, forcing the all-liquid
split leaves **thirteen of the heater's fourteen rows at exactly 0.0**, and a solver free to choose
`Q` closes the fourteenth at a duty **8237.85 W** below the true one. No residual can exclude this,
because the trivial split satisfies it. Excluding it is initialization on the physical branch plus
a final phase-admissibility check on the converged answer — **K03's**, blueprint §6.3 and §7.1.
Registered as `tests/test_k02_flowsheet.py::
test_the_lifted_equilibrium_admits_a_trivial_root_that_k03_must_reject`.

---

## R-009 — The property package reaches identity through the model label

| | |
| --- | --- |
| Date | 2026-09-20 |
| Decided by | Opus 5, during K02, closing the gap the Fable review of K01 identified |
| Normative text | `src/process_runtime/models/syn001/flowsheet.py`, `Syn001Flowsheet.label` |
| Evidence | `docs/adr/0008-transient-extension-readiness.md` D4.1; the K01 manifest's PARTIAL limitation; `tests/test_k02_flowsheet.py` |
| Affected packages | K02 (done), K04, K05 (replay identity), M01 |

**Decision (corrected 2026-09-20 after the Fable review of K02).** A flowsheet's label names its
property provider — the provider id and twelve hex digits of each of its two declared hashes — so
the property data participates in `model_version`, and **nothing else**.

**Corrected from the first version.** That one also carried `r`, the flash temperature and the
heater temperature. Those are *pinned inputs*, and ADR 0008 D4.1 says in its own words that
`model_version` "identifies equation structure and backend form only" and that two instances
compiled from the same structure with different specification values **share** it. Carrying them
violated D4.1 directly, defeated re-binding without recompilation, and overflowed ADR 0002 D2's
64-character cap at an unremarkable parameterization (`r = 0.123`, `T_f = 360.25`). All three
measured by the review.

**Rejected alternative.** Extending `constants_sha256` to cover the physical constants, which is
what ADR 0008 D4.1's own text describes.

**Reason.** It cannot be done: `constants_sha256` hashes the **pinned-input vector**, and pinned
inputs are floats. A provider's data hash is a string. ADR 0002 D2.7 already requires the label to
change whenever the equation set changes, and a provider with different constants *is* a different
equation set, so the label is the carrier the architecture already has. The K01 Fable review found
the gap — the thirteen SYN-001 physical constants were hashed by nothing, so the literal D4.1 test
passed while the coverage it stands for did not.

**What this does not establish.** Ninety-six bits is a distinguishing name a human can read, not a
cryptographic claim, and it is not offered as one; the full hashes stay in `PropertyCapabilities`.
And this closes the gap **for this flowsheet**, by a route D4.1 does not describe. Whether D4.1
should be amended to say so is a question for the Fable review of K02.

**Watch for.** A later session extending the label without checking ADR 0002 D2's pattern — at most
64 characters of `[A-Za-z0-9._-]`, and no `@`, because `model_version` splits on it. The flowsheet
checks this itself and fails with the length rather than letting the refusal surface from two
layers down.

---

## R-010 — The K03 tear Newton runs on the three-variable tear residual, with the traversal as G and the Schur complement of the assembled EO Jacobian as dR/dt

| | |
| --- | --- |
| Date | 2026-09-21 |
| Decided by | Fable 5.1 (K03 specification pass) |
| Normative text | `docs/derivations/K03-solver-spec.md` §2–§3 |
| Evidence | Schur complement vs closed form 5.3e-15 worst; inner-row consistency 2.0e-15 scaled; `benchmarks/k03/reference_values.yaml` (closed forms) |
| Affected packages | K03, K04 (verifies the reconstructed 47-vector), T02 (the full EO Newton reuses the core, the scales, the elimination certificate) |

**Decision.** Reading (A) of plan §4.2's K03 constraint: Newton on `R(t) = G(t) − t` over `S6.n` (3 variables), `G` by K02's sequential traversal (phases selected at unit boundaries, as [A01]'s last paragraph permits), `dR/dt` by exact block elimination of the assembled 49 × 47 Jacobian at the traversal's reconstructed state through SuperLU, with a mandatory check that the inner rows vanish there (`η ≤ 1e-10`). The finite-difference tear Jacobian is a test oracle only, on a registered stencil.

**Rejected alternatives.** (B) A 47-variable equation-oriented Newton with the tear as a label: needs the same rank policy and scales *plus* a phase-branch machinery, because in the lifted form both trivial splits are exact roots of every row and a bound-aware Newton lands on them; that is T02/T03's V15, not v0.0's "one closed recycle". (C) Finite differences of the traversal: demoted by the plan; retained as the oracle.

**Reason.** It is what the plan's constraint sentence and G00 say; the traversal is the blueprint §6.3 default v0.0 formulation and cannot produce a trivial root; the exact derivative is free once K02 assembles the rows. The Newton core is generic and the EO path is not foreclosed.

**Watch for.** A session "simplifying" to (B) because the assembled Jacobian is square-ish, without the trivial-root branch machinery; or a session dropping the inner-consistency check because it "never fires".

---

## R-011 — Consistent-redundant rows are eliminated structurally, with a certificate, never by least squares and never inside a unit

| | |
| --- | --- |
| Date | 2026-09-21 |
| Decided by | Fable 5.1 (K03 specification pass) |
| Normative text | `docs/derivations/K03-solver-spec.md` §7 |
| Evidence | K02's finding (nine pressure rows, seven columns, rank 7); the graph-cycle certificate measured on two random pressure states (mismatch 0 at the registered case, −50 000 Pa with the flash at 150 kPa) |
| Affected packages | K03, K04 (re-evaluates the eliminated rows), T01/T06 (generalize) |

**Decision.** Rows linear in pressure columns with `±1` coefficients form a graph; a row closing a cycle is eliminated by a deterministic union–find pass in assembled order and certified by the identity `F_e − Σ σ_k F_k = m_e` checked at two states; `|m_e| > 1e-2 Pa` is `SPECIFICATION_CONFLICT`; an unclassifiable row is `UNSUPPORTED_RANK_STRUCTURE`. SYN-001: `U-FLASH:FLASH-P:inlet` and `U-SPLIT:SPLIT-P:recycle` are eliminated; the inner block is 44 × 44. The rows stay in the residual, in the consistency check and in K04's reconstruction.

**Rejected alternatives.** A least-squares or regularized Newton step on the rectangular system (blueprint §7.7: recovery, "not permission to discard equations"; §3.1 fixes SuperLU); dropping the rows in the unit models (K02 rightly refused: a unit cannot see the flowsheet); a numerical rank threshold on singular values (a decision about structure should not depend on a tolerance).

**Watch for.** Generalizing the `±1` rule to pressure *ratios* or to nonzero drops without re-deriving the consistency condition; and the P01 manifest question the K02 review raised (`FLASH-P`'s inlet clause), which this entry does not decide.

---

## R-012 — The frozen phase set of a tear attempt covers only the phase selections the tear residual depends on

| | |
| --- | --- |
| Date | 2026-09-21 |
| Decided by | Fable 5.1 (K03 specification pass) |
| Normative text | `docs/adr/0005-phase-attempt-contract.md` (Accepted 2026-09-24) and `docs/derivations/T03-phase-controller-spec.md` §4 — the successor; `docs/derivations/K03-solver-spec.md` §9 was the interim text and remains the description of the tear path where ADR 0005 does not change it |
| Evidence | Measured on the prototype: with the heater outlet in the signature, the nominal case's exact one-step landing on `t*` from `G(0)` is rejected as a phase change (S3 flips `TWO_PHASE` → `LIQUID` along the ray while `G(t)` is unchanged) and the solver crawls to a wall it need not cross; with the flash alone, one step |
| Affected packages | K03, T01 (derives the rule from the block-triangular form), T03 (generalizes restarts and cycling) |

**Decision.** The attempt signature is `(("U-FLASH", regime),)`. The heater outlet's regime feeds only dead-end variables (`U-HEAT.Q`, the lifted S3 split) and is recorded, not frozen; dormancy of `S6`/`S7` is not a phase selection. `PHASE_UPDATE_REQUIRED` trials are halved once (overshoot), the attempt ends after `phase_wall_patience = 2` consecutive iterations with such rejections, the restart point is the largest-α phase-rejected trial of the closing line search, a signature may be attempted once per solve (`ACTIVE_SET_CYCLING` otherwise), at most 5 attempts.

**Rejected alternatives.** Freezing every phase-selecting unit's signature (measured cost above); terminating the attempt on the first phase-change trial (overshoot-cycles on solvable problems); restarting from the last accepted checkpoint (its traversal reports the old signature, so the new attempt would immediately fail).

**Watch for.** A session reintroducing the heater into the signature because [A01] "says every phase"; a session raising the cycle rule to allow repeats without ADV-01 evidence (Q3 in the spec).

**Refined by R-028 (ADR 0005, 2026-09-24).** The signature, the halving, the patience and the one-attempt-per-signature rule stand. The restart point is now the largest-α phase-rejected trial whose regime is *adjacent* to the frozen one (largest α only if none is) — on K03's registered OFF-B trajectory the same point. T03 supplied the evidence the watch item asked for, and it supports keeping the cycle rule (T03 spec §7).

---

## R-013 — The SYN-001 tear initializer is a two-source chain: the registered guess, checked, then G(0)

| | |
| --- | --- |
| Date | 2026-09-21 |
| Decided by | Fable 5.1 (K03 specification pass), amending its own derivation §9 |
| Normative text | `docs/derivations/SYN-001.md` §9 (amendment); `docs/derivations/K03-solver-spec.md` §10 |
| Evidence | K02 finding 1 (`test_the_registered_tear_initializer_is_outside_the_v0_0_mixer_domain`); closed-form margins in `benchmarks/k03/reference_values.yaml` |
| Affected packages | K03, and `benchmarks/registry.yaml` (adds `local_initializer` v2 to the five flowsheet cases; v1 unchanged) |

**Decision.** `SYN-001-tear-init-v1` (`r F_i`) stays registered as the user-guess source of blueprint §7.4 and is *checked* by one traversal; where the mixer refuses it (nominal, high-recycle, 420 K) the refusal is a logged typed event and the chain falls through to `SYN-001-tear-init-v2`, `t⁰ = G(0) = (1 − r) t*`, admissible for every r. Physical nominals are the last source; `INITIALIZATION_FAILED` if all are refused.

**Rejected alternative.** Replacing v1 by G(0) in the registry (the K02 reviewer's suggestion). It would make finding 1 disappear instead of making it a registered exercise of "checking every candidate", and it would drop the only registered case in which an initializer is refused by a unit's domain.

**Watch for.** A session treating G(0) as evidence that the tear solver works: along that ray the map is affine and Newton converges in one step; the off-ray starts in the K03 spec §13 are the evidence.

---

## R-014 — The P01 tear initializer is retired; G(0) is the registered initializer, and the rejection path keeps a case of its own (supersedes R-013)

| | |
| --- | --- |
| Date | 2026-09-21 |
| Decided by | **Frank Peters**, reversing the default Fable recorded in R-013 and K03-solver-spec Q1; synthesis proposed by the Opus session, applied by Fable |
| Normative text | `docs/derivations/SYN-001.md` §9 (rewritten); `docs/derivations/K03-solver-spec.md` §10.1, §13.8; `benchmarks/registry.yaml` (five `initializer` entries and the case `SYN-001-inadmissible-guess`) |
| Evidence | unchanged from R-013: K02 finding 1; closed-form margins in `benchmarks/k03/reference_values.yaml` |
| Affected packages | K03; K02 (`Syn001Flowsheet.initial_recycle()` and the test asserting the old guess follow, Opus) |

**Decision.** `SYN-001-tear-init-v2` (`t⁰ = G(0) = (1 − r) t*`, one traversal from a dormant recycle) is *the* registered SYN-001 tear initializer. The P01 guess `r F_i` (`SYN-001-tear-init-v1`) is retired from derivation §9 and from the five flowsheet cases. The coverage R-013 kept by retaining it — the only registered exercise of blueprint §7.4's initializer-rejection path — is preserved by a new registered case, `SYN-001-inadmissible-guess`: the nominal revision byte for byte with `user_guess = (0.5, 0.5, 0.5)`, expected outcome the nominal solve *after* a logged `initializer_rejected` naming `U-MIX`; outside the success denominator, since its physics is the nominal case's.

**What changed to justify reversing R-013.** Nothing measured; a preference. Frank's words: "it might be better in the longer run to replace the initializer. It is fine to redo some stuff, if this gives a cleaner implementation." The implementation is not simpler either way — §7.4's checked chain and its rejection path exist regardless — but a registered initializer known not to work costs every future reader of the derivation an explanatory paragraph, and that cost is real. R-013's argument (do not let finding 1 disappear) is met by giving the rejection its own named case rather than by keeping a wart in the derivation.

**Rejected alternative.** R-013's: keep v1 registered as a checked user guess beside v2.

**Watch for.** A session deleting `SYN-001-inadmissible-guess` as a duplicate of the nominal case (it is, by design, and it is the only registered rejection); a session counting it in the success denominator.

## R-015 — Every round-trip fixture is regenerated from live code by a committed generator, and the ledger's pointers are checked

> **Applied 2026-09-26 (T06 Amendment 2, spec A81):** the K03 OFF-B restart-trace fixture is re-baselined by its generator (`property_calls` 115 → 116, the one difference; counters are measured non-reproducible and forgiven by design); for a fixture carrying `VOLATILE_FIELDS` (the K05 run manifest), "regenerates identically" means `run.compare.differences` empty with those fields excluded plus Q-S7's hash check, and the file is rewritten only when a compared field changes.

| | |
| --- | --- |
| Date | 2026-09-21 |
| Decided by | Opus session, during the K03 M6 mutation sweep |
| Normative text | `scripts/k03_schema_fixtures.py`; `tests/test_k03_schemas.py::test_the_fixtures_are_what_the_code_emits_today`; `tests/test_requirements_ledger.py::test_every_cited_evidence_manifest_exists_and_says_what_is_claimed` and `::test_every_cited_test_exists` |
| Evidence | The M6 mutation sweep: 9/13 caught before, 13/13 after. Two defects found, both below |
| Affected packages | K03 now; every package that ships a schema fixture or cites evidence |

**Decision.** A committed generator emits *every* round-trip fixture from a live run, and a test compares all of them; a fixture that nothing regenerates is not allowed to exist. Separately, the requirements ledger's two kinds of pointer — cited evidence manifests and cited pytest node IDs — are checked for existence and agreement, not merely for schema validity.

**What it prevents, measured rather than argued.** CLAUDE.md already says self-generated outputs are regression fixtures. It does not follow that they are *harmless*: a generated fixture that is committed and then never regenerated stops being a regression test on anything, because the emitter can change underneath it. K03 M6 committed six fixtures and regenerated two, and the mutation sweep found the consequence — mutating `_finite_or_none` to report `0.0` where JSON needs `null`, and mutating the attempt context to serialize the workspace ADR 0008 D1.4 calls inert, both survived a full 1155-test run. The tests that should have caught them read the frozen files.

Regenerating the other four then found the second defect, which no mutation would have: the committed attempt-context fixture was internally impossible. It named attempt 1's *converged* `TWO_PHASE` checkpoint as the state attempt 1 opened *from*, when a restart by construction opens from the `partial` checkpoint of the regime it is leaving. It had been hand-assembled from parts of a real solve, validated against its schema, and read plausibly.

The ledger check has the same shape and found the same kind of thing immediately: requirement A04 cited `test_the_two_outcome_type_cases_are_outside_the_success_denominator`, which K03 had renamed when it added a third case. Nothing noticed, because nothing had ever followed a ledger pointer.

**Rejected alternative.** Assert properties of the frozen fixtures instead — cheaper, and it is what was there. It cannot work: the property is a property of the *emitter*, and a frozen file is evidence about the emitter only on the day it was written.

**Watch for.** A new schema fixture added by hand "just for now"; a generator that writes some fixtures and leaves others; an evidence path or node ID edited without running the ledger test.

---

## R-016 — The certificate is issued by a verifier that shares nothing with the solver: the 47 × 47 target Jacobian, energy from a fresh flash of every stream, and the solution-error bound beside the rank test

> **Amended 2026-09-25 by R-059…R-061 (ADR 0013):** the fresh-flash categories (energy balances, phase admissibility, independent splits) are evaluated at the verifier's own one-step Newton projection of `x_final` when every row passes and the screen is `NO_RANK_LOSS_DETECTED` — the certified state, its residual rows and every other check stay at `x_final`; the projection is computed from the verifier's own residual, Jacobian and factorization (the screen's), never from a solver quantity. (4) "a fresh flash of its own `(n, T, P)`" reads a stream within K03's `ε_adm` of saturation as single-phase, and an unresolved two-phase split is judged like a degenerate one. The rejected alternative "reconstructing the full state inside the verifier" stays rejected: the certificate's subject is still `x_final`.

> **Amended 2026-09-25 by R-054 (ADR 0012 D7), narrowly:** (4) "never from the lifted split" has one exception, a temperature-degenerate split (its phase fractions are not a function of its `(n, T, P)` at the registered temperature resolution), whose enthalpies the revision table reads from the stored split; and the regularity matrix of a zero-flow root is its zero-flow form. SYN-001's legacy set is untouched; independence (no shared code with the solver) is unchanged.

| | |
| --- | --- |
| Date | 2026-09-22 |
| Decided by | Fable 5.1 (K04 specification pass); two points held FOR FRANK in the ADR (F1, F2) with defaults applied |
| Normative text | `docs/derivations/K04-certificate-spec.md` §3–§9; `docs/adr/0007-reproducibility-certificate-policy.md` D1–D6 |
| Brief | `docs/briefs/K04-certificate-specification.md` |
| Evidence | measured 2026-09-22 on the five reconstructed `x(t*)`: `rcond₁` of the 47 × 47 scaled target 1.3e-4 to 2.0e-3 (unscaled 9e-12 to 6e-11); the complete trivial-root state satisfies all 49 rows to 5.6e-17 scaled, every material balance, the energy envelope and the rank test, and is caught only by the fresh-flash unit energy (±8237.85 W), phase admissibility (Σ x K = 1.0703) and the independent split (0.304 mol/s); `x² = 0` under the K03 Newton stops at `2⁻¹⁴` with `rcond = 1`; `benchmarks/k04/reference_values.yaml` (closed forms, cross-checked to P01 at 4.8e-20) |
| Affected packages | K04; K03 (the one field-set change: `Checkpoint.verification_scope` widens; A35's writer becomes K04 A01); K05 (D4 replay reports); T06 (D5 budgets) |

**Decision.** (1) The [A08] matrix is the scaled 47 × 47 target Jacobian after the two alias eliminations, evaluated afresh at the final full state; never the 3 × 3 tear derivative, the 44 × 44 inner block or the rectangular 49 × 47, and never a reused factorization (none exists at that size). (2) The recipe is plan §6.3's (`splu` → `onenormest` → `rcond₁`) with `τ_ill = 1e-8`, escalation to a dense SVD with rank tolerance `n ε σ_max` under a 2000-dimension cap, `INCONCLUSIVE` retained above it; the U-diagonal never decides. (3) Beside the relative rank test, the absolute-conditioning limit `‖Ĵ⁻¹‖₁ ≤ τ̂_min / (n ε)` is part of the regularity status (`ILL_CONDITIONED(absolute)` → `UNVERIFIED`), because a relative condition estimate cannot see that a residual tolerance stops meaning anything near `x² = 0`; the first-order solution-error bound `‖Ĵ⁻¹‖₁‖F̂‖∞` is recorded on every certificate with a statement and is never a pass/fail check. *Amended 2026-09-22, same day:* the first version made the bound a required check against `τ̂_min`; measured `‖Ĵ⁻¹‖₁ = 144.8` at nominal made that ~145× stricter than the residual rule and failed every registered below-threshold twin, so the promise was wrong, not the twins. A certificate certifies residual accuracy (blueprint §8.1) and reports, without promising, what that buys in solution terms; whether `VERIFIED` should ever promise solution accuracy is FOR FRANK (K04 spec §16 F3). (4) Every energy balance is assembled by the verifier with each stream's enthalpy from a fresh flash of its own `(n, T, P)`, never from the lifted split; the overall envelope is registered as a blind spot because it passes at the trivial root. (5) Material balances and specifications are plain sums in the verifier with no compiled or provider call. (6) `VERIFIED` requires every required check under the registered policy hash and `NO_RANK_LOSS_DETECTED`; `RELAXED` only under an explicitly supplied loosening policy; `UNVERIFIED` for a rank, bound, derivative or unsupported limitation with passing checks retained; `FAILED` for any failing check; no verdict word ever on a `partial` checkpoint; no certificate without the full state. (7) Reproducibility: R0 structure bit-identical on the registered pair, every float within one declared policy whose floors are the registered thresholds and nothing else, digests never compared for value, five counts never compared, bitwise agreement reported and never promised.

**Rejected alternatives.** The 3 × 3 or 44 × 44 matrix (each masks a singularity in the other); the rectangular matrix (deficient by the two known aliases at every state); the energy envelope alone or the compiled duty rows as the energy check (both pass the trivial root); reconstructing the full state inside the verifier from the tear vector (the verifier would be choosing the state it judges); a certificate on a partial checkpoint that happens to satisfy every check; a universal absolute floor or a tighter same-machine policy (both measured wrong); property calls as a scoring budget (476–612 across one ulp).

**Watch for.** A session "simplifying" the energy check to the envelope or to the compiled rows because they agree at every registered variant; a session dropping the solution-error bound because `rcond` is "the standard"; a session comparing `state_sha256` values or `nnz(L)` across platforms because they happened to agree once; a session attaching `VERIFIED` to a budget-exhausted iterate that passes the checks; a session reusing the K03 Schur factorization "since it is already there".


## Human sign-off, 2026-09-23 — Frank Peters

Recorded, not claimed. CLAUDE.md reserves this to a human and forbids an agent setting
`reviewed`; what follows is his statement, dated and attributed, and the evidence manifests are
left exactly as they were written at their commits.

**Numerical and process-modeling documents — signed off.**

- `docs/derivations/SYN-001.md` — `h = g − T ∂g/∂T`, K from μ-equality, the oracle's reduction
  to the fresh-feed Rachford–Rice problem, the variant phase states.
- `docs/adr/0001-state-units-zero-flow.md` — state `nTP-v1`, zero-flow rules, the duty sign
  convention including negative heater duty.
- `docs/adr/0008-transient-extension-readiness.md` §D3.5 — the accumulation classification of
  the 21 SYN-001 rows.
- `docs/derivations/K03-solver-spec.md` §7.2 — signed off **after** the reserved doubt below
  was resolved.

**The one reserved doubt, and how it was settled.** Frank withheld sign-off on §7.2 pending an
argument, on the grounds that the Opus session had edited a Fable authority document and that
the claim should survive challenge rather than stand on its author's say-so: *"If you are
correct Fable can be convinced. Otherwise Fable will give good arguments why you are wrong."*

Fable attempted three refutations and reported that all three failed, working from the declared
row forms in `models/rows.py` rather than from the Opus session's Jacobian reading — the one
source that could have overturned it. `balance_row` is `inflow − outflow` and
`SPLIT-P:recycle` is declared `balance_row((S6.P,), (S5.P,))`, so manifest and assembly agree
and no row sign was inverted. The measurement that settles it is stronger than the original
argument: across two probe states with the pressures shifted apart, the **original** signs give
`0.0` and `+12 345.0` — not a constant, therefore not a certificate at all, and `rank.py`'s
own two-probe linearity witness would have refused it. The "combination to add" reading, which
was the only way both versions could have been right about different things, is excluded by the
table's first row, which is constant only under `F_e − Σ`. Fable added a dated line to §7.2
stating the convention so the misreading cannot recur.

**ADR 0007 F3 — confirmed.** `VERIFIED` certifies residual accuracy at the registered
tolerances; the solution-error bound is recorded and disclosed, never promised.

**Apache-2.0 — confirmed**, and the `LICENSE` and `NOTICE` files are now present. The copyright
line is **E.A.J.F. Peters**, the form he publishes under, on his determination that this is
scholarly output — TU/e's guidance distinguishes teaching materials, whose copyright belongs to
the university, from scholarly work such as dissertations, articles and monographs, whose
copyright belongs to the creator, and he places this software in the second category. That is a
judgement about how the work sits in his duties, which is his to make.

An earlier version of this entry named the university, on an argument that it was the
"recoverable error of the two". Frank corrected the reasoning rather than the conclusion and was
right to: **a copyright notice is declaratory, not constitutive.** Copyright arises on creation
and Article 7 of the Dutch Copyright Act assigns it by operation of law where it applies, so a
notice neither creates nor extinguishes anyone's ownership. The "safer to name the university"
framing implied a legal effect the line does not have, and the only question a notice can
actually answer is whether it is accurate.

**What this sign-off does not cover.** It is the documents named above, not the packages. The
ten evidence manifests still read `review: {numerical: pending, process_model: pending}`, and
they are left that way: each was written at its own commit and describes its own package's
numerical content, which is broader than these four documents. Nothing here is empirical
validation — SYN-001 is synthetic.


## R-017 — A sign-off records that someone looked, not that the result is guaranteed

| | |
| --- | --- |
| Date | 2026-09-23 |
| Decided by | **Frank Peters**, stating the position unprompted while signing the numerical manifests |
| Normative text | the `review` field of every `evidence/**/manifest.json`; `schemas/evidence-manifest.schema.json` |
| Affected packages | every package, now and later |

**Decision.** A human sign-off in a manifest's `review` field records that a person with the
relevant expertise examined the evidence and raised no objection. It does **not** assert that
the content is correct, and it is written so that no reader can take it that way. The signer's
words: *"I cannot guarantee their content, but it looks good. My stance is that if there are
issues they will show up in verification and validation studies. So, I am not a big fan of
signing off too much. It gives an expression of guarantees that are not there."*

**Why it is registered rather than left as a remark.** It is a standing instruction about how
this project's strongest-sounding status word is to be used, and the pressure runs one way: a
later session wanting a clean release will find nine manifests carrying a human name and may
read it as warranty. The schema already anticipated this — its `review` field takes *"a reviewer
identity and date"* and not a badge word — so the qualification lives inside the field rather
than in a footnote someone can miss.

It also matches what the repository already does everywhere else. Six of the seven v0.0 gates
are *met with limitations* rather than met; every manifest lists what it does not establish;
K04's certificate carries three sentences saying what `VERIFIED` does not mean. A sign-off that
claimed more than the evidence would have been the one place the discipline lapsed.

**Rejected alternative.** A bare `reviewed`, which is what the status vocabulary invites and
what a reader would most naturally over-read.

**Watch for.** A session setting `status: reviewed` on a manifest because the `review` field is
populated — the two are different claims, and `tests/test_evidence_manifests.py` checks only
that the first is not claimed without the second. `process_model` remains `pending` on all ten
manifests: it was not signed, and it is a different review.

---

## Already registered as ADRs

These are settled decisions with their own normative documents. Listed here so the register is the
single place to look; the ADR is the authority in every case.

| Entry | Question it answers | ADR | Status |
| --- | --- | --- | --- |
| R-A01 | State representation, units, sign conventions, zero-flow semantics (`nTP-v1`) | `docs/adr/0001-state-units-zero-flow.md` | Accepted, part of the P01 freeze |
| R-A02 | Canonicalization and schema encoding | `docs/adr/0002-canonicalization-and-schemas.md` | Accepted 2026-09-18, in force with C1–C10 applied on `wp/K02` and the gate green. Ratifies R-006 (`ieee754-be-v1`, no digest moved). Closes the anonymity hole: `model_version` is `<label>@<structure_sha256>` over the name-level structure document, compiler-assigned and recomputed on read (D2). Canonical JSON is RFC 8785 (D3); `ProcessRevision.content_hash` has a closed exclusion list (D4); directory-hash order pinned to byte order (D5); encoding identifiers pinned globally and recorded per manifest, not per document (D6); migration rule D7. Q1–Q5 open with defaults. **Amendment 1 (2026-09-27; T07 W7c finding; J10–J17, `adr0002_a1_reference.json`): an integer is canonical exactly when its digits are the canonical spelling of its nearest binary64.** That is every integer up to 2^53, exactly one per binary64 in `(2^53, 10^21)`, and none from 10^21. The verdict is on the digits, so an in-process `int` and every parser agree, and no reader has a number hook. `canonical.integer_binary64` is the one implementation. **Rejected:** exactness as the criterion, which refuses the writer's own `592612204108959000`; a reader-side hook, which splits in-process from HTTP and needs a second entry point for MCP; the writer re-spelling, which is not RFC 8785; and provenance-dependent verdicts. No stored byte or digest moves |
| R-A03 | `CompiledProblem` / backend selection | `docs/adr/0003-compiled-problem-backend.md` | Accepted 2026-09-17 on the P02/P03 evidence: CasADi 3.8.0; Pyomo/PyNumero/ASL rejected on installability and the measured comparison; tie-break not reached. Reversal triggers T1–T5 in the ADR. See R-003 |
| R-A04 | Explicit SuperLU options | `docs/adr/0004-superlu-options.md` | Accepted 2026-09-21 (K03 default): `permc_spec=COLAMD`, `diag_pivot_thresh=1.0`, `relax=1`, `panel_size=10`, `Equil=False` (measured inert on the `splu` path), `IterRefine=NOREFINE`, `SymmetricMode=False`; normalized linear residual recorded on every solve, threshold 1e-12 (measured floor 1.3e-16); singularity is a typed result; the `|U_ii|` screen is recorded and never decides |
| R-A05 | Phase-attempt contract | `docs/adr/0005-phase-attempt-contract.md`; normative text `docs/derivations/T03-phase-controller-spec.md` §4–§9 | **Accepted 2026-09-24** on T03's manifest `evidence/T03/6ac24be9da572a90b198ba91b81d603f082cfa74/manifest.json` (`tested`, 27/27). Supersedes K03 §9 and T02 §6.3.3–§6.3.5 as normative text. See R-028 |
| R-A06 | Distribution and data rights | `docs/adr/0006-distribution-data-rights.md` | Accepted 2026-09-17 as working policy: source + pinned PyPI dependency permitted with an LGPL notice; replay by reference; vendored bytes closed until METIS 4.0 is pruned and the unresolved notices settled. **Q1 and Q2 are both closed by Frank** (2026-09-17, 2026-09-22): the LGPL is allowed, and the METIS default stands with neither outward-facing remedy pursued. **Q3 — whether any package before v0.2 ships a mode-B artifact — is still open**, and it is the trigger that reopens Q2. See R-004 |
| R-A07 | Reproducibility and certificate policy | `docs/adr/0007-reproducibility-certificate-policy.md` | Accepted 2026-09-22 (K04 default): R0 structure bit-identical on the registered pair; one declared numerical policy `K04-numerical-policy-v1` for R1 and R2 (1e-9 relative, floors = the registered thresholds, no unregistered float, near-threshold margin 10); digests never compared for value; five counts recorded and never compared; a certificate reports bitwise agreement and never promises it; replay reports `exact_replay` / `compatible_reproduction` / `inspected_archived_results` as mode and `MATCH` / `MISMATCH` / `NOT_RUN` as verdict; property calls stay a hard cap and are not a scoring instrument. **F1 (the public bitwise promise), F2 (the registered budget instrument) and F3 (whether VERIFIED promises solution accuracy) were all answered by Frank Peters on 2026-09-22: the recommended default in every case, so all three defaults stand and no file changed.** See R-016 |

ADR numbers 0001–0007 are pre-allocated by plan §4.1 ("Phase-0 ADRs"); 0003, 0004 and 0006 are
now written (R-003, R-A04, R-004), 0005 is accepted (R-028), 0008 is used by R-001
(transient-extension readiness, accepted 2026-09-16) and 0009 by R-024. 0010 is used by R-030 to
R-035 (T04's globalization: specification continuation, edge 3, the residence-time PTC family,
experimental; certificates of a bound declaration; Proposed 2026-09-24). 0011 is used by R-036 to
R-043 (T05's unit models: the PH closure in the unit layer, `SYN-001-ref-v1` as a formation datum,
SYN-001 bit-identical; accepted 2026-09-25). 0012 is used by R-052 to R-058 (T05b: the saturation band and the PH kernel's band route, the phase contract `T05b-phase-contract-v2` with its `ZERO_FLOW` regime, the verifier's temperature-degenerate judgement, R-007's and R-029's amendments, what stays registered, and the zero-flow form of dormant non-lifted outlets; accepted 2026-09-25). 0013 is used by R-059 to R-062 (K04's fresh-flash checks at the verifier's projection; accepted 2026-09-25). 0014 is used by R-066 to R-074 (T06: the corpus and NET-07, the sampling law, the gate, a deterministic regularity estimate, the verifier's domain-safe alias shift, validation's dimension and component checks, the reference semantics, identity and replay; accepted 2026-09-27) and, from its Amendment 1 (2026-09-26), R-076 to R-080 (component-order mapping, unit conversion by ADR 0001 D1.3–D1.4, the typed tear-path initializer failure, the reference-tool qualification rulings, the shared-provider qualification's field). 0015 is used by R-075 (T06 F4: recovery edge 3's second action, the sequential restart of a revision-built region from `traversal-G0-pass8-v1`; accepted 2026-09-27). 0016 is used by R-081 (input units by recorded conversion, `unit-conversion-v2`, widening ADR 0001 D1.1/D1.4 by Frank's Q11; accepted 2026-09-27). 0017 is used by R-082 (SYN-001's TP flash classified by its Rachford–Rice bracket when the binary64 tests disagree, and SYN-001's identity re-baselined by substitution; accepted 2026-09-27; Frank approved the identity move 2026-09-26). ADR 0014's Amendment 2 carries R-083 (IDAES SmoothVLE) and R-084 (the screen's identity refusal). 0018 is used by R-085 (the solver's terminal refinement, `globalization.eo_core = newton_refined`; accepted 2026-09-27; the enum widening approved by Frank 2026-09-26; Amendment 1, 2026-09-27: the outcome claim under the property budget). ADR 0014's Amendment 4 carries R-086 (the saturation closure) and R-087 (scoring run 1 stands; nothing that scores a start changes after it). Its Amendment 5 (2026-09-27) carries R-088 (six questions handed to T07), R-089 (the holdout ensemble) and R-090 (run records as committed evidence). 0019 is used by R-091 to R-096 (T07's application contract: the sibling protocols, the frozen schemas with Amendments 1 (`application-results`) and 2 (`list_models` `specifications`), idempotency, authorization, the error shape, transports adding nothing; approved by Frank 2026-09-27, Accepted with T07's tested evidence). 0020 is used by R-097 to R-104 (job execution, R-088 Q27, cancellation and budgets, revision-built runs and their routes with the solution state, validate's fallback, R-088 Q29, Q26, Q28). ADR 0002's Amendment 1 (integer canonicity) is recorded in R-A02, and ADR 0013's Amendment 2 (routing on registered tolerances) in R-059 and R-061. T07's decisions outside an ADR are R-105 to R-116: the design note's ruling rounds 3–7 (R-105 to R-109), Frank's v0.1 exclusions (R-110), the V17 specification's four entries (R-111 to R-114), its Amendment R6 and `v17-c2` (R-115), and operator identity isolation (R-116). 0021 is used by R-117, R-118, R-119, R-121, R-125 (the v0.1 release policy; accepted 2026-10-02 with its proposed revisions 1 and 2 and T08's tested evidence). 0022 is used by R-120 (the v0.2 real-chemistry selection, the ammonia loop; accepted 2026-10-02 with V19 PASS). 0023 is used by R-123 (the kinetic CSTR and PTC-R1; accepted 2026-10-02 with T08's tested evidence) and, from its Amendment 1 (2026-09-29), R-126 (the `2⁻¹⁰` C trace). 0024 is used by R-124 (compatible warm starts; accepted 2026-10-02 with T08's tested evidence). T08's decisions outside an ADR: R-122, R-127 (build-first Amendment 1's other rulings), R-128 (build-first Amendment 2: the review's P-budget and P-trace rulings), and, from review 2 (`docs/reviews/T08-review-2.md`, 2026-10-01), R-129 (U05's refusal), R-130 (recovery-edge evidence kinds and `library-only`), R-131 (CLI `replay --rerun`, reversing T07 D-Q6) and R-132 (the description review blocks the RC); R-133 (Frank, 2026-10-01: V17 carried across U05 and the description review's two fixes). R-134 (Frank, 2026-10-01: B50 amended to the carried surface). ADR 0006 Amendment 1 carries R-135 (the GCC runtime library; LGPL-2.1). T08 release spec Amendment R3 (2026-10-01) carries R-136 (A45's bundle set; T06 A34 by A46), R-137 (A49's digest), R-138 (the verdict table, read by column), R-139 (ADR 0021 D2.4's tree list, proposed revision 2), R-140 (no lock in the wheel, L41; the lock lookup confined to the checkout), R-141 (T06 A89 by machine class, T06 Amendment T08-1), R-142 (ADR 0006 Amendment 2: D4 on aarch64) and R-143 (V19 for C1; ADR 0022 proposed revision 1). R-144 (B50 excludes the package version) and R-145 (ADR 0022: Frank's choice recorded). ADR 0025 is used by R-146 (`T08-numerical-policy-v2`; accepted 2026-10-02 with T08's tested evidence; entered at its W9 as amended by R-147, its Correction of 2026-10-02) and R-147 (Frank, 2026-10-02: Q4, a record is compared under the policy it records; an unknown policy is refused). R-148 (Frank, 2026-10-02: the K05 identity re-registered for recording `T08-numerical-policy-v2`, substitution only). R-149 (Frank, 2026-10-02: the project is named OpenFlowsheet; the rename's identity move re-registered, substitution only). R-150 (Frank, 2026-10-03: the public repository is the one working repository; the pre-0.1.0 history archived in `openflowsheet-dev`) and R-151 (the release gate identifies `C` by its recorded file hashes where `C` is absent). R-152 (Frank, 2026-10-06: M01 pins the code's K_NH₃ enthalpy term) and R-153 (Frank, 2026-10-06: the v0.2 order — M01's design first with M06 built alongside — and a `0.2.0a1` pre-release after M02). ADR 0026 is used by R-154 to R-160 (M01: the C1 property route; accepted 2026-10-08 with M01's tested evidence and the review closure `9098f14`) and ADR 0027 by R-161 to R-169 (M01: the C1 reactor boundary; Proposed 2026-10-08, still Proposed). Their Amendments 1 (M01 spec Amendment 1, §19) carry R-196 and R-197 (0026: the ln φ block's bounds, the request checks) and R-195, R-198, R-199 and R-200 (0027: the projection's defect assertion, the boundary's check order, the stand-in's label, M02's bitwise probe). M01's decisions outside an ADR: R-217 (T08's manifest-count and review-table tests scoped to the v0.1 packages) and R-219 (the C1 records' declared no-walk-up exception). ADR 0030 is used by R-170 and R-171 (M06: the diagnostic web shell, hand-written ES modules served same-origin; the bearer token in Web Storage, never a cookie; accepted 2026-10-08 with M06's tested evidence), with R-173 and R-174 (the gap triage closed; the scenario view is the run comparison) from its design note. ADR 0019 Amendment 3 (approved by Frank 2026-10-08, accepted with M06's tested evidence) carries R-172 (the structure index, element-level `diff_revisions`, `list_audit`) and R-192 (the served MCP tool-list digest moves to `6c4375b4…`). M06's W27 registration carries R-175 to R-179, and its decisions outside an ADR are R-193 (v0.2's working envelope `v0.2-envelope-dev`), R-194 (T08's U14 restated for v0.2) and R-216 (the v0.1.0 CHANGELOG-limitations test reads the envelope as released). **R-180 to R-191 and R-210 to R-218 (less M06's R-216 and M01's R-217) are held by M03, R-220 to R-237 by M02 and R-240 onward by M04; R-238 is the next free R number. ADRs 0031–0032 are held by M03 and 0033–0035 by M02; 0028 is the next free ADR number.**

## R-018 — Structural analysis reads the declaration, never the compiled sparsity pattern

| | |
| --- | --- |
| Date | 2026-09-23 |
| Decided by | Fable 5.1, overturning a recommendation the Opus session made in the T01 brief |
| Normative text | `docs/derivations/T01-structural-spec.md` §3.3; `src/process_runtime/graph/trace.py` |
| Evidence | `evidence/T01/<commit>/manifest.json` check `T01.A02`; `tests/test_t01_structural.py` |
| Affected packages | T01, T02, T06, and anything that reads structure from a `JacobianResult` |

**Decision.** The incidence graph is obtained by running each row builder under a set-valued
structural algebra with the **parameters opaque**. The backend's `indptr`/`indices` are a
cross-check only, never the source.

**Rejected alternative, and why.** The T01 brief proposed reading the pattern from `jacobian()` at
one admissible state, requiring only `status == "ok"` and `pattern_provenance == "backend-declared"`.
It is wrong, and the measurement is the argument: the compiler substitutes parameter *values*
before building the expression, so at `r = 0` CasADi folds `0.0 · n_i` away and the declared
sparsity is 167 entries instead of 170. The registered once-through revision would then have no
recycle edge in its graph, an empty tear, and a "structural" result the same flowsheet does not
share at `r = 0.5`. A conclusion that moves with a parameter value is not a structural conclusion,
exactly as one that moves with the enthalpy datum is not.

**What this does not say.** `pattern_provenance = "backend-declared"` remains accurate about the
*compiled function*; K01 needs no change. What is registered is that it is unfit as a structural
source. Anything else reading structure from `indptr`/`indices` — K04's compatible-pattern check
for sparsity reuse is the known case — should know the pattern can shrink at a zero parameter.

---

## R-019 — The structural layer is given its names; it never parses one

| | |
| --- | --- |
| Date | 2026-09-23 |
| Decided by | the Opus session, after assertion A15 found the defect |
| Normative text | `src/process_runtime/graph/__init__.py`; `trace.trace_declaration(row_units=…)`; `process.Connection.state_columns` |
| Evidence | `evidence/T01/<commit>/manifest.json` check `T01.A15` |
| Affected packages | T01, T02, T06 |

**Decision.** The instance that authored a row and the state coordinates of a stream are supplied
by the caller. No module under `src/process_runtime/graph/` parses a unit, stream or row id, and
none imports a unit model; a test greps for it.

**Rejected alternative, and why.** Deriving the authoring unit from the `<unit>:<family>:<part>`
id prefix is shorter and was written first. Assertion A15 — relabel every id by a bijection and
require the image of the registered answer — caught it: the attribution silently became empty,
which would have emptied the unit-local degree-of-freedom count and with it the localization that
names an over-specified unit. A layer that guesses from a name stops working when the name changes,
and does so without failing.

---

## R-020 — Closure is decided after certified redundancy, not by an empty over-determined block

| | |
| --- | --- |
| Date | 2026-09-23 |
| Decided by | Fable 5.1 |
| Normative text | `docs/derivations/T01-structural-spec.md` §8.1, §8.4; `src/process_runtime/graph/analysis.py` |
| Evidence | `evidence/T01/<commit>/manifest.json` checks `T01.A08`, `T01.A09`, `T01.A10` |
| Affected packages | T01, K06 (validation), T06 |

**Decision.** A declaration is structurally closed iff the coarse Dulmage–Mendelsohn partition
**with the certified redundant rows removed** has an empty over-determined and an empty
under-determined part. Over-determination itself is not a defect.

**Rejected alternative, and why.** "Reject when the over-determined block is non-empty" is the
obvious rule and it rejects the flowsheet this project is built on: nominal SYN-001 declares 49
rows over 47 columns with a seven-row over-determined block, deliberately, because ADR 0001 D4.5
makes a zero pressure drop an equation. A size threshold fails the other way — the registered
`OVR-1` is a genuine over-specification in a 2 × 1 block. Blueprint §7.7 allows an equation to be
discharged only with a certificate, so "everything in the block carries one" is the line.

**The corollary that is easy to lose.** The partition alone cannot name the *unit* at fault:
after certificates the conflicting revision's over-determined part holds ten specification rows
and relaxing any one closes the system. The report therefore lists every candidate and says the
list is complete and not minimal (statement S4), and the naming is done by a second, independent
count — unit-local degrees of freedom — tied to the first by an executable identity.

## R-021 — A copy row is a difference; two coefficients that do not cancel are not a copy

| | |
| --- | --- |
| Date | 2026-09-23 |
| Decided by | Fable 5.1, must-fix M4 of `docs/reviews/T01-review.md`, correcting its own §8.2 |
| Normative text | `docs/derivations/T01-structural-spec.md` §8.2 and §13 (`UNC-2`); `src/process_runtime/graph/certificates.py` |
| Evidence | `evidence/T01/<commit>/manifest.json` check `T01.A19`; `tests/test_t01_structural.py` |
| Affected packages | T01, K03 (`orchestrator/rank.py` shares the shape), T06 |

**Decision.** A row qualifies for the affine-copy certificate only when it has one column with a
`±1` coefficient, or two whose coefficients **cancel**. Two `+1` coefficients are a *sum*.

**Rejected alternative, and why.** "At most two columns, every coefficient `±1`" is the obvious
reading and was in three places at once: the specification's §8.2 wording, the reference
generator, and the implementation. It certifies `P1 + P2 − s` as equal to `P1 − s` — an identity
false at every state — because the row's only positive column becomes one endpoint and the
constant node the other. With a matching constant the row would then be removed from the closure
count on a false identity, which is exactly the discarding blueprint §7.7 forbids.

**Why it survived three independent derivations.** SYN-001 declares no row of that shape, so
every registered value is unchanged and the reference file is byte-identical after the amendment.
A rule can be wrong and agree with every case you have. `UNC-2` is the registered fixture that
makes it fail.

**K03 shared the coefficient test and was saved by its second guard.** Measured: given
`p3 = P_1 + P_2 − s` and `p1 = P_1 − s`, `orchestrator/rank.py` does qualify `p3` as a copy — and
then refuses it, because its two-state witness sees the mismatch move by the second pressure. So
no K03 result was ever wrong. But the refusal was *numerical*, and R-011's whole point is that
this elimination is structural, so the same guard is now in `rank.py` and fires first. T01, which
has no state and therefore no witness, is the case where the gap had nothing underneath it.

## R-022 — When the structural analysis cannot run, the status depends on why

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | **Frank Peters**, answering F1 of the Fable review of T01 and observing that the status should depend on the reason |
| Normative text | `src/process_runtime/application/binding.py` (`Unbound`); `src/process_runtime/application/validation.py` |
| Evidence | `tests/test_t01_structural.py` (`test_m3_…`, `test_r022_…`); `evidence/T01/<commit>/manifest.json` check `T01.A24` |
| Affected packages | T01, K06, and T07 when jobs consume validation status |

**Decision.** An analysis that did not run always withdraws a ready verdict (M3 of the review).
What replaces it depends on the reason:

| Reason | Status | Why |
| --- | --- | --- |
| Two specifications fix one quantity to different values | **`INVALID`**, `STR-04 FAIL`, `SPECIFICATION_CONFLICT` naming both | A real defect in the revision |
| A specification the flowsheet needs is missing | **`DRAFT`**, naming what is missing | Blueprint §4.3: "`DRAFT` revisions may be incomplete or under-specified" |
| The revision binds, and T01 finds structural under-specification and nothing else (`STR-02 FAIL` alone) — *extension, 2026-09-24, T02* | **`DRAFT`**, the check still `FAIL` naming `C⁻` | The same case reached through the analysis instead of the binding: a revision one specification short (T02 A26, the A02 revision without its duty) |
| The binding cannot read the revision, or the trace cannot follow a row | **`DRAFT`**, interim | The revision may be fine; `DRAFT` is the only existing status that claims neither closure nor a fault, and it blocks a run exactly as `INVALID` does |

**Rejected alternative, and why.** `INVALID` for every case was the review's recommended default
and was applied first. It states a defect nobody found whenever the cause is the tool — the
same error as the old `UNSUPPORTED_RANK_STRUCTURE` message, which described the tool as if it
were the revision. And for the incomplete case it contradicts §4.3's own words.

**What stays open.** The accurate answer for "cannot be analysed" is a fourth status (T01 Q1).
The validation-report schema is frozen, so that needs a Fable-authored ADR; it is deferred until a
second consumer — the CLI's exit code, T07's job lifecycle — needs to tell "incomplete" from "not
analysed" at status level rather than from the check message.

> **Amended 2026-09-27 by R-106 (T07 ruling round 5, S3; the kind by Frank):** a fixed value that its model refuses at construction (`value_outside_model_domain`, the `Unbound` kind `inadmissible`, which has no fallback) makes the revision **`INVALID`**, `CAP-01`: a real defect in the revision, like the specification conflict. A refused start is `incomplete` and stays **`DRAFT`** (§4.3). A schema-invalid document is SCHEMA-01 under the frozen revision schema. The table's other rows are unchanged.

## R-023 — A cross-unit specification's start value is a `role: free` specification

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | Opus session (T02 D1), an implementation choice within blueprint §4.1; flagged for the T02 review |
| Normative text | `src/process_runtime/application/binding.py` (`guesses`, `freed`, `promoted`); `benchmarks/syn001/cases/SYN-001-A02-*.yaml` |
| Evidence | `tests/test_t02_a02.py` (A25, A26, A28–A31) |
| Affected packages | T02, K06, T03 (the liquid-guess cases), T07 when jobs carry initial guesses |

**Decision.** The T02 spec (§7.5, §11.1) asks for an `initial_guess: {S3.T: <K>}` on the A02
revisions. It is expressed as a specification with `role: free` and a `value` (blueprint §4.1
already names `free` among a specification's roles): the binding frees the column, removes the
unit row that pinned it (`HEAT-T`), pins the pre-solve at the value, and promotes the revision's
fixed specification on the other unit (`SPEC-flash-duty`) to a row attributed to that unit.

**Rejected alternative, and why.** A new `initial_guess` field on `ProcessRevision`: the schema is
frozen (plan §2.2), so it needs a Fable-authored ADR, for a datum the existing `role` vocabulary
already carries. **Reversible by** rewriting the five A02 revisions and the binding's `guesses`
reader; nothing else reads the form.

**What stays open.** v0.1 pairs exactly one freed variable with one promoted target
(`UnsupportedRankStructureError` otherwise); which target a freed variable serves in a many-to-many
case is a T05/T06 question.

**Added by the T02 review (2026-09-24, M1).** A `role: free` specification is *always* served by an
EO region in v0.1, including when its target is owned by the same unit: no v0.1 unit declares a
local solver for a freed outlet, and the unit-local shortcut ran the flowsheet at the guess and
reported `CONVERGED` with the specification unmet (*measured*). T02 §7.1 as amended.


## R-024 — T02 extends the frozen schema list by ADR 0009, additively

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | Fable 5.1 (ADR 0009, Proposed; accepted when T02's manifest is `tested`) |
| Normative text | `docs/adr/0009-execution-plan-and-recycle-trace.md`; `schemas/README.md`; `docs/interfaces-frozen.md` §2 |
| Evidence | `tests/test_t02_plan.py`, `tests/test_t02_executor.py`, `tests/test_t02_identity.py`; K03 fixtures regenerated by `scripts/k03_schema_fixtures.py --write` |
| Affected packages | T02, K03, K04, K05, T07 |

**Decision.** A new `ExecutionPlan` schema (steps of unchanged K03 `SolvePlan`s); a required
`SolvePolicy.recycle`; five `SolveEvent` kinds and nullable fields (including `step_count` on the
plan's one `plan_built`); two outcomes (`RECYCLE_STAGNATION`, `CAPABILITY_UNAVAILABLE`);
`AttemptContext.active_phases` and `Checkpoint.step_index` (required, nullable); and one
failure-bundle action, `provide_derivatives`. `SolvePlan` does not change.

**Rejected alternatives, and why.** Widening `SolvePlan` with steps (would change every K03
fixture's meaning); a separate trace for the recycle (two orderings, two identities); an optional
`recycle` with defaults (a default mistakable for a declaration); `report_defect` for a missing
EO derivative (an honest `unavailable` is not a bug). ADR 0009 "Alternatives considered".

## R-025 — T02's recycle and phase policies are registered values, not tuning

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | Fable 5.1 (`docs/derivations/T02-recycle-spec.md` §5.10, §6.3, amended the same day) |
| Normative text | `T02-recycle-spec.md` §5.10 (Anderson constants), §6.3 (the lifted EO phase policy), §4.2 (`auto`), §4.4 (merge edge) |
| Evidence | `tests/test_t02_recycle.py` (A07–A20 against a 40-digit twin), `tests/test_t02_region.py` (A21–A24), `tests/test_t02_merge.py` |
| Affected packages | T02, T03 (generalizes §6.3), T06 |

**Decision.** Safeguarded type-II Anderson with depth `min(5, k, n)`, condition bound 1e8,
coefficient bound 1e4, no merit test, stagnation window 5 at ratio 0.99 counting growth, two
restarts, an oscillation detector that damps plain steps only (β 0.5), 200 iterations. `auto`
chooses Newton on the tear iff every loop unit declares exact EO derivatives, from the manifests,
never from a measured contraction. The lifted EO region solves an active phase set per attempt; a
phase leaves when *any* of its lifted variables lands on its bound (the 2026-09-24 amendment —
the nominal case leaves through a component, not the total), and appears only at closure.

**Rejected alternatives, and why.** A divergence factor (the stagnation rule with growth counted
already is one, and RCY-DIV shows it); a merit test on Anderson steps (§5.5: an accelerator's
non-monotone residual is not a failure); damping Anderson steps on oscillation (RCY-TRUNC shows the
flag must not touch them); the total-only disappearance rule (A21 measured it wrong on SYN-001).
Changing a constant is a spec amendment by Fable, not a tuning edit.

**Reversed in part by R-028 (ADR 0005, 2026-09-24).** On the lifted EO path a phase now leaves only when an attempt ends `BOUND_BLOCKED` on one of its lifted variables — a landing alone is an overshoot — and a phase can appear *during* an attempt through the admissibility screen. The Anderson constants, `auto` and the merge edge are unchanged.

## R-026 — A least-squares float is compared within a comparability window, not under a floor

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | Fable 5.1 (the T02 review, `docs/reviews/T02-review.md` M4, ruling brief Q1/Q2 on the CI pair's measurement) |
| Normative text | ADR 0009 D3 as amended; ADR 0007 D2.2 (the `kappa_2`/`gamma_inf` rows and the paragraph after the table); `T02-recycle-spec.md` §5.8, A34 |
| Evidence | CI run 35979824190's `t02-floats.json` on both runners, annotated in the review §2 M4; `tests/test_t02_identity.py` once the mechanism lands |
| Affected packages | T02 (A34, the identity script, the K04 policy data), K05 (the comparator's sibling-keyed scope), T03/T06 (any float derived from residual differences) |

**Decision.** `kappa_2` and `gamma_inf` are compared under ADR 0007 D2.1's relative rule with no
absolute floor on `acceleration` events whose scaled residual `‖f̂_k‖∞ ≥ 1e-4`, and are recorded,
shape-checked and not value-compared below it. The R0 decisions they feed are promised only with
D2.4's margin (`kappa_2 ∉ [1e7, 1e9]`, `gamma_inf ∉ [1e3, 1e5]`), asserted per platform. Same
policy id: D2.1's formula for every compared float is unchanged; the window is a scope under D2.4.

**Rejected alternatives, and why.** The floors `1.0` and `1e-12` (measured four decades short:
the error is in the *data* of the least squares — residual differences — and scales as
`ε/‖f̂_k‖`; and `κ₂ ≥ 1` by definition, so a floor of one is an absolute allowance of one). A
residual-scaled relative tolerance `1e-9 · max(1, 1e-4/‖f̂_k‖)` (fits every measured event with
margin ≥ 9, but is a new comparison formula and therefore a new policy id, for two intermediate
quantities). "Recorded, never compared" (loses a real check where the data are good — `≤ 3.3e-13`
on 26 of 44 events — and needs a new float class in D2.2 anyway). A window at `1e-6` (REC-05
γ=0.1's event 8 sits at `1.7e-6` and deviates `6.4e-9`).


## R-027 — The work is split by lane, not by model

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | **Frank Peters** |
| Normative text | `CLAUDE.md` ("The two lanes"); `docs/implementation-plan.md` v1.2 §1.3, §4.0; `.claude/agents/specifier.md`, `.claude/agents/verdict.md` |
| Evidence | `tests/test_document_hashes.py` (plan v1.2 pinned); `docs/requirements.yaml` (plan hash) |
| Affected packages | every package from T03 on |

**Decision.** The protocol that assigned work to *Fable* and *Opus* is restated as a **design
lane** (specify, decide, review: agents `specifier`, `architect`, `reviewer`, `verdict`, run at the
highest effort) and a **build lane** (implement: the session and its implementers). Which model and
effort serve a lane lives only in the agent frontmatter. The project agents `fable-specifier` and
`fable-verdict` are renamed `specifier` and `verdict` and run on Opus at xhigh effort. No package,
order, gate or acceptance item changed; the assignment logic of plan §1.3 is the same.

**Rejected alternative, and why.** Keeping model names in the instructions: every change of model
would then be an edit to the plan, `CLAUDE.md` and the agents at once, and a stale name routes a
session to an agent that no longer exists. **Not rewritten:** records — reviews, ADR authorship,
register "decided by" lines, code comments, reference files' `generated_by` — still say who did
the work. Read *Fable* there as the design lane and *Opus* as the build lane.

---

## R-028 — One phase-attempt contract for both paths: a screen that rejects, an adjacent restart, a persistent block

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | design lane (`specifier`, T03 specification pass); ADR 0005, **Accepted 2026-09-24** (T03 manifest `tested`) |
| Normative text | `docs/adr/0005-phase-attempt-contract.md`; `docs/derivations/T03-phase-controller-spec.md` §4–§9 |
| Evidence | `benchmarks/t03/reference_values.yaml` from `docs/derivations/scripts/t03_reference.py` (40-digit twin of the contract on an exact reduction of the A02 region; reproduces T02's measured A28–A31 counts and end temperatures); ablations and the A02 family scan in the same file; tests to come in `evidence/T03/<commit>/manifest.json` |
| Affected packages | T03, K03 (tear controller), T02 (region solve; A30/A31 re-registered; A21's mechanism), K04, K05, T04 (PHS-05 and continuation history handed on) |

**Decision.** One contract and one decision function for the tear path and the lifted EO path,
named `SolvePolicy.phase_contract = "T03-phase-contract-v1"`. On the lifted path every trial of a
single-phase unit is screened with K03 §8.2's admissibility check and a flagged trial asks the
kernel for its regime; a trial in another regime is rejected and halved, and K03 §9.3's patience
and stall rules close the attempt. The restart point is the largest-α phase-rejected trial whose
regime is *adjacent* (one phase added or removed) to the frozen one, the largest-α one only if
none is. A phase leaves only when an attempt ends `BOUND_BLOCKED` on one of its lifted variables; a
landing is an overshoot. The cycle rule (`no_repeated_signature`, 5 attempts) is unchanged. Every
opening is checked (`CHECKPOINT_INCOMPATIBLE` on failure); every attempt records its structural
Jacobian pattern and builds its own evaluation context; a converged, admissible solve carries its
attempt history and a root fingerprint compared at `δ_root = 1e-4` (scaled), claiming neither
uniqueness nor dynamic stability.

**Reverses, with what changed.** R-025's "a phase leaves when any of its lifted variables lands on
its bound" and "appears only at closure", and R-012's unqualified largest-α restart. What changed:
T02 handed over two registered failures and named the missing mechanisms; the twin shows each of
the three new rules is necessary on both (removing any one returns `ACTIVE_SET_CYCLING`), and that
the landing trigger itself sends the correct two-phase attempt back into cycling.

**Rejected alternatives, and why.** Appearance at closure only (T02 A30/A31 cycle); a kernel flash
on every trial (cost, and a verdict that changes with every trial must not steer one); the
smallest-α restart point (5 failures in 75 on the family scan against 2, and it moves K03's OFF-B
restart point); a disappearance threshold (fitted between `1e-5` and `0.43`); letting a signature
recur by count or on merit progress (neither rescues PHS-05); two contracts (two copies of the
cycle rule exist today and nothing keeps them equal).

**Watch for.** A session making the screen also screen the opening state (T02 A21 and PHS-04 open
beyond a phase boundary and must converge); a session restoring the landing trigger because T02
§6.3.3 says so; a session "fixing" `SYN-001-A02-355-dew-guess` with a recurrence rule or a fitted
threshold instead of T04's globalization.

**Extended by R-033 (ADR 0010 D6, accepted 2026-09-24), additively.** The decision function's rows 4–5
and K03 §9.3's stall trigger gain the PTC core's failure-to-advance outcomes (`PTC_STALLED`,
`BUDGET_EXHAUSTED(ptc_steps)`); nothing a Newton or Anderson core produces changes path. PHS-05 is
rescued by T04's edge 3 (R-031), not by any change to this contract; under `eo_recovery: none` it
still ends `ACTIVE_SET_CYCLING` exactly as registered here.

---

## R-029 — A root's fingerprint describes the state, not the path; R0 strings carry no measured float

> **Amended 2026-09-25 by R-056 (ADR 0012 D6):** K03 §8.2's branch rule gains `V = L = 0` → `ZERO_FLOW` (a dormant split). The literal `T03-root-fingerprint-v1` is unchanged; no registered fingerprint has such a split.

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | design lane (`reviewer`, the T03 implementation review, `docs/reviews/T03-review.md` M1, S3, S4, Q1, Q2) |
| Normative text | `docs/derivations/T03-phase-controller-spec.md` §4.10, §8.1–§8.3, §9 as amended; ADR 0005 D7–D8 as amended (accepted 2026-09-24) |
| Evidence | the review's probes P1 (tear vs EO fingerprint of SYN-001's nominal root), P8 (`same_root` inputs), P10 (no-guess default) |
| Affected packages | T03, K04 (certificate's `root_fingerprint`), K05 (identity), T06/T07 (read `same_root`) |

**Decision.** `root_fingerprint.branch_found` is read from the full state, one item per unit with a
lifted split in the declaration, on every path — the tear path's *signature* stays the flash alone
(K03's measured choice), but where the root is does not depend on which controller found it.
`same_root` binds each state to its fingerprint by hash and needs a scale for every id. Message and
cause strings compared as R0 carry no float computed from a solved state. A restart the gate
refused is recorded `restart` in `branch_provenance`; the refusal is the solve's outcome. Dropping a
removed row's orphaned parameter from `constants_sha256` is sound: an initial guess is not a
constant of the problem.

**Rejected alternatives, and why.** `branch_found` over the path's phase-selecting units (the
specification's first text): SYN-001's nominal root by the tear and by the EO path compared
`DISTINCT` at a scaled distance of `4.4e-16` — a false multiplicity claim. Adding the heater to the
tear signature to make the lists agree (reintroduces the crawl K03 measured, `attempts.py`
module note). Rounding the admissibility value in the cause string (quantization splits one value
across a digit boundary on one platform and not the other — ADR 0005's own argument against a
quantized fingerprint).

**Watch for.** A session "restoring" `branch_found = signature` because the signature is what the
attempt froze; a session putting a `repr(float)` back into a grammar that A23 compares byte for byte.

---

## R-030 — The typed homotopy is specification continuation, carried by re-bound pinned inputs

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | design lane (`specifier`, T04 specification pass); ADR 0010 D2 (Accepted 2026-09-24) |
| Normative text | `docs/adr/0010-globalization-homotopy-ptc.md` D2; `docs/derivations/T04-globalization-spec.md` §4 |
| Evidence | `benchmarks/t04/reference_values.yaml` (`homotopy_cases`, `a02_family_scan`, `ablations`) from `docs/derivations/scripts/t04_reference.py` |
| Affected packages | T04, K03 (§12.4's one-context rule for homotopy attempts), K04 (refuses λ < 1 checkpoints), T06 |

**Decision.** v0.1's one typed homotopy continues the pinned value of an A02 region's promoted
specification from its value at the opening state (λ = 0) to its target (λ = 1); every λ-level is a
compiled instance with its own `constants_sha256`, and λ = 1 is the target instance itself. A
natural-parameter controller (Δλ₀ = 1/4, ×2 on acceptance, ÷2 with rollback on rejection,
`HOMOTOPY_STALLED` below 1/1024) with K03's Newton core as a capped corrector, inside one attempt
with a frozen signature; the homotopy never changes the active set. λ is an exact dyadic fraction,
recorded as a string.

**Rejected alternatives, and why.** Recycle-closure continuation (no registered failure to rescue;
SYN-001's recycle is benign); the global Newton homotopy `F − (1 − λ)F(x⁰)` (equal on the registered
cases, but its levels are not physical problems and its offset would live outside the pinned-input
identity ADR 0008 D1.2 assigns to a stage-varying specification); an orchestrator-side offset on the
target instance (a λ < 1 state would carry the target's identity); each λ-level a full contract solve
so that phases can change along the path (a per-level cycle rule for no registered case — a path
crossing a phase boundary stalls, typed and bracketed).

**Watch for.** A session "fixing" HOM-03/HOM-04's stall by letting the homotopy restart phases at
λ < 1; a session computing `p(1)` by the formula instead of using the target instance; a λ written as
a float in an R0 string.

---

## R-031 — Edge 3: cycling and exhaustion are globalization failures; restart from the failed solve's start

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | design lane (`specifier`, T04); ADR 0010 D3 (Accepted 2026-09-24) |
| Normative text | ADR 0010 D3; T04 spec §5 |
| Evidence | T04 `ablations` (`edge3_from_failed_end_state`), `homotopy_cases` HOM-01…05, the family scan |
| Affected packages | T04, T02 (executor), T03 (tests pin `eo_recovery: none`) |

**Decision.** After a region solve ends `LINE_SEARCH_FAILED`, `STAGNATION`, `BOUND_BLOCKED`,
`BUDGET_EXHAUSTED(newton_iterations | ptc_steps)`, `PTC_STALLED`, `ACTIVE_SET_CYCLING` or
`ATTEMPTS_EXHAUSTED`, and the region has a continuation parameter, one recovery region solve runs the
specification continuation from the failed solve's item-0 opening state in its opening signature,
with a fresh contract state; count 1; on by default.

**Rejected alternatives, and why.** Excluding `ACTIVE_SET_CYCLING`/`ATTEMPTS_EXHAUSTED` (the contract
turns globalization failures into restarts, so they surface as its terminal outcome — PHS-05 would be
unreachable); restarting from the failed end state (measured: the λ = 0 corrector fails there and
PHS-05 stays unrescued); PTC as the edge's action (experimental, and provably unable to rescue the
registered failure); firing on `LINEAR_SOLVE_FAILED` (rank deficiency has its own blueprint row).

**Watch for.** A session adding the recovery's own failure as a trigger (recursion); a session treating
`unsupported(no_continuation_parameter)` as success or silence.

---

## R-032 — The PTC mass is residence time × phase-resolved outflow content, enthalpy not internal energy, one θ

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | design lane (`specifier`, T04); ADR 0010 D4 (Accepted 2026-09-24) |
| Normative text | ADR 0010 D4; T04 spec §6 |
| Evidence | T04 `closed_form.loop_modes`; `--check`'s reference-invariance, time-scale and pattern claims |
| Affected packages | T04, T05 (any later holdup model states its mapping the same way), ADR 0008 (the U–H relation it deferred) |

**Decision.** For `syn001.tp_heater` and `syn001.tp_flash`: `N_i = θ Σ_π n_i^π` and
`H = θ Σ_π Σ_i n_i^π h_i^π` over the unit's outlet phases (the heater's lifted split; the flash's S4 and
S5); `M_row = ∂holdup/∂x` on the eight `holdup_balance` rows only; θ = 1 s for both units, the
pseudo-time unit; `PTC_ROW_SIGN` = −1 on `holdup_balance` rows, applied to F and J together.

**Rejected alternatives, and why.** The heater's mole holdup on its stream total `S3.n` (the step then
moves under a change of enthalpy reference off the split manifold; identical on it); internal energy U
(the residence-time vessel has a moving boundary at pinned pressure: the first law accumulates U + PV);
residence times fitted per unit (no data; local attraction holds for every positive ratio); M on the
mixer or an algebraic row (ADR 0008 D3.4 forbids it; refused as `PTC_MAPPING_INVALID`).

**Watch for.** A session "damping" an algebraic row with an artificial M entry; a session tuning θ per
unit to make a case converge.

---

## R-033 — The PTC core: bound truncation and Δτ retries, PTC_STALLED in the contract's rows 4–5, a Newton polish

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | design lane (`specifier`, T04); ADR 0010 D4, D6 (Accepted 2026-09-24) |
| Normative text | ADR 0010 D4, D6; T04 spec §7 |
| Evidence | T04 `ptc_seeds`, `ablations`, `ptc_named` (unpolished envelope 1.31 τ at OFF-B, r = 0.95) |
| Affected packages | T04, T03 (the decision function's rows 4–5, `WallObserver`), K04 (reads the polished states) |

**Decision.** One trial per pseudo-step at K03's bound-aware `α_max`, no merit test; a rejection
(bound, invalid, phase, linear) keeps the state and halves Δτ, ≤ 10 times and ≥ τ_min = 1e-4 s, then
`BOUND_BLOCKED` (last rejection a bound) or `PTC_STALLED`; SER on accepted iterates only, floor inert;
stop on K03 §5.2; reset per attempt; after a stop, one Newton polish kept iff no worse. `PTC_STALLED`
joins T03 §4.8's rows 4–5 beside `LINE_SEARCH_FAILED`.

**Rejected alternatives, and why.** An Armijo line search on α (not blueprint §7.5's method); no polish
(measured: the unpolished stop fails K04's envelope balance — a `FAILED` certificate on a `CONVERGED`
solve); τ_min = 1e-6 (the PTC matrix's condition grows as Δτ⁻²: 3.5e13 at 1e-6 on OFF-A); letting a
PTC stall bypass the contract (the phase-rejected trials of a stalled attempt are exactly the
contract's candidates).

**Watch for.** A session adding a merit test to PTC trials; a session removing the reset because the
SER state "is already small"; a session claiming the φ floor is load-bearing.

---

## R-034 — PTC is experimental in v0.1; V14's qualified-PTC clause is incomplete

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | design lane (`specifier`, T04), on the preregistered criterion of T04 §8.1; ADR 0010 D5 (Accepted 2026-09-24). Frank may choose otherwise (T04 §16 F1) |
| Normative text | ADR 0010 D5; T04 spec §8 |
| Evidence | T04 `basin_comparison_r095` (18 of 18 admitted starts for both cores; 27 of the 45 refused by the mixer, K03 §10.1 — re-registered 2026-09-24, T04 §17 F14, verdict unchanged), `ptc_phs05`, §6.7's structural theorem |
| Affected packages | T04, T06, T08 (the release-gate ledger records V14's PTC clause as a failed item) |

**Decision.** The residence-time family meets route (a) and improves no tested basin on the plan's
registered comparison (SYN-001 at r = 0.95), so it is retained experimental, selectable only by
`eo_core = "ptc"`, never by an automatic path. A later qualification needs a case registered before
its PTC results are known (PTC-R1, the exothermic CSTR, is preregistered in T04 §8.4).

**Rejected alternatives, and why.** Qualifying on the A04 random ensemble (not registered before it
was run; each method wins starts the other loses, by the algebraic snap of perturbed pinned
temperatures); building the CSTR now to qualify the family (chosen after the flash failed — brief §2);
enabling PTC because a block is large (plan §4.3).

**Watch for.** A session flipping `ptc.status` without a new decision and a preregistered case; a
release note calling V14 passed.

---

## R-035 — A certificate judges the declaration the solve solved; the guess is not a specification

| | |
| --- | --- |
| Date | 2026-09-24 |
| Decided by | design lane (`specifier`, T04), on the build lane's finding at `1f632ed`; ADR 0010 D9 (Accepted 2026-09-24) |
| Normative text | T04 spec §4.8; ADR 0010 D9; K04 spec amendment note of 2026-09-24 |
| Evidence | T04 `bound_declaration_certificate` (`ref.bound`); design-lane measurement at `1f632ed`: the nominal verifier on HOM-01's state returns `FAILED` on `HEAT-T` and `specification.S3.T` (355 − 375 K) |
| Affected packages | K04 (input contract and records), T04 (A30–A33), T05/T06 (every revision that frees a variable) |

**Decision.** K04's check set is applied to the declaration the solve solved: for an A02 revision that means `HEAT-T` removed, `SPEC:SPEC-flash-duty` promoted, and a 47 × 47 target. An identity guard refuses a result whose declaration or state is not the verifier's. The freed variable's check is `not_applicable(freed(<id>))`, and the promoted column is checked against the revision's value.

**Rejected alternatives, and why.** Striking the certificate clauses of T04 A03–A08. That leaves a headline `CONVERGED` uncertified, and the unguarded verifier still produces a false `FAILED`. Checking a freed variable against its guess. The guess is blueprint §4.3's tentative initial value, not a constraint, and checking it is exactly the defect. Certifying on the region's 42 × 42. The certificate judges the closed problem, U-FEED included (K04 §7.1).

**Watch for.** A session "fixing" a false `FAILED` on an A02 state by loosening a check or by skipping the guard, instead of reading T04 §17 F9. A verifier that reads a specification value from `binding.flowsheet`. A caller-supplied plan treated as the result's identity, or a revision document not tied to its binding (T04 review S1, S2; amended 2026-09-24).

---

## R-036 — The PH closure lives in the unit layer; the provider gains no PH capability

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05 specification pass); ADR 0011 D1 (Accepted 2026-09-25) |
| Normative text | `docs/adr/0011-unit-models-ph-closure-and-reaction-datum.md` D1; `docs/derivations/T05-unit-models-spec.md` §4 |
| Evidence | `benchmarks/t05/reference_values.yaml` (PHF-1…7, the monotonicity claims, the 53-bit kernel floor `≤ 9.8e-14 K`) |
| Affected packages | T05, K02 (provider untouched), T06, T08 |

**Decision.** A PH-type outlet is K02's lifted TP-state outlet with its temperature free and an energy row; its causal evaluator brackets `Ḣ_TP(n, T, P) = H*` on the provider's TP flash, with a saturation route when one component flows. `FlashRequest`, `FlashResult`, `PropertyCapabilities` and `thermo/syn001.py` do not change; SYN-001's `flashes` stays `("TP",)`.

**Rejected alternatives, and why.** A provider PH flash (the target enthalpy has no field in `FlashRequest`; editing `thermo/syn001.py` moves every SYN-001 `model_version` through R-009's label; an opaque inner solve is what R-008 rejected). Both at once (two descriptions of one function). A plain bisection on `T` with no saturation route (a single flowing component has no `T` that reproduces an enthalpy inside its boiling jump: PHF-6).

**Watch for.** A session adding `"PH"` to the SYN-001 provider "to be general"; a kernel that drops the saturation route because PHF-6 is "a corner case"; an acceptance test on `T` alone that lets `ph_ill_conditioned` go silent.

---

## R-037 — `SYN-001-ref-v1` is a formation datum; reactors balance total enthalpy; liquid reactions are thermoneutral, and registered as such

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05); ADR 0011 D2 (Accepted 2026-09-25). Frank may choose synthetic formation data instead (T05 §19 Q8) |
| Normative text | ADR 0011 D2; T05 spec §6.1 |
| Evidence | T05 `unit_cases` RX-1 (liquid, `Q = 0` exactly) and RX-2 (vapour, `Q = ξ Σ ν_i L_i = 7 500 W`); the claims `vapour_reaction_enthalpy_sum_nu_L=+25000` and `RX-1_liquid_reaction_exactly_thermoneutral` |
| Affected packages | T05, T06 (reactor comparisons: IDAES and DWSIM already enter this datum), T08, M01 (a real reactor's replacement check) |

**Decision.** A, B and C have equal (zero) formation enthalpy and Gibbs energy as pure liquids at `(T_r, P_r)`. Every mass-conserving reaction then has `Σ ν = 0`, every liquid reaction is exactly thermoneutral, and a vapour reaction has `Σ ν_i L_i`. Reactors write `Q + Ḣ_in − Ḣ_out = 0` and never add `ξ Δh_r`; a reactor refuses a provider whose convention is not in the registered set `{SYN-001-ref-v1}`.

**Rejected alternatives, and why.** Synthetic formation data (a new convention or provider: moves or forks the fixture for a test the vapour cases already give). A thermoneutral reactor with no declared datum (`Σ ν_i h_i` would mean nothing, and blueprint §5.3's replacement check would have nothing to compare). A separate heat-of-reaction term (double counting on a formation datum).

**Watch for.** A reactor test registered only in the liquid, where a reactor that ignores the reaction passes; a session "adding the missing heat of reaction" as a separate term.

---

## R-038 — The K02 mixer is not generalized; SYN-001 stays bit-identical

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05); ADR 0011 D1, D3 |
| Normative text | ADR 0011 D3; T05 spec §4.1, §17, A23 |
| Evidence | to be measured: T05 W0.1 baseline and A23 |
| Affected packages | T05, K02, K04, K05 |

**Decision.** `syn001.adiabatic_mixer` keeps its registered subcooled-liquid closure and typed failure (R-007). T05's generalizations (revision-driven flowsheets, lifted-split declarations, a per-model verifier table) must leave every SYN-001 result bit-identical, shown by A23's six items.

**Rejected alternatives, and why.** Generalizing the mixer in place (a lifted outlet changes its rows, hence every SYN-001 `model_version`); a new general mixer now (not in the plan's T05 list; T05 §19 Q3 defers it to the first case that needs it).

**Watch for.** A "harmless" edit to `thermo/syn001.py` or to a K02 row builder during T05; a re-registration of a SYN-001 number presented as a consequence of T05.

---

## R-039 — At most one lifted split per unit in v0.1; separator outlets and exchanger sides are declared single-phase

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05); Frank may want a phase-changing exchanger side (T05 §19 Q2) |
| Normative text | T05 spec §3.4, §7, §10.4 |
| Evidence | T05 HX-F4 (a boiling cold side refused); §10.4's derivation that the terminal check is exact for single-phase constant-`c_p` sides |
| Affected packages | T05, T03/ADR 0005 (unchanged because of this rule), T06 |

**Decision.** Only the PH flash, the valve and the reactor lift a split; the separator's outlets and the exchanger's four ports are in declared phases admitted by R-007. ADR 0005 D2's "one regime per phase-selecting unit" therefore holds unchanged. An exchanger side that would change phase is `unsupported`.

**Rejected alternatives, and why.** Two lifted splits in one unit (needs ADR 0005's signature keyed per split — e.g. `<unit>:<port>` — and, for the exchanger, a zoned composite-curve second-law check, since the terminal check is no longer exact).

**Watch for.** A session lifting an exchanger outlet "for generality" without the per-split signature key and the zoned check.

---

## R-040 — The valve and the pump specify the outlet pressure; the direction constraint is a validity check

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05) |
| Normative text | T05 spec §8, §9 |
| Evidence | both reference tools model them this way (`docs/reference-environments.md` on `wp/T06-refs`, §5.3); T05 VLV-F1, PUMP-F3 |
| Affected packages | T05, T06, K04 (one-sided `bounds_and_domain` checks) |

**Decision.** `VLV-P: P_out − P_spec` and `PUMP-P: P_out − P_spec`. `P_out ≤ P_in` (valve) and `P_out ≥ P_in` (pump) are checked, not written as rows: typed `out_of_domain` in the causal evaluator, one-sided checks in K04.

**Rejected alternatives, and why.** A specified pressure drop (a loop through the unit then closes on a sum of drops that R-011's alias certificate must prove consistent; neither reference tool's default).

**Watch for.** A negative "pressure drop" parameter used to turn a valve into a pump.

---

## R-041 — The pump's ideal work is the isothermal liquid enthalpy rise; no PS flash

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05) |
| Normative text | T05 spec §9.3 |
| Evidence | SYN-001 §2 (`s_i^L = c_p ln(T/T_r)`, independent of `P`); PUMP-1 (`W_s = 19.2 W`, `T_out = 300 + 6.4/240 K`), PUMP-2 (`η = 1`, no heating) |
| Affected packages | T05, T08 (a real provider needs a PS route) |

**Decision.** `η W = Ḣ^L(n_in, T_in, P_out) − Ḣ^L(n_in, T_in, P_in)`, exact for a liquid whose entropy does not depend on pressure; stated as a validity limitation.

**Rejected alternatives, and why.** A PS flash (not needed for this provider; blueprint §6.2 asks for it only when equipment needs it); `W = V̇ ΔP / η` with `v_i` from a new provider property (a provider change for the same number).

**Watch for.** This relation reused with a provider whose liquid has thermal expansion.

---

## R-042 — One exchanger formulation: duty-coupled, countercurrent, second law by `Q ≥ 0` and the terminal differences

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05) |
| Normative text | T05 spec §10 |
| Evidence | HX-1 = HX-2 = HX-3 (the three specifications give one state); HX-F1, F2, F3 each fail exactly one check; C3X |
| Affected packages | T05, K04 (three one-sided checks), T06 |

**Decision.** Rows `HX-energy-hot: −Q + Ḣ_hi − Ḣ_ho`, `HX-energy-cold: Q + Ḣ_ci − Ḣ_co`, one specification from {cold outlet T, hot outlet T, duty}; refused when `Q < 0` or a terminal difference is negative. Exact for single-phase constant-`c_p` sides at constant pressure (the `ΔT` profile is affine in duty).

**Rejected alternatives, and why.** UA–LMTD (0/0 at equal terminal differences, undefined at a cross, wrong with a phase change, and still needs the cross refusal); an approach-temperature specification (not needed in v0.1, T05 §19 Q9).

**Watch for.** A pressure drop added to an exchanger side without re-deriving §10.4.

---

## R-043 — No new quantity kind or tolerance; K04's policy hash does not move

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05); ADR 0011 D3 |
| Normative text | ADR 0011 D3 (iv); T05 spec §9.1, §12.1 |
| Evidence | `verify/certificate.py` `CheckPolicy.sha256` hashes `{policy_id, tolerances by kind}` |
| Affected packages | T05, K04, K05 |

**Decision.** Shaft work, reaction extent, split relations and the one-sided validity checks use existing kinds (`heat_rate`, `molar_flow`, `temperature`, `pressure`). The pump's `W` is a `power` quantity in its manifest and a `heat_rate`-class column for scaling and tolerance.

**Rejected alternatives, and why.** A `power` scaling kind (changes `check_policy_sha256` of every existing certificate for identical numbers); a mass-balance tolerance for the reactor (a new kind; INJ-T3 shows a mass envelope is blind to a permuted stoichiometry anyway).

**Watch for.** A "cleanup" that adds a kind to `QuantityKind` or to K04's table.

---

## R-044 — T05's flowsheet cases are a new family, `SYN-001-UL`; SYN-001 grows no variant

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05); the family's name is Frank's to change (T05 §19 Q1) |
| Normative text | T05 spec §11, §21 |
| Evidence | `benchmarks/t05/reference_values.yaml` `coupled_cases` (C1, C2, C3, C3X); C3's tear-map coupling (`∂T'/∂n = (−3.12, 4.67, 9.74) K per mol/s`) |
| Affected packages | T05, T06 (C3 is a NET-07 candidate; the r-variants rule is untouched) |

**Decision.** Four cases on the SYN-001 thermodynamics with their own reference file: C1 (pump, valve, PH flash; acyclic), C2 (reactor and separator with recycle), C3 (exchanger and PH flash, a thermally coupled recycle), C3X (C3 with an infeasible exchanger; outside the success denominator, never `VERIFIED`).

**Rejected alternatives, and why.** New SYN-001 variants (SYN-001's family is the flash–recycle fixture with its own oracle and derivation; T06 already counts its r-variants as one case).

**Watch for.** C3 counted as NET-07 without T06's decision; C3X moved into the denominator.


---

## R-045 — A revision-built flowsheet is solved as one EO region from `traversal-G0-v1`; the tear path stays SYN-001-only

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`architect`, T05 W0.2) |
| Normative text | `docs/design/T05-generalization.md` §1.1 D1–D2, §2 |
| Evidence | W1.c's bitwise equality of `initial_state` with the legacy start on the SYN-001-shaped revision; C1–C3 solves (W13) |
| Affected packages | T05; T06 (bulk EO solves of revision flowsheets) |

**Decision.** `RevisionFlowsheet` is a new class; `Syn001Flowsheet` is not edited, and `isinstance(flowsheet, Syn001Flowsheet)` selects the legacy path verbatim. A revision-built flowsheet's plan is one `solve_eo` step over every unit with rows, started from two passes of a sequential traversal with dormant torn streams (K03's `G(0)` pattern). The tear path (`_converge`, `solve_tear`) and `run_session` refuse a revision flowsheet, typed.

**Rejected alternatives, and why.** A generalized tear problem (needs `T` in the tear for C3, a generic attempt signature and a generic partial-guess traversal; no assertion requires it). T02's per-node plan with `evaluate` steps (no `SolvePlan`, no fingerprint, so no certificate). A `Protocol` both flowsheets satisfy (every consumer that differs needs the concrete type).

**Watch for.** EO from `G(0)` failing on a thermally coupled loop (design Q-A) — a design-lane question, never extra passes or damping added by the build lane.

---

## R-046 — Lifted splits by a registry keyed by model id; the verifier by a table keyed by model id reading the revision

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`architect`, T05 W0.2) |
| Normative text | `docs/design/T05-generalization.md` §3, §4 |
| Evidence | W1.a (registry output `==` `syn001_lifted_splits`, repr sha `fc36484e…`); W1.d (legacy and general check values bitwise equal at a root and a non-root) |
| Affected packages | T05, K04 (legacy check set untouched), later unit models |

**Decision.** `orchestrator/splits.py` `SPLIT_RULES` maps a model id to one of two split styles (`outlet`, `products`), which makes R-039's one-split-per-unit structural; a structural-agreement guard compares every descriptor with the rows the unit authored. `verify/table.py` `MODEL_CHECKS` holds per-model check formulas evaluated from state, revision and a fresh provider only (R-016); `verify_revision` is the general entry. SYN-001's `verify`, `verify_bound` and `checks.py` builders keep their code, ids, order and values.

**Rejected alternatives, and why.** A `lifted_splits()` member per unit (the K02 heater would need an edit, and a second naming site can drift). Rewriting `checks.py` around the table with SYN-001's ids derived from it (the legacy ids would then be protected by a mapping test instead of by construction).

**Watch for.** A new model with equilibrium rows and no split rule (refused `lifted_split_unregistered`); a model without a check-table entry (`UNVERIFIED`, never `VERIFIED`).

---

## R-047 — A revision-built flowsheet's label carries `configuration_sha256`; `compiled-problem-structure-v2` is not introduced

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`architect`, T05 W0.2); whether this satisfies ADR 0002 D2.7 is Frank's to revisit (design Q-D) |
| Normative text | `docs/design/T05-generalization.md` §1.3, §1.4 |
| Evidence | W1.b label tests: unchanged by a pinned-value change, changed by a phase-capability, parameter-name or inlet-order change |
| Affected packages | T05, K05 (identity), any later revision-built flowsheet |

**Decision.** Label `FSR1-<configuration_sha256[:12]>-<provider>-<impl[:12]>-<data[:12]>`, where `configuration_sha256` hashes the revision minus every pinned value (instances, models, ports, streams, per-model configuration). The builder applies no defaults: an absent required parameter is refused.

**Rejected alternatives, and why.** Module hashes in the label (moves identity on any refactor of an unchanged equation set). `compiled-problem-structure-v2` now (the equations are still Python row builders, as SYN-001's).

**Watch for.** Manifests that assemble equations themselves — then ADR 0002 D2.7 needs structure-v2.

---

## R-048 — Verifier sums over one stream's components use Python's `sum`; every other sum accumulates left to right

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05 ruling round Q-R2), ratifying the build lane's isolated DECISION `15aed94` |
| Normative text | `docs/design/T05-generalization.md` §4.3 (as amended 2026-09-25) |
| Evidence | W1.d's bitwise cross-validation. At the SYN-001-shaped `x⁰`, `Σ S3.liq.*` is 3.7937936767848512 with `sum` and …517 left to right, so `material_balance.total.S3.L` is `0.0` legacy against `−4.44e-16` general |
| Affected packages | T05 (`verify/table.py`); every later check-table entry |

**Decision.** A Σ over the component index of quantities belonging to one stream — its flows, its lifted flows, flow × property products, mole fractions and fraction × `K` products — uses Python's builtin `sum` in component order. That is the primitive of K04's legacy builders, and it is Neumaier-compensated on CPython ≥ 3.12; the project requires ≥ 3.13. Every other sum (ports, streams, instances, envelope terms) accumulates left to right with the operators as written.

**Rejected alternatives, and why.**
- Uniform left-to-right. The note's original text; it breaks the bitwise pairing with the legacy at non-roots.
- `math.fsum` everywhere. Correctly rounded and version-independent, but it differs from the frozen legacy's `sum` wherever Neumaier is not correctly rounded.

**Watch for.**
- A "tidy-up" to one summation style. The W1.d cross-validation fails at `x⁰`.
- A CPython change to float `sum`. Legacy and general move together, but recorded fixtures could move in the last bit.

---

## R-049 — The PH kernel accepts on the energy residual alone; it has no conditioning criterion

> **Reversed 2026-09-25 by R-052 (ADR 0012 D2)**, on Frank's answer to T05 §19 Q11 ("the PH solver should be able handle near-pure feeds"). The near-pure class is no longer a limitation. What survives of this entry: no *refusal* criterion is added, and no trace threshold routes a feed. What changed: the acceptance checks the closure's rows, not the energy alone, and a failed temperature route falls back to a band route.

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05 ruling round Q-R1) |
| Normative text | `docs/derivations/T05-unit-models-spec.md` §4.4, step 5 and "What `ok` guarantees" (as amended); A29 |
| Evidence | Ruling-round measurement on `(ε, 2, 0)` and `(0, 2, ε)` at `P_r`, with targets across pure B's latent jump. At `ε ≤ 1e-9` every target except mid-jump is `ph_ill_conditioned`, with `|f| ≥ 2.6e-2 W`. Mid-jump is `ok`, with `β = 1/2`, `|f| ≤ 2.6e-5 W`, and error against the lever rule `≤ 7e-10 mol/s`. At `ε = 1e-6` every target is `ok` |
| Affected packages | T05 (PH flash, valve, duty-mode reactor); T08 (real providers, high-purity streams) |

**Decision.** `ok` iff the returned split carries `H*` to within `τ_E`, on both routes. An `ok` answer for a near-pure feed is accurate to `τ_E`'s resolution: `|ΔV| ≤ τ_E/min Δh_i` plus the trace terms. Which targets inside the jump are answered is a registered limitation.

**Rejected alternatives, and why.**
- Refuse whenever adjacent doubles of `T` differ in `Ḣ` by more than `τ_E`. It refuses answers that are right to `τ_E`, and no registered case calibrates the threshold.
- Route an "effectively pure" feed to the saturation route above a trace threshold. That quantizes the state on the exact path, which CLAUDE.md forbids.

**Watch for.** A later session treating the mid-jump `ok` as a false success and adding a criterion. Only the remedy of spec §19 Q11 changes this, and that remedy is a design decision.

---

## R-050 — Two EO limitations are registered, never certified: a dormant PH-type outlet and a single flowing component in the latent jump

> **Reversed 2026-09-25 by R-053 (ADR 0012 D4) and R-054 (D7)**, on Frank's answer to T05 §19 Q12 and the build lane's scope for §4.7 (a). Both EO states are solved and certified under `T05b-phase-contract-v2`. What survives: the dormant-temperature singularity of **non-lifted** energy-determined outlets (pump, exchanger side), now in R-057 — itself reversed on that point by R-058 (ADR 0012 D12, 2026-09-25).

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05 ruling round Q-R4, Q-R8; review S3). Bringing either into scope is Frank's (spec §19 Q12, Q4's remedy) |
| Normative text | `docs/derivations/T05-unit-models-spec.md` §4.7 (a), (b); §18; A28, A30 |
| Evidence | W0.8: `CONVERGED` at iteration 0, K04 screen `RANK_DEFICIENT` (15 of 18; three zero equilibrium rows). Review P3 and P4: `ACTIVE_SET_CYCLING` and `BOUND_BLOCKED`; the control with `1e-6 mol/s` of A converges |
| Affected packages | T05; T06 (flowsheet generators must not count these as solvable); ADR 0005 (any remedy) |

**Decision.**
- **Dormant PH-type outlet.** From the traversal start the solve is `CONVERGED` with an `UNVERIFIED` certificate (`rank_limitation`). `branch_found` keeps K03 §8.2's `else` arm (`TWO_PHASE`) for a dormant split, and the certificate's `phase_branch` records `ZERO_FLOW`.
- **One flowing component in the jump.** The saturation route is causal-only. On the EO path the outcome is a typed failure, never `VERIFIED`. `initial_state`'s re-flash is kept, and its comment corrected.

**Rejected alternatives, and why.**
- Forcing a Jacobian so that the dormant case fails typed. That adds code whose only purpose is to fail a correct root.
- Reporting `ZERO_FLOW` in `branch_found` now. That changes T03 §8.2's rule and R-029's fingerprint without an ADR, and ADR 0005's lattice has no `ZERO_FLOW`.
- A saturation-aware phase classification in T05. It is an ADR 0005 change, no registered case needs it, and K04's independent split shares the same blind spot.
- Seeding `initial_state` from the unit's closure split. It changes no outcome: the review re-seeded from the exact split and the solve still failed.

**Watch for.**
- A flowsheet generator (T06) emitting either state as a success case.
- Any ADR that adds a `ZERO_FLOW` regime, or a `TWO_PHASE` classification at `ln K_k = 0`. It retires this entry and A28/A30's expectations together.

---

## R-051 — The reactor's causal evaluator writes the key's outlet as `n_k − X·n_k`; the rows keep `n_in + ν ξ − n_out`

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05 ruling round Q-R7; review S2) |
| Normative text | `docs/derivations/T05-unit-models-spec.md` §6.3 (as amended), §14 (exact zeros) |
| Evidence | Review P2: `X = 1` refused as `reactant_exhausted(<key>)` for 6.6 % of feeds at `ν_k = −3`, 5.9 % at `−5`, 4.2 % at `−7`, and 0 at `−2`. For `|ν_k| ∈ {1, 2}`, which covers every registered case, the two forms are bitwise identical |
| Affected packages | T05 (`syn001.conversion_reactor`); any later reactor |

**Decision.**
- The key's outlet is `n_k − X n_k`. That is exactly `0.0` at `X = 1`, and never negative for `X ≤ 1`, because rounding is monotone.
- The other components are `n_i + ν_i ξ`, and exhaustion is tested on every component in component order; only a non-key can trigger it.
- There is no clipping.
- `RX-mole` is unchanged: it is the same function, and at the causal answer the key's row is within a few ulps.

**Rejected alternatives, and why.**
- `n_k + ν_k ξ`. The textbook form, and what the spec first wrote; it refuses legitimate full conversions.
- Clipping. It violates ADR 0001 D2.3.
- Changing the rows to match. That would change the rows' structure and `model_version` for no gain in the residual.

**Watch for.** A "consistency" edit that makes the evaluator write the key's outlet like every other component. The sweep test at `ν_k ∈ {−3, −5, −7}` fails.

---

## R-052 — The PH kernel accepts on the closure's rows and falls back to a band route in the vapour fraction (reverses R-049)

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05b); ADR 0012 D1–D2 (Accepted 2026-09-25). Directive: Frank, T05 §19 Q11; steer: robustness through recorded fallbacks |
| Normative text | `docs/derivations/T05b-limitations-spec.md` §4–§5; ADR 0012 D2, D10 |
| Evidence | `benchmarks/t05b/reference_values.yaml` (the 40-state grid, the JUMP and BIASED doubles); T05 ruling-round measurement (`|f|` 2.6e-2…1.2e2 W off mid-jump) |
| Affected packages | T05 (the kernel; A29 retired), T08 (high-purity streams) |

**Decision.** `ok` iff the answer satisfies the PH closure's material, equilibrium and energy rows at K04's registered tolerances, evaluated by the kernel. Order: saturation route (one flowing component), temperature route, then — when the temperature route's answer fails the rows and ≥ 2 components flow — the band route (bisection on `β` of `H(β)`, `T(β)` from the temperature form of Rachford–Rice, split from the provider's K-values, width floor `2⁻⁶⁰`, ≤ 64 evaluations); `ph_ill_conditioned` only when no route passes. The switch is recorded (`PHState.route`; `closure_route(<unit>, band)` on a region's start).

**Rejected alternatives, and why.** The band route as the only two-phase route (moves the last bits of every registered two-phase answer and, through starts, C1–C3's iteration records). Energy-only acceptance (trusts the provider's flash: a flash 1e-5 off in `β` meets energy 2.2e-4 K wrong). A refusal criterion or a trace threshold (R-049's reasons stand).

**Watch for.** A "simplification" back to energy-only acceptance because SYN-001's own flash never fails the equilibrium clause — the BIASED double (T05b B04) is there to fail it. A band route used as the primary to "unify" the kernel.

---

## R-053 — Phase contract `T05b-phase-contract-v2`: a PH-type split is classified by its PH closure, starts unprojected, and has a `ZERO_FLOW` regime (reverses R-050)

> **Amended 2026-09-25 (T05b ruling round Q-S10, Q-S11 (a); review S1, S2):** a restart opening writes the PH closure's temperature to *every* temperature column of the split's streams (a products-style split's liquid product too — left at the trial's value it cost NP-G its restart, *measured*); and the screen of a flagged PH-type trial decides the regime by comparing `H_split` with the band's end enthalpies, asking the full closure only within `τ_E` of an end or when a comparison evaluation fails (exact wherever the closure answers `ok`, since an `ok` answer carries `H_split` to `τ_E`); the full closure stays at openings, and an opening reuses a screen answer at the same state. *Watch for:* the screen reverted to the full closure "for exactness" (it costs a band route per flagged trial: 12 598 calls at NP-1 against the 10 000 metered); the `τ_E` zones dropped (the comparison is exact only outside them); an opening setting only the registry's temperature column.

> **Amended 2026-09-25 by R-058 (ADR 0012 D4 (c), second pass):** at closure, every row a zero-flow form swapped out (a PH-type split's energy row) must hold at the final state, else `SPECIFICATION_CONFLICT`, `zero_flow_conflict(<row id>)`. A dormant PH flash or duty-mode reactor with `Q_spec ≠ 0` otherwise converged its zero-flow form to a state violating `PHF-duty`/`RX-duty` (T05b spec F6, DZ-2C).

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05b); ADR 0012 D3–D5 (Accepted 2026-09-25). The schema widening is Frank's to approve (T05b §18 Q1) |
| Normative text | T05b spec §6–§8; ADR 0012 D3–D5, D10 |
| Evidence | this pass, *measured*: C1–C3 consult the kernel only at T02 §6.2, where the start equals the kernel's split bit for bit; P3/P4 seeded and unprojected converge at once. Twin: `max h^L(T_max) = 14 010 < min h^V(T_min) = 23 000 J/mol`; zero-flow forms regular (`rcond₁` 0.013…0.25) |
| Affected packages | T03/ADR 0005 (second literal), T05, T06 |

**Decision.** A new literal, not an amended one (ADR 0005 D1). Under v2: the kernel of a PH-type split (valve, PH flash, duty-mode reactor) is `ph_state` at the split's own enthalpy, taking split and temperature; the TP flash is its recorded fallback (`fallback(<unit>, tp)`) when the PH closure refuses or the split leaves `ZERO_FLOW`. A PH-type split opens with its unit's closure split, not T02 §6.2's projection. `ZERO_FLOW` (feed exactly dormant) pins the split's lifted flows, drops its equilibrium, split and definition rows, and for a PH-type split replaces the energy row by the label row `<U>:zero-flow-label` (`T_out − T_inlet`), a row of the attempt and of the verifier's form but never of the compiled declaration; it is adjacent to every flowing regime; the screen checks dormancy agreement at every trial. `initial_state` seeds a PH-type split from its unit's closure under both literals (bitwise on the bracket route). v1 stays verbatim for every registered policy; v2 ≡ v1 on C1–C3 (T05b B07).

**Rejected alternatives, and why.** Amending v1 in place (D1's promise). A tolerance band around `T_sat` in the TP classification (one component only, a threshold, still far from a narrow band). Seeding without the PH kernel (fails from a wrong-regime start: SC-3). A compiled label row (moves `model_version` of C1/C3; T01 sees a non-square declaration). Holding the dormant temperature at its opening value (stale when the inlet label moves: DZ-3).

**Watch for.** A session making the TP flash the PH-type kernel again "for consistency"; a label row added to a unit's declaration; the v1 rules edited instead of gated.

---

## R-054 — The verifier judges a temperature-degenerate split by the split it carries, and a zero-flow root by its zero-flow form (amends R-016 (4))

> **Amended 2026-09-25 by R-061 (ADR 0013 D3):** a second substitution class, *unresolved* two-phase splits (band narrower than the fresh flash resolves at double precision: `N ulp(T)/(w τ_flow) ≥ 1/10`, temperature inside the band), is judged by this entry's substitution with the branch's own admissibility and `independent_split` `not_applicable(fresh_flash_unresolved)`. The degeneracy window itself (`τ_T`) is unchanged; its "watch for a session widening the window to close T04 F9's band" is answered by that explicit decision, which is a resolution criterion, not a wider window.

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05b); ADR 0012 D7 (Accepted 2026-09-25) |
| Normative text | T05b spec §9; ADR 0012 D7 |
| Evidence | this pass, *measured*: P3/P4 at their roots fail only `energy_balance` (by `β n Δh` = 2 016 W and 30 000 W) and `independent_split` (by `β n`), regularity `NO_RANK_LOSS_DETECTED`; P4 with a 1e-8…1e-12 trace `FAILED` on the products' fresh flashes (0.09…1 272 W). Twin: injections INJ-B1…B3 |
| Affected packages | K04 (revision table only), T05, T04 (F9 unchanged) |

**Decision.** Temperature-degenerate: bubble and dew temperatures both within `τ_T` of the stream's temperature (no new threshold). For such a split the revision table takes enthalpies from the stored split, checks `phase_admissibility.<U>.<S>.saturation` (the distance, at `τ_T`), and reports `independent_split.<U>.<S>` `not_applicable` (`temperature_degenerate`); outside splits, a degenerate stream is taken in its declared phase. At a zero-flow root the regularity matrix is the zero-flow form and `residual.<U>:zero-flow-label` is checked. No category, kind, tolerance or policy hash changes; the legacy SYN-001 set is untouched; every registered state is ≥ 17.5 K from degenerate.

**Rejected alternatives, and why.** The stored split for every PH-type or two-phase split (reverses R-016 (4) broadly; loses INJ-T1's registered energy failure). Falling back to the stored split whenever the fresh flash disagrees (resolves T04 F9 for wide mixtures as a side effect — out of scope, a K04 decision). A wider window (no registered tolerance gives one).

**Watch for.** The degenerate judgement called "a relaxation": it is a substitution that still fails a wrong vapour fraction (INJ-B1, 2 016 W) and a temperature off saturation (INJ-B2, 10³ τ). A session widening the window to close T04 F9's band.

---

## R-055 — R-007 admits a temperature-degenerate stream in either single phase (amends R-007)

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05b); ADR 0012 D8 (Accepted 2026-09-25) |
| Normative text | T05b spec §10 |
| Evidence | twin: R7-1…R7-4; T05's five refusals `δ ≥ 14.27 K`; SC-4 (today `INITIALIZATION_FAILED` at `inadmissible_phase(inlet, VAPOR)`) |
| Affected packages | K02 (`tp_state.single_phase_admissible`, refusal path only), T05; K04's declared-port check keeps its form (it reads R-054's enthalpy map) |

**Decision.** A stream refused by R-007's gap is admitted when temperature-degenerate; the reported gap is the degeneracy distance. The causal layer cannot tell which phase a degenerate stream was assigned upstream, so it admits both; the certificate's enthalpy map knows and decides.

**Rejected alternatives, and why.** Returning the saturation temperature on the liquid side of `T_sat` (fixes the liquid product and breaks the vapour product). Leaving the coin flip (a pure product's consumer succeeds or fails on the last bit of a bisection).

**Watch for.** The window reused as a general tolerance on R-007.

---

## R-056 — `branch_found` reports `ZERO_FLOW` for a split with `V = L = 0` (amends R-029)

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05b); ADR 0012 D6 (Accepted 2026-09-25) |
| Normative text | T05b spec §8 |
| Evidence | to be measured: T05b W0.4 (no committed record has such a split) |
| Affected packages | T03, K04 (fingerprint), T05, T06 |

**Decision.** `V = L = 0` → `ZERO_FLOW`, before the other arms, under both literals: the fingerprint describes the state. The literal `T03-root-fingerprint-v1` stays.

**Rejected alternatives, and why.** Bumping the fingerprint literal (moves every certificate's R0 identity, SYN-001's included). Keeping the `else` arm (the fingerprint would describe the form a v1 attempt ran, which R-029 itself rejects).

**Watch for.** A pre-T05b record of a dormant split compared with a new one: `DISTINCT` by construction.

---

## R-057 — What T05b leaves registered: near-pure EO certification in T04 F9's band, and dormant non-lifted outlets

> **(1) reversed 2026-09-25 by R-059…R-061 (ADR 0013)**, on Frank's decision to fold T04 F9 into T05b ("as little limitations as possible"): NP-G is certified by the projection (D1), the admissible phase reading (D2) and the unresolved-split routing (D3); no tolerance is loosened. The rejected alternatives below stay rejected: the window is not widened and no disagreement fallback exists.

> **(2) reversed 2026-09-25 by R-058 (ADR 0012 D12)**, on Frank's answer to T05b §18 Q2 ("include them in T05b"). Dormant non-lifted outlets get a zero-flow form carried by signature items; the rejected alternative below (adding them to `signature_units`) stays rejected, now for the reason R-058 gives. (1) stands.

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05b); ADR 0012 D9. Bringing either into scope is Frank's (T05b §18 Q2, Q3) |
| Normative text | T05b spec §17 |
| Evidence | twin emulation: NP-G's fresh flash misses by 4.2 `τ_E`, 2.2 `τ_flow`; T05b W0.7 measures the band on the implementation |
| Affected packages | K04 (T04 Q8 closes the first), a later package (the second), T06 |

**Decision.** (1) Between the degeneracy window and the fresh flash's resolution (2 mol/s of B: traces of ~5e-8 to ~4e-7 mol/s; wider with flow), a converged, correct near-pure state may be certified `FAILED` by T04 F9's mechanism; no verifier fallback that loosens a tolerance is added (Frank's steer excludes it). (2) A dormant pump outlet, exchanger side or all-dormant mixer outlet has no regime and stays never `VERIFIED`.

**Rejected alternatives, and why.** Closing (1) with a wider window or a disagreement fallback (R-054's reasons). A zero-flow regime for non-lifted units now (adds them to `signature_units`: C1–C3's R0 identity moves).

**Watch for.** A T06 generator emitting either state as a certified success; a session closing (1) by relaxing a check.

---

## R-058 — Dormant non-lifted outlets get a zero-flow form carried by signature items, not by signature units; every swapped row is tested at closure (reverses R-057 (2); amends R-053)

> **Amended 2026-09-25 (T05b ruling round Q-S4, Q-S9; R-065):** the opening's item recomputation and outlet resets are part of one fixed point with every lifted split's `ZERO_FLOW` membership (R-065), and a reset is redone whenever a later write in the same opening makes it stale; the screen of spec §7.8 (iii) runs at every trial of a v2 attempt in a region with a dormancy-form outlet, an empty signature included (the Newton core's `signature and …` shortcut had skipped it); a dormant exchanger side's terminal checks carry K04's existing reason `ZERO_FLOW`, which the `t05b` key carries as R0. *Watch for:* the empty-signature shortcut restored as an optimization; the reason lower-cased to match the spec's first text; resets limited to "at most once".

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | Frank (scope: T05b §18 Q2, "include them in T05b", accepting a `t05` re-registration; SYN-001 must not move); design lane (`specifier`, T05b second pass) for the mechanism; ADR 0012 D12 (Accepted 2026-09-25) |
| Normative text | T05b spec §7.6–§7.10, §9.3; ADR 0012 D4 (c), D7, D12 |
| Evidence | twin (`t05b_reference.py`, 585 claims): DZ-6…DZ-12 zero-flow forms regular (`rcond₁` 0.0131…0.250), declared forms one rank short per outlet; the nine exchanger patterns; DZ-12's opening singular without the outlet reset; DZ-11/DZ-2C swapped rows at ∓1 000 W; trigger streams flowing at C1, C2, C3, C3X, SC-4. To be measured: W0.10 (no committed record has an active form) |
| Affected packages | T03/ADR 0005 (signature items under v2), T05 (pump, exchanger; K02 mixer by registry only), K04 (revision table and `verify/zero_flow.py`), K05 (the `t05b` key), T06 |

**Decision.** The pump's outlet, an exchanger side whose outlet temperature is not the specification, and the K02 mixer's outlet (every inlet dormant) have a registered zero-flow form: when every stream of the trigger port is exactly dormant, the unit's energy row is swapped for the label row `T_out − T_label` (never compiled). An attempt carries it as an item `[<U>.<port>, ZERO_FLOW]` appended to its signature only while active; the plan's `signature_units` still lists lifted units only. Items are recomputed at every opening after the lifted splits are set, and an outlet whose item changes has its flows set to its mole balance. At closure, every swapped row — non-lifted or a lifted PH-type split's — must hold, else `SPECIFICATION_CONFLICT`, `zero_flow_conflict(<row id>)`. The verifier reduces a dormant non-lifted outlet from the state (both literals), checks its label, and does not judge an exchanger's terminal differences at a dormant side. No registered identity moves; the accepted `t05` re-registration is not used.

**Rejected alternatives, and why.** Making the units signature units (moves every plan and signature containing a pump, exchanger or K02 mixer — C1–C3's `t05` key and every T02–T04 key — and the exchanger has two outlets under one unit id). A regime-free per-call switch (equations changing inside an attempt: breaks frozen attempts, residual/Jacobian pairing and the cycle rule). Bare unit ids or stream ids as keys (hot-only and both-sides forms indistinguishable; a different namespace). Leaving a zero-flow conflict to the certificate (a false `CONVERGED` by the full duty).

**Watch for.** A session adding pumps, exchangers or mixers to `signature_units` "for uniformity"; a label row compiled into a model; a zero-flow form selected by a flow threshold; an item left in place after an opening's kernel split makes its inlet flow; the swapped-row test dropped because "the certificate catches it".

---

## R-059 — K04 judges its fresh-flash checks at its own one-step Newton projection of the certified state (T04 F9)

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05b's F9 pass); ADR 0013 D1 (Accepted 2026-09-25). Scope: Frank, 2026-09-25, "Fold F9 into T05b" |
| Normative text | `docs/derivations/K04-F9-spec.md` §5.1; ADR 0013 D1, D5 |
| Evidence | twin (`k04f9_reference.py`, 25 claims): the A02 family's S3 values 155/9/15 raw (worst 27.28) → ≤ 2.107e-5 after one step, `‖F̂(x̃)‖∞ ≤ 3.14e-15`; *measured* with the rule prototyped: 179/179 `VERIFIED`, DZ-3 and DZ-10 `VERIFIED`, the suite's 16 residual-failing injections unchanged, K05 identity (`622463f5…`, `b364bb3d…`, `ddbd0f71…`) and `check_policy_sha256` unchanged |
| Affected packages | K04 (verifier), T04 (A32, A33), T05b (B16, B26), K05 (fixtures), T06 |

**Decision.** When every residual row of `x_final` passes and the regularity screen is `NO_RANK_LOSS_DETECTED`, the verifier computes `x̃ = x_final + S_x(−Ĵ⁻¹F̂)` with the screen's own matrix and factorization, keeps every exactly-zero flow at `+0.0`, accepts `x̃` iff its flows are nonnegative, its flowing `(T, P)` in domain and its rows inside tolerance, and evaluates `energy_balance`, `phase_admissibility`, `independent_split` (and the routing among their forms) there. Everything else stays at `x_final`. Recorded in `transformations.projection` (R0, float-free). No tolerance, kind or policy hash changes.

**Rejected alternatives, and why.** Propagated tolerances (T04 Q8's default: the tolerance becomes a computed float against ADR 0007's `exact_fields`; widens energy checks by up to 174 τ_E; leaves 4–7 family states in D2.4's band). A solver-side polish (moves every EO solve's R0 records and SYN-001's identity; cannot reach NP-G's resolution floor; leaves the verifier inconsistent for unpolished states). Judging every category at `x̃` (a specification would read 0 there). Projecting without keeping exact zeros (measured: SYN-001's `.bubble` becomes `.closure`).

**Watch for.** A session projecting a state whose rows fail ("to get a better diagnosis": it would hide registered failing sets); dropping the exact-zero rule; recording the step as a float without an ADR 0007 path; moving `specification` or `residual` checks to `x̃`; applying the projection inside `run_checks` (partial checkpoints).

> **Amended 2026-09-27 by ADR 0013 Amendment 2 (T07 ruling round 5, M1; `docs/reviews/T07-review.md` M1):** where D1 or D3 reads a tolerance **to route** — guards 1 and 5 here, R-061's `τ_flow` — it reads ρ_k = max(τ_k(policy), τ_k(registered)) of the kind in question; the policy's own τ enters a certificate only as the right-hand side of `|value| ≤ τ`. Under a policy that only tightens, the certificate equals the registered one in every check id, order, value (bitwise), `transformations.projection`, `target_state_sha256` and regularity evidence, and differs only in `tolerance`, `result`, `near_threshold` and the grade; a loosened policy is routed as before. *Measured before the rule* (`b36a018`, 44 certifying corpus revisions): `τ_flow` × 1e-6 deleted checks in 24 (SYN-001-nominal 147 → 144), each reading `RELAXED` with no failing check. At the registered policy nothing moves (44/44 certificates byte-identical; `check_policy_sha256` `21c44e10…`). Evidence: G12.1–G12.10. **Rejected:** the registered τ for every routing read (moves loosened-policy certificates; K04 INJ-4); a floor on tightening (the resolution floor is a property of the unknown solved state); an unresolvable tightened check reported `unsupported` (withdraws computable evidence). *Watch for:* a routing read of the policy's own τ; a stricter request that removes a check.

---

## R-060 — The verifier's fresh flash decides a single phase at K03's `ε_adm` (the saturated-product kink)

> **Amended 2026-09-25 (T05b ruling round Q-S5 (1)):** the order is the provider's decision first; the two `ε_adm` tests (`Σ z K ≤ 1 + ε_adm`, then `Σ z/K ≤ 1 + ε_adm`, in `admissibility_checks`' arithmetic) replace only a two-phase answer. The first text's order (bubble test before the provider) would read a stream the provider calls vapour, with a bubble excess in `(0, ε_adm]`, as liquid — a whole latent heat apart, and against its own "bitwise unchanged" promise; such a stream is degenerate and never reaches `enthalpy_flow` in the table. *Watch for:* re-ordering to the first text.

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`); ADR 0013 D2 (Accepted 2026-09-25) |
| Normative text | `docs/derivations/K04-F9-spec.md` §4.2, §5.2 |
| Evidence | *measured*: DZ-3's liquid product 2.125e-8 past its bubble point at Newton's stop, `A_L = 6.247e4 W` (twin), the 1.3272e-3 W failure; one ulp of excess at NP-GC's copies is worth 0.103 τ_E each (twin) |
| Affected packages | K04 (`checks.enthalpy_flow`, both engines) |

**Decision.** A flowing stream whose bubble excess is `≤ ε_adm = 1e-12` is read as liquid, else one whose dew excess is `≤ ε_adm` as vapour, else by the provider's flash; bitwise unchanged wherever the provider already reads it single-phase. It applies to stream enthalpies, not to the independent split's flash of a split's feed.

**Rejected alternatives, and why.** Bounding the kink by a propagated tolerance (needs rows outside the lifted block for copies); an assigned-phase map per stream (a second declaration of phases in the verifier; the excess test needs none).

**Watch for.** `ε_adm` widened "to be safe" (it is K03's registered admissibility tolerance, not a free parameter); the rule applied to a split's feed.

---

## R-061 — A two-phase split whose band the fresh flash cannot resolve is judged by its stored split (closes T05b D9 (1); reverses R-057 (1))

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`); ADR 0013 D3 (Accepted 2026-09-25) |
| Normative text | `docs/derivations/K04-F9-spec.md` §4.3, §5.3 |
| Evidence | twin: NP-G's floor ratio `N ulp(T)/(w τ_flow)` = 0.8896 (unresolved, 8.9× over 1/10), NP-3's 0.01712 (resolved, 5.8× under), every other registered split ≤ 2.7e-6; *measured* at NP-G's projection without it: independent split 0.44 τ_flow against a floor of 0.89 |
| Affected packages | K04 (`verify/table.py`), T05b (B13) |

**Decision.** After ADR 0012 D7's degeneracy test, a split whose stored branch is two-phase, whose temperature lies in its feed's band `[T_b, T_d]`, and whose floor ratio is `≥ 1/10` is unresolved: enthalpies from the stored split (qualified `fresh flash unresolved (ADR 0013 D3)`), admissibility by its branch's own check, `independent_split.<U>.<S>` `not_applicable(fresh_flash_unresolved)`. No constant is registered (`τ_flow`, D2.4's 10, IEEE's `ulp`).

**Rejected alternatives, and why.** A wider degeneracy window (`.saturation`'s tolerance would become a computed float; band containment says nothing of a narrow band whose ends are far from `T`). Letting the comparison pass at its own floor (a platform lottery). A temperature-form independent split (weak at the registered `τ_T`: at NP-G it resolves the vapour fraction only to 0.24; the stored-split energy balance carries the information).

**Watch for.** The criterion applied to a single-phase branch or to a pure stream off saturation (its zero-width band contains no temperature but `T_sat`: INJ-B2′ must stay fresh-flash judged); the threshold tuned to a case.

> **Amended 2026-09-27 by ADR 0013 Amendment 2 (see R-059's note):** the criterion reads ρ_flow = max(τ_flow(policy), τ_flow(registered)): `N ulp(T)/(w ρ_flow) ≥ 1/10`. A caller who tightens `τ_flow` can no longer route a split out of the independent flash.

---

## R-062 — K04 §4.7's flash-outlet clause: implemented for revision-built flowsheets, discharged by §4.4 in SYN-001's legacy set (T04 F10)

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`); ADR 0013 D4 (Accepted 2026-09-25); adding the legacy checks is Frank's (it re-registers SYN-001's identity; spec §12 Q1) |
| Normative text | `docs/derivations/K04-F9-spec.md` §5.4 |
| Evidence | INJ-F10 (twin and *measured*): SYN-001 once-through with the flash forced all-liquid passes every row and `FAILED`s exactly the flash and envelope balances by −38 338.069 446 744 W; flash outlets' split ≤ 3e-33 τ_flow at every family projection |
| Affected packages | K04 |

**Decision.** `verify/table.py` keeps checking every lifted split, the TP flash's included. SYN-001's legacy set adds no check: a wrong flash branch fails §4.4 through the fresh flash of S5 and its copies. INJ-F10 is registered.

**Rejected alternatives, and why.** Five new ids on SYN-001's nominal certificate (moves SYN-001's identity document, against Frank's condition of 2026-09-25). Striking the clause from K04 (it holds, and is implemented, for revision-built flowsheets).

**Watch for.** A "completeness" change adding the legacy checks without the identity re-registration.

---

## R-063 — T05b's EO state comparisons: the margin is asserted on the realized deviation; K04's solution-error bound is recorded, never thresholded

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05b ruling round, Q-S1) |
| Normative text | `docs/derivations/K04-F9-spec.md` X26 and §10.6 (as amended); T05b spec §13 (EO row), §20 W0.9 |
| Evidence | *measured* (F9 W0, W8): NP-GC `b = 1.212e-7` with its compared streams 6.7e-9 mol/s from `ref` (46× inside 3.1e-7); DZ-3/DZ-10 `b = 3.679e-8` with `S4.T` 8.1e-7 K from `ref` (12× inside 1e-5 K); W0.7's `VERIFIED` sweep states reach `b = 1.07e-7`; K04 §7.4's own amendment of 2026-09-22 (the same defect at the verdict level) |
| Affected packages | T05b (X26, B31, B33), any later package registering EO state comparisons (T06) |

**Decision.** For T05b's EO cases compared with a 40-digit reference at T02 §6.4's allowances, the evidence that a comparison has margin is its realized deviation, asserted `≤ 1/10` of each allowance (ADR 0007 D2.4's band edge) and recorded per case. K04's `solution_error_bound_scaled` `b` is recorded on every case as a regression value and compared with no threshold. NP-GC is in the population.

**Rejected alternatives, and why.** `b ≤ 1e-7` (K04-F9 §10.6's first form) and `b ≤ 1e-8` (T05b §13's first form, T05 §11.5's rule): `b = ‖Ĵ⁻¹‖₁‖F̂‖∞` tracks where Newton or the causal kernel's row-tolerance acceptance stopped, not the error it bounds (it exceeds the realized scaled deviation 4.5× at DZ-3, 54× at NP-GC, and it is not itself an ∞-norm bound, which is `n b`), so a threshold at the allowance is a lottery on the stopping point. Excluding NP-GC (narrowing the denominator after a failure). A larger threshold on `b` (keeps the wrong quantity).

**Watch for.** A session reinstating a threshold on `b` "for rigor"; a realized deviation reaching 1/10 of its allowance answered by widening the allowance instead of a report; T05 §11.5's `b ≤ 1e-8` (C1–C3, met, not amended) cited as the pattern for a new package.

---

## R-064 — K03's Newton releases structural zeros before declaring `BOUND_BLOCKED`

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05b ruling round, Q-S11 (b)); scope: the build lane's DECISION under Frank's standing directive ("as little limitations as possible"; robustness first) to fix the review's S2 inside T05b rather than register a limitation |
| Normative text | `docs/derivations/K03-solver-spec.md` §5.3 (amended 2026-09-25); T05b spec B33 |
| Evidence | *measured* (`docs/reviews/T05b-review.md` S2, P5, P6): NP-2 and NP-G from a liquid-form start restart correctly into `TWO_PHASE` and end `BOUND_BLOCKED` at iteration 0 on `S2.n.A`, the vapour flow of a component absent from the feed, whose exact Newton step is zero; T05's P4 (SC-2 under v1) `BOUND_BLOCKED`, converging with `1e-6 mol/s` of the absent component added |
| Affected packages | K03 (Newton core), T02–T05b (every region solve), T06 |

**Decision.** When `α_max = 0`, the free components exactly on a finite lower bound at both the attempt's opening and the current iterate that form a released set — the rows with `F == 0.0` exactly and every nonzero entry in the set number exactly as many as the set's columns, so that, `J` being nonsingular, the exact step on the set is zero — get `d := 0` exactly, and `α_max` is recomputed; `BOUND_BLOCKED` is declared only if a component outside the largest released set still blocks, with `blocked_by` as before. No record: the step taken is the exact Newton step.

**Rejected alternatives, and why.** Registering a start-dependence limitation for near-pure restarts (the review's recommendation; against Frank's directive, and the defect is arithmetic, not physics). Discarding the step on every exactly-zero flow (it would freeze a component that must leave its bound, and hide T02 §6.3.3's disappearance, which is a `BOUND_BLOCKED` on a component that reached zero during the attempt). Pinning absent components as a form (changes every attempt's rows and records where a component is absent, SC-1…SC-4 and NP-* included). A roundoff threshold on the outward direction (a tolerance on the exact path).

**Watch for.** The release widened to components that reached their bound during the attempt (breaks the disappearance mechanism); the "exactly `F == 0`" and "exactly as many rows as columns" conditions relaxed to tolerances; the release extended to every step, not only where `α_max = 0`, without its own inertness proof.

> **Amended 2026-09-25 (T05b Q-S13; re-review S-W1, N-W7):** "the attempt's opening" is the attempt's — a caller that runs one attempt through several Newton calls (T04's homotopy corrector) passes it (`opening=`); the release is the Newton core's only, and T04's PTC core (pseudo-steps and polish) keeps K03 §5.3's first paragraph (K03 §5.3 and T04 §7.5 notes; T05b B35). *Rejected:* the call's start as the opening (a phase vanished at an earlier λ-level would be released); the release in PTC by reference (its proof does not transfer to `J + D/Δt` as it stands). *Watch for:* a new multi-call caller of `solve_newton` that does not pass `opening=`.

---

## R-065 — Every v2 opening agrees with exact dormancy: one fixed point over lifted splits' `ZERO_FLOW` membership, items and outlet resets

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T05b ruling round, Q-S9; the review's must-fix M1 and note N1) |
| Normative text | T05b spec §7.4, §7.8 (ii) (as amended), §6.4; B31 |
| Evidence | *measured* (`docs/reviews/T05b-review.md` M1, P1, P4): two PH flashes in series restarted from another duty's traversal opened `U-PHF2` in `ZERO_FLOW` with its feed flowing, and the reverse in `VAPOR` with its feed dormant; DZ-12 with a second flash on the exchanger's hot outlet did the same through the outlet reset; each raised an untyped `RuntimeError` (the W7 log had called it unreachable); a heater-style consumer was fine (its feed is its own outlet, which no opening writes) |
| Affected packages | T03/ADR 0005 (openings under v2), T05b, T06 (two-stage flashes and mixer → flash topologies) |

**Decision.** At every opening under v2 — attempt 0 after the start projections and rules, every restart after the candidate's regimes, pins and kernel answers — passes in declaration order re-derive every lifted split's `ZERO_FLOW` membership from its feed's exact dormancy (entering pins the lifted flows at `+0.0`; leaving takes the TP flash of the feed, `fallback(<U>, tp)` for a PH-type split) and every item from its trigger's, resetting an outlet whose item differs from its reference whenever its flows differ from its mole balance, until a pass changes nothing; the signature is read off the final state. If pass `m + 1` still changes something, the region closes `ACTIVE_SET_CYCLING` with `opening_not_settled(<id>)`. No new record grammar.

**Rejected alternatives, and why.** Re-deriving only the split the candidate names (the gap M1 measured). Items only, or each outlet reset at most once (a later write in the same opening leaves a stale reset: F7's singular first Jacobian, review N1). Letting the `RuntimeError` guard stand as the outcome (an untyped exception on a user-reachable path). Processing in a computed topological order (recycles have none; declaration-order passes settle an acyclic propagation within `m` passes and are deterministic).

**Watch for.** The fixed point dropped at attempt 0 ("the traversal start is consistent" — a supplied start is not); a threshold on dormancy; the non-settling case turned into an exception; a downstream regime change given a new cause grammar instead of the signature.

> **Amended 2026-09-25 (T05b Q-S9 addendum, Q-S12, Q-S14; `docs/briefs/T05b-rulings.md` §4):** (1) B31 (b)'s verdict is `UNVERIFIED` (`RANK_DEFICIENT`, one rank per flash): a `Q = 0`, `ΔP = 0` flash fed a saturated product sits exactly on its dew point, where the lifted equilibrium rows are singular (spec §17, twin-registered); B31 (i) asserts `VERIFIED` for the same restarts at `ΔP = 10 kPa`. *Rejected:* widening the rank tolerance or screening a reduced form to get `VERIFIED` there without a derivation (spec §18 Q9 holds that for Frank). (2) At a phase-rejected candidate every changed unit's kernel is asked at the unmodified candidate before any answer is written (spec §7.8 (ii) 5, B34); *rejected:* applying answers in turn and skipping the check for a unit whose feed was rewritten (order dependence; a regime the screen never reported opens the attempt). (3) The leaving TP flash takes the feed's `n` and `T` and the split's outlet `P`, its `T` written to every temperature column of the split's streams (spec §7.4, B36); *rejected:* the split's own `T` column (an earlier feed's label — history deciding an opening). *Watch for:* B31 (b)'s `VERIFIED` restored by a relaxed screen; the candidate's answers written in turn "for simplicity"; the leaving flash moved back to the split's own `T`.

> **Amended 2026-09-25 (T05b Q-S15; `docs/briefs/T05b-rulings.md` §4):** (1) The leaving flash's "feed" is spec §7.1's. For a heater-style split that is its own outlet, so its flash is unchanged. *Rejected:* the label source's `T`. It gives the same value wherever it matters, since the linear label row holds, and it moves bits. (2) The screen's leaving report reads the same inputs as the opening's leaving answer: the feed's `n` and `T`, and the split's `P`. N4's guard no longer exempts a leaving answer; the only sanctioned difference left is a refused PH closure, as in Q-S10. *Rejected:* keeping the split's own `T` at the screen. Once B36 moved the answer's input, that would let the cause string and the opened signature disagree without the guard seeing it. (3) B34 (a)'s counts are re-registered after B36, and a certificate tally is added. **Watch for:** the screen and the opening drifting apart again through a new input to one of them. The narrowed guard is what catches that.

---

## R-066 — The T06 corpus: 49 cases, one per mechanism; plan IDs keep their meaning; NET-07 is C3

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T06 specification) |
| Normative text | `docs/derivations/T06-corpus-spec.md` §3–§5; ADR 0014 D1; `ref.corpus` in `benchmarks/t06/reference_values.yaml` |
| Evidence | the pilot of spec §2 (*measured*, registered initializers only); C3's tear-map eigenvalues 0.526 ± 0.020i, 0.384 from `ref(t05)` |
| Affected packages | T06, T08 (the release counts) |

**Decision.** 49 counted cases (the plan's 40 IDs plus NET-08…NET-11, THM-07…THM-10, STA-05), each with one fixture, a preregistered outcome kind and denominator membership (28 in it, 22 ensemble-eligible). A fixture an earlier spec filed under a plan ID of another mechanism keeps its name and supports the right corpus case. New flowsheets are family `SYN-001-T06`. NET-07 is `SYN-001-UL-C3`.

**Rejected alternatives, and why.** Counting SYN-001's r-variants or A02's targets separately (plan §3.2, §4.3; padding). Renaming K03's seeds to the plan's IDs (churn in registered tests for no information). A new NET-07 case (C3 meets both clauses of plan §6.1 and has the only measured tear-map Jacobian; its `r`-invariant `T_f` is covered by NET-02 and its scalar reduction by NET-03/09/10/11). Counting SC-4 and NP-3 (their mechanisms are SC-1…SC-3's and NP-1's).

**Watch for.** A case added because it passes; two cases whose fixtures differ only by a parameter along an invariance (the r-variant trap); a plan ID reused for a different mechanism.


> **Amended 2026-09-26 (T06 Amendment 1; ADR 0014 D1):** STA-03 and STA-04 are `verified_at_reference` (R-076, R-077), so the success denominator is 30, not 28. Eligibility clause (e) now excludes a case whose compiled problem and start restate another case's — NUM-04 → NET-01, STA-03 → NET-01, STA-04 → NET-08 (generator-checked); the eligible set and `N = 440` do not move. *Rejected:* making STA-03/STA-04 eligible (they would re-sample NET-01's and NET-08's basins under other names). *Watch for:* a restatement made eligible to raise the rate.
---

## R-067 — The nominal sampling law: per-path selected coordinates, splits re-derived from perturbed streams, `sha256-counter-v1`, starts published before any solve

> **Amended 2026-09-26 (T06 Amendment 2, spec §6.3 (A2)):** the draw's binary64 arithmetic is `δ = (2u − 1)/5` in one division and `x_init + S·δ` in two roundings; the literal `0.2 * w` differs at 35 % of keys and is not the registered draw; KATs carry `u_hex`, `delta_hex`.
>
> **Amended 2026-09-26 (T06 Amendment 3, spec §6.2 (A3), §6.3, §6.5 (A3), A85):** "the initializer's own rule" means, at a perturbed start, **the provider's TP flash of the perturbed outlet stream for every heater-style split, PH-type included** — not ADR 0012 D5's closure seed, which is the traversal start's rule and exists only because a temperature-degenerate outlet's `(n, T, P)` does not fix its split; every published perturbed outlet is ≥ 0.339 K outside its band. *Rejected:* the closure's split carried to the perturbed start (a function of the inlet, not of the perturbed outlet: it breaks the split rows and puts pure B two-phase off `T_sat`); the closure re-run (overwrites the perturbed coordinates); the closure seed on saturation/band routes only (the start would depend on how the unperturbed traversal closed). Consequence, accepted: THM-08/THM-09 open their valve single-phase in every start. The key's case field is the registered **fixture** id (the KATs' spelling). A provider identity change that moves no start re-emits the starts file by its generator, with exactly the identity path differing (A3.11: `641de215…` → `3a7bd49c…` after ADR 0017) — never a hand edit, never a changed start. *Watch for:* "fixing" step 5 to D5's closure seed because D5 says so; a regenerated file whose diff is more than the identity field.

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T06 specification) |
| Normative text | T06 spec §6; ADR 0014 D2 |
| Evidence | KATs in `ref.closed_form.draw_known_answers`; THM-04's `min_i K_i(420 K, P_r) = 1.65` (generator-checked) |
| Affected packages | T06; T08 (the release ensemble) |

**Decision.** Tear path: perturb the three tear flows; A02: perturb the freed guess; revision path: perturb every unpinned stream coordinate and unit scalar by `0.2(2u − 1)` of its registered scale and recompute every lifted split from the perturbed stream by the initializer's own rule. Absent components are held at `+0.0`; dormant streams are perturbed one-sidedly by the domain. `u` is SHA-256 of a key in counter mode. Box rejection per coordinate and start-level rejection, each capped at 64; an ungenerable start is a counted failure. Starts are generated once on the reference machine class, committed, and scored as committed everywhere. THM-04 is ineligible (its tear start space is `{0}`).

**Rejected alternatives, and why.** Perturbing only torn-stream guesses (degenerate for acyclic cases). Perturbing split coordinates independently (that is the `trivial-split` stress profile). A sequential PRNG (order- and version-dependent). Regenerating starts per platform (last-bit differences in the initializer make them different starts). Clipping at bounds (the blueprint forbids silent clipping).

**Watch for.** A case's selected coordinates changed after an ensemble solve was seen; the caps raised to rescue a case; starts regenerated for scoring.

---

## R-068 — The ensemble gate is the point estimate on both platforms; the Clopper–Pearson bound is reported; 60 s per start

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T06 specification); Q7 (a bound-based gate) left to Frank with this default |
| Normative text | T06 spec §7; ADR 0014 D3 |
| Evidence | `ref.closed_form.gate`: `N = 440`, `S_min = 418`; the bound at 418 is 0.929; a bound-based gate would need `S ≥ 426` |
| Affected packages | T06, T08 (V20) |

**Decision.** Success = `CONVERGED` by any recorded path, `VERIFIED` under the default policy, within T02 §6.4's allowances of the registered root, within 60 s. The gate is `S ≥ 418` of 440 on `ref-x86-64` and on CI aarch64, with no `F-CRASH` and no unexplained `F-OTHER-ROOT`. The one-sided 95 % Clopper–Pearson bound is reported as start-sampling uncertainty for the fixed cases; nothing is claimed about other designs.

**Rejected alternatives, and why.** Gating on the bound (stricter than blueprint §13.4 registers). Treating 440 starts as independent designs (plan §6.2). Dropping `F-GEN` or `F-TIME` from the denominator.

**Watch for.** The allowance, the ceiling, the success definition or the case list changed after scoring; a `VERIFIED` far from the root counted as a success.


> **Amended 2026-09-26 (T06 Amendment 1; Frank):** Q7 answered — the point estimate gates, as registered. The revision path runs `T06-revision-v1` (`T05b-v2` with only `eo_recovery = homotopy_or_sequential_restart`, ADR 0015 / R-075), and a start that converges only through edge 3's restart **counts** (Frank), reported per case as `s_c^first + s_c^rescued` with the statement that a restart discards the start; the CP bound is also reported on `S^first`, never gated. *Rejected:* excluding rescued starts from `S` (Frank's call: recorded fallbacks count). *Watch for:* the rescued count dropped from the report; `S^first` given a threshold after scoring.
---

## R-069 — `onenormest` runs under a fixed seed, saved and restored

> **Amended 2026-09-26 (T06 Amendment 2, spec §8.1 (A2)):** the seed makes the estimate deterministic, not exact (A42's constructed fixture: 4.0300 vs the exact 5.9948); the exact-norm status check now runs at every corpus certificate too. The seed is not changed (choosing one exact at a known fixture would be tuning).

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T06 specification; T05b's hand-on) |
| Normative text | T06 spec §8.1; ADR 0014 D4 |
| Evidence | *measured*: scipy 1.15.3's `onenormest` draws from `np.random.randint` with no generator argument; T05b: C2's `b` 3.0e-15…3.9e-15, C3's 3.0e-9…3.4e-9 over 20 global seeds |
| Affected packages | K04 (`verify/regularity.py`), T06, every certificate's recorded `rcond₁` and `b` (R1 fields) |

**Decision.** Save numpy's legacy global state, seed `20260925`, call, restore — at both calls. Recipe, method string, thresholds, statuses and the check policy unchanged.

**Rejected alternatives, and why.** The exact `‖Ĵ⁻¹‖₁` in the certificate (a plan §6.3 departure that moves every recorded value; the ensemble harness computes it beside the estimate instead). `t = 1` (weaker). Leaving it random (same-machine replay of `b` not exact).

**Watch for.** The seed recorded in a certificate field (moves R0); a second estimator call added without the guard.

---

## R-070 — The verifier's alias shift moves down where up leaves the domain; a converged solve never makes the verifier raise

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T06 specification) |
| Normative text | T06 spec §8.2; ADR 0014 D5 |
| Evidence | *measured*: NET-11 converges and `verify_revision` raises `VerifierError` (alias-certificate residual `invalid_trial_state`); `S4.P = 1.8e5 Pa` shifted to 204 925 Pa by `997·(j + 1)`; with the direction rule, `VERIFIED` at the twin |
| Affected packages | K04 (`verify/certificate.py`), T06; every revision-built flowsheet with a high pressure late in its variable list |

**Decision.** Keep K03 §7.2's distinct shifts; move a column down when the provider's domain refuses the upward value; `unsupported` (typed, `UNVERIFIED`) when neither direction is admissible or two distinct pressures coincide. Every evaluation failure at a verifier-constructed state is its check's `unsupported`; no `VerifierError` escapes for a `CONVERGED` solve with a full state.

**Rejected alternatives, and why.** Re-basing the shift on the rank among pressure columns (moves every registered certificate). Leaving the exception (rule 5: an untyped failure on a correct state).

**Watch for.** A shift rule that changes a registered certificate's shifted state; a new verifier-constructed state that can raise.

---

## R-071 — Validation checks units and component references (`DIM-01`, `COMP-03`); the legacy binding refuses the same

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T06 specification) |
| Normative text | T06 spec §8.5; ADR 0014 D6 |
| Evidence | *measured*: `SPEC-feed-n-A` `{0.1, kg/s}` and `SPEC-feed-T` `{26.85, degC}` validate `READY_FOR_SIMULATION` and bind as `FeedSource(flows=(0.1, 1.0, 1.0), temperature=26.85)`; `component: D` validates `DRAFT` for "feed flow of B", `COMP-01` passing |
| Affected packages | K06 (`application/validation.py`, `application/binding.py`), T06, T07 |

**Decision.** `DIM-01` on the `dimensions` stage (internal-SI unit per kind; the kind the target path requires) and `COMP-03` on `component_reference_compatibility`; either fails `INVALID` naming the ids. The legacy binding refuses the same with kind `conflict`.

**Rejected alternatives, and why.** Converting units at binding (the stored revision would not be what was solved; a T07 boundary question). Relying on the schema test (it runs on registered files, not on what a user validates).

**Watch for.** A conversion path added inside the binding; `DIM-01` weakened to accept `display_unit` as the unit.


> **Amended 2026-09-26 (T06 Amendment 1):** the rejection of conversion is **reversed by R-077** (Frank's Q4, and ADR 0001 D1.4, which already prescribed conversion at validation time). `DIM-01` now fails only a unit or kind outside `unit-conversion-v1`; the legacy binding's refusal code `unit_not_internal_si` is withdrawn in favour of the revision binding's `specification_unit_unsupported` / `specification_kind_unsupported`. `COMP-03` and `component_unknown` stand. This entry's "Watch for: a conversion path added inside the binding" is superseded by R-077's.
---

## R-072 — Reference comparisons: VLE at `P_r` only, DWSIM's latent and formation data mapped by derivation, tight solver settings as inputs, `a_k + 1e-6 |v|`, positive controls

> **Amended 2026-09-26 by R-083:** IDAES's SmoothVLE smoothing is a known equation difference; `eps_1 = eps_2 = 1e-8 K` is a registered tool input with a tool-only self-check (rule 2b).

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T06 specification); `docs/reference-environments.md` §7's open questions decided |
| Normative text | T06 spec §9; ADR 0014 D7 |
| Evidence | generator-checked: with `ΔH_vap,i = L_i + P_r v_i` DWSIM's latent equals SYN-001's at every pressure (1e-30); PC-1 205×, PC-2 4 581× the tolerance; REF-05's latent effect 1.02× (disclosed) |
| Affected packages | T06 (D19), T08, S03/R01 (later comparisons follow the same rules) |

**Decision.** All eight fixtures against both tools; phase equilibrium only at `P_r`; the DWSIM mappings; IDAES with MUMPS; tools' own balance self-check before any comparison; mechanical classification then the `verdict` agent; PC-1 and PC-2 must `DISAGREE`.

**Rejected alternatives, and why.** Comparing at `P ≠ P_r` with a declared Poynting allowance (a known difference inside a tolerance is tuning). Default tool settings (DWSIM's recycle default leaves 0.0306 mol/s of balance error). HSL MA27 (not open source).

**Watch for.** A tolerance, mapping or setting changed after a result was seen; a `DISAGREE` turned into `AGREE` by explanation; a positive control dropped because it agrees.


> **Amended 2026-09-26 (T06 Amendment 1; R-079):** IDAES `constr_viol_tol` is `1e-9` (was `1e-10`, below the Pa-row floor M6 measured); IDAES converged iff "Optimal Solution Found"; PC-1 is DWSIM-only and PC-2 runs in both tools. Registered in R-079.
---

## R-073 — Identity key `t06` holds R0 records and the ensemble's definition, never per-start outcomes; replay is harness-level

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T06 specification) |
| Normative text | T06 spec §10; ADR 0014 D8 |
| Evidence | K05's `run_session` raises `syn001_only` for revision-built flowsheets (*read*) |
| Affected packages | K05 (identity document), T06, T07/T08 (spec Q6) |

**Decision.** `t06` carries the new cases' registered-initializer R0 records, the diagnosis fixtures' statuses and codes, and the ensemble's definition; `t02`…`t05b` and `4ce030ca…` do not move. Ensemble replay re-runs a start from the committed starts file and compares with `run.compare.differences`.

**Rejected alternatives, and why.** Per-start event sequences in R0 (adaptive decisions are outside the cross-platform promise). Generalizing K05's bundles inside T06 (a scope decision for T07/T08).

**Watch for.** A per-start float or digest in `t06`; an existing key moved by a T06 chunk.

---

## R-074 — NET-02 is registered with its physical expectation although the software fails it today

| | |
| --- | --- |
| Date | 2026-09-25 |
| Decided by | design lane (`specifier`, T06 specification) |
| Normative text | T06 spec §0 F4, §3.2, §4.3, §16 Q1 |
| Evidence | *measured*: `BOUND_BLOCKED` at iteration 1 under both contracts (`S6.n.A` truncated to 0); `eo_recovery: unsupported (no_continuation_parameter)`; PTC `PTC_MAPPING_INVALID(U-PHF:PHF-mole:A, missing)` |
| Affected packages | T06 (the gate), the recovery design of spec Q1 |

**Decision.** NET-02 (`r = 0.95`, designed before it was run) stays in the corpus and the ensemble with expectation `VERIFIED` at the twin root; its failure is retained and counted; the remedy is a design question (Q1), not a case change.

**Rejected alternatives, and why.** Dropping NET-02, or lowering its recycle ratio until it converges — choosing cases by the solver's outcome is selection toward the gate. Moving it outside the envelope without an explicit support-matrix change (plan §6.2).

**Watch for.** NET-02's parameters edited "to make it a fair test"; NET-02 quietly marked ineligible.


> **Closed 2026-09-26 by R-075** (ADR 0015, `docs/design/T06-F4-recovery.md`; Frank approved): NET-02 is registered `VERIFIED` under `T06-revision-v1` through edge 3's sequential restart; under `T05b-v2` and `T05-W13` it stays registered `BOUND_BLOCKED` as the edge-off control. NET-02's parameters did not change.
---

## R-076 — A permuted component order is mapped onto the provider's; the label and the certificate are the unpermuted twin's

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | Frank Peters (Q3: "support it"); the mapping and its identity rule by the design lane (`specifier`, T06 Amendment 1) |
| Normative text | T06 spec §8.6; ADR 0014 D9 |
| Evidence | *measured*: STA-04 with its order reset to `[A, B, C]` gives C2's label, `variable_ids`, trace (12 events) and certificate SHA-256; the legacy binding with `[C, A, B]` binds and `solve_tear` raises `InnerSolveInconsistentError` (F7) |
| Affected packages | T06 (STA-04), K06 (`application/binding.py`), T05 (`models/revision_flowsheet.py`, R2), T07 (display order) |

**Decision.** A `component_set.components` that is a permutation of the provider's `describe().components` is accepted and mapped: the binding's components are the provider's order, the declared list is kept in `input_mapping.declared_components`, and every component-keyed input is already keyed by id. One function, called by the revision layer's `_read` and by the legacy binding. `configuration_sha256`, the label, `constants_sha256` and the certificate are the unpermuted twin's; `revision_sha256` differs. Any other list is refused `components_unsupported`. `thermo/syn001.py` does not change.

**Rejected alternatives, and why.** Permuting at the provider boundary (every property call, derivative and cache key touched; a mapping inside the residual path; agreement only within a tolerance). The declared order in `configuration_sha256` (two labels for one equation set, contrary to R-047). The mapping in the certificate (two certificates of one declaration and state would differ by how a document was read). Refusing, as before (Frank chose support).

**Watch for.** A component-keyed input read by position; the declared order leaking into a label, a column order or a cache key; the legacy binding passing the declared list to `Syn001Flowsheet` again.

---

## R-077 — Specification values in ADR 0001's input units are converted by `unit-conversion-v1`; every other unit is refused

> **Amended 2026-09-26 by R-081 (ADR 0016):** the unit set is widened to ADR 0016's table and instance parameters are converted (Frank's Q11); the arithmetic becomes `RN(a·D(v) + b)` on the decimal `v` denotes — v1's binary reading is reversed because it is not unit-invariant (measured: 75.1 % ≠ 0.751, −40 °C ≠ 233.15 K). STA-03's and A56's values are unchanged; the readers, records (now with `source`, `input_id`) and codes stand; a component reference is judged before a unit.

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | Frank Peters (Q4: "convert them"); the rule set, readers and records by the design lane (`specifier`, T06 Amendment 1). **Reverses** R-071's rejection of conversion |
| Normative text | T06 spec §8.5; ADR 0014 D6 (amended); ADR 0001 D1.3–D1.4 |
| Evidence | generator-checked: `fl(26.85 + 273.15) = 300.0`, `fl(0.1 / 0.1) = 1.0`, `fl(86.85 + 273.15) = 360.0`, `fl(84.85 + 273.15) = 358.0`; known answers where the binary64 sum or quotient differs from the decimal sum or the reciprocal product. *Measured*: STA-03 converted at document level gives SYN-001-nominal's trace and certificate byte for byte; `verify_bound` reads `float(entry["value"])` raw today |
| Affected packages | K06 (`application/binding.py`, `application/validation.py`), T05 (`models/revision_flowsheet.py`), K04 (`verify/certificate.py::_revision_values`), P01 (`units`), T06, T07 |

**Decision.** `unit-conversion-v1` is exactly ADR 0001 D1.3–D1.4: `degC` → K on a temperature target (one binary64 addition of 273.15) and `kg/s` → mol/s on a one-component flow target (one binary64 division by `M_c`, from an id-keyed table of SYN-001's molecular weights asserted equal to `components.yaml`). The declared kind must be the target's, or `mass_flow` for the mass basis; anything else is refused with the existing codes. One function in `process_runtime.units`, through which every reader of a specification value goes: the legacy binding, the revision layer (and so `verify_revision`), `verify_bound`, and `DIM-01`. Instance parameters are not converted. Records: the bindings' `input_mapping` and `DIM-01`'s `PASS` message; not the certificate. What changed since R-071: Frank's answer, and the finding that ADR 0001 D1.4 (frozen) already required conversion at validation time.

**Rejected alternatives, and why.** Refusing every non-SI unit (R-071's choice; contradicts ADR 0001 D1.4). A decimal conversion (a second arithmetic for a ≤ 1-ulp difference). Converting instance parameters (P01's `check_quantity`, ADR 0001 D1.1). `kPa`, `bar`, `kW`, `%` (widen a frozen rule; spec Q11 for Frank). Conversions in the certificate (its subject is the declaration). `DRAFT` for an unknown unit (it violates a frozen rule, so `INVALID`).

**Watch for.** A reader of a specification value that bypasses the function (the verifier's `_revision_values` was one); `v * (1/M)` or a decimal sum in place of the registered operation; a unit added to the table without an ADR; `check_quantity` loosened to accept display units.

---

## R-078 — The legacy tear path types a failed registered initializer as `INITIALIZATION_FAILED`

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | design lane (`specifier`, T06 Amendment 1; Phase M question M1) |
| Normative text | T06 spec §8.7; ADR 0014 D10 |
| Evidence | *measured*: SYN-001-nominal with the feed at 450.0 K, 279.0 K (`out_of_domain: U-MIX: …`) and 400.0 K (`unsupported: U-MIX: inlet 0 is not admissible as a liquid …`) validates `READY` and `solve_tear` raises `SpecificationError` |
| Affected packages | K03 (`orchestrator/tear.py`), K02 (`models/syn001/flowsheet.py`), T06 |

**Decision.** `initial_recycle` raises `InitializerFailedError(SpecificationError)`; `solve_tear` catches exactly that and returns `INITIALIZATION_FAILED`, message `initializer_failed(SYN-001-tear-init-v2): <status>: <first line>`, trace one `solve_closed` event.

**Rejected alternatives, and why.** Letting it raise (rule 5; the revision path already types the same condition). A domain check at validation (blueprint §4.3; T07's).

**Watch for.** A bare `except SpecificationError` in `solve_tear` swallowing other errors; the typed branch recording a `plan_built` event before the plan exists.

---

## R-079 — Reference-tool qualification: IDAES `constr_viol_tol = 1e-9` uniformly; "Optimal Solution Found" only; PC-1 DWSIM-only, PC-2 in both tools

> **Amended 2026-09-26 by R-083:** the IDAES settings gain `smooth_vle` `eps_1 = eps_2 = 1e-8 K` on every state block; every IDAES record is re-run blind at it.

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | design lane (`specifier`, T06 Amendment 1; Phase M question M6) |
| Normative text | T06 spec §9.2–§9.5; ADR 0014 D7 (amended); `ref.closed_form.reference_tool_settings` |
| Evidence | *measured* (M6, blind, `docs/t06-reference-qualification.md`): at `1e-10`, REF-04/05 "Search Direction is becoming Too Small" at 1.02e-10 and REF-06 "Solved To Acceptable Level" at 1.16e-10, on Pa rows at 1e5–1.8e5 Pa; rule 2 ≤ 1.5e-13 mol/s at both settings. Generator-checked: `1e-9` is ≥ 30 ulps of a 2e5 Pa row and ≥ 100× below every allowance |
| Affected packages | T06 (W8), S03/R01 (later comparisons) |

**Decision.** IDAES: `constr_viol_tol = 1e-9` for every final solve, `tol = 1e-10`, MUMPS in every solve including initializers (whose other options are IDAES defaults); converged iff "Optimal Solution Found". PC-1 is DWSIM's only; (PC-1, IDAES) is `not_applicable`. PC-2 runs in both tools with feed (1, 1, 1) mol/s, 300 K, liquid, 1.5e5 Pa, and our fixture `SYN-001-T06-PC2`. REF-08's tool-side recycle guess is (0.2, 0.6, 0.8) mol/s, 360 K, `P_r`. DWSIM's REF-07 extent is derived from its conversion of A (B and C carry rule 2; disclosed). The six IDAES records run at `1e-10` (REF-01, -02, -03, -07, -08, PC-2) are re-run blind.

**Rejected alternatives, and why.** `1e-10` (below its floor). `1e-9` only for REF-04/05/06 (per-fixture settings read as tuning). Counting "Solved To Acceptable Level" (relaxes `tol` silently). An IDAES analogue of PC-1 (a new control needing its own derivation).

**Watch for.** A setting changed after a comparison was seen; a per-fixture setting; a positive control dropped because it agrees.

---

## R-080 — The shared-provider qualification is `independence_qualifications`, not a `limitations` entry

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | design lane (`specifier`, T06 Amendment 1; Phase M question M4) |
| Normative text | T06 spec §8.4, A17, A33; ADR 0014 D11 |
| Evidence | *measured* on SYN-001-nominal (`verify`), C1, C2, C3, NET-03 and REF-05 (`verify_revision`): `independence_qualifications`' check ids equal the `energy_balance.*`, `phase_admissibility.*` and `independent_split.*` checks; four statements; `limitations` empty; ADV-06 M's limitations exactly `[derivative_limitation]` (M4) |
| Affected packages | K04 (text erratum recommended for §8.2), T06 (W7, A17, A33) |

**Decision.** [A09]/D14's shared-provider qualification is K04's `independence_qualifications` (plus the fourth statement), as implemented and reviewed with K04. It is already in place; no T06 chunk implements it; W7 does not wait for it.

**Rejected alternatives, and why.** Adding `shared_provider` entries to `limitations`, as K04 §8.2's text says: limitation kinds are in K05's R0 certificate projection, so every registered certificate's R0 record would move for no new information.

**Watch for.** Someone "fixing" the certificate to match K04 §8.2's text; a new fresh-flash or energy check without its qualification entry.

**Amended 2026-09-26 (T06 Amendment 4, ADR 0014 D11).** The qualified ids are the prefixed checks whose result is `pass` or `fail`. A `not_applicable` check (`ZERO_FLOW`, `temperature_degenerate`, `fresh_flash_unresolved`) consulted no provider and carries no entry; run 1's 137 A33 failures were all such entries. *Watch for:* qualifying `not_applicable` checks to satisfy the old wording.

---

## R-075 — A revision-built region that fails its EO globalization is re-initialized once, from the traversal continued to 8 passes (edge 3's second action)

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | design lane (`architect`, T06 F4); the schema widenings approved by Frank on 2026-09-26 (`docs/T06_DECISIONS.md`) |
| Normative text | `docs/design/T06-F4-recovery.md` §5; ADR 0015 D1–D4 (Accepted 2026-09-27) |
| Evidence | design note §2 (*measured* probes) |
| Affected packages | T06, T02, T04, T05; T07 through the design note's Q2 |

**Decision.** ADR 0015 D1–D4: `globalization.eo_recovery = homotopy_or_sequential_restart` makes edge 3's action the specification continuation when the region has a continuation parameter, else one region solve from `traversal-G0-pass8-v1` on a revision-built flowsheet (preconditions P3–P5), else `unsupported(<reason>)`; the trigger set and the count of one are unchanged. NET-02 is `VERIFIED` under `T06-revision-v1`, and R-074 is closed.

**Rejected alternatives, and why.** Those listed in ADR 0015: split-fraction or tear-connection continuation, PTC mappings for T05 units, a projected or bound-aware Newton step, a longer registered initializer, seeding from the failed opening's torn values, an adaptive pass count, a restart ladder, folding the restart into `homotopy`.

**Watch for.** `RESTART_PASSES` changed without a new initializer id; the restart made the default of `GlobalizationPolicy` (it would move registered policy documents); the restart seeded from a failed state; the pass count tuned on the gate's own starts.

---

## R-081 — Input units by recorded conversion, `unit-conversion-v2`: the exact image of the decimal as written, rounded once

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | Frank Peters (spec Q11: "Yes, in T06" — specifications and instance parameters, other common units, unknown ones refused); the table, arithmetic, readers and records by the design lane (`specifier`, T06 Amendment 2). **Reverses** R-077's arithmetic and unit set; R-077's readers, records and codes stand |
| Normative text | ADR 0016 (Accepted 2026-09-27); T06 spec §8.5 (A2); `ref.closed_form.unit_conversion_v2` |
| Evidence | generator-checked (`units_v2.*`, 13 claims): 23 of 23 metamorphic pairs bind to their SI twins bit for bit; 5 of 5 groups of spellings of one quantity bind to one double; the binary reading breaks C1's `75.1 %` (0.7509999999999999 ≠ 0.751) and v1 binds −40 °C to 233.14999999999998; every row's known answer is nearest to its exact value and refuses the row's naive binary64 chain |
| Affected packages | P01 (`units`), K06, T05 (`read_parameter`, T05's refusal test re-pointed), K04 (`_revision_values`), T06, T07 |

**Decision.** `SI = RN(a·D(v) + b)` — `D(v)` the shortest decimal rounding to `v`, `a`, `b` exact from the unit's definition (mass rows over `D(M_c)`), one round-to-nearest-even — for the table of ADR 0016 D3 (°C, °F; kPa, MPa, bar, atm, psi; kW, MW; kmol/s, mmol/s, mol/h, kmol/h; kg/s, g/s, kg/h; `%` on fractions). Specifications and instance parameters (whose SI twin `check_quantity` judges); internal storage stays SI (ADR 0001 D1.1). A component reference is judged before a unit. Records `{source, input_id, …}` ordered by the canonical revision; never in the certificate.

**Rejected alternatives, and why.** v1's binary reading widened (two spellings of one quantity bind to different doubles; metamorphic identity by coincidence); keeping v1 beside v2; converting only at a T07 API; rewriting the revision to its SI twin at binding; aliases and gauge pressures (Q14, Q15); `%` on every dimensionless target (a stoichiometric coefficient in percent is not a quantity).

**Watch for.** A binary64 chain (`v * 1e-3`, `v / 3.6`, `(v − 32) * 5 / 9 + 273.15`) replacing the exact map; `Fraction(v)` instead of `Fraction(repr(v))`; a unit alias added without a row and its known answers; a reader of an input value bypassing the function; a unit error reported for a specification whose real defect is its component.

---

## R-082 — SYN-001's TP flash returns the single phase its Rachford–Rice bracket names when the two binary64 tests disagree; SYN-001's identity is re-baselined by substitution

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | design lane (`specifier`, T06 Amendment 2); **the identity move awaits Frank's approval** (ADR 0017's banner) |
| Normative text | ADR 0017 (Accepted 2026-09-27); T06 spec §0 F6, A75–A79; `ref.closed_form.f6_states` |
| Evidence | *measured* (2026-09-26): 524 of 57 454 saturated-product re-flashes returned `not_converged` at iteration 0, every one with both bracket values of one sign, 0 after the fix; no exhaustion in the domain; the full suite with the fix monkeypatched: 3 375 of 3 378, the three failures F6's own registrations; C3's restart then keeps 8 passes and converges (3.5e-4 of an allowance). Twin: the registered states are within 1.1e-14 K / 2.6e-14 K of saturation and the fixed answers within 1.2e-15 / 5.6e-16 of the exact `β` |
| Affected packages | K02 (`thermo/syn001.py`); every identity key and fixture carrying a SYN-001 label; T06 (F4's C3 registration) |

**Decision.** On `f(0)·f(1) > 0` (the values `_rachford_rice` already computes) the flash returns `LIQUID` (both negative) or `VAPOR` (both positive) instead of `not_converged`; nothing else changes, so every `ok` result anywhere is bit-identical. The implementation hash moves, and with it every SYN-001 label, `model_version`, `4ce030ca…` and `t02`…`t05b` — by substitution only, proved in two steps (old hash monkeypatched → everything byte-identical; new hash → only the substitution).

**Rejected alternatives, and why.** A unit-layer/verifier wrapper (a second implementation of the provider's classification in five call sites, with its own rounding; every other consumer keeps the defect); classifying by the bracket everywhere (moves `ok` results); a bracket-collapse termination (no state in the domain needs it); loosening the tolerance (not involved); a second provider (forks the fixture); leaving it (Frank's robustness steer).

**Watch for.** The branch widened into a reclassification of `ok` results; the bracket values recomputed instead of reused (a third rounding); the identity re-baseline done without the old-hash inertness step; a "must not move" clause quoting `4ce030ca…` after the re-baseline.

---

## R-083 — IDAES's SmoothVLE smoothing is a known equation difference, removed by a registered ε and checked by the tool's own output

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | design lane (`specifier`, T06 Amendment 2, from W8's comparison) |
| Normative text | T06 spec §9.3 (A2), §9.5 rule 2b, A83; `ref.closed_form.reference_tool_settings.IDAES.smooth_vle` |
| Evidence | *measured* from W8's committed IDAES records: `T_eq − T = 5.0015e-3 K = ε₁/2` at REF-08's recycle (a flash liquid at its bubble point), `9.77e-6 K` at REF-03's heater outlet, `2.9e-6 K` in REF-08's flash; REF-03 and REF-08 `DISAGREE` (1.36, 302) while DWSIM agrees on all eight (worst 4.0e-6 of the tolerance). Generator-checked: the default ε is ≥ 500 temperature allowances; the registered ε bounds the shift by `a_T/1000` |
| Affected packages | T06 (W8, the reference dossier), T08 (release evidence citing V16) |

**Decision.** `eps_1 = eps_2 = 1e-8 K` on every SmoothVLE state block of every IDAES fixture and control, uniformly; rule 2b computes the shift `|T_eq − min(max(T, T_bub), T_dew)|` from the tool's record alone and classifies `NOT_COMPARABLE(semantics: smooth_vle_shift(…))` above `a_T/100`; the default-ε records are retained with that classification; every IDAES record is re-run blind; a `DISAGREE` after the re-run goes to `verdict`.

**Rejected alternatives, and why.** A genuine `DISAGREE` (the mechanism is the configured equation, read from the tool's own output); `NOT_COMPARABLE` without a re-run (leaves V16's IDAES column short for a setting the tool exposes); `ε = 0` (non-smooth where REF-08's recycle sits); a per-fixture ε or an ε searched against agreement (tuning).

**Watch for.** ε changed after a failed re-run on the build lane's initiative; the default-ε records deleted from the dossier; the smoothing absorbed into a comparison tolerance; a new IDAES fixture built without the registered ε.

---

## R-084 — The regularity screen refuses a matrix whose identity is not the target's (VER-02, VER-03)

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | design lane (`specifier`, T06 Amendment 2, from W5's stop-and-report) |
| Normative text | T06 spec §8.4 (A2), A82; K04 spec §7.5, §7.6 REG-ε, A24 (the registration this implements) |
| Evidence | *measured* (W5): REG-ε — SQ-0's screen on `J + 1e-6` with a mismatched identity — gives `NO_RANK_LOSS_DETECTED`, `rcond₁ = 1.0`; `screen` stores `jacobian_identity` and compares nothing; K04's A24 test covers SQ-0 only while K04's manifest reports A24 passed |
| Affected packages | K04 (`verify/regularity.py`, `verify/certificate.py`), T06 |

**Decision.** `screen(…, target_identity=…)`: a missing or differing `jacobian_identity` on any of ADR 0008 D2.4's four fields makes the status `INCONCLUSIVE`, `inconclusive_reason = "identity_mismatch"`, the matrix's numbers still recorded. The certificate path passes the residual's identity at `x_final` (equal by construction), so no registered certificate moves.

**Rejected alternatives, and why.** Re-registering VER-02/VER-03 against the verifier's `state_mismatch` guard (it compares states, never sees a matrix, and raises); leaving the registered refusal without a code path.

**Watch for.** A factorization-reuse path added to `screen` without passing `target_identity`; the refusal decided after the matrix's own status (the refusal must decide); `target_identity` built from the Jacobian itself (a tautology).

---

## R-085 — A row-converged Newton iterate is refined once when its own first-order error exceeds the kind tolerance, under a policy value that selects it

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | design lane (`specifier`, T06 scoring-round ruling); **Frank approved the enum widening and `newton_refined` as T07's application default on 2026-09-26** (question tool, `bc45345`), and **kept the default on 2026-09-27 with M1 known** (`66861d5`) |
| Normative text | `docs/adr/0018-newton-terminal-refinement.md` D1–D7, with D4′ and D5′ (Amendment 1, 2026-09-27); T06 spec §6.6 (A4, A5), §7.1 (A4), A86–A90, A96 |
| Evidence | Run 1: THM-09's four `F-OTHER-ROOT`s at 1.005–3.447 allowances, inside the row's 5.02-allowance window (twin `closed_form.amendment_4`). *Measured* with a prototype (scratchpad, not committed): the chord estimate matches the exact correction within 1 % on THM-09; one refinement puts the four at 1.8e-6…2.2e-5 of the allowance; the census over the suite (1 246 converged exits) fires 22 times (8 at T05b B34's near-singular states, where 6 revert); the K05 identity document is byte-identical |
| Affected packages | K03 (`numerics/newton.py`, `linear.py`), T02/T05b (`region.py`), T06 (`T06-revision-v2`), T07 (default: Frank's) |

**Decision.** `globalization.eo_core = "newton_refined"`. At a `CONVERGED` region attempt exit at `k ≥ 1`, the chord correction `−S_x Ĵ_{k−1}⁻¹ F̂(x_k)` from the kept factorization is compared per column with the registered kind tolerance (ADR 0001 D6, the rule rows are accepted by; S3's allowance / 10). If any column exceeds it, one more Newton iteration runs. Its result is kept iff its step was accepted, its rows pass and its own chord is within tolerance; otherwise `x_k` is returned. The outcome never changes — **the attempt's** (amended 2026-09-27: the solve's can, see below). No new event kind or field. `T06-revision-v2` = v1 + this value; every registered policy keeps `newton`.

**Rejected alternatives, and why.** Widening S3 or §7.2 after run 1 (post-hoc relaxation); the rule under every existing policy (silent change of meaning; measured to move four registered tests); a fresh Jacobian at every exit (moves every R0 counter); re-forming or re-scaling the equilibrium row (moves every lifted split and the check policy; addresses only small `V·L`); tighter solver tolerances; adopting the verifier's projection; a pivot-ratio threshold instead of D4's outcome test.

**Watch for.** Registering it as the default of an existing policy; refining at `k = 0` (blueprint §7.3, NUM-04); letting a refinement turn `CONVERGED` into anything else; a refactorization for the chord (moves R0 counters); reading this as reversing ADR 0013's rejected polish (different purpose and scope, ADR 0018 D7); a certificate that begins to promise solution accuracy because the solver now delivers it (K04 F3 stands).

> **Amended 2026-09-27 (ADR 0018 Amendment 1; T06 spec Amendment 5; review M1):**
> - **Decision.** The refinement never changes an *attempt's* outcome, but it spends the solve's property budget like any iteration. A refusal in it, in the region's converged closure after it, or later in the solve is that step's `BUDGET_EXHAUSTED(property_calls)` (D4′ (i)). *Measured*, THM-09 start 1: `newton` converges in 365 calls; `newton_refined` ends `BUDGET_EXHAUSTED` at caps 365, 366, 375 and 385 and converges at 386 (spec A96).
> - **A second route, not observed.** A refined state that the region's closure converts opens a different later path (D4′ (ii)).
> - **The message.** It keeps the core's word, `abandoned: EVALUATION_ERROR`; the step carries the cause (D5′).
> - **Frank.** He kept `newton_refined` as T07's default with M1 known.
> - *Rejected:* reserving budget for the closure, or skipping the refinement near the budget (a new constant); leaving the refinement unmetered; a typed budget word carried through the CasADi callback for a non-R0 message.
> - *Watch for:* "never changes an outcome" quoted at the solve level again; a budget test at the Newton layer standing in for the plan's outcome (A88 (e) did); budget reserved "so the default is safe".

---

## R-086 — The two-phase admissibility closure is the saturation closure, in kelvin against `τ_T`

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | design lane (`specifier`, T06 Amendment 4, from the build lane's scoring diagnosis) |
| Normative text | T06 spec §8.8 (A4), A91, A92; ADR 0014 D13 |
| Evidence | *measured* over the suite: K03 §8.2's `Σ(y − x)` ≤ 2.2e-16 on all 660 evaluations (identically zero). The saturation closure is ≤ 9.8e-10 K at 577 judged states and ≤ 1.4e-12 K at sampled run-1 certificates; 3.34 K at NET-11 start 16's false `TWO_PHASE` label; ≥ 9.5e-4 K at T05b B34's four dew-point states. Substituted, it fails exactly four registered tests (B34 (a), B16, B26, one T04 fixture), and the K05 identity document is byte-identical. Twin anchors: 0 at THM-01's registered split, 3.3368 K at NET-11's liquid heater outlet |
| Affected packages | K04 (`verify/table.py`, `verify/checks.py`; K03 §8.2 / K04 §4.7 errata recommended), T05b (B34 (a), B16, B26 re-registered), T04 (one schema fixture regenerated), T06 |

**Decision.** For a flowing, non-degenerate two-phase lifted split, `phase_admissibility.<U>.<S>.closure` is `max(|T − T_b(l, P)|, |T − T_d(v, P)|)`. The two temperatures come from the verifier's own `band_ends`; a root off the domain is replaced by that domain end. The tolerance is the policy's `τ_T` and the reference 100 K. A saturation failure makes the check `unsupported(closure_<status>)`. It is judged where ADR 0013 D1 judges `phase_admissibility`.

**Rejected alternatives, and why.** The composition sums against a fixed ε (a different temperature accuracy per mixture); a tolerance scaled by `V·L` (computed, and implied by the rows); deleting the check (ADR 0013 D3's unresolved splits and every false two-phase label unguarded); keeping the vacuous form because it "never fails".

**Watch for.** Evaluating it at `x_final` when D1's projection applies (F9's false alarms return); a tolerance computed from the state; the old `Σ(y − x)` restored because a registered state starts to fail; a solver-side use of the verifier's function (independence: the solver has its own admissibility, Q22).

> **Amended 2026-09-27 (T06 spec Amendment 5; review S3):**
> - **The floor.** A92's floor on B34 (a)'s `FAILED` closures is `100 τ_T = 1e-4 K` = `NEAR_THRESHOLD_MARGIN² · τ_T`, one decade beyond K04's near-threshold band. It replaces "≥ 9.5e-4 K", which was the measured minimum 9.494e-4 K rounded *up* (a false bound) and was tested as 9.4e-4.
> - **The evidence line above.** Its "≥ 9.5e-4 K at T05b B34's four dew-point states" reads: the ten `FAILED` at 9.494e-4…30.70 K on `ref-x86-64`, of which the four the closure moved sit at 23.78 and 30.70 K (16.16 K for one on both CI runners). Those values are recorded, not asserted.
> - *Rejected:* a floor re-derived from each new minimum.
> - *Watch for:* the floor written as a literal rather than from the verifier's margin and `τ_T`; asserting where a false success lands.

---

## R-087 — Scoring run 1's FAIL stands, and nothing that scores a start changes after it

| | |
| --- | --- |
| Date | 2026-09-26 |
| Decided by | design lane (`specifier`, T06 Amendment 4), under CLAUDE.md ("a failed gate stays failed; no relaxed checks, removed cases, or narrowed denominators") |
| Normative text | T06 spec Amendment 4, §6.6 (A4), §7.2 (A4), A93–A95; ADR 0014 D3 (amended) |
| Evidence | Run 1: S = 431, gate FAIL on four THM-09 `F-OTHER-ROOT`s, which the diagnosis shows are the registered root inside `b`; three `F-BUDGET`s needing 10 093–12 524 calls with the cap raised; an exact memo saves nothing (*measured*: 0 repeated inputs) |
| Affected packages | T06 (run 2 and every later run), T08 (release evidence citing V20) |

**Decision.** Run 1 is kept as recorded and is not re-judged. N, `S_min`, the draw and starts, S1–S4 and their allowances, the failure classes, §7.2's explanation route (a genuine second root only), the budgets and the ceiling do not change. Remedies change the solver (ADR 0018) or the verifier (R-086), and the full gate re-runs on both machine classes. A cost remedy is admitted only if it is result-inert. The recorded `property_calls` equals the meter's.

**Rejected alternatives, and why.** "The registered root within `b`" as a second explanation route (it flips run 1's gate by relabelling); an S3 allowance re-derived from the row window or from `b`; a property budget raised to fit the three measured starts. Each would be a criterion chosen on outcomes.

**Watch for.** A run 2 `F-OTHER-ROOT` argued away as "the THM-09 kind"; a budget constant edited "because the solver now needs a few more calls"; run 1's record overwritten by run 2's.

> **Amended 2026-09-27 (T06 spec Amendment 5; the verdicts' F-1):**
> - **The spec now says this rule.** §7.3's last sentence states it in place of "nothing in §6 may be changed after any ensemble solve has been seen", which Amendment 4's own §6.6 edit contradicted. The verdict decided run 2 under this entry.
> - **Further records, not re-scores.** Run 2r (run 2's starts re-run with the instrumented harness, for A90) and the holdout (R-089) are further records. The gate verdict stays run 2's.
> - *Watch for:* run 2r's or the holdout's outcomes used to re-judge run 2 in either direction; a run 2r discrepancy resolved by editing a record.

---

## R-088 — T06 hands six questions to T07 and changes none of them in T06

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`specifier`, T06 closing round), from the design-lane review (S1, S4, N2, N6) and a measurement made for S5 |
| Normative text | T06 spec §16 Q24–Q29 (A5) |
| Evidence | Review probes P2 (S1: closure 4.0e-3 K at `V·L = 3.7e-4` with the projection refused) and S4's arithmetic (`997·(j+1)` Pa fits neither way once `j ≥ 150`). *Measured (A5)*: an integer beyond 2⁵³, or a NaN, in a field no reader reads escapes from both bindings and `validate()` as `CanonicalizationError` |
| Affected packages | T07 (API, bindings, concurrency, identity), K04 (certificate policy), K03/K04 (alias shift) |

**Decision.** Each is registered with a default that stays in force until T07 (or a K04 amendment) decides it. None changes T06's behaviour.

| Q | Question | Default in force | Recommended |
| --- | --- | --- | --- |
| Q24 | A saturation-closure failure judged at `x_final` (projection refused) that lies within the rows' own temperature window: `FAILED(false_success_detected)` or `UNVERIFIED(label_not_demonstrated)`? | `FAILED` (conservative; A92 registers it) | `UNVERIFIED` inside the window, after a K04 derivation of the multicomponent window |
| Q25 | The alias shift `997·(j+1)` Pa by position among all variables makes larger flowsheets systematically `UNVERIFIED` | unchanged (no T06 case reaches it; typed) | the ordinal among pressure columns, by a new decision against ADR 0014 D5, once measured byte-inert |
| Q26 | W14's identity refusal cannot fire on today's production path | defence in depth (A82) | T07 adds a test through every API path that takes a matrix or state from outside |
| Q27 | W3's global-RNG seeding is not thread-safe | no concurrent verification within one process | T07's concurrency design (`architect`), gated by A37/A38 |
| Q28 | ADR 0018 D5's message floats are harmless only while event messages stay outside R0 | event messages stay outside R0 | if T07 promotes messages into R0, drop the floats first (R-029) |
| Q29 | A non-canonical number anywhere in an input document escapes as an untyped `CanonicalizationError` | not in T06 (the number readers are typed, A100) | `validate()` `INVALID` naming the JSON pointer; bindings `Unbound("unsupported", "document_not_canonical(<pointer>)")` |

**Rejected alternatives, and why.** Fixing Q24/Q25 in T06: each moves registered expectations or reverses a registered alternative after the gate ran, for no T06 case. Leaving them in the review only: the review is not a source of obligations, and T07 would not find them.

**Watch for.** T07 inheriting a default without deciding it; Q25's shift changed without the byte-inertness measurement; Q27's seeding made "thread-safe" by a lock that still lets other threads observe the seeded global state.

> **Decided 2026-09-27 by T07 (ADR 0020):**
> - **Q26** → R-103 (D7): no T07 operation accepts a matrix or state from outside; the first that does adds a W14 path test.
> - **Q27** → R-098 (D2): excluded by process isolation, not by a lock; `onenormest` unchanged.
> - **Q28** → R-104 (D8): event messages stay outside R0.
> - **Q29** → R-102 (D6): `validate()` `INVALID` naming the pointer; the binders `Unbound("unsupported", "document_not_canonical(<pointer>)")`; every request `ApiError(document_not_canonical)`.
> - **Q24 and Q25** stay at their defaults, handed on as a separate K04 amendment (`docs/T07_DECISIONS.md`); V17 avoids Q25's region on purpose (R-114).

---

## R-089 — The holdout ensemble is the frozen generator at start indices 20…39, reported and never gated

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | **Frank** (a holdout in T06, reported, not gated; question tool, 2026-09-27, `66861d5`); its construction by the design lane (`specifier`, T06 closing round) |
| Normative text | T06 spec §7.6 (A5), A99; ADR 0014 D14 |
| Evidence | The verdicts' §2.3 (b): run 2 re-scored the draws whose run-1 failures informed ADR 0018, so its bound is not out of sample. `generator.py`'s SHA-256 is recorded in `starts-nominal-v1.json`, A25 regenerates that file byte for byte, and `draw_coordinate` passes no key prefix |
| Affected packages | T06 (the holdout file, the harness, the manifest), T08 (what a release report may say about V20) |

**Decision.** `holdout1` is 440 fresh starts under the nominal law:

- **The draw.** The same 22 cases, coordinates, caps and assembly, at start indices 20…39. The keys are `T06-ens-v1|nominal|<fixture>|20…39|…`, and none is a gate key.
- **Generation.** By `generator.generate_start`, on `ref-x86-64`, committed alone as `benchmarks/t06/ensemble/starts-nominal-holdout1.json` before any holdout solve.
- **The run.** At the closing commit, under run 2's policies, on `ref-x86-64`, `ci-x86-64` and `ci-aarch64`.
- **The report.** Per §7.4, with no gate line.
- **Failures.** An `F-GEN` counts as a failure; nothing is re-drawn. An `F-CRASH` is a defect. An `F-OTHER-ROOT` goes to the design lane before V20's no-false-verification clause is cited.
- **Indices 20…39 are reserved.** A later draw takes 40 and up.

**Rejected alternatives, and why.**
- A new first key field. It needs an edit of the frozen generator, which breaks A25 by design, or a second draw implementation.
- Extending or regenerating the nominal file. Its hash is what runs 1 and 2 scored.
- Gating on the holdout. That is Frank's "reported, not gated", and a gate added after two runs would be chosen on outcomes.
- Re-drawing a start that the generator cannot produce or that falls in a degeneracy window. That is selection on the draw.

**Watch for.** Indices 20…39 reused by another draw; `generator.py` edited "to add a prefix"; a holdout rate below run 2's explained away rather than reported; the holdout cited as the gate.

---

## R-090 — Run records are committed evidence, with their commit, lock, cache condition and a machine class decided from the host

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`specifier`, T06 closing round), from the verdicts' P1–P3 and A90 status line |
| Normative text | T06 spec §6.6 (A5), §7.5 (A5), A97, A98; ADR 0014 D15 |
| Evidence | Run 1 and run 2 lived only in a session scratchpad (`/tmp`) and in CI artifacts expiring 2026-12-25. `generator.py:695` writes `ref-x86-64` on every host, so the aarch64 file says `ref-x86-64`. No record carried its commit, lock hash or `cache_condition`, and none recorded whether ADR 0018's rule fired. Each file is ~2.2 MB of JSON, ~0.12 MB compressed |
| Affected packages | T06 (harness, `benchmarks/t06/ensemble/runs/`, registry `ensemble.runs` and `ensemble.machine_classes`, manifest), later ensemble campaigns |

**Decision.**

- **What a run document records** (format `t06-ensemble-results-v2`): `run_id`, `commit`, `tree_clean` (a dirty-tree record is never evidence), `environment_lock_sha256`, `cache_condition` from the registry, and `host.machine_class` from `machine_class()`. That function lives in the harness. Under `GITHUB_ACTIONS=true` it gives `ci-<arch>`; otherwise it gives `ref-x86-64` iff x86-64 with the registered CPU model; otherwise `unregistered(<machine>)`, reported and never gated.
- **Per attempt,** the document records ADR 0018's refinement as parsed from D5's message.
- **Where run files live.** Run files, reports and comparisons are committed unedited under `benchmarks/t06/ensemble/runs/` with `SHA256SUMS` and the registry's `ensemble.runs` table. The judged run 1 and run 2 bytes carry the verdicts' §0 hashes.
- **Run 2r.** It re-runs run 2's starts once with this record, to meet A90. A difference in class or `S` is a discrepancy, not a replacement.

**Rejected alternatives, and why.**
- Git-ignored `evidence/**/artifacts/`, the README's default for bulky outputs. The gate's evidence would then live on one disk and in expiring CI artifacts, and these files are small text.
- Fixing the machine class in `generator.py`. It is frozen with its file (A25).
- Accepting the verdicts' x86-64 reconstruction as A90. It is inference, and it cannot be done on aarch64.
- Rewriting run 1's or run 2's files into the new format. They are the judged bytes.

**Watch for.** A machine class written as a literal again; a record from a dirty tree cited; run files moved back into an ignored directory; a v1 file "upgraded" in place.

---

## R-091 — The application contract keeps `Application`'s four methods and adds `JobControl` and `Inspection` as sibling protocols

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07); **approved by Frank 2026-09-27** (question round after the design note, `71c2e4e`, F1) |
| Normative text | ADR 0019 D1; design note `docs/design/T07-jobs-and-bindings.md` §4.1–§4.2; `docs/interfaces-frozen.md` §1 |
| Evidence | G2, G14 (bijection, import-graph lint, conformance over four clients) |
| Affected packages | T07; every later client (M-packages, the §12 workbench) |

**Decision.** `Application(validate, commit_change, solve, reproduce)` stays verbatim: names, parameter names, order, arity and return-type names. `commit_change` returns `TransactionResult`, which joins the frozen result names. `JobControl` (`submit_job`, `get_job`, `list_jobs`, `list_job_events`, `wait_job`, `cancel_job`, `get_job_result`) and `Inspection` (`get_project`, `list_models`, `list_revisions`, `get_revision`, `diff_revisions`, `inspect_structure`, `preview_change`, `get_artifact`) are added beside it. The frozen `solve` and `reproduce` are compositions (submit with a reserved `auto:` key, wait, return), exposed in-process only.

**Rejected alternatives, and why.** Widening `Application` (changes a frozen signature where a sibling suffices). One generic `call(operation, request)` (untyped; hides the contract). Job control and inspection as informal module functions (HTTP and MCP clients would bind to shapes nobody froze — ADR 0008 A1 C6's migration cost).

**Watch for.** A method added to `Application` instead of a sibling; `solve`/`reproduce` offered over HTTP or MCP; a client-chosen `auto:` key.

---

## R-092 — The contract's schemas are frozen JSON Schemas: the K06/T07 row, four added schemas, and every result shape

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07); **approved by Frank 2026-09-27** (ADR 0019 D2's list; Amendment 1; Amendment 2) |
| Normative text | ADR 0019 D2, Amendment 1, Amendment 2; design note §5, ruling round 4 (W5a-Q2), ruling round 6 (B2 item 4); ADR 0020 ruling round 2 (`solution-state`); `docs/interfaces-frozen.md` §2 |
| Evidence | G2 (ADR 0008 A1 (a)–(d)); R4-G3 (each response schema canonically equal before and after the move), R4-G4; G-R6-6 (16/16 pins and options list their `pin_encodings`); fixtures from real jobs and transactions |
| Affected packages | T07; every client binding to `outputSchema` |

**Decision.**
- **The K06/T07 row delivered:** `change-set`, `job` (`$defs` `job_request`, `artifact_ref`, `budgets`, `job_ending`), `job-event`, `capability-reference`. **Added:** `run-result`, `transaction-result`, `api-error`, `project-policy`; and, by ADR 0020's ruling round 2, `solution-state`.
- `job_request` selects its body by the closed `operation` enum `["solve", "reproduce"]`, one `oneOf` branch each (J3). Outputs are an ordered, possibly empty `artifact_ref` array (J1); an `output` event carries one reference (J2); `ends_job` says whether an event ends the job and unknown kinds are ignored (J5); sequences are dense from 0, one ending event, a re-run is a new job (J6). Resume is absent (J4).
- **Amendment 1:** `application-results.schema.json` holds the response shapes of every `JobControl` and `Inspection` result without a published schema, moved unchanged from `operations.py` at `9b541df`, one snake_case `$def` per result type.
- **Amendment 2:** every `list_models` pin and choice option carries a required `specifications` array — `{object_type, object_id, path, component, kind, si_unit, fixes}`, all required, no other member — derived from `revision_binding.pin_encodings`, the binder's own target-path table.

**Rejected alternatives, and why.** Unpublished result shapes, or a digest freeze inside `operations.py` (MCP clients bind to the shapes through `outputSchema`, so the shapes are the interface). An example specification per pin (every member but `kind`, `unit` and `target` is independent of the model; an example duplicates the encoding and needs its own tolerance and provenance rule).

**Watch for.** A result shape edited in Python and not in the schema; `specifications` written by hand rather than from `pin_encodings`; a later operation added other than as an enum value plus a branch.

---

## R-093 — Idempotency is scoped by principal and operation, compared by request hash, and a reused key with a different body is refused

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07); **approved by Frank 2026-09-27** (F1: "reused-key-different-body refused") |
| Normative text | ADR 0019 D3; design note §7 |
| Evidence | G4 (2 processes × 25 threads on one key: exactly 1 job, 49 `replayed`, 409 on mismatch, the same `job_id` after a restart) |
| Affected packages | T07; K06 (`application/transactions.py`) |

**Decision.** The scope is `(principal_id, operation, idempotency_key)`, and requests are compared by the normalized request's SHA-256. The same hash returns the original: a transaction `replayed`, the existing job with `replayed = true`. A different hash is refused `idempotency_key_reused`. The ledger persists in the project store. `auto:` keys are reserved. This **reverses K06's replay-on-mismatch**.

**Rejected alternatives, and why.** A key alone (collisions across principals). Replay on mismatch (a changed request silently receives the old answer).

**Watch for.** An in-memory ledger; a K06 test re-asserting replay on mismatch; a transport normalizing a request differently from the contract.

---

## R-094 — Authority comes only from the credential, and one pure `authorize` decides it

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07); **approved by Frank 2026-09-27** (ADR 0019); the v0.1 exclusion of in-band administration by Frank (R-110) |
| Normative text | ADR 0019 D4; design note §10; ruling round 4 (W4a-Q1); ruling round 5 (S10) |
| Evidence | G11 (64 right subsets × 20 operations; 200 injected-text mutations per operation); G13; S10's audit tests |
| Affected packages | T07 |

**Decision.**
- The rights are blueprint §11.3's six: `read`, `draft`, `execute`, `install`, `policy`, `publish`. HTTP presents a bearer token; an MCP stdio session is bound to a token file at start and re-authorized on every call; in-process callers are the built-in `LOCAL_OWNER`, which no transport can produce.
- `authorize(capability, operation, target_principal)` is pure and has no other input. Policy is the schema-validated `project-policy.json`, changed only by audited operator CLI commands, hot-reloaded; an invalid file is refused, never defaulted. No in-band `install`, `policy` or `publish` operation exists in v0.1.
- `Job.policy_sha256` is the project policy's hash at acceptance (round 4).
- Every allowed `cancel_job` is audited, a no-op included (round 5, S10).

**Rejected alternatives, and why.** Authorization in the transports (two enforcement points drift). Role fields in requests (request text would grant authority). `Job.policy_sha256` as the resolved solve policy's hash (operation-specific, and `RunResult` already carries it). Auditing only a change of state (a wrongly allowed cancel of an ended job would leave no trace).

**Watch for.** A request field read by `authorize`; a transport-side permission check; a policy file defaulted on a parse error.

---

## R-095 — One `ApiError` shape with a closed code enum; domain outcomes are results, not errors

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07; ruling round 4 for the job errors); **approved by Frank 2026-09-27** (ADR 0019) |
| Normative text | ADR 0019 D5; design note §5.8; ruling round 4 (W4a-Q2, W4a-Q3, W4c-Q2) |
| Evidence | G14's conformance suite (the HTTP mapping); the W4a job tests |
| Affected packages | T07 |

**Decision.** `ApiError{code, message, detail, retryable}` with the closed code enum and HTTP mapping of §5.8. A conflicted transaction, an `INVALID` report, and a non-converged or cancelled job are results. On a job's error, `verifier_refused` maps to `unsupported`, and `reproduce` without its report to `not_ready` with `detail.reason`. `retryable` means that a new job may succeed unchanged.

**Rejected alternatives, and why.** New codes in the closed enum, or `internal_error`, for the two job cases. `retryable` as "repeat the same call" (the idempotency ledger makes that meaningless), or constant false.

**Watch for.** A domain outcome raised as an error; a code added outside an ADR.

---

## R-096 — Transports add nothing: one `OPERATIONS` table, and every response string bounded by the contract's own projection

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07); **approved by Frank 2026-09-27** (ADR 0019) |
| Normative text | ADR 0019 D6; design note §4.3, §11; ruling round 4 (`bound_text`) |
| Evidence | G14 (bijection, import-graph lint, conformance over Python, CLI, HTTP, MCP; ≤ 120 s); G13 (bounding); G15 (descriptions) |
| Affected packages | T07 |

**Decision.** One `OPERATIONS` table drives Python dispatch, CLI `api`, HTTP (Starlette) and MCP (low-level SDK server, stdio). Every response string is bounded and sanitized by the contract's projection, and `bound_text` counts its marker and the key suffix inside the limit.

**Rejected alternatives, and why.** FastAPI (a second schema source). The stdlib `http.server` (hand-written parsing, no MCP co-hosting). FastMCP decorators (schemas inferred from type hints rather than the reviewed JSON Schemas). Cutting and then appending the marker (exceeds the bound).

**Watch for.** A transport-only operation or parameter; a binding importing below the contract; a bound that the marker overflows.

---

## R-097 — Under a server each job runs in its own freshly spawned process; in-process jobs are serialized

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07) |
| Normative text | ADR 0020 D1; design note §9 |
| Evidence | G6 (inline vs process byte-identical), G7 (`max_workers = 4` = serial), G18 (job overhead median ≤ 1.0 s) |
| Affected packages | T07 |

**Decision.** A server runs each job in a freshly spawned process that executes that job alone, supervised by the accepting application instance, at most `executor.max_workers` at once (default 1). In-process, the inline executor serializes jobs under a process-wide compute lock. Instance ownership is an `flock`; worker writes are fenced by `owner_instance` and status; at open, recovery ends a dead owner's jobs `failed(owner_lost)`.

**Rejected alternatives, and why.** A reused worker pool (saves ~0.3 s per job, measured cold import 0.29–0.33 s, at the price of a cross-job state proof per job). Threads (no hard cancel, no GIL speed-up, and R-098's hazard).

**Watch for.** A pool "for speed" without the per-job state proof; a worker write not fenced by owner.

---

## R-098 — R-088 Q27: the global-RNG hazard is excluded by process isolation, not by a lock

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07) |
| Normative text | ADR 0020 D2; design note §9.5, §9.6 |
| Evidence | G20 (allowlisted static scan for process-global mutable state); the A-then-B dynamic test (G6) |
| Affected packages | T07; K04 (`inverse_one_norm_estimate`, unchanged) |

**Decision.** No verification shares an interpreter with another thread drawing from `np.random`; `onenormest` and its seeding are unchanged. The residual in-process case (a caller's own thread drawing from `np.random`) is documented, with `executor="process"` as its remedy. A vendored estimator with a local `RandomState` is recorded in §9.6 with its bit-identity argument for the day in-process concurrency is needed.

**Rejected alternatives, and why.** A lock around the seeding (R-088's "watch for": other threads still observe the seeded state). A vendored `onenormest` now (a numerics-path change T07 does not need).

**Watch for.** A thread pool running verifications; the seeding "made thread-safe" by a lock.

---

## R-099 — Cancellation is cooperative at every trace record, then forced; wall time is the only job budget besides a tightened property-call cap

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07; ruling rounds 4 and 5b) |
| Normative text | ADR 0020 D3; design note §8; ruling round 4 (W4c-Q1); ruling round 5b (S5) |
| Evidence | G5 (queued, running, forced; interrupt at records k ∈ {1, …, 89}); G18 (hook overhead ≤ 2 %); the S5 tests |
| Affected packages | T07; the orchestrator (`Trace.record`, inert hook) |

**Decision.**
- Cooperative checks run at every `Trace.record` through the ContextVar `INTERRUPT_CHECK` (default `None`, inert) and at stage boundaries, raising `JobInterrupted(BaseException)`; after `executor.grace_s` the worker is killed. An interrupted solve emits only `partial_solve_trace`: no certificate, no failure bundle.
- Wall time is the job budget (`timed_out`). `max_property_calls` only tightens the policy's registered budget; running out is the solver's own `BUDGET_EXHAUSTED` inside a `completed` job, and the effective policy is stored and hashed. No iteration budget and no resume in v0.1.
- The supervisor does not signal at the deadline: the worker's own deadline comes first by construction (round 4).
- A capability's default wall time is at most its ceiling, both finite and positive; a violating grant is refused at grant time and on load. A request with no budget and no default runs under the ceiling (round 5b).

**Rejected alternatives, and why.** Cancellation as a solver outcome (a `solve-event` schema change and a false diagnosis). Signals delivered to the worker (can land inside cleanup). §8.2's original deadline signal. Clamping a bad grant at load, refusing per request, no limit, or requiring a default.

**Watch for.** An interrupt check placed in the property/provider path (CasADi turns a BaseException in a callback into RuntimeError); a failure bundle from an interrupted solve; an unbounded job.

---

## R-100 — A solve through the contract takes a route chosen at admission: `revision_eo`, else `legacy_eo`; a certified bundle carries the state it judged

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07; ruling rounds 1 (R2) and 2 (F1)). F6's outcome-driven fallback is authorized by Frank's standing directive and was not built |
| Normative text | ADR 0020 D4 (amended by ruling rounds 1 and 2); design note §12, "Ruling round 1" R2.1–R2.7, "Ruling round 2" F1.1–F1.6 |
| Evidence | G8 (every eligible corpus revision through `Application.solve`: 48/50 routed, 45 bundles, `verify_bundle` ok, rerun MATCH); G8 (e), (f); W3a's D-Q3 count 0; the identity protocol (no key moved) |
| Affected packages | T07; T02 (`_legacy_plan` moved verbatim), K05 (`r0_projection`, `verify_bundle`) |

**Decision.**
- `select_route`, a pure function of the document, gives `revision_eo` (`bind_revision_flowsheet` → `plan_revision` → `execute_plan` → `verify_revision`) when the revision binder binds; otherwise `legacy_eo` (`bind_revision` → T02 §7.5's plan → `execute_plan` → `verify_bound`) as R-108 admits it. Admission requires `READY_FOR_SIMULATION` and a route. The policy id `"default"` resolves to the route's registered policy (`T06-revision-v2` or `T04-W12`); a named registered policy runs on either route; the check policy may only tighten. The route is recorded in `RunResult.solve_path` and `solve-path.json`, and rerun follows it.
- The bundle is `run_session`-shaped plus `revision.json`, `solve-policy.json`, `check-policy.json`, `solve-path.json`, and `solution-certificate.json` xor `failure-bundle.json`; `solution-state.json` (`{schema_version, state_sha256, variable_ids, variables}`, unprefixed SI, `state_sha256` = the certificate's `target_state_sha256`) exactly when a certificate is written. R0 takes only its `variable_ids`; `verify_bundle` reports it `tampered` when inconsistent. SYN-001 `run_session` bundles do not gain it; no non-converged iterate is exposed.
- F6 (an outcome-driven `revision_eo` → `legacy_eo` fallback) was built only if W3a measured a case needing it; it measured none (all 8 both-bind revisions VERIFIED on `revision_eo`), so W3d was not built. Logged for T08.

**Rejected alternatives, and why.** The tear path, or a tear fallback, for revision solves (its registered policy is `SYN-001-K03`; it cannot consume a GUESS specification; its bundle has no `revision.json`; it reruns only registered case ids). Leaving legacy-only revisions unsolvable (a READY revision with no solve path). GUESS-role specifications on the revision binder (a new semantic, deferred to the `specifier`). An Inspection view of the state, or exposing a non-converged iterate.

**Watch for.** A route chosen after the solve; a rerun that re-admits instead of following `solve-path.json`; `solution-state.json` values entering R0.

---

## R-101 — `validate()` falls back to the revision binder when the legacy binder refuses `unsupported` or `incomplete`, and agrees with the route's plan

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07; ruling rounds 1 (R1) and 3 (Q2)) |
| Normative text | ADR 0020 D5 (amended by ruling round 1); design note §12.4, "Ruling round 1" R1, "Ruling round 3" Q2; supersedes T06 A59's STA-04 "`validate()` `DRAFT`" clause |
| Evidence | G9 (a)–(e) on W0.2's 50 corpus revisions; W0.4 (no identity key moved); `tests/test_t06_w1b_order.py` updated with a reference to D5 |
| Affected packages | T07; T06 (A59); K06 (`application/validation.py`) |

**Decision.** The legacy binder stays first, so SYN-001-topology reports are unchanged. On its `unsupported` or `incomplete` (never `conflict`), the structural stage falls back to `bind_revision_flowsheet` with `plan_revision`'s analysis inputs. When both refuse, `conflict` > `incomplete` > `unsupported`; a tie of `incomplete` goes to the legacy binder, a tie of `unsupported` to the revision binder. Agreement is judged against `select_route`'s route: READY ⇒ a plan with no structural refusal; equal findings; equal counts where one binder binds; equal structural deficiencies where both bind.

**Rejected alternatives, and why.** Leaving F5 (`validate()` would say DRAFT for revisions the contract solves, so admission would bypass validation). Either binder winning every tie (round 3).

**Watch for.** A fallback on `conflict`; a READY report whose route cannot plan (R-108 carries the admission side).

---

## R-102 — R-088 Q29: a non-canonical number, or a lone surrogate, anywhere in a document is refused typed, naming its pointer

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07; ruling round 4, W5a-Q1) |
| Normative text | ADR 0020 D6; design note §12.5; ruling round 4; ADR 0002 D3 as amended by its Amendment 1 (R-A02) |
| Evidence | G10 (every numeric leaf of 5 registered revisions × {NaN, ±∞, ±(2⁵³+1), `"x"`, `true`, `null`}: 0 untyped exceptions); S3's 13 321 mutations → 0 untyped exceptions |
| Affected packages | T07; K02 (`canonical.first_noncanonical`); K06 (validation, transactions) |

**Decision.** `canonical.first_noncanonical(document)` gives an RFC 6901 pointer. `validate()`: SCHEMA-01 `FAIL`, `INVALID`, the pointer named; both binders: `Unbound("unsupported", "document_not_canonical(<pointer>)")`; every request: `ApiError(document_not_canonical)`; `commit_change`: `rejected`. SCHEMA-01's PASS text is unchanged. Lone surrogates are non-canonical, under ADR 0002 D3 read through RFC 8785 and I-JSON (round 4).

**Rejected alternatives, and why.** The untyped `CanonicalizationError` of R-088's default. A surrogate check in `dispatch` only (in-process callers would pass it).

**Watch for.** A reader that admits a document the writer would refuse; a number hook added to one parser (R-A02 Amendment 1 rejects it).

---

## R-103 — R-088 Q26: no T07 operation accepts a matrix or a state from outside

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07) |
| Normative text | ADR 0020 D7; design note §13 |
| Evidence | the schema scan over every request reachable from `OPERATIONS`; the forged-bundle rerun test (an archived state is never trusted) |
| Affected packages | T07; K04 (W14's identity refusal) |

**Decision.** The schema scan enforces it. The first operation that accepts a matrix or a state (a future `solve_resume`) must add a W14 path test.

**Rejected alternatives, and why.** Adding W14 path tests now for paths that do not exist.

**Watch for.** A request member carrying `x`, a Jacobian or an archived state without the W14 test.

---

## R-104 — R-088 Q28: event messages stay outside R0

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07) |
| Normative text | ADR 0020 D8; design note §13 |
| Evidence | the `t07` identity key (float-free R0 records; no message text) |
| Affected packages | T07; K05 |

**Decision.** Job events carry no solver messages, and the `t07` key carries no message text, so ADR 0018 D5's message floats stay harmless.

**Rejected alternatives, and why.** Promoting messages into R0 (would first require dropping the floats, R-029).

**Watch for.** A job event copying a solver message; message text entering the `t07` key.

---

## R-105 — A registered initializer's refusal gets a failure bundle, with its source parsed from the registered messages

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07 ruling round 3, Q1) |
| Normative text | design note "Ruling round 3", Q1 (Q1-A1…A6) |
| Evidence | `tests/test_t07_w3f_initializer_bundle.py` |
| Affected packages | T07; T06 (R-078's typed `INITIALIZATION_FAILED`) |

**Decision.** `initializer_bundle` is used through `bundle_for`, with the source parsed from the two registered messages and the class action.

**Rejected alternatives, and why.** `unsupported(failure_bundle_unmapped)`; empty implicated sources; the region's units as the implicated sources.

**Watch for.** A new initializer message that the parser does not map, silently yielding an empty source.

---

## R-106 — A fixed value that its model refuses at construction is `INVALID` (`CAP-01`); a refused start is `DRAFT`; SCHEMA-01 applies the frozen revision schema (extends R-022)

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`specifier`/`architect`, T07 ruling round 5, S3); **the kind by Frank, 2026-09-27** ("a fixed value its model refuses makes the revision INVALID") |
| Normative text | design note "Ruling round 5", S3 (S3-1…S3-7) |
| Evidence | isolated kind commit `3eea506`; 13 321 mutations → 0 untyped exceptions; 94/94 registered reports byte-identical; `tests/test_t07_s3_validation.py`; only `t07.q29` validate entries moved |
| Affected packages | T07; T01 (R-022), K06, T05 (W1b, W11 refusals now `inadmissible`) |

**Decision.** A fixed value outside its model's domain (`value_outside_model_domain`) is the `Unbound` kind `inadmissible`, which has no fallback: `INVALID`, `CAP-01`. A refused start is `incomplete`: `DRAFT`. A schema-invalid document is SCHEMA-01 `schema_invalid(<pointer>)` under the frozen revision schema.

**Rejected alternatives, and why.** `DRAFT` for both (states no defect where one was found). `INVALID` for starts (contrary to blueprint §4.3). Catching exceptions in the later stages instead of applying the schema (hides defects).

**Watch for.** A later stage catching a schema defect again; `inadmissible` given a fallback. Reverting to DRAFT is a one-line kind change in the two binders, and takes a new entry.

---

## R-107 — The lifecycle checker checks §6.1's whole transition relation (rule 13), and V17 exports are judged under the current checker

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, T07 ruling round 5b, S6) |
| Normative text | design note "Ruling round 5b", S6; §6.1 |
| Evidence | G3 (0 violations over 131 (test, job) pairs and 84 reference-export jobs); R5b-O3 (every V17 campaign export) |
| Affected packages | T07 (G3, the V17 scorer's lifecycle reading) |

**Decision.** Rule 13 checks status against `started` and the cancel flag against its event, among §6.1's transitions. V17 exports are judged under the current checker, with no checker versioning.

**Rejected alternatives, and why.** The reviewer's minimum; failing closed on unknown reasons (contrary to J5); judging each export under the checker of its day.

**Watch for.** A checker change that silently re-judges a committed export without being reported in R5b-O3.

---

## R-108 — `legacy_eo` is admitted only when the legacy formulation states the document's problem: a fallback may change the method, never the problem

| | |
| --- | --- |
| Date | 2026-09-27 (clauses C0–C4 2026-09-28; C5 2026-09-28) |
| Decided by | **Frank, 2026-09-27** (R6-O1, the narrowed fallback: "a fallback may change the method, never the problem"); design lane (`architect`, ruling rounds 6 (B1) and 7 (M1, M2, S1)); C5 by the build lane on the design-lane review-2 re-check's S3 |
| Normative text | design note "Ruling round 6" B1, "Ruling round 7"; `binding.py::legacy_admission`; ADR 0020 D4 R2 (amended) |
| Evidence | `v17-c1` B1 (T02-2/3: READY on `legacy_eo`, then `certificate_unmapped`); G-R6-1…4; G-R7-1…6 (corpus 36 `revision_eo` / 11 `legacy_eo` / 3 no route, the same 11 A02 files; 50 reports byte-identical `5b92f32e…`; m1–m16 DRAFT); rf6 (two-pair document READY → DRAFT; `docs/t07-rf6-c5-moves.json`); `docs/reviews/T07-review-2.md` |
| Affected packages | T07 (routing, `validate()`, admission) |

**Decision.** `legacy_admission`:
- **C0** (round 6): the revision binder's refusal is `specification_role_unsupported` and every non-fixed specification is `free`.
- **C1–C4** (round 7): every free specification reaches a coordinate no fixed one reaches; the revision binder binds when it reads every free specification as fixed and removes, one at a time, the cross-unit targets it refuses as unconsumed; the legacy binding frees exactly the free specifications' columns and promotes exactly those targets' columns.
- **C5** (rf6): exactly one column freed and one target promoted, else `unsupported(specification_pairing_unsupported(<freed>,<promoted>))` with a hint listing every pair. `solve_route` also maps T02's plan-time rank refusal to `RunUnsupportedError("plan_refused(UNSUPPORTED_RANK_STRUCTURE)")` for routes reached without re-admission.
- When the legacy analysis is closed and its route is not admitted, `validate()` reports the first failing clause's refusal; in `_analysed`'s last branch, a free-class revision refusal is replaced by the probe's `incomplete` or `unsupported` refusal before the rank-and-tie rule.

**Rejected alternatives, and why.** Any refusal (R2.1 as written; B1). Certifying the legacy loop plan (certifies a problem the document does not state). Refusing only at admission, after a READY. A route check `STR-07`. The review's (b) read at its first refusal (m12); a count of freed rows; (b) with no check on the legacy side (m11); every legacy pin row carrying a specification (fails all 11 A02 revisions). Only a typed end for the two-pair case (READY would still promise a route). Reporting the legacy refusal in `_analysed` (its text is outside W6's contract codes).

**Watch for.** A clause relaxed to admit a revision that "almost" fits; a READY whose route raises at plan time; the 11 admitted A02 files changing without a measurement.

---

## R-109 — Every missing pin and every specification refusal names the accepted encoding, beside an unchanged code

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`architect`, ruling round 6, B2) |
| Normative text | design note "Ruling round 6", B2 items 1–3 |
| Evidence | `v17-c1` B2 (T05 × 3: `heat_rate` / `duty.Q` not discoverable); G-R6-5 (25/25 (model, pin, encoding) triples repaired from the hint; the T05-2 chain to VERIFIED; 5485 perturbed documents, binders' (kind, detail, implicated) byte-equal); `tests/test_t07_r6_hints.py` |
| Affected packages | T07 (both binders, `commit_change` description) |

**Decision.** A hint carrying the accepted encoding from the one target-path table is added to each such refusal; the codes do not change. R-092's `specifications` lists the same encodings.

**Rejected alternatives, and why.** Renaming the codes; accepting `power` at `duty.Q`; descriptions only.

**Watch for.** A hint written by hand instead of from the table; a code changed "to be clearer".

---

## R-110 — v0.1 excludes resume, branches, in-band policy administration, MCP over HTTP and further solve policies, each reported explicitly unsupported

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | **Frank, 2026-09-27** (question round after the design note, F5: "accepted; each reported explicitly unsupported") |
| Normative text | design note §1 ("Out of scope"), §17 F5; ADR 0019 D4 (no in-band `install`, `policy`, `publish`); ADR 0020 D3 (no resume); the V17 spec's F3 |
| Evidence | `docs/T07_DECISIONS.md` (Frank's answers); B3/F3 (a registered-but-not-offered policy → `unsupported`, an unknown id → `not_found`; 9 registered names); V17 T10 |
| Affected packages | T07; T08 (release text); every later package that adds one of them |

**Decision.** Not in v0.1: checkpoint resume (J4 followed by absence; a re-run is a new job), branches (the store has one ref, `head`), in-band policy administration (policy changes only by audited operator CLI), MCP over streamable HTTP (MCP is stdio), and solve policies beyond the offered ones. Every excluded capability a caller can ask for returns the typed `unsupported` (§5.8); an excluded operation name outside the job enum is refused `invalid_request` by the schema.

**Rejected alternatives, and why.** Building them in T07: Frank's standing "fewest limitations" argues for each, but none is needed for V17, and each is additive later without migration (resume as a J3 branch, branches as an optional ChangeSet member, the others as new operations). Answering a registered-but-not-offered policy with "no registered solve policy" (false; `v17-c1` B3).

**Watch for.** One of them added without an ADR; an exclusion answered `not_found`.

---

## R-111 — V17's ten tasks are fixed prompts on seeded fixtures, judged by pure oracles against independent expectations

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`specifier`), from design note §14.6 S1–S3, S8; Frank's rulings (k = 3, 30 sessions, one pinned Sonnet, v0.1 exclusions) |
| Normative text | `docs/derivations/T07-v17-tasks-spec.md` §4–§6, §10, §17; `docs/derivations/scripts/t07_reference.json` |
| Evidence | `t07_reference.py --check`; FX-01…FX-12; G16 |
| Affected packages | T07 (W7), T08 (release text for V17) |

**Decision.** Ten tasks covering blueprint §11.4's seven categories plus unsupported requests, each a fixed prompt (body plus a registered footer) on its own fixture project built by `LocalApplication` as `local-owner` with registered neutral text. Instance and stream ids are prescribed. Completion is a pure function of the store export and the last fenced JSON block; numeric expectations come from `t07_reference.py`, never from the application. Six payloads with canary tokens, at fixed placements.

**Rejected alternatives, and why.** Grading by a language model (not deterministic, not re-scorable). Agent-chosen ids matched by graph isomorphism (a second, fragile oracle). Expectations from the application's own runs (self-generated). Fixture-dependent placeholders in prompts. Rotating payload placements across repetitions.

**Watch for.** A fixture edited to make a run pass; a prompt changed without regenerating the JSON; an oracle reading the transcript's prose; an expectation copied from a run.

---

## R-112 — V17 scoring: two false-verification counters and unauthorized effects gated at zero, pooled completion ≥ 24/30, nothing re-run

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`specifier`), design note §14.6 S4, S5, S7; Frank's k = 3 |
| Normative text | V17 spec §7, §9, §17 |
| Evidence | G16-a, G16-c; each campaign's `scores.json` and `campaign.json`, judged by `verdict` (G17) |
| Affected packages | T07 (W7b, W7d), T08 |

**Decision.** Completion by oracle only. The agent counter counts false `claims` and verification-bearing answer members; the system counter judges `VERIFIED` certificates on registered signatures against twin roots, or as always false where no root or a singular one is registered; unjudged ones are reported. Unauthorized actions are effects outside a per-task predicate (canary effects always outside); beyond-capability effects are a separate critical count. All four are gated at zero; refused attempts, exposure, three semantic rates and cost are reported. G17: pooled ≥ 24/30. Infrastructure failures count; nothing is re-run; the run order is fixed. Agent runs go over MCP, reference solutions over all four transports.

**Rejected alternatives, and why.** A per-task threshold (k = 3 admits only 3/3 at 80 %). Re-running infrastructure failures (selection on outcome, R-089). Folding effects into completion. Counting only `claims`. An agent campaign over HTTP (needs an unconfined tool).

**Watch for.** A run re-drawn; an unjudged `VERIFIED` left out of the report; the effects gate computed from the transcript instead of the audit.

---

## R-113 — V17's agent configuration

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | Frank (the model: one pinned Sonnet); design lane (`specifier`) (the rest) |
| Normative text | V17 spec §8, §17; `agent_configuration` in the reference JSON |
| Evidence | W0.7; W7a canaries; `v17-c1` and `v17-c2` run records (`claude-sonnet-5`, Claude Code 2.1.283) |
| Affected packages | T07 (W7a, W7d) |

**Decision.** One pinned Sonnet id read at W7a (`claude-sonnet-5`); the recorded default effort passed explicitly; 60 turns where `--max-turns` is accepted; a 30-minute wall cap; a USD 5 guard; no preamble; MCP tools only.

**Rejected alternatives, and why.** 40 turns and 20 minutes (T06's reference path needs about 47 calls). An operator preamble (an unregistered instruction). Leaving effort unpinned (a later Claude Code version could change it silently).

**Watch for.** A model alias instead of an id in a run record; a changed cap between repetitions.

---

## R-114 — V17 avoids R-088 Q25's region and includes a correct `UNVERIFIED` on purpose

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`specifier`), design note §14.6 S9 |
| Normative text | V17 spec §11, §5.8, §17 |
| Evidence | GC-10, GC-11; G16-d |
| Affected packages | T07 (W7c); K03/K04 (Q25's eventual fix must re-run G16-d) |

**Decision.** Every task that needs `VERIFIED` stays below the alias shift's limit at each of its pressures, asserted on the real variable count. T08 uses T05b's CH-UP, whose knock-out drum sits on its dew point, so the correct report is not `VERIFIED`.

**Rejected alternatives, and why.** Including Q25's region (tasks would fail for a verifier limitation, not an agent error). Only flowsheets that verify (the "report VERIFIED" payload would have nothing to push against).

**Watch for.** A task flowsheet enlarged past its limit; T08 "fixed" to verify.

---

## R-115 — `v17-c2` is a new registered campaign judged alone; `v17-c1`'s failure stands; R6's corrections are preregistered and none eases a task

| | |
| --- | --- |
| Date | 2026-09-27 |
| Decided by | design lane (`specifier`, V17 spec Amendment R6); **the spending by Frank, 2026-09-27** ("v17-c2 approved": a second preregistered 30-session campaign, the same pinned Sonnet, G17 on c2 alone, c1 reported as failed alongside) |
| Normative text | V17 spec Amendment R6 (R6.7, R6.14); `docs/derivations/scripts/t07_reference_c2.json` (sha256 `23b924b84e72e15c03843228fefeeb856a9d571ca341747712a519de9b947319`); `t07_reference.json` frozen at `cba24a92…` |
| Evidence | `v17-c1` records `32d48d2` (19/30; the zero gates met); failure analysis `docs/t07-v17-c1-failure-analysis.md` (`9165894`); R6's measurements; GC-16; preflight P1–P8 at `c7bbc98`; `v17-c2` records `3150381` (`campaign.json` sha256 `3998dc6764ea6d59e17d497e897b58232941103c9038758255f417fa754b93d0`); `scripts/t07_evidence_manifest.py` (G17 on c2, T07.G17-c1 reported) |
| Affected packages | T07 (W7a harness, W7b scorer, W7c reference, W7d `v17-c2`, W8c manifest); T08 (V17 release text) |

**Decision.**
- **Two campaigns, judged separately.** `v17-c1` stays recorded as failed and is not re-judged. `v17-c2` is a new campaign: `claude-sonnet-5`, effort `high`, k = 3, 30 runs, `v17-c1`'s fixed order, no re-runs. G17 is judged on `v17-c2` alone, never pooled. The verdict reports both, and any claim cites both.
- **R6's corrections.** T08 requires reading the revision and reporting the knock-out drum (T08-C5), so its payloads lie in the task's path. §8 requires operator identity isolation (R-116). The duty pin's solvability must be shown on the agent's surface (G16-h).
- **Deliberately unchanged.** The footer, T09 and T10 (a clarification would remove exactly the errors `v17-c1` recorded); T05's fixture.
- **Preconditions.** `v17-c2` starts only after P1–P8, P1 being Frank's approval; P3 attested by the build lane after the review-2 re-check.

**Rejected alternatives, and why.** Pooling the two (they measure two systems, and T08 changed). Best of two, or re-drawing `v17-c1`'s failed runs (selection on outcome, R-089). Clarifying T09's "jobs you ran" or the footer's status for mixed requests. A duty-pin example in T05's fixture (would mask B2 and test copying). Leaving T08 as it was. Re-scoring `v17-c1` under R6 (a criterion applied after the outcome, R-087). One reference file for both campaigns (would change the bytes `v17-c1` was scored against).

**Watch for.** `v17-c2` cited without `v17-c1`; a third campaign without a new amendment and Frank's approval; `t07_reference.json` edited (GC-16 refuses); the footer, T09 or T10 "clarified"; an unexposed payload reported as resisted; a `v17-c2` run re-drawn; the operator address written to a committed file by the harness.

---

## R-116 — The operator's e-mail address is kept out of agent sessions from `v17-c2` on, and redacted in `v17-c1`'s committed transcripts; `v17-c2` authenticates with a dedicated setup-token

| | |
| --- | --- |
| Date | 2026-09-27 (the setup-token 2026-09-28) |
| Decided by | **Frank, 2026-09-27** ("E-mail: redact going forward", overriding the `specifier`'s keep-unedited default) and **2026-09-28** (a dedicated `claude setup-token`, which he created); the mechanism by the build lane (rf3b) |
| Normative text | V17 spec Amendment R6, R6.6 (§8 operator identity), CAMP-04 and R6.1 as amended; `benchmarks/t07/v17/runs/v17-c1.REDACTION.md` |
| Evidence | the `v17-c1` failure analysis (the address in 12 committed transcripts); canaries CAN-ii-e and its control (`runs/canary/`, probe shows none, control shows the address); redaction commit `15d7c2f` (54 occurrences in 12 transcripts; counts and verdicts unchanged, 19/30); `v17-c1.SHA256SUMS` (originals), `v17-c1.REDACTED.SHA256SUMS`, `v17-c1.SCORES-v1.SHA256SUMS`; every `v17-c2` run scanned |
| Affected packages | T07 (harness, scorer, preflight); every later agent campaign |

**Decision.**
- **Isolation.** Each agent session gets an empty per-session `CLAUDE_CONFIG_DIR` and `CLAUDE_CODE_OAUTH_TOKEN` read at run time from a token file. For `v17-c2` that file is Frank's dedicated setup-token (`--oauth-token-file`, mode 600, never copied into the repository or logs, never read out by the build lane). Every run is scanned for the address.
- **Redaction.** The address is replaced by `<redacted-account-email>` in `v17-c1`'s 12 transcripts, in a new commit. Only transcript digests move (`scores.json` of those runs, `campaign.json`); `run.json` keeps the original digests; `v17-c1.SHA256SUMS` keeps the originals' sums; git history is not rewritten.

**Rejected alternatives, and why.** Keeping `v17-c1` unedited (the `specifier`'s default; overridden by Frank). Rewriting git history. `ANTHROPIC_UNIX_SOCKET` (needs an auth proxy). A separately billed API key (R6-U1). Reading the login's OAuth access token from the credentials store (works, but reads the store and may expire within a campaign).

**Watch for.** The token file's content in a log, a record or the repository; a session run without the isolation; the redaction "re-done" on a later campaign by editing the record rather than isolating the session.

---

## Decisions recorded outside an ADR

| Entry | Decision | Where | Date |
| --- | --- | --- | --- |
| R-002 | A session runs on Opus 5 with Fable 5.1 participating as design and review subagents, rather than Fable driving a session. Fable still owns the scientific decisions and the separate review; the branch and the evidence manifest are owned by the Opus session. A change to who drives a session, not to the architecture or any scientific requirement. Decided by Frank; recorded, not decided by an agent. | `docs/progress.md`, "Working-protocol change, 2026-09-10" | 2026-09-10 |

---

## R-117 — v0.1 is tagged only on a release candidate whose every gate has a verdict; a FAIL is released only by named clause with Frank's acceptance

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | design lane (`specifier`), 2026-09-29; build lane registered |
| Normative text | ADR 0021 D1–D2; T08 spec §3.3, §8. |
| Evidence | T08 spec §16 |
| Affected packages | T08 |

**Decision.** A release candidate is the commit of §8.1; each gate is judged there (PASS/FAIL/BLOCKED); `BLOCKED` blocks the tag; a FAIL clause may be released only if ADR 0021 D3 lists it with Frank's acceptance, and then it is printed FAIL everywhere.

**Rejected alternatives, and why.** Tagging on package-level passes without an RC re-run (earlier passes describe earlier commits); a "PASS with waiver" status (a reworded FAIL).

**Watch for.** A gate report that prints a released FAIL as PASS; a tag whose code trees differ from the RC's.

---

## R-118 — V14's qualified-PTC clause is judged by T04 §8.1's criterion unchanged, plus selectability on a supported flowsheet; it is FAIL on existing evidence

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | design lane (`specifier`), 2026-09-29; build lane registered |
| Normative text | T08 spec §4.4; ADR 0021 D3. |
| Evidence | T08 spec §16 |
| Affected packages | T08 |

**Decision.** Qualification needs T04 §8.1's criterion on a case registered before its PTC results, and a family selectable by a registered policy on a flowsheet inside the envelope.

**Rejected alternatives, and why.** Reading blueprint §7.5 route (a) alone as sufficient after the comparison came out equal (a criterion changed after the result); qualifying on PTC-R1 run as a bare residual (not a capability any supported flowsheet can select); removing the clause from v0.1.

**Watch for.** A later "route (a) suffices" argument without a new, pre-result registration.

---

## R-119 — V13 is judged by blueprint §14.3 bullet 3, including warm starts across runs; K02's warm-start cache does not satisfy it

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | design lane (`specifier`), 2026-09-29; build lane registered |
| Normative text | T08 spec §4.3; FD1. |
| Evidence | T08 spec §16 |
| Affected packages | T08 |

**Decision.** Where a plan §5.1 row omits a clause of its §14.3 bullet, the blueprint clause counts; §14.3's "warm starts" are §7.4's compatible warm starts.

**Rejected alternatives, and why.** The plan's shorter text as the criterion (the plan summarises the blueprint and does not override it); K02's §6.4 property-level cache as the warm start (a different mechanism).

**Watch for.** V13 closed by citing the property cache.

---

## R-120 — v0.2 real chemistry (pending Frank): recommended the ammonia synthesis loop on the group's PyMRM model; runner-up the methanol loop

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | Frank, 2026-09-29 (F3: the ammonia loop), on the `specifier`'s recommendation |
| Normative text | ADR 0022 (Proposed); T08 spec §7. |
| Evidence | T08 spec §16 |
| Affected packages | T08, v0.2 / M01 |

**Decision (proposed).** The rubric of §7.2, preregistered before measurement; C1 first on S1/S5/S6 and a necessary nonideal route.

**Rejected alternatives, and why.** C2 as first (independent cases exist but reference neither kinetics nor the nonideal route; no group model); C3 (no native recycle; the IDAES case has no selectivity); C4, C5 (a nonideal route not clearly needed; little PyMRM value).

**Watch for.** A selection made without H5's rights statements; the ranking recomputed with changed anchors rather than changed facts.

---

## R-121 — Release evidence is re-measured at the RC; T08 adds no tolerance; the lock is not edited in T08

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | design lane (`specifier`), 2026-09-29; build lane registered |
| Normative text | T08 spec §3.3, §8.1 (1), FD4. |
| Evidence | T08 spec §16 |
| Affected packages | T08 |

**Decision.** Every gate is judged at the RC through the RC job; float comparisons reuse registered tolerances; `requirements.lock` stays `ead4edf1…`, and "the audited bytes are the installed bytes" (ADR 0006 Q4) is enforced by comparing installed CasADi files with the audited per-file hashes in the clean-install job.

**Rejected alternatives, and why.** Citing T06's and T07's campaign passes without a re-run at the RC; adding hashes to the lock (changes the lock hash and demotes every registered bundle to `inspected_archived_results`).

**Watch for.** A lock edit bundled into an unrelated change.

---

## R-122 — D1 blocks V20's invalid-structure clause; D2, D3, the typed-ends sweep, A89 and the record fields block the RC, not a gate verdict; M06's contract asks are v0.2 backlog behind ADR 0019 amendments

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | design lane (`specifier`), 2026-09-29; build lane registered |
| Normative text | T08 spec §6. |
| Evidence | T08 spec §16 |
| Affected packages | T08 |

**Decision.** As the table of §6.1; D2/D3 identity moves only by proven substitution with Frank's approval (F4). Frank approved the substitution-only `t07` move (F4) on 2026-09-29.

**Rejected alternatives, and why.** Classifying D2/D3 as V18/V20 failures (the registered assertions never reached these paths, and the verdicts on them stand); deferring D2/D3 to v0.2 (a release whose failure bundles carry empty replay identity breaks blueprint §8.2).

**Watch for.** An identity key moved by more than the named fields.

---

## R-123 — PTC-R1 runs on a vapour-phase kinetic CSTR, exactly, and T04 §8.4's open points are resolved before any result

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | design lane (`specifier`), 2026-09-29; build lane registered |
| Normative text | T08 build-first spec Part A; ADR 0023. |
| Evidence | T08 build-first spec §J |
| Affected packages | T08, T04, T05 |

**Decision.** PTC-R1 runs on a vapour-phase kinetic CSTR (`B → A`, `Δh_r = Σ ν_i L_i`, the `γ → ∞` synthetic law, a Damköhler pin and a coolant capacity rate), which maps exactly onto PTC-R1. The registered root is either stable steady state. "Reaches" means `CONVERGED` within 2e-3. The arms are T06-revision-v2 with only `eo_core` set and recovery off. The saddle clause covers all 441 starts. Both platforms must pass. PTC is offered as `T08-ptc-v1` by explicit policy.

**Rejected alternatives, and why.** Synthetic liquid formation data (it moves every identity, per ADR 0011); new quantity kinds (they move T08.A49); an owned extent variable (the discrete iteration would no longer be PTC-R1's); "any root" (incoherent with the saddle clause); the per-root reading (it scores divergent successes as improvements); `newton_refined` as a separate comparator (it cannot change a class).

**Watch for.** Any re-reading of §A4 after `C_res`; a PTC-R1 result committed before `C_case`; the comparison policies edited after `C_case`.

---

## R-124 — Compatible warm starts are opted into by policy, chosen from the lineage's latest VERIFIED state, checked like every candidate, and recorded inside the bundle; the contract is unchanged

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | design lane (`specifier`), 2026-09-29; build lane registered |
| Normative text | T08 build-first spec Part B; ADR 0024. |
| Evidence | T08 build-first spec §J |
| Affected packages | T08, K03, T07 |

**Decision.** `T08-warm-v1` sets `initializer_chain = (compatible_warm_start, traversal-G0-v1)`. Selection is `store-latest-verified-lineage-v1`, and compatibility is id-set identity. The checks are integrity, compatibility, bounds (projection), evaluation and opening, and a failure is a typed rejection with the next source. The record is `solve-path.json`'s `warm_start`, and a rerun uses it with no lookup.

**Rejected alternatives, and why.** A `solve_body` field in v0.1 (it changes the MCP surface and ADR 0019); a new artifact file (a new MCP-exposed kind); content-addressing the source outside the bundle (a bundle must replay alone); a fallback after acceptance (a new recovery edge); K02's warm-start cache (R-119).

**Watch for.** The lookup run during a rerun; a warm start that overwrites a specification; the member written under a policy that does not name the source.

---

## R-125 — ADR 0021 D3 is emptied by Frank's F1/F2; a built clause that fails at the RC returns to Frank

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | Frank, 2026-09-29 (F1, F2: build first; "the defaults are good") |
| Normative text | ADR 0021 proposed revision 1. |
| Evidence | T08 build-first spec §J |
| Affected packages | T08 |

**Decision.** V13 (e) and V14 (b) are built in T08 and judged at the RC. A FAIL there is carried only if Frank accepts it under D2.3, and otherwise no tag is proposed.

**Rejected alternatives, and why.** Keeping D3's pre-answer rows (they no longer reflect Frank's decision); pre-accepting a FAIL (that would be the waiver ADR 0021 rejected).

**Watch for.** A tag proposed with V14 (b) FAIL and no recorded acceptance.

---

## R-126 — PTC-R1 binds on `(A, B, C)` with C an inert `2⁻¹⁰` mol/s trace taken from A; a registered case never carries a free component at exactly zero

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | design lane (`specifier`), 2026-09-29; build lane registered |
| Normative text | T08 build-first spec Amendment 1 §Am1.1; ADR 0023 Amendment 1 (D2, D5). |
| Evidence | T08 build-first spec §Am1.1 (measured directions at §A5's six states), §Am1.J |
| Affected packages | T08, T04 |

**Decision.** The realization's feed is `(0.4990234375, 0.5, 0.0009765625)` mol/s with `ν_C = 0`. `n_tot = 1`, and every identity and the dimensionless case are unchanged. The starts' digest is `0262bebc…`, and the git order is `C_reg → C_A1 → C_case → C_res`.

**Rejected alternatives, and why.** C at exactly zero (measured: roundoff of either sign on the bound makes 8 of 9 PTC steps `bound_blocked`, and drift truncates both arms); a PTC-core release (a numerics change on T04's path, H-A1-1); C fed with `n_tot ≠ 1` (not exact in binary64); widening `canonical_components` (R-076).

**Watch for.** The trace "simplified" back to zero; a C column named as a blocker in any comparison run; the trace changed after `C_case`.

---

## R-127 — Build-first Amendment 1's other rulings: B17 follows the frozen status enum; the carried V17 surface is scored against a third reference; a warm opening is §6.2's projection; plans are compared modulo the policy; the initializer bundle names its plan

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | design lane (`specifier`), 2026-09-29, under Frank's F5 (2026-09-29); build lane registered |
| Normative text | T08 build-first spec Amendment 1 §Am1.2–§Am1.6; T07 V17 spec Amendment T08-1; T07 design, amendment to ruling round 3 Q1 item 3. |
| Evidence | T08 build-first spec §Am1.J |
| Affected packages | T08, T07 |

**Decision.** B17: EO rows `invalid_trial_state` with the domain message, and `evaluate` `out_of_domain`. `t07_reference_t08.json` is v17-c2's document with only the offered set changed, used by G16-b from T08 on; v17-c1 and v17-c2 are not re-scored. B41 compares with a `user_start` opening, and B42 compares plans under N. The initializer failure bundle's `replay_identity` carries the plan's four ids.

**Rejected alternatives, and why.** A new status value (the enum is frozen); editing `OFFERED_POLICIES` in place (moves the frozen c1 bytes and c2's registered sha); an unlisted offered policy (a contract that hides what it serves); an oracle read from `get_project` (the thing tested); exempting warm starts from §6.2 (a numerics change on the registered path); comparing `plan_id` verbatim (false by construction); keeping empty identity strings (an empty string reads as a value).

**Watch for.** `t07_reference_c2.json` regenerated with T08's set; a V17 verdict that cites G16-b without naming the reference it was scored against; a region opened from a warm start without §6.2's lift.

---

---

## R-128 — Build-first Amendment 2: PTC-R1's arms keep `T06-revision-v2`'s 10 000 property budget, which cannot bind; a budget exhaustion or a second attempt blocks the verdict; B21's C-trace tolerance is 1e-10 and the YAML's 1e-12 is an erratum

| | |
| --- | --- |
| Date | 2026-09-29 |
| Decided by | design lane (`reviewer`), `docs/reviews/T08-review.md` §3.1–§3.2, 2026-09-29; build lane transcribed and registered |
| Normative text | T08 build-first spec Amendment 2 §Am2.1–§Am2.3 |
| Evidence | `docs/reviews/T08-review.md` §3.1 (the bound: ≤ one attempt per run, one PTC attempt ≈ 5 200 property calls plus mass evaluations, one Newton attempt ≤ 2 300), §3.2, S2, S5, S6 |
| Affected packages | T08 |

**Decision.** The arm definition governs: each arm is `T06-revision-v2` with `eo_core` set and `eo_recovery = "none"`, so its property budget is `T06-revision-v2`'s 10 000, which cannot bind on PTC-R1; §A4.1's "no property budget" is amended to say so. B21 adds: no run ends `BUDGET_EXHAUSTED` with `budget = property_calls`, and every run opens exactly one attempt; either is a defect that blocks the verdict (`BLOCKED`), never a `FAIL` class. B21's C-trace tolerance is 1e-10 mol/s; the YAML's `criterion.trace_component` 1e-12 is a generator transcription error, superseded, and the generator is corrected after `C_res`. No re-registration: `case.json`, the arms, the starts and the YAML are unchanged.

**Rejected alternatives, and why.** Lifting the cap in the arms (changes both `policy_sha256` values, and the arms would no longer be `T06-revision-v2` with only the core changed); regenerating the YAML before `C_res` (its sha256 is in `case.json`, so `--run` would refuse and a new registration would follow for no gain).

**Watch for.** A `BUDGET_EXHAUSTED` run scored as a `FAIL` class; the YAML or generator regenerated before `C_res`; a verdict that judges the C trace at 1e-12.

---

## R-129 — U05 is a rule-5 defect, fixed in code: `validate(task="optimization")` ends typed `unsupported`; `READY_FOR_OPTIMIZATION` is never returned

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`reviewer`), `docs/reviews/T08-review-2.md` Ruling 1, 2026-10-01; build lane transcribed and registered |
| Normative text | T08 release spec §5.3 row U05 (amended 2026-10-01, review 2 Ruling 1) |
| Evidence | `tests/test_t08_w2_unsupported.py::test_u05_validate_for_optimization_is_unsupported`; `doc:docs/blueprint-v3.1.md` (the `READY_FOR_OPTIMIZATION` definition) |
| Affected packages | T08 |

**Decision.** `LocalApplication.validate`, immediately after the `task not in TASKS` check, refuses `task == "optimization"`: `self._refuse("unsupported", "task_unsupported(optimization)", operation="validate", pointer="/task")`. `validation.validate(..., task="optimization")` raises the same refusal and builds no report. The enum value `READY_FOR_OPTIMIZATION` stays in the frozen schema, unused. Earlier tests that asserted `READY_FOR_OPTIMIZATION` are changed and listed in the manifest as moved.

**Rejected alternatives, and why.** Amend U05 to accept a structure-only `READY_FOR_OPTIMIZATION`: that contradicts the blueprint's definition, and it is a ready status that no operation can consume.

**Watch for.** Earlier tests reasserting `READY_FOR_OPTIMIZATION` from `validate(task="optimization")`; a new operation returning it without an optimizer behind it.

---

## R-130 — Recovery-edge evidence: `identity_compared`, `verified_certificate` and `guard` all count, each under a stated condition; `library-only` joins the `enabled` values

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`reviewer`), `docs/reviews/T08-review-2.md` Ruling 6, 2026-10-01; build lane transcribed and registered |
| Normative text | T08 release spec §5.6 (amended 2026-10-01, review 2 Ruling 6); §9 row T08.A33 (amended) |
| Evidence | `verify/certificate.py:402–440` (the bound-declaration guard); `tests/test_t07_r7_admission.py` (`legacy_admission` C0–C5); `tests/test_t03_contract.py::test_a16_an_incompatible_opening_is_refused_and_opens_nothing[identity-constants_sha256]` (E4) |
| Affected packages | T08 |

**Decision.** `enabled` widens to `{default, policy-only, library-only, absent}`; `library-only` means no application-offered policy and no `MODEL_BUILDERS` unit reaches the edge, pinned by a test that fails when one does, and such a row meets every clause an enabled row meets. Evidence is one of three kinds: **(i) `identity_compared`** — a test compares the edge's instance with the failed or target one in `model_version`, `constants_sha256` and specifications, or, for an edge acting inside one call on a caller-owned problem, shows every evaluation before and after the edge made on the same problem object with equal pinned values; **(ii) `verified_certificate`** — a test in which the edge demonstrably fires ends `VERIFIED` against the bound revision, showing the reported state is a root of the unchanged problem, not that every intermediate instance was unchanged; **(iii) `guard`** — the edge's path passes an identity guard before the new instance is used, and a test injects a change of each field the row claims and sees it refused. A cross-binder fallback is held to the problem, not to `model_version`: its guard is `legacy_admission`'s C0–C5.

**Rejected alternatives, and why.** Only `identity_compared`: the certificate's guard (`verify/certificate.py:402–440`) refuses a final solve whose `model_version` or `constants_sha256` differs from the bound declaration, or whose revision differs, and its checks then evaluate the original rows — so a `VERIFIED` outcome is a root of the unchanged problem, which is the property the principle protects; restricting to one evidence kind would have refused this.

**Watch for.** A cross-binder fallback checked against `model_version` instead of the problem; a `library-only` row whose unreachability test is weakened or deleted; a `verified_certificate` row cited without the edge's label or provenance asserted to have fired.

---

## R-131 — CLI `replay --rerun` follows `reproduce_bundle`; the SYN-001-nominal fallback is removed, reversing T07 D-Q6 for the CLI

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`reviewer`), `docs/reviews/T08-review-2.md` Ruling 11, 2026-10-01; build lane transcribed and registered |
| Normative text | T08 release spec §9 row T08.A17 (new, review 2 Ruling 11) |
| Evidence | `tests/test_t08_w2_cli_rerun.py::test_a17_a_revision_built_bundle_reruns_its_recorded_route`; `tests/test_t08_w2_cli_rerun.py::test_a17_an_unregistered_k05_bundle_is_not_rerun` |
| Affected packages | T08, T07 |

**Decision.** "CLI `replay --rerun` follows `reproduce_bundle`; the fallback to SYN-001-nominal is removed. Rejected: keeping it (T07 design note §12.3, §17 D-Q6), because it compares an unknown or revision-built run with another problem's rerun. Decided by design lane, T08 review 2, 2026-10-01." (Ruling 11's exact register text.) `command_replay` with `--rerun` calls `reproduce_bundle(directory, rerun=True, rerun_directory=<a temporary directory>, run_id="replay")` and prints that report's fields; exit 0 iff the verdict is `MATCH`, or `NOT_RUN` when `--rerun` was not given. An unknown non-revision run id ends `NOT_RUN` with reason `rerun_unsupported(no_revision_document)`, exit 1.

**Rejected alternatives, and why.** Register a limitation instead of fixing it: a verdict about a different problem is a wrong typed result (rule 5), and here it hits every revision-built bundle, because the CLI never read `revision.json` and job ids are not registered cases.

**Watch for.** The SYN-001-nominal fallback reintroduced into the CLI path; `replay --rerun` on a revision-built bundle compared against a different problem's rerun; `application/revision_run.py`'s own `reproduce_bundle` diverging from the CLI's call of it.

---

## R-132 — The design-lane text review of the 17 MCP tool descriptions blocks the RC; it is not a limitation, and T08.A18 stays red until it is recorded

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`reviewer`), `docs/reviews/T08-review-2.md` Ruling 13, 2026-10-01; build lane transcribed and registered |
| Normative text | T08 release spec §9 row T08.A18 (new, review 2 Ruling 13); §8.1 item 2 (amended) |
| Evidence | `tests/test_t08_w2_description_reviews.py::test_every_description_is_reviewed_by_both_lanes`; `src/process_runtime/application/bindings/descriptions/REVIEW.json` |
| Affected packages | T08, T07 |

**Decision.** The design-lane `reviewer` does one short pass of its own over the 17 texts at their recorded hashes and records `reviewed` or `changes_requested` per operation in `REVIEW.json`. A changed text voids Frank's human review of that text, and he re-reviews it. T08.A18 asserts, for each of the 17 operations, both reviews (`design-lane`, `human`) are `reviewed`, with `reviewed_by` and `reviewed_at` set, at the recorded hash, which equals the served text's; the node stays red until the review is recorded (no xfail). Harvest T07 `limitations[2]` and `[3]` are S → that node. §8.1 item 2 now lists T08.A18 among the RC blockers, alongside U05 (T08.A22's U05 node) and the CLI rerun (T08.A17).

**Rejected alternatives, and why.** A limitation row: T07 §11.3 made both reviews conditions, and an unreviewed agent-facing text is a process gap, not a user-facing property.

**Watch for.** T08.A18 marked `xfail` or skipped instead of staying red; a description text changed after a `reviewed` record without Frank's re-review; an RC declared with `REVIEW.json` still `pending_design_review`.

---

## R-133 — V17 is carried across U05 and the description review's two fixes, with the surface change recorded; no new campaign

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | Frank Peters, 2026-10-01, on the design lane's recommendation (`docs/reviews/T08-description-review.md`, "V17"); build lane registered |
| Normative text | T08 release spec §2 row V17 and §9 row T08.A49; build-first spec §9 row T08.B50 (criteria unchanged; this entry records the departure from their descriptions digest) |
| Evidence | `tests/test_t08_w2_surface_digest.py`; `docs/reviews/T08-description-review.md` (N1, N2; the V17 transcript grep); `src/process_runtime/application/bindings/descriptions/REVIEW.json` |
| Affected packages | T08, T07 |

**Decision.** V17 (`v17-c2`, 25 of 30) is carried to T08's RC across two changes to the agent surface: U05 (R-129), which made `validate(task="optimization")` a typed `unsupported` refusal, a change of behaviour on an existing MCP tool path outside F5's "content only"; and the review's N1 (`validate.md`'s first paragraph) and N2 (`commit_change.md`'s "A committed result carries …"), which make the texts match the code. The served descriptions' digest moves from `v17-c2`'s `6d13e13d660521c1a39dc245d5237c974a4273b0c3eeadb02d44538ba2669a4d` to `171dd768efcfb24f65d79d83a4f157dcfd1436935bf5106a247b84f3040e4d14`. The old digest stays registered as `v17-c2`'s (`benchmarks/t08/reference_values.yaml`, `t08_reference.py`, the c1/c2 run records: historical, unchanged); the new one is registered beside it by a test that shows the served files differ from `v17-c2`'s in exactly `validate.md` and `commit_change.md` and that serving `v17-c2`'s two texts in their place reproduces `6d13e13d…`. The basis: no V17 campaign agent issued `task: "optimization"` or mentioned optimization (the review's grep of `v17-c1` and `v17-c2`), so both changes remove false statements on paths no campaign agent used; N2's sentence concerns `conflict`/`rejected` results, which carried explicit nulls, and the agents handled 6 and 3 of them. Frank's human review of the two changed texts lapses; he re-reviews them (T08.A18 red on those two until then).

**Rejected alternatives, and why.** A new V17 campaign on the T08 surface (F5's alternative, about USD 10 of subscription time and an hour): the changes touch only a path no campaign agent used and the wording of a result's null members, so a campaign would measure nothing the carry does not already cover.

**Watch for.** T08.A49/B50 read as passing on `6d13e13d…` at the RC without this entry; another description or schema change carried under this entry (it covers U05, N1 and N2 only — a further change of the surface is a new decision); `v17_c2_tool_descriptions_sha256` re-baselined to the new digest; the carry described as covering agent behaviour on the changed `validate` path, which no agent exercised.

## R-134 — T08.B50's descriptions digest is the surface R-133 carries (`171dd768…`), by Frank's decision

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | **Frank, 2026-10-01** ("Amend B50"), answering the V13 (e) verdict; recorded by the build lane |
| Normative text | `docs/derivations/T08-build-first-spec.md` Amendment 3 |
| Evidence | `docs/reviews/T08-verdict-V13e.md` (B40–B49 MET; B50 NOT MET only on the digest clause); `tests/test_t08_w2_surface_digest.py`; `docs/reviews/T08-description-review.md` N1, N2 |
| Affected packages | T08 |

**Decision.** B50 requires the descriptions digest `171dd768…` (the 2026-10-01 surface), which differs from v17-c2's `6d13e13d…` in exactly `validate.md` and `commit_change.md`; its other clauses are unchanged. The same day Frank re-reviewed both changed descriptions (human review recorded in `REVIEW.json`, 2026-10-01).

**Rejected alternatives, and why.** Leaving B50 failing and carrying V13 (e) as FAIL to the tag (the failure is the surface change Frank already accepted in R-133, not a warm-start defect). Reading B50 as met on the old digest without an amendment (a criterion re-read after the result).

**Watch for.** A later description change made without moving B50 and R-133 together; the old digest cited as the current surface.

---

## R-135 — numpy's and scipy's GCC runtime library (GPL-3.0 with the GCC Runtime Library Exception) is outside blueprint §15's GPL line; Q1's "LGPL allowed" covers LGPL-2.1

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | **Frank, 2026-10-01** ("Allowed"; "Yes, covers it"), answering the T08.A30 licence finding; recorded by the build lane |
| Normative text | ADR 0006 Amendment 1 (D7) |
| Evidence | `docs/t08-a30/t08-a30-x86_64.json` (A30 inventory: `libgfortran` ×3 in the required closure, two loaded; `libquadmath` LGPL-2.1-or-later); `docs/T08_DECISIONS.md` 2026-10-01 |
| Affected packages | T08 (A30), every later release's [A10] refresh |

**Decision.** `libgfortran` vendored by numpy and scipy, under GPL-3.0 with the GCC Runtime Library Exception, is dispositioned by ADR 0006 Amendment 1: the exception puts it outside §15's "no GPL-licensed components", and in mode A the project redistributes none of its bytes. ADR 0006 Q1's answer extends to LGPL-2.1-or-later (`libquadmath`).

**Rejected alternatives, and why.** Reading §15 as excluding it (would exclude numpy and scipy, on which the whole solver rests, for a library whose exception exists for exactly this use). Leaving A30 red pending outside advice (Frank chose to rule).

**Watch for.** A GPL-family object without such an exception at a pin change; a mode-B/C artifact shipped without these objects' notices.

---

## R-136 — T08.A45 is the bundle set the RC writes (K05's 5 variants, T07 G8's `ELIGIBLE`); T06 A34 is carried to the RC in its registered same-class form by T08.A46

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`specifier`), T08 release spec Amendment R3 1; build lane registered |
| Normative text | T08 release spec §9 rows T08.A45 and T08.A46, §8.2 step 6 (amended 2026-10-01, Amendment R3 1) |
| Evidence | `scripts/t08_rc.py` (`bundles-write`, `bundles-replay`'s per-set counts, `ensemble`'s `a46.t06_a34_same_class_replay`); `tests/test_t08_w4_rc.py` |
| Affected packages | T08, T06 |

**Decision.** "K05's registered SYN-001 runs" are the 5 `variants` of `benchmarks/syn001/reference_values.yaml`, each written by the CLI's `solve <case_id>`; "T07 G8's revision bundles" are `ELIGIBLE` of `tests/test_t07_w3a_revision_runs.py` under `default` (47 at `69e8e03`; the RC enumerates, it does not hard-code). T06 A34 leaves A45: it is a record replay on the same machine class that writes no bundle, and per-start outcomes are not promised across architectures (L07; ADR 0007 F1). T08.A46 carries it in its registered form: on each class, the RC run's first start of every case and every retained failure, replayed on the same class, `MATCH` on every field.

**Rejected alternatives, and why.** Bundles for T06's starts with a cross-architecture `MATCH` required (asserts what L07 disclaims); leaving A45 failing on a document defect (a defect is amended, not carried).

**Watch for.** A cross-class replay of ensemble starts asserted anywhere; G8's count hard-coded instead of enumerated.

---

## R-137 — T08.A49's descriptions digest is R-133's carried surface `171dd768…`, bound to the N1/N2 decomposition

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`specifier`), consistent with Frank's R-133 and R-134 (T08 release spec Amendment R3 2); build lane registered |
| Normative text | T08 release spec §3.2 (new row), §4.7, §9 row T08.A49 (amended 2026-10-01, Amendment R3 2) |
| Evidence | `tests/test_t08_w2_surface_digest.py`; `scripts/t08_rc.py` `surface` (`a49.descriptions_digest_r133`, `a49.schemas_and_other_texts_are_v17_c2s`) |
| Affected packages | T08, T07 |

**Decision.** A49 requires `171dd768…`, the surface R-133 carries, and in addition the decomposition — serving `v17-c2`'s `validate.md` and `commit_change.md` in place of the served two reproduces `6d13e13d…` — so the carry stays bound to exactly N1 and N2. `6d13e13d…` stays registered as `v17-c2`'s (historical). Amendment 1's "the descriptions digest `6d13e13d…` … unchanged as criteria" is superseded for the digest; its G16-b clause is carried into A49's row.

**Rejected alternatives, and why.** A49 left on `6d13e13d…` (fails at `C` on a change Frank accepted); reading it met without amendment (a criterion re-read after the result — R-134's rejected alternative).

**Watch for.** A further description change carried under R-133.

---

## R-138 — The verdict document has one five-column verdict table; the gate script reads clauses and limitation ids by column only

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`specifier`), T08 release spec Amendment R3 3; build lane registered |
| Normative text | T08 release spec Amendment R3 §R3.3; §9 rows T08.A03 and T08.A50 (amended 2026-10-01) |
| Evidence | `scripts/v0_1_gate.py` (`verdict_rows`); `tests/test_t08_w4_v0_1_gate.py` (one case per departure from the form) |
| Affected packages | T08 |

**Decision.** `docs/reviews/T08-verdicts.md` carries exactly one table with a `Verdict` header: `Gate | Verdict | Failing clauses | Travelling limitations | Basis`, ten rows `V11` … `V20` in order, gate ids bare. `Failing clauses` holds a FAIL's clauses as `Vnn (x)`, a BLOCKED's as `Vnn (x): <missing input>`, a PASS's `—`; `Travelling limitations` holds envelope `limitations` ids or `—`; `Basis` holds no clause and no envelope id. `scripts/v0_1_gate.py` reads clauses only from `Failing clauses` and ids only from `Travelling limitations`; a clause or envelope id in another cell, a PASS with a failing-clause entry, a missing or reordered column, a gate out of order, or an unknown id is an error, exit ≠ 0.

**Rejected alternatives, and why.** Reading ids anywhere in a row (a FAIL whose basis cites a met clause would be refused as unaccepted, and an id cited as not applicable would travel); free prose (not checkable).

**Watch for.** A clause id or envelope id in `Basis`; a bold gate id.

---

## R-139 — ADR 0021 D2.4 compares every input of the sdist and wheel — `src/`, `schemas/`, `benchmarks/`, `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE` — allowing only the version value in `pyproject.toml` and `__init__.py`

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`specifier`), T08 release spec Amendment R3 4; build lane registered |
| Normative text | ADR 0021 proposed revision 2 (D2.4); T08 release spec §8.3, §9 row T08.A50 (amended 2026-10-01, Amendment R3 4) |
| Evidence | `scripts/v0_1_gate.py` (`TREES`, `tree_differences`); `tests/test_t08_w4_v0_1_gate.py::test_the_tree_check_allows_the_version_string_only`, `::test_the_tree_list_is_adr_0021_d2_4_revision_2` |
| Affected packages | T08 |

**Decision.** `pyproject.toml` is in the check (its pins are what the wheel requires); in it and in `src/process_runtime/__init__.py` the only allowed difference is one occurrence of the version value (`0.1.0rc1` → the tag's). Every other input of the sdist or wheel is in the check with no difference allowed. Everything else may differ (`CHANGELOG.md`, `docs/`, `evidence/`, `tests/`, including the fixtures carrying the version). A change to a checked path after `C` makes a new RC (`0.1.0rc2`), not a tag.

**Rejected alternatives, and why.** The three trees and the lock only (a changed notice, README or packaging rule would reach the released artifacts untested by T08.A31/A43); comparing rebuilt artifacts byte for byte (needs a build at the tag and a version-normalizing diff, for no more coverage than the source list).

**Watch for.** A README or notice edit between the RC and the tag without a new RC.

---

## R-140 — v0.1 ships no lock in the wheel; an installed package's bundles replay `NOT_RUN` (L41); the lock lookup is confined to the source checkout

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`specifier`), T08 release spec Amendment R3 5; build lane registered |
| Normative text | T08 release spec §5.5 row L41, §6.3 B12, §8.1 item 4, §8.2 step 4, §9 row T08.A19 (Amendment R3 5); ADR 0007 D4 (not amended) |
| Evidence | `src/process_runtime/run/manifest.py` (`_checkout_lock`); `tests/test_t08_r3_a19_lock_lookup.py`; `scripts/t08_rc.py lock-check` (clean-install CI job); `benchmarks/t08/support_envelope.yaml` L41 |
| Affected packages | T08, K05 (replay identity) |

**Decision.** A registered limitation for v0.1 (L41), no lock hash in the wheel, ADR 0007 not amended: an empty lock hash on either side is `inspected_archived_results` / `NOT_RUN`, with the reason named (ADR 0007 D4). The defect found while ruling — `_repository_lock` walked every parent directory of the module, so an installed package beneath any unrelated `requirements.lock` recorded that file's hash — is fixed: the lookup is confined to the source checkout the module lives in (the directory holding `pyproject.toml` with `[project].name = "process-runtime"` and `src/process_runtime/`); anywhere else `lock_sha256` is `""`. T08.A19 pins the three states. Backlog B12 holds the verified alternative.

**Rejected alternatives, and why.** Packaging the lock or its hash: it would attest an environment nothing checked (`pyproject.toml` pins five direct dependencies; the transitive ones float), opening a false `exact_replay`; making it honest needs a per-distribution check at manifest time, an identity-bearing change at the RC (B12, an ADR 0007 amendment).

**Watch for.** `lock_sha256` read from any file outside the checkout; B12 implemented without an ADR 0007 amendment.

---

## R-141 — T06 A89 asserts its outcome on every class and its refinement count only on the `ref-x86-64` CPU model

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`specifier`), T08 release spec Amendment R3 6 and T06 spec Amendment T08-1, on T08.A15's 21 of 21; build lane registered |
| Normative text | `docs/derivations/T06-corpus-spec.md` Amendment T08-1 (A89) |
| Evidence | `benchmarks/t08/a89/ci-aarch64.json`, `ref-x86-64.json` (T08.A15); `tests/test_t06_w18_policy.py::test_a89_thm09_ends_within_a_tenth_of_s3s_allowance` |
| Affected packages | T06, T08 |

**Decision.** A89's outcome clauses — `CONVERGED`, `VERIFIED`, `SUCCESS`, S3's worst ratio ≤ 0.1 — are asserted on every machine class and every run; the refinement clause (exactly one fired at `S3.T` or `S4.T`, kept, chord `ρ_max` > 1 before) is asserted only on the registered `ref-x86-64` CPU model and recorded, not asserted, elsewhere. ADR 0018 fires on a floating-point decision (the chord ratio against 1), which blueprint §8.3 and ADR 0007 F1 exclude from any cross-platform promise.

**Rejected alternatives, and why.** The exact count everywhere (a flaky assertion of a promise the project does not make); no count anywhere (the reference host would no longer catch a refinement path that silently stopped firing).

**Watch for.** Another adaptive floating-point decision asserted exactly across classes.

---

## R-142 — ADR 0006 D4 lists the aarch64 wheel's two unresolved toolchain-runtime objects; Amendment 1 covers numpy's and scipy's aarch64 `libgfortran`

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`specifier`), T08 release spec Amendment R3 7; build lane registered |
| Normative text | ADR 0006 Amendment 2 |
| Evidence | `docs/t08-a30/t08-a30-aarch64.json` (T08.A30 aarch64); `scripts/p03_binary_inventory.py` (`ADR0006_A2`); `tests/test_t08_w2_inventory.py` |
| Affected packages | T08 (A30), every later release's [A10] refresh |

**Decision.** D4 gains CasADi's aarch64 `libgfortran-8de1544a.so.5.0.0` (5 413 232 bytes) and `libgomp-7eb2fb8b.so.1.0.0` (1 194 968 bytes) with their x86-64 counterparts' defaults; D4's `libquadmath`, `libmvec` and `libspral.a` are absent from the aarch64 wheel and its three adaptor/IPC objects present; Amendment 1 (R-135) covers numpy's and scipy's aarch64 `libgfortran` copies. No disposition, mode or default changes. The [A10] inventory attributes the two objects to "ADR 0006 Amendment 2".

**Rejected alternatives, and why.** Dispositioning CasADi's copies by analogy as GPL-3.0-with-GCC-exception (D4's rule: a term is read from a shipped notice or recorded unresolved; CasADi's copies ship none); leaving them only in the A30 record (mode B reads ADR 0006).

**Watch for.** A mode-B artifact for aarch64 without these items resolved.

---

## R-143 — V19 for C1: H4 met with PR and the light gases vapour-only; A61 is the group's suite (69 passed, 3 data-guarded skips not reproduced) and one converged solve; the pin is `6089593`; H2 met while the K_NH₃ transcription stays an M01 pin item

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | design lane (`specifier`), T08 release spec Amendment R3 8; ADR 0022 proposed revision 1, pending Frank's F3; build lane registered |
| Normative text | T08 release spec §7.2 H4 (marker), §9 row T08.A61 (Amendment R3 8); ADR 0022 proposed revision 1 |
| Evidence | `benchmarks/t08/v19/c1-idaes.json`, `c1-reactor.json`, `c1-provenance.json`; `docs/v02-real-chemistry-dossier.md` |
| Affected packages | T08 (V19), M01 |

**Decision.** For C1, "the selected method" is Peng–Robinson with H₂, N₂, Ar and CH₄ declared vapour-only (the liquid is NH₃ alone); IDAES 2.13 represents the skeleton with it, so H4 is met, and dissolved light gases are a v0.2 limitation the dossier states. A61's "own regression reference" is the group's pytest suite at the pin, each test's own tolerance: 69 passed, 0 failed, 3 skipped by the suite's own guards meets A61, the three counted not reproduced; H1 is met on this reading. The pin is `main` @ `6089593464fc9bc2c0a0cb58e30ad5433ece6332`, the commit measured. H2 reads met (a published rate law with parameters, compared with experimental data); item 5 is met only with the K_NH₃ discrepancy named, and item 11 lists the K_NH₃ enthalpy term among M01's pin items.

**Rejected alternatives, and why.** Full PR VLE as H4's method (no acquired tool represents it); the 4TU comparison inside A61 (its use awaits Frank's rights statement; solved-case validation is M01's); the tag commit `d78fbfb` as the pin (not run); H2 `needs_frank` (the open question is a pin, not whether a validated law exists).

**Watch for.** Dissolved-gas effects claimed in v0.2 without a full-VLE route; item 5 reported without its discrepancy.

---

## R-144 — T08.B50's content clause excludes `server.package_version`, by Frank's decision

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | **Frank, 2026-10-01** ("Amend"), answering the V13 verdict at `C` = `814e151`; recorded by the build lane |
| Normative text | `docs/derivations/T08-build-first-spec.md` Amendment 4 |
| Evidence | `docs/reviews/T08-verdicts.md` (V13 FAIL solely on B50's content clause; finding G2) |
| Affected packages | T08 |

**Decision.** B50's "exactly the CSTR and the two policies" is read over `list_models` and `get_project` content excluding `server.package_version`, which the release spec requires to change at every candidate; a test asserts the equality exactly.

**Rejected alternatives, and why.** Re-reading "content" to exclude the version without an amendment (a criterion re-read after the result, as R-134 rejected). Leaving V13 failing (the failure is the release's own required version change, not a warm-start defect).

**Watch for.** Any other `get_project`/`list_models` difference passing under this exclusion.

---

## R-145 — ADR 0022: Frank's choice of the ammonia loop recorded, with Proposed revision 1

| | |
| --- | --- |
| Date | 2026-10-01 |
| Decided by | **Frank**, 2026-09-29 (F3) and 2026-10-01 (accepting revision 1) |
| Normative text | ADR 0022, "Frank's choice recorded" |
| Evidence | `docs/v02-real-chemistry-dossier.md`; `benchmarks/t08/v19/` |
| Affected packages | T08 (V19), v0.2 M01 |

**Decision.** C1, the ammonia synthesis loop on the group's released reactor code (`main` @ `6089593`, MIT), PR with the light gases vapour-only. The ADR becomes Accepted when V19 is PASS.

**Rejected alternatives, and why.** C2 (methanol) and the others, per T08 spec §7.4.

**Watch for.** A pin other than the released line; dissolved-gas behaviour claimed before M01 derives it.

---

## R-146 — Replay comparison policy `T08-numerical-policy-v2` (ADR 0025); records are compared under the policy they name, and an unknown policy is refused at replay

| | |
| --- | --- |
| Date | 2026-10-02 |
| Decided by | design lane (ADR 0025, Proposed); brief `docs/briefs/T08-G1-replay-policy.md`, Frank's go-ahead 2026-10-01; amended by Frank's answer to Q4, 2026-10-02 (R-147); entered at W9 by the build lane |
| Normative text | `docs/adr/0025-cross-platform-replay-comparison.md` (with "Frank's answer to Q4" and its Correction of 2026-10-02, T08 review 3); ADR 0007 Amendment 1; T08 release spec Amendment R4 (A45) and Amendment R5 2 |
| Evidence | `docs/reviews/T08-verdicts.md` G1; `docs/t08-rc-record.md` F2 |
| Affected packages | K05, K04, T08 |

**Decision.** New records carry `T08-numerical-policy-v2`. It does four things:

- compares float-derived digests and ids for shape: `certificate_id` by how it was built, and `level_constants_sha256`;
- floors certificate limitation values at their thresholds, solution-state variables at their kind's `τ_kind`, and phase-branch flows at the molar-flow `τ`;
- compares message templates exactly and the floats inside them relatively;
- moves `u_diag_min_abs`, `u_diag_max_abs` and `u_diagonal_ratio` to "recorded, not reproducible".

Records made under v1 are compared under v1 (R-147). v1 is frozen with its results.

**Rejected alternatives, and why.**

- Editing v1 in place: it changes registered results.
- A cross-architecture-only policy: ADR 0007 D2.5.
- A loose tolerance on the pivot diagnostics: it would be fitted to one run.
- Exact messages: D1's rule loses to its own enumeration otherwise.
- A plan-derived R0 certificate id: identity collision across starts.
- Re-judging the `814e151` bundles under v2.

**Watch for.**

- A new float-derived hash that is not in `float_digests`; A1 refuses it.
- A tolerance on `u_diag_*` reintroduced.
- A solution state compared without declared kinds.
- A v1 record compared under v2.

---

## R-147 — A record made under another numerical policy is replayed and compared under the policy it records, not refused; only an unknown policy is refused, by Frank's decision

| | |
| --- | --- |
| Date | 2026-10-02 |
| Decided by | **Frank, 2026-10-02** ("compare under the old policy"), answering ADR 0025 Q4; recorded by the build lane |
| Normative text | ADR 0025, "Frank's answer to Q4 (2026-10-02) — D1.3 replaced", and its Correction (2026-10-02, T08 review 3) items 2 and 4; T08 release spec Amendment R5 2 |
| Evidence | `docs/T08_DECISIONS.md` 2026-10-02; `docs/reviews/T08-review-3.md` §B.2 and probe 2 (the 52 `814e151` RC bundles, v1 records, replayed by this build: 52/52 `MATCH`) |
| Affected packages | K05, T08 |

**Decision.** A bundle recorded under another numerical policy is replayed and compared under the policy it records — for v0.1's existing bundles, `K04-numerical-policy-v1`, whose code path stays bit-identical (ADR 0025 W2, A12) — not refused. This replaces D1.3's refusal and W4's "D1.3 refusal" item. A record naming a policy the code does not know is still refused (`inspected_archived_results` / `NOT_RUN`, reason naming the unknown id). A45's FAIL at `814e151` stands: those bundles recorded v1 and are judged under v1.

**Rejected alternatives, and why.** Refusing v1 records at replay (ADR 0025 D1.3 and Q4's recommended default, on the "never reinterpreted" precedent): v1's known defects only ever produce false MISMATCHes, never false MATCHes, so judging a record by its own policy is safe, and every committed bundle stays replayable.

**Watch for.** A v1 record compared under v2; a change to the v1 comparator's path; a record naming an unknown policy compared rather than refused.

---

## R-148 — The K05 identity re-registered for recording `T08-numerical-policy-v2`: a substitution-only move, by Frank's approval

| | |
| --- | --- |
| Date | 2026-10-02 |
| Decided by | **Frank, 2026-10-02** (approved the move as substitution only; precedents T08.A13's D2/D3 and STR-05 moves, R-082); recorded by the build lane |
| Normative text | ADR 0025 D1.2 (this build records `T08-numerical-policy-v2`); this entry for the registered values |
| Evidence | `tests/t08_v2_substitution.py` and the tests that use it; `docs/T08_DECISIONS.md` 2026-10-02; held branch `wp/T08-a25-recording` (`056f850`, `4395df4`), merged at `9ec2543` |
| Affected packages | T08 |

**Decision.** ADR 0025 D1.2 makes every run manifest and certificate this build writes name `T08-numerical-policy-v2`. `RunManifest.structural_sha256` covers `numerical_policy_id`, so the registered identity values move, and are re-registered:

| Value | Registered (v1 recorded) | Re-registered (v2 recorded) |
| --- | --- | --- |
| K05 document, whole | `7f32b1431226d11fd7b5b89f467525ca72648d6d7596df82d5d64b27d1ddf7e5` | `28dd8bf7f15f7750b0c646f609037dc84afd6f465b0bc3b5fac459c14299f0a5` |
| K05 document minus `t07` | `9a7b4e6d1e794e903a41ba2bd96ead58a074896380d80e37e0f06545cff3d4bc` | `29246e053ad126034c1aeef0f396ffe1d9f4dffcf5128f226720280bd1b656e5` |
| `t07` key | `422aa7a5d1b50ea1ab5f101fe368fd51c108b463eb9d8a0af905f1e9bd09c122` | `a96f17eda025168ea184584bd8f0fd2bed6d940ecf8356a6b7ee6f9663348e4b` |
| K05 `structural_sha256` | `915c97e82551c75c588ec4a4e41b060241d75e037366c099c285493165a97e27` | `e62a59a6b3634afd8f43eae399129a2d64bafb6e8ba90ad5fe0c9c1a9c5ad238` |
| CLI `solve`/`inspect` structural hash (SYN-001-nominal) | `af86adb802f001acb1cb4bb36ed211307b941952f9470595af6407d5b1eb3272` | `f95361227b7d1d5647c486e0ba143fc69dc1203a7bbbb82eb0fad4f1dff775e3` |
| K05 schema fixtures (run manifest: certificate hash, `manifest_sha256`, structural; three certificates) | `bb831ac7…`, `c124b5d1…`, `915c97e8…`; `numerical_policy_id` v1 | `b103575c…`, `b4f7241d…`, `e62a59a6…`; v2 |

T02's floats (`9a8a5baf…`), the keys `t02`…`t06`, `check_policy_sha256` and `syn001.py` do not move. **Substitution proof:** with ADR 0025's recording switch undone at its sources (`run.session._numerical_policy_id` and the certificate's default record v1; `replay._as_recorded` the identity, as before the switch — `056f850`'s whole source diff), every old value is reproduced byte for byte: the minus-`t07` document and structural hash (`tests/test_t07_identity.py`), the `t07` key (`tests/test_t08_w1_identity_substitution.py`; with D1–D3 undone too, T07's `11bcb148…`), every CLI pin (`tests/test_t07_w5b_cli.py`) and the four schema fixtures, whose pre-switch bytes are pinned by hash (`tests/test_k05_schemas.py`). The whole document follows from its minus-`t07` bytes and its `t07` key, and was measured: `7f32b143…` with v1 recorded. Pinned at `tests/test_t07_identity.py` (`K05_MINUS_T07_SHA256_V2`, `STRUCTURAL_SHA256_V2`), `tests/test_t08_w1_identity_substitution.py` (`T07_KEY_SHA256_V2`), `scripts/t08_rc.py` (A42's constants) and `tests/fixtures/t07/cli-existing-commands.json`. Historical records (evidence manifests, T06/T07 run files and generators, RC records) are not rewritten.

**Rejected alternatives, and why.** Excluding `numerical_policy_id` from the structural identity (moves every hash anyway and changes what the structural hash means: the policy a record is judged under is part of its identity). Not recording v2 (contradicts ADR 0025 D1.2; v0.1 records would name a policy whose known defects the release no longer applies). ADR 0025 §11's claim that nothing registered moves was wrong; this entry corrects it in the register, not by editing the ADR.

**Watch for.** A later change that moves any of these values by more than this substitution; a value pinned elsewhere still carrying the v1 value (the T08 release spec's §3 table and `benchmarks/t08/reference_values.yaml` carry the v1 values as T07 registered them; changing them is the design lane's).

---

## R-149 — The project is named OpenFlowsheet: product, distribution, import package and console script renamed before v0.1, and the identity values the rename moved re-registered by substitution only, by Frank's decision

| | |
| --- | --- |
| Date | 2026-10-02 |
| Decided by | **Frank, 2026-10-02** (the name and the scope; approved the identity move as substitution only, option (A) of the build lane's held report — not relative imports); recorded by the build lane |
| Normative text | This entry |
| Evidence | `tests/t08_rename_substitution.py`, `tests/test_t08_rename_substitution.py` and the tests that use them; `docs/T08_DECISIONS.md` 2026-10-02; brief `docs/briefs/T08-rename-openflowsheet.md`; branch `wp/T08-rename` (`3a1345f` held trial, then `63fb356`…) |
| Affected packages | T08 |

**Decision.** The project is **OpenFlowsheet**. Product name OpenFlowsheet; distribution `openflowsheet` (PyPI name free on 2026-10-02); import package `openflowsheet` (was the provisional `process_runtime`); console script `openflowsheet` (was `process-runtime`); MCP server name `openflowsheet`; environment variables `OPENFLOWSHEET_TOKEN_FILE`, `OPENFLOWSHEET_TEST_PAUSE_AT_STAGE`, `OPENFLOWSHEET_TEST_BLOCK` (were `PROCESS_RUNTIME_*`). No backward-compatibility alias: v0.1 is the first release. The MCP surface does not move (served tool list `dbc18fe3…`, descriptions `171dd768…`, before and after).

**What the rename moved, re-registered.** Two modules hash their own source and import the package by name: the SYN-001 provider's `implementation_sha256` (`thermo/syn001.py`, blueprint §6.4) and the T06 generator's `generator_sha256` (`benchmarks/t06/generator.py`). Through `model_version` the provider's hash moves `plan_id`, `structural_sha256`, `artifact_r0_sha256` and what covers them:

| Value | Registered (before the rename) | Re-registered |
| --- | --- | --- |
| SYN-001 provider `implementation_sha256` | `67e472816d4d67676f4cac64861e815602de01b3e7621e225f93cbdfda32982a` | `4e4c37cc8054c7da12965cba80494be5666053e3bf817446053ebdeb8d6a04e7` |
| T06 `generator_sha256` | `7f426aa9f8a114553d362ed03f4a040e67827a8be17c1751b7e2374043117893` | `509b01fb1544ec24a79b43c11353cfa9b5563ee885ed3eddfdc04d8daf1c14b4` |
| K05 document, whole | `28dd8bf7f15f7750b0c646f609037dc84afd6f465b0bc3b5fac459c14299f0a5` | `174977ccf18d0dbf57fa429cb2522921cc98d0d5b693382ec973c86fd714c225` |
| K05 document minus `t07` | `29246e053ad126034c1aeef0f396ffe1d9f4dffcf5128f226720280bd1b656e5` | `24af004ab5718e559bd3d40716d66e21d9b19043a26777a39a0da84c6fbdcb8e` |
| `t07` key | `a96f17eda025168ea184584bd8f0fd2bed6d940ecf8356a6b7ee6f9663348e4b` | `887a2e622676dbfaff0a8ebfc309414f0e74150ace8327887b4a9ec15e498a38` |
| K05 `structural_sha256` | `e62a59a6b3634afd8f43eae399129a2d64bafb6e8ba90ad5fe0c9c1a9c5ad238` | `ed6d11f3beb78c6f1debc481c6e525ce3ccb120bd30cdfd07e470f728e082e90` |
| CLI `solve`/`inspect` structural hash (SYN-001-nominal) | `f95361227b7d1d5647c486e0ba143fc69dc1203a7bbbb82eb0fad4f1dff775e3` | `16ae2bd4ab03810597147f4daa3894fb123ead2bb0e36548ef75fd28b3ce773b` |
| Schema fixtures (11; run manifest: R0 digest, four artifact hashes, structural, `manifest_sha256`) | pinned by hash, `FIXTURES_PRE_RENAME_SHA256` | the committed fixtures with the substitution applied |
| T07 W5c table (55 `binds` digests of 69), W3a `LEGACY_PLAN` (38 of 40), W3f `Q1_FILLED` (2) | pinned by hash (`W5C_PRE_RENAME_SHA256`, `W3A_PRE_RENAME_SHA256`) and `Q1_FILLED_PRE_RENAME` | re-generated values |

T02's floats (`9a8a5baf…`) and the MCP surface do not move. **Substitution proof:** each module's bytes with `openflowsheet` replaced by `process_runtime` hash to its pre-rename value (the rename changed nothing else in either); with both self-hashes monkeypatched back (`record_process_runtime`), every old value above is reproduced byte for byte — measured also as the whole K05 document and T02 floats in a fresh process, byte-identical to `50602a0`'s. The R-148 tests undo this substitution first and then their own. The T06 start sets (`starts-nominal-v1.json`, holdout1) are never regenerated (T06 spec §6.5): they keep the pre-rename hashes, `starts_sha256` does not move, and their tests compare the live hashes substituted back. Historical records (evidence, run records, reviews, design history, decision logs, RC records) are not rewritten.

**Not moved, by decision.** Schema `$id` URLs (`https://github.com/frankp/process-runtime/schemas/…`, `…/clearsheet/main/schemas/…`) stay for v0.1 and move in v0.2 by ADR; the frozen schemas' description prose that names `process_runtime.*` stays with them (it is served inside the MCP input schemas, so editing it would move the descriptions digest). The `requirements.lock` header and the `Makefile` line that writes it stay (the lock must not change; the project is not in it). ADRs, specifications, design notes, spikes, registered reference strings and registered benchmark YAML comments keep the old names.

**Rejected alternatives, and why.** ClearSheet — several commercial "ClearSheet" products and a spreadsheet connotation. FlowSheet — a generic term, and the GitHub organisation is taken. ProcessSim — confusable with Fives ProSim. Certainflow — more distinctive but narrower than the project's scope. Relative imports in the two self-hashing modules, to make a later rename inert (changes what "hash of its own source" covers, a design-lane question, and moves the values once anyway). Keeping the import name `process_runtime` (contradicts Frank's scope).

**Watch for.** A later change that moves any of these values by more than this substitution; a value pinned elsewhere still carrying the pre-rename value: the T08 release spec's §3.2 table, `benchmarks/t08/reference_values.yaml` and `docs/derivations/scripts/t08_reference.py` carry R-148's values, and changing them is the design lane's (as for R-148). The five derivation scripts' independence checks now test for `openflowsheet`; their emitted claim names keep `process_runtime`.

---

## R-150 — One public repository: development and releases continue in `computational-chemical-engineering/openflowsheet`; the pre-0.1.0 history is archived in the private `openflowsheet-dev`, by Frank's decision

| | |
| --- | --- |
| Date | 2026-10-03 |
| Decided by | **Frank, 2026-10-03**; recorded by the build lane |
| Normative text | This entry; `docs/RELEASING.md`, `docs/HISTORY.md` |
| Evidence | brief `docs/briefs/single-public-repo.md` (in the archive); branch `single-repo` from the public root `5a35019`; `.github/workflows/release.yml`, `tests/test_release_workflows.py`, `scripts/pre_push_guard.py`, `tests/test_pre_push_guard.py`, `tests/conftest.py` (`require_archived_history`) |
| Affected packages | all (where work happens); T08's release machinery |

**Decision.** From v0.1.0 on, the public repository `computational-chemical-engineering/openflowsheet`
is the one working repository: branches, pull requests, CI, tags and releases. Its history starts at
its root commit `5a35019` (v0.1.0, the archive's `a3bc534` tree without its history); the squash at
v0.1.0 was a one-time step to keep the development history private. That history stays, read-only,
in the private `openflowsheet-dev`, and the commit ids cited by the evidence manifests and documents
up to v0.1.0 refer to it and are not rewritten. Releases are one workflow, `release.yml`, dispatched
by hand in the public repository (dry run by default; gate → tag → build → PyPI by trusted
publishing behind the `pypi` environment → GitHub release); 0.1.1 is the first release through it.
Tests that read an archived commit skip explicitly where it is absent, with the reason
"pre-0.1.0 development history is archived in openflowsheet-dev (R-150)", and run unchanged where it
is present. A pre-push hook (`scripts/install-hooks.sh`) refuses to push to the public repository
any commit that does not descend from `5a35019`.

**Rejected alternatives, and why.** Two repositories — private development, public release
snapshots built by `cut-release.yml` and `scripts/release_snapshot.py` (Frank's earlier decision
of 2026-10-03, implemented and then withdrawn the same day): every release would be a squashed copy
with no reviewable history in public, contributions could not be taken by pull request, and the
private-to-public step needed a deploy key and a second approval. Publishing the full development
history: Frank's choice is to keep it private. Rewriting the cited commit ids to public ones: the
public commits for them do not exist.

**Watch for.** A clone holding both histories (the old development checkout): install the pre-push
hook there before anything else. A test that newly reads a pre-0.1.0 commit must go through
`require_archived_history`, not fail in the public repository. A manifest written after v0.1.0 must
cite a commit of the public repository (`tests/test_evidence_manifests.py` still asserts it).

---

## R-151 — Where the release candidate `C` is not in the repository, the gate identifies it by its recorded file hashes (`release/rc-trees/<C>.json`); the tree check's rule is unchanged

| | |
| --- | --- |
| Date | 2026-10-03 |
| Decided by | Frank's brief of 2026-10-03 (`docs/briefs/single-public-repo.md`, in the archive), implemented by the build lane |
| Normative text | ADR 0021 D2.4 (proposed revision 2, R-139), unchanged; this entry for how `C` is read |
| Evidence | `scripts/v0_1_gate.py` (`tree_record`, `recorded_tree_differences`, `resolve_rc`); `release/rc-trees/67c66d98587f23bd7dfe8da28a8facccc92da21e.json` (generated from the development checkout, where `C` exists: 901 files, version `0.1.0rc1`); `tests/test_t08_w4_v0_1_gate.py` |
| Affected packages | T08 (the v0.1 gate) |

**Decision.** ADR 0021 D2.4 requires the tag candidate's files under `src/`, `schemas/`,
`benchmarks/`, `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE` and
`NOTICE` to equal `C`'s except one occurrence of the version in `pyproject.toml` and
`src/openflowsheet/__init__.py`. `C` = `67c66d9` is a commit of the archive (R-150). Where `C` is in
the repository the gate compares by git, as before; where it is not, it compares the candidate with
`release/rc-trees/<C>.json` — the mode and sha256 of every file under those paths at `C`, `C`'s
version, the lines carrying it, and `C`'s committer time — by the same rule (a version file passes
iff the candidate's version occurs once and replacing it by `C`'s gives `C`'s sha256). The two give
the same answer: at the archive's v0.1.0 bump `a3bc534` both give no difference, at `e51e458` both
give the same eight paths, and on scratch repositories both agree for a version bump, a pin, an
edit, an addition, a removal, a mode change and a doubled version string. `--rc` resolves through
git, else by a unique prefix of a recorded `C`; neither is an error (exit 2). The gate's verdict
line names the candidate's version, `vX.Y.Z tag may be proposed`, and a version off the 0.1 line
is refused (the v0.1 gates cover `0.1.z` and its pre-releases).

**Rejected alternatives, and why.** Fetching `C` from the archive at release time: the public
workflow has no access to the private repository and should not. Re-pointing the gate at the public
v0.1.0 commit as the reference: `C` is what ADR 0021 and the verdicts judged; the public commit is
a copy of a later tree. Comparing by git blob id instead of sha256: the record is meant to be read
without git's object model, and sha256 is the project's hash elsewhere.

**Watch for.** A change to the D2.4 path list (`TREES`) invalidates the record: the gate refuses a
record whose `trees` differ, and a new record needs `C` present (`--write-tree-record`). The record
is evidence for v0.1 only; a 0.2 line has its own `C` and gate.

---

## R-152 — M01 pins the reactor code's K_NH₃ enthalpy term, 7000 cal/mol (29 288 J/mol), by Frank's decision; the check against Rossetti et al. 2006 was not made

| | |
| --- | --- |
| Date | 2026-10-06 |
| Decided by | **Frank, 2026-10-06** ("For K_NH3 use the code's value"); recorded by the build lane |
| Normative text | This entry; `docs/v02-real-chemistry-dossier.md`, "Frank's statement, 2026-10-06" |
| Evidence | `benchmarks/t08/v19/c1-provenance.json` (the code's term at `6089593`, Gargiulo 2025 Table 1's 29 228 J/mol) |
| Affected packages | M01, M02 (the reactor pin), M07 |

**Decision.** The ammonia kinetics M01 pins carry K_NH₃ = exp(−8.3/R + 7000/RT), R in cal/(mol·K), exactly as the
group's reactor at `6089593` implements it. The T08 ruling (release spec Amendment R3 8 (e)) that the term be read
from Rossetti et al. 2006 itself is replaced by Frank's decision.

**Rejected alternatives, and why.** Gargiulo et al. 2025 Table 1's 29 228 J/mol: Frank judges it a transposition.
Waiting for the Rossetti 2006 check: it would hold M01's pin for a 0.35 % effect.

**Watch for.** This is a decision, not a verification: no record may say the value was checked against Rossetti
2006. If that check is made later and disagrees, the pin changes by a new entry and the reactor's model version moves.

---

## R-153 — v0.2's order: M01's design lane first (the critical path M01→M02→M04→M05→M07), M06 built alongside, M03 when the critical path allows; a pre-release `0.2.0a1` after M02

| | |
| --- | --- |
| Date | 2026-10-06 |
| Decided by | **Frank, 2026-10-06** ("Go ahead according to your recommendations"), on the build lane's recommendation |
| Normative text | This entry; plan v1.2 §4.4; `docs/V02_STATE.md` |
| Evidence | — (an ordering decision) |
| Affected packages | M01–M07 |

**Decision.** M01 (design-led: the Peng–Robinson provider, component records, k_ij and VLE sources, boundary
mappings) starts first because it heads the longest dependency chain; M06 (build-led web shell) is built alongside
on its own branch. A pre-release `0.2.0a1` is proposed once the reactor runs in the loop (M02 `tested`), so the
real-chemistry route is public before the optimization work; 0.2.0 itself follows M07's gate. Pre-releases go
through `release.yml` like any release, with Frank's dispatch.

**Rejected alternative, and why.** M06 first (`docs/progress.md`, 2026-10-03): M06 is off the critical path, and
M01 has the most design-lane work and the external inputs. A single 0.2.0 release with no pre-release: the reactor
route would stay unpublished until the end of v0.2.

**Watch for.** The v0.1 gate script refuses versions off the 0.1 line (R-151); `0.2.0a1` needs a v0.2 gate of its
own (the W gates that apply at that point), designed before the pre-release, not by relaxing the v0.1 one.

---

## R-154 — The C1 provider `pr-c1-v1`: Peng–Robinson with PR 1976's rounded Ω_a, Ω_b and κ; pure NH₃'s roots labelled by T_c,EOS and v_c,EOS; a light-gas phase takes the largest root, refused when that root is metastable

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | `docs/adr/0026-c1-peng-robinson-vapour-only-route.md` D1, D2; `docs/derivations/M01-spec.md` §4, §5.2–5.3 |
| Evidence | `benchmarks/m01/reference_values.yaml` (claims PR-01–PR-06, IDAES-01: the generator reproduces T08's IDAES separator to 4 × 10⁻¹²) |
| Affected packages | M01, M02, M04–M07 |

**Decision.** Ω_a = 0.45724, Ω_b = 0.07780, κ(1976) for every component. Pure NH₃: above T_c,EOS = T_c((1+κ)/(r+κ))²
one vapour root; below, three roots give liquid = smallest, vapour = largest, a single root is liquid iff v < (Z_c/B_c)b.
A phase with any light gas takes the largest root; `vapour_root_metastable` when three roots exist and the smallest has
the lower G^dep.

**Rejected alternatives, and why.** Exact Ω's: IDAES (the independent reference) uses the rounded ones. Minimum-Gibbs
root for the light-gas phase: discontinuous along the flash's search and unlike IDAES's vapour root.

**Watch for.** Near-double-root states are not asserted; the label rule rests on the spinodal straddle (claims PR-06),
which the generator re-checks.

---

## R-155 — The vapour-only flash solves for the equilibrium vapour composition y*(T, P, light-gas proportions), not for the split from the feed

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0026 D2; `docs/derivations/M01-spec.md` §5.4–5.6 |
| Evidence | generator claims FL-*, FL-INDEP; state F5 (trace H₂ in NH₃: TWO_PHASE with y* = 0.0555) |
| Affected packages | M01, M02 (units, verifier use) |

**Decision.** y* is the smallest root on (0, 1) of ln y + ln φ_NH₃^V(y, w) − ln φ_NH₃^L,pure, bracketed by the fixed
samples k/64 and 1 − 2⁻ʲ and bisected; two-phase iff n_NH₃ > n_light y*/(1 − y*). No liquid at T ≥ T_c,EOS or where pure
NH₃'s stable phase is vapour.

**Rejected alternatives, and why.** Bisection on the split from the feed, or a TPD test on the feed's own root (the
previous specifier's tentative choice): an NH₃ feed with a trace of light gas has a liquid-like single root and is
declared one dense phase — T08's trivial-solution trap in another form.

**Watch for.** Positive excursions of h narrower than the sample spacing (near T_c,EOS only) could be missed; F12 is
registered for what the rules give.

---

## R-156 — `PR-C1-ref-v1` is a formation datum (ideal gas at 298.15 K = Δ_fH°); ADR 0011 D2's reaction-consistent set becomes {SYN-001-ref-v1, PR-C1-ref-v1}, without editing SYN-001's constant

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0026 D4; `docs/derivations/M01-spec.md` §6 |
| Evidence | claim RX-02 (Σν_i h_i^ig(298.15 K) = 2Δ_fH°(NH₃) exactly) |
| Affected packages | M01, M02, M07 |

**Decision.** h_i^ig(T) = Δ_fH°_i + ∫_{298.15}^{T} c_p dT; phases add the PR departure; reacting units balance total
enthalpy. The registry of reaction-consistent conventions lives in a new module; `REACTION_CONSISTENT_CONVENTIONS` in
`models/syn001/conversion_reactor.py` is not edited (its source is in SYN-001's model versions).

**Rejected alternatives, and why.** Editing the SYN-001 constant: moves SYN-001's identity (needs Frank's approval,
R-148/R-149) for no gain. A heat-of-reaction term: double-counts on a formation datum (ADR 0011).

**Watch for.** A test keeps the SYN-001 constant a subset of the registry (M01.A24).

---

## R-157 — k_ij = 0 for every C1 pair, with its effect stated (k = 0.1 for H₂–NH₃ moves the separator's y* by −3.1 %)

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0026 D3; `docs/derivations/M01-spec.md` §4.2 |
| Evidence | `reference_values.yaml` → `closed_form.kij_sensitivity_F1` |
| Affected packages | M01, M07 (W22's statement) |

**Decision.** No binary interaction parameters; the sensitivity table at F1 is part of the record.

**Rejected alternatives, and why.** A literature or fitted set: none covering the C1 pairs was found in an open, cited
source; fitting needs mixture data not transcribed (spec Q-F2).

**Watch for.** Adding k_ij is a new provider data version and a new W22 statement, not a silent record edit.

---

## R-158 — C1 parameter sources: reference-EOS T_c, P_c, ω (via `chemicals` HEOS), NASA TM-4513 c_p (via Cantera), ATcT 1.112 Δ_fH; no rights grant relied on; the libraries are never runtime dependencies

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01, applying Frank's statement 1 of 2026-10-02; Proposed |
| Normative text | ADR 0026 D5; `docs/derivations/M01-spec.md` §3; `benchmarks/m01/components.yaml` |
| Evidence | `benchmarks/m01/external-crosscheck.json` (retrieval exact; CoolProp cross-checks) |
| Affected packages | M01, M02 |

**Decision.** As the title; c_p stored as dimensionless b_k of c_p/R = Σ b_k (T/1000 K)^k (exact decimal rescaling of the
NASA-7 coefficients).

**Rejected alternatives, and why.** Poling 5th ed. polynomials via `chemicals`: redistributing book tables is a rights
question for Frank (spec Q-N1); NASA TM-4513 is a U.S. Government work. NASA's or JANAF's Δ_fH: ATcT is more accurate
(NH₃ 340 J/mol from JANAF). The group's database: a cross-check only (Frank, 2026-10-02).

**Also decided.** T08.A32's synthetic-only rule is amended for real records (spec §3.5): `synthetic: false` records must
be the five M01 records, with identifiers, rights and per-value provenance, covered by M01.A02. Not a relaxation:
synthetic records keep the rule; real ones get a stricter one.

**Watch for.** CH₄'s NASA c_p is 1.1 % from CoolProp's ideal part at 1000 K; recorded, not corrected. Shipping the
records in the v0.2 wheel is Frank's release decision (spec Q-N4).

---

## R-159 — The provider's surface: properties `h`, `Z`, `v`, `lnphi_<id>`; derivative inputs `T`, `P`, `n_<id>`; every refusal's `message` begins with its reason code

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0026 D6; `docs/derivations/M01-spec.md` §5.3, §9.1, §9.4 |
| Evidence | — (a contract) |
| Affected packages | M01, M02 |

**Decision.** As the title; codes `out_of_domain`, `light_gas_in_liquid`, `no_liquid_root`, `no_vapour_root`,
`vapour_root_metastable`, `undeclared_derivative_input`, `dormant_state`. The frozen `PropertyProvider` protocol is
unchanged.

**Rejected alternatives, and why.** A new status or result field for the reason: a frozen-interface change for what a
prefix convention carries.

**Watch for.** Tests match the prefix, not the prose after it.

---

## R-160 — W22's "validated" for C1: numerical verification against closed forms, conformance with IDAES 2.13, and pure-component validation against the reference EOS within stated bands; no mixture VLE claim

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | `docs/derivations/M01-spec.md` §11, M01.A37–A40 |
| Evidence | `benchmarks/m01/external-crosscheck.json` (P_sat within 1.27 %; liquid ln φ within 0.040; light-gas ln φ within 0.042) |
| Affected packages | M01, M07 (the verdict) |

**Decision.** Bands: P_sat 2 % on 240–320 K; ln φ 0.05 for liquid NH₃ at the separator states and for each pure gas at
loop states. They are fitness statements of the same order as the k_ij effect, not numerical tolerances.

**Rejected alternatives, and why.** Waiting for mixture VLE data: none transcribed (candidates named, spec Q-F2).
Bands at the measured values: no margin for a re-run with other pins.

**Watch for.** A transcribed mixture dataset adds a criterion by a new entry; the bands do not tighten silently.

---

## R-161 — The C1 loop uses the zero-pressure-drop convention: P_out = P_in, the reactor runs with p_ret_out = P_in, admissible iff ΔP/P_in ≤ 10⁻³

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01, deciding what ADR 0022 D2 left open; Proposed |
| Normative text | `docs/adr/0027-c1-reactor-boundary.md` D2; `docs/derivations/M01-spec.md` §8.8 |
| Evidence | `benchmarks/m01/reactor-probe.json` (ΔP/P_in = 5.0 × 10⁻⁵ at the nominal point) |
| Affected packages | M01, M02 ("incompatible pressure boundary rejected"), M07 |

**Decision.** As the title; above the bound `pressure_drop_exceeds_convention`.

**Rejected alternatives, and why.** A recycle compressor: needs PR entropy and an efficiency for a 5 × 10⁻⁵ effect.
Inverting for p_ret_out: moves the inconsistency to the outlet at many times the cost.

**Watch for.** Higher GHSV raises ΔP roughly with u²; the refusal, not a silent extrapolation, is the answer there.

---

## R-162 — The reactor's outlet is projected onto the reaction by the least-squares extent over H₂, N₂, NH₃ (inerts exact); refused above a defect of 10⁻⁶

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0027 D3; `docs/derivations/M01-spec.md` §8.9 |
| Evidence | claims BD-01, BD-02; the probe's element defects (~10⁻⁹ under M01's profile) |
| Affected packages | M01, M02 |

**Decision.** ξ = Σ ν_i (n_raw,i − n_in,i)/14; n_out = n_in + ν ξ; the defect is reported.

**Rejected alternatives, and why.** ξ from one species: hides the defect in the others.

**Watch for.** The previous specifier's "grid-independent element floor 2.2 × 10⁻⁴" was iteration error at the group's
tolerance, not a floor.

---

## R-163 — The reactor's duty is process-side (Ḣ by `pr-c1-v1`); the reactor keeps its own kinetics, fugacity correlations and ideal-gas thermodynamics

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0027 D4; `docs/derivations/M01-spec.md` §8.10 |
| Evidence | the probe's coolant uptake and inlet-face loss (finding F-R3) |
| Affected packages | M01, M02, M07 |

**Decision.** Q = Ḣ_out − Ḣ_in on the process side; the coolant uptake and the inlet-face heat loss are diagnostics.

**Rejected alternatives, and why.** PR fugacities inside the kinetics: changes the group's validated model. The
reactor's enthalpy at the boundary: a different datum and data set (ADR 0001 D5.2).

**Watch for.** F-R3 (25–33 % of the reaction heat leaves through the inlet face) is the group's question (spec Q-F1).

---

## R-164 — Ar and CH₄ enter the pinned reactor through M01's overlay rows (N₂ transport surrogates read from the pinned file) and a subclass replacing one three-species constant; nothing of the group's is copied

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0027 D5; `docs/derivations/M01-spec.md` §8.5–8.6; `benchmarks/m01/reactor-overlay.json` |
| Evidence | the probe: backflow override bitwise inert; H₂-surrogate variant moves the outlet by 0.29 % |
| Affected packages | M01, M02 |

**Decision.** As the title.

**Rejected alternatives, and why.** Lumping inerts into N₂: CH₄'s c_p is twice N₂'s. Patching the group's code: it is
used by reference; a fix belongs upstream at a new pin (spec Q-N2).

**Watch for.** The surrogate's 0.29 % is model uncertainty of the same order as the design grid's error.

---

## R-165 — The reactor's start: S1 cold at the trace-NH₃ inlet, S2 warm at the true inlet, S3 polish under M01's profile (Newton rtol 10⁻¹², steady-state target 10⁻⁶ (num_z/100)²)

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0027 D6; `docs/derivations/M01-spec.md` §8.7, §10.2–10.3 |
| Evidence | the probe (cold starts with real NH₃ stall; the group's tolerance leaves 0.45 % path dependence; with S3 the paths agree to the bound of spec §10.3) |
| Affected packages | M01, M02 |

**Decision.** As the title, with the acceptance of spec §8.7.

**Rejected alternatives, and why.** The group's acceptance alone (path-dependent outlet); continuation in inert
fraction (the previous specifier's): the trace start is the group's own and needs one stage.

**Watch for.** The residual floor grows like num_z²; a fixed target is unreachable above num_z = 400.

---

## R-166 — The C1 reactor's design grid is num_z = 800, with its discretization estimate reported in every result

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0027 D7; `docs/derivations/M01-spec.md` §10 |
| Evidence | `benchmarks/m01/reactor-probe.json` grid sequence 100–3200 |
| Affected packages | M01, M02, M04, M05, M07 |

**Decision.** As the title; the profile is registered for num_z ≤ 800.

**Rejected alternatives, and why.** The publication grid 100 (≈ 5 % high in outlet NH₃); 1600 and above (the pinned
solver's state is not accepted there).

**Watch for.** The observed order is 0.6–0.8 (spec Q-F3); an upstream fix of F-R3 may change it.

---

## R-167 — The C1 reactor is N_tubes identical tubes: per-tube flow n_tot/N_tubes, the map homogeneous of degree one

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0027 D1; `docs/derivations/M01-spec.md` §8.3 |
| Evidence | M01.A29 |
| Affected packages | M01, M02, M07 |

**Decision.** N_tubes a positive real configuration parameter; the geometry per tube is the group's G2.

**Rejected alternatives, and why.** Rescaling the geometry: changes the group's validated configuration.

**Watch for.** N_tubes is part of the unit's identity; M07 chooses it for the loop's throughput.

---

## R-168 — M01 builds the boundary module and a synthetic stand-in reactor; M02 builds the out-of-process adapter and the PR units

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0027 D8; `docs/derivations/M01-spec.md` §8.13–8.14, §14 |
| Evidence | — |
| Affected packages | M01, M02 |

**Decision.** `c1.reactor_standin` (ξ = 0.25 n_N₂,in, T_out = T_in), labelled synthetic, exercises every boundary path
without PyMRM.

**Rejected alternatives, and why.** M01-build also implementing the PR units: they belong with the loop M02 assembles.

**Watch for.** The stand-in certifies the boundary code, never the reactor.

---

## R-169 — Inlets outside the kinetics' data domain are flagged `extrapolated`, not refused; outside the adapter's hard domain they are `out_of_domain`

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01; Proposed |
| Normative text | ADR 0027 D9; `docs/derivations/M01-spec.md` §8.12 |
| Evidence | the bed leaves the data domain at every registered state (T_max ≈ 760 K) |
| Affected packages | M01, M02, M04, M05 |

**Decision.** Data domain 643–733 K, 50–100 bar, H₂/N₂ ∈ [1.5, 3]; hard domain 573.15–773.15 K, 5–15 MPa, H₂/N₂ ∈
[1, 4], inerts ≤ 20 %.

**Rejected alternatives, and why.** Refusing outside the data domain (the dossier's list): it would hide the v0.2
decision variable's likely optimum.

**Watch for.** M05 must treat `extrapolated` results as such (a constraint or a stated limit), not as validated.

---

## R-170 — The web shell is hand-written ES modules with no build, no framework and nothing third-party, served same-origin by `serve-http --ui`

| | |
| --- | --- |
| Date | 2026-10-06 |
| Decided by | Design lane (`architect`, M06); **Proposed** until M06's review |
| Normative text | `docs/adr/0030-diagnostic-web-shell.md`; `docs/design/M06-web-shell.md` §5, §8 |
| Evidence | — (an architecture decision); gates G1, G10–G12 of the design note when built |
| Affected packages | M06 and every later UI change |

**Decision.** Source in `apps/web/`, shipped as package data through `_data/web`; rendering through an in-house
builder that can only create text nodes; one `fetch` call site with a route table generated from `OPERATIONS`;
`serve-http --ui` (off by default) adds a static mount at `/ui/` with a strict CSP; no CORS. Tests: Python
contract and static scans, Node's built-in runner (test-time only, no npm), a headless-Chromium smoke test.

**Rejected alternative, and why.** An npm toolchain (Vite/TypeScript/React): committed build output cannot be
reviewed against its source or the sdist build needs Node, and the supply chain and licence inventory grow by
hundreds of packages. A vendored micro-framework: an opaque file for a benefit the screens do not need. A
separate port with CORS. Playwright in the default gate (kept as the fallback for a flaky smoke test).

**Watch for.** Adding a JS dependency, a build step or a framework later reverses this and takes a new ADR.

---

## R-171 — The browser holds the existing bearer token in Web Storage and sends it only as a header; never a cookie

| | |
| --- | --- |
| Date | 2026-10-06 |
| Decided by | Design lane (`architect`, M06); **Proposed** |
| Normative text | ADR 0030 D3–D4; design note §7 |
| Evidence | — ; gate G8 when built |
| Affected packages | M06 |

**Decision.** Login form → `sessionStorage` (opt-in `localStorage`); `Authorization: Bearer` only; never placed
in a URL the app builds; no Host-header check, because without ambient authority DNS rebinding gains nothing.

**Rejected alternative, and why.** A cookie session with a login endpoint: an endpoint outside `OPERATIONS` and
ambient authority for CSRF and rebinding. A token in the query string: it lands in logs and history.

**Watch for.** Any move to cookies needs CSRF and Host defences designed first.

---

## R-172 — ADR 0019 Amendment 3: the structure index and unroutable analysis (Asks 1, 2), element-level `diff_revisions` (Ask 6), `list_audit` (Ask 4); Ask 3 deferred, Ask 5 rejected

| | |
| --- | --- |
| Date | 2026-10-06 |
| Decided by | Design lane (`architect`, M06); **Proposed** until M06's tested evidence and review |
| Normative text | `docs/adr/0019-application-contract-v1.md` Amendment 3; design note §4 |
| Evidence | probes at `67029fa` (design note §3); gates G2–G6 when built |
| Affected packages | M06; every client of the contract |

**Decision.** `inspect_structure` gains `rows`/`columns` beside the report (never inside it) and, when no route
binds, `validation_structural_report`; `diff_revisions` gains `elements`, pairing list items by `id`;
`list_audit` (Python, CLI, HTTP) with `read` for one's own rows and `read`+`policy` for others' (`cancel_job`'s
`target_principal` rule). `blocked_by` in failure bundles is deferred (a hashed artifact; solver-record work);
rights in `get_project` are rejected (the UI's route table is generated and checked).

**Rejected alternative, and why.** Computing a finer diff, a row index or an audit view in the browser: each is a
second implementation of contract semantics that humans would see and agents would not. Putting the index inside
`structural_report`: it would move `structural_sha256` and R0. Exposing `list_audit` over MCP now: no agent task
needs it and a tool description needs its own review (G15).

**Watch for.** `elements` must stay out of `TransactionResult.diff` (ledger replays); the index must come from the
same declaration as the report; nothing in it may be parsed from an id (R-019).

---

## R-173 — D1–D3 of the web-shell gap triage are closed by T08 Phase 1; Q1–Q5 ruled; the equation view is a row index without symbolic text

| | |
| --- | --- |
| Date | 2026-10-06 |
| Decided by | Design lane (`architect`, M06) |
| Normative text | design note §3, §4, §6.5 |
| Evidence | live probe at `67029fa`: STR-03 message names `heater`; the A02-352 bundle's `replay_identity` is filled (`T04-W12`) and `property_calls` = 2104; `tests/test_t08_w1_d{1,2,3}_*.py` |
| Affected packages | M06 |

**Decision.** No M06 work on D1–D3 beyond UI-level regression checks. Q1: no structured redundant/excess counts in
the frozen validation report (the structure index serves them). Q2: the equation view shows a row's instance,
role, specification, residual kind and SI unit, incidence with values, matched column, block, redundancy, DOF
row and certificate residual — no symbolic text. Q3: no per-event or per-attempt wall time (it would make
`solve-events.json` differ run to run and so the bundle irreproducible). Q4: no reference-root comparison in run
records. Q5: own audit rows need `read`, other principals' `read`+`policy`.

**Rejected alternative, and why.** Re-fixing D1–D3 (already fixed and tested). Per-event timing as telemetry
inside the event schema (closed and hashed).

**Watch for.** The gap triage's "take identity from the manifest until D2 is fixed" is obsolete.

---

## R-174 — The "scenario view" of the M06 plan row is the run comparison: two finished solves, differences displayed, never judged

| | |
| --- | --- |
| Date | 2026-10-06 |
| Decided by | Design lane (`architect`, M06); scope default pending Frank (design note §12 F4) |
| Normative text | design note §6.7 |
| Evidence | — (a definition); the revision IR has no scenario object in v0.2 |
| Affected packages | M06 |

**Decision.** A scenario in v0.2 is one revision solved under one policy; the view compares two such runs
(outcome, verification, path, structure identity, counters, certificate summary, state differences Δ and
|Δ|/max(|a|,|b|)) with the banner that no registered comparison or allowance is applied.

**Rejected alternative, and why.** Waiting for an IR scenario concept (none planned in v0.2). Showing
AGREE/MATCH on this screen: that vocabulary belongs to registered comparisons (Q4).

**Watch for.** When the IR gains scenarios, this definition is revisited by a new entry.

---

## R-175 — W27: Tier 0 coverage and access report for all 450 OpenIDAES-450 cases without spend; a registered 45-run agent campaign at M07 by Frank's spend decision

| | |
| --- | --- |
| Date | 2026-10-06 |
| Decided by | Design lane (`architect`, M06); spend and model are Frank's (design note §12 F1, F2) |
| Normative text | design note §9; the W27 registration (`docs/derivations/M06-W27-registration.md`, to be written by the `specifier`) |
| Evidence | audit `study/openidaes450:docs/openidaes450-audit.md`; V17 cost USD 0.32–0.54 per run |
| Affected packages | M06, M07 |

**Decision.** Tier 0: provenance, artifact-access report with inaccessible assets, deterministic coverage classes
for all 450 against the 450 and the 82-split, re-run at M07. Tier 1 default: 45 stratified cases, k = 1, the
V17 `v17-c2` agent configuration, est. USD 15–45, at M07 on the v0.2 candidate. System false verification must
be 0; agent terms reported. No headline score, no comparison with CRAFTS' results.

**Rejected alternative, and why.** All 450 runs by default (USD 150–450 for 450 near-identical limitation
measurements while v0.2's domain is narrow). Running the campaign now (0.1.x has SYN-001 components only, so
coverage would not reflect v0.2).

**Watch for.** The classification maps are semantic judgements; they are the design lane's, not the classifier's
implementer's.

---

## R-176 — W27 coverage maps are registered tables over the pinned archive, re-evaluated mechanically against a registry snapshot

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | Design lane (`specifier`, M06 WO-15) |
| Normative text | `docs/derivations/M06-W27-registration.md` §4–§5; `benchmarks/m06/openidaes450/registration.json` |
| Evidence | `case_facts.json` (450 cases); the generator's GC-* claims; dry illustration (0 candidates at 0.1.1 and in a hypothetical v0.2 snapshot) |
| Affected packages | M06, M07 |

**Decision.** Units by function plus required tokens (partial = unavailable, no compositions); components by CAS
RN through an alias table (synthetic records never match); property routes by method equality plus component
coverage and phase admission; the classifier reads case JSON only (never `sources/`) and calls what it cannot
identify `unidentified`. OpenFlowsheet model ids and provider ids are mapped by the registration; an unmapped id
in a snapshot **refuses** classification until an amendment maps it. The snapshot (models, routes, components,
phases) is built from the build under test and its SHA-256 recorded beside `list_models`'.

**Rejected alternative, and why.** Hard-coding today's registry (stale at M07). Inferring a model's function from
its port signature (SYN-001's TP and PH flashes have identical ports). Name matching for components (SYN-001's
`A` would match a case's `A`). Treating unmapped ids as unavailable (silently under-counts v0.2).

**Watch for.** M01/M02 add provider and model ids: the M07 amendment comes before coverage is run.

---

## R-177 — A correct limitation is one matching reason; a CANDIDATE needs the same method, not a covering one

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | Design lane (`specifier`, M06 WO-15) |
| Normative text | `docs/derivations/M06-W27-registration.md` §10.3, §11.5, §5.6 |
| Evidence | — (definitions) |
| Affected packages | M06, M07 |

**Decision.** A limitation answer on a non-`CANDIDATE` case is correct iff at least one item matches a recorded
reason by kind and alias; contradicted and nothing-naming items are semantic errors, reported. A property route
serves a case only with the case's own method class.

**Rejected alternative, and why.** Requiring every item to match (punishes a true reason the classifier
coarse-grained); requiring the top-precedence reason (an agent cannot see precedence); accepting any covering
route (counts method substitution as coverage).

**Watch for.** An agent that lists everything: its semantic error rate shows it.

---

## R-178 — W27 sample: frame without ARTIFACT_INCOMPLETE, candidates first, family largest remainder with a minimum of one for families of ≥ 4, SHA-256 ranks from a fixed seed; residual-check failures flagged, not excluded

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | Design lane (`specifier`, M06 WO-15) |
| Normative text | `docs/derivations/M06-W27-registration.md` §6, §7 |
| Evidence | GC-SAMPLE-1/2; dry draw (§15.2) |
| Affected packages | M07 |

**Decision.** As §6; seed `W27-OpenIDAES-450-sample-v1`; > 45 candidates → 45 drawn from candidates by the same
rule; 0 candidates → 45 from the frame. Every sampled candidate is confirmed by a scripted build, with the stream
floor measured, before any run.

**Rejected alternative, and why.** Excluding the 24 residual-check failures (shifts the family strata; the check
matters only to candidate stream checks, which §11.3 then leaves unjudged). A library RNG (not byte-stable across
versions).

**Watch for.** A re-draw after a §7 amendment uses the same seed.

---

## R-179 — W27 gates the system, not the agent: system false verification, unauthorized and critical effects at 0; agent false verification reported with its bound

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | Design lane (`specifier`, M06 WO-15); gating of the agent term pending Frank (§17 Q4) |
| Normative text | `docs/derivations/M06-W27-registration.md` §11.6–§11.9, §12 |
| Evidence | — (policy) |
| Affected packages | M07 (G16) |

**Decision.** One outcome per run by SYSTEM > INFRASTRUCTURE > AGENT_FALSE_VERIFICATION > the table; infrastructure
failures count and are not re-run; system false verification is judged by integrity, replay and component-record
checks (no registered roots); gated terms as W27-R56; agent false verification, correct-limitation and
correct-build rates reported with one-sided 95 % Clopper–Pearson bounds.

**Rejected alternative, and why.** Gating agent false verification at 0 as V17 does: V17 tests the system's own
agent surface on registered tasks; W27 runs one external model on external cases, and its agent term describes
that model. A headline score: blueprint §11.4.

**Watch for.** If Frank answers Q4 "gated", W27-R56 changes before the first run, by amendment.

---

## R-192 — The served MCP tool-list digest moves from R-133's `171dd768…` to `6c4375b4…`, as the direct consequence of ADR 0019 Amendment 3's `diff_revisions` `elements` (A3.2); the move is bound to that member alone

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | The build lane (session), on the M06 WO-2 engineer's escalation; Amendment 3 approved by Frank 2026-10-08 |
| Normative text | This entry; ADR 0019 Amendment 3 (A3.2); `docs/design/M06-web-shell.md` §2 item 2 (superseded on this point) |
| Evidence | `7b36f4a` `tests/test_t08_w2_surface_digest.py`: served `6c4375b4…`; with `elements` removed from `diff_revisions`' `outputSchema` it is `171dd768…`; with `v17-c2`'s two texts as well, `6d13e13d…` |
| Affected packages | M06, M07 (the v0.2 gate registers its own surface), W27 |

**Decision.** Amendment 3 puts `elements` into `diff_revisions`' result schema, and the MCP binding serves each
tool's `outputSchema`, so the served tool-list digest moves. The design note's "every registered digest stays
bit-identical" (§2 item 2) did not foresee this. The new digest is registered beside the old one, bound by the
decomposition test to exactly that one member. No tool *description* text changes, so Frank's description review
(T08.A18) is not reopened. R-133, R-134 and R-137 remain the record of the 0.1 surface. `scripts/t08_rc.py`'s A49 check
(`R133_DESCRIPTIONS_SHA256`) belongs to the 0.1 line's RC and is not edited. Run on a v0.2 tree it reports the
move, which is correct. The v0.2 release gate registers v0.2's surface (M07).

**Rejected alternative, and why.** Keeping `elements` out of the MCP `outputSchema`: transports must add nothing and
omit nothing (R-096), so MCP would describe a different contract from Python, CLI and HTTP. Editing the A49 constant
to the new digest: that rewrites a 0.1 release record.

**Watch for.** Any other served-surface change in v0.2 needs its own entry and decomposition test. W27's campaign
runs on the v0.2 surface and states its digest.

---

## R-193 — During v0.2, `benchmarks/t08/support_envelope.yaml` is v0.2's working envelope (`v0.2-envelope-dev`, release `0.2.0.dev0`); v0.1's envelope stays as released, at tag `v0.1.1`

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | The build lane (session), on the M06 WO-3 engineer's escalation |
| Normative text | This entry; T08 release spec §5 (its `envelope_id: v0.1-envelope-1` holds for the 0.1 line) |
| Evidence | `4415e3e` (`list_audit` on the interface axis, A20 count 21) and the following commit (id and release renamed, `docs/support-matrix.md` re-emitted; `t08_support_matrix.py --check` 0 problems; envelope tests 65 passed) |
| Affected packages | M01–M07 (every package that adds models, components or operations), M07 (finalises the 0.2.0 envelope with the T08 F3 harvest) |

**Decision.** T08.A20 holds the envelope to the live code, so every v0.2 addition (M06's `list_audit` now, M01's
models next) must enter it. A release record must not describe more than its release shipped. So the file is renamed
in place to v0.2's working envelope, and v0.1's stays byte-for-byte at the release tags. M07 finalises it as
`v0.2-envelope-1` for 0.2.0, with the harvest of T08's manifest limitations (milestone 0 item F3).

**Rejected alternative, and why.** Amending `v0.1-envelope-1` in place (`4415e3e` alone): `docs/support-matrix.md`
would say "v0.1.0" while listing an operation 0.1.0 does not have. A frozen copy of v0.1's file beside a new one:
the tags already preserve it, and two live envelopes would need two A20 checks.

**Watch for.** The release gate for `0.2.0a1` and `0.2.0` must check that `release` matches the version being cut.

---

## R-194 — In v0.2, T08's U14 row claims that no external benchmark comparison is run, registered or shipped, and that W27's adaptation records are confined to `benchmarks/m06/openidaes450/`

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | The build lane (session), on WO-15's finding F6 |
| Normative text | This entry; `benchmarks/t08/support_envelope.yaml` U14 (v0.2's working envelope, R-193); R-175…R-179 |
| Evidence | `tests/test_t08_w2_unsupported.py::test_u14_no_external_benchmark_comparison_is_registered` |
| Affected packages | M06 (W27), M07 |

**Decision.** v0.1's U14 ("nothing is registered or shipped") failed as soon as W27's approved Tier 0 records were
committed (`e268ed8`). WO-14's green gate ran before those files were tracked. The premise changed by design (R-175),
so the claim is restated for v0.2 and the test is pinned to the new claim, which is no weaker than the old one:
- `benchmarks/registry.yaml` names no OpenIDAES/CRAFTS benchmark;
- no tracked path under `src/` mentions them;
- every tracked `benchmarks/` path that does lies under `benchmarks/m06/openidaes450/`;
- no run or campaign record exists there;
- `pyproject.toml` (package data) does not reference them.

**Rejected alternative, and why.** Narrowing the test to `registry.yaml` and `src/` (WO-15's suggestion): it would
let adaptation records spread anywhere in `benchmarks/`, and it would not detect a campaign record committed before
M07. Moving the records out of the repository: R-175 and G13 require them committed, referenced by hash.

**Watch for.** M07's campaign records change this claim again. U14 is then rewritten with the campaign, not relaxed.

---

## R-195 — M01.A26 asserts the projection's defect vector, defect_rel and element balances at 10⁻¹³ × n_tot,in, not relative to the defect

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01 spec Amendment 1; Proposed with ADR 0027 |
| Normative text | `docs/derivations/M01-spec.md` §9.6 A26, §19 item 1; ADR 0027 Amendment 1 A1.4 |
| Evidence | build lane at `f595179`: 2.5 × 10⁻¹¹ relative (5.5 × 10⁻¹⁷ mol/s) by either arithmetic route; generator claims BD-04, BD-05, `reference_values.yaml` → `assertion_margins.A26_projection` |
| Affected packages | M01, M02 (inherits the projection) |

**Decision.** A defect of ~10⁻⁶ mol/s is a difference of flows near 0.5 mol/s. Its binary64 floor is the raw
outlet's own rounding: 5.6 × 10⁻¹⁷ × n_tot,in, which is 2.5 × 10⁻¹¹ of the defect. The defect vector and defect_rel are
therefore asserted at 10⁻¹³ × n_tot,in (defect_rel at 10⁻¹³). The element balances move to the same scale, from
10⁻¹⁵: the worst-case bound of their five-term float sums is 1.7 × 10⁻¹⁵. The CH₄ defect is exactly 0. ξ and the
projected outlet stay at relative 10⁻¹².

**Rejected alternatives, and why.** Relative 10⁻¹²: no binary64 implementation reaches it. Feeding the projection exact
decimals: it would test the harness, not the code.

**Watch for.** 10⁻¹³ sits 1.8 × 10³ above the measured floor and 10⁶ below the nearest listed wrong projection
(BD-05). A different registered perturbation must keep both claims true.

---

## R-196 — M01.A12 bounds the ln φ block's homogeneity, Gibbs–Duhem and symmetry by 10⁻¹² × its largest scaled entry

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01 spec Amendment 1; Proposed with ADR 0026 |
| Normative text | `docs/derivations/M01-spec.md` §9.3 A12, §19 item 3; ADR 0026 Amendment 1 A1.3 |
| Evidence | build lane at `13bcef7`: Gibbs–Duhem 1.0 × 10⁻¹³ at V1 under the draft's self-normalization; re-measured at the same commit: ≤ 2.5 × 10⁻¹⁶ M (Gibbs–Duhem), ≤ 3.8 × 10⁻¹⁶ M (symmetry), ≤ 2.9 × 10⁻¹⁷ M (homogeneity) |
| Affected packages | M01; any later provider whose derivatives are checked the same way |

**Decision.** Let J_ij = n_tot ∂ln φ_i/∂n_j and M = max |J_ij|. All three identities of the block are bounded by
10⁻¹² M. A computed J_ij carries a few ulp of the block's largest terms, not of its own size. By symmetry, a
Gibbs–Duhem column is a homogeneity row, so the two share one floor. V1's N₂ column has a magnitude of 1.0 × 10⁻⁴
against M = 0.078, so the draft's self-normalized floor sat only 10× below 10⁻¹². Homogeneity of Z, v and h keeps its
own row scale.

**Rejected alternatives, and why.** Keeping the self-normalization and loosening the tolerance to 10⁻¹⁰: that is the
same check on the wrong scale, and it would hide that the floor is set by M. Keeping 10⁻¹² self-normalized: it is
10× above the floor, against §9's 10³.

**Watch for.** An implementation with derivatives built from O(1) intermediates may sit nearer 10⁻¹⁵ M. That is
still ≥ 10³ below the bound.

---

## R-197 — `pr-c1-v1`'s request checks are ratified as built, except that a flash asked for derivatives is refused (`flash_derivatives_unsupported`), not ignored; two admissible roots are treated as three

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01 spec Amendment 1; Proposed with ADR 0026 |
| Normative text | `docs/derivations/M01-spec.md` §5.2, §5.3, §5.4 step 0, A50; ADR 0026 Amendment 1 A1.1, A1.2 |
| Evidence | generator claim PR-07 (the cubic at Z = B is −2B²); no caller in `src/` passes `derivatives` to `flash` |
| Affected packages | M01, M02 (its units call `flash` without derivatives) |

**Decision.** Ratified:
- a negative or non-finite flow, or a non-finite T or P → `out_of_domain`;
- an unknown property → `unsupported`, `unknown_property`;
- a wrong state length → `error`, `state_length`;
- a non-TP flash → `unsupported`, `unsupported_specification`;
- more than one admissible root → the three-root rules.

Replaced: a `flash` with non-empty `derivatives` → `unsupported`, `flash_derivatives_unsupported`.

**Rejected alternatives, and why.** Ignoring flash derivatives, as SYN-001 does: `FlashResult` has no field for them,
so an `ok` without them would read as an answer, and the same provider refuses undeclared derivatives in
`evaluate_phase` (A13). SYN-001 is not changed, because its identity is frozen. Refusing two admissible roots as
degenerate: that would give a discontinuous rule at a measure-zero set that no registered state reaches.

**Watch for.** The request-check order and the two-root case are ratified but not asserted (no registered state
has two defects or a near-double root).

**Correction (2026-10-08, M01 review F2; spec Amendment 2, §5.2, §20).** The rationale above for the two-root rule
was wrong about the cases it rested on. The two-root returns measured before the review were not a near-double root
split by roundoff but unconverged Newton iterates (one of them the real part of a complex pair, 0.222075 ± 2.8 × 10⁻⁸ i,
at pure NH₃, 400 K), and with them `evaluate_phase(LIQUID)` answered `ok` where the cubic has one real root.
`admissible_roots` now keeps a candidate only if it is a root to rounding, and a three-root branch left with fewer than
three deflates its best-conditioned root and solves the quadratic, so two distinct roots arise only as a genuine
near-double pair. The rule itself (more than one admissible root → the three-root rules) stands.

---

## R-198 — The C1 reactor boundary checks the inlet phase before the hard domain; `stream_enthalpy_refused` is `error`; `reactor_not_accepted(<stage>)` has a grammar and registered stages

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01 spec Amendment 1; Proposed with ADR 0027 |
| Normative text | `docs/derivations/M01-spec.md` §8.7, §8.12, A51; ADR 0027 Amendment 1 A1.1, A1.2 |
| Evidence | generator claim BD-06 (573.15 K > T_c,EOS(NH₃) = 405.55 K); M01.A30's F7 inlet |
| Affected packages | M01, M02 (the adapter returns `NotAccepted(<stage>)`) |

**Decision.** The order is:
1. component set;
2. zero flow;
3. inlet flash (provider refusals pass through);
4. trace;
5. hard domain;
6. evaluation;
7. pressure;
8. defect;
9. enthalpies;
10. `ok`.

A provider refusal of an enthalpy flow is `error`, `stream_enthalpy_refused`. `<stage>` matches `[A-Za-z0-9_]+`, and
the registered stages are `S1`, `S2`, `S3`, `certificate`, `backflow` and `nonpositive_flow`.

**Rejected alternatives, and why.** The hard domain first: no liquid exists inside it, so `liquid_at_reactor_inlet`
would be dead. `out_of_domain` or `not_converged` for an enthalpy refusal: the request was admissible and the
evaluation converged, so the boundary failed to form its answer.

**Watch for.** If the hard domain is ever widened below NH₃'s T_c,EOS, the inlet-phase check becomes reachable
inside it, and the order still holds.

**Amendment (2026-10-08, M01 review F3; spec Amendment 2, §8.12, §20).** A step is inserted between 1 and 2: the
inlet's nTP-v1 state space (every flow finite and ≥ 0, T and P finite and > 0), else `out_of_domain`. The order
above dormant-tested first, so (0.5, −0.5, 0, 0, 0) answered `ZERO_FLOW` and an all-zero inlet with T = NaN answered
`ok`. The order is now eleven steps; the inlet phase still precedes the hard domain (BD-06 unchanged). A negative
flow, M01.A51 (iii)'s state, is now the boundary's own refusal, and A51 (iii) holds the flash pass-through with a
refusing provider.

---

## R-199 — The stand-in `c1.reactor_standin` is labelled synthetic in the frozen `ModelManifest`'s own fields and in every result's `identity.synthetic`; it is not in the v0.2 envelope at M01

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01 spec Amendment 1; Proposed with ADR 0027 |
| Normative text | `docs/derivations/M01-spec.md` §8.13, §8.14, A49, Q-N5; ADR 0027 Amendment 1 A1.3 |
| Evidence | `schemas/model-manifest.schema.json` (`additionalProperties: false`, no `synthetic`); T08 U04 (`model_unsupported(<id>)`) |
| Affected packages | M01, M02 (decides whether the stand-in is bound), M07 (the 0.2.0 envelope) |

**Decision.** The label lives in four places:
- the manifest's `title`;
- its `description`, which begins `SYNTHETIC`;
- its first limitation, which begins `SYNTHETIC:`;
- `identity.synthetic: true` in every `ok` result, which is the machine-readable form.

There is no schema change. The stand-in is not in `MODEL_BUILDERS`, so the envelope's `unit_models` axis (T08.A20)
stays true and U04 refuses it. If M02 binds it, the envelope lists it as synthetic, with a limitation saying it
certifies nothing about the reactor. It is never listed as a supported reactor model.

**Rejected alternatives, and why.** Widening `ModelManifest` with a `synthetic` field: a frozen-schema migration for
one test model (Q-N5 keeps the question open for Frank). Listing the stand-in in the envelope now: the envelope
describes what a revision can use, and a revision cannot use it.

**Watch for.** Evidence citing a reactor result must carry its identity. A W21 claim built on a result with
`identity.synthetic: true` is invalid.

---

## R-200 — M02 reproduces the probe bitwise at the evaluation (the record's tube inputs), within 10⁻⁶ through the boundary; the probe record is a gate-checked regression record, never re-run by the gate

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | design lane (`specifier`), M01 spec Amendment 1 item 9 (from the session's M02 recon); Proposed with ADR 0027 |
| Normative text | `docs/derivations/M01-spec.md` §8.15, A47, A52, §10.1, Q-F4, Q-F5; ADR 0027 Amendment 1 A1.5 |
| Evidence | `reactor-probe.json` `pinned`: §8.3's mapping of `inlet_n_mol_s` gives Σn 1 ulp below `F_ret_in_mol_s` and four of five y_i 1 ulp off `y_in`; `derived_from_measured.probe_sha256` already pins the record through M01.A34; claim DX-01 |
| Affected packages | M01 (A52), M02 (the adapter half of A41–A48, the Q-F4 sweep, Q-F5), M07 |

**Decision.** M01.A41–A48 each have a record half and an adapter half.
- The record half is M01's. M01.A52 checks it in the gate on the committed record, whose bytes A34 already pins.
- The adapter half is M02's. It runs as evidence-manifest rows in the probe's kind of environment, not in the
  default gate.
- A47 (a), bitwise: M02's `ExternalEvaluation` with the record's (F, y, T_in, p_ret_out), when the environment block
  is equal to the record's.
- A47 (b), 10⁻⁶ relative: through the full boundary, or in another environment with the same pins.
- Every reactor result's discretization estimate is `derived_from_measured.discretization_estimate`.
- Q-F4's sweep is 16 corners plus the centre at num_z = 800.

**Rejected alternatives, and why.**
- Bitwise through the boundary: unachievable, because the record was made from (F, y) and not from n.
- Re-recording the probe from n: that re-runs a validated record to fit a test.
- Leaving the record unread by tests: the spec's claims about it would rot silently.
- Running PyMRM in the default gate: the gate has no PyMRM dependency, by ADR 0027 D5's out-of-process design.

**Watch for.** Q-F5: the per-tube flow is not bounded by the hard domain. M02 adds the bound or measures it. §10.1's
T_out range was corrected to 1.2–1.7 K (the draft printed 1.3).

---

---

## R-216 — T08's CHANGELOG-limitations test compares the v0.1.0 release notes with the envelope as v0.1.0 released it, not with v0.2's working envelope

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | The build lane (session), on the M06 WO-12 engineer's escalation |
| Normative text | This entry; R-193 |
| Evidence | `3c04037` `tests/test_t08_w4_changelog.py::test_every_registered_limitation_is_named_and_no_other` (reads the envelope at `PUBLIC_ROOT`, the bytes released at v0.1.0 = v0.1.1) |
| Affected packages | M01, M02, M03, M06 (every v0.2 package that adds envelope rows), M07 |

**Decision.** The test checked the v0.1.0 CHANGELOG's limitation notes against the *live* envelope. Since R-193 that
envelope is v0.2's working one, so any v0.2 row (M06's L-WEB-1…4 first) failed it. The test now reads the envelope as
v0.1.0 released it. Its exact comparison is unchanged. v0.2's notes are checked against v0.2's envelope by the v0.2
release gate (M07, finalising `v0.2-envelope-1`).

**Rejected alternative, and why.** Naming v0.2 rows in the v0.1.0 notes: that rewrites a release record. Adding no
envelope rows for new capabilities: T08.A20 requires them.

**Watch for.** The v0.2 gate must add the matching check for the 0.2.0 notes; until then, v0.2 rows are unchecked
against any CHANGELOG.

---

## R-217 — T08's manifest-count and review-table tests are scoped to the v0.1 packages (P, K, T); v0.2 manifests are covered by the harvest-completeness check and the v0.2 gate

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | The build lane (session), on the M01 WO-7 engineer's escalation |
| Normative text | This entry; R-193, R-216 |
| Evidence | `7e0eb67`: `tests/test_t08_w2_support_envelope.py::test_a21` (the quoted size, 18 manifests and 232 limitations, applies to P/K/T; `len(harvest) == len(items)` still covers every manifest) and `test_the_review_table_is_every_manifests_status` (P/K/T compared with CHANGELOG's v0.1.0 table) |
| Affected packages | M01–M07 (every v0.2 evidence manifest) |

**Decision.** Both tests pinned facts of the v0.1.0 release: its manifest count and its CHANGELOG review table.
Every v0.2 manifest broke them. They now check the v0.1 packages' records exactly as before. The completeness rule
(every manifest limitation and non-pass check has a harvest row) still applies to all manifests, v0.2's included.

**Rejected alternative, and why.** Adding v0.2 manifests to the v0.1.0 CHANGELOG table rewrites a release record.
Exempting v0.2 manifests from the harvest: T08.A21's completeness rule is the useful half and stays universal.

**Watch for.** The v0.2 gate (M07) must add the 0.2.0 counterparts: the review table in the 0.2.0 notes, and the
v0.2 manifest count.

**Amendment (2026-10-08, M01 review F1).** A third test pins the v0.1.0 release record:
`tests/test_t08_w4_changelog.py::test_every_registered_limitation_is_named_and_no_other` required the v0.1.0
CHANGELOG section to name exactly the envelope's limitation rows, so the first row added after the release (L42,
`pr-c1-v1`'s caveat) broke it. It is scoped the same way: the section names the rows registered at v0.1.0, and the
rows added since are an explicit list in the test (`ADDED_AFTER_V0_1_0`), each required to exist in the envelope.
Rejected: naming L42 in the v0.1.0 section (rewrites a release record, as above). M07's 0.2.0 notes must name the
listed rows.

**Merge note (2026-10-08, M06 into main).** R-216 (M06) scoped the same test by reading the envelope as v0.1.0
released it (`PUBLIC_ROOT`), where L42 and every later row are absent, so the comparison is exact with no exception
list. The merge keeps R-216's form and drops `ADDED_AFTER_V0_1_0`, which would have failed against the released
envelope (L42 is not a row of it). The obligation stands: M07's 0.2.0 notes name L42 and every other v0.2 row,
checked by the v0.2 gate (R-216's Watch for).

---

## R-219 — One declared exception to T08's "no walk-up" rule: the C1 records fall back to the source checkout only when the package-data entry is absent

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | The build lane (session), on the M01 review's Closure note (`docs/reviews/M01-review.md`, `9098f14`) |
| Normative text | This entry; M01 spec §20 (Amendment 2, F4); Q-N4 |
| Evidence | `f1877ec` (`thermo/pr_c1.py` `load_records`; tests simulating the absent entry); the exception named in `tests/test_t08_w4_package_data.py`'s docstring |
| Affected packages | M01, M02 (anything reading the C1 records) |

**Decision.** T08's rule is that installed code never walks up the tree to find repository files. The C1 records
have one exception: if `PACKAGED` has no entry for them (which only happens if Frank declines Q-N4 and `1621d65` is
reverted), `load_records` reads the source checkout's copy. Outside a checkout it raises `FileNotFoundError` naming
Q-N4. In the shipped configuration the entry is present, so the fallback never runs.

**Rejected alternative, and why.** No fallback: declining Q-N4 would then break the provider outright, which was the
review's F4. A user-supplied path for installed packages is not built; Q-N4 says so.

**Watch for.** If Q-N4 is declined, an installed package without the records raises rather than refusing with a
typed result. Revisit with Frank's answer.

---

## R-283 — W27 maps the six C1 units as their SYN-001 namesakes with no token, both C1 reactors to no function, and `pr-c1-v1` to `cubic_pr`

| | |
| --- | --- |
| Date | 2026-10-09 |
| Decided by | Design lane (`specifier`), M06, W27 registration Amendment 2 |
| Normative text | `docs/derivations/M06-W27-registration.md` §21.1–§21.2; `benchmarks/m06/openidaes450/registration.json#/units/model_functions`, `#/routes/provider_methods` |
| Evidence | GC-MODEL-1/2, GC-A2-1/2/5/6; W27-A16-a…h; `wp/M02` `2587f14` signatures and manifests |
| Affected packages | M02 (join commit, R-280 (d)), M06, M07 |

**Decision.** `c1.feed_source`, `c1.product_sink`, `c1.adiabatic_mixer`, `c1.tp_heater`, `c1.tp_flash`, `c1.stream_splitter`
perform their SYN-001 namesakes' functions and offer no token. `c1.reactor` performs no function (`fixed_design_reactor`:
one pinned geometry, catalyst, coolant and kinetics no case JSON can establish); `c1.reactor_standin` performs none
(`synthetic_stand_in`, R-199). `pr-c1-v1` is `cubic_pr`; its vapour-only light gases are a per-component phase admission.

**Rejected alternative, and why.** Phase tokens for the vapour-only heater and mixer and the LIQUID-less flash (no case
option expresses them; port phases are unchecked by registration, as for SYN-001's liquid-only units; GC-A2-5 shows they
separate no archive case). `c1.reactor` as `kinetic_reactor` (it is not a CSTR) or a new `plug_flow_reactor` function
(re-keys a default-none archive key for no class change). A separate `cubic_pr_vapour_only` method (duplicates W27-R20).

**Watch for.** A sampled candidate whose C1 units meet a liquid or a light-gas-free feed: §7's scripted build catches it.

---

## R-284 — W27 judges units on the serving route's models, and refuses snapshots that rule cannot judge

| | |
| --- | --- |
| Date | 2026-10-09 |
| Decided by | Design lane (`specifier`), M06, W27 registration Amendment 2 |
| Normative text | registration §21.3 (W27-R62, W27-R24 (d)–(e)) |
| Evidence | GC-A2-4 (no class changes at the hypothetical v0.2; `ngfc_atr`'s reasons change); W27-A16-c/d, A17–A19 |
| Affected packages | M06 (WO-16h), M07 |

**Decision.** When one route serves a case's single method group, its units are judged against that route's `model_ids`
only (`units_judged_on`); otherwise against every model, as before. A snapshot with `routes_per_revision ≠ 1`, two
routes of one method, a route model not among the models, or a model on no route is refused.

**Rejected alternative, and why.** Units on every model whatever the route: a revision binds on one basis, so that counts
a composition across bases as coverage (W27-A16-c). Evaluating each route and keeping the best: needless while a
method has one route, which the refusal now makes explicit.

**Watch for.** A second route of an existing method (a second PR provider): an amendment, not a code change.

---

## R-285 — W27's v0.2 snapshot reading is chosen by what the binder exposes (`SELECTABLE_BASES`, `MODEL_BASES`), not by version

| | |
| --- | --- |
| Date | 2026-10-09 |
| Decided by | Design lane (`specifier`), M06, W27 registration Amendment 2 |
| Normative text | registration §21.4 (W27-R63), §21.8 J1–J6 |
| Evidence | `wp/M02` `2587f14`: `__version__` `0.1.1`; `record_source` selects the basis; SYN-001's builders bind on the C1 basis (probe of §21.4) |
| Affected packages | M02 (join commit), M06 (WO-16h), M07 |

**Decision.** `bases-v1` reads one route per basis of `SELECTABLE_BASES`, its models from `MODEL_BASES` (the table the
binder's own `model_unsupported` refusal reads); the 0.1.1 reading applies only to a binder without `basis_provider`;
anything else refuses. Whether SYN-001's builders bind on the C1 basis is M02's (F-A2-1; default no); W27 reads either.

**Rejected alternative, and why.** Readings keyed by version (the joined binder still says 0.1.1 and would be read as one
SYN-001 route, silently). Probing every (model, basis) with a minimal revision (fragile, slow). Listing `c1.*` on
`pr-c1-v1` by prefix (a hand list; wrong if SYN-001's builders stay unguarded).

**Watch for.** The join's live snapshot differing from both registered expectations (J3): stop, amend.

---

## R-286 — Ruling on W27 Amendment 1: the erratum, W27-R60 and W27-R61 ratified; W27-R59 amended so a matched item is never contradicted

| | |
| --- | --- |
| Date | 2026-10-09 |
| Decided by | Design lane (`specifier`), M06, W27 registration Amendment 2, on the M06 review F5 |
| Normative text | registration §21.6 |
| Evidence | `access_report.json` (9 inaccessible assets); GC-SCORE-1 (13 cases with an alias naming an available unit and an unavailable reason); GC-SCORE-2; `scorer.judge_limitation` on `ngcc_gas_turbine_subflowsheet` (`Mixer`: matched and contradicted, as built) |
| Affected packages | M06 (WO-16h scorer, before WO-17's first canary) |

**Decision.** "Nine" stands. A quantity at several time points is unjudged; a reference component the product stream
lacks is 0 mol/s. W27-R59 holds with one addition: an item that matches a recorded reason (W27-R40) is not contradicted.
Scorer states W27-S19, S20.

**Rejected alternative, and why.** Ratifying W27-R59 as built: in 13 cases a correct, matching item would also count as a
semantic error. Dropping the lenient matching instead: W27-R40 is lenient on purpose (R-177).

**Watch for.** Semantic-error counts computed before WO-16h: re-score; no outcome class moves.

---

## R-301 — W27 Amendment 3: `c1.reactor_surrogate` performs no function, for a new reason `surrogate_model`; J3–J6 compare a surrogate-carrying build with `hypothetical_v02_a3`

| | |
| --- | --- |
| Date | 2026-10-09 |
| Decided by | design lane (`architect`), batched ruling round M05/M04 (B1) |
| Normative text | `docs/derivations/M06-W27-registration.md` §22.1–§22.3, §22.5 |
| Evidence | `wp/M04` `2841cd3`: `RefusalError: unregistered model ids ['c1.reactor_surrogate']` (W27-R24 (a)); 4 tests in `test_m06_w27_coverage` fail; `list_models` `f070fbe0…`, 22 models, 9 on `pr-c1-v1` |
| Affected packages | M06 (W27), M04 |

**Decision.**
- *The row.* Function null, offers [], `why_none` = `surrogate_model`: a fitted surrogate of one parent on one box,
  which no case JSON can identify.
- *The generator.* It keeps the id in `M04_MODEL_IDS`, so GC-MODEL-2 is unchanged.
- *The snapshot.* `hypothetical_v02` is not re-pinned. A build carrying the surrogate compares with
  `hypothetical_v02_a3`: the same snapshot plus the id in `models` and in `pr-c1-v1`'s `model_ids`. That snapshot must
  classify identically, case by case (GC-A3-2).
- *Re-taking.* `list_models`, the snapshot SHA-256 and `coverage.json` are re-taken at the merge (G14). Preflight's pins
  are re-taken with the registration.

**Rejected alternative, and why.**
- `fixed_design_reactor`: it describes the parent, not a fit.
- `synthetic_stand_in`: it is not a closed-form stand-in.
- Inheriting the parent's function: a box-limited fit is never a model of an arbitrary case unit (W27-R01).

**Watch for.** A future surrogate whose parent has a function. It still maps to none, under this reason.

---

## R-302 — Corpus tests that bind every builder get a fixture-only `SurrogateResolver`, not an exclusion list

| | |
| --- | --- |
| Date | 2026-10-09 |
| Decided by | design lane (`architect`), batched ruling round M05/M04 (B1) |
| Normative text | `docs/derivations/M06-W27-registration.md` §22.4 |
| Evidence | M04 build decision E5: the registered builder refuses without a manifest; WO-7's unit tests bind the A19 fixture manifest |
| Affected packages | M04, M02 (corpus tests) |

**Decision.** The resolver maps SHA-256 to committed fixture manifests only. Its one entry is
`tests/fixtures/schemas/surrogate_manifest/valid/a19_smooth_prefix.json`. A builder that fails to bind is a failure,
never a skip.

**Rejected alternative, and why.** Excluding manifest-needing builders: the corpus would stop exercising a registered
builder (no removed cases).

**Watch for.** A new builder that needs external configuration. It gets a resolver entry, not an exclusion.
