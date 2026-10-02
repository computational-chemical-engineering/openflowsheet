# ADR 0008 Amendment 1: design-lane review

**Reviewed:** `main..5a61f37` on `adr/transient-readiness-2`, which is the brief (f4e2f6d), Amendment 1
A1.0–A1.8 (f82dfdc), and work orders W1–W3 (5a61f37). **Reviewer:** design lane (`reviewer`),
2026-09-26. **Verdict: approve with fixes.** There is one must-fix, and it is a one-line change
to the status line. No finding touches numerics, and no finding asks for a hashed file to change.

**What I ran:** `pytest tests/test_adr_0008_transient_readiness.py`, which gave 44 passed with
`process_runtime` resolved inside the worktree. I also ran a discovery probe, which confirmed that
U1 sees all twelve `MODEL_ID` modules. I did not rerun the full suite. I accept the reported
figure of 3145 passed and the empty `git diff --stat` over the hashed trees.

**What I checked against the source:** the files that enter identity. These are the twelve
self-hashing `models/syn001/*.py` modules and `thermo/syn001.py`. `rows.py`, `tp_state.py` and
`ph_kernel.py` do *not* enter identity. I also checked `structure_sha256`'s coverage
(`canonical.py:377`), which is variable, equation and parameter ids plus row kinds only. Beyond
those I checked the reactor's configurations (`conversion_reactor.py:218-242`), the HX, flash and
heater holdup rows, SYN-001's `h`, `lnK` and `V_MOLAR` (`thermo/syn001.py:288-316`), the
Specification schema's `oneOf`, the mixer and splitter pressure rows, the `graph/dof.py`
diagnostic, the `WarmStartCache` scope, the CasADi parameter baking (`casadi_backend.py:326`), and
the importers of `mass.py`.

---

## Findings (most severe first)

### F1 — must-fix: the amendment comes into force without Frank's approval

`docs/adr/0008-transient-extension-readiness.md:582` says the amendment is "In force once W1–W3
land, check.sh passes …, and the design-lane `reviewer` has reviewed." None of those conditions
is Frank's approval. This review satisfies the last one, so once it lands, J1–J4 would bind T07
while Q-A3 ("Are J1–J4 within T07's scope?") is still open with Frank. T07 is the next package
and may start in another session. The brief (§8) and W4 (`:687`) both make Frank's approval the
acceptance step. ADR 0008 itself was in force only because Frank had directed it (`:3`).

**Correction.** "In force on Frank's acceptance (W4), once W1–W3 have landed, check.sh passes and
the reviewer has reviewed. Until then U1/U2 stand as ordinary tests and J1–J4 are advisory to
T07."

### F2 — should-fix, needs a decision: rigidity is presented as the reason `U` is correct; it only fixes the row's form, and the isobaric case is excluded without being named

