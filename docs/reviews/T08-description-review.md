# T08 — design-lane review of the 17 MCP tool descriptions (T08.A18) and three small rulings

**Reviewer:** design lane (`reviewer`), 2026-10-01. **Branch:** `wp/T08` at `d43bf2c`. **Brief:**
`docs/briefs/T08-description-review.md`. This is a review of the text only. It edits no description, no
`REVIEW.json`, and commits nothing.

## Method

I read each description against what `dispatch` does today, using `application/operations.py` (rows, request
schemas, the wait cap), `local.py` (`_result`, `_wait`, `list_job_events`, `get_project`, `_prepare`,
`_conflict`/`_rejected`), `admission.py` (tolerances, budgets, `POLICY_UNSUPPORTED_ON_ROUTE` = ∅),
`verify/certificate.py` (`is_registered` → RELAXED), `policies.py`, `revision_binding.py` (`_KINETIC_CSTR`, the
target-path table), the T08 diff of `application/`, and the job, transaction, application-result and run-result
schemas. In-process probes through `dispatch` (`.venv/bin/python`, a fresh project with read, draft and execute
rights):

- `get_project` lists `T04-W12`, `T06-revision-v2`, `T08-ptc-v1`, `T08-warm-v1` with hashes, and `default_policy_id` `"default"`.
- `list_models` lists `syn001.kinetic_cstr` with `pins: []`, `choices: []`, a `duty` energy inlet, and 8 required parameters.
- `validate {task: "optimization"}` returns `unsupported`, `task_unsupported(optimization)`, `/task`.
- `list_job_events {after_sequence: "5"}` returns `invalid_request`, `'5' is not of type 'integer'`.

I grepped the V17 transcripts (`benchmarks/t07/v17/runs/v17-c1`, `v17-c2`):

- No call anywhere uses `optimization`. Every `task` value is `"simulation"`.
- `list_job_events` appears 120 times, with no integer-type refusal.
- There are 6 `conflict` and 3 `rejected` transaction results.

All 17 files hash to their `REVIEW.json` records.

