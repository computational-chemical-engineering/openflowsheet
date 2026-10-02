# Brief — P03 backend verdict (ADR 0003 and ADR 0006)

**To:** `fable-verdict`. **From:** the Opus 5 session, 2026-09-17. **Branch:** `wp/P03`, at commit
`2bbd914`. **Plan authority:** §4.1 row P03, §8.1 day 10.

Everything you need to decide is pasted below. You should not have to read a results directory, and
you should not need to re-derive anything. Where a pointer appears it is for provenance, not because
the content was left out.

---

## 1. The question

**Which backend does `CompiledProblem` compile to, and on what terms may the project distribute
it?** Two decisions, both closing on the evidence already collected:

- **ADR 0003 — `CompiledProblem` / backend.** CasADi, or Pyomo/PyNumero/ASL, or neither.
- **ADR 0006 — distribution and data rights.** What the project may ship, given what the selected
  backend's distribution actually contains.

Either may instead be **one narrowly evidenced blocker**. The plan forbids a third option: "Do not
spend another open-ended month comparing libraries." If the evidence below does not settle a
question, say precisely which measurement is missing and stop — do not commission a survey.

## 2. Why this needs Fable

The measurements are done and they are not close on the one axis that separates the candidates. The
hard part is not arithmetic; it is judging **what the numbers are evidence of**. Specifically:

1. The two routes **do not assemble the same matrix** and are not timed at the same boundary. A
   verdict that compares them as though they were is wrong even if it picks the right winner.
2. The problem has 17 variables. The Jacobian gap is overhead, not scaling, and the project's real
   problems are not 17 variables. Deciding how much weight a 4× overhead ratio at n=17 deserves is a
   judgment call about extrapolation, and it is yours.
3. The distribution finding (§5.3) is a genuine constraint that most readings would over- or
   under-react to. It is not a numerical defect and it does not touch the evaluation path, but it is
   also not nothing.

## 3. What is already decided, and not open to you

Do not reopen these. They are authorities or settled decisions, and a verdict that relitigates them
cannot be applied.

- **`docs/blueprint-v3.1.md` is the architectural authority; `docs/implementation-plan.md` v1.1 is
  the execution authority.** Re-planning is out of scope. A departure needs its own ADR.
- **Plan §2.1 interfaces and §2.2 schemas are frozen** (`docs/interfaces-frozen.md`, end of P01).
  They change only by a Fable-authored ADR, which this is not. The frozen boundary you are selecting
  a backend *for*:

  ```python
  class CompiledProblem(Protocol):
      metadata: CompiledProblemMetadata
      def residual(self, x, context) -> EvaluationResult: ...
      def jacobian(self, x, context) -> JacobianResult: ...
      def reconstruct(self, x, context) -> ProcessState: ...
  ```

  with, from §2.1: sparse Jacobians have a documented CSC ordering; row and column IDs and source
  maps are declared explicitly; `jacobian` and `residual` must describe the same function at the
  same state; optional JVP/VJP/Hessian capabilities are negotiated; **a missing exact Hessian cannot
  be replaced with fabricated zeros**.
- **ADR 0001** fixes state `nTP-v1`, units, the `kind` vocabulary, zero-flow semantics and the sign
  and reference conventions. **ADR 0008 D1–D3** are part of the same freeze: no time at the
  evaluation boundary; `state_sha256` covers exactly the dense `x`; a required per-equation
  `accumulation` declaration with `F_row = inflow − outflow + sources`.
- **The plan's decision rule**, verbatim from `docs/implementation-plan.md` §4.1:

  > **P03 decision rule:** correctness, sparse composition, distributability, and installability are
  > hard criteria; then compare measured runtime and development cost. Keep CasADi on a defensible
  > tie. If a candidate is blocked, retain the exact build/error evidence and choose the demonstrated
  > viable route. If neither works, stop model breadth, identify the smallest blocker, and propose a
  > bounded ADR remedy. Do not spend another open-ended month comparing libraries.

  You apply this rule. You do not rewrite it.
- **P02 states no preference between the routes.** That was deliberate. The preference is yours.
- **ADR numbering:** 0003 and 0006 are pre-allocated for exactly these two decisions. 0009 is the
  next free number and you should not need it.
