# X07a ruling: replay platforms (Q-2) and floating-point differences on the new legs (Q-3)

**Status:** design-lane ruling (`specifier`), 2026-11-20, on `docs/briefs/X07a-R-platforms.md` at `bd7548e4`
(branch `wp/X07a`). Sections 4 and 6 bind X07a-WO3. The two texts drafted in section 5 are **proposed**: Frank accepts
ADRs, and `wp/X07a` does not merge to `main` before ADR 0007 Amendment 3 is Accepted (R3).
**Not ruled:** Q-1 (pywin32 licence: rights, Frank).

## 1. Authority and scope

Read for this ruling, narrowly: ADR 0007 D1, D3, D4, Amendments 1 and 2, "Changing this ADR"; ADR 0025 header, section 1
and "does not establish"; ADR 0060 D2 (the `platforms` row); ADR 0067 header, D7, E-F8-8, build table rows 4 to 6, open
question 5; ADR 0056 row 5; `docs/roadmap/roadmap.md:50, :121`; the K05 review M5 (`docs/reviews/K05-review.md:176-195`);
`src/openflowsheet/run/replay.py:40-141`; `src/openflowsheet/run/manifest.py:86-152`;
`scripts/corpus_identity.py:49-81, 469-505, 770-800`; `docs/X07a_DECISIONS.md`; the tests named in section 2.

Consistency with frozen text: no frozen interface changes (`ReplayReport` and its fields, the three `ReplayMode` values,
every schema stay as they are); the F0 registry `benchmarks/f0/corpus.json` is not re-recorded; no file in F0 M9's list
is touched (M9 registers 35 files under `models/` and `thermo/`; `run/replay.py` is not among them).

## 2. Facts this ruling rests on

- **F-1 Registration authority.** ADR 0007 D3.3: the registered pair is `ubuntu-latest` x86-64 and `ubuntu-24.04-arm`
  ("Frank's choice of 2026-09-22; not open"). D4's table: `exact_replay` when "same lock-file hash, same platform
  identity, same thread pins" (no registration condition); `compatible_reproduction` when "same lock-file hash, a
  different *registered* platform"; `inspected_archived_results` when "a dependency, lock or platform outside the
  registered set is missing or changed, or the rerun was not attempted". "Changing this ADR": a change to what replay
  reports needs a new ADR. No ADR defines string ids for registered platforms; `replay.py:53` encodes the pair as
  `(platform.machine(), platform.system())` values.
- **F-2 Code.** `REGISTERED_PLATFORMS = {(x86_64, Linux), (aarch64, Linux)}` (`replay.py:53`). `decide_mode` (`:86`)
  runs the lock rungs, then checks registration of both sides (`:105-111`) **before** it compares identities (`:113`),
  so an unregistered platform gets `inspected_archived_results` even when nothing differs. The K05 review M5 asked for
  "either outside the set -> `inspected_archived_results`" after measuring an s390x archive replayed as
  `compatible_reproduction` on x86-64; the case it measured had two different platforms.
