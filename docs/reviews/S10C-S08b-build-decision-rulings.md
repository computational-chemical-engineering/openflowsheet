# Ruling round: D1 (S10-C G2), D2 and D3 (T07 THM-09/4 pin): design lane (`verdict`), 2026-10-26

Read-only on `main` at `75b226c6`. These rulings are numerical and procedural. They are not human numerical sign-off.
The next free register ids are **R-795** and **R-796**. The last entry on `main` and on every `wp/*` branch is R-794,
and R-787…R-789 are marked unused.

## D1: S10-C G2 admits three named files. **ACCEPT**, plus a docs-only erratum (WO-D1)

- G2 under S10-C design §6 as written ("empty over `numerics/`"): **not met** at `2aedd250`, because `newton.py` changed (+/−123 lines).
- G2 as amended by R-795: **met**. Outside the three admitted paths the frozen diff is empty, and the edited tests are within
  the allow-list. I checked this myself (`git log 53228775..2aedd250 -- <path>`): exactly three commits touch the admitted
  paths, and each has its authority. `e88f72a9` is WO-R2 (R-782, reviewed in R-783). `f23985bf` is WO-R6 (R-786, proved
  by G-R8 bit identity). `fbba9643` is the T07 per-class pin, ruled in R-796. The one assert those commits remove from a
  test is `assert cap == 10_000`, which R-782's decision text itself orders.
- Reasoning. G2's job is to make sure S10-C changes no frozen code without design-lane authority. R-782 is that authority:
  the note, the amendment to K03 §5.3, R-783 and R-784. Its §4.7 also orders the two test edits. G2's text was written
  before R-782 existed, so it treats an authorised amendment like an unauthorised edit. That is a defect in the registered
  criterion. I record it as a finding and amend G2, as R-784 amended G-R7. This is not a relaxation:
  - the admission names exact files, not a directory;
  - every other frozen path is still checked;
  - the manifest prints the admitted diff (`admitted_by_r782_r786`: 3 files, +148 −65).
- Rejected alternatives:
  - *Leave G2 failing, with the manifest at `implemented`.* G2 could then pass only if R-782 were reverted. A gate that
    can pass only by undoing a registered ruling is mis-specified, not failed. `implemented` would also report a reviewed,
    CI-judged change as unauthorised.
  - *Admit all of `numerics/`.* Any edit outside R-782 would ride in unseen.
- What this does not establish: anything about R-782's numerics (that evidence is R-782–R-786). A by-name admission is not
  a review.
- What would reopen it: a commit touching an admitted path that no register entry authorises, or a regeneration of the
  S10-C manifest at another commit (the commit list must then be checked again). The manifest is **not** regenerated now,
  because its G2 description already discloses the admission.

**WO-D1** (build lane, docs-only, no gate). Under S10C-design §6's G2 row, add: "*(Amended 2026-10-26, R-795.)* G2
admits, by name, `src/openflowsheet/numerics/newton.py`, `tests/test_t06_w20_counters.py` and
`tests/test_t07_interrupt.py` as changed by R-782 (WO-R2 `e88f72a9`), R-786 (WO-R6 `f23985bf`) and R-782 §4.7 item 4
(`fbba9643`). Every other frozen path stays untouched." Then add R-795 below.

## D2: no pin on an unregistered class. **ACCEPT**, with change C1

- G5's record-k leg on an unregistered class: **met by construction**. Interrupt at k, k checks, the trace prefix equals the
  uninterrupted trace, and the RNG is restored, all checked against the machine's own uninterrupted run. For
  interruption semantics, that self-reference *is* the specification. It is not a fixture.
- The length pin there: **not applicable**. No recorded value exists, and T06 §7.5 says an unregistered class is
  "reported, never gated".
- "Reported": **not met today**. A passing run on that path prints nothing. C1 fixes this.
- The length is a self-generated regression fixture (CLAUDE.md). It says nothing about whether interruption is correct.
  `len > max(K)` stays a hard assert on every class, because it is the precondition for every k ∈ K interrupting inside
  the run, which is what G5 registers.
- Rejected alternatives:
  - *Fail on an unregistered class.* This was `fbba9643`'s own alternative. It gates a class nobody could register, and
    contradicts §7.5 and ADR 0007 D3.2 (F1, Frank 2026-09-22: bitwise agreement is reported, never promised).
  - *Skip the leg there.* It removes G5 assertions that are fully valid on that class.

## D3: ci-x86-64 unpinned. **ACCEPT** the unpin, with change C1 (which supersedes `1d4ca814`'s message) and the re-pin rule