The anchors are `:634-635` (U–H.1/U–H.2), `:661` (Q-A1) and `mass.py:25` ("A physical vessel is
rigid").

`U` is the first-law energy content of *any* control volume. For a moving boundary the balance is
`dU/dt = F_energy − P dV/dt`. For a rigid one it is `dU/dt = F_energy`. Rigidity therefore decides
only that the dynamic energy row equals the steady row. It does not decide *what* is held.

There are two consequences.

- **(a) Q-A1 misstates what a "no" costs.** The amendment says a "no" is "a hash-moving model
  edit under a new ADR". It is not. A non-rigid unit still holds `U`. What changes is the dynamic
  variant's row, which gains a `−P dV/dt` term. The steady manifests do not change.
- **(b) The isobaric variable-volume case is excluded but never named.** This is a liquid holdup
  with a level under a pinned pressure: the common "flow-driven" simplification for tanks and
  CSTRs. Its natural conservative form holds `H = U + P V` with `P` constant in time. U–H.5's own
  algebra, with a physical rather than a pseudo volume, keeps `M` a constant 0/1 selection. The
  alternative is `U` plus a state-dependent `−P dV/dt` accumulation term, which breaks U–H.4's
  constant `M`. U1 forbids any enthalpy holdup in `process_runtime.models`, so together U–H.4 and
  U1 exclude this formulation outright.

The physics of the amendment is right for the five units. Drums, shells, tubes and a reactor
vessel are rigid, so Q-A1's default of "yes" is correct.

**Correction (my recommendation).** Keep U1 and the ruling. Reword U–H.1 and U–H.2 so that `U`
is the held energy in general and rigidity is the premise under which the row stays the steady
row. Reword Q-A1's consequence to say that a "no" moves no steady file. Add one clause to U–H: an
isobaric variable-volume control volume is a distinct model kind that holds `H` at its pinned `P`
(P never a state), and it is admitted only by an ADR that amends U1. Frank decides whether TX's
first release admits it. My default is no.

### F3 — should-fix: X4's acceptance gate is blind to the kernels X4 tells TX to share

The anchors are `:611` (X4) and `heater.py:189-190`. Each model's `artifact_hash` is the file hash
of the model's own module and nothing else. `models/rows.py`, `syn001/tp_state.py`,
`syn001/ph_kernel.py`, `bisection.py`, `saturation_band.py`, `models/__init__.py` and
`syn001/__init__.py` enter no identity.

X4 tells the dynamic variant to share the `rows.py` builders. Its gate checks only that the twelve
steady modules and `thermo/syn001.py` are unchanged, plus a bitwise equality between steady rows
and dynamic rows. Suppose TX edits `rows.py`, for example by adding a parameter to a builder.
The steady numerics would change, and nothing in the gate would notice:

- the steady modules' bytes stay the same;
- both variants call the edited builder, so the bitwise equality still holds;
- no identity moves.

This also weakens C4's reason (1). Keeping the dynamic form out of `heater.py` only moves the
editing pressure onto files that no identity covers.

**Correction.** Add to X4's gate: "the shared kernel modules are unchanged across TX's merge, or
every test that pins a SYN-001 digest, certificate or replay passes unmodified". The second
clause is A1.7 gate 2 restated for TX. It is the only check that catches drift in the shared
kernels.

### F4 — should-fix: X4 and X1(d) contradict each other

X1(d) (`:605`) lets TX add the property `v` to SYN-001 "as a registered digest migration under its
own ADR". X4 (`:611`) requires the `git diff` over `thermo/syn001.py` to be empty across TX's
merge. TX cannot take the first route and pass the second gate.

**Correction.** Exempt that migration from X4's gate: "empty, except for an X1(d) migration made
under its own ADR". Alternatively, drop the migration route from X1(d) and keep only "a new
provider".

### F5 — should-fix, needs a decision: J2 goes beyond what readiness requires, and one clause works against the trajectory case

The anchors are `:617-622`. J1 is necessary and correctly argued: cardinality is the one choice
that is cheap now and breaking later. J2's "any number of output events before the terminal one"
and J3 are cheap and justified. The rest of J2 is T07's own lifecycle design, and T07 is a
Build-led package (plan `:245`):

- **"Progress members are operation-neutral counts … solver quantities stay in solve events."**
  The natural progress measure of a trajectory is simulated time against `t_end`, a real number.
  This clause forbids it, or forces an ADR to reverse it. That undercuts J3's claim that a
  trajectory operation is merely "an added value and branch".
- **"Exactly one terminal event, nothing after it."** Combined with the blueprint's
  checkpoint/resume requirement, this means resuming a cancelled or failed job has to be a new
  job. That is a defensible design, but T07 should make the choice. It has nothing to do with
  transients.
- **Closed enums on response-side `kind` values** (J1 artifact kind, J2 event kind). An added
  value is "additive, no instance changes" for stored documents. It still breaks a client that
  validates responses or matches exhaustively on `kind`. That is the same kind of client breakage
  C6 uses to justify J1.
- **Overstatement.** "Cardinality cannot change additively" is too strong: a list member can be
  added beside a deprecated single one. The ruling survives this, because J1 is simply cheaper now.

**Correction (recommended).** Keep J1, J2's streaming clause (outputs may precede the terminal
event; one terminal event ends the stream) and J3 as binding. Demote the dense-sequence rule, the
progress-member rule, "nothing after terminal" and J4 to recommendations for T07. Add one binding
reader rule: consumers ignore unknown artifact and event `kind` values, except that an event
marked terminal is always terminal. Trim acceptance (b) to match.