- **The project's own licence is unsettled and is not yours to settle.** `pyproject.toml` declares
  `license = "Apache-2.0"`; the `LICENSE` file was deliberately not added, because adding it is a
  rights assertion about Frank's group's contributions that only Frank can make. Treat Apache-2.0 as
  the *intended* core licence (blueprint §15) and say what follows from it — do not treat the
  missing file as a blocker you must clear, and do not assert the rights on his behalf.

## 4. The measured comparison

From `docs/p02-measurements.md`, recorded 2026-09-10 from `spikes/p02/results/<backend>/`. Host:
Debian 13, x86-64, Python 3.13.5, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, NumPy 2.2.4 and
SciPy 1.15.3 pinned identically in both environments so a difference is attributable to the backend
and not to the array stack. Machine load was not controlled, so the median is the headline and the
minimum is reported beside it. Five fresh processes for import, compile and memory; 200 timed calls
after 20 warm-ups for evaluation.

### 4.1 Correctness and composition — both routes pass

The P02 evidence manifest (`evidence/P02/507dccf…/manifest.json`, status `tested`) records **93
checks: 89 pass, 0 fail, 4 not applicable**. Both routes carry the verdict **PASS-composition**
(`P02.verdict.casadi`, `P02.verdict.pyomo`).

*Provenance note.* `docs/p02-measurements.md` §intro says "70 assertions pass … three are not
applicable". That count predates the Fable review of the completed implementation, which found a
coverage defect in the judge and added assertions. **89/0/4 from the manifest is the authoritative
count**; the prose header was not updated. This does not change either verdict.

### 4.2 One-off costs

| | CasADi 3.8.0 | Pyomo 6.10.1 + PyNumero |
| --- | --- | --- |
| Backend import, median / min | 12.6 / 12.4 ms | 432.1 / 417.4 ms |
| NumPy import, for scale | 36.1 ms | 36.6 ms |
| Compile the lifted form, median / min | 5.76 / 5.63 ms | 162.5 / 161.1 ms |
| Compile the inlined form | 2.29 / 2.24 ms | not applicable |
| First residual call | 0.110 ms | 0.150 ms |
| First Jacobian call | 0.223 ms | 1.015 ms |

The Pyomo compile figure includes writing the problem and loading the ASL library, which happens
inside `PyomoNLPWithGreyBoxBlocks` construction — its import looks expensive and its compile more so
because the two are one cost split across two lines.

### 4.3 Steady-state evaluation, at two levels

**Backend** = evaluation plus construction of the input from the NumPy state vector (`set_primals`
plus evaluation on the Pyomo side). **Boundary** = what the `CompiledProblem` boundary then does:
naming the entries, assembling the canonical CSC, and on the Pyomo route the name-keyed permutation
into specification order.

| Median / min, µs | CasADi backend | CasADi boundary | Pyomo backend | Pyomo boundary |
| --- | --- | --- | --- | --- |
| Residual | 74.6 / 59.2 | 119.4 / 117.0 | 67.0 / 54.9 | 66.8 / 64.3 |
| Jacobian | 178.5 / 175.8 | 238.8 / 235.2 | 742.8 / 714.2 | 827.8 / 807.7 |

**The residual costs the same on both routes at both levels. The Jacobian does not:** CasADi is
about 4× faster at the backend level and about 3.5× at the boundary, a gap larger than any
bookkeeping difference between the two harnesses. At 17 variables this is overhead, not scaling.

### 4.4 Memory

| Stage, resident set | CasADi | Pyomo |
| --- | --- | --- |
| After NumPy import | 25.8 MiB | 25.6 MiB |
| After backend import | 35.1 MiB | 111.7 MiB |
| After compiling the lifted form | 48.2 MiB | 116.4 MiB |
| Peak allocation during compile | 0.09 MiB | 0.44 MiB |

Current resident set from `/proc/self/status`, not peak.

### 4.5 Structure and callback behaviour

