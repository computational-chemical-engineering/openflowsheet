# T03 review — the phase-attempt contract, checkpoint compatibility and root provenance, against `docs/derivations/T03-phase-controller-spec.md` and ADR 0005

**Reviewer:** design lane, `reviewer` (Claude Opus 5.5), 2026-09-24. Plan §1.3: the design lane
reviews every build-lane package that touches residuals, derivatives, phase logic, scaling,
certificates or replay identity; this one touches phase logic, certificates and replay identity.
**Brief:** `docs/briefs/T03-implementation-review.md`.
**Reviewed at:** `wp/T03` = `731f350`; commit range `c799ad9..731f350`. Run here: the full test
suite, **1579 passed** (43 s); the three T03 test files, 38 passed; `t03_reference.py --check`,
**107 checks passed**, committed YAML SHA-256 `7ac2449d…fcd` equal to the specification's header;
`k04_reference.py --emit` byte-identical to the committed `benchmarks/k04/reference_values.yaml`.
The evidence manifest was not available at review time (MANIFEST_PENDING).
**Environment:** x86-64 Linux 6.12.86, the repository's `.venv`. No CI artefact was examined.
**Measured:** every finding marked *measured* comes from a probe run against `731f350` in this
session; each probe is described where it is used (P1–P13) so it can be re-run from the tests'
own helpers. Nothing is marked measured that was only read.
**Amendments made in this commit:** T03 specification §4.3, §4.10, §8.1–§8.3, §9, §10; ADR 0005
D7–D8 (Proposed); register R-029. Each is marked in place with the finding that caused it.

---

## 1. Verdict

**The contract is implemented as specified, and the registered trajectories are the twin's.**
One decision function (`phase_contract.decide`) and one wall observer serve both controllers; the
precedence table, the §4.5 selection, the gate order (budget → cycling → opening checks) and the
message grammar exist once. The screen reads a trial and never alters it (A04 bit-identity holds on
every call), goes through the closure check's own callable at `admissibility_epsilon`, and asks the
kernel exactly on the flagged trials: the screen's provider calls on PHS-01/02/03 are **28, 26, 14
= 15 + 13, 14 + 12, 8 + 6** (P9), the specification's screened/flagged counts. Disappearance is by
`BOUND_BLOCKED` on a watched variable and a landing no longer closes an attempt. PHS-01…05 match
the 40-digit twin trial by trial; A21's closure moved to the block with its numbers intact. The
phase *numerics* of this package are sound; by reading, each of the three rules is pinned by an
asserted trial verdict or closing iteration in the trajectory tests (the brief measured the
adjacency ablation; I did not re-run the ablations).

**It is not done.** Three things are wrong where the tests do not look:

1. **The root fingerprint describes the path, not the root.** `branch_found` is the tear
   signature on the tear path (the flash alone) and every lifted split on the EO path, so SYN-001's
   nominal root — reached by K03's tear and by T02 A21's region, **4.4e-16 apart in scaled
   coordinates over all 47 columns, same problem identity** — compares **`DISTINCT`** (M1). That is
   a false multiplicity claim from the one comparison D11's evidence rests on. The specification's
   wording allowed it; it is amended here.
2. **The no-guess refusal (§9) holds only if the caller remembers it.** Without the opt-in
   `missing_guesses` argument, `execute_plan` runs `SYN-001-A02-360-no-guess` from a 350 K start
   the binding invented and reports **`CONVERGED`**, with `initializer_source = user_guess`; and
   the same `role: free` without a value on the flash temperature crashes the binding with
   `ValueError` (M2). This is T02 N9's silent path, closed by convention.
3. **A03 is false on OFF-B, a case it names.** The tear Jacobian's reconstruction traverses the
   flowsheet under the *base* context, shared by every attempt: **148 of 504** provider calls of
   OFF-B's attempt 0 and **200 of 421** of attempt 1 (P5). The A03 test runs only the lifted cases,
   and its pinned-zero check reads values the region writes after the solve (M3).