- **F-3 Identity** (`manifest.py:117`): architecture, OS, Python version, BLAS name; `os_release` excluded. The exact
  rung also needs an equal BLAS version (`:125`), equal thread pins and pins known on both sides (`threads_known`,
  Frank's F4 answer of 2026-09-22).
- **F-4 F0 M7** (`corpus_identity.py:79-81, 793-796`): off the reference class `ref-x86-64`, M7 judges `verdict` and
  `integrity_ok`. On macOS (run 44615939688) all 52 bundles are `NOT_RUN` against a registered `MATCH`; M2, M3 and M5
  are equal there, so the R0 of the RC set agrees.
- **F-5 Measured differences** (WO2, macOS run 44629506428):
  - T05b B02, `kernel_targets`: 1.9163045025588417 (`0x1.ea92ee8faaf33p+0`) against 1.9163045025588423
    (`0x1.ea92ee8faaf36p+0`): 3 ulp, 3.5e-16 relative, inside `T08-numerical-policy-v2`'s relative 1e-9 by a factor of
    about 2.9e6. It fails only because its expectation is bitwise (`float.hex()`, `tests/test_t05b_kernel_inert.py:1-7`).
  - M03, `qualification.outcomes[8].splits[1].margin`: 1.3370443359361772e-05 against 1.33704433897...e-05: absolute
    3.03e-14, relative 2.27e-9 (from the truncated Linux value), 2.3 times the policy's 1e-9. The comparison is
    policy-bounded (`tests/m03_fixture_compare.py:132-137`). M03's rules floor the outcome's `scaled_residual_inf` and
    `residual_normalized` at the sibling threshold (`:318-343`) and give `splits[].margin` no floor. The same member
    kind is floored at `feas` in `studies/nlp/replay.py:353`, and compared relatively without a floor by M03's own
    `measurement_differences` (`:144-145`: "a regime margin ... its tolerance is a minimum and not a noise floor").
  - TH-C1 goldens (`tests/test_st_cli.py:106`): byte identity of the CLI rendering of a fresh solve against
    self-generated regression goldens (module docstring); all three forms differ.
- **F-6** ADR 0025 holds no per-platform record and no layout for one: "platform" occurs at its lines 189, 317-318 and
  335-341 only, and its "does not establish" excludes "any third platform". Its remedy for the aarch64 excess that
  triggered it (21 of 52 RC bundles `MISMATCH`) was reclassification, applied on every platform.
- **F-7** ADR 0060 D2's `platforms` is the extension descriptor's declarative vocabulary (`linux-x86_64`,
  `linux-aarch64`, `windows-x86_64`, `macos-x86_64`, `macos-arm64`), "never consulted by admission". It registers
  nothing, and names a platform no CI leg runs (`macos-x86_64`).
- **F-8** ADR 0067 is Proposed. D7 is headed "(ADR 0025's pattern; X07a)"; its build table schedules D7 as F8-WO5
  "(0.6, with X07a)" in `run/platform_refs.py`; the roadmap places X07a in 0.5 (`roadmap.md:50`). Nothing of D7 exists
  in `src` or `tests`.
- **F-9** `tests/test_k05_replay.py:374-402` (the S8 guard against "a registration without a measurement") maps every
  runner whose label lacks "arm" to `(x86_64, Linux)`. Since D-7 added `windows-latest` and `macos-latest`, both map to
  `(x86_64, Linux)` and the guard still passes: it is vacuous for the two new legs.
- **F-10 Grid measurement** (this ruling, at `bd7548e4`, a scratch script over the 288 environments defined in section 6
  A1): the rule of R1.2 changes `decide_mode` on exactly 64 of 82 944 ordered pairs. Each of the 64 is a pair of equal
  environments on an unregistered platform with verified equal locks and known equal pins, and moves from
  `inspected_archived_results` to `exact_replay` with no reason. None of the 20 736 pairs with both sides registered
  changes, in mode or in reasons.

## 3. Findings on the governing text

- **G-1** ADR 0067 D7 cites "the platform ids of ADR 0060 D2" for the registered platforms. As an authority for
  registration this is wrong (F-7): the registered set is ADR 0007 D3.3's pair. ADR 0060 D2 is usable for the spelling
  of ids only. Erratum E-D7-1.
- **G-2** D7's "ADR 0025's pattern" and "ADR 0025's existing layout" have no referent (F-6). ADR 0025's actual pattern,
  reclassification on every platform, is the step that must come before any per-platform record. ADR 0067 open question
  5 is settled by fact: there is no existing layout, so D7's own naming applies. Erratum E-D7-2.
- **G-3** Schedule: D7's heading says X07a, its build table says F8-WO5 in 0.6 "with X07a", and the roadmap puts X07a
  in 0.5. Erratum E-D7-5 and Q-8.
- **G-4** The K05 S8 guard is vacuous for the new legs (F-9). WO3 A4 repairs it.
- **G-5** `docs/X07a_DECISIONS.md` Q-2 cites `run/replay.py:239` for the registration rung; at `bd7548e4` it is
  `replay.py:105-111` (`decide_mode` at `:86`).
- **G-6** ADR 0007 D4's `inspected_archived_results` row is ambiguous for a same-identity replay on an unregistered
  platform; its `exact_replay` row names no registration condition. The K05 M5 correction and the code took the reading
  that excludes exact replay there. Amendment 3 settles the reading.

## 4. Rulings

### R1 (Q-2): replay platforms

**R1.1 macOS arm64 and Windows x86-64 stay unregistered in 0.5.** Registration is the promise of ADR 0007 D3: R0
bit-identical, and floats within the policy each record names, between registered platforms. It changes Frank's D3.3
choice, and the measurement that would justify it has never run: M7 has only ever been `NOT_RUN` there, and the one
policy-bounded comparison that measured a cross-platform float on macOS (F-5, M03) exceeds the policy. A green leg does
not make that promise.

**R1.2 A rerun that meets D4's `exact_replay` conditions gets `exact_replay` on any platform.** The conditions: both
locks verified and equal; equal identity (architecture, OS, Python version, BLAS name); equal BLAS version; equal thread
pins, known on both sides. Registration governs only a replay whose environments differ. Where either side is
unregistered, every replay that does not meet the exact conditions is `inspected_archived_results` / `NOT_RUN` with the
existing reason (`recorded on` or `running on` `<machine>/<system>, which is not a registered platform; ...`, first the
recorded side), and never `compatible_reproduction`. Between registered platforms `decide_mode` is unchanged, reasons
included (F-10). The lock rungs keep their place before every other rung.

Reason: an exact replay compares a run with itself on one platform identity. It makes no cross-platform claim, so D3.3
is not engaged, and it is the only way a macOS or Windows leg can test determinism on its own platform. **The mode a
same-host rerun on an unregistered platform gets is `exact_replay`**, with the verdict as compared and `bitwise_floats`
as observed. Because the reviewed reading (K05 M5, the code) is the other one, R1.2 is drafted as ADR 0007 Amendment 3
(section 5.1) rather than treated as already within the text.

**R1.3 What registers a platform.** Nothing in X07a registers one. A platform P joins D3.3's set only by an ADR 0007
amendment accepted by Frank that cites this evidence, from P's CI leg at one commit of a measurement branch that adds P
to `REGISTERED_PLATFORMS` (that branch is not merged before the acceptance):

- **E-1** F0 on P: M1, M2, M3, M5, M6 (the committed sample), M8 and M9 PASS. This is R0 equality over the registered
  corpus.
- **E-2** F0 M7 on P with P registered: 52 of 52 bundles `compatible_reproduction` / `MATCH`, `integrity_ok` true. This
  covers floats of a linux-x86_64 archive within the policy each bundle names. ADR 0025's trigger measurement, the same
  52-bundle replay on aarch64, is the precedent.
- **E-3** Every `replay-committed` row (R2, P1c) for P lifted, its test green.
- **E-4** Every `policy-difference` row for P resolved, either by a classification fix applied on every platform
  (P3b) or by a D7 per-platform record (which needs D7 built: F8-WO5).
- **E-5** The literal pin `tests/test_k05_replay.py:566` and the CI-matrix guard (WO3 A4) updated in the same commit.

Not sufficient on its own: a green same-host leg (after R1.2 it measures determinism on P, not comparability with the
registered set), or R0 equality without E-2 (registration also promises floats). The reverse direction (bundles written
on P replayed on Linux) is not required: the v2 comparator is `math.isclose` (`run/compare.py:559`), whose relative term
is symmetric, and E-1 already compares the R0 of runs made on P with the registry. `bitwise` rows (P2) are not part of
registration, because registration promises no bits (ADR 0007 D3.2).

**R1.4 F0 M7 per machine class.** The registry is not re-recorded. F0 classifies the host by
`run.manifest.environment()`'s `(architecture, os_name)` against `run.replay.REGISTERED_PLATFORMS`. That is one copy of
the set; its literal pin in `test_k05_replay.py:566` stays and is the independent guard.

| Host | M7 judges, per registered bundle key |
| --- | --- |
| reference class `ref-x86-64` | `verdict`, `mode`, `integrity_ok` as registered (unchanged) |
| another machine on a registered platform | `verdict`, `integrity_ok` as registered (`M7_PORTABLE`, unchanged) |
| a machine on an unregistered platform | `verdict == "NOT_RUN"`, `mode == "inspected_archived_results"`, `integrity_ok` as registered, and the report's reasons exactly one, beginning `running on <machine>/<system>, which is not a registered platform` |

Log line for the third row: `M7: <machine>/<system> is not a registered replay platform (ADR 0007 D3.3): judged
inspected_archived_results/NOT_RUN with the unregistered-platform reason; MATCH is judged on the registered legs`.

*Erratum (review R-10, `docs/X07a-review.md`, 2026-11-20):* for "the report's reasons exactly one" read "the report's
reasons exactly two, in this order: the `running on <machine>/<system>, which is not a registered platform` reason,
then `no rerun was supplied`"; a third reason, a missing one or a lock reason fails (D-20).

This does not relax M7. On an unregistered platform the replay policy forbids the comparison, so `MATCH` is not a
possible correct answer there. The judged answer is exact and fails on a false registration (`compatible_reproduction`
or `MATCH`), an integrity failure, an unverified lock (its reason would come first) or an unknown policy (a second
reason). The rerun comparison of all 52 bundles stays judged on both Linux legs.

**R1.5 Replay-class tests.** Three cases:

- A bundle written in the same session on the host needs no platform branch: R1.2 makes it `exact_replay`. If one
  still fails on a leg, it is a defect to diagnose, not a platform limit.
- A test of `decide_mode` as a function builds complete environments from a registered Linux template. It never mutates
  one field of the host's environment, as `test_k05_replay.py:173-195` and `:553-576` do now (on macOS they produce
  `(x86_64, Darwin)` and expect `compatible_reproduction`).