| | CasADi | Pyomo |
| --- | --- | --- |
| Assembled lifted system | 17 × 17, 60 nonzeros | 17 × 17, 60 nonzeros |
| Stored structure size | 792 bytes | 792 bytes |
| Inlined system | 11 × 11, 43 nonzeros | not available on this route |
| Value calls per residual, per block | 1 | 1 |
| Jacobian calls per Jacobian, per block | 1 | 1 |
| Value calls per Jacobian, per block | 1 | 0 |
| Callback probes during compile | none | one Jacobian call per block |
| Second order through opaque callbacks | absent, raises | absent, raises |
| Forward and reverse products (JVP/VJP) | **exact** | **absent** |

Neither route falls back to finite differences or to a dense Jacobian. The specification's threshold
for suspecting a difference fallback is `n_inputs + 1` value calls per Jacobian — three for block K,
six for block H — and both routes are far below it; one call is not evidence of differencing.

### 4.6 Where the two routes are *not* measuring the same thing

This is the part a verdict most easily gets wrong, so it is stated explicitly.

1. **They do not assemble the same matrix.** CasADi eliminates the callback outputs, giving a
   Jacobian in the original variables. The grey-box route carries callback inputs and outputs as
   explicit primals with `gb.output_constraints[...]` rows. The same toy problem is 2×2 in CasADi
   and 7×7 in Pyomo. The lifted forms were matched at 17×17 / 60 nonzeros precisely so that a
   comparison was possible at all; the **inlined** 11×11 form exists only on the CasADi route.
2. **Ordering must be pinned by name on both routes, for different reasons.** CasADi fills a sparse
   `DM` in column-major (CCS) order, not triplet declaration order — values supplied in triplet
   order silently produce a permuted Jacobian. `PyomoNLP` does not preserve constraint declaration
   order: for a model declaring `e1` then `e2`, `evaluate_jacobian_eq()` returned `e2` as row 0.
3. **PyNumero writes a grey-box output constraint as `f(inputs) − output`**, so the harness applies a
   declared row-sign adapter to the six defining rows and records the native orientation
   (`raw_structure.json`, asserted by A24). CasADi needs no such adapter.
4. **A CasADi callback must declare its Jacobian sparsity** through `has_jac_sparsity` and
   `get_jac_sparsity`, or the assembled pattern is over-approximated. This is a live obligation on
   whichever property-provider plumbing K01 writes, not a defect.

### 4.7 What P02 explicitly does not establish

Verbatim from the manifest's limitations, because a verdict must not claim more than these allow:

- P02 is a composition test on a synthetic subsystem: not a solver test, not a performance benchmark
  on a real flowsheet, and not the backend selection.
- 17 variables. The timings measure boundary and assembly overhead, not scaling.
- SYN-001 is synthetic. Nothing is empirical validation of any thermodynamic model.
- The declared sparsity of both callback blocks is P02's own. Whether a *real* property provider's
  declared sparsity is correct is not tested.
- Second order is absent through opaque callback Jacobians on **both** routes. CasADi returns exact
  second derivatives when the block ships symbolic derivative code — a capability fact for K01, not
  part of the P02 verdict.
- One host, one platform. **No CI has ever executed any of this.**
- `review.numerical` and `review.process_model` are `pending` on every package. No human numerical or
  process-modeling reviewer has seen any of it.

## 5. Installability and distribution

### 5.1 Installability, measured (`docs/backend-environments.md` §4)

**CasADi** installs from a manylinux wheel with no build step and imports immediately.

**PyNumero's ASL interface does not work from a plain `pip install Pyomo`.** The measured sequence:

| Step | Result |
| --- | --- |
| After `pip install Pyomo==6.10.1` | `AmplInterface.available()` → `False` |
| After `pyomo download-extensions` | still `False`; fetches `gjh` and `mcpp` only, reports AMPL GSL no longer downloadable |
| `pyomo build-extensions`, no setuptools in the venv | every target fails: `ModuleNotFoundError: No module named 'setuptools'` |
| `pyomo build-extensions`, setuptools installed | pynumero, aslfunctions, ampl_function_demo, cspline_external, mcpp build; **appsi fails** (`ModuleNotFoundError: No module named 'pybind11'`); ginac skipped; **command exit code 1** |
| After that build | `AmplInterface.available()` → `True` |

