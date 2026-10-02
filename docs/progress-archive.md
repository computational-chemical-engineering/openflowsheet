# Progress archive

Closed narrative moved out of `docs/progress.md` on 17 September 2026, so that the file a session
reads at startup states the current position rather than the history that produced it
(`CLAUDE.md`, "Authority"; the context-discipline rule that a note holds the current state and why,
not the story of how it got there).

**This file is not read at session start and is not an authority.** It is kept because these notes
record what was asked, what was answered and what was measured during P00, P01 and P02, which a
later session may need to grep for a specific question. Everything here is closed; anything still
open lives in `docs/progress.md`. Where a statement here was true when written and is no longer
true, it is left as written and the correction is in `docs/progress.md` — this is a record, not a
maintained description of the repository.

Authoritative status for every package is its evidence manifest under `evidence/<package>/`, and
the decisions are in `docs/adr/` indexed by `docs/decision-register.md`.

---

## P02 as it stood at completion (was "Current package")

## Current package

**P02 — matched CasADi and Pyomo/PyNumero/ASL spikes — complete and tested.** Plan §4.1 row P02,
§8.1 days 3–7. Requirements D02, D03 and A05 carry test node IDs and this evidence, and remain
`planned`: a package test is not requirement closure, and the backend selection is P03.

The specification is `docs/derivations/P02-composition-spec.md` (Fable), with
`benchmarks/p02/reference_values.yaml` generated at 40 digits by
`docs/derivations/scripts/p02_reference.py`. The compiled subsystem is a single flash of the fresh
feed in component flows, K-form equilibrium, with the two property callbacks entering through
lifted variables and defining rows: 17 variables, 17 equations, 60 structural nonzeros. Both
backends assemble that system natively and are judged by one code path in the repository
environment, on committed artifacts, with no backend installed.

**Results.** Worst deviation as a fraction of each assertion's own tolerance: assembled Jacobian
entries 0.0 (CasADi) and 2.0e-06 (Pyomo) over 360 entries each; the callback columns against the
independent P01 reference 1.7e-03 on both; fourth-order finite differences 6.3e-03 and 3.6e-04;
directional derivative 5.7e-04; Schur elimination 1.3e-05; cross-backend agreement 1.9e-04.
SuperLU on each backend's exported matrices: scaled linear residual 3.8e-17, affine rows after the
Newton step 7.4e-17 times their scale, recovered direction error 4.6e-15, and the registered
scaling brings the condition number from about 1e10 to about 1e2.

**What P02 established beyond passing.**

- Neither route falls back. Callback counts are exactly one value call per residual and one
  Jacobian call per assembled Jacobian on both routes. CasADi additionally calls each block's
  value method once per Jacobian, because its Jacobian callback takes the block's nominal output;
  PyNumero does not. The threshold for suspecting a finite-difference fallback is three value
  calls for block K and six for block H, so both routes are far below it.
- Both assemble exactly the declared pattern at every state, with the entries that vanish at the
  single-phase states stored and exactly zero, so structural and numerical zeros stay distinct.
- Second order through opaque callback Jacobians is **absent** on both routes, reported as a
  typed failure of the whole request rather than as zeros. The supplementary record shows CasADi
  returns exact second derivatives when the block ships symbolic derivative code. That is the
  answer to the blueprint's optional-Hessian question, and it is a capability fact for K01.
- A CasADi callback must implement `has_jac_sparsity` and `get_jac_sparsity`; without them the
  assembled pattern gains six stored zeros where block H declared structural zeros.
- PyNumero writes a grey-box output constraint as `f(inputs) − output`, the negative of the
  specification's orientation. The harness applies a declared row-sign adapter to the six defining
  rows and records the native orientation; the specification was corrected to say so.
- Five specification defects were found by review or implementation and amended by Fable rather
  than worked around: two registered states whose residual rows collided, an assertion stated for
  states where it is mathematically false, a floor borrowed from the other form, and the row
  orientation claim above.
- Three checks in the judge itself passed vacuously on absent evidence, and the Fable review found
  a fourth and worse case: every per-state loop skipped a record whose status was not `ok`, so a
  backend that failed the single-phase states entirely could still be reported PASS-composition.
  Coverage is now asserted before any deviation is compared, and four tests attack the judge:
  perturb one entry, return a structural zero as 1e-13, delete an artifact, and fail two states.
- The review also produced eight smaller corrections, all applied: a per-column tolerance where a
  flat floor had been three decades too loose on one column, a second-order check that accepted a
  record with no outcome, two checks that trusted numbers the harness had computed about itself,
  the perturbed state that carries the linear-solve evidence never being compared to the closed
  form, an echoed state hash now recomputed, and two fields of the frozen boundary type that
  defaulted to claiming exactness.