- A committed bundle recorded on another platform falls under P1c.

### R2 (Q-3): floating-point differences on a new leg

**R2.1 ADR 0067 D7 does not settle Q-3 for 0.5.** D7 is about registered platforms ("R0 is identical on every
registered platform") and reference records the comparator consumes, and is scheduled as F8-WO5 (F-8). None of the
three named failures is a D7 case:

| Failure | Class | Why |
| --- | --- | --- |
| `test_t05b_kernel_inert.py::test_every_registered_call_is_bitwise_the_baseline[kernel_targets]` and the same module's `test_the_baseline_is_what_the_generator_emits_today` | bitwise | an inertness claim: the kernel before T05b W0.1 against the kernel after, on one platform. A macOS record emitted today comes from the post-change kernel, so the test would compare the code with itself (F-5: the difference is 3 ulp, inside the policy) |
| `test_st_cli.py::test_th_c1_golden[csv,json,text]` | bitwise | byte identity of a fresh solve's rendering against self-generated regression goldens |
| `test_m03_schemas.py::test_the_fixtures_are_what_real_runs_emit_today` | policy-bounded | a float 2.3 times beyond the policy on an unregistered platform; first the classification question (Q-4), meanwhile a platform-difference row |

A bitwise expectation **never** takes a per-platform record. Of the three, only a policy-bounded comparison can become a
D7 case, and only after its platform is registered and its classification is settled.

**R2.2 The rule for each further failure of this class.** Apply in order and stop at the first that holds:

- **P1 The replay mode is the cause** (`NOT_RUN`, `inspected_archived_results`, the unregistered-platform reason).
  - P1a A same-session bundle: R1.2 applies; no platform branch.
  - P1b Constructed environments: build them from a complete registered template; no platform branch.
  - P1c A committed bundle recorded on a registered platform and replayed on an unregistered one. On that platform the
    test asserts the policy's answer through one shared helper (`tests/conftest.py`, for example
    `assert_inspected_off_registered(report)`): mode `inspected_archived_results`, verdict `NOT_RUN`, `integrity_ok`
    true, and reasons exactly one, the `running on` reason. The comparison claim stays judged on the registered legs.
    Row class `replay-committed`, lifted by the platform's registration.
    *Erratum (review R-10, 2026-11-20):* the reasons are exactly two, the `running on` reason and then `no rerun was
    supplied` (as R1.4's erratum; D-20).
- **P2 The expectation is bitwise** (`float.hex()`, `repr` or byte goldens, `==` on a float or on a digest of floats
  recorded on another platform). Mark the node with the shared marker `bitwise_baseline` (`tests/conftest.py`). It runs
  on `BITWISE_BASELINE_PLATFORMS = {(x86_64, Linux), (aarch64, Linux)}`, where the committed baselines were recorded or
  measured bit-identical; registration never adds to this set. Off it, the node is skipped with a reason beginning
  `bitwise_baseline_off_platform`. Row class `bitwise`. Never a per-platform record, never an edit of the committed
  bits, never the Linux assertion turned into a tolerance. Companions, where they apply:
  - if the same document has a policy comparison in the repository (`run.compare.differences` or a registered rule
    set), run it on every platform under P3;
  - if the test contains a platform-independent step on committed input (formatting, serialisation), test that step on
    every platform.
- **P3 The expectation is policy-bounded** (`run.compare.differences`, `math.isclose` under a cited policy, M03's
  rules).
  - P3a Record the path, the Linux value, the leg's value, the bound (relative, floor, the floor's source) and the ratio
    |difference| / bound.
  - P3b Classification. Does the comparison give the quantity the class and floor that the policy's own rules give it
    (ADR 0007 D1 and D2.2, ADR 0025 D2 to D6)? Examples of a departure: a digest compared for value, a pivot-path
    diagnostic compared, a thresholded quantity compared without its registered threshold's floor. A departure is a
    comparator defect on every platform. Fix it everywhere, with a mutation case showing that a change above the
    corrected bound is still caught, as one isolated commit logged as a design-lane item for the X07a reviewer pass.
    Where the class is a judgement the policy's text does not settle (F-5's margin is one), do not choose: open a
    question carrying the P3a numbers.
  - P3c Until then, a platform-difference row. The test asserts, on that platform, that its set of beyond-policy paths
    equals exactly the registered set (`tests/conftest.py`, for example `PLATFORM_DIFFERENCES[(machine, system)][node]`):
    an extra path fails, and a registered path that no longer differs fails. On a registered platform the set is empty
    by construction, and a test asserts the registry has no registered-platform key.
  - Never a D7 record on an unregistered platform, never a wider relative tolerance, never an edit of the
    Linux-recorded fixture.