So the Pyomo route requires cmake, a C and a C++ compiler, and setuptools on the installing machine,
and its build command **exits nonzero even on the success path** because APPSI fails for want of
pybind11. APPSI is not on the P02 route; the nonzero exit was recorded as a limitation and not
worked around.

### 5.2 The binary and plugin audit, completed on this branch

Full document: `docs/p03-binary-audit.md`; machine-readable record:
`spikes/p03/results/{casadi,pyomo}-inventory.json`; instrument:
`scripts/p03_binary_inventory.py`. This discharges requirement **D04**'s and evidence tag
**[A10]**'s measurement obligation. The headline table:

| | CasADi 3.8.0 | Pyomo 6.10.1 + built ASL |
| --- | --- | --- |
| Compiled objects distributed | 232 (119 distinct), 240 481 560 B | 1, 1 367 496 B |
| Loaded by the P02 route | 19 384 616 B | ASL built on the host |
| **Disabled distributed bytes [A10]** | **1 885 160 B, 12 objects** | **0** |
| Notice in the metadata directory | **none** | `licenses/LICENSE.md` present |
| Notices in the package tree | 81 files, 40 components, 430 274 B | none |
| Declared own licence | LGPL-3.0-or-later | BSD-3-Clause |
| Restrictive notice found | **METIS 4.0 (§5.3)** | none |
| Compiled bytes with no notice at all | 5 723 463 B, 8 objects | ASL terms unresolved |
| Proprietary vendor code shipped | **none** | **none** |

Points that bear on the verdict:

- **[A10]'s "disabled distributed bytes" are 1 885 160 across 12 objects** — ten plugin shims
  (`nlpsol:knitro`, `snopt`, `worhp`, `madnlp`, `ccopt`; `conic:mosek`, `xpress`, `cplex`, `gurobi`;
  `linsol:ma27`) plus the CPLEX and Gurobi adaptor stubs. Eight fail `dlopen` outright; CPLEX and
  Gurobi load and then fail registration, emitting a diagnostic on import. **No vendor library is
  bundled** — `libgurobi*`, `libmosek*`, `libcplex*`, `libknitro*`, `libsnopt*`, `libworhp*`,
  `libhsl*`, `libcoinhsl*` are all absent — so nothing proprietary is redistributed. These are bytes
  a user downloads and can never run.
- **The wheel ships no symlinks.** 126 628 591 bytes — 53% of the compiled payload — is duplicated
  content, because each SONAME spelling is a full copy. Download and image size only.
- **The P02 route loads 19 384 616 of 234 809 336 shipped bytes.** CasADi `dlopen`s a plugin on
  first use, so no plugin is in the link-time closure of `_casadi.so`; the closure is `_casadi.so`
  plus `libcasadi.so.3.7` and nothing else from the package. 215.4 MB is shipped and dormant on that
  route.
- **A P02 statement is corrected.** `docs/backend-environments.md` §5 said the distribution "ships
  no LICENSE, NOTICE or COPYING file" and that notices "must be assembled from upstream". True of
  `casadi-3.8.0.dist-info/`, false of the package tree, which carries 81 notices across 40
  components under `casadi/include/licenses/` including CasADi's own LGPL-3.0 text. The
  assembled-from-upstream claim is withdrawn; §5.3 replaces it.
- **5 723 463 bytes across 8 distinct objects carry no notice anywhere** and no embedded licence
  text: `libgfortran`, `libquadmath`, `libgomp`, `libmvec` (hash-suffixed — the `auditwheel`
  signature, host libraries copied in without their notices), `libspral.a`, `libmatlab_ipc.so`, and
  the two adaptor stubs. Their terms are recorded as **unresolved**. Unresolved is not permissive;
  the audit deliberately does not guess them.
- **Pyomo's ASL terms are also unresolved** from the installed artifacts: the build leaves no notice
  for the AMPL Solver Library, only `src/mcpp/LICENSE`.

### 5.3 The one finding — METIS 4.0 under a no-redistribution notice

`casadi/include/licenses/metis-external/metis-4.0/LICENSE` (889 bytes, SHA-256
`2ecd4c415834a03b…`) reads in part, verbatim:

