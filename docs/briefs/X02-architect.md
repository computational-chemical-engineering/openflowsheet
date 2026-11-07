# Architect brief: X02 — declared warm starts for external and coupled units (0.4)

Status: brief, 2026-11-07. Roadmap (ADR 0057) 0.4 package X02, design pass: architect. Recon 2026-11-07 (Haiku; facts
below; paths under `src/openflowsheet/`).

## 1. The question

How does a run declare and use a warm start for external and coupled units — a previous converged state or a user
iterate — such that the certificate judges the converged answer independently of the start, the cache key and the
bundle state whether a warm start was used, and nothing that runs cold changes by one bit? Return a design note with
work orders and verification gates.

## 2. Why it needs the architect

It lifts two registered decisions (R-224, R-287) that were rejected for identity reasons: a warm start makes results
history-dependent at ~1e-8, which an exact cache cannot key (ADR 0033:106-107). It touches the experiment cache key,
the coupled outer loop, replay identity (rerun from a bundle) and the request protocol of external children — and must
stay inside the frozen v2 core (R-941; ADRs 0065–0067) and F0's identity gate.

## 3. Current state

**The lift (ADR 0056 row 2, Accepted, `docs/adr/0056-capability-extension-plan.md:28`):** "A declared warm start
(previous converged state, or a user iterate) for external and coupled units; the certificate checks the converged
answer independently; bitwise identity across warm/cold is not claimed and the cache key states whether a warm start
was used." Target note `docs/roadmap/target-architecture.md:772`: "X02 extends the cache key additively; the
warm-start member appears only when a warm start was used." (:1045 "additive cache key".)

**Registered decisions being lifted (R-925 lifts both as policy for X02):**
- R-224 (`docs/decision-register.md:4950`): cold S1–S3 only, no reactor warm start, no persistent child. Rejected
  alternative (ADR 0033:106-107): warm-starting from a neighbour → history-dependent at 1e-8; an exact cache cannot key it.
- R-287 (`:6469`): `parameter_unsupported(<U>.coupling_initial.X | .dT)`; w0 is the variant's `coupling.initial`.
  Rejected: an optional signature member, "a start point is solver state (ADR 0020 D7)". Recon note: ADR 0020 D7
  (`docs/adr/0020-job-execution-and-revision-runs.md:126-129`) actually says "No T07 operation accepts a matrix or state
  from outside" — reconcile.
- M02 N6 (`docs/design/M02-pymrm-adapter.md:882`): "no warm start of the reactor … Reversible by: a new variant with a
  warm profile whose requests carry the warm source in their identity."

**Existing warm-start machinery (T08 W4, ADR 0024 `docs/adr/0024-compatible-warm-starts.md`, built):** opt-in by
policy `T08-warm-v1` (`application/policies.py:12-13, :40, :86`); D1 "a user_start wins"; D2
`store-latest-verified-lineage-v1`; D4 bundle record; D5 replay; D6 contract unchanged.
- `application/store.py:1083-1110 latest_verified_solution(...)`: latest VERIFIED `solve` job in the revision lineage
  with a `solution_state` artifact. `application/jobs/runner.py:210-230 warm_start_candidate(...)`.
- `orchestrator/warm_start.py` (136 lines): `WarmStartCandidate(document, source_job_id, source_revision_id,
  selection)`, `from_record` (rerun), `WarmStartRecord`, `intact`, `compatible`, `project_bounds`; "the candidate
  supplies only x0".
- `run/solution_state.py`: `solution-state-v1` {state_sha256, variable_ids, variables}. `revision_run.py:837-839`
  writes `solve_path["warm_start"]` iff consulted; `:981-985 _recorded_warm_start` for rerun. `run/identity.py:128-149`
  R0 projection keeps status/reason/selection/ids, no values.
- `orchestrator/executor.py:222` `user_start`; `:246-252` refused on SYN-001 flowsheets and checked against columns.

**External and coupled paths (cold today):**
- Protocol `adapters/external/protocol.py:1-52`: one attempt = one child, JSON request on stdin, `result.json`; no
  start-point field. `adapters/experiments/request.py:60-94 build_request(variant, capabilities, n_tubes, components,
  inlet, environment_fingerprint_sha256)`; `:53-57 experiment_key = document_sha256(request − key)`, members `model{id,
  version, artifact_ref}`, `boundary{provider_id, provider_identity_sha256, n_tubes, sweep_ratio}`, `inputs`,
  `environment_fingerprint_sha256`; no warm member. Store `adapters/experiments/store.py:126-133` by key.
- pymrm child `adapters/pymrm/child.py:126-139`: PROFILE S1 (trace_NH3 1e-9, dt_init 1e-6), S2 starts from S1's fields
  within one evaluation only; `:747 first.solve(dt_init=...)`. Runner `adapters/experiments/runner.py:250-257`
  (`cache: "use" | "bypass"`).
- Refusal: `application/revision_binding.py:540-547` (`parameter_unsupported(<unit>.<name>)` for unknown parameters);
  `:1358-1363` comment (build log D46); `:1383-1387` `initial = variant.coupling["initial"]` → X, dT_K.