The should-fix items are all on paths no registered case reaches: a budget refusal inside the
screen escapes the attempt loop and the result forgets the attempts (S1, measured); provenance on
the executor's region paths names `user_guess` where there was none and does not follow a merge
(S2, measured for the first); `same_root` trusts its inputs (S3, measured); a float in R0 strings
(S4, latent); and two of the six precedence rows plus both retained T02 conversions have no test
at all after A30/A31 were superseded (S5, measured over the whole suite).

The eight decisions of brief §3 are accepted, one with a spec amendment and two with hardening
notes (§5). The three questions of brief §5 are ruled in §5.

**Not examined:** `t03_reference.py` beyond `--check`; the registry prose and the four new case
YAMLs beyond the no-guess entry; schema JSON layout beyond the new fields; fixture regeneration;
the CI pair's artefacts (A23's cross-platform claim is therefore unreviewed here — only
`t03_identity.py`'s content was read); the manifest script (A26); the Anderson core; K05's replay
refusal of a pre-T03 policy document (ADR 0005 C2 — no test found, not probed).

---

## 2. Must-fix findings

### M1 — `branch_found` is path-dependent: one root reached by the tear and the EO path compares `DISTINCT`

**Where.** `src/process_runtime/orchestrator/tear.py:671-677` (the tear fingerprint:
`branch_found=result.signatures[-1]`, the flash only), `src/process_runtime/orchestrator/attempts.py:356-361`
(`branch_found=opening`), against `src/process_runtime/orchestrator/region.py:708-716` (every
active lifted split, from the state). `roots.py:68` then returns `DISTINCT` on any list difference.

**Measured (P1).** SYN-001 nominal, `tests/test_t02_region.py`'s `case("SYN-001-nominal")`,
solved by `solve_tear(item.flowsheet)` and by `solve(item, initializer(item))`:

```
policy, model_version, constants_sha256, variable_ids_sha256:  equal
branch_found  tear = [['U-FLASH','TWO_PHASE']]
              eo   = [['U-HEAT','LIQUID'], ['U-FLASH','TWO_PHASE']]
scaled ∞-distance over 47 columns (Scaling.from_spec):  4.44e-16
same_root(tear, eo) = DISTINCT
with branch_found = _branch_found over syn001_lifted_splits on each full state:  both
    [['U-HEAT','LIQUID'], ['U-FLASH','TWO_PHASE']]  →  SAME
```