> The METIS package is copyrighted by the Regents of the University of Minnesota. It can be freely
> used for educational and research purposes by non-profit institutions and US government agencies
> only. Other organizations are allowed to use METIS only for evaluation purposes, and any further
> uses will require prior approval. **The software may not be sold or redistributed without prior
> approval.**

METIS 5.1.0 was relicensed Apache-2.0; METIS 4 was not. The `metis-external/LICENSE` beside it is
EPL-1.0, but that covers the Coin-OR `ThirdParty-Metis` wrapper, not the METIS code.

**Attributed from the binary, not the filename.** `libcoinmetis.so.2.0.0` (306 208 bytes, SHA-256
`1166d99729c03357…`) defines `METIS_EstimateMemory`, `METIS_mCPartGraphKway` and `METIS_EdgeND`, all
removed from the METIS 5 API, and defines neither `METIS_SetDefaultOptions` nor `METIS_Free`, both
introduced in METIS 5. (`METIS_PartGraphKway` exists in both lines and was not used as evidence.)

**Scope and reachability.** Exactly one distinct object carries METIS code, shipped three times
under its SONAME spellings: **918 624 bytes of the download**. No other shipped object exports a
`METIS_` symbol. It is a `DT_NEEDED` dependency of `libcoinmumps`, `libipopt`, `libsipopt` and
`libuno`, and transitively of `libbonmin`, `libCbc`, `libClp`, `libCgl`, `libOsiCbc`, `libsleqp` and
the `linsol:mumps` plugin. **It is not in the closure of `_casadi.so`**, so nothing on the P02 route
loads it — but `Linsol("mumps")` does, successfully.

*Not to be confused with:* HiGHS vendors a different METIS
(`highs-external/extern/metis/LICENSE.txt`, Apache-2.0). Only the Coin-OR METIS 4.0 is restrictive.

**This is not a numerical defect and does not touch the evaluation path.** It is a constraint on
what the project may put inside anything it distributes. It is ADR 0006's question and the audit
deliberately stopped short of answering it.

## 6. Already tried and rejected, with the evidence

So that none of this comes back as a recommendation:

- **Timing the two routes at a single level.** Rejected in P02: comparing a bare backend call
  against the other route's full boundary would flatter one of them. Both levels are reported
  instead (§4.3). Do not ask for a single headline number.
- **Comparing the inlined CasADi form against Pyomo.** Not possible — the grey-box route has no
  inlined form (§4.5). The 17×17 lifted form is the matched comparison, and it exists because P02
  built it to be matched.
- **Taking `build-extensions`' nonzero exit as a Pyomo blocker.** Rejected: APPSI is not on the
  route, the libraries P02 needs did build, and `AmplInterface.available()` is `True` afterwards. It
  is recorded as a limitation. Do not upgrade it to a blocker; if you want to weigh it, weigh it as
  installability friction under the hard criterion.
- **Treating the commercial-solver shims as a rights problem.** Rejected by measurement: no vendor
  library is bundled, only adaptors. The rights finding is METIS, not the shims. The shims are a
  *bloat and user-confusion* fact.
- **Concluding from the empty `dist-info` that CasADi ships no notices.** Wrong, and corrected
  (§5.2). Do not rebuild a verdict on the withdrawn claim.
- **A survey of further backends** (JAX, symengine, hand-written AD, ADOL-C, …). Explicitly out of
  scope by the plan's last sentence. The candidate set is closed.

## 7. How your verdict will be verified, and what it must survive

- `docs/p03-binary-audit.md` and the two inventory JSONs are regenerable by one command; any factual
  claim you make about the distributions must match them. If you believe a number there is wrong,
  say so — do not quietly use a different one.
- The gate `PATH=.venv/bin:$PATH ./scripts/check.sh` is green at **424 tests** and must stay green.
  Your deliverable is documentation, so it should not move it; two tests
  (`tests/test_document_hashes.py`, `tests/test_requirements_ledger.py`) do check document hashes and
  the requirements ledger, so if a decision implies a ledger change, say so and let the Opus session
  make it.
