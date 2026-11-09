# REL040 — S-6's three record findings: ruling

Design lane (`specifier`), 2026-11-09. Brief: `docs/briefs/REL040-s6-ruling.md`. Read at `wp/REL040p` `a1a00e17` (the
S-6 record in `docs/RP_DECISIONS.md`, RP with A-10), `wp/S6dbg` `76d191f2` (`docs/S6DBG_DECISIONS.md`, F-B) and `main`
`7adcd58d`. Register: **R-1008** (one entry). RP amendment: **A-11**.

## 0. Authority and scope

- This note is the normative text for rulings 1–4 (§2–§5), for RP amendment A-11 (§6), for register entry R-1008 (§7),
  and for the behaviour of the three tools that work orders WO-1 to WO-4 specify (§8).
- It changes none of these:
  - the reactor's environment fingerprint (M02 design §2.4) or the experiment-key semantics (ADR 0036 D8);
  - any experiment key or store, and G10's comparison;
  - W22 (b)'s criterion (alpha spec §6.2, "Only `inputs.*_sha256` members may differ"), M01.A37's tolerances, or any
    other gate's criterion or tolerance (RP §1 item 3);
  - R-458's rule for the five in-process records;
  - any 0.3.0 record. The tag `v0.3.0` keeps its tree. The records in `main`'s tree move only by §7.1's re-takes, as
    the five in-process records already do;
  - any frozen interface.
- It does not rule on S-6's other finding, F-A (the NLP-1 inventory `TypeError`). F-A is a class (a) code fix with its
  own evidence on `wp/S6dbg` `3e25b294`, and merging it is the orchestrator's call.
- Every number in §1 was measured for this ruling, or is quoted from the record named beside it. All comparisons in
  this note are exact (§8.0).

## 1. Facts

| # | Fact | Source |
| --- | --- | --- |
| F1 | Each of the committed REAL record's four coupling records (`S0`, `cand-C1-P1`, `cand-C1-poll-preheater.T_spec-plus`, `…-minus`) holds `frozen.reactor.fingerprint.platform` = `Linux-6.12.111+deb13-amd64-x86_64-with-glibc2.41`. Its `fingerprint_sha256` = `document_sha256(fingerprint)` = `dfce4150194f9d4a1b2e4814f0d803187e441fef435f65709b8ca9164c0beaaf`, which is every archived request's `environment_fingerprint_sha256`. | design-lane recomputation, `openflowsheet.canonical.document_sha256` |
| F2 | The same fingerprint with `6.12.111` → `6.12.113` hashes to `5710568df0d65b08fff44935a8ba5c97bb878e44c77dbcdae428768cc6a4bfa7`, the live digest that S6dbg measured. Today the host reads `Linux-6.12.113+deb13-amd64-x86_64-with-glibc2.41`, so the C library is unchanged (2.41). | recomputation; S6dbg F-B |
| F3 | The kernel string appears in clear only at that leaf of the four coupling records. It occurs 0 times in the record, the ledger, the store index, the environment sidecar and the experiments archive. The archive holds 144 files: 48 keys, each with a request, a result and an attempt. The kernel enters every one of the 48 experiment keys through the fingerprint digest, archive file names included. | `grep` over `benchmarks/m05/records/trust-region-study-real.*` |
| F4 | The fingerprint of the five in-process records is `{kind, boundary_sha256, module, module_sha256, openflowsheet_version}`. It has no host member, so the kernel change does not affect them. | R-458 evidence |
| F5 | 0.3.0's journey (`benchmarks/m07/journey/2d945b5d…/m05/…coupling/*.json`, R3 `carried_from: rerun`) holds `6.12.111` at the same four leaves. Step 15's `a21.replay` failure at S-6 therefore has the same cause as F-B. All three committed journeys re-ran R3. | `grep` |
| F6 | A REAL re-take on the same kernel (M05 S70, `cdacc32`, 2026-10-16) took 1454 s of wall time for 48 cold experiments at `OMP_NUM_THREADS=1`. Every request and result file came out bytewise equal, the attempts differed only in timings, and the ledger, store index and environment were byte-identical. On one host, REAL reproduces bitwise. | `docs/design/M05-build-decisions.md` S70 |
| F7 | `scripts/m05_retake_diff.py --digest-only` walks the record (without `provenance`), the ledger, the coupling records, the store index and the environment. It does **not** walk REAL's experiments archive, and the only clear non-digest leaf it admits is `version`. On a kernel re-take of REAL it would classify the four `platform` leaves as `other` and FAIL by construction, and it would never read the archive's 48 result files. | `scripts/m05_retake_diff.py:313–360` |
| F8 | Step 11 compares the committed `benchmarks/m01/idaes-conformance.json` (SHA-256 `7dc55096…`, taken at `13bcef7f` on 2026-10-08) with S-6's re-run (`76068ff5…`). Two members differ: `environment.platform` (`…6.12.111…` → `…6.12.113…`) and `inputs.reference_values_yaml_sha256` (`6cef65b1…` → `46d684cd…`). | S-6 `step11/rc-step11.json` |
| F9 | Only one commit after `13bcef7f` touches `benchmarks/m01/reference_values.yaml`: `49e99756` (M01 Amendment 1, 2026-10-08), with 65 lines inserted and 0 deleted. It adds `derived_from_measured.discretization_estimate`, `assertion_margins` and six `generator_claims` (PR-07, PH-GAP, BD-04, BD-05, BD-06, DX-01), and changes no existing value. `idaes_conformance.py` only hashes the file (`:64`, `:546`); the states it uses are transcribed from `closed_form` into its source (`:88`). W22 (b) admits a differing `inputs.*_sha256` member that is listed, and M01's manifests (`3c803920…`, `6c816830…`) list this member with its reason. | `git diff 13bcef7f 49e99756`; alpha spec §6.2 |
| F10 | Two other committed files hold `dfce4150…`: M02's `benchmarks/m02/g10-adapter-halves-v3.json` (step 12's archived input, A-5) and M04's `benchmarks/m04/wo11-b2-it1-v3/manifest.json`. The RC does not replay either against the live reactor, and steps 12 and 13 passed at S-6 on `6.12.113`. | S-6 table |

## 2. Ruling 1 — M05's REAL record

**RP as written does not handle it.** RP §7.1 re-takes only the five in-process records, and their fingerprint has no
host member (F4). §4.5's R3 re-run at J produces the journey's own M05 record, so it cures step 15 but not step 14:
step 14 replays the committed `benchmarks/m05/records/trust-region-study-real.*`, which no step re-takes. RP needs
amendment A-11.