**Why.** §8.2 said "per phase-selecting unit", and §4.1 defines that set per path. On the tear
path the signature deliberately omits the heater (K03's measured crawl, `attempts.py` module note)
— right for what an attempt *freezes*, wrong for where a root *is*. The certificate already records
the heater's split from the state (`verify/certificate.py:_phase_branch`), so the fingerprint and
the certificate that carries it disagree about the same object.

**Correction.** §8.2 is amended in this commit: `branch_found` is `_branch_found` of every unit
with a lifted split in the declaration, read from the full state, on every path (the tear path's
reconstructed state has the S3 and flash splits). Move `_branch_found` out of `region.py` into
`roots.py` (or `phase_contract.py`) and call it from `tear.py:671` with `final_state` and the
declaration's splits; `attempts.py:356`'s provisional fingerprint then needs no `branch_found` of
its own (the tear always overrides it; for the bare controller keep the signature — it has no
declaration). Do **not** add the heater to the tear signature. Re-registration: OFF-B's
fingerprint in `tests/test_t03_roots.py:183` and in `scripts/t03_identity.py`'s document becomes
`[[U-HEAT, LIQUID], [U-FLASH, TWO_PHASE]]`.

**Test that catches it.** P1 as a test: `same_root` of the tear and EO results of SYN-001 nominal
is `SAME`, with both fingerprints' `branch_found` equal.

### M2 — The §9 no-guess refusal is opt-in, and the binding fabricates the guess it refuses

**Where.** `src/process_runtime/application/binding.py:334` (`assembly = … _declared_default(column)`)
and `:649-656` (a one-entry SYN-001 table, `ValueError` for anything else);
`src/process_runtime/orchestrator/executor.py:150` (`missing_guesses: Sequence[str] = ()`) and `:249`.

**Measured.** (P10) `SYN-001-A02-360-no-guess` bound (`binding.missing_guesses == ('S3.T',)`) and
run through `tests/test_t02_executor.py:run_flowsheet` *without* passing `missing_guesses`:
**`CONVERGED`, `S3.T = 359.99999946 K`**, pre-solve opened normally — from the flowsheet's
`HEATER_TEMPERATURE = 350.0`, which the binding baked into `binding.flowsheet`; the region's
provenance item 0 says `initializer_source = user_guess` (S2). (P4) `SYN-001-A02-360.yaml` with
`SPEC-flash-T` made `role: free`: with its value, `bind_revision_or_reason` returns a `Binding`;
with the value replaced by `bounds`, it raises **`ValueError: no declared default for the freed
coordinate 'S4.T'`** — an untyped exception from a function whose contract is to return a reason.

**Why it is must-fix.** §9 exists to close exactly this ("silence reads as success", T02 N9, "T03
owns it"). Today it is closed only for callers that forward a side-channel list with a permissive
default, and only for `S3.T`. The registered test (A24) passes because its helper forwards the
list. The value the binding invents is not inert: it is a legitimate-looking start.

**Correction.** Carry the missing guesses in the plan: `specification_regions`/`build_execution_plan`
record them on the region step (the plan is built from the binding's `freed`, so the fact is
available there), and `_run_step` refuses from `step.region` alone; drop the `execute_plan`
keyword. In the binding, do not take the value from a table: either use the flowsheet class's own
constructor default for the coordinate (introspected, so every freeable coordinate works) with the
missing guess recorded, or — better — return an `Unbound`/typed reason for any coordinate the
flowsheet cannot be assembled without; never `ValueError`. §9 is amended in this commit to say the
refusal holds by construction.

**Tests that catch it.** (a) P10 as a test: the no-guess revision through `execute_plan` with no
extra argument ends `INITIALIZATION_FAILED` naming `S3.T`. (b) P4 as a test: `role: free`
without a value on `SPEC-flash-T` returns a `Binding` whose `missing_guesses == ('S4.T',)` (or a
typed `Unbound`) and never raises.

### M3 — A03 is false on OFF-B: the tear Jacobian traverses under the shared base context; the test omits the case

**Where.** `src/process_runtime/orchestrator/tear.py:304-310`: `jacobian(t, context)` calls
`self.reconstruct(...)`, which traverses `self.flowsheet` and re-splits S3 with
`self.flowsheet.context` (`:222`, `:242`) — the base objects, not the attempt's
`flowsheet_context`. The residual path (`:283`) does use the attempt's flowsheet.
`tests/test_t03_contract.py:207-240` parametrizes A03 over the five lifted cases only; A03 names
"OFF-B, A21, PHS-01…05, PHS-SYN-1/2".

**Measured (P5).** OFF-B through `solve_tear`, every `ExactPropertyCache.flash/evaluate_phase` call
tagged with the attempt open at the time and the calling frame:

```
attempt 0: own context 356   base flowsheet context 148  (130 evaluate_phase + 18 flash, all inside jacobian)
attempt 1: own context 221   base flowsheet context 200  (182 + 18, all inside jacobian)
```

(A further 85 calls come after `solve_closed`, in the post-solve reconstruction, outside any
attempt; 274 precede the first `attempt_opened`.)

**Why it is must-fix.** Numerically inert — the contexts are field-equal — but A03 is an acceptance
assertion, and a manifest that reports it `pass` from a test that leaves out the one case where it
fails is a narrowed denominator (`CLAUDE.md`, scientific conduct). The fix is three lines. The test
also has a hole of its own: `test_t03_contract.py:234-236` checks `attempt.end_state[name] == +0.0`
for pinned variables, but `region.py:800-801` *writes* `+0.0` into the end state after the solve,
so the check reads back what the code wrote and would pass if the evaluator had seen `1e-3`.

**Correction.** `Syn001TearProblem.jacobian` (and `check_inner_consistency`'s reconstruction) takes
the attempt's flowsheet, as `residual` does: `as_newton_problem(attempt)` passes
`replace(self.flowsheet, context=attempt.flowsheet_context)` to both. Add OFF-B to A03's test with a
provider spy (P5's shape) asserting every provider and compiled call between an attempt's
`attempt_opened` and its `attempt_closed` carries one of that attempt's two context objects. Replace
the pinned-zero check with one on the vectors the compiled residual actually received (wrap
`compiled.residual` and read the pinned positions of its input), including the sign bit.

**Test that catches it.** The OFF-B spy above: zero base-context calls inside an attempt.

---

## 3. Should-fix

### S1 — A refusal inside the screen escapes the attempt loop; the result then forgets the attempts

`region.py:553-583` calls the provider directly — `_admissible` → `verify.checks.k_values`
(`region.py:251`), and `provider.flash` (`:569`) — outside the compiled residual, which is where a
budget refusal is turned into an `error` evaluation. A `BudgetExhaustedError` raised there leaves
`solve_newton` and `solve_region`, and `executor.py:509-510` builds
`RegionResult(outcome="BUDGET_EXHAUSTED", state=dict(start), attempts=())`.

*Measured (P3b):* PHS-01 through the plan executor with `max_property_calls` swept over 157–346:
where the refused call is the compiled residual's, the region result keeps its attempts,
provenance and checkpoint; where it is the screen's (caps 189, 190, 199, 200, 209, 210, … 346),
it carries **0 attempts, 0 provenance items, no checkpoint and `S3.T = 350.0`** — at cap 346 after
the region had accepted `351.232 K` (the trace shows it). §4.8 requires the last accepted iterate
and the `partial` checkpoint; §8.1 requires provenance on every result. The same shape one call
earlier: `k_values` raises `VerifierError` on a non-`ok` status, which `solve_region` does not
catch (by reading; unreachable with SYN-001's provider because the residual has already evaluated
K at the same `(T, P)`).

*Correction:* the screen converts both exactly as the compiled residual does — catch
`BudgetExhaustedError` and `VerifierError` in `screen` and return `Evaluation(status="error", …)`
(→ `EVALUATION_ERROR` → `decide` → `closed`, the executor then reporting `BUDGET_EXHAUSTED` from the
meter) or `invalid_trial_state` for a provider refusal. §4.3 is amended accordingly. The tear path
has the same pre-existing gap one level up (`tear.py:619-649` returns `attempts=0`, `x = start`, no
provenance); fold it in if cheap, otherwise hand it to K05's replay work explicitly.
*Test:* P3b's cap 346 → `BUDGET_EXHAUSTED` with `len(branch_provenance) == 1`, a `partial`
checkpoint and `state["S3.T"] == 351.232445119600…`.

### S2 — `branch_provenance` item 0 on the executor's region paths

`solve_region(initializer_source="user_guess")` (`region.py:598`) is never overridden:
`executor.py:499` does not pass it. *Measured (P7):* the nominal flowsheet under `recycle.method =
eo` (T02 A21 through the plan) records item 0 `initializer_source = user_guess`; there is no user
guess — the start is the reconstruction of `SYN-001-tear-init-v2` (`executor.py:449`). By reading:
the executor's merge edge (`executor.py:354`, `_converge` → `_region`) records the region as a fresh
`attempt 0`, `opening_source = initializer`, instead of continuing the loop's list with
`merge_best_iterate` as `merge.converge_with_merge` does (§8.1: "a merge's region attempts follow the
loop's") — T02 S2's two merge implementations, and T03's provenance landed in one; and a
`_KernelRefusedError` (`region.py:620-626`) returns a result with no provenance. §8.1 is amended to
say what `initializer_source` must be. *Correction:* `_region` takes the source (`user_guess` for a
specification region, the plan's registered initializer id for a promoted loop, `None` plus an
`attempt` offset and `merge_best_iterate` for a merge), and the merge edge's provenance is built by
one function both callers use. *Test:* P7 as a test (`initializer_source == "SYN-001-tear-init-v2"`
for nominal `eo`); a forced flowsheet merge (a constructed stalling `RecyclePolicy`, or a stub
recycle result through `_converge`) whose `branch_provenance` is `[anderson/initializer,
newton/merge_best_iterate]`.

### S3 — `same_root` trusts its caller

`roots.py:51-74`: the maximum runs over `scales`' keys with `default=0.0`, and neither state is tied
to its fingerprint. *Measured (P8)*, REC-05 MR-A and MR-B: registered scales → `DISTINCT`; **empty
scales → `SAME`**; MR-A's fingerprint paired with MR-B's state → **`SAME`** (the state's hash is not
MR-A's `full_state_sha256`). The digest the fingerprint carries "to identify the state compared" is
never compared. *Correction* (§8.3 amended): take the variable ids; refuse (typed error, not a
verdict) unless each state's ADR 0008 D2 hash over the ids equals its `full_state_sha256`, the ids'
hash equals `variable_ids_sha256`, and every id has a positive scale; take the maximum over the ids.
*Test:* P8's two bad calls raise; the registered A19/A20 comparisons are unchanged.

### S4 — A measured float inside R0 strings (latent)

`region.py:463` writes `inadmissible(S3, all_liquid, {value!r})`; `phase_contract.py:231, 234`
write `{value!r}`/`{bound!r}` into `checkpoint_incompatible(...)`. These strings are
`attempt_opened.message`, `solve_closed.message` and `branch_provenance.cause` — R0, compared byte
for byte by A23 and by K05 replay. `Σ x K` at a solved state can differ in its last bits across the
CI pair, which would be a false structural `MISMATCH`. No registered case produces either message
today (S5), which is why A23 is green. *Correction* (§4.10 and ADR 0005 D8 amended): R0 forms
`inadmissible(<stream>, <branch>)` and `checkpoint_incompatible(<check>, <variable or field>)`; the
number goes on `RegionAttempt` and the failure bundle's observations. Update
`test_t03_contract.py`'s `GRAMMAR` and A16's `startswith` checks with it. *Test:* the regex rejects
any digit-bearing float in a cause; a constructed §4.7(a) conversion (S5) produces the value-free
cause and records the value on `RegionAttempt`.

### S5 — Two precedence rows and both retained T02 conversions have no test

*Measured (P11):* `phase_contract._proposal` and `_LiftedOps.converged` spied over the **entire
suite (1579 passed)**. Closures reached: lifted `CONVERGED` → admissible (65), `BOUND_BLOCKED` →
`phase_disappeared` (23), `PHASE_UPDATE_REQUIRED` → patience (29), `LINE_SEARCH_FAILED` → stall
(7), `LINEAR_SOLVE_FAILED` → none (1); tear patience (33), stall (3), `LINE_SEARCH_FAILED` → none
(1), `BUDGET_EXHAUSTED` → none (4). **Never reached:** §4.7(a)'s `inadmissible` restart, §4.7(b)'s
`kernel_disagrees` restart, row 5 at all (lifted `STAGNATION`, wall-free `LINE_SEARCH_FAILED`,
unwatched `BOUND_BLOCKED`, `BUDGET_EXHAUSTED(newton_iterations)`), and the brief's own question
(rows 3–5). T02 A30/A31 were their only tests and are superseded. Under T03 both conversions can
fire only from an attempt's unscreened opening or from a `TWO_PHASE` unit, so they are rarer — and
untested code in the one function both paths share. *Correction:* a table test of `decide` with a
stub `PathOps` and constructed `NewtonResult`s, one row per line of §4.8 including the gate's three
refusals (P13 is its shape; it ran here and returned what §4.8 says), plus one physical case per
conversion where one can be built (a `TWO_PHASE` region attempt stagnating where the kernel reports
a single phase). Two smaller gaps in the same family: A16's "every registered opening passes all
six checks" spies only the lifted cases (OFF-B's opening is not included), and A15's
`pattern == jacobian_pattern(structure_entries, rows, free)` recomputes the recorded value with the
function that produced it (the registered 42 × 42 / 38 × 38 shapes and the stored-entries-in-pattern
check are the independent parts, and they hold).

---

## 4. Notes (no change required, or a wording amendment made here)

- **N1 — Opening checks on internal restarts are tautological, by design.** On both paths
  `OpeningState`'s `model_version`/`constants_sha256`/`step_index`/`scale_segment` come from the same
  source as the `OpeningRequirement`'s (`attempts.py` `_TearOps.opening_check`, `region.py:521-540`),
  and the tear `active_set` check compares the candidate's signature with itself. §5.1 says as much
  ("cheap invariants"); A16's refusals are constructed by monkeypatching `check_opening`, which tests
  the function and the refusal plumbing, not a path. When the first external source arrives (a warm
  start), the state must carry the identity of the evaluation that produced it — not the
  requirement's.
- **N2 — Decision 1's mechanism is sound but narrow in how it observes reads.** `graph/trace.py`
  `_ReadTokens` records `__getitem__` only; a builder that read a parameter with `.get(name, default)`
  or by iteration would see it dropped *silently* and use its default. No builder does today
  (grep over `models/`), and blocks cannot read parameters (`ProblemSpec.validate` feeds them
  variables only). Harden by overriding `get`, `__contains__`, `__iter__`, `keys`, `items`, `values`
  to record (or raise). Measured (P2): the drop removes exactly `U-HEAT.T_spec` from the four A02-360
  revisions, whose identities are now equal; nominal SYN-001 has no orphans. Consequence to record:
  after the drop the freed coordinate's guess is in no R0 plan or problem field — only in the opening
  digests — so K05 tells PHS-01 from A02-355 by a digest; the plan's region step should record its
  guesses (M2's change is the natural place).
- **N3 — The screen's refusal mapping (brief §4, second item) is right in effect.** A non-`error`
  flash status becomes `invalid_trial_state` and `error` becomes `EVALUATION_ERROR`, as K03 §5.5
  requires; the status is in the message. Pass the provider's own status through as the evaluation's
  (the `Evaluation` vocabulary has `out_of_domain`, `not_converged`, `unsupported`) rather than
  translating it, and name the unit as well as the stream (§5.5: "the unit id, the status and the
  message").
- **N4 — `_LiftedOps.at_candidate` (decision 7) is right by construction** — `opened` equals the
  screened `full(candidate.x)` bit for bit (non-free coordinates are untouched between the attempt's
  `base` and its end state; pinned ones are `+0.0` in both), and the kernel is deterministic. Make the
  construction checked, not assumed: if the kernel's regime differs from `candidate.signature`, raise
  a defect, because the cause string (`_changes(frozen, candidate.signature)`) and the new signature
  would otherwise disagree silently.
- **N5 — Dead or loose surface.** `decide(attempts_run=)` has no caller; `WallObserver.should_close`
  ignores its `iteration`; `Conversion.opening: Any` is an ndarray on one path and a `(state,
  regimes)` pair on the other; `region.py:653`'s `hasattr(compiled, "structural_pattern")` turns a
  compiled problem without the method into a silent `jacobian_pattern = null`, which D5 allows only
  for an attempt with no compiled problem — make it a protocol member or refuse.
- **N6 — Stale module notes that contradict the contract.** `region.py:12-16` ("A phase leaves when
  its lifted total reaches its bound … No trial is ever rejected for the kernel's opinion of it") and
  `attempts.py:24-27` ("The restart point is the phase-rejected trial with the largest α") describe
  the rules T03 reversed; R-028's watch list names exactly the regression a reader of those lines
  would make.
- **N7 — Performance.** Nothing matters at 42 × 42. The screen adds per trial of a single-phase unit
  one uncached K-value call and, when flagged, one flash (P9: 28/26/14 calls on PHS-01/02/03 — ≈ 8 %
  of the ~335 provider calls PHS-01's region step makes in P3's plan run; 0 on two-phase attempts). `check_opening`'s bounds loop tests
  `name in requirement.free` on a tuple (`phase_contract.py:233`, O(n²) per restart) and
  `_LiftedOps.opening_check` rebuilds `set(pinned)` per element (`region.py:525`); use sets before a
  plant-size region arrives.
- **N8 — `opened_from` after an attempt that accepted nothing** is the most recent earlier
  checkpoint (K03 §12.5 writes none for such an attempt); §4.10 now says so. Harmless.
- **N9 — The manufactured merge path records no `attempt_opened`** (P12: MR-C's trace has none), so
  §8.1's "`opening_state_sha256` equals that attempt's `attempt_opened.state_sha256`" cannot be
  checked there; the region path satisfies it (A17). The schema's `opening_state_sha256` pattern
  admits `""` while A17 requires non-empty — tighten when the merge path records its openings.
- **N10 — A `-0.0` from a provider** on a single-phase kernel result's empty side would make the
  lifted `active_set` check refuse (§5.1 wants the sign bit clear) although the attempt loop then
  writes `+0.0` anyway; SYN-001's provider returns literal `+0.0` (by reading). Correct as specified;
  noted for T05's providers.
- **N11 — The K04 specification header's reference SHA is stale** (`79f263c8…`; the file was
  `0abedaf4…` before T03 and is `2a1b5ecb…` now, re-emitted byte-identically here). Pre-existing;
  T03's `delta_scaled_inf` edit moved it again. Whoever next touches K04's header should pin it.

---

## 5. Rulings

### Brief §5

- **Q1 — `decision` of a gate-refused restart: `restart`.** The item records what the attempt's
  closure proposed; the gate's refusal is the solve's, carried by its outcome and its terminal
  message, and the last item of a refused solve is identifiable as the last item. It is also what
  `benchmarks/t03/reference_values.yaml` registers for PHS-05. §8.1 amended to say so (register
  R-029).
- **Q2 — Dropping orphaned parameters from the declaration's identity: sound.** `constants_sha256`
  identifies the function; a parameter no remaining row reads is not part of it, and an initial
  guess is not a constant of the problem — without the drop, A02-360 from 358 K and from 350 K were
  two problems, which is false. The change to every A02 revision's `constants_sha256` is the
  correction of an identity that was wrong, not a regression. Accepted with N2's hardening and N2's
  note that the guess must then be recorded in the plan.
- **Q3 — §14 Q2–Q5 defaults: confirmed.** Q2 (no far-restart refusal): no threshold separates
  A21's `1e-5` from PHS-05's `0.43` with an argument, and nothing measured here changes that. Q3
  (`phase-controller case` outside the denominator): the right reading of the registry's own
  classes — the physics is T02's registered sweep — but it is the registry's vocabulary and so
  Frank's to overrule (§6). Q4 (`δ_root = 1e-4`): confirmed; its margins (≥ 50× every registered
  error bound, 1/9 629 of REC-05's separation) are what the comparison needs, and what it lacked was
  M1's and S3's input discipline, not a different δ. Q5 (`alpha` on `attempt_opened`): confirmed;
  the halving index is on the certificate's provenance (R0), and `alpha` agrees with it (A17 holds).

### Brief §3 decisions

1. Orphaned parameters — accepted (Q2, N2).
2. No-guess revision carries `bounds` — accepted for the revision; the *mechanism* is M2.
3. `restart` for a gate-refused restart — accepted (Q1).
4. `delta_scaled_inf` as an ADR 0007 D1 exact field — accepted; it is a registered constant, not a
   measurement. §10's "no float is added" is amended to "no *measured* float".
5. The cycling `solve_closed` message under §4.10's grammar — accepted; §10 amended to list the K03
   test it re-registers.
6. The region records no `solve_closed` — accepted; *measured (P6)* that the plan executor's
   `solve_closed` carries the region's message for PHS-05 (`active_set_cycling(U-HEAT:TWO_PHASE,
   U-FLASH:TWO_PHASE; phase_wall(stall, U-HEAT:LIQUID->TWO_PHASE))`). §4.10 amended to say where it
   lives for a bare region solve.
7. `at_candidate` takes the kernel's regimes — accepted, with N4's check.
8. `jacobian_pattern` shape and the tear path's inner block — accepted; it is §5.2's text.

### Brief §4 ("least sure")

- **Rows 3–5 for `BOUND_BLOCKED` with no watched blocker and a wall in the window.** The
  implementation follows §4.8 exactly: row 3 declines, row 4 does not apply (`BOUND_BLOCKED` is not
  one of K03 §9.3's three stall outcomes, which §4.3 reproduces verbatim), row 5 asks the kernel at
  the end state, and — the end state being an admissible screened iterate — the kernel agrees and
  the failure stands. *Measured (P13, stub `PathOps`, wall at iteration 3, closure at 4):*
  `BOUND_BLOCKED` → terminal `BOUND_BLOCKED` via `['blocked', 'kernel_disagrees']`;
  `LINE_SEARCH_FAILED` and `STAGNATION` → restart via `at_candidate`. Upheld: a block on a non-phase
  variable says Newton wants some other flow negative, a different pathology from a phase wall, and
  restarting in a new phase set on it would be a guess. No test pins it (S5).
- **The screen's kernel-refusal mapping** — right in effect (N3).
- **Counters through `PropertyMeter`, not "the exact property cache"** — right; the region path has
  no cache and the meter is what makes the calls count against `max_property_calls` (P3 shows them
  refused at the cap). §4.3 amended. The one gap is S1.

---

## 6. FOR FRANK

Nothing here needs a decision of Frank's to proceed. Two things he may want to know:

- **Registry class `phase-controller case` (spec Q3).** Applied as the specification's default and
  confirmed here as consistent with the registry's existing classes; it is registry vocabulary, so
  it is his to overrule. Reversible by a registry edit.
- **The fingerprint amendment (M1, R-029) changes a registered R0 value**: OFF-B's
  `root_fingerprint.branch_found` gains the heater. It is a correction of a false `DISTINCT`, made
  under ADR 0005 while it is still Proposed, so no accepted decision is reversed.

---

## 7. What the fixes must not do, and what T04 inherits

- **M1 must not add the heater to the tear signature.** The signature is what an attempt freezes
  and K03 measured the crawl that freezing the heater causes; only the fingerprint reads the state.
- **M3's fix must stay numerically inert.** The contexts are field-equal; OFF-B's trajectory, its
  restart point and every K03 count must be bit-identical before and after (compare the trace's R0
  projection).
- **S4 changes R0 strings** that no registered case emits today; A23's document must be unchanged
  by it (assert that).
- **T04 inherits** PHS-05 (and the 377 K guess), unchanged by this review; the budget-refusal shape
  of S1 on the tear path if it is not folded in here; and S5's lesson — a conversion kept "from T02"
  needs its own test the day its only registered case is re-registered.

---

## 8. Ruling after the review: A21 and the stateless certificate (manifest finding, 2026-09-24)

**Finding.** `verify()` (`src/process_runtime/verify/certificate.py:309-340`, the `final_state is
None` branch) returns a certificate with `regularity: null` — e.g. for OFF-B under
`max_attempts = 1`, `ATTEMPTS_EXHAUSTED` — which `schemas/solution-certificate.schema.json` rejects
(`regularity` is a bare `$ref` to `regularity-evidence`, whose required fields need a state). Same
code and schema on `main` (K04).

**Ruling: (c) — no schema change; that certificate must not exist.** K04 §3 already decides it: "A
non-`CONVERGED` solve receives no certificate and a `FailureBundle`" (and K04 A20: "no certificate
object exists anywhere in the result"); T03 A12 and A16 say "no certificate" for the phase-controller
failures. The defect is that `verify()` certifies a non-converged result at all, not that the schema
cannot hold the result. Correction (build lane, in T03 — one guard): `verify()` refuses a result
whose outcome is not `CONVERGED` with a typed error (`VerifierError`), issuing no certificate; the
caller's route for a failed solve is the failure bundle. §8.1's provenance on a failed solve lives
on the solve result (`SolveResult.branch_provenance`), which already carries it — do **not** attach
it to a certificate that should not be issued, and the failure-bundle schema gains nothing.

**A21.** "Every certificate validates" ranges over certificates issued; after the guard, the
stateless certificate is never issued and A21 is judged on the converged solves' certificates (the
spec's A21 row carries this clarification). This is not a narrowed denominator: the case moves from
"an invalid certificate" to "no certificate", which is what K04 and T03 both require, and A21's
probe must assert exactly that (`verify()` on OFF-B with `max_attempts = 1` raises; the result's
`branch_provenance` has one item, `restart` refused by the budget). Until the guard lands, A21 is
`fail`.

**Handed to K04, not ruled here.** The remaining stateless path — a `CONVERGED` result without
`x_final` (K04 §3's second paragraph, A01) — still yields a schema-invalid certificate: K04's
specification mandates a certificate its schema cannot hold. It is unreachable on every registered
path since K04 A01 made every `CONVERGED` result carry `x_final`, and it is not a phase-attempt
question, so it does not go into ADR 0005. A K04 follow-up decides between refusing that input too
and a nullable `regularity` tied to `target_state_sha256 == ""` (a schema change, own ADR). T03's
manifest lists it under `limitations` as a handed-on K04 defect.