- The Opus session owns the branch and the evidence manifest (decision register R-002), and will
  record `implemented`/`tested` honestly. **Never set `reviewed`** and do not claim it: that needs
  human numerical and process-modeling sign-off which no agent may give.
- K01 is the immediate consumer. It turns the selected spike into the production compiler and
  inherits ADR 0008 D4 (`constants_sha256` over the full pinned-input vector, a new `parameter_ids`
  field, an inert-`workspace` test, `row_accumulation` in `CompiledProblemMetadata` at schema
  promotion). A verdict that leaves K01 unable to start has not closed P03.

## 8. Deliverable

Two ADRs, written by you, in the repository's existing ADR style (see
`docs/adr/0001-state-units-zero-flow.md` and `docs/adr/0008-transient-extension-readiness.md` for
the house form — status, context, decision, consequences, what this does not establish, and where
the ADR carries open questions, each with a recommended default).

### 8.1 `docs/adr/0003-compiled-problem-backend.md`

Must contain, at minimum:

1. **The verdict**, stated in one sentence at the top.
2. **The hard criteria, one subsection each** — correctness, sparse composition, distributability,
   installability — with, for each candidate, `met` / `not met` / `insufficient evidence` /
   `blocked`, and the specific measurement that decides it. A criterion you cannot decide from §4
   and §5 is `insufficient evidence` and you name what is missing.
3. **Only then** the measured runtime and development-cost comparison, with the extrapolation
   question of §2.2 addressed explicitly rather than assumed away.
4. **Whether the tie-break clause was reached**, and if so why the tie is defensible.
5. **What the verdict does not establish** — at minimum the §4.7 limitations restated as they bear
   on the decision.
6. **What K01 inherits**: the ordering obligations of §4.6, the callback sparsity declaration
   obligation, the JVP/VJP capability difference, and the second-order position (absent through
   opaque callbacks on both routes; exact when a block ships symbolic derivative code).
7. **What would reverse this decision** — the concrete future observation that would justify a new
   ADR. The register exists to prevent silent reversal; give the next session the trigger.

### 8.2 `docs/adr/0006-distribution-data-rights.md`

Must contain, at minimum:

1. **What the project may distribute**, given §5.2 and §5.3, distinguishing at least: depending on
   the backend from PyPI as an ordinary pinned dependency; vendoring or re-distributing the wheel's
   bytes inside a container, an installer or a replay bundle; and distributing source only.
2. **The METIS 4.0 disposition** specifically, with its scope (918 624 bytes, one object, reachable
   only through MUMPS/Ipopt/Uno) and the remedies you consider adequate, in the order you would
   have them tried.
3. **The LGPL-3.0-or-later position**: CasADi's own licence against the project's intended
   Apache-2.0 core, for the dynamic-linking case the architecture actually uses. Say what obligation
   this creates. Do **not** assert the project's rights on Frank's behalf (§3, last bullet).
4. **The unresolved components** of §5.2 named individually, each as an explicit open item with a
   recommended default, not folded into a general reassurance.
5. **Notice obligations the project takes on** if it ships anything containing the backend: what must
   be collected, from where, and which package owns it (T08 also owns D04 — say what it inherits).
6. **What this ADR does not establish**, including that no rights assertion about the project's own
   contributions is made here.

### 8.3 Also return, in your report to the session

- The **decision-register entries** for R-A03 and R-A06, in the form `docs/decision-register.md`
  already uses, so the Opus session can apply them verbatim.
- Any **requirements-ledger change** you believe D04 or A10 now warrants — but state it as a
  recommendation with the reason; the session applies it and owns the manifest.
- **One narrowly evidenced blocker**, if that is your answer instead of one or both ADRs. Name the
  single missing measurement and what would produce it.

## 9. Out of scope

Do not write production code, do not modify `src/`, `tests/`, `benchmarks/` or `spikes/`, do not
regenerate any P02 result, do not amend the plan or the blueprint, do not evaluate a backend outside
the two candidates, do not set any `reviewed` field, and do not add the `LICENSE` file or assert the
project's right to distribute its own contributions. If you find an error in
`docs/p03-binary-audit.md` or in the numbers above, report it — do not edit the audit yourself.