- **P4** Anything else (paths, encodings, processes) is not this class; WO2's rules apply.
- **P5** Each row goes into the platform-limit table of `docs/X07a_DECISIONS.md` with an id `X07a-L<n>`, the test
  node(s), the platform, the class, the P3a numbers where they apply, the run id, and what lifts it.

### R3 ADR consequences

- **ADR 0007 Amendment 3** (proposed, section 5.1) carries R1.2 and R1.3. It is needed because ADR 0007 requires an ADR
  for a change to what replay reports, and the reviewed reading is the other one (G-6). WO3 builds against it on
  `wp/X07a` as one isolated, revertible commit. X07a merges to `main` after Frank accepts it; until then the X07a
  manifest names it as a limitation.
- **ADR 0067 D7 errata** (proposed, section 5.2), to be folded into ADR 0067 before its acceptance.
- No change to ADR 0025, ADR 0056 or ADR 0060.

## 5. Drafted texts (proposed)

### 5.1 ADR 0007 Amendment 3 (X07a): exact replay on any platform; the evidence that registers a platform

**Status:** Proposed, 2026-11-20. Ruling `docs/X07a-platform-ruling.md`, R1.2 and R1.3.

**D4.** The table is unchanged. Its `exact_replay` row is read as written: the same verified lock, the same platform
identity (architecture, OS, Python version, BLAS vendor; D3.3), the same thread pins known on both sides (F4), and, as
the implementation already requires, the same BLAS version. These conditions decide `exact_replay` on any platform,
registered or not. The registered set governs only a replay whose environments differ: where either side is outside
it, such a replay is `inspected_archived_results` / `NOT_RUN` with a reason naming that side, and never
`compatible_reproduction`. Between registered platforms nothing changes.