### F6 — should-fix: U1 silently skips any model module whose `EQUATIONS` has an unrecognised shape

The anchor is `tests/test_adr_0008_transient_readiness.py:384-385`. A module that has a `str`
`MODEL_ID` but builds `EQUATIONS` as a list, from a factory, or as a mapping to lists hits
`continue`. The registered-set check protects only the twelve known rows. The rows U1 exists to
police in future are TX's dynamic variants, and those are exactly the ones that could arrive in a
new shape and never be checked.

**Correction.** In `unit_library_holdups`, fail when a module defines a `str` `MODEL_ID` and its
`EQUATIONS` matches neither accepted shape. This is one assert.

Optionally, and cheaply, also assert on the Python library the relation that M2 pins only on the
YAML fixtures: row dimension equals holdup dimension with the time exponent lowered by one. That
is the one physical link a 0/1 `M` relies on.

### F7 — note: U1 is a meaningful invariant; U2 is a tripwire, and its claim should say so

**U1.** The manifest distinguishes `U` from `H` only through the symbol and the prose, because
both have dimension `ENERGY`. A structured discriminator would edit all twelve hashed modules, so
a string pin is the right-sized pin under the brief's constraint. It breaks only when text that is
itself part of each model's hashed identity is reworded, and such a rewording is already a
deliberate, identity-moving edit.

**U2.**

- **What it pins:** the set of modules that *import `mass.py` directly*.
- **What it misses:**
  - use through `region.py` or `executor.py` APIs, which is the path X5 legitimately gives TX for
    consistent initialisation;
  - an integrator placed inside those two modules;
  - `importlib.import_module(".mass", "process_runtime.orchestrator")`.
- **Wording.** The `mass.py` docstring's "(U2) pins who does" is accurate only for direct
  imports.
- **Stronger anchor.** `mass.py`'s own `HoldupQuantity` value `"enthalpy_content"` and
  `MASS_POLICY = "T04-residence-time-v1"` already separate the two at the type level.

**Suggestion.** Add to X3/X8 a positive TX acceptance item: the physical `M` is built from the X8
map alone, has entries exactly 1.0, and carries no `MASS_POLICY`. That item states U–H.4 directly
rather than through the import graph.

### F8 — note: C4's ruling is right, but reasons (2)–(3) and the stated precedent line are inaccurate

The anchors are `:611` and `conversion_reactor.py:218-242`.

The reactor's two configurations already change one parameter id: `<U>.T_spec` versus
`<U>.Q_spec`, with dependencies `outlet.state.T` versus `duty.Q`. The configurations therefore
already give *two `structure_sha256` values, and two `model_version`s,* under one `model_id` and
one `artifact_hash`. Consequences for the argument:

- Reason (2) ("another `structure_sha256`") does not distinguish a mode from this precedent.
- The line "adding … parameters makes a new model" contradicts the precedent unless it reads
  "beyond swapping which pinned specification one algebraic row reads".
- Reason (3) is weaker than stated. The holdup rows keep their equation ids across a mode, and PTC
  would not run on a dynamic mode anyway.

The decisive reasons are that ownership changes (holdup columns, closure rows, a volume parameter,
pressure semantics) and that the certified modules must stay byte-identical. Subject to F3, those
suffice. I agree with the ruling: a separate model sharing kernels, with no refactoring now.

### F9 — note: the C7 schema fragment, as quoted, accepts `value` together with `schedule`

The anchor is `:624` against `schemas/specification.schema.json`. The existing branches are
`{required:[value], not:{required:[bounds]}}` and the mirror for `bounds`. Take a document
`{value, schedule}`:

- it matches branch 1;
- it fails the proposed branch 3, because of branch 3's own `not`;
- so `oneOf` holds, and the document is valid.

The migration must also add `schedule` to both existing branches' `not`, and add `schedule` to
`properties`, because the schema has `additionalProperties: false`. No existing instance changes,
so the ruling ("additive later") stands. The exact text is what would be wrong if TX copied it.