- Whether ci-x86-64 is a determinism unit for this trajectory: **not met, measured.** I read this in CI 40359016227 at
  `d34f8b57`; the job logs are in the scratchpad `ci/` directory.
  - `check (ubuntu-latest)` measured **136**: `assert 136 == 94`, `test_t07_interrupt.py:236`.
  - `default-install` was also `ubuntu-latest`, so also ci-x86-64, on the same image (ubuntu-24.04 20261012.334.1). It
    passed the whole suite with the `ci-x86-64: 94` pin in place (12979 passed, and no skip line names the file).
  - So two ci-x86-64 runners disagreed at one commit. The runner varies, not the tree, which also agrees with
    S08-IDENTITY/S10C-IDENTITY PASS and ref-x86-64 94 at the S08b head.
  - That the **CPU model** is what varies is **unproven**: neither job logged it.
- G5 on ci-x86-64 after the unpin: **met** (every assertion still runs, and `> 89` is asserted).
- Accrual of the length and CPU evidence: **not met**. After `f4b5d8dd`, the CPU naming in the failure message can never
  print on ci-x86-64. C1 fixes this.
- **Is unpinning correct?** Yes. A pin that takes two values on one class at one commit pins nothing, and it turns CI red
  by runner lottery. The project already knew this class varies:
  - `ci.yml`'s check-job comment says the x86-64 runners disagree on converged floats (2026-09-21);
  - T08's PTC-R1 diagnostic (CI 36851384496 reproduced 1 of 5 records);
  - ADR 0007 D3.2.

  So `fbba9643`'s `ci-x86-64: 94` entry was the error, and T07-1 corrects it.
- **Should the registry split CI classes by `cpu_model`?** No.
  - T06's classes are registered benchmark identity: A97 (b)/(e), the class recorded in each run record, and the gate's
    class list. Splitting them for a T07 fixture would change T06's registration.
  - The CPU model only stands in for the real cause, and GitHub changes its runner pool without notice.
  - The precedent to follow instead is T08's PTC-R1 diagnostic, which keys bit equality on (class, host `cpu_model`)
    inside the test, with no registry change.
  - **How to measure without a dispatch:** with C1, every push gives two free samples, the `check (ubuntu-latest)` job
    and `default-install`.
- **Print on every run?** Yes. That is C1.
- **Do R-627 or §7.5 already answer this?** Partly:
  - §7.5 settles only the unregistered case. It says nothing on whether a registered class is a determinism unit.
  - R-627 is about S07 A31's property digest, so it does not decide this either. Its "x86-64 stays bitwise" held in the
    same failing job (the S07 step passed 3484). That points at the linear-algebra layer.
- **Hypothesis, not a finding:**
  - 94 goes with OpenBLAS's `Haswell` kernel. Local Zen3 reports `Haswell` for both numpy's and SciPy's libraries; I
    probed this.
  - 136 goes with an AVX-512 kernel on EPYC 9V74 and with NeoverseN2 on aarch64. Zen3 cannot run AVX-512 kernels, so
    note §8's "12 local kernels" never covered that case.
  - C1's core-name fields test this at no cost.
- **Re-pin rule** (this removes the limitation using data, under Frank's directive). A key (ci-x86-64, `cpu_model`, OpenBLAS
  core) gets a test-local pin only when ≥ 2 CI jobs with that key report the same length and none reports another. A
  single contradiction removes the key. Never pin a set of lengths. Each addition is a build decision citing the run ids.
  The registry is unchanged.
- **What would reopen it:** a ci-x86-64 length that differs between two jobs with the same key (then the key is not the
  unit), or ci-aarch64 reporting a second length. ci-aarch64 registers no `cpu_model` either, so the same rule would
  apply to it.
- **What this does not establish:** that THM-09/4 is bitwise stable on ref-x86-64 or ci-aarch64. Those pins rest on one
  host and one runner pool.

**Limitation that travels with the decision** (S08b and the S10-C manifests, release report): "THM-09/4's uncapped record
length is regression-pinned on ref-x86-64 and ci-aarch64 only. On ci-x86-64 and on unregistered classes it is reported,
not pinned. G5's interruption assertions run on every class."

**C1** (build lane; test-only, suitable for Sonnet; no numerics; one isolated commit):
1. In `test_interrupt_at_record_k`, for THM-09 on **every** class and before the pin assert, build exactly one line:
   `T07 THM-09/4 uncapped: machine_class=<ensemble.machine_class()> cpu_model=<generator._cpu_model()>
   openblas_numpy=<core> openblas_scipy=<core> records=<len(ref.lengths)> outcome=<ref.outcome>`. Read each core
   name with `ctypes`, with `restype = c_char_p`:
   - numpy: `numpy.libs/libscipy_openblas64_*.so`, symbol `scipy_openblas_get_corename64_`;
   - SciPy: `scipy.libs/libscipy_openblas*.so`, symbol `scipy_openblas_get_corename`.

   On any failure, write `unknown`. Add no new dependency. Both symbols are verified locally and return `Haswell`.
2. Print the line in the terminal summary of every run, passing or failing. For example, append it to a stash that a
   `pytest_terminal_summary` hook in `tests/conftest.py` prints. CI's `-q` logs of the `check (ubuntu-latest)` and
   `default-install` jobs, and `scripts/gate.sh`'s log, then carry it.