**D3.3.** Unchanged. The registered pair stays `ubuntu-latest` x86-64 and `ubuntu-24.04-arm`. An exact replay on an
unregistered platform compares a run with itself on one platform identity and carries no promise to any other platform.

**Registering a platform.** A platform joins D3.3's set only by a further amendment accepted by Frank. That amendment
cites, from the platform's CI leg at one commit of a measurement branch that adds it to the registered set: F0 M1, M2,
M3, M5, M6 (sample), M8 and M9 PASS; F0 M7 52 of 52 `compatible_reproduction` / `MATCH` with `integrity_ok`; every
replay of a committed bundle passing without a platform limit; every beyond-policy float there resolved by
reclassification on every platform or by an ADR 0067 D7 record. A same-host green leg does not register a platform.

**What this amendment does not establish.** That a run on an unregistered platform agrees with any other platform, in
R0 or in floats; that floats reproduce bit for bit anywhere (D3.2 stands).

**Acceptance evidence.** X07a-WO3 A1 (the decision table over 82 944 ordered pairs), A2 (64 pairs change, all
same-identity pairs on unregistered platforms; none between registered platforms), A6 (same-session reruns
`exact_replay` / `MATCH` on the macOS and Windows legs).

**Affected requirements.** As ADR 0007 (D20, A08); K05's G05 evidence is unchanged. **Migration impact:** none. No
stored record, schema, digest or registered expectation changes, and every replay between registered platforms reports
as before.

### 5.2 ADR 0067 D7 errata (proposed; fold in before ADR 0067 is accepted)

- **E-D7-1** (G-1) "(the platform ids of ADR 0060 D2)" becomes "(ADR 0007 D3.3's registered set, as amended; ids spelled
  in ADR 0060 D2's vocabulary: `linux-x86_64` = (x86_64, Linux), `linux-aarch64` = (aarch64, Linux), `macos-arm64` =
  (arm64, Darwin), `windows-x86_64` = (AMD64, Windows), as `platform.machine()` and `platform.system()` report them)".
- **E-D7-2** (G-2) The heading "(ADR 0025's pattern; X07a)" becomes "(after ADR 0025's classification step; F8-WO5)".
  Added: "A per-platform record is made only for a quantity shown to be correctly classified under the policy. ADR
  0025's remedy for the aarch64 excess was reclassification on every platform; a float that exceeds the policy because
  the comparison misclassifies it is fixed in the comparison, on every platform." Open question 5 is closed by fact: ADR
  0025 has no per-platform layout, so D7's naming applies.
- **E-D7-3** Added: "Per-platform records exist only for registered platforms. On an unregistered platform a
  beyond-policy float is a platform-difference row (X07a ruling, P3c): evidence toward a registration, never a
  reference record."
- **E-D7-4** Added: "A bitwise expectation (a refactor or inertness baseline, a byte golden) never takes a per-platform
  record. It is judged on the platforms where it was recorded or measured bit-identical (X07a ruling, P2)."
- **E-D7-5** (G-3) Build table row 5 "F8-WO5 (0.6, with X07a)" becomes "F8-WO5 (0.6, or with the first platform
  registration under ADR 0007 Amendment 3, whichever is first)". E-F8-8 is unchanged.