**Decision: option (1), made a standing rule.** M05's REAL record is re-taken at K3 at **every** cut, on the host that
runs C's steps 11, 14 and 15, and committed in J together with the five in-process records. The proof is a committed
tool. It establishes that nothing moved except the host's platform string at its one bound leaf, and the digests that
string feeds.
- **Command** (from a clean worktree at K3, in the audited nlp environment, with the reactor environment built from
  K3's lock):
  `OMP_NUM_THREADS=1 PYOMO_CONFIG_DIR=<venv>/share/pyomo PYTHONNOUSERSITE=1 PYTHONPATH=src:<cache>/nlp-test-tools
  <venv>/bin/python scripts/m05_wo9_real.py --retake-into <dir>` (the flag is WO-2's; `<dir>` lies outside the
  repository).
- **Proof**: `git archive <K3> benchmarks/m05/records | tar -x -C <old>`, then
  `<venv>/bin/python scripts/m05_retake_diff.py --digest-only <old>/benchmarks/m05/records/trust-region-study-real
  <dir>/trust-region-study-real --old-platform '<p>'`. Here p is the committed `S0` coupling record's
  `frozen.reactor.fingerprint.platform`, and the `platform` class is WO-1's. The proof passes iff it prints `PASS` with
  `version=0`, `other=0` and `environment=equal`. **Must be equal:** every non-digest, non-timing leaf of the record,
  ledger, coupling records, store index and experiments archive, bitwise. That includes every leaf of the reactor
  fingerprint except `platform`, its digests among them. The environment sidecar must be equal byte for byte. The
  old→new digest map must be a function and injective. `platform` must be 4 when the host's string differs from p, and
  0 when it is equal.
- **Where it lands**: `<dir>/trust-region-study-real.*` replaces `benchmarks/m05/records/trust-region-study-real.*`
  (the `.coupling/` directory as a whole) in J's commit. The proof's summary line goes into J's commit message and the
  RC build log.
- **Why every cut, not only after a kernel change.** The condition would need a diagnosis step that S-6 needed a debug
  package for. The re-take costs about 25 minutes of free compute (F6). It also reproduces REAL cold at K3's code,
  which is a stronger check than the replay alone. If K3's code had moved a REAL number, the proof fails at K3, where
  step 14 would otherwise fail at C.

**Rejected.**
- *(2) An ADR dropping the kernel, or `platform`, from the key-relevant fingerprint.* This changes M02 §2.4 and ADR
  0036 D8 and moves every experiment key and every M02/M04/M05 store. It is a D2.4 change made before a cut, to save a
  25-minute re-take. R-458 rejected the same move for the version, for the same reason.
- *(3) A replay that serves a request whose key differs only in the fingerprint.* This weakens G10: a change to key
  derivation would pass unseen (R-458's second rejected alternative).
- *Re-take now on `main`.* The host can change again before K3. It rebooted on 2026-11-06. The re-take belongs to the
  host that runs C's steps.
- *Re-take with today's `--digest-only` unchanged.* It fails by construction and skips the archive (F7).

## 3. Ruling 2 — step 11's IDAES record

**The `reference_values_yaml_sha256` change is not a real input change and needs no verdict.** It comes from M01
Amendment 1 (F9). The diff only inserts lines, and the script only hashes the file. W22 (b) already admits the member
when it is listed, and M01's manifest gives the reason. On its own this member would not fail `a40.idaes_numbers_identical`.
The check fails on `environment.platform` alone.

**Rule.** The IDAES record falls under the same standing rule as REAL, because step 11 compares its `environment`
exactly. It is re-taken at K3 at every cut, on the RC host, and committed in J.
- **Command**: `<idaes-venv>/bin/python -I benchmarks/m01/idaes_conformance.py --out <dir>/idaes-conformance.json`,
  in the pinned IDAES environment that step 11 uses (`IDAES_DATA` as there).
- **Proof**: `.venv/bin/python scripts/m01_idaes_retake_diff.py benchmarks/m01/idaes-conformance.json
  <dir>/idaes-conformance.json --old-platform '<p>'`. Here p is the committed record's `environment.platform`, and the
  tool is WO-3's. **Must be equal:** every member under `m01_evidence_manifest._differences`, the comparator that step
  11 uses, with two exceptions. `environment.platform` may differ only from p to the running `platform.platform()`.
  An `inputs.*_sha256` member may differ only when its new value is the SHA-256 of its named input file, tracked and
  unmodified at K3.
- **Where it lands**: `benchmarks/m01/idaes-conformance.json` in J's commit. At 0.4.0 the expected differing members are
  exactly `environment.platform` and `inputs.reference_values_yaml_sha256`.
- W22 (b)'s criterion is unchanged. With the record re-taken on the RC host, step 11 at C expects an empty
  `differing_members`.

**Rejected.** *Classify `environment.platform` as host provenance in step 11's comparison*, following the pattern of
R-902. That changes the W22 (b) criterion text, which RP may not change (RP §1 item 3), and it would read as a check
relaxed after a failure. *Re-take only REAL and accept a W22 FAIL with a standing row*: a FAIL whose cause has a
mechanical cure is not a limitation.

## 4. Ruling 3 — the journey J for 0.4

The 0.4 J is recorded at the cut by RP as written, together with A-11. No action is needed before K3 beyond WO-1 to
WO-6.
- J = K3 + §7.1's re-takes: the five, REAL and IDAES. REAL's `provenance.run_commit` is K3, and J differs from K3
  in `benchmarks/m05/**`, so R3 is not carried and re-runs at J. It would re-run anyway, because `src/openflowsheet/**`
  has changed since `cdacc32`. The journey runs at J and is committed under `benchmarks/m07/journey/<J>/`, which gives
  C, and it is carried to C by `--carry-journey J --rc C`.
- The journey's R1 experiments and its R3 re-run are bound to the host's platform (F5). The journey at J and step 15 at
  C therefore run on one host platform (A-11 item 2).
- S-6's `a21.carry_journey` fail was the expected outcome for 0.3.0's J and is not a finding. Its `a21.replay` failure
  is F-B's mechanism (F5), and recording the 0.4 J on the RC host cures it.

## 5. Ruling 4 — Frank

No question for Frank. This is procedure: no criterion, scope or claim changes. One information line goes into the cut
message (RP §8.5), not onto the decision board:

> For information, no decision: at the 0.4.0 cut the workstation re-takes two stored results (the reactor optimisation
> study and the IDAES cross-check), about half an hour of compute. Both record the machine's Linux kernel version, which
> changed at the 6 November reboot. If a re-take changed any number, the cut would stop and come back to the design
> lane.

## 6. RP amendment A-11 (verbatim; added as §17.4 on `wp/REL040p`, after A-10)

> ### 17.4 Amendment A-11 (REL040 S-6 ruling, 2026-11-09)
>
> - **A-11 (§4.5, §5.1, §6.1, §6.5, §7.1, §12, §14; R-1008; `docs/reviews/REL040-s6-ruling.md`).** Records bound to
>   the RC host are re-taken at K3 on that host and committed in J. Nothing else in RP changes.
>   1. §7.1's third bullet ("The five in-process G10 records are re-taken, …") is replaced by:
>      "- The records bound to a version or to the RC host are re-taken at K3, from a clean worktree at K3, on the host
>      that runs steps 11, 14 and 15, and are committed together as J (§4.5). Each re-take is written outside the
>      repository and proved by a committed tool, and it replaces the committed files only after its proof prints
>      `PASS`. The proofs' summary lines go into J's commit message and the build log.
>      - The five in-process G10 records (TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R, LOOP-S), digest-only, proved with
>        `scripts/m05_retake_diff.py --digest-only --old-version <the committed records' version>` (R-458).
>      - M05's REAL record `benchmarks/m05/records/trust-region-study-real.*`, written by `scripts/m05_wo9_real.py
>        --retake-into <dir>` in the audited nlp environment with `OMP_NUM_THREADS=1`. It is proved with
>        `scripts/m05_retake_diff.py --digest-only <committed stem> <dir>/trust-region-study-real --old-platform <p>`,
>        where p is the committed `S0` coupling record's `frozen.reactor.fingerprint.platform`. The proof must print
>        `PASS` with `version=0`, `other=0` and `environment=equal`. Its `platform` count is the number of coupling
>        records when the host's platform string differs from p, and 0 when it is equal (R-1008).
>      - M01's IDAES conformance record `benchmarks/m01/idaes-conformance.json`, written by
>        `benchmarks/m01/idaes_conformance.py --out <dir>/idaes-conformance.json` in the pinned IDAES environment. It is
>        proved with `scripts/m01_idaes_retake_diff.py <committed> <dir>/idaes-conformance.json --old-platform <p>`,
>        where p is the committed record's `environment.platform`. Only `environment.platform` and `inputs.*_sha256`
>        members may differ, and each such input hash must be the SHA-256 of its file at K3 (R-1008).
>
>      The reactor's environment fingerprint (M02 §2.4) holds `platform.platform()`, the kernel release included, and
>      its digest is part of every experiment key (ADR 0036 D8). M05's REAL record therefore replays (step 14) only on
>      the platform it was taken on. Step 11 compares the IDAES record's `environment` exactly (alpha spec §6.2 W22 (b)).
>      A kernel upgrade on the RC host fails steps 11 and 14 until both records are re-taken on it. After the tag
>      (§7.4), only the five are re-taken, because neither of the other two holds the version."
>   2. §4.5: "J is K3 plus the re-taken G10 records (R-458, §7.1)." becomes "J is K3 plus the records re-taken under
>      §7.1 (R-458, R-1008)." §4.5 gains a last paragraph: "The journey at J runs on the host of §7.1's re-takes, and
>      step 15 replays it at C on that host. Its R1 experiments and its R3 re-run are bound to that host's platform
>      string through the reactor's fingerprint, as M05's REAL record is. 0.3.0's journey at `2d945b5d` was recorded on
>      kernel `6.12.111` and does not replay on another kernel (S-6)."
>   3. §5.1, C's bullet: "the re-taken G10 records, whose commit is J (§4.5, R-908)" becomes "the records re-taken
>      under §7.1, whose commit is J (§4.5, R-908, R-1008)".
>   4. §6.5 gains a last paragraph: "`a60.w24.m05_g10_real_replay` also carries `host_platform`, the runner's
>      `platform.platform()`, and `record_platform`, the `frozen.reactor.fingerprint.platform` of the committed REAL
>      record's `S0` coupling record at C. When that record cannot be read, `record_platform` is `null` and the check
>      carries the reason. Neither field is judged, and the pass rule is unchanged. The fields make §12's host-mismatch
>      stop checkable." §6.1 step 15 gains: "`a21.replay` carries `host_platform` and `record_platform` in the same way,
>      read from the `S0` coupling record of the M05 record that the journey's R3 used: `benchmarks/m07/journey/<J>/m05/`
>      for a re-run, `benchmarks/m05/records/` for a carried record."
>   5. §12 gains two stops:
>      "- A §7.1 re-take proof does not print `PASS`. The re-take is not committed, and the cut stops before J.
>      - Step 11, 14 or 15 fails at C while the host's platform differs from the compared record's: step 11's
>        `differing_members` holds `environment.platform`, or a step 14 or 15 check's `host_platform` differs from its
>        `record_platform`. C's records are committed as they are. The remedy is a new J from the same K3 on this host
>        (§7.1's re-takes and the journey) and a new C. A comparison or replay that sets the platform aside is never
>        the remedy (R-1008)."
>   6. §14 gains the row: "| R-1008 | records bound to the RC host re-taken at K3 on that host and committed in J; their
>      proofs; the host-mismatch stop | §7.1, §4.5, §5.1, §12 |".
>
>   Why: at S-6 (`9743871e`), steps 11, 14 and 15 failed only because the workstation's kernel moved from `6.12.111`
>   to `6.12.113` at its 2026-11-06 reboot. The REAL record (taken 2026-10-16) and the IDAES record (2026-10-08) both
>   bind the kernel string, and RP re-took neither.

## 7. Register entry R-1008 (verbatim, on `wp/REL040p` with A-11)

> ## R-1008 — Records bound to the RC host are re-taken at K3 on that host at every cut and committed in J: M05's REAL record (the reactor fingerprint's `platform` is in every experiment key) and M01's IDAES record (step 11 compares its `environment` exactly); each re-take proved by a committed tool; the fingerprint and W22 (b)'s criterion unchanged
>
> | | |
> | --- | --- |
> | Date | 2026-11-09 |
> | Decided by | design lane (`specifier`), REL040 S-6 ruling |
> | Normative text | `docs/reviews/REL040-s6-ruling.md` §2, §3, §8; RP amendment A-11 (§7.1, §4.5, §5.1, §6.1, §6.5, §12, §14) |
> | Evidence | S-6 (`docs/RP_DECISIONS.md` § S-6, `wp/REL040p`); S6dbg F-B (`docs/S6DBG_DECISIONS.md`, `wp/S6dbg`): the live fingerprint digest is `5710568d…` and the recorded one `dfce4150…`. The design lane recomputed `document_sha256` of `S0`'s fingerprint with `6.12.111` → `6.12.113` and got `5710568d…`. Step 11 differs in `environment.platform` and in `inputs.reference_values_yaml_sha256` (M01 Amendment 1, `49e99756`, insertions only, already admitted by W22 (b)). M05 S70: REAL reproduces bitwise on one host in 1454 s |
> | Affected packages | REL040 (the cut), M05 (REAL record, `m05_retake_diff.py`, `m05_wo9_real.py`), M01 (IDAES record, `m01_idaes_retake_diff.py`), M07 (J), RP |
>
> **Decision.** At every cut, M05's REAL record and M01's IDAES conformance record are re-taken at K3 from a clean
> worktree, on the host that runs steps 11, 14 and 15. They are committed in J with the five in-process records. REAL's
> proof is `m05_retake_diff.py --digest-only --old-platform`. It admits the platform leaf only at
> `.frozen.reactor.fingerprint.platform`, bound to its digest, and requires every other fingerprint leaf, the digests
> included, to be equal. It also walks the experiments archive under the digest map. IDAES's proof is
> `m01_idaes_retake_diff.py`. It admits only `environment.platform`, from the committed value to the running host's,
> and input hashes that equal their files at K3. A failed proof stops the cut. A host mismatch at C means a new J and a
> new C.
>
> **Rejected.** *Dropping `platform` from the key-relevant fingerprint*: this changes ADR 0036 D8's key semantics and
> every store, for a 25-minute re-take, as R-458 found for the version. *A replay that ignores the fingerprint*: it
> weakens G10. *Reading `environment.platform` as provenance in step 11*: that changes W22 (b)'s criterion, which RP may
> not do. *A re-take only when the platform differs*: it adds a diagnosis branch to save free compute. *A re-take now on
> `main`*: the host can change again before K3.
>
> **Watch for.** A proof with `other` > 0, meaning a number moved with the host, is a stop for the design lane. So is
> a new RC machine: a changed `machine`, `cpu_model` or `cpu_flags_sha256` fails REAL's proof by design. R-458's watch
> item ("REAL's replay at the new version") is answered: the replay does not depend on the version, and it is bound to
> the host's platform.

## 8. Work order (build lane, `wp/REL040p`)

*Amended by §11 (2026-11-09): WO-1 (b), S6R-10 and S6R-12 to S6R-15 are replaced there; WO-7 and WO-8 and assertions
S6R-26 to S6R-29 are added.*

### 8.0 Tolerance

Every assertion below is exact, whether string equality, bitwise float equality or byte equality. These are identity
proofs. S70 measured that REAL reproduces bitwise on one host (F6), and S-6 measured that the IDAES re-run's numbers
are bitwise equal across the kernel change (F8: no numeric member differs). The roundoff floor of a re-run is therefore
zero differences, and the smallest error worth catching is one ulp in one leaf. No tolerance is introduced (RP §4.1).

### 8.1 Items

Do not spawn sub-agents. WO-1 to WO-4 are code in `scripts/` and `tests/`; `scripts/` is not a D2.4 path. Their tests
run in the default tier unless stated. They touch replay identity, so the package's single `reviewer` pass covers WO-1,
WO-3 and WO-4.

**WO-1 — `scripts/m05_retake_diff.py --digest-only`: a `platform` class and the archive walk** (Opus).
- (a) `--old-platform <p>`. A class `platform` admits exactly one leaf: the coupling records'
  `.frozen.reactor.fingerprint.platform`. It is a constant path, as `VERSION_PATH` is, so it fails closed. On every
  coupling pair whose frozen unit's `fingerprint` has a `platform` member, the committed side must equal p and the
  re-take side must equal the running `platform.platform()`. Without `--old-platform` the two sides must be equal. A
  pair that breaks this is `other`. In such a fingerprint, every leaf other than `platform` must be equal on both sides,
  digests included and not relabelled; a difference is `other`. The binding `fingerprint_sha256 ==
  document_sha256(fingerprint)` must hold on both sides, as for `version`. The same text at any other path is `other`.
  The summary line gains `platform=<n>` after `version=`.
- (b) When either stem has `<stem>.experiments.json`, both must have it; otherwise the difference is `other`. The
  archive is walked after the store index, under the map that the other documents built. A file name's 64-hex key is
  relabelled by that map, and the name's two-character directory becomes the first two characters of the relabelled
  key. A key with no image, or a file without a partner on either side, is `other`. Request and result files are walked
  leaf by leaf, digest leaves into the map and anything else differing as `other`. Attempt files are walked the same
  way, with `TIMING` (including `execution.timing.*`) counted as timing.
- Assertions, in `tests/test_m05_retake_digest_only.py` with the file's synthetic-stem pattern unless named:
  - **S6R-01**: the platform moves P0 → P1, the binding is recomputed and the fingerprint digest is relabelled
    everywhere. With `--old-platform P0` and the running platform patched to P1, the result is `PASS` with `platform` =
    the number of coupling records and `other=0`.
  - **S6R-02**: the same pair without `--old-platform` → `FAIL`, naming the leaf.
  - **S6R-03**: `--old-platform` other than the committed side → `FAIL`.
  - **S6R-04**: the running platform other than the re-take side → `FAIL`.
  - **S6R-05**: the platform moves but `fingerprint_sha256` is kept → `FAIL` (binding).
  - **S6R-06**: the platform moves and `fingerprint.lock_sha256` (and separately `export_tree_sha256`) changes, with
    the binding recomputed → `FAIL`, `other` naming that leaf.
  - **S6R-07**: the platform moves and `fingerprint.python` changes → `FAIL`, `other`.
  - **S6R-08**: the platform string moves at another path (in the record, or in a coupling record outside
    `frozen.reactor.fingerprint`) → `other`.
  - **S6R-09**: archive cases.
    - A consistent key relabelling across names and leaves → `PASS`.
    - One result leaf moved by one ulp → `FAIL`, naming `experiments <name>…`.
    - One archive file missing on the re-take side → `FAIL`.
    - Two committed keys mapped to one → `FAIL`.
    - An attempt differing only in `execution.timing.wall_s` → `PASS`, counted as timing.
  - **S6R-10** (the committed REAL stem): build the re-take side as follows, then expect `PASS` with `version=0`,
    `platform=4`, `other=0` and `environment=equal`:
    - set the four coupling records' platform leaf to the `…6.12.113…` string;
    - recompute `fingerprint_sha256` as F′;
    - replace `dfce4150…` by F′ in every file;
    - relabel every experiment key k as `sha256((k + F′).encode()).hexdigest()` in every file and archive name;
    - set `artifacts.experiment_store` as `m05_wo9_real` computes it over the rewritten archive;
    - patch the running platform to the new string.

    Separately, a byte copy without `--old-platform` → `PASS`, `changed-digests=0`.
  - All existing tests in the file stay unchanged and passing, S77's pair included.

**WO-2 — `scripts/m05_wo9_real.py --retake-into <dir>`** (Opus; the file is in `carry.r3_files`, which J re-runs
anyway).
- A cold run with the default run's settings and refusals writes the record and sidecars as
  `<dir>/trust-region-study-real.*`, never under `benchmarks/`. It uses the `write` path with a stem argument, as
  `compare` has had since R-455. It refuses with exit 2 and the stated reason when `<dir>` resolves inside the
  repository, when `<dir>/trust-region-study-real.json` exists, or when `--replay` is also given. These checks run
  before the run starts.
- **S6R-20**: the three refusals, each with its reason, run in the tier where `tests/test_m05_wo9_gates.py` runs.
- **S6R-21** (live, WO-6): the written file set has the committed names: the record, `.ledger.json`, `.store.json`,
  `.environment.json`, `.experiments.json`, and `.coupling/` with the same four names. `provenance.tree_clean` is
  `true` and `provenance.run_commit` is the worktree's HEAD.

**WO-3 — `scripts/m01_idaes_retake_diff.py <committed> <retake> [--old-platform <p>]`** (Opus).
- The tool computes `differing = sorted(m01_evidence_manifest._differences(committed, retake))`.
- Each member is classified:
  - `environment.platform` is admitted iff `--old-platform` is given, the committed side equals p and the re-take side
    equals the running `platform.platform()`;
  - `inputs.<name>_sha256` is admitted iff `<name>` is `components_yaml` (`benchmarks/m01/components.yaml`) or
    `reference_values_yaml` (`benchmarks/m01/reference_values.yaml`), the re-take value is that file's SHA-256, and
    the file is tracked and unmodified;
  - anything else is `other`.
- It prints one line, `IDAES-RETAKE PASS|FAIL differing=<comma list> platform=<0|1> inputs=<n> other=<n>`, then each
  problem. It exits 0 iff PASS.
- Assertions, in `tests/test_m01_idaes_retake_diff.py`, on copies of the committed record:
  - **S6R-11**: a byte copy, without `--old-platform` → `PASS`, `differing=` empty.
  - **S6R-12**: `environment.platform` set to P1, the running platform patched to P1, and `--old-platform` = the
    committed value → `PASS`, `platform=1`, `other=0`.
  - **S6R-13**: S6R-12 without `--old-platform`, with the running platform ≠ P1, or with `--old-platform` ≠ the
    committed value → `FAIL` in each case.
  - **S6R-14**: `inputs.reference_values_yaml_sha256` set to the tree file's SHA-256 → `PASS`, `inputs=1`. Set to
    `"0"*64` → `FAIL`. An added `inputs.unknown_sha256` → `FAIL`.
  - **S6R-15**: each of these → `FAIL`, `other` naming the member:
    - one float leaf moved by one ulp (`math.nextafter`);
    - `environment.python` changed;
    - `environment.platform` and one number changed together.

**WO-4 — `scripts/release_rc_local.py`: platform fields in steps 14 and 15** (Opus).
- Add A-11 item 4's fields. The check ids and pass rules do not change; RP §6.1 says that a changed id is a line-file
  change.
- Assertions, in `tests/test_rel_rc_local.py`:
  - **S6R-17**: `a60.w24.m05_g10_real_replay` carries `host_platform` = `platform.platform()` and `record_platform` =
    the committed `S0` leaf. Its result follows the replay log alone, in four cases: passing and failing logs, each
    with equal and with unequal platforms.
  - **S6R-18**: `a21.replay` carries both fields. `record_platform` comes from the journey's `m05/` `S0` when that
    exists and from `benchmarks/m05/records/` otherwise. A missing file gives `null` with the reason.
  - **S6R-19**: the existing step 11, 14 and 15 tests stay unchanged and passing.

**WO-5 — documents** (Sonnet).
- Apply §6's A-11 to `docs/derivations/release-procedure.md` on `wp/REL040p`, both §17.4 and the section edits.
- Add §7's R-1008 to `docs/decision-register.md`.
- Append to `docs/RELEASING.md`, after the R-458 sentence (`:196–197`): "At every cut, M05's REAL record and M01's
  IDAES conformance record are also re-taken at K3 on the RC host and committed in J, each proved by its tool, because
  both bind the host's platform string, the kernel release included (RP §7.1, R-1008). A kernel upgrade between J and
  the RC's steps 11, 14 and 15 means a new J and a new C."
- Run `tests/test_rel_release_gate.py`, whose RP-text and §14 checks apply.

**WO-6 — rehearsal of the cure** (Opus; RC host; nothing merged; result logged in `docs/RP_DECISIONS.md`).
- This settles open question O-1. Work from a clean worktree at `wp/REL040p`'s head after WO-1 to WO-5:
  - **S6R-22**: REAL re-take into scratch (WO-2), then the proof with `--old-platform
    'Linux-6.12.111+deb13-amd64-x86_64-with-glibc2.41'` → `RETAKE-DIGEST-ONLY PASS trust-region-study-real: …
    version=0 platform=4 other=0 environment=equal`. Record `changed-digests` and the class counts; they are not
    predicted here.
  - **S6R-23**: IDAES re-take into scratch, then WO-3's proof with the same `--old-platform` → `PASS`, with `differing`
    exactly `environment.platform,inputs.reference_values_yaml_sha256`.
  - **S6R-24**: on a scratch branch J′ (the head plus one commit that copies both re-takes in), run `release_rc.py
    local` steps 11 and 14 as S-6 did. Expect `a40.idaes_numbers_identical` to pass with `differing_members` [], and
    `a60.w24.m05_g10_real_replay` to pass with `REPLAY PASS REAL differences=0` and `host_platform` = `record_platform`.
  - **S6R-25** (negative control): step 14 at the head without the re-takes still fails, now with `host_platform` ≠
    `record_platform`. This shows that the fields detect the stop.
  - Delete J′ afterwards.
- If S6R-22 or S6R-23 fails: stop, do not commit, and report the proof's problem lines to the design lane.

**At the cut**: no extra work order. RP §7.1 as amended applies, with `--old-version 0.4.0.dev0` for the five.

## 9. Open questions, each with a default

*O-1 is answered by the fresh-worktree rerun (§11.0): no REAL or IDAES number moved. O-5 is added in §11.7.*

- **O-1 (needs a fact): does the kernel change move any REAL or IDAES number?** S6R-22 and S6R-23 measure it, and so
  does every later cut's proof. Default: it does not (F6, F8). If it does, the proof stops the cut (A-11 item 5), and
  the design lane rules.
- **O-2 (needs the design lane, not now): should M02 §2.4's key-relevant fingerprint drop the kernel release, by ADR?**
  Default: no. Revisit only if the re-take at K3 becomes impossible on the RC host, or if the RC machine changes. A new
  machine fails REAL's proof on `machine`, `cpu_model` and `cpu_flags_sha256` in any case.
- **O-3 (preference): re-take at every cut, or only when the platform differs?** Default: every cut (§2). Reversible by
  one amendment line.
- **O-4 (preference): a committed driver for REAL's re-take?** Default: yes, WO-2's flag. The five keep E6/K's recipe,
  which this ruling leaves as it is.

## 10. What this ruling does not establish

- It does not establish that the kernel cannot move REAL's or IDAES's numbers in general. Each proof shows equality
  between two specific host states, and nothing more.
- It does not establish that REAL's or IDAES's numbers are right. The re-take proofs are regression identity with the
  committed records. Validity rests on M05's and M01's own evidence.
- The synthetic tests (S6R-01 to S6R-15) test the proof tools' logic. They do not measure a kernel re-take; S6R-22 and
  S6R-23 do.
- It does not establish that steps 12 and 13's records are host-independent. The M02 and M04 files that hold `dfce4150…`
  (F10) stay as they are. They are not replayed against the live reactor, and they passed on `6.12.113`. If a later
  step does replay them, the same binding applies.
- It does not establish that a new RC machine can re-take REAL. That case fails the proof by design (O-2).
- It establishes nothing about F-A, and nothing about whether 0.4.0 passes any gate.

## 11. Confirmation round (Q-S6a–d, D-22), 2026-11-09

Design lane (`specifier`). Brief: `docs/briefs/REL040-s6-confirm.md`. Read at `wp/REL040p` `0282e4d6` and `wp/X04`
`9446a592` (head `0f7d9b87`).

This section amends §8: WO-1 (b), S6R-10, S6R-12 to S6R-15, and §8.0's rule. It also adds A-11 item 7, WO-7, WO-8,
assertions S6R-26 to S6R-29, and one note to ADR 0075. It changes no gate criterion, tolerance, fingerprint, experiment
key or proof pass rule. The only frozen-schema change is the one already made in `9446a592`, which the ADR 0075 note
records (§11.5).

### 11.0 Facts measured for this round

| # | Fact | Source |
| --- | --- | --- |
| G1 | The fresh-worktree rerun produced two passing proofs, so no number moved with the kernel (O-1 is answered). REAL: `RETAKE-DIGEST-ONLY PASS … changed-digests=103 digest=504 timing=528 path=128 version=0 platform=4 other=0 environment=equal`, T* = 653.1500351610193. IDAES: `IDAES-RETAKE PASS differing=environment.platform,inputs.reference_values_yaml_sha256 platform=1 inputs=1 other=0`. | `docs/RP_DECISIONS.md` on `wp/REL040p` (`99ac9e6e`) |
| G2 | Every REAL log digest is the empty-file digest `e3b0c442…b855`, in the committed record and in the rerun's re-take alike. That is 96 in the archive (48 attempts, each with `.execution.logs.stdout_sha256` and `.stderr_sha256`) and 32 in the coupling records. No log digest differs in G1's proof. | design-lane count over `0282e4d6` and the rerun's `wo6-fresh/retake-real` |
| G3 | A scratch J′ was built from `0282e4d6`'s tree with both rerun re-takes copied in. At J′, `tests/test_m05_retake_digest_only.py` passes 35 of 35, and `tests/test_m01_idaes_retake_diff.py` fails 6 of 11: S6R-12, the three S6R-13 cases, S6R-14's tree-file case, and S6R-15's platform-and-number case. At `0282e4d6` alone both modules pass, 46 of 46. The rest of `tests/test_m01*.py` passes at J′. The build lane's J′ (S6R-24) ran only steps 11 and 14, and neither selects the M01 module. | design-lane run: `git archive 0282e4d6` plus the re-takes, in a scratch git repository, with the repository's `.venv` and `PYTHONPATH=src` |
| G4 | The six failures have one cause, in two places. The module pins `P1 = "Linux-6.12.113+deb13-amd64-x86_64-with-glibc2.41"` (`:44`), the platform that J commits, so at J the platform has nothing to move. It also asserts that the committed `inputs.reference_values_yaml_sha256` differs from the tree file's hash (`:98`), and at J the two are equal. | `tests/test_m01_idaes_retake_diff.py` at `0282e4d6` |

### 11.1 Q-S6a: the class `path`, confirmed

**Confirmed**, as built in `81716c0a`. WO-1 (b) as written had a defect in this note. It walked attempt files with
"anything else differing as `other`" and missed that an attempt's log path spells out its experiment key. Every key move
therefore made all 128 log paths `other`, so REAL could never pass. WO-1 (b) gains this last paragraph:

> A string leaf at `.*.execution.logs.relpaths.<name>`, in an archived attempt or a coupling record, is class `path`.
> It is admitted iff two conditions hold once the whole walk is done:
> - every 64-hex run in the committed text is a `<key[:2]>/<key>` store directory whose key has an image under the map;
> - the committed text, with each such directory relabelled as an archive name is (`<image[:2]>/<image>`), equals the
>   re-take text.
>
> Anything else at that path is `other`. The summary line carries `path=<n>` after `timing=`.

- **S6R-26** registers the tests that `81716c0a` added. Every result is exact.
  - `test_log_paths_relabelled_with_their_keys_pass_as_path` → `PASS`, with the leaves counted as `path`.
  - `test_a_log_path_that_is_not_its_relabelled_path_is_other` → `FAIL` with `other` in each of its three cases: the
    directory kept, the text moved, and a key that is not the image.
- A-11's pass rule is unchanged (`PASS`, `version=0`, `other=0`, `environment=equal`). `path` is not part of the rule,
  just as `digest` is not. It is 128 on REAL when the platform moves (S6R-10) and 0 when it does not.
- **Rejected:** *removing the log paths from the walk.* Then 128 leaves would be read by nothing, and a log path that
  named the wrong experiment would pass.

### 11.2 Q-S6b: a clean worktree is a fresh `git worktree add`, confirmed; A-11 item 7

**Confirmed.** This is procedure, so it belongs in RP. The text below is verbatim, for
`docs/derivations/release-procedure.md` on `wp/REL040p`:

- §7.1: the re-take bullet ("The records bound to a version or to the RC host are re-taken at K3, …") gains this text
  after its first sentence:
  "The clean worktree is a new one, made for the cut's re-takes by `git worktree add --detach <path> <K3>`. Before the
  first re-take starts, `git status --porcelain --ignored` in it prints nothing, and the build log records that check.
  A worktree that has held an earlier run, an install or a build is not clean, even when `git status --porcelain`
  prints nothing."
- §17.4: A-11 gains item 7:
  "7. (S-6 confirmation round, 2026-11-09.) §7.1's re-take bullet gains the definition of the clean worktree: a new
  `git worktree add --detach <path> <K3>`, in which `git status --porcelain --ignored` is empty before the first
  re-take, recorded in the build log. Why: at WO-6 a reused worktree held a git-ignored `src/openflowsheet.egg-info`.
  With `PYTHONPATH=src` it added `openflowsheet` to the REAL re-take's environment sidecar (17 → 18 distributions),
  and the proof failed. From a fresh worktree the sidecar was equal."

**Rejected.**
- *Run without `src/` on `PYTHONPATH`.* The re-take would not then run K3's code from the worktree, and the proof would
  establish the identity of some other tree.
- *`git status --porcelain --ignored` alone, on a reused worktree.* It would pass after `git clean -xfd`, but a new
  worktree costs nothing and leaves nothing to judge.

### 11.3 Q-S6c: a child's stderr is part of the identity, confirmed and sharpened (WO-7)

**Confirmed.** A reactor child's log content is evidence of what the attempt did. A warning can be the only trace of a
changed code path whose numbers happen to agree.

Today, however, the proof carries `stdout_sha256` and `stderr_sha256` as *digest* leaves, which are relabelled under
the map. That has two faults:
- **WO-6's failure did not say where it was.** It surfaced as `map: e3b0c442… has two images`, without naming the
  attempt or the leaf.
- **A uniform change would pass.** Suppose every log in the re-take changed to one common content X. Then
  `e3b0c442…` → X is a bijection, and the proof prints `PASS` with the change counted as `digest`.

A log's content is not derived from an experiment key or the fingerprint, so it must be equal, not relabelled. G2 shows
that this changes nothing in G1's passing proof.

**WO-7 (Opus, `wp/REL040p`).** The package's single `reviewer` pass covers it.
- (a) `scripts/m05_retake_diff.py --digest-only` compares a leaf at a path ending `.execution.logs.stdout_sha256` or
  `.execution.logs.stderr_sha256` exactly, before the digest class. Such a leaf never enters the map. A difference is
  `other`, and the problem line names the leaf and both values.
- (b) `scripts/m05_wo9_real.py --retake-into <dir>` copies every non-empty `child.stdout` and `child.stderr` from the
  temporary store before the store is removed. Each goes to `<dir>/child-logs/<its relpath>`, where the relpath is the
  `execution.logs.relpaths` value.
  - The run prints `child-logs kept=<n>`. With n = 0 it makes no directory.
  - `child-logs/` does not match `trust-region-study-real.*`, so it never reaches J.
  - Without `--retake-into`, nothing changes.
- **S6R-27** (`tests/test_m05_retake_digest_only.py`, synthetic stems):
  1. One archived attempt's `stderr_sha256` moves from the empty digest to another value, and everything else is a
     consistent relabelling → `FAIL`, `other=1`, naming `…execution.logs.stderr_sha256`.
  2. The same move in a coupling record's iteration → `FAIL`, `other=1`.
  3. Every log digest on the re-take side moves to one common value → `FAIL`, with `other` equal to the number of
     log-digest leaves. This case is in the list because it discriminates. On stems whose only empty-file digests are
     log digests, the tool at `0282e4d6` admits it as `digest` and passes.
  4. S6R-10's two cases and S77's pair print the same summary lines as before WO-7.
- **S6R-28** (in the tier where `tests/test_m05_wo9_gates.py` runs), on a synthetic store tree:
  - with one empty log and one non-empty log, exactly the non-empty one is copied, to its relpath, and `kept=1` is
    printed;
  - with all logs empty, `kept=0` is printed and no directory is made.
- **Live check** (logged in `docs/RP_DECISIONS.md`): run the amended proof on the rerun's scratch re-take. It must print
  G1's REAL line byte for byte.
- **RP's stop is unchanged** (A-11 item 5), and there is no retry rule. The committed logs are all empty (G2), so a
  non-empty log at K3 fails REAL's proof. The cut stops before J, and the design lane rules with the kept text in hand.

### 11.4 Q-S6d: S6R-10 reads the record's platform, confirmed; WO-3's tests carry the same pin (WO-8)

**Confirmed**, as built in `0282e4d6`. The defect was this note's: S6R-10 named the `…6.12.113…` string as its target,
and that is the platform J commits. S6R-10 is replaced by:

> **S6R-10** (the committed REAL stem). Read p from the `frozen.reactor.fingerprint.platform` leaf of the four coupling
> records, and assert that the four agree. Build the re-take side on a made-up platform P_RETAKE, asserted ≠ p:
> 1. set the four platform leaves to P_RETAKE;
> 2. recompute the fingerprint digest as F′;
> 3. replace the committed fingerprint digest by F′ in every file;
> 4. relabel every experiment key k as `sha256((k + F′).encode()).hexdigest()` in every file and archive name;
> 5. set `artifacts.experiment_store` as `m05_wo9_real` computes it;
> 6. patch the running platform to P_RETAKE.
>
> Then the proof with `--old-platform p` → `PASS` with `path=128 version=0 platform=4 other=0 environment=equal`.
> Separately, a byte copy without `--old-platform` → `PASS` with `changed-digests=0`.

§8.0 gains a rule that applies to every test of the re-take tools: **no assertion may depend on the host or the date at
which a committed record was taken.**
- An old platform or an old input hash is read from the committed record, or set synthetically on the committed side.
- Every new platform is a made-up literal, and the module asserts at import that it differs from the committed one.

**Rejected:** *J updates P0 and P1 with each re-take.* That puts a test edit into every cut's J. A forgotten edit fails
C's step 14 and CI, and the test would go on pinning a fact about the host.

**Finding (G3, G4).** `tests/test_m01_idaes_retake_diff.py` carries the same pin. Any J that commits the IDAES re-take
fails 6 of the module's 11 tests in CI.

**WO-8 (test-only, `wp/REL040p`, before K3).** S6R-12 to S6R-15 are replaced by the same assertions under the new rule:
- P1 and every other platform literal in the module are made-up strings that no host prints, for example
  `Linux-0.0.0-s6r12-retake`. The module asserts at import that each one differs from P0. P0 is still read from the
  record.
- S6R-14's tree-file case sets the committed side's `inputs.reference_values_yaml_sha256` to a made-up stale value,
  asserted ≠ the tree file's SHA-256. It sets the re-take side's to the tree file's SHA-256 → `PASS`, `inputs=1`. The
  assertion at `:98` is removed.
- Every expectation, both PASS/FAIL and summary line, is otherwise as in §8 WO-3.

**S6R-29 (live, after WO-8; logged in `docs/RP_DECISIONS.md`).**
1. Make J′ as S6R-24 did: in a fresh worktree at `wp/REL040p`'s head, add one commit that copies both rerun re-takes
   in.
2. At the head and at J′, `tests/test_m05_retake_digest_only.py` and `tests/test_m01_idaes_retake_diff.py` pass in full,
   with the same number of tests collected at both.
3. At J′, the default-tier pytest selection that `scripts/check.sh` runs has no failure that it does not also have at
   the head.
4. Delete J′ afterwards.

Every comparison is exact: test counts and test ids. The two trees differ only in the committed records, so a test
that depends on them fails at exactly one of the two.

### 11.5 D-22: the catalogue param type `display_unit` needs an ADR 0075 note

**ADR 0075 as written does not cover it.** Three facts:
- `schemas/message-catalogue.schema.json` is a registered schema (ADR 0058; the MSG paragraph of
  `docs/interfaces-frozen.md`). A frozen schema changes only by a design-lane ADR.
- ADR 0075's "Amends (each additive)" list names each schema the ADR widens, and it does not name this one.
- Its Consequences say "No stored datum, fixture or digest moves" and "The MSG slot is filled without changing MSG's
  interfaces". Yet `9446a592` moves the core catalogue's `sha256` in two `message_entry` round-trip fixtures.

**The mechanism itself is right.** It is the narrowest change that implements D7.7. It adds one enum value and leaves
the template grammar untouched, and `{unit!raw}` still gives the D2 spelling. The `!unit` conversion was correctly
rejected. Nothing goes to Frank: D7.7 is his FQ4 answer, and the note changes no decision.

**The note must be in X04's merge.** It is a docs-only commit on `wp/X04` and needs no re-run. The text below is
verbatim.

- ADR 0075, appended to the end of "Amends (each additive)":
  "- *(Note, design lane, 2026-11-09; X04 D-21/D-22.)* `schemas/message-catalogue.schema.json` (ADR 0058,
  `openflowsheet-messages-v1`): the param `type` enum gains `display_unit`, a display unit whose rendered text is
  `units.display.text_unit` of its value (`degF` → `°F`, D7.7); its `!raw` rendering and the param value itself keep
  the D2 spelling. Every existing catalogue stays valid, and MSG's catalogue table (`docs/design/MSG-messages.md`)
  lists the type. `explain`'s `params[].type` is an unconstrained string in
  `application-results.schema.json#/$defs/message_entry`, so no response schema moves. `display_out_of_range` declares
  its `unit` param with this type, so the core catalogue's `sha256` moves, and the two `message_entry` round-trip
  fixtures carry the new value (that member only). The Consequences bullets "No stored datum, fixture or digest moves"
  and "The MSG slot is filled without changing MSG's interfaces" are read with this note. Nothing in a run, bundle,
  manifest or store moves (F0 unchanged)."
- `docs/interfaces-frozen.md`, in the X04 paragraph, after "…`project_summary.ambient_pressure` is required and nullable
  (ADR 0075 D6.3).":
  " `message-catalogue.schema.json`'s param `type` enum gains `display_unit` (ADR 0075 note, X04 D-22); every existing
  catalogue stays valid."

### 11.6 Order of work

On `wp/REL040p`:
1. WO-8, then S6R-29.
2. WO-7, with S6R-27, S6R-28 and the live proof line.
3. A-11 item 7 into RP §7.1 and §17.4, docs only. Then run `tests/test_rel_release_gate.py`, because its RP-text checks
   apply.

On `wp/X04`: the note from §11.5, before the merge.

The package's single `reviewer` pass on `wp/REL040p` covers WO-7 (a) along with WO-1, WO-3 and WO-4. No REAL re-take is
needed before K3.

### 11.7 Open questions, each with a default

- **O-5 (needs a fact): what wrote to stderr in WO-6's first run?** One attempt did, and its startup took 19.7 s
  against 1.7 s. Default: not pursued. It did not recur from a fresh worktree. If it recurs at K3, WO-7 (b) keeps the
  text and the proof stops the cut.
- **O-6 (needs a fact): are other default-tier tests bound to the committed records' host?** S6R-29 measures it.
  Default: none beyond WO-8's module. G3 and the step 14 run at J′ in S6R-24 found no others.

### 11.8 What this round does not establish

- It does not review the code of WO-1 to WO-5. That is the `reviewer` pass's job, and that pass also covers WO-7 (a).
- G3 ran in a scratch git repository without history, where the `test_evidence_manifests.py` "commit exists" cases fail
  for that reason alone. G3 is therefore not default-tier evidence for J. S6R-29 is.
- It does not find the cause of WO-6's stderr (O-5). It does not show that the reactor child never writes to stderr,
  only that the committed record and the rerun have empty logs.
- For D-22 it rules only on whether ADR 0075 covers the change. It does not review X04's code or the fixture re-take.