---

## P00 prerequisites and unverified items (was part of "Blockers")

## Blockers

None. No package is `BLOCKED`.

**Open questions from ADR 0008, none blocking.** The ADR registers four with recommended
defaults, applied as written. **Q1 is closed: Frank confirmed on 2026-09-16 that the SYN-001 heater
is a holdup unit**, so the registered `holdup_balance` classification (`HEAT-mole` → `N_i` mol,
`HEAT-duty` → `U` J) stands and no file changed. Q2 (K01 adds `row_accumulation`/`parameter_ids` at
schema promotion), Q3 (keep the name `constants_sha256`) and Q4 (no `conditional_class` constraint
on holdup rows) keep their defaults and are discharged by the named packages, K01 and T04.

P00 had no blocked prerequisite: Python 3.13.5, the four pinned runtime dependencies, pytest,
mypy and `python3 -m venv` were already present, and PyPI was reachable for `ruff==0.12.11` and
the two type-stub packages. Evidence: `docs/baseline-report.md` §4–§6 and the `commands` block
of `evidence/P00/07a7ff01fd2767f7ad34a6442c5a817536ac0a6d/manifest.json`, which records the
actual exit codes.

Two things are *unverified* rather than blocked, and are recorded as limitations in the P00
manifest:

- `.github/workflows/ci.yml` is committed but has never executed. No CI evidence exists.
- All checks ran on one platform (Debian 13, x86-64, Python 3.13.5). The two-platform structural
  identity required by gate **G05** is work package K05, not P00.


---

## Handoff and escalation notes

Notes between Fable 5.1 and Opus 5 (plan §1.3: escalation between models is a written note here
naming the blocker, the evidence, and the smallest change requested).

**Project agent definitions, 2026-09-16.** `.claude/agents/` now holds two project-scoped Fable
agents, because 19 of the 31 packages are Fable-led and their deliverables are scientific documents
and verdicts rather than software designs: `fable-specifier` authors derivations, ADRs and test
specifications with registered states, tolerances and numbered assertions, and `fable-verdict`
decides whether registered criteria are met given evidence. They carry the rules this project has
already paid for — expectations independent of what they judge, no tolerance without its step,
stencil and measured floor, no assertion satisfiable by an accidental zero, and every claim a
document makes about its own numbers enforced by its generator. The global `fable-architect` and
`fable-reviewer` remain the right agents for software design and for reviewing a completed
implementation; P02 used both. A newly added agent file is not addressable by name until the
session restarts; until then the fallback is a general-purpose subagent with the model set to Fable
and the agent's instructions supplied inline, which is how every Fable pass in P01 and P02 ran.

> **Superseded 2026-09-17.** Both project agents are addressable by name; `fable-specifier`
> authored ADR 0008 on 2026-09-16. The inline-instruction fallback is no longer needed.

**Opus session → Fable, P02 (2026-09-10).** The specification was reviewed before commit and
amended five times on measured evidence rather than worked around; the details are in the P02
commits and in specification §12 findings (i) to (vi). Two harnesses, one judge, one linear-solve
path. The Fable review of the completed implementation ran on 2026-09-10 and every finding is
applied in `507dccf` and `f4473a2`. Open items handed back to a later session: the specification's
open questions Q4,
Q5, Q6 and Q8 were resolved by taking its own recommended defaults (results committed under
`spikes/p02/results/`, envelope schemas kept as drafts under `spikes/p02/schemas-draft/`, the
`CompiledProblem` protocol introduced in `src/process_runtime/compiled.py`, and the repetition
counts kept as written). Q1, Q2, Q3 and Q7 were settled by measurement and are recorded in the
specification.

**Working-protocol change, 2026-09-10 (recorded, not decided by an agent).** Frank's model
routing policy changed: a session now runs on Opus 5 and Fable 5.1 participates as design and
review subagents rather than driving a session. Effect on plan §1.3 and the §4.1 *Model* column,
stated plainly so a later session does not read a silent deviation: for a Fable-led package the
scientific decisions remain Fable's — the P02 composition test specification is written by a Fable
design pass and committed as the authority the harness implements — but **the branch and the
evidence manifest are owned by the Opus session**, not by a Fable session. The substance of §1.3
is preserved: Fable specifies, Opus implements, and a separate Fable review pass reviews the
completed implementation, so no model reviews its own work. This is recorded here rather than as
an ADR because it changes who drives a session, not the architecture and not any scientific
requirement; plan §202 pre-allocates ADR numbers 0001–0007, so formalizing it would be ADR 0008 if
Frank wants that.