## 6. X07a-WO3: work order and acceptance

**Lane and owner.** Build lane on `wp/X07a`. The replay and F0 changes (C1, C4) touch replay identity: an Opus engineer
does them, and the X07a `reviewer` pass covers them. The mechanical row work (C5, C6) may be done by Sonnet. Commits name
the package; stage named paths only.

**Changes.**

- **C1** `run/replay.py` `decide_mode` per R1.2. After the lock rungs: if identity, BLAS version and thread pins are
  equal and known on both sides, return `exact_replay` with no reason; otherwise the registration loop (text unchanged),
  then the existing differing rungs. `REGISTERED_PLATFORMS` is unchanged. The comment at `:40-52` gains one sentence:
  the set governs reproduction across environments, and exact replay needs no registration (ADR 0007 Amendment 3).
- **C2** New `tests/test_x07a_replay_platforms.py` (A1).
- **C3** `tests/test_k05_replay.py`: constructed environments at `:173-195` and `:553-576`; the CI-matrix guard (A4).
- **C4** `scripts/corpus_identity.py` M7 per R1.4, plus a unit test of the judgement (A5).
- **C5** `tests/conftest.py`: `BITWISE_BASELINE_PLATFORMS` and the `bitwise_baseline` marker (P2), the P1c helper, and
  the `PLATFORM_DIFFERENCES` registry (P3c).
- **C6** P1 to P5 applied to every Q-2 or Q-3 failure on the macOS and Windows legs, one row each.

**Acceptance.** Report each item with its command and its one-line result.

- **A1 Decision table** (`tests/test_x07a_replay_platforms.py`, on every leg).
  - The grid: environments are built directly as `Environment(...)`. Platform ∈ {(x86_64, Linux), (aarch64, Linux),
    (arm64, Darwin), (AMD64, Windows)}; `python_version` ∈ {"3.13.1", "3.12.8"}; `blas` = {"name": n, "version": v}
    with n ∈ {"openblas", "accelerate"} and v ∈ {"0.3.28", "0.3.29"}; `threads` = every one of the three
    `THREAD_VARIABLES` set to t, with t ∈ {"1", "4", None}; `lock_sha256` ∈ {"a" × 64, "b" × 64, ""}; `os_release`
    "r". That is 288 environments and 82 944 ordered pairs.
  - Why each axis is in the grid: platform has two registered and two unregistered values, so both sides of the
    registration rung are exercised. Python version and BLAS name are identity members. BLAS version drives the
    BLAS-version rung, the thread values drive the pins rung and the pins-known rung, and the lock values drive the
    unverified-lock and differing-lock rungs. Every axis has at least two values, so each rung changes the counts.
  - Every pair's mode equals the table T, whose first holding row decides:
    1. a lock empty, an ADR 0069 template reason;
    2. locks differ, a reason beginning `the lock file differs`;
    3. identity, BLAS version and pins equal and known on both sides: `exact_replay`, no reason;
    4. the recorded side unregistered: inspected, a reason beginning `recorded on <m>/<s>, which is not a registered
       platform`;
    5. the current side unregistered: the same with `running on`;
    6. otherwise `compatible_reproduction`.

    Every non-exact decision carries exactly one reason.
  - Counts, in closed form. A pair passes the lock rungs for 2 of the 9 lock combinations, which is 1 152 of the 5 184
    environment pairs of each ordered platform pair. Exact pairs agree in every member, with pins known and the lock
    non-empty: 4 × 2 × 2 × 2 × 2 × 2 = **128**, 64 of them on registered platforms. Compatible: 4 × 1 152 − 64 =
    **4 544**. Inspected at a lock rung: 82 944 × 7/9 = **64 512**. Inspected `recorded on`: 2 × 4 × 1 152 − 64 =
    **9 152**. Inspected `running on`: 2 × 2 × 1 152 = **4 608**. Total 82 944. All five counts were measured at
    `bd7548e4` with C1's rule applied in a scratch script, and they agree.
  - Mutation evidence (measured): dropping the lock condition from row 3 gives 576 exact pairs; dropping identity,
    2 048; BLAS version, 256; thread equality, 256; pins known, 192; the code at `bd7548e4` gives 64. Each differs from
    128, so asserting the five counts catches each of these slips.
- **A2 No-op on registered pairs** (one-time measurement, logged in `docs/X07a_DECISIONS.md`). Over the A1 grid,
  `decide_mode` at `bd7548e4` (from `git show bd7548e4:src/openflowsheet/run/replay.py`, in scratch) against C1:
  - 82 880 pairs identical in mode and reasons;
  - 64 pairs differ, every one a pair of equal environments on (arm64, Darwin) or (AMD64, Windows), moving from
    inspected to `exact_replay`;
  - 0 differing pairs with both sides registered.

  This ruling measured 288 / 82 944 / 82 880 / 64 / 0.