3. Use the same line as the pin assert's message (it replaces `1d4ca814`'s tuple). Leave the pins
   `{"ref-x86-64": 94, "ci-aarch64": 136}` and `> max(K)` unchanged.
4. At each branch merge, copy the CI lines into the repository: a table of run id, job, `cpu_model`, cores and records in
   `docs/t07-measurements.md` § W4b. CI logs expire.

Acceptance:
- Locally, `pytest -q tests/test_t07_interrupt.py -k "record_k and THM"` prints exactly one line with
  `machine_class=ref-x86-64 … records=94` and passes.
- The same command under `GITHUB_ACTIONS=true` prints `machine_class=ci-x86-64` and passes.
- A monkeypatched pin mismatch fails and still prints the line.

## Register entries (append after R-794)

```markdown
## R-795 — S10-C G2 amended: R-782/R-786's three files admitted by name; the literal G2 was not met

| | |
| --- | --- |
| Date | 2026-10-26 |
| Decided by | design lane (`verdict`), ruling round on S10-C/S08b build decisions |
| Normative text | `docs/derivations/S10C-design.md` §6 G2 (amended 2026-10-26) |
| Evidence | `evidence/S10c/2aedd250…/manifest.json` `S10C.G2` (`admitted_by_r782_r786`: 3 files, +148 −65; frozen diff otherwise empty); `git log 53228775..2aedd250` on the three paths = `e88f72a9` (WO-R2, R-783), `f23985bf` (WO-R6, R-786, G-R8), `fbba9643` (R-796) |
| Affected packages | S10-C |

**Decision.**
- G2 admits `numerics/newton.py`, `tests/test_t06_w20_counters.py` and `tests/test_t07_interrupt.py` as changed by those
  three commits. Every other frozen path stays untouched. The S10-C manifest stands at `tested`.
- G2 as written (empty over `numerics/`) was not met. Its text predated R-782 and did not provide for a design-lane
  amendment of K03 inside the package. That is a defect in the criterion, not a failure of the work.

**Rejected alternatives, and why.**
- *G2 failing, manifest `implemented`:* it could pass only by reverting R-782, a registered ruling.
- *Admitting `numerics/` wholesale:* any edit outside R-782 would ride in unseen.

**Watch for.** A by-name admission in any package's gate without a register entry naming the authorising decision and the
commits it covers. A regenerated S10-C manifest without the commit list re-checked.

---

## R-796 — T07 THM-09/4's uncapped length: pinned only on a class shown deterministic; reported on every run

| | |
| --- | --- |
| Date | 2026-10-26 |
| Decided by | design lane (`verdict`), ruling round on S10-C/S08b build decisions |
| Normative text | `tests/test_t07_interrupt.py` (`THM09_RECORDS`, C1's report line); T06 spec §7.5 (A5); ADR 0007 D3.2 |
| Evidence | CI 40359016227 at `d34f8b57`, image ubuntu-24.04 20261012.334.1: `check (ubuntu-latest)` 136, `default-install` (also ci-x86-64) passed with the 94 pin. CI 40295317759 and 40315691647: 94 on ci-x86-64. Local ref-x86-64: 94. ci-aarch64: 136 |
| Affected packages | T07 (G5 record-k leg); S10-C (R-782 §4.7 item 4); S08b (T07-1) |

**Decision.**
- Pins: ref-x86-64 94 and ci-aarch64 136. ci-x86-64 and unregistered classes are not pinned. Every class asserts
  `len > max(K)` and runs every record-k interrupt check against its own uninterrupted run.
- Every run prints class, CPU model, numpy's and SciPy's OpenBLAS core, length and outcome (C1). The CI lines are copied
  into `docs/t07-measurements.md` at each merge.
- Re-pin rule: a key (class, `cpu_model`, OpenBLAS core) is pinned only after ≥ 2 CI jobs with that key agree and none
  disagrees. One contradiction removes it. A set of lengths is never pinned. The T06 registry is unchanged.

**Rejected alternatives, and why.**
- *Keeping `ci-x86-64: 94`:* two ci-x86-64 runners gave 94 and 136 at one commit, so the pin pins nothing.
- *Failing on an unregistered class:* contradicts §7.5 and ADR 0007 D3.2.
- *`cpu_model`-split CI classes in the registry:* changes T06's benchmark identity for a T07 fixture. The CPU model only
  stands in for the cause.
- *Skipping the leg off the pinned classes:* removes G5 assertions that are fully valid there.

**Watch for.**
- A live-trajectory pin keyed on bare ci-x86-64 elsewhere. Pins over committed records, such as A98's `S_first`, are
  unaffected.
- A second length on ci-aarch64, which registers no `cpu_model`.
- A failure message that names the CPU only on a pinned class.
```