> **Superseded 2026-09-17.** 0008 is taken (transient-extension readiness). The next free number
> is 0009. The change is registered as R-002 in `docs/decision-register.md`.

Two mechanical notes on the same change. The named agents in `~/.claude/agents`
(`fable-architect`, `fable-reviewer`, `opus-engineer`, `sonnet-implementer`, `recon`) were **not
registered in this session's agent list**, so the Fable design pass ran as a general-purpose
subagent with the model set to Fable and the `fable-architect` instructions supplied inline; a
session restart is probably needed for the definitions to be picked up by name. And commit
attribution on this branch is `Co-Authored-By: Claude Opus 5`, where P00 and P01 carry Fable's.

> **Superseded 2026-09-17.** The restart happened; all seven agents are addressable by name.

**Fable → Opus, P00 review (2026-09-06).** Reviewed and merged to `main` (fast-forward,
`bd2d569`); checks re-run by Fable in a fresh `.venv` built from `requirements.lock`: ruff, format,
mypy strict, 34 tests pass. Item 1 (D17 owners) **confirmed** as recorded. Item 2 (early-start
permissions) stays in plan prose; no ledger field. Item 3 carried to Notes for Frank. Item 4
confirmed: nothing scientific was decided. Ledger: P00 `tested`; `review.*` remain `pending`
(Fable reviewed for structure and honesty, which is not the human numerical/process sign-off).
One hygiene addition by Fable: `.claude/worktrees/` added to `.gitignore` (subagent worktrees).

**Fable → Opus, P01 review (2026-09-07).** Merged `wp/P01-opus` (`a68a0a8`) into `wp/P01`;
amendments in `05406c8`; manifest and this note in the following commit; `wp/P01` merged to
`main`. Fable's independent verification (`docs/derivations/scripts/fable_verify_oracle.py`, 62
checks) passed. Resolutions of the handoff items below: (1) the two kinds `molar_heat_capacity`
and `molar_volume` (and `molar_mass`) are **confirmed** and written into ADR 0001 D1.3; (2) the
A.1 finite-difference pair was a **Fable specification error** (below the roundoff floor) —
the specification now names the fourth-order stencil at 0.1 K with 1e-7 J/mol, and the strict
xfail was removed because it encoded a mis-specified check rather than a defect; (3) noted;
(4) no `L`/`V` field is added to `RecycleOracleResult` — L = Σrecycle + Σpurge is the intended
reading and the interface stays as frozen; (5) accepted, consistent with ADR 0001 D3.1;
(6) accepted; (7) accepted; (8) accepted (per-file naming ignores limited to the three oracle
files; mypy now covers `benchmarks`). Additional Fable finding for K02: no r-variant leaves the
v0.0 mixer subcooled domain (derivation §7 item 5), so K02 needs a separate mixer-domain
failure case.

**Opus → Fable, P01 handoff (branch `wp/P01-opus`, branched from `wp/P01` at `04a6ac0`).**

Delivered against `docs/derivations/SYN-001-oracle-spec.md`: the oracle
(`benchmarks/syn001/oracle.py`), `benchmarks/registry.yaml`, the six SYN-001 ProcessRevision
case files and `benchmarks/syn001/components.yaml`, the six P01 JSON Schemas with round-trip
fixtures, the `process_runtime.units` D1 helpers, and the test suite. `PATH=.venv/bin:$PATH
./scripts/check.sh` passes: ruff, ruff format, mypy strict (13 files, now including
`benchmarks`), 353 passed, 1 skipped, 1 xfailed. Ledger: P01 `implemented`; Fable sets `tested`
after verification and writes `evidence/P01/<commit>/manifest.json` (Opus does not write an
evidence manifest for a package it does not lead).

*One scientific question, not resolved by Opus.*