- **A3** `tests/test_k05_replay.py` passes on all four legs with no platform branch. The environments of
  `test_d4_the_mode_table_in_full` and `test_m5_an_unregistered_platform_is_unknown_on_either_side` are built from a
  registered Linux template (`replace(env, architecture="x86_64", os_name="Linux")` and its aarch64 sibling), and the
  s390x cases still give inspected with `not a registered platform`.
- **A4 CI-matrix guard** (`test_the_ci_workflow_pins_threads_and_compares_two_platforms`).
  - An explicit runner table: `ubuntu-latest` (x86_64, Linux), `ubuntu-24.04-arm` (aarch64, Linux), `macos-latest`
    (arm64, Darwin), `windows-latest` (AMD64, Windows). A runner label missing from the table fails the test.
  - Assertions: `REGISTERED_PLATFORMS` ⊆ the matrix pairs, and matrix pairs − `REGISTERED_PLATFORMS` ==
    {(arm64, Darwin), (AMD64, Windows)}.
  - The same assertions on a copy of the matrix without `ubuntu-24.04-arm` fail; the test asserts that it does.
- **A5 F0.**
  - `scripts/corpus_identity.py --check` PASS on both Linux legs and on the workstation, M7 judged as before.
  - macOS: M7 PASS with the R1.4 log line. Windows: the same, if F0 runs to its end there; otherwise log what stopped
    it.
  - `git diff --quiet bd7548e4 -- benchmarks/f0/corpus.json` succeeds (the registry is untouched).
  - A unit test of M7's judgement on a constructed unregistered host. The policy's answer passes. Each of these fails:
    verdict `MATCH`; mode `compatible_reproduction`; reasons led by a lock reason; two reasons; `integrity_ok` false
    where the registry says true. On a registered non-reference host, `NOT_RUN` still fails (unchanged).
- **A6 Same-session family on macOS and Windows.**
  - The Q-2 nodes pass with mode `exact_replay` and no platform branch: `test_g8_rerun_matches_on_the_same_host` (all
    parameters), `test_a16_a17_the_replay_matrix` (all cells), and the `test_g16*` and `test_t07_q26_*` nodes of Q-2.
  - Logged per leg: `environment().lock_sha256` is non-empty, and `(architecture, os_name)` is as reported. This confirms
    (arm64, Darwin) and (AMD64, Windows), or corrects this ruling, which then says so (Q-6).
- **A7 Bitwise class.**
  - Both T05b B02 bitwise tests and `test_th_c1_golden` carry `bitwise_baseline`.
  - Both Linux JUnit artifacts show 0 skips whose reason begins `bitwise_baseline_off_platform`. On macOS and Windows
    those skips equal the marked nodes.
  - TH-C1 companions on all four legs:
    - (a) `to_text`, `to_csv` and `to_json` of the golden JSON document (`stream_table_format.py:238, :356, :484`), with
      `_golden`'s adjustments, equal the goldens byte for byte. Check this on Linux first; if it fails there, stop and
      report, because the premise that the goldens are the formatter's image of the JSON golden is false.
    - (b) The fresh JSON document against the golden JSON under `differences(..., policy_id=CURRENT_POLICY_ID)`: empty
      on Linux; under P3 elsewhere.