### F10 — note: X8's structure-document member must be omitted when empty

The anchor is `:626`. `structure_document` hashes every member it emits. If the row→holdup map is
emitted as `{}` for steady models, every SYN-001 `model_version` moves. X8 should say "absent when
the problem has no holdup column".

### F11 — note: two precision points in X1 (C1)

The anchor is `:605`.

- **(a)** X1(a) should require that `v` be thermodynamically consistent with `h` and `lnK`:
  `∂h/∂P|_T = v − T ∂v/∂T`, and a Poynting or fugacity term in `lnK` built from the same `v`.
  SYN-001 already satisfies this (`h^L = c_p(T−T_r) + v_i(P−P_r)`, and the `lnK` Poynting term
  uses `V_MOLAR`). A future provider might not, and a UV closure on an inconsistent triple still
  conserves `U` but gets the pressure response wrong.
- **(b)** A "native provider UV flash … as an accelerator" (X1(c)) needs `FlashRequest` widened to
  carry `U` and `V` targets. That is a frozen-interface ADR, and X1(c) should say so. It is not
  needed now.

### F12 — note: U–H.7 is SYN-001's default case, and its second remedy has index 2

The anchor is `:642`. SYN-001's liquid molar volume is a constant (`V_MOLAR`). Every liquid-full
SYN-001 vessel is therefore in the U–H.7 case: the heater with liquid, and the HX liquid sides.

U–H.7's alternative, "determines `P` from flow–pressure rows", gives an **index-2** DAE.
`Σ v_i N_i = V` holds only on the differential states, and `P` enters only after that relation is
differentiated once. The amendment should say this, so that TX does not assume index 1 and so
that X8's structural analysis is required to detect it. It also bears on Q-A2's default.

---

## Answers to the five questions

1. **The U–H constraint.** It is correct and sufficient for rigid volumes, including the
   exchanger's two sides (U–H.6, which matches `HX-energy-hot` and `HX-energy-cold`, each with its
   own `Q` sign) and the vapour–liquid drums (common `(T,P)`, with the outlets drawn from the
   holdup phases). The conservative-form argument (U–H.4) is right: in conservative form,
   amount and energy are conserved exactly at every step, whereas under `M(x)ẋ` conservation is
   lost to truncation error. "Rigid" is the correct physical premise for the five units, but it is
   not what makes `U` correct (F2), and U–H.7 has index 2 (F12).
2. **C4.** The ruling is correct. The identity argument is weaker than written, because the
   reactor already has two `model_version`s under one `model_id` (F8). Kernel sharing escapes
   X4's gate (F3), and X4 contradicts X1(d) (F4).
3. **J1–J4.** J1, J2's streaming clause and J3 are necessary and minimal. The rest of J2, and J4,
   over-constrain a Build-led package. J2's rule that progress is counts only works against
   trajectories (F5).
4. **The rejections.** None of the "already additive" claims is wrong in the sense that matters:
   none reopens every unit model or a frozen interface.
   - C2 is stronger than argued. The mixer and splitter already state node pressure equalities,
     and `dof.py` books them as local excess.
   - C5: `WarmStartCache` is never instantiated in `src/`, so the only cache that can outlive a
     solve is the exact cache.
   - C7 needs a corrected fragment (F9).
   - C8 needs "omitted when empty" (F10).
   - C1's accelerator path would widen `FlashRequest` (F11b), but that path is optional.
   - C9 and C10: agreed.
5. **The tests.** U1 pins U–H.1 as far as the manifest can express it, which makes it meaningful
   rather than brittle, apart from the skip hole (F6). U2 pins direct importers only (F7). U1b
   and U2b demonstrate that the detectors can fail, but not that U1's discovery driver can. The
   registered-set assertion covers that for the twelve known rows.

## Not examined

- The T04 §6.2 derivation itself (taken as settled, R-032).
- CasADi's constant folding for Q-A4.
- Whether the YAML manifest fixtures still match the Python `EQUATIONS`: M-group and U1 read
  different sources.
- The `wp/T06` branch.
- The draft register text of A1.8, beyond its consistency with the rulings.