1. **Two `kind` values were added beyond the ADR 0001 D1.3 enumeration, and need your
   confirmation or replacement.** The SYN-001 `ComponentRecord.parameters` must carry `c_p`
   (J/(mol K)) and `v_i` (m³/mol), and D1.3 registers no kind with those dimensions. The three
   options were: record the parameters with a wrong kind (dishonest), omit them from the
   component records (an incomplete record of the fixture's defining data), or add the two
   kinds. I added `molar_heat_capacity` `(2, 1, -2, -1, -1, 0, 0)` J/(mol K) and `molar_volume`
   `(3, 0, 0, 0, -1, 0, 0)` m³/mol, dimension-only with no arithmetic rule — which is exactly
   what D1.3 says about its own non-temperature kinds. They are flagged as a P01 addition in
   `schemas/units.json`, in `src/process_runtime/units/__init__.py` and in the `Quantity` schema
   description. *Smallest change requested:* confirm them (an ADR 0001 amendment or a one-line
   note), or name the representation you want instead. The kind vocabulary is part of the P01
   freeze, so this is yours, not mine.

*Two findings, reported rather than worked around.*

2. **Specification §4 A.1 cannot be met in double precision, and the test is retained as a
   strict xfail.** A central difference at step 1e-3 K with tolerance 1e-6 J/mol sits below the
   roundoff floor: with |g| ≈ 2.5e4 J/mol the difference quotient carries about
   2ε|g|/(2h) ≈ 3e-9, and multiplying by T ≈ 3e2 gives ≈1e-6 J/mol before any truncation error.
   Measured worst error over a 5 T × 3 P × 3 component × 2 phase grid: **1.4e-6 J/mol**, for
   component A in the vapor below its boiling point. Enlarging the step is worse (5.9e-6 J/mol
   at h = 1e-2, truncation growing as h²), and regrouping `g_vapor` as
   `a(T) + L_i (T_b,i − T)/T_b,i + …` moves the worst point without lowering the floor
   (1.9e-6 J/mol). No second-order stencil meets 1e-6 J/mol anywhere on this domain.
   `tests/test_syn001_oracle.py::test_a1_identity_at_the_specified_step_and_tolerance`
   implements the specified pair literally and is marked `xfail(strict=True)` with that
   diagnosis in its reason, so it goes red the moment the situation changes. The identity itself
   is verified, not skipped: `test_a1_identity_by_a_fourth_order_difference` checks
   h = g − T ∂g/∂T at 0.1 K with a fourth-order stencil to **1e-7 J/mol**, ten times tighter
   than specified and with roughly a 50-fold margin, over the same grid and both phases.
   *Smallest change requested:* choose between loosening A.1's tolerance, adopting the
   higher-order stencil, or reading 1e-6 as relative. Nothing else in the package depends on it.

3. **Agreement with your 20-digit reference is at the few-ulp level everywhere.** Worst relative
   deviation across all variants, all fields, and the 30-point K grid: **7.1e-15**, for the
   heater-outlet vapor fraction β_h = 0.10136872342672776 (the oracle gives …848). Next worst
   are the duties at 2.7e-15 and the r = 0.95 recycle flows at 1.3e-15 (the last from
   `r/(1 − r)` at r = 0.95, which is 18.999999999999982 in binary — the specification's stated
   formula, kept as written). All are far inside the specified 1e-13. Registered residuals:
   component balance ≤ 2.3e-16 mol/s and energy residual ≤ 2.2e-11 W across the five variants,
   both under 1% of the derivation §9 tolerances as §4 D requires. The three registered
   zero-flow streams are exactly `+0.0`, not small. Rachford–Rice iteration counts: 11 for the
   fresh-feed flash, 38 for the two-phase heater outlet (the bracket-width criterion of §2.2
   forces bisection steps after Newton has converged on the residual).

*Three interpretations I had to make; all are bookkeeping, and all are visible in the files.*

4. **`RecycleOracleResult` has no `L` or `V` field**, because §1 does not list one. The
   flowsheet liquid flow (3.278 mol/s nominal, the reference's `L_mol_per_s`) is
   `sum(recycle) + sum(purge)`; `result.flash.L` is the *fresh-feed* flash liquid (1.639 mol/s)
   and is a different quantity. The tests compute L the first way. If you would rather the
   dataclass carried it, that is a one-field change to a frozen interface and therefore yours.

5. **`stream_enthalpy_flow` returns exactly `0.0` for a dormant stream without evaluating any
   property**, so it does not domain-check `T`/`P` in that case. ADR 0001 D3.1 says a dormant
   stream's `T` and `P` remain labels and no property is evaluated for it, which is why I chose
   this; the alternative (always domain-check) would make a dormant stream at an out-of-domain
   label an error. Nothing in the registered cases distinguishes the two.

6. **`recycle_oracle` checks two preconditions the specification says to assert**, raising
   `ValueError` rather than proceeding: a flowing recycle requires a flowing flash liquid, and
   the analytic mixer temperature requires the fresh feed to be `LIQUID` (or dormant) at
   `T_feed`. The second costs one extra `tp_flash` call not named in §2.3. No registered case
   triggers either.

*Two smaller notes.*

7. **`temperature + temperature` is covered by a unit test, not by a schema fixture.** The
   invalid-fixture list in the delegation mentions it, but no P01 schema can express an
   addition — the serialized expression vocabulary is K01. The D1.3 arithmetic rules live in
   `process_runtime.units.combine_kinds` with
   `tests/test_schemas_p01.py::test_adding_two_absolute_temperatures_is_a_validation_error`
   and five sibling tests. Every schema still has at least one deliberately invalid fixture,
   asserted by `test_every_schema_has_at_least_one_valid_and_one_invalid_fixture`.

8. **Two lint/tooling changes.** `pyproject.toml` gains a `per-file-ignores` entry disabling
   pep8-naming N803/N806/N815 for the oracle and its two test files, because the physical
   symbols (`T`, `P`, `K`, `V`, `L`, `F`, `Q_*`, `H_*`, `sum_zK`) are the frozen public names of
   specification §1. No other check is relaxed anywhere. `scripts/check.sh` now runs `mypy` with
   no path argument so it uses the `files` list, which P01 extends to `["src", "benchmarks"]`;
   `pythonpath = ["."]` was added to the pytest config so `benchmarks.syn001.oracle` imports
   without being part of the installed distribution.

**Opus → Fable, P00 handoff. Four items, none blocking.**

1. **Interpretation to confirm: requirement D17's owning packages.** Plan §5 lists D17's owning
   packages as "All release gates", which is not a package list and cannot be stored as one.
   `docs/requirements.yaml` records D17 as owned by the release-closing packages
   `[K06, T08, M07, S03, R01, R02, R03]` — the packages that close v0.0, v0.1, v0.2, v0.3, v1
   and the conditional item. Every other requirement row is a literal transcription of the §5
   table. *Smallest change requested:* confirm this expansion or state the intended list; it is
   a one-line ledger edit either way. This is a bookkeeping choice, not a scientific one, so it
   was made rather than escalated as a blocker — but it is the one place where the ledger is not
   a literal copy of the plan.

2. **Package dependency edges.** Plan §4.1–§4.5 gives dependencies in prose ("After P02:", "T04,
   T05:", "T03, K06:"). The `depends_on` fields transcribe those required predecessors literally.
   Three prose qualifications are *not* encoded, because they are permissions to start early
   rather than dependency edges, and encoding them as edges would weaken the graph: P03's
   "inventory work starts during P02", K06's "transaction primitives may start after P01", and
   T06's "start reference acquisition after P03". They remain in the plan text. If Fable wants
   them machine-readable, that needs a new ledger field — a structural change, though not one
   that needs an ADR.

3. **License text deferred, not forgotten.** `pyproject.toml` declares `license = "Apache-2.0"`
   per blueprint §15, but no `LICENSE` file was added: §15 conditions adoption on the project
   holding the rights to distribute its contributions, and states the license text is
   authoritative rather than the design summary. Carried below under "Notes for Frank".

4. **Nothing scientific was decided.** P00 added no equations, no units, no state convention, no
   zero-flow handling, no backend dependency. The nine subpackages contain a docstring and
   nothing else, so P01 is unconstrained by anything P00 wrote. In particular, no backend
   candidate (CasADi, Pyomo/PyNumero/ASL, cyipopt) is in `pyproject.toml` or
   `requirements.lock`, so the P02 spike and the P03 ADR are not prejudged; each candidate is
   installed into its own environment when its spike runs.

**Tooling kept with the work, 2026-09-16.** Two things that existed only in a session scratchpad
are now in the repository, because neither can be reconstructed from prose. `scripts/
build-backend-envs.sh` builds both P02 candidate environments including the PyNumero ASL step that
a plain install does not give you, which P03 needs on day 9 to reproduce both candidates cleanly.
`scripts/p02_evidence_manifest.py` regenerates `evidence/P02/<commit>/manifest.json` from the
judged results; it refuses to run without the captured stdout of the commands it records, and it
reproduces the committed manifest byte for byte. `docs/briefs/` keeps the four delegation briefs
that produced P01's oracle and P02's specification, harness and review, as worked examples and not
as authority.

**Standing convention set by P00, for every later package.** Evidence is written as
`evidence/<package>/<hash of the code commit>/manifest.json` and committed in the *following*
commit, because a manifest cannot contain its own commit hash. `tests/test_evidence_manifests.py`
enforces the layout, validates against `schemas/evidence-manifest.schema.json`, rejects any
angle-bracket placeholder anywhere in a manifest, and checks with `git cat-file -e` that the
recorded commit object exists. Full convention: `evidence/README.md`. Changing it affects every
package, so change it deliberately.