- **A8 M03.** `test_the_fixtures_are_what_real_runs_emit_today` keeps `found == []` on Linux. On macOS the set of
  beyond-policy paths equals its `PLATFORM_DIFFERENCES` entry exactly (F-5's margin path, with its fixture name taken
  from the leg's log), with its row carrying the P3a numbers. Q-4 is opened in `docs/X07a_DECISIONS.md`.
- **A9 Rows agree with code.** A test collects the `X07a-L<n>` ids in the platform-limit table of
  `docs/X07a_DECISIONS.md` and the ids carried by every `bitwise_baseline` use, P1c helper use and
  `PLATFORM_DIFFERENCES` entry, and asserts the two sets are equal. `PLATFORM_DIFFERENCES` has no
  registered-platform key.
- **A10 No Linux relaxation.** Every node that passed on a Linux leg in run 44652504290 (head `a24a0bf3`) passes on the
  same leg at the WO3 head; no Linux node is newly skipped. New nodes may be added.
- **A11 Documents.**
  - The install notes and `benchmarks/t08/support_envelope.yaml`'s reproducibility statement say: "macOS arm64 and
    Windows x86-64: bundles made on the same platform identity replay exactly; bundles from another platform are
    inspected, not reproduced (ADR 0007 D3.3, Amendment 3)".
  - The X07a manifest's limitations name Amendment 3 as proposed and the two unregistered platforms, with the T08
    harvest rows (D-13).
- **A12 Class closed.** On macos-latest, no failure of the Q-2 or Q-3 class remains: each is fixed by R1.2 or R1.5, or
  carries a row. The leg is green if no other class remains. Windows: the same for this class; other classes stay as in
  WO2's position.

**Stop and report instead of choosing:**

- A7(a)'s premise fails on Linux.
- A same-session test still fails on a new leg after C1 (a determinism defect).
- A leg's lock does not verify (Q-6).
- G05 fails on a difference that involves an unregistered leg only (Q-7).
- A P3b classification that the policy's text does not settle.
- Any Linux node newly fails or is skipped.

## 7. What this ruling does not establish

- Any cross-platform promise for macOS or Windows, in R0 or in floats. F0's equal M2, M3 and M5 there are observations.
- That a same-identity rerun on macOS or Windows reproduces bits, across OS releases or otherwise: `exact_replay`
  compares under the policy and reports bits as observed (ADR 0007 D3.2).
- That the premises of the numerical policy, measured on Linux (ADR 0025 D7's noise model), hold on macOS or Windows.
- That F-5's margin excess is noise rather than a defect: that is Q-4.
- That the bitwise baselines hold on linux-aarch64 by promise. They hold there by observation, and
  `BITWISE_BASELINE_PLATFORMS` records the observation.
- The `(machine, system)` values for macOS and Windows: they come from Python's documented behaviour, not from a leg's
  record. A6 confirms them.
- Anything of Q-1, the `nlp` and reactor environments (X07b), or D7's implementation (F8-WO5). The X07 scope item
  "per-platform reference records where floating point differs" (ADR 0056 row 5) is met by F8-WO5 at registration, not
  by X07a. X07a supplies the measurement rows that F8-WO5 will need.

## 8. Open questions, each with a default

- **Q-4 (needs a fact).** Is M03's `qualification.outcomes[].splits[].margin` correctly compared without a floor?
  - The measurement that settles it: the margin's defining expression and its operands' magnitudes at fixture outcome
    8, split 1 (the ratio |operand| / |margin|), and whether a registered threshold (`TAU_REGIME` = 1e-4 at
    `studies/sensitivity.py:89`, or `feas`) floors it under ADR 0007 D2.2's rule.
  - Default: no floor, following M03's own rule for regime margins; the macOS platform-difference row stands; ruled in
    the X07a reviewer round.
- **Q-5 (needs the user's preference, Frank).** Register macOS arm64 and/or Windows x86-64 for cross-platform
  reproduction, and when?
  - Default: not in 0.5. Evaluate at F8-WO5 (0.6) on E-1 to E-5. An unattended session never registers a platform.
- **Q-6 (needs a fact).** Does each new leg record a verified lock? The measurement is A6's logged `lock_sha256`.
  - Default: yes, since the runtime closure is nine distributions with wheels on both platforms (`run/lock.py:41-51`).
  - If not: the same-session family fails at the lock rung. Stop and file it with Q-1 as a per-platform lock question.
- **Q-7 (needs a fact).** Does G05 (the `identity` job, which compares every leg that emitted its identity) pass with
  four legs?
  - Default: unchanged. If it fails only on a difference involving an unregistered leg, stop and report the differing
    keys, without excluding the leg.
- **Q-8 (needs a preference, orchestrator).** When is D7 built?
  - Default: per E-D7-5, at F8-WO5 (0.6) or with the first registration, whichever is first. X07a builds no part of D7.

## 9. Alternatives rejected

- **Register macOS and Windows in X07a on a green leg.** It promises R2 where nothing has measured it (K05 M5), and F-5
  already shows one cross-platform float beyond the policy on macOS.
- **Keep `decide_mode` and make the same-session tests platform-aware.** That puts branches in about 144 tests and leaves
  the new legs with no determinism test of replay.
- **F0 M7 `NOT JUDGED` off registered platforms.** It discards a checkable answer, the mode decision and the integrity.
- **Per-platform bitwise baselines.** For an inertness baseline the comparison becomes tautological. For goldens, every
  package's regeneration would need four legs, and the baselines would still promise bits that ADR 0007 D3.2 refuses to
  promise.
- **Build D7 in X07a.** D7 serves registered platforms, and nothing is registered in 0.5. F8-WO5 carries the comparator
  plumbing.
- **Floor the M03 margin now.** It is a classification judgement, and M03's own rule leaves regime margins without a
  floor. The build lane may not make it.
- **A strict `xfail` of a whole policy-bounded test on a platform.** It would hide a new difference anywhere else in the
  same test. P3c's exact path set does not.