The T08 changes to the agent surface are U05 (a change of behaviour), two offered policies, and one model.
`operations.py`, `authz.py`, `projection.py` and the job and result schemas do not differ from `main`.
`POLICY_UNSUPPORTED_ON_ROUTE` is empty, so both new policies run on either route. The warm-start source is found
by the runner (the latest VERIFIED solve in the revision's lineage), and `solve_body` gains no member for it.
The verifier grades every run whatever the policy, so neither policy creates a safety statement that the
descriptions would have to make. The kinetic CSTR consumes no pin, so the six-row target table stays complete.

## Per description

| File | sha256 | Verdict |
|---|---|---|
| cancel_job.md | `e87d799cbe4c32f845772273180fc44d0571fc09a4071a41bd5ef299fab1e557` | approve |
| commit_change.md | `53266974fe402613f3b147da7bc4673c5d57f55d2f3bf9f7c5dc48f5c9b0b384` | **necessary change** (N2) |
| diff_revisions.md | `4a351ae2d7f67e5ff026cc5551109eeb19d7556eedbd2dd50298032858430fea` | approve |
| get_artifact.md | `22cb20636e1f01efa15af3458e83978ad762e5d5279229db8d8723e6e7122883` | approve |
| get_job.md | `349d0218d98e272591986daddfd1a87474d37c6a7d473f355e90ddfbf14a56b7` | approve |
| get_job_result.md | `7eeab9bbee35cd31f55269dd2cd5de2ba4147d531a58ea4b5103e8c903f3520d` | approve |
| get_project.md | `9ac0612f06676a8ebea3ff185df1fb942a3350efb79f63be53c1c05244aec6fb` | approve (optional O3) |
| get_revision.md | `02442571d8c73ce99121f9248e712214fde89cca7d493c88876f6eb018cae932` | approve |
| inspect_structure.md | `4e7c30320406679057dba4933e89a3e77f769538106b396961c1b677c45c9e8d` | approve |
| list_job_events.md | `66b1ec26d3b22a53e17e43732d56496fd3e28db339298b0e3557987ef836c7d3` | approve (optional O1) |
| list_jobs.md | `ffe3183f0de54bcf71b90151d8170915af647182bea734a682719fd8e04a6e03` | approve |
| list_models.md | `941766bdd62094110bf39cacc25c6515efac4041e782f2cae8c5abcacd291db7` | approve |
| list_revisions.md | `12c3e8f9c506c79fb7ef52e23630ac3cea548c04ed5b80b2e5f0a629a5beaec4` | approve |
| preview_change.md | `a90d23555bc367af9f91e62704f7f4bc3e5a41d386f99d36a65a89cb7e70b701` | approve (optional O2) |
| submit_job.md | `61b8509cafb9b4ab101e54622b68b36cf8e938b54df65db105b29b5c36c1771d` | approve (optional O3) |
| validate.md | `302dc544f519046e25efe6d5a5e83840b6017bfbd36d94a3e3e54435eaae7c12` | **necessary change** (N1) |
| wait_job.md | `4a5b99596c771bf6b3254fa9c294e8ad32077de45c3a2e64b93eda0dca37a01c` | approve (optional O4) |

### Safety

No description invites an agent to weaken verification, relax a tolerance, bypass authorization, or read an
unverified result as verified. The texts for `submit_job`, `get_job_result`, `get_artifact`, `wait_job`,
`list_jobs` and `list_job_events` make the correct negative statements: `completed` is not convergence or
verification; `check_tolerances` only tighten, and a tightened run is at best RELAXED (true by
`is_registered`); an archived certificate or `NOT_RUN` is not verification. The bounds stated in the texts match
the code: depth 1–12 (default 4), pages up to 200 (default 50), events up to 500 (default 100), nested arrays
20, 64 KiB, wait default 20 s with a 30 s cap and 100 events, and job ids matching `^job-[0-9]{6,}$`.

### Necessary changes (each one moves the descriptions digest)

**N1. `validate.md`, first paragraph: false since `46dcf74` (U05).** The text offers `"optimization"` and lists
`READY_FOR_OPTIMIZATION`. Today the call is refused `unsupported` before the revision is read, and no status
produces READY_FOR_OPTIMIZATION. The failure is closed and typed, but the paragraph states something that does
not happen. Replace the first paragraph exactly with:

> Validate a stored revision for "task": "simulation" and return its validation report: a status (DRAFT, READY_FOR_SIMULATION or INVALID), the checks with their results, and the structural counts. "task": "optimization" is refused unsupported (task_unsupported(optimization)): this version checks no optimization formulation.

The new file is 1190 characters. Nothing else in the file changes.

**N2. `commit_change.md`: "Every result carries the validation report and a semantic diff." is false.**
`_conflict` and `_rejected` return `validation: null, diff: null` (`local.py:1349–1352, 1380–1388`;
`transaction-result.schema.json`: "`rejected` carries `error`; `conflict` carries `conflict`"). This has been
false since T07, so it is not a T08 regression. Its impact is low: the fields are explicitly null, and the V17
agents handled 6 conflicts and 3 rejections. It is still a false statement of the contract. Replace that one
sentence exactly with:

> A committed result carries the validation report and a semantic diff.

The new file is exactly 1500 characters, which is at G15's cap. Shorter wording does not fit the meaning.

### Optional changes (v0.2; no change before the tag)

- **O1. `list_job_events.md`.** "it is the last sequence returned: pass it as "after_sequence"". `next_cursor`
  is a string, `after_sequence` is an integer, and a cursor passed verbatim is refused with a precise pointer.
  The fix is to add ", as an integer,". The text is not false, and no V17 agent was caught by it.
- **O2. `commit_change.md` / `preview_change.md`.** `"task"` is listed without its values. `"optimization"`
  now raises U05's error (unaudited from `_prepare`, already a build-lane item). Say "simulation" only.
- **O3. `get_project.md` / `submit_job.md`.** Policy ids are offered with no word on what each one changes:
  `T08-warm-v1` warm-starts from the latest VERIFIED solve in the revision's lineage; `T08-ptc-v1` uses the
  experimental PTC core; `"default"` resolves per route. The verdict is the verifier's under any policy, so this
  is a sufficiency gap, not a safety one.
- **O4. `wait_job.md`.** When `"ended"` is true but more than 100 events follow `after_sequence`, the rest are
  read with `list_job_events`. The text implies that `ended` means you have seen everything.

## Rulings (§2)

**1. E7: accept B31's start, under `T06-revision-v2` only.** Ruling 7's "do not substitute another case"
forbids another flowsheet. It does not forbid another registered start of the same revision. `T06-revision-v2`
is the route's registered policy, so the policy condition holds; do not use `T05b-v2`. `_ph_closure` drives the
opening's classification and never enters the residual, so a different trajectory, here `ACTIVE_SET_CYCLING`
against `CONVERGED`, is a legitimate outcome and not a change of physics. The test must:

- run patched and unpatched from the same start, built by `test_b31i`'s own helper (imported, not copied), and
  assert that the two start vectors are bit-equal;
- in the patched run, assert at least one `_ph_closure` call and that both `fallback(U-PHF, tp)` and
  `fallback(U-PHF2, tp)` are recorded;
- assert that the patched outcome is in `SolveOutcome` and that no exception is raised;
- assert that the patched run issues no VERIFIED certificate;
- assert that the unpatched run is `CONVERGED` and records neither of those fallbacks, which makes the patch
  the cause;
- assert that the plan's `model_version` and `constants_sha256` are equal across the two runs, and also equal
  to the patched failure bundle's, if one exists. The root-fingerprint clause is vacuous here, because the
  patched run does not converge.

Cite the test in E7 as `identity_compared`. E7's user-facing text must not imply that the fallback preserves
convergence. **E7's evidence is not `null`.**

**2. Ruling 8's exemption: confirmed.** `auto` resolves on `incapable`, which is computed over the loop's
`node` (`execution.py:736–741`). A model with no outlet port of any kind has no outgoing edge, so it is in no
cycle. The equality assertion `exempt == {"syn001.product_sink"}` keeps the exemption closed: a new model
without an outlet reopens it.

**3. S6: the union of both proposals.** Apply the fail-closed rule:

- to every `kind=` argument in modules under `orchestrator/`, `numerics/` and `verify/`;
- to every `.record(kind=…)` call and every `_initializer_event` third argument in every module.

`SolveTrace.record` is the only entry point for events. Under the second clause, a flagged call outside the
three directories is therefore a producer by construction, not a false positive. The directory clause also
catches forwarding helpers with other names. Add two mutation cases: a local `kind` passed to a helper in an
`orchestrator` module, and `trace.record(kind=k)` in an `application` module. The build lane measured zero
false positives for the directory rule, and a grep shows no `.record(` caller outside `numerics/` and
`orchestrator/`, so the union should also be zero. Confirm that by running it.

## V17

The carry question is open regardless of the descriptions. U05 changed the behaviour of an existing MCP tool
path. That is outside F5, which Frank answered as "content only; no schema, description or tool change". N1
only makes the text match that behaviour. N2 rides on the same digest movement at the cost of one more
file's human re-review. Every changed hash voids Frank's 2026-09-29 human review of that file.

Evidence for Frank's decision: neither V17 campaign issued `task: "optimization"`, or mentioned optimization at
all. Both changes remove false statements about paths that no campaign agent used. **My recommendation (needs
a decision, Frank's): carry V17 with the change recorded, and run no new campaign.**

## Not examined

- The bodies of artifacts behind `get_artifact` beyond `solution-state.json`'s shape.
- The cancel grace mechanics, the replay semantics of a `rejected` idempotent commit, and diff_revisions'
  "descriptive members" list, all of which I took from T07's design and Frank's human review.
- Whether `test_b31i`'s start goes through the full revision solve rather than a region-level entry. Ruling 1
  assumes the full solve; if it does not, Ruling 7's stop condition stands and E7 is `null`.
- The S6 union, which I have not run.

## Addendum, 2026-10-01: Ruling 1 (E7) after its stop condition was hit

**Facts** (build lane `c8d4a0e`; the CH-UP-DP start from `test_b31i`'s `CASES`, bit-equal across builds;
`T06-revision-v2`; `_ph_closure` patched to return `None`):

- **Region entry** (`solve_from_v2` → `solve_region`):
  - patched: `ACTIVE_SET_CYCLING`, with `fallback(U-PHF, tp)` and `fallback(U-PHF2, tp)` recorded;
  - unpatched: `CONVERGED`, with `fallback(U-PHF2, tp)` recorded.
- **Full revision solve** (`execute_plan(user_start=…)`):
  - patched: `CONVERGED` and `VERIFIED`, both fallbacks recorded;
  - unpatched: `CONVERGED` and `VERIFIED`, with `fallback(U-PHF2, tp)` only.

**Two of Ruling 1's assertions rested on false premises. Both are withdrawn.**

- *"The unpatched run records neither fallback."* The leaving-`ZERO_FLOW` producer also writes the
  `U-PHF2` label, so that label cannot tell the two branches apart. Only `U-PHF` discriminates.
- *"The patched run issues no VERIFIED certificate."* This assumed the patched run would not converge.
  When the solve does converge, VERIFIED is the correct verdict.

**Ruling: accept the build lane's proposal, amended.** Use the full revision solve. E7's evidence is
kind (ii) `verified_certificate` (Ruling 6), not `identity_compared`, and it is not `null`. The test asserts:

1. Both runs start from the same state, built from `test_b31i`'s `CASES` (imported, not copied), and the two
   start vectors are bit-equal. Both runs use `T06-revision-v2`.
2. Patched run, firing:
   - at least one `_ph_closure` call on `U-PHF` whose feed is not all zero;
   - `fallback(U-PHF, tp)` is recorded.

   The patch wrapper records each call's unit and whether its feed is zero. This shows that the injected
   `None` is the no-answer branch, not a `ZERO_FLOW` split.
3. Unpatched run: `fallback(U-PHF, tp)` is absent. `U-PHF2` is asserted on in neither run.
4. Patched run, verdict: no exception, outcome `CONVERGED`, verdict `VERIFIED` by
   `verify_revision`/`verify_bound`. The certificate's `model_version`, `constants_sha256` and revision equal
   the bound declaration's.

**E7's note** must not claim that the fallback preserves convergence. It cites the region-entry
`ACTIVE_SET_CYCLING` as the observed counter-case, which is reachable only through the library.
