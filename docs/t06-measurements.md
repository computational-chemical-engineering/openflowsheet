# T06 measurements (append-only)

Build-lane measurements for T06 (spec `docs/derivations/T06-corpus-spec.md` §17, phase M). Each
entry: the date, the commit it was measured at, the command, and the number. Entries are
appended, never rewritten; a later measurement that supersedes one says so. Commands run from
the repository root with `PYTHONPATH=src:.` and the project venv. Host: Debian 13, x86-64 (AMD
Ryzen Threadripper PRO 5965WX, 48 threads), Python 3.13.5, numpy 2.2.4, scipy 1.15.3, CasADi
3.8.0.

---

## 2026-09-25 — M1, M2, M3 at `9864e66` (base `792c594`; no `src/` change)

Script: `scripts/t06_phase_m.py` (committed with this entry). Case files: `benchmarks/t06/cases/`
(commit `9864e66`; written to spec §4.1–§4.3 and §9.2).

### M1 — the new revisions, solved from their registered initializer

**Files.** Ten new flowsheets `SYN-001-T06-{THM01,THM02,THM10,STA02,NET02,NET03,NET06,NET09,NET10,NET11}`,
five diagnosis fixtures `SYN-001-T06-{STR02,STR06,STA03-kgs,STA03-degC,STA04}`, seven REF
fixtures `SYN-001-T06-REF01…REF07`; revision ids `<file stem>-r1`. Sinks the spec leaves
unnamed: `U-SINK-V` (a vapour product), `U-SINK-L` (a liquid product), `U-SINK-P` (a purge),
`U-SINK-R` (REF-02's recycle-port outlet), `U-SINK` (a single product); REF-01's second feed is
`U-FEED2`. `tests/test_t06_m1_cases.py` (55 tests, 1.1 s): schema validity, binding in the spec's
declaration and stream order, every assembled row of the ten new flowsheets within K04's `τ` at
the twin's 20-digit root (a changed pin — `S4.T` 370 → 371 K in NET-11, `S9.T` 340 → 341 K in
NET-03, THM-01's flash at `P_r` — moves a row to 1e6–2e6 `τ`), and each diagnosis fixture its
parent with exactly the one stated change.

**Solves.** `python scripts/t06_phase_m.py m1` (bind → `plan_revision` → `execute_plan` →
`verify_revision`, `T05b-v2` and `T05-W13`). "worst" is `max |ours − twin| / allowance` over every
coordinate `ref.closed_form.corpus_cases` registers (T02 §6.4's allowances; no coordinate
missing); for REF, over the §9.4 quantities at §9.4's tolerance.

| Case | `T05b-v2` | `T05-W13` | worst (v2) |
| --- | --- | --- | --- |
| THM01 | `CONVERGED`, `VERIFIED` | same | 8.35e-9 (`U-FLASH.Q`) |
| THM02 | `CONVERGED`, `VERIFIED` | same | 3.24e-9 |
| THM10 | `CONVERGED`, `VERIFIED` | same | 5.45e-9 |
| STA02 | `CONVERGED`, `VERIFIED` | same | 5.45e-3 (`S5.n.A`) |
| NET02 | `BOUND_BLOCKED` at iteration 1; `eo_recovery=unsupported`, `eo_recovery_unsupported=no_continuation_parameter`; `S6.n.A` = 0.0 | same | — |
| NET03 | `CONVERGED`, `VERIFIED` | same | 2.08e-7 |
| NET06 | `CONVERGED`, `VERIFIED` | same (worst 6.39e-4) | 6.40e-8 |
| NET09 | `CONVERGED`, `VERIFIED` | same | 4.46e-4 |
| NET10 | `CONVERGED`, `VERIFIED` | same | 1.40e-6 |
| NET11 | `CONVERGED`, then `VerifierError: the residual for the alias certificates returned invalid_trial_state` (`H_S4_liquid: pressure 204925.0 Pa outside [50000.0, 200000.0] Pa`) | same | 3.24e-3 (state; uncertified) |
| REF01…REF07 | all `CONVERGED`, `VERIFIED` | same | 2.94e-11, 1.47e-10, **3.94e-8** (REF03 `S2.vap.A`), 2.37e-10, 2.48e-9, 7.82e-11, 9.76e-11 |

**Against spec §2's pilot: reproduced, no difference.** Eight new cases and REF-01…REF-07
`VERIFIED` under both contracts; NET-02 `BOUND_BLOCKED`; NET-11 `VerifierError`. REF's worst
3.94e-8 (REF-03) is §2's 3.9e-8. `python scripts/t06_phase_m.py m1-detail` gives §2's quoted
digits exactly: THM-02 `S2.T` 369.1567744489916 K; THM-10 `S2.T` 366.7319114617808 K; NET-03
`S5.T` 359.8252376050488 K, `S7.n.A` 0.37194082868103223, `S10.n.A` 1.7270664699333753; NET-09
`S6.n` (0.27562216379112986, 0.24167480070952238, 1.3602936381085373). NET-02's trace: one
accepted step at iteration 0, `BOUND_BLOCKED` at iteration 1, `S6.n.A` the only flow column at
exactly 0.0. NET-11 with the alias shift reversed where the upward one leaves the domain (a
monkeypatch; measurement only): the reversal fires once, at `S4.P` (variable index 24, 180 000 +
24 925 Pa), and the certificate is `VERIFIED`, no failing check, `S8.n.A` 0.5808715286179267,
`S5.T` 351.7559133964751 K, `S6.T` 353.4759834709805 K — §2's values. The committed files use the
spec's §4.1 order (feeds first, connections in stream order), not the pilot's helper order (units,
then feeds, then sinks); the outcomes and digits did not move.

### M2 — the 22 eligible cases from their registered initializers, with the four wall times

`python scripts/t06_phase_m.py m2 --repeats 7`. Policies (§6.6): revision path `T05b-v2`; tear
path (NET-01, THM-03) `solve_tear` under `SolvePolicy("SYN-001-K03")` from
`SYN-001-tear-init-v2`, certified by `verify`; NET-05 through its binding and plan
(`run_flowsheet` of `tests/test_t02_executor.py`, `SolvePolicy` defaults) certified by
`verify_bound`. Cold per repeat (fresh binding, provider, compiled problem and plan); one
unmeasured warm-up solve first. Attribution by timing wrappers only: *compile* = binding,
planning and every `compile_problem` call (the executor's and the verifier's included);
*init* = `revision.traversal_start` / `Syn001Flowsheet.initial_recycle` / NET-05's sequential
pre-solve; *solve* = the rest of the solve call; *verify* = the rest of the certificate call.
Seconds, median of 7; outcome, verdict, attempts and iterations identical across the 7 repeats
for every case.

| Case | Path | Outcome | Verdict | att / it | compile | init | solve | verify | **total** | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STR-01 | revision | CONVERGED | VERIFIED | 1 / 0 | 0.036 | 0.013 | 0.004 | 0.130 | **0.204** | 0.204 |
| STA-01 | revision | CONVERGED | VERIFIED | 1 / 0 | 0.026 | 0.006 | 0.004 | 0.077 | **0.114** | 0.117 |
| STA-02 | revision | CONVERGED | VERIFIED | 1 / 3 | 0.027 | 0.014 | 0.016 | 0.098 | **0.175** | 0.177 |
| STA-05 | revision | CONVERGED | VERIFIED | 1 / 0 | 0.012 | 0.000 | 0.002 | 0.028 | **0.043** | 0.043 |
| NUM-03 | revision | CONVERGED | VERIFIED | 1 / 0 | 0.012 | 0.035 | 0.002 | 0.024 | **0.073** | 0.075 |
| THM-01 | revision | CONVERGED | VERIFIED | 1 / 0 | 0.012 | 0.000 | 0.002 | 0.025 | **0.051** | 0.052 |
| THM-02 | revision | CONVERGED | VERIFIED | 1 / 0 | 0.012 | 0.006 | 0.002 | 0.024 | **0.054** | 0.054 |
| THM-03 | tear | CONVERGED | VERIFIED | 1 / 1 | 0.032 | 0.006 | 0.052 | 0.098 | **0.209** | 0.212 |
| THM-07 | revision | CONVERGED | VERIFIED | 1 / 0 | 0.012 | 0.001 | 0.002 | 0.023 | **0.038** | 0.039 |
| THM-08 | revision | CONVERGED | VERIFIED | 1 / 0 | 0.012 | 0.001 | 0.002 | 0.023 | **0.038** | 0.039 |
| THM-09 | revision | CONVERGED | VERIFIED | 2 / 2 | 0.022 | 0.002 | 0.017 | 0.053 | **0.094** | 0.095 |
| THM-10 | revision | CONVERGED | VERIFIED | 1 / 0 | 0.012 | 0.006 | 0.002 | 0.025 | **0.056** | 0.056 |
| NET-01 | tear | CONVERGED | VERIFIED | 1 / 1 | 0.031 | 0.005 | 0.059 | 0.097 | **0.215** | 0.221 |
| NET-02 | revision | **BOUND_BLOCKED** | — | 1 / 1 | 0.032 | 0.013 | 0.017 | — | **0.080** | 0.080 |
| NET-03 | revision | CONVERGED | VERIFIED | 1 / 4 | 0.056 | 0.014 | 0.027 | 0.243 | **0.375** | 0.388 |
| NET-05 | legacy EO | CONVERGED | VERIFIED | 1 / 3 | 0.039 | 0.055 | 0.013 | 0.087 | **0.214** | 0.274 |
| NET-06 | revision | CONVERGED | VERIFIED | 1 / 3 | 0.023 | 0.016 | 0.014 | 0.058 | **0.128** | 0.131 |
| NET-07 | revision | CONVERGED | VERIFIED | 1 / 3 | 0.024 | 0.013 | 0.015 | 0.094 | **0.156** | 0.201 |
| NET-08 | revision | CONVERGED | VERIFIED | 1 / 2 | 0.024 | 0.002 | 0.010 | 0.069 | **0.122** | 0.123 |
| NET-09 | revision | CONVERGED | VERIFIED | 1 / 3 | 0.030 | 0.002 | 0.014 | 0.097 | **0.154** | 0.179 |
| NET-10 | revision | CONVERGED | VERIFIED | 1 / 3 | 0.038 | 0.003 | 0.016 | 0.131 | **0.205** | 0.276 |
| NET-11 | revision | CONVERGED | **VerifierError** | 1 / 3 | 0.049 | 0.029 | 0.021 | 0.008 | **0.126** | 0.143 |

**Eligibility (§6.1).** Clause (a) as measured: 20 of the 22 reach their expectation
(`CONVERGED`, `VERIFIED`) from the registered initializer; NET-02 (F4) and NET-11 (F3) are the
two known failures, both as §2 recorded. Clauses (b)–(e) are definitional and nothing measured
here bears on them. Observation, not a finding against the spec: for nine acyclic cases
(STR-01, STA-01, STA-05, NUM-03, THM-01, THM-02, THM-07, THM-08, THM-10) the registered
initializer is already the root — Newton converges at iteration 0 — because the traversal
evaluates an acyclic flowsheet causally (STR-01's registered mechanism). Their ensemble starts are therefore ±20 % perturbations of the
root itself; §6.2 perturbs "about a registered initializer state", which this satisfies, and
A04's "not from a hidden converged answer" is not engaged (the initializer is registered and
causal, not hidden).

**Q10.** Largest median total 0.375 s (NET-03), largest single total 0.388 s (NET-03); every
median is below 0.6 s, so Q10's default — the 60 s ceiling — stands without amendment.
Verification dominates the time of every converged case (e.g. NET-03 0.243 of 0.375 s).

### M3 — today's STR-02, STR-06, STA-03, STA-04

`python scripts/t06_phase_m.py m3` (`validate()`; the legacy binding `bind_revision`; where it
binds, `solve_tear` under `SYN-001-K03` and `verify`; the general binding
`bind_revision_flowsheet`).

| Fixture | `validate()` | Legacy binding | Solve | General binding | vs §3.2's expectation |
| --- | --- | --- | --- | --- | --- |
| STR02 | `DRAFT`; SCHEMA-01, GRAPH-01/02, COMP-01/02, COND-01 `PASS`; STR-01…STR-05 `NOT_RUN`, message "…a specification the flowsheet needs is not declared: heater outlet temperature", implicated `["heater outlet temperature"]` | `None` | not run | `Unbound(incomplete, specification_missing(S3.T))` | **met today** |
| STR06 | `DRAFT`; COMP-01 `PASS` ("3 components: ['A', 'B', 'C']"); STR-01…05 `NOT_RUN`, "…not declared: feed flow of B", implicated `["feed flow of B"]` | `None` | not run | `Unbound(unsupported, specification_unsupported(SPEC-feed-n-B))` | **F2 reproduced** (no `COMP-03`; misdiagnosed as a missing B feed) |
| STA03-kgs | `READY_FOR_SIMULATION`, every check `PASS` | `Binding`; `FeedSource(U-FEED, flows=(0.1, 1.0, 1.0), T=300.0, P=100000.0)` | `CONVERGED`, certificate **`VERIFIED`** — of a different process: `S4.n` = (0, 0, 0) (all-liquid flash), `S6.n` = (0.1, 1.0, 1.0) | `Unbound(unsupported, specification_unit_unsupported(SPEC-feed-n-A))` | **F1 reproduced** |
| STA03-degC | `READY_FOR_SIMULATION`, every check `PASS` | `Binding`; `FeedSource(U-FEED, flows=(1.0, 1.0, 1.0), T=26.85, P=100000.0)` | `solve_tear` **raises** `SpecificationError: the once-through pass that defines the registered initializer failed: out_of_domain: U-MIX: liquid enthalpy: temperature 26.85 K outside [280.0, 440.0] K` | `Unbound(unsupported, specification_unit_unsupported(SPEC-feed-T))` | **F1 reproduced** (read as 26.85 K) |
| STA04 | `DRAFT`; COMP-01 `PASS` ("['C', 'A', 'B']"); STR-01…05 `NOT_RUN` ("cannot be analysed by T01's binding…") | `None` | not run | `Unbound(unsupported, components_unsupported)` | **met today** (the registered refusal) |

Two observations for the design lane, neither a new finding against the spec: (i) the general
binding already refuses both STA-03 variants with a typed `specification_unit_unsupported` —
F1 is confined to `validate()` and the legacy binding, where W1 puts its fix; (ii) on the legacy
path a feed outside the provider's domain (STA03-degC) reaches `solve_tear`, which raises
`SpecificationError` from the initializer rather than returning a typed outcome. W1's binding
refusal removes the route to it for this fixture; whether `solve_tear`'s raise on an
out-of-domain registered initializer is itself acceptable is not in M3's scope.

## 2026-09-26 — W4/W5 at `58e25bf` (base `a01a9d4`; no `src/` change)

### W5 A02 — the revision-built `verified_at_reference` cases under their registered policies

`pytest tests/test_t06_w5_corpus.py` (registry-driven: fixture, policy by registry key,
reference by `reference`/`reference_key`); worst `|x − x_ref| / allowance` over every registered
coordinate, T02 §6.4's allowances. Every run `CONVERGED` from `traversal-G0-v1` and `VERIFIED`.

| Case | Fixture | Policy | Coords | Worst ratio @ column |
| --- | --- | --- | --- | --- |
| STR-01 | SYN-001-UL-C1 | T06-revision-v1 | 45 | 5.98e-09 @ S6.n.A |
| STA-01 | T05b:DZ-3 | T06-revision-v1 | 41 | 9.83e-09 @ S6.T |
| STA-02 | SYN-001-T06-STA02 | T06-revision-v1 | 42 | 5.45e-03 @ S5.n.A |
| STA-03 | -kgs / -degC (revision path) | T06-revision-v1 | 35 | 2.09e-09 @ S2.T (both) |
| STA-04 | SYN-001-T06-STA04 | T06-revision-v1 and T05b-v2 | 34 | 1.16e-09 @ S2.T (both) |
| STA-05 | T05b:DZ-7 | T06-revision-v1 | 21 | 0 |
| NUM-03 | T05b:NP-1 | T06-revision-v1 | 8 | 1.96e-09 @ S3.T |
| THM-01 | SYN-001-T06-THM01 | T06-revision-v1 | 16 | 8.35e-09 @ U-FLASH.Q |
| THM-02 | SYN-001-T06-THM02 | T06-revision-v1 | 16 | 3.24e-09 @ S3.n.A |
| THM-07 | T05b:SC-2 | T06-revision-v1 | 11 | 0 |
| THM-08 | T05b:SC-1 | T06-revision-v1 | 11 | 2.37e-10 @ S2.liq.B |
| THM-09 | T05b:SC-3 | T06-revision-v1 | 22 | 5.72e-10 @ S4.n.B |
| THM-10 | SYN-001-T06-THM10 | T06-revision-v1 | 16 | 5.45e-09 @ S3.n.C |
| NET-02 | SYN-001-T06-NET02 | T06-revision-v1 | 43 | 1.86e-02 @ S3.liq.C |
| NET-03 | SYN-001-T06-NET03 | T06-revision-v1 | 71 | 2.08e-07 @ U-COOL.Q |
| NET-06 | SYN-001-T06-NET06 | T06-revision-v1 | 27 | 6.40e-08 @ S4.T |
| NET-07 | SYN-001-UL-C3 | T06-revision-v1 | 42 | 3.60e-03 @ S3.T |
| NET-08 | SYN-001-UL-C2 | T06-revision-v1 | 34 | 1.16e-09 @ S2.T |
| NET-09 | SYN-001-T06-NET09 | T06-revision-v1 | 44 | 4.46e-04 @ S2.T |
| NET-10 | SYN-001-T06-NET10 | T06-revision-v1 | 54 | 1.40e-06 @ S2.T |
| NET-11 | SYN-001-T06-NET11 | T06-revision-v1 | 60 | 3.24e-03 @ S5.T |

NUM-04 (never certified before): SYN-001-nominal's legacy binding, the `solve_eo` region of
its plan under `T02-eo`, started at the tear solve's `final_state`: `CONVERGED`, iterations 0,
Jacobian calls 0, `x_final` bitwise the tear state, `verify_bound` `VERIFIED` with no failing
check. NET-02's control (A63) under `T05b-v2` and `T05-W13`: `BOUND_BLOCKED`, iterations 1,
`unsupported(no_continuation_parameter)`, one item.

### W5 A19 — VER-02/VER-03's registered refusal has no path (stop-and-report)

K04 §7.6 REG-ε: `screen(csc([[0 + 1e-6]]), jacobian_identity={state_sha256: 0…0,
target_state_sha256: f…f})` → `NO_RANK_LOSS_DETECTED`, `rcond_1 = 1.0`, `inconclusive_reason
None`. `screen` records `jacobian_identity` and compares nothing (it takes no target state), so a
regularized SQ-0 masks the rank loss — exactly VER-02's mechanism. No test or source path yields
`INCONCLUSIVE(identity_mismatch)` (`grep identity_mismatch` finds only a docstring in
`verify/regularity.py`); the K04 manifest's "the refusal path for a mismatched identity exists
and is tested" is not borne out. The certificate-level stale-state guard is a `VerifierError`
(`state_mismatch(full_state_sha256)`, T04 A31 iii). Held as a strict xfail.

## 2026-09-26 — M7 and W6 (base `1f07cdc`; worktree `agent-ad00a0dccbbca61cd`)

### W6 inertness: step 5 extracted (`b92c659`) and the start-injection point (`d317633`)

Protocol (`thermo/syn001.py` `75c9d5ba…`; `scripts/k05_structural_identity.py` document whole
`91fac60822ddcebe…`, keys `t02` `6a912013…`, `t03` `12bdbcdb…`, `t04` `bdb5d94a…`, `t05`
`ddbd0f71…`, `t05b` `4f29500e…`; structural `4ce030cab1e4b4a2…`; `CheckPolicy().sha256`
`21c44e105a1b7842…`; `scripts/t02_identity.py --floats-out` `9a8a5baf14e4f04f…`): identical at
base, after `b92c659` and after `d317633`, the K05 document and the T02 floats byte for byte.
Direct comparisons against the code at `1f07cdc` (loaded from `git show` beside HEAD's):
`traversal_start` and `restart_start` on all 23 revision-built corpus fixtures, 46 of 46 starts
equal bit for bit (values, order, band routes); `execute_plan` with `user_start` absent, all 25
registered revision-path runs (the 23 registrations, NET-02's two edge-off controls) — every
event's document and the final state's bits — 25 of 25 byte-equal.

### M7 — the published starts (`benchmarks/t06/ensemble/starts-nominal-v1.json`)

`python scripts/t06_ensemble.py generate`, 2026-09-26T12:09:37Z, 5 s wall, no solve. Host
`ref-x86-64` (AMD Ryzen Threadripper PRO 5965WX, Python 3.13.5, numpy 2.2.4, scipy 1.15.3).
Generator `benchmarks/t06/generator.py` sha256 `7f426aa9f8a11455…`. File: canonical JSON,
1 109 603 bytes, sha256 **`641de215f74abde3c5e90dceed0daac13c5de8dbed003bdc59b5274254e6127e`**
(registry `ensemble.starts_sha256`). A25's test regenerates it byte for byte; a pre-publication
generation (the generator one docstring earlier, so another `generator_sha256`, same starts) was
regenerated byte for byte by `check` with the default BLAS threads and with
`OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=1`.

KATs (A21): 10 of 10 `k53`, `u_hex`, `delta_hex` bit for bit; the literal `0.2*w` differs at
exactly the three registered keys.

**Acceptance and rejection counts:** 440 of 440 starts accepted, **0 `F-GEN`**. 9 056 coordinate
draws, 1 161 rejected by the box, every one below its lower bound: on the accepted joint attempts
1 065 flows below 0 (dormant or small streams), 9 temperatures below 280 K, 2 extents below 0,
no pressure; 85 more flows in NET-01's refused joint attempts. 73 joint rejections, all NET-01's (tear path): `traversal_refused(unsupported)`,
"U-MIX: inlet 1 is not admissible as a liquid" (K03 §10.1's check on a perturbed recycle), at
most 12 before acceptance (start 13 attempts); THM-03's 20 starts needed none; no revision-path
start was refused by step 5 (`kernel_refused`: 0), so ADR 0017 D6's regeneration trigger (a
recorded rejection naming `not_converged`) does not apply.

| Case | path | coordinates | held at +0.0 | coordinate rejections | joint rejections | start ‖F̂‖∞ (min…max) | start rcond₁ (min…max) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| STR-01 | revision | 24 | 0 | 47 | 0 | 0.192…1.05 | 3.6e-4…5.9e-3 |
| STA-01 | revision | 24 | 0 | 156 | 0 | 0.252…0.489 | 9.9e-5…1.0e-2 |
| STA-02 | revision | 28 | 8 | 60 | 0 | 0.292…0.620 | 8.5e-3…1.3e-2 |
| STA-05 | revision | 10 | 0 | 69 | 0 | 0.131…0.199 | 1.4e-2…3.1e-2 |
| NUM-03 | revision | 8 | 3 | 34 | 0 | 0.164…0.377 | 6.8e-3…3.4e-2 |
| THM-01 | revision | 7 | 0 | 14 | 0 | 0.090…0.523 | 4.5e-5…1.0e-2 |
| THM-02 | revision | 10 | 0 | 22 | 0 | 0.164…0.413 | 9.7e-3…4.0e-2 |
| THM-03 | tear | 3 | 0 | 8 | 0 | 0.0035…0.166 | 3.4e-4…5.2e-3 |
| THM-07 | revision | 6 | 6 | 0 | 0 | 0.112…0.329 | 4.7e-3…2.5e-2 |
| THM-08 | revision | 2 | 8 | 0 | 0 | 0.041…0.720 | 5.1e-5…1.0e-2 |
| THM-09 | revision | 8 | 12 | 28 | 0 | 0.085…0.778 | 2.2e-4…8.0e-3 |
| THM-10 | revision | 10 | 0 | 19 | 0 | 0.155…0.537 | 1.1e-2…4.1e-2 |
| NET-01 | tear | 3 | 0 | 104 | 73 | 0.060…0.116 | 3.7e-4…2.7e-3 |
| NET-02 | revision | 30 | 0 | 83 | 0 | 0.206…0.889 | 3.7e-6…2.5e-3 |
| NET-03 | revision | 47 | 0 | 99 | 0 | 0.337…0.875 | 4.9e-5…8.0e-4 |
| NET-05 | legacy EO | 1 | 0 | 0 | 0 | — (pre-solve) | — |
| NET-06 | revision | 20 | 0 | 22 | 0 | 0.208…0.410 | 1.2e-2…2.5e-2 |
| NET-07 | revision | 35 | 0 | 71 | 0 | 0.187…0.502 | 9.0e-3…1.2e-2 |
| NET-08 | revision | 22 | 0 | 69 | 0 | 0.198…0.755 | 5.2e-3…5.5e-3 |
| NET-09 | revision | 28 | 0 | 77 | 0 | 0.304…0.745 | 2.2e-5…1.5e-3 |
| NET-10 | revision | 34 | 0 | 145 | 0 | 0.278…0.696 | 2.1e-5…1.2e-3 |
| NET-11 | revision | 39 | 0 | 34 | 0 | 0.303…1.38 | 1.2e-5…2.9e-3 |

(Coordinate rejections include those of refused joint attempts. Conditioning: the declaration's
compiled rows less the plan's eliminated alias rows, scaled by the plan's scales, exact dense
`rcond₁` — reported, not the region's regime-reduced matrix.)

**The split re-derivation (§6.2 step 5, no PH closure) against the registered start.** With every
selected coordinate at `x_init` (zero perturbation) the assembly reproduces `traversal-G0-v1`'s
start bit for bit on 17 of the 19 revision cases, including STR-01's and NET-11's valves, whose
closures took the PH kernel's bracket route. It does not on THM-08 (SC-1) and THM-09 (SC-3):
their valve's closure took the **saturation route** (pure B at `T_sat`), whose split
`S2.V = 0.0672` the TP re-flash cannot give (it calls a pure stream at `T_sat` liquid, as
`revision._start_from_pass` says). In the ensemble `S2.T` is perturbed off `T_sat`, where a pure
stream is single-phase and the TP flash is its split: THM-08's valve starts `LIQUID` in 11 starts,
`VAPOR` in 9; THM-09's `LIQUID` 12, `VAPOR` 8. Logged as a decision for design-lane confirmation.

**Acyclic census (§7.4 (A2), A84).** From each case's plan (T01's structural report: no loop):
**10** acyclic cases — STR-01, STA-01, STA-05, NUM-03, THM-01, THM-02, THM-07, THM-08, **THM-09**,
THM-10. §6.2 and §15 say nine; M2's list of nine was "the registered initializer is already the
root", which THM-09 (SC-3, 2 attempts) is not, although it has no loop. A finding against the
text (A84 anticipates it); the flag is not changed.

### W6 — the smoke run (5 published starts; the scoring ensemble is not run)

After the starts were committed (`9ecba79`): `python scripts/t06_ensemble.py run --out smoke.json
--cases STR-01 NET-01 NET-02 NET-05 NET-11 --starts 0` — start 00 of one case per path (revision,
tear, legacy EO) and of two revision cases with a recycle. Policies by canonical hash:
`T06-revision-v1` `27b6c8d6…`, `SYN-001-K03` `3cbefb93…`, `T04-W12` `1f7d1172…`.

| Start | path | class | first solve | attempts / iterations | regularity, rcond₁ | S3 worst / allowance | total s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| STR-01/00 | revision | SUCCESS | — | 1 / 4 | NO_RANK_LOSS, 3.15e-3 | 2.1e-4 (S6.T) | 0.143 |
| NET-01/00 | tear | SUCCESS | — | 1 / 2 | NO_RANK_LOSS, 1.16e-3 | 1.3e-9 (S3.n.C) | 0.168 |
| NET-02/00 | revision | SUCCESS, **rescued** | `BOUND_BLOCKED` | 1 / 6 | NO_RANK_LOSS, 6.33e-5 | 1.9e-2 (S3.liq.C) | 0.190 |
| NET-05/00 | legacy EO | SUCCESS | — | 2 / 6 | NO_RANK_LOSS, 2.41e-3 | 1.7e-2 (S3.vap.A) | 0.182 |
| NET-11/00 | revision | SUCCESS, **rescued** | `ACTIVE_SET_CYCLING` | 1 / 3 | NO_RANK_LOSS, 6.03e-4 | 3.2e-6 (S5.T) | 0.348 |

`S = 5` (first 3, rescued 2). Replay (`replay smoke.json`): 5 of 5 `MATCH`. A32: 5 matrices,
estimate/exact within 1.1e-14 of 1, no estimate above the exact norm beyond 1e-12, no status
disagreement. A33: 0 failures. Wall times (compile / init / solve / verify) sum to within the
total's harness overhead; the largest total 0.35 s against the 60 s ceiling. CasADi prints two
`DomainError` tracebacks to stderr during NET-05's run (`H_S3_liquid` at `T = 442.6396 K`, T02's
registered liquid-branch root of `Q_flash = 0`, outside the provider's domain): the compiled
residual reports them as an `error` evaluation — a rejected trial, not an escaped exception —
and no crash is recorded.

### W6 — A32 over every certificate the corpus issues (§8.3 (A2))

`tests/test_t06_w6_a32.py`: 44 certificates re-issued with the screen captured — A02's 23
revision-path runs, 5 tear-path (NET-01, THM-03, THM-04, STA-03 kg/s and °C), NUM-04, 4 on the
bound declaration (HOM-01 = ADV-01; A02-355/360/365 = NET-05 and its variants), 9 our-side REF
solves (REF-01…08, PC-2), STR-05's twin CH-UP-DP and T05 INJ-T1's twin (VLV-2). 44 matrices,
`n` 11…79. Estimate / exact `‖Ĵ⁻¹‖₁` ∈ [0.9514, 1 + 8.2e-15]: never above the exact norm beyond
1e-12; the smallest is STA-02 (the seeded estimate 4.9 % low), and there the exact norm takes the
same decision (`none`: neither the relative nor the absolute test fires). No status flips at any
of the 44. ADV-06 L/M are not covered: `NoisyProvider` is W7's and does not exist yet.

## 2026-09-26 — W13 (ADR 0017, F6) at `9ede861` (base `b708b56`)

The one change to `src/process_runtime/thermo/syn001.py` (+11/−1): on `f(0)·f(1) > 0`,
`_rachford_rice` returns `β = 0` (both negative) or `1` (both positive) with **zero
iterations**, and `flash` answers `_single_phase` for that phase. Implementation hash
`75c9d5bad4f1cb3c8aa28b97d529777949434ebf911c0d9e11568b1e69ddd6ce` →
**`67e472816d4d67676f4cac64861e815602de01b3e7621e225f93cbdfda32982a`**.

**Protocol** (each phase): `scripts/k05_structural_identity.py --out k05.json` (document digest
= the file's SHA-256; "minus" digests and keys as in `docs/t05b-measurements.md`: `json.dumps(…,
indent=1, sort_keys=True) + "\n"` and `json.dumps(key, sort_keys=True)`); `CheckPolicy().sha256`;
`scripts/t02_identity.py --floats-out`; `scripts/{k03,k04,k05,t04}_schema_fixtures.py` (check
mode) and K05's four documents with `VOLATILE_FIELDS`/provenance keys stripped;
`scripts/t05b_ph_baseline.py --check`; the full `pytest` with two measurement plugins (not
committed): one digests every `Syn001Provider.flash` call per test node (`repr((request,
result))`, round-trip exact) and records every non-`ok` result and every bracket-branch return;
the other records every `verify`/`verify_bound`/`verify_revision` certificate (document SHA-256,
verdict, checks, limitations, regularity floats; W2/W3's plugin). **A78's old hash** is
substituted by a `sitecustomize` import hook on `PYTHONPATH` that replaces
`thermo.syn001._implementation_sha256` with a function returning the pre-commit value, in every
process (subprocesses included; checked with a dummy hash).

### A78 — the fix with the old hash: byte-identical except F6's registrations

| Item | Base (`b708b56`, unmodified) | Fix + old hash |
| --- | --- | --- |
| provider-reported hash | `75c9d5ba…` | `75c9d5ba…` (file `67e47281…`) |
| K05 identity document | `91fac608…cdf06` | identical |
| minus `t05b` / minus `t05`,`t05b` | `622463f5…` / `b364bb3d…` | identical |
| keys `t02` `t03` `t04` `t05` `t05b` | `6a912013…` `12bdbcdb…` `bdb5d94a…` `ddbd0f71…` `4f29500e…` | identical |
| `structural_sha256` / `artifact_r0_sha256` | `4ce030ca…` / `9285e860…` | identical |
| `check_policy_sha256` / T02 floats | `21c44e10…` / `9a8a5baf…` | identical |
| K03, K04, T04 fixture generators | "all fixtures match" | identical |
| K05 documents, volatile stripped | `45fda154…` | identical |
| T05b PH baseline | matches | matches |
| suite | 3681 passed | 3678 passed, **3 failed**: `test_wo3_c3_is_truncated_at_pass_4_by_u_mix`, G6 C3 × {`T05-W13`, `T05b-v2`} — F6's registrations |
| certificates issued by the suite | 662 | 662, every record identical (document SHA-256 included) |
| flash calls (nodes) | 114 039 (936) | 115 242 (936); **932 nodes byte-identical** |

The 4 nodes whose flash sequence differs all build C3's restart start: the 3 registrations and
`test_wo3_no_compiled_residual_or_jacobian_is_called` (passes both times). In the whole suite the
bracket branch fires in exactly 4 calls, one per such node — C3's traversal pass 4 — where the
base returned `not_converged`; C3's traversal then continues to pass 8 (186/187 → 487 calls).
The 9 `out_of_domain` and 1 `unsupported` results are the same calls in both. T06's our-side
reference records (A50: live solve == committed record, `certificate_sha256` included) pass
under the old hash, so they too are byte-identical.

### A79 — the real hash: the re-baseline

| Item | New value |
| --- | --- |
| `implementation_sha256` | `67e472816d4d67676f4cac64861e815602de01b3e7621e225f93cbdfda32982a` |
| K03 `model_version` | `SYN001-fs1-syn001-67e472816d4d-44f894ff62f9@73a8950bc0038a967ddf8cf7f5d1d07695ff6c230e1965ff898fe8e02ef67769` |
| K03 `plan_id` | `SYN-001-SYN001-fs1-syn001-67e472816d4d-44f894ff62f9-SYN-001-K03` |
| every SYN-001 label | `<prefix>-syn001-67e472816d4d-44f894ff62f9[@…]` (`SYN001-fs1`, `FSR1-<12 hex>`); 18 distinct `model_version`s in the identity document, their sorted list digests to `a6f60945…` |
| K05 `structural_sha256` | `915c97e82551c75c588ec4a4e41b060241d75e037366c099c285493165a97e27` |
| K05 `artifact_r0_sha256` | `77508d4ac3373f523f87c89ba83841173f94ba12c608deb3c8ab83053576471d` |
| K05 identity document (whole) | `00ff5a9ab5f3d7431ae5d553a8305ea1d4edd2d9ddb70bb7dfa31c6b751bd475` |
| minus `t05b` | `29cb0bacfd44e8a53f89bc12d1381ba10916ca0247568bb1ef61e4c795193e4b` |
| minus `t05`, `t05b` | `d67f59ebdd274e2a30f77c0f85dbd37c5c3a4517ea848452e8e892a488636abf` |
| key `t02` | `0b75311abed11b504fbac422a7851459d7c90a499e86c7fd3d409e1afc1fcf8d` |
| key `t03` | `1b8a5b2e8b60637c39f1cd81ccded92b6112f5574b6d0ffee0c15f53e293e666` |
| key `t04` | `c0b9bee7a1961175af052153b115d98413d100bde71d4031ba0dc6ec4ed9b142` |
| key `t05` | `24199c7efe863ae3b17d3033b29ca8da54e76e4bac6a6540931596aab0c5be1f` |
| key `t05b` | `3f2feee21d5b241743c6f237ffee09a34e4d7fd229be5c972a9619ee5511be47` |
| unchanged | `policy_sha256` `051a894c…`, `constants_sha256` `4054a86c…`, `check_policy_sha256` `21c44e10…`, T02 floats `9a8a5baf…` |

**Substitution check** (pre-commit document with `75c9d5ba…` → `67e47281…` and `75c9d5bad4f1` →
`67e472816d4d` applied, leaf by leaf against the new one): the identity document, 31 109 leaves,
190 label occurrences — the only other differences are the digests `structural_sha256` and
`artifact_r0_sha256`. The suite's 662 certificates: every field equal except the two document
digests (633 of 662 move; the other 29 do not change). Flash call sequences, A78 vs A79:
identical in every common node except G6 C3 `T05-W13` — under A78 that test stopped at the old
`passes_used == 3` assertion before solving, under A79 it solves, and `T05-W13`'s opening
projection makes one kernel flash (`T05b-v2`'s none; the base shows the same +1, 187 vs 186).

**Regenerated with their committed generators (R-015)**, each checked by the substitution:

- `scripts/k03_schema_fixtures.py --write`: `solve_plan/valid/syn001_nominal.json`,
  `solve_event/valid/syn001_nominal_trace.json`, `solve_event/valid/syn001_off_b_restart_trace.json`,
  `attempt_context/valid/syn001_restart.json` — substitution only.
- `scripts/k04_schema_fixtures.py --write`: `solution_certificate/valid/syn001_nominal_verified.json`,
  `solution_certificate/valid/syn001_trivial_root_failed.json`,
  `regularity_evidence/valid/syn001_nominal.json` — substitution only.
- `scripts/t04_schema_fixtures.py --write`: `attempt_context/valid/t04_hom05_homotopy.json`,
  `attempt_context/valid/t04_ptc_restart.json`, `solution_certificate/valid/t04_hom01_bound_verified.json`
  — substitution only.
- `scripts/k05_schema_fixtures.py`'s `run_manifest/valid/syn001_nominal.json` only (A81 (b): a
  compared field moved; the three replay reports carry no label and are not rewritten), with
  `OMP_NUM_THREADS=1` as committed: substitution plus the digests `structural_sha256`,
  `artifact_r0_sha256`, `manifest_sha256`, four artifact digests, and the volatile
  `elapsed_seconds`, `started_at`.
- `scripts/t06_references_ours.py`: the nine `benchmarks/t06/references/results/ours-*.json`, each
  exactly one line (`certificate_sha256`); then `scripts/t06_reference_comparison.py --write`
  (`comparison.json`: the nine input digests only, no row moves) and the README's `SHA256SUMS`
  command (the nine lines).

No gate test pins `4ce030ca…`, `b364bb3d…`, `91fac608…` or a key digest (grep over `tests/`,
`scripts/` outside the closed packages' manifest generators, `benchmarks/`, `.github/`); CI's
identity job compares the two platforms with each other, not with a registered value. The
historical records in `scripts/t05_evidence_manifest.py`, `scripts/t05b_evidence_manifest.py`
and `docs/derivations/scripts/k04f9_reference.py` (`identity_under_the_prototype`) are left as
the records of their commits (ADR 0017 C3). **Not run:** the CI identity job on x86-64 and
aarch64 (ADR 0017 D3 (3)); it needs a push.

### A75–A77

- **A75** (`tests/test_t06_w13_f6.py`): `F6-liquid` → `ok`, `LIQUID`, `β = 0.0`, message `""`,
  vapour outlet dormant at the feed's `T`, `P`, liquid outlet the feed bit for bit; `F6-vapour`
  mirrored (`VAPOR`, `1.0`). Control (x86-64 only): both states meet D1's condition in the
  provider's arithmetic. Before the fix both were `not_converged`, "Rachford-Rice did not reach
  1e-14 in 200 iterations".
- **A76**: 10 000 feeds from `F6-reflash-v1|<i:04d>|<field>` → 1 470 two-phase, 2 940 re-flashes.
  Before: 21 `not_converged` (8 liquid, 13 vapour), each meeting D1's condition — the spec's
  measurement. After: all 2 940 `ok`; the 21 return the phase D1 names; every other outcome count
  unchanged (liquid products: 223 `TWO_PHASE`, 1 239 → 1 247 `LIQUID`; vapour: 242 `TWO_PHASE`,
  1 215 → 1 228 `VAPOR`).
- **A77**: C3's restart start `passes_used = 8`, `rejected = ()`; G6 C3 `CONVERGED`, worst
  3.458e-4 of an allowance at `S3.T` under both `T05-W13` and `T05b-v2`; every G6 case keeps 8
  passes. F4's truncation branch (a pass `j ≥ 3` a unit refuses), which only C3 exercised,
  stays covered: `test_wo3_a_unit_refusing_pass_j_truncates_the_sequence_to_j_minus_1` injects
  C3's old pass-4 refusal and asserts 3 passes and the recorded rejection.

Gate: `./scripts/check.sh` at `9ede861`: ruff, format, mypy clean; **3687 passed** (3681 + 6 new).

## 2026-09-26 — W16 (A3.11): the starts file re-emitted for the provider hash (base `ec7ca59`)

`python scripts/t06_ensemble.py generate --force` on `ref-x86-64` (host block unchanged:
AMD Ryzen Threadripper PRO 5965WX, Python 3.13.5, NumPy 2.2.4, SciPy 1.15.3;
`OMP_NUM_THREADS=2`), `benchmarks/t06/generator.py` untouched (`generator_sha256` `7f426aa9…`, as
recorded): 22 cases, 440 starts accepted, 1 161 coordinate and 73 joint rejections (all
`traversal_refused(:unsupported)`), 0 `F-GEN` — the M7 counts. 1 109 603 bytes, sha256
**`3a7bd49c66493744753d1eac554101317c931e0ef51d9154d6f7cab3124fef82`** — the value A3.11
registers, exactly. `check` then regenerates it byte-identically.

**JSON-path proof** (leaf-by-leaf walk of the parsed documents, dict keys unioned, list lengths
compared, leaves compared by type and value; script not committed): against the committed
`641de215f74abde3c5e90dceed0daac13c5de8dbed003bdc59b5274254e6127e` document, **one** differing
path — `/provider/implementation_sha256`:
`75c9d5bad4f1cb3c8aa28b97d529777949434ebf911c0d9e11568b1e69ddd6ce` →
`67e472816d4d67676f4cac64861e815602de01b3e7621e225f93cbdfda32982a` (ADR 0017's move, the live
`Syn001Provider().describe().implementation_sha256`). `git diff --stat`: one line changed. Every
start, draw, rejection, regime and conditioning value is unchanged.

The registry's `ensemble.starts_sha256` → `3a7bd49c…`. A25's test now regenerates with the live
provider's block (`_live_provider_block()`, from `Syn001Provider().describe()`) and asserts the
published block equals it. Negative control: with the `641de215…` file restored, A25 and the
registry-hash test both fail (2 failed); with `3a7bd49c…`, both pass.

## 2026-09-26 — W9: the `t06` identity key (base `a41881e`, no `src/` change)

`scripts/t06_identity.py`, included by `scripts/k05_structural_identity.py` as key `t06` (§10,
ADR 0014 D8 (amended)). Every entry is under its **registered** policy: §4.3's ten flowsheets,
REF-01…REF-07 and ADV-06 L/M/H under `T06-revision-v1`; NET-02's control under `T05b-v2`
(`BOUND_BLOCKED`) as its own entry; STA-03's variants, A69's `3.6 kmol/h` and `80.33 degF`
spellings, and §8.7's feeds on the tear path under `SYN-001-K03`; STA-04 under `T06-revision-v1`.
Measured outcomes: the 10 new cases and 7 REF fixtures `CONVERGED`/`VERIFIED`; ADV-06 L
`VERIFIED`, M `CONVERGED`/`UNVERIFIED`, H `INITIALIZATION_FAILED` (`initializer_failed(U-VLV):
ph_ill_conditioned`); the four STA-03/A69 tear records equal SYN-001-nominal's; STA-04's record
equals C2's (declared order `C, A, B`); §8.7's three feeds `INITIALIZATION_FAILED` with A62's
messages. Ensemble definition: 22 cases with fixture ids and selected coordinates (equal to the
published file's), per-path policy ids and `policy_sha256` (`T06-revision-v1` `27b6c8d6…`,
`SYN-001-K03` `3cbefb93…`, `T04-W12` `1f7d1172…`, each equal to the registry's), `nominal`,
`T06-ens-v1`, `sha256-counter-v1`, the ten KATs' `k53`. `floats_in` empty; hex digests only under
`constants_sha256`, `model_version`, `variable_ids_sha256`, `policy_sha256`.

| Item | Value |
| --- | --- |
| K05 document (whole) at base | `00ff5a9ab5f3d7431ae5d553a8305ea1d4edd2d9ddb70bb7dfa31c6b751bd475` (A79's) |
| new document minus `t06` (`json.dumps(…, indent=1, sort_keys=True) + "\n"`) | `00ff5a9a…d475`, byte-equal to base |
| `structural_sha256` | `915c97e82551c75c588ec4a4e41b060241d75e037366c099c285493165a97e27` (unchanged) |
| keys `t02` `t03` `t04` `t05` `t05b` | `0b75311a…` `1b8a5b2e…` `c0b9bee7…` `24199c7e…` `3f2feee2…` (A79's) |
| key `t06` (`json.dumps(key, sort_keys=True)`) | **`f7f928c92f297838569ad619c8d0f03ab3017e2fb4ef5e2f3bb47349b0cd0a66`** |
| K05 document (whole), new | **`0e8b8d4681fefd91ebd2619f679767d0f84939411e6cabc47d36ec50d23eef6f`** |
| `check_policy_sha256` / T02 floats / `thermo/syn001.py` | `21c44e10…` / `9a8a5baf…` / `67e47281…` (unchanged) |

Two emissions in two processes are byte-identical. §8.7's 400 K message carries one computed
number, `{equivalent:.3g}` K (`models/syn001/mixer.py`, "misplace the outlet temperature by 300
K"); recorded verbatim as §10 asks for the first line. **Not run:** the CI identity pair
(x86-64/aarch64, A45); it needs a push.

## 2026-09-26 — W18 (ADR 0018): `T06-revision-v2` (base `364d2ce`)

| Item | Value |
| --- | --- |
| `T06-revision-v2` `policy_sha256` | `c03d7205fb445b4e3c0d2c5d712c04fc60fbb6bde1f8ff753c7cedffd61c66ab` (v1 `27b6c8d6…` unchanged) |
| K05 document minus `t06`; `structural_sha256` | `00ff5a9a…`, `915c97e8…` (unchanged) |
| keys `t02` … `t05b`; `check_policy_sha256`; T02 floats | unchanged (`0b75311a…` `1b8a5b2e…` `c0b9bee7…` `24199c7e…` `3f2feee2…`; `21c44e10…`; `9a8a5baf…`) |
| key `t06` | **`e0e871f6e4f803bac876ae06a0204a3c31f2c1880135d8c5b8ef0a313424ad6d`**; equal to the base key after substituting the policy id (in `policy_id` and the plan ids) and the policy hash — the rule fires in none of the key's solves |
| K05 document (whole) | **`9a7b4e6d1e794e903a41ba2bd96ead58a074896380d80e37e0f06545cff3d4bc`** (base `e4892e75…`) |

With the hook in and no policy selecting it: the K05 document byte-identical (`e4892e75…`) and every fixture generator's output identical. A87 (b), the 19 revision cases' registered-start solves, `newton` against `newton_refined` under otherwise one policy: the rule fires in none; traces R0-equal, final states bit-identical, every event equal except the closing events' `linear` record. A89 (THM-09 under v2; S3 worst ratio, chord `ρ_max` before → after, all kept, all on `S3.T`, all `VERIFIED` `SUCCESS`): start 1 `1.842e-6` (10.02 → 1.84e-5), 2 `2.166e-5` (34.30 → 2.17e-4), 5 `1.859e-6` (10.07 → 1.85e-5), 10 `3.723e-6` (14.24 → 3.72e-5), 6 `2.444e-7` (3.65 → 2.42e-6), 19 `1.705e-6` (9.64 → 1.70e-5); under `newton` the same starts measure 1.005, 3.447, 1.010, 1.429, 0.366, 0.967 (run 1's). The reference results' `certificate_sha256` moved on REF-03, REF-04, REF-05 and PC-2 on regeneration although a v1 and a v2 certificate of the same fixture are equal documents in one process: the committed hashes predate the current verifier (most likely W19's §8.8 closure, which changes exactly the two-phase splits' checks; not bisected), and `test_a50_our_committed_record_is_what_a_live_solve_produces` does not compare that field.

## 2026-09-26 — W21 (Q23, A94): where the three `F-BUDGET` starts' property calls go

**Outcome: none landed.** No cost remedy is committed; the three starts stay `F-BUDGET` in run 2 unless the design lane admits one (spec §6.6 (A4), Q23).

**Attribution** (every call the `PropertyMeter` charged, by the outermost solver frame and the kernel path; under `T06-revision-v2`, which never fires before the budget runs out; the 10 001st is the refused call):

| Start | phase controller (`decide` → `ph_state`) | of which `_band_route` → `big_f` → `band_temperature` → `_k_values` | trial phase screen (of which `band_temperature` → `_k_values`) | residual rows | Jacobian rows |
| --- | --- | --- | --- | --- | --- |
| THM-08/3 | 6 190 (two `ph_state` calls: 3 057, 3 131) | 5 761 | 3 650 (3 392) | 124 | 37 |
| THM-08/12 | 5 956 | 5 535 | 3 878 (3 604) | 130 | 37 |
| THM-09/4 | 3 883 | 3 538 | 5 696 (5 194) | 342 | 80 |

**Mechanism.** `band_temperature` bisects `T(β)` over the provider's whole `[280, 440] K` to adjacent doubles, about 50 `lnK` calls; `ph_state`'s band route bisects `β` with one `band_temperature` per `β`, about 55 × 55 ≈ 3 000 calls per invocation; the trial screen's band ends cost about 100 per screened trial. Residual and Jacobian rows are under 5 %.

**Candidate, not landed.** For a single-component stream (THM-08's and THM-09's pure B) the sign of `g(T) = (K − 1)/(1 + β(K − 1))` is the sign of `K − 1` for every `β ∈ [0, 1]`, so every `band_temperature` of one band route (and a screen's bubble/dew pair) visits the same midpoints: `lnK` at exactly repeated `(n, T, P)`. An exact `lnK` memo scoped to one band route would return bit-identical `K` and remove most of the 5 500–5 800 band-route calls; the saving was **not measured**. Left to the design lane because (i) whether a memoized request counts as `requested_evaluations`/`cache_hits` or as not requested is a counters-semantics decision (blueprint §6.4, R-015; the region path records `requested_evaluations = property_calls`, `cache_hits = 0`); (ii) it moves `property_calls` in every registered PH-type trace and fixture that records it; (iii) it must sit at `lnK`, not at `band_temperature`'s answer: on an adjacent-double tie `bracketed_root`'s choice of end depends on `β`, so a `β`-blind memo of the answer is not result-inert.