- Coupled: `application/coupled_run.py:662-676 solve_coupled(binding, *, policy, experiments, trace=None,
  warm_start=None, on_iteration=None)`; warm_start read by the k=0 inner solve only (`:680-700`, label
  `route_initializer` / `user_start`). Outer loop `orchestrator/coupling.py:286-297`; outer start = `block.initial`
  (`:316`); nothing reads a previous coupled outer iterate. Caller `revision_run.py:679-705`, dispatch `:536-545`.
- Certificates: `verify/certificate.py:681-690 verify_revision(...)`; no reference to warm start or iterate history.
  `coupled_run.py:796-851 coupling_evidence`: reads the final iterate's entries, `coupling.w` and the attributed request
  (`_inputs_equal :760`); EXT-COUPLING:<unit>:xi / :T checks.
- Caches: `thermo/cache.py:175-215` exact property/flash keys; `:270-290 WarmStartCache` approximate, guesses only.
- F0: M6 pins thermo provider cache keys only (`scripts/corpus_identity.py:62-66, :339-365`), not experiment keys; M7
  pins replay verdict/integrity of the 52 v0.3.0 bundles.

**Tests pinning today:** `tests/test_m02_wo9_reactor.py:386-398` (refusal `parameter_unsupported(R.coupling_initial.X)`),
`:442` (cold w0 = 0.15, 80 K converges and verifies); `tests/test_m02_wo10_coupled.py:178, :184, :302, :363`;
`tests/test_m02_pymrm_child.py:441, :555, :825`; `tests/test_m02_experiments.py:374`;
`tests/test_t06_w6_injection.py:104` (user_start refusal); `tests/test_t08_w4_warm_starts.py` B40–B49.

## 4. Constraints and invariants

- Cold runs bit-identical: every existing experiment key, cache key, bundle, replay verdict and certificate at a cold
  start unchanged (F0 M1–M9 PASS; existing tests' node ids and expectations unchanged).
- Exact caches key on exact canonical inputs; a warm-started result is never served for a cold request or vice versa;
  the warm member appears in a key only when a warm start was used (additive).
- The certificate's verdict must not depend on the start (judged on the converged answer); state what "independently"
  means for EXT-COUPLING checks.
- Replay: a bundle made warm must rerun from its recorded start (ADR 0024 D5 pattern); the mode rules of ADR 0007 D4
  unchanged.
- Frozen core (R-941): ADRs 0060–0067 "Core at the end of W1"; the schemas in plan §2.2 change only by ADR (ADR 0019
  amendment, next free 14 — X05 may take it; verify).

## 5. Already decided / genuinely open

Decided: the lift itself and its sentence (ADR 0056 row 2); bitwise warm/cold identity not claimed; T08 W4's machinery
exists and should be reused where it fits; no persistent child unless the design argues it.
Open: (a) the warm source(s) for an external unit — previous converged experiment, previous run's solution state, user
iterate — and how each is addressed; (b) the request/protocol member and the experiment-key member; (c) whether the
coupled outer loop may start from a previous converged w (and how R-287's `coupling_initial` parameters are admitted);
(d) declaration surface (policy, revision parameter, operation argument) and its contract/schema impact; (e) refusal
and fall-through rules (incompatible, missing, unverified source) and their messages (MSG catalogue codes); (f) what
the pymrm child does with a warm start (S1 skipped? profile seeded?) and the evidence that it converges to the same
answer within the certificate tolerance; (g) the replay record.

## 6. Already tried and rejected (with evidence)

- Neighbour warm starts keyed into the exact cache (ADR 0033:106-107): history-dependent at 1e-8 → rejected; any design
  must key or segregate warm results.
- `coupling_initial` as an optional signature member (R-287): rejected as "solver state" — reconcile with ADR 0020 D7's
  actual text.
- Reactor warm profile without the source in request identity (M02 N6): rejected.

## 7. Verification the build will be judged by

Cold identity: F0 PASS; full gate; existing M02/T08 tests unchanged. Warm: converged answer within the certificate's
tolerance of the cold one on the registered reactor case(s), certificate VERIFIED on both, warm member present only when
used, rerun from bundle reproduces the warm run, refusals with catalogue codes and controls. Name the cases and
tolerances.

## 8. Deliverable

`docs/design/X02-warm-starts.md` (design note: decisions with rejected alternatives, interfaces, key/record formats,
work orders sized ~150k context each, gates) and, if the contract or a schema changes or a registered decision is
reversed, `docs/adr/0070-X02-warm-starts.md` (Proposed; ADR numbers: 0069 is X05's — verify the next free). Draft
register lines (unnumbered: `wp/MSG` and `wp/RP` hold R-942…R-949 unmerged). Commit on main (docs-only, named paths).

## 9. Out of scope

F6–F8 builds; OPT; RRC (revision-region continuation, a separate architect pass); X05; dynamic initial conditions
(ADR 0066 D5).
