# HOSTMOVE: records and judgements bound to the RC host, after the move from SMM-TRS2 to SMM-TR09 (ruling)

Design lane (`specifier`), 2026-11-11. Read at `wp/V04-after` `c57c2ca0`, whose records are byte-equal to the
`v0.4.0` tag `b6cdf552`. Register: **R-1020** (one entry). RP amendment: **A-13** (§17.6). T06 amendment: **H-1**
(§7.4, applied by WO-H5). Machine-readable inventory of the committed host leaves:
`docs/derivations/scripts/hostmove_host_leaves.py` writes `hostmove_host_leaves.json` (`--check` byte-compares).

## 0. Authority and scope

- This note is the normative text for the host-move rule (§2), rulings 1 to 5 (§3 to §7), RP amendment A-13 (§9),
  register entry R-1020 (§10), T06 amendment H-1 (§7.4), and the behaviour of the work orders WO-H1 to WO-H6 (§11).
- It decides what counts as the same evidence when the host that takes a committed record changes. It is a
  design-lane ruling because it touches replay identity and G10's criterion (CLAUDE.md, the two lanes; RP §7.3;
  R-1008's rejected alternatives).
- It changes none of these:
  - G10's criterion and its replay. `m05_wo8_runs.compare` and AM-23 keep comparing the environment sidecar exactly,
    `machine`, `cpu` and `cpu_count` included;
  - the in-process or the reactor fingerprint (M02 §2.4), any experiment key (ADR 0036 D8), or any store;
  - W22 (b)'s criterion, R-458's rule, R-902, or the pass rules of R-1008's two proofs as far as they go. It adds one
    class beside them;
  - any gate's criterion or tolerance (RP §1 item 3). T06's gate (S ≥ 418 of 440 on the reference class and on
    `ci-aarch64`) and A89's and A90's expected values are unchanged;
  - M03 A41, the audited nlp environment, `docs/m03-ipopt-audit.md` and the committed inventory;
  - any record of 0.4.0 or earlier, and any frozen interface (`docs/interfaces-frozen.md` names none of the files
    touched here).
- R-1008's criteria are kept: no host field is dropped from a fingerprint, no replay sets a fingerprint member aside,
  and no member is read as provenance in a comparison that judges.

## 1. Facts

Every number below was measured for this ruling on SMM-TR09, or is quoted from the record named beside it.

| # | Fact | Source |
| --- | --- | --- |
| H1 | SMM-TR09: `platform.node()` `SMM-TR09`; CPU `AMD Ryzen Threadripper 2950X 16-Core Processor`; `os.cpu_count()` 16; `platform.platform()` `Linux-6.12.86+deb13-amd64-x86_64-with-glibc2.41`; external root `/home/eajfpeters/.cache/openflowsheet/external`. SMM-TRS2, as the committed records hold it: `SMM-TRS2`, `AMD Ryzen Threadripper PRO 5965WX 24-Cores`, 48, `Linux-6.12.113+deb13-amd64-x86_64-with-glibc2.41`, `/home/frankp/.cache/openflowsheet/external`. | host; `hostmove_host_leaves.json` |
| H2 | The five in-process records' only host-identity leaves are their environment sidecars' `machine` (the host name: `platform.node()`, not the architecture), `cpu` and `cpu_count`. The record, ledger, store index and coupling records name neither the CPU nor the host. The five sidecars are equal to each other. Their fingerprint `{kind, boundary_sha256, module, module_sha256, openflowsheet_version}` has no host member (S-6 F4). | `hostmove_host_leaves.json` `m05_in_process`; `scripts/m05_wo8_runs.py:251-271` |
| H3 | The five TR09 re-takes (clean worktree at `b618f2fe`, 2026-11-11, recipe in `docs/RP_DECISIONS.md` from line 646) prove `FAIL` with `other=0`, `platform=0`, `path=0`, and the single reason `environment: differs outside distributions_sha256 (['cpu', 'cpu_count', 'machine'])`. Counts (changed-digests, digest, timing, version): TR-E2 41, 146, 20, 4; TR-E2-FAR 79, 320, 35, 7; TR-E2-FD 70, 215, 20, 4; LOOP-R 91, 285, 26, 3; LOOP-S 37, 124, 20, 4. The re-takes' sidecars hold `SMM-TR09`, the 2950X and 16, and every other key byte-equal to the committed ones (`distributions_sha256` `f775c97d…`, `conda_builds_sha256` `d7a1dc8c…`, `omp_num_threads` `"1"`, the same `python`). So every number of the five reproduces bitwise on the other CPU. | `docs/RP_DECISIONS.md:657-664`; the re-takes' sidecars |
| H4 | `m05_retake_diff._environment` (`:417-445`) admits only `distributions_sha256` beside byte equality. G10's replay (`m05_wo8_runs.compare`, `:500-510`) and AM-23 compare every sidecar key exactly. At `b618f2fe` on TR09, AM-23 fails 5 of 5 against the 0.4.0 records. | code; `docs/RP_DECISIONS.md` |
| H5 | M05's REAL record holds the host in 79 leaves beside R-1008's 4 `platform` leaves: in the four coupling records' `.frozen.reactor.fingerprint`, `cpu_model` (4), `cpu_flags_sha256` (4) and `env_allowlist.NUMBA_CACHE_DIR` (4, the pinned environment's absolute directory under the account's cache, `/home/frankp/…/pymrm-6089593-032a050c6cf3/numba-cache`); every attempt's cheap fingerprint `execution.fingerprint.cpu_model`, 16 in the coupling records' iterations and 48 in the archive; and its sidecar's three keys (3). No committed host string occurs at any other leaf. Each role holds one committed value. | `hostmove_host_leaves.json` `m05_real` (the generator refuses to emit otherwise) |
| H6 | R-1008's REAL proof holds every reactor-fingerprint leaf but `platform` equal (S-6 WO-1 (a)) and requires `environment=equal`. On TR09 it therefore fails by construction on 76 fingerprint leaves and on the sidecar. R-1008's watch item names exactly this ("a new RC machine … fails REAL's proof by design"), and S-6 O-2 deferred it to a change of RC machine. `docs/NEW_HOST_SETUP.md` §6 plans the first TR09 cut with that proof. | R-1008; S-6 ruling §9 O-2, §10 |
| H7 | REAL re-taken on TR09 (clean worktree at `c57c2ca0`, the REL040 recipe, `--retake-into` outside the repository, 2074 s, T* = 653.1500351610193 K). R-1008's proof prints `FAIL … platform=4 other=76 environment=differs`, and every one of its 77 problem lines lies at a registered host-identity path of H5. No number, request, result or log digest differs (§4.3). | this ruling's run |
| H8 | M01's IDAES record names the host only at `environment.platform`, and names no CPU and no host name. Re-taken on TR09 at `c57c2ca0` (`.venv-idaes`, step 11's environment, 7 s) and proved with R-1008's tool: `IDAES-RETAKE PASS differing=environment.platform platform=1 inputs=0 other=0`. | `hostmove_host_leaves.json` `m01_idaes`; this ruling's run |
| H9 | On TR09, `m03_ipopt_inventory.py --env .venv-nlp --check` prints `--check FAILED: … differs in pynumero_asl_lookup_without_pyomo_config_dir`; the committed value is `~/.pyomo/lib/libpynumero_ASL.so`, TR09's is `(none)`. `--workload trsp-exe --check` prints `--check passed: … (G1 PASS … G6 PASS)`. The field is Pyomo's library lookup with `PYOMO_CONFIG_DIR` unset (`default_lookup`, `:444-456`), a function of the account's home directory. The audited route sets `PYOMO_CONFIG_DIR` (`m03_nlp_check.sh`), the adapter refuses a library whose SHA-256 is not the audited `6646bbdd…` (audit §9, WO-8's answer 2), and the route's own lookup (`workload.*.pynumero_asl`) is compared. The comparator already sets `host.libc` and the platform objects' hashes aside, because they belong to "the platform every Python process runs on, not part of the route" (audit §4.1). M03 N1's standing acceptance has scope `paths:docs/m03-ipopt-audit.md,benchmarks/m03/ipopt-inventory-*.json,scripts/build-m03-ipopt-env.sh`. | this ruling's run; code; `release/acceptances.md:34,54` |
| H10 | T06's reference class is defined by one CPU model: `benchmarks/registry.yaml` `ensemble.machine_classes.ref-x86-64.cpu_model` = `AMD Ryzen Threadripper PRO 5965WX 24-Cores`, and T06 spec §7.5 (A5) item 2 names it. On TR09, `ensemble.machine_class()` is `unregistered(x86_64)`. Consequences: RC step 6's `a46.registered_class` fails (`scripts/t08_rc.py:1222-1224`); F0 does not judge M4, judges M6 without the run key trails and M7 without the mode (`scripts/corpus_identity.py:780-797`); the class-conditioned tests report instead of asserting. | code; registry |
| H11 | F0 on TR09 (`cfab93e7`): `F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 NOT JUDGED, M5 61/61, M6 70/70, M7 52/52, M8 105/105, M9 35/35`. F0 on TR09 at `c57c2ca0` with the class reported as `ref-x86-64` (a measurement wrapper, not committed): `F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35`, in 42 s. Every committed `state_sha256`, run key trail and replay mode reproduces bitwise on the 2950X. | `docs/RP_DECISIONS.md` (checks at `cfab93e7`); this ruling's run |
| H12 | The ten modules that condition on the class (`tests/test_t06_w6_generator.py`, `_w18_policy`, `_w28_records`, `_w29_runs`, `_w30_holdout`, `_w31_runs`, `tests/test_t07_interrupt.py`, `tests/test_t08_w1_a89_repeats.py`, `tests/test_t08_w1_records.py`, `tests/test_v02a_r347_machine_class.py`) on TR09 at `c57c2ca0`: as it is, 252 passed, 3 skipped (one of them "generate writes on ref-x86-64 only"); with `generator._cpu_model` reporting the registered model in the test process (a pytest plugin, not committed), so that A25's and A99 (a)'s byte identity, A89's refinement clause, A90's expected counts and W28's host equality are asserted, 252 passed, 2 skipped (both R-150 history), 1 failed. The failure is the measurement's artifact: `test_the_install_check_record_carries_the_machine_class` compares the class its subprocess computes, which the plugin does not reach, with the class the test process computes. | this ruling's run |
| H13 | T06's published starts and holdout record `host.cpu_model` = the registered model, and `python` 3.13.5, `numpy` 2.2.4, `scipy` 1.15.3, which TR09's `.venv` has. | `hostmove_host_leaves.json` `t06` |
| H14 | M04's machine class is `<machine>/<OpenBLAS kernel>`: `x86_64/Haswell` on TR09, equal to its `RECORDED_ON`. | this ruling's run |

## 2. The rule: what counts as the same evidence on another host

**Decision (R-1020).** A committed record taken on host A is replaced by a re-take on host B, and is then the same
evidence, iff a committed proof tool establishes all of these:
1. the re-take was made by the committed writer, from a clean worktree as RP §7.1 defines it, and is written outside
   the repository;
2. every leaf that is not a registered host-identity leaf, a digest, a timing, or a leaf of an already registered
   class (`version` R-458, `platform` R-1008, `path` S-6) is bitwise equal. Every computed quantity is such a leaf:
   **a computed number never moves with the host**;
3. each host-identity leaf of the re-take equals the value that host B measures, read by the same function that
   wrote it, and each such leaf of the committed record holds one value per role;
4. the operator names host A (`--old-host <A>`), and A is the committed record's host name;
5. the digests move by one old-to-new map that is a function and injective, and no host-identity leaf enters that map.

The comparison that the record serves afterwards (G10's replay, step 11, step 14, AM-23) is not changed. It stays exact
on host B.

**The registered host-identity leaves.** This list is closed. A leaf joins it only by a register entry.

| Record | Leaf | Measured on host B by |
| --- | --- | --- |
| each M05 environment sidecar | `machine`, `cpu`, `cpu_count` | `platform.node()`, the first `model name` of `/proc/cpuinfo`, `os.cpu_count()` (`m05_wo8_runs.environment_fingerprint`) |
| a coupling record's reactor fingerprint | `.frozen.reactor.fingerprint.platform` (R-1008's class, unchanged) | `platform.platform()` |
| the same | `.frozen.reactor.fingerprint.cpu_model`, `.frozen.reactor.fingerprint.cpu_flags_sha256` | the child's own `_cpu()` (`src/openflowsheet/adapters/pymrm/child.py:336-350`) |
| the same | `.frozen.reactor.fingerprint.env_allowlist.NUMBA_CACHE_DIR` | `str(external_root() / <env dir> / "numba-cache")`, where the last two path components must be equal on both sides |
| an attempt, in a coupling record or the archive | a leaf at a path ending `.execution.fingerprint.cpu_model` | the child's `_cpu()[0]` |
| M01's IDAES record | `environment.platform` (R-1008, unchanged) | `platform.platform()` |

Two corollaries complete the rule.
- **A judgement conditioned on a registered host property moves only by proof.** It holds on the new host with its
  committed expectation unchanged, or it is not moved. Until it moves, it is reported as not judged, and a procedure
  that needs it stops (§7, RP (P6)). It never lapses silently.
- **Host state that is no part of the evidenced object is recorded and printed, not compared.** That is state of the
  account rather than the machine, outside every environment prefix and the repository (§6).

Why this and not a looser rule. G10 is a same-machine, same-environment criterion (M05 §19.4, S59: thread counts move
the 16th digit). Its evidence is that a replay on the record's host reproduces every number. A host move keeps that
evidence only if the new host reproduces the same numbers, and the proof is where that is shown, once, with every
number compared. After it, the replay is exact again. The host-identity leaves are the only ones a correct re-take on
another machine can change. A leaf outside the list that moves is a finding, not a host move.

## 3. Ruling 1: the five in-process G10 records

**What binds them.** The sidecar's three keys and nothing else (H2). Their numbers reproduce bitwise on TR09 (H3).

**Decision.** The five are re-baselined on TR09 now, at the first change after the tag (RP §7.4), by the re-takes
already taken (H3) and a proof that admits the three sidecar keys (WO-H1, WO-H2). At every later K3 and every later
first change after a tag, the proof always names the committed host, so that a host move needs no separate branch.

**The proof at V04-after** (WO-H2; nlp environment, the re-takes' own environment line):
```
git archive HEAD benchmarks/m05/records | tar -x -C <old>
env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 OMP_NUM_THREADS=1 PYOMO_CONFIG_DIR=<nlp>/share/pyomo \
  PYTHONNOUSERSITE=1 PYTHONPATH=src:<nlp-test-tools> <nlp>/bin/python scripts/m05_retake_diff.py \
  --digest-only <old>/benchmarks/m05/records/trust-region-study-<case> <retakes>/trust-region-study-<case> \
  --old-version 0.4.0 --old-host SMM-TRS2
```
- **May differ:** `machine` `SMM-TRS2` to `SMM-TR09`, `cpu` the 5965WX to the 2950X, `cpu_count` 48 to 16, each equal to
  the running host's value; the coupling records' `openflowsheet_version` 0.4.0 to 0.5.0.dev0 (R-458); digests,
  relabelled one-to-one; timings.
- **Must stay equal:** every other leaf of the record (without `provenance`), the ledger, the coupling records and the
  store index; every other sidecar key, byte for byte (`omp_num_threads`, `python`, `distributions`,
  `distributions_sha256`, `conda_builds`, `conda_builds_sha256`).
- **Pass:** each case prints `RETAKE-DIGEST-ONLY PASS … path=0 version=<v> platform=0 other=0 environment=host host=3`
  with exit 0, and with changed-digests, digest and version equal to H3's (HM-19).
- **Then:** the 36 files replace `benchmarks/m05/records/trust-region-study-{tr-e2,tr-e2-far,tr-e2-fd,loop-r,loop-s}.*`
  in one commit, whose message carries the five lines. AM-23 on TR09 at that commit: 5 passed (HM-20).
- **Not run here:** REAL's replay. REAL's record names SMM-TRS2 and is re-taken at the first TR09 K3 (§4). RP §7.4
  does not ask for it after a tag, and on TR09 it fails by H5 until then.

**At every later K3, and every later first change after a tag.** RP §7.1 as amended: `--old-version <v> --old-host
<h>`, where h is the committed sidecars' `machine`. On an unchanged host the result is `environment=equal` (or
`distributions`) and `host=0`. On a new host it is `environment=host` (or `distributions+host`).

**Rejected.**
- *Drop `machine`, `cpu` or `cpu_count` from the sidecar.* That changes G10's criterion and moves the five's committed
  sidecars. R-1008 rejected the same move for the reactor's `platform`. The host name is what makes G10 a same-machine
  criterion.
- *Compare the sidecar in G10's replay without the host keys, or read them as provenance (R-902's pattern).* That is a
  replay that sets the fingerprint aside, which R-1008 rejected because it weakens G10.
- *Commit the TR09 re-takes without a proof, as a fresh baseline.* Self-generated output then replaces the evidence
  chain, and a number that moved with the host would pass unseen.
- *Admit any value on the re-take side.* A re-take from a third machine could then be committed for this host. The
  re-take side must equal what the running host measures.
- *Give `--old-host` only when the host differs.* That adds a diagnosis branch to save nothing (R-1008's rejected
  alternative for the platform). Named every time, the flag is a cross-check that costs nothing.
- *Keep TRS2's records and run G10 only on TRS2.* TRS2 is retired (Frank, 2026-11-10).

## 4. Ruling 2: M05's REAL record

### 4.1 What binds it, and why R-1008's proof does not cover the move

REAL holds the host in 79 leaves beside the 4 `platform` leaves (H5). R-1008's proof admits only `platform` and
requires `environment=equal` (H6), so it fails on TR09 by construction. The statement that the first TR09 cut handles
REAL is true only once WO-H1 exists. Without it, the first TR09 cut stops at §7.1 (RP §12).

### 4.2 Decision

REAL is re-taken at the first TR09 K3, as R-1008 already requires at every cut, and not before. A re-take on `main` now
is rejected for R-1008's reason: the host can change again before K3, for example by a kernel upgrade. The proof gains
`--old-host`:
```
<nlp>/bin/python scripts/m05_retake_diff.py --digest-only <old>/benchmarks/m05/records/trust-region-study-real \
  <dir>/trust-region-study-real --old-platform '<p>' --old-host SMM-TRS2
```
p is the committed `S0` coupling record's `frozen.reactor.fingerprint.platform`. The proof runs in the re-take's
environment line, so that `external_root()` reads what the re-take read.
- **May differ:** R-1008's `platform` leaves (4); the 79 host-identity leaves of H5, each to the running host's value;
  digests (the fingerprint digest, every experiment key, archive names, the experiment-store digest), one-to-one;
  log paths (`path`); timings.
- **Must stay equal:** every other reactor-fingerprint leaf (`python`, `implementation`, `machine` = `x86_64`,
  `packages`, `thread_env`, every other `env_allowlist` member, `export_tree_sha256`, `merged_database_sha256`,
  `lock_sha256`, `runner_sha256`); every request and result in the archive; every log digest (S-6 WO-7); every other
  leaf of the record, ledger, coupling records and store index; the sidecar's other six keys, byte for byte.
- **Pass:** `RETAKE-DIGEST-ONLY PASS trust-region-study-real: … version=0 platform=4 other=0 environment=host host=79`.
  `host` is 0 on an unchanged host. It counts the admitted leaves that differ and, like `digest` and `path`, is not
  itself part of the pass rule: the tool checks each leaf against the running host.
- Step 14's replay and step 15's journey then run on TR09 against TR09's record, exactly, as R-1008 and A-11 item 2
  require.

### 4.3 Rehearsal (H7)

Measured for this ruling, so that the first TR09 cut does not learn it at K3. REAL was re-taken on TR09 from a clean
worktree at `c57c2ca0` (`git status --porcelain --ignored` 0 lines) with the REL040 recipe. The re-take was proved
with R-1008's tool unchanged, and each of its problem lines was classified by path. The classifier is a scratch
script and is not committed.

- Run: `scripts/m05_wo9_real.py --retake-into <scratch>` exit 0 in 2074 s, `DECISION_STABLE`, T* =
  653.1500351610193 K (the committed value), `study_cold=48`, `bijection_violations=0`, `child-logs kept=0`. Its file
  set equals the committed one, and its sidecar equals the committed one byte for byte outside `machine`, `cpu` and
  `cpu_count`.
- R-1008's proof as it stands (`--digest-only … --old-platform 'Linux-6.12.113+deb13-amd64-x86_64-with-glibc2.41'`),
  run in the re-take's environment line: `RETAKE-DIGEST-ONLY FAIL trust-region-study-real: changed-digests=104
  digest=504 timing=528 path=128 version=0 platform=4 other=76 environment=differs`, with 77 problem lines.
- Every problem line lies at a registered host-identity path: `.frozen.reactor.fingerprint.cpu_model` 4,
  `.cpu_flags_sha256` 4, `.env_allowlist.NUMBA_CACHE_DIR` 4, coupling attempts' `execution.fingerprint.cpu_model` 16,
  archived attempts' `execution.fingerprint.cpu_model` 48, and the one sidecar line `environment: differs outside
  distributions_sha256 (['cpu', 'cpu_count', 'machine'])`. No other leaf differs. The digest map is a function and
  injective, and every request, result and log digest of the 48 experiments is equal. `digest`, `timing` and `path`
  equal REL040's passing line on TRS2 (504, 528, 128).
- So REAL's numbers reproduce bitwise on the 2950X, and WO-H1's class would make this proof pass with `host=79`
  (76 leaves and 3 sidecar keys), as H5 predicts. `changed-digests` is 104 here against REL040's 103. One more digest
  moves because the CPU-flags digest sits under the old tool's map. Under WO-H1 that leaf never enters the map, so
  HM-27 does not predict `changed-digests`.

This is a rehearsal at `c57c2ca0`, not K3's re-take, and nothing from it is committed. K3's proof decides.

### 4.4 Rejected

- *Drop `cpu_model`, `cpu_flags_sha256` or the environment path from the reactor's fingerprint.* That changes M02
  §2.4 and ADR 0036 D8's keys and moves every M02, M04 and M05 store, to save a 35-minute re-take (R-1008's first
  rejected alternative).
- *Point `OPENFLOWSHEET_EXTERNAL_ROOT` on TR09 at `/home/frankp/…`, so that `NUMBA_CACHE_DIR` matches.* A
  fingerprint leaf made equal by imitation hides a real difference, and the CPU leaves would still differ.
- *A replay that serves a request whose key differs only in host leaves.* That weakens G10 (R-458, R-1008).
- *Run the RC on TRS2.* It is retired and resets under load.

## 5. Ruling 3: M01's IDAES record

No change. Its environment names the host only at `environment.platform` (H8), which R-1008's tool admits. Measured
on TR09: `IDAES-RETAKE PASS differing=environment.platform platform=1 inputs=0 other=0`. At the first TR09 K3 it is
re-taken and proved by RP §7.1 as written. `--old-platform` is the committed record's `environment.platform`,
`Linux-6.12.113+deb13-amd64-x86_64-with-glibc2.41` today.

## 6. Ruling 4: the m03 inventory's `pynumero_asl_lookup_without_pyomo_config_dir`

**Decision.** The member is host state. `scripts/m03_ipopt_inventory.py --check` sets it aside, as it sets aside
`host.libc` and the platform objects' hashes, and prints it on every run where it differs, as
`host state (not compared): pynumero_asl_lookup_without_pyomo_config_dir '<committed>' -> '<now>'` (WO-H3). The
record keeps writing it, so its value stays visible. The committed inventory is not re-taken, and no file in M03 N1's
scope changes.

**Why it is host state, by a criterion that can be checked.** Its value is a function of files outside the audited
environment's prefix and outside the repository, namely the account's `~/.pyomo/lib`. Audit §4.1 already classes the
host's C library this way: "the platform every Python process runs on, not part of the route", compared by path and
package only. The route never takes this lookup. It sets `PYOMO_CONFIG_DIR`, its own lookup
(`workload.<order>.pynumero_asl`) stays compared, and the adapter refuses any library whose SHA-256 is not the audited
one (H9). The member records the hazard that motivated those guards. It does not record a property of the audited
environment, and it cannot fail them.

**Rejected.**
- *Re-take the inventory on each host and keep `--check` exact.* The committed inventory is in M03 N1's scope (H9), so
  every re-take lapses Frank's licence acceptance for a change that touches no licence. It also recurs whenever a
  `~/.pyomo/lib` build appears on the RC host or disappears from it, and `pyomo build-extensions` writes there by
  default. It compares a fact outside the audited object.
- *Drop the member from the record.* That changes the record's format and removes the measurement behind audit §2's
  finding.
- *Place an unaudited `libpynumero_ASL.so` in TR09's `~/.pyomo/lib` to match.* That installs the hazard to satisfy a
  check.
- *Run the lookup with `HOME` or `PYOMO_CONFIG_DIR` pinned.* The member exists to measure the unset case.
- *Edit `docs/m03-ipopt-audit.md` to record the classification.* That file is in M03 N1's scope. The classification
  lives in the tool's docstring and in R-1020.

## 7. Ruling 5: T06's reference machine class `ref-x86-64`

### 7.1 What binds it

The class is defined by SMM-TRS2's CPU model (H10). On TR09 it is `unregistered(x86_64)`. Three things follow:
- RC step 6's `a46.registered_class` fails at the first TR09 cut;
- F0, the post-merge check on `main`, stops judging M4 and parts of M6 and M7. It still prints `PASS` (H11);
- A25, A99 (a), A89's refinement clause, A90's expected counts and W28's host check report instead of asserting
  (H12).

The second and third are judgements lapsing silently on the new host. The second has already happened at
`cfab93e7`.

### 7.2 Decision

SMM-TR09's CPU joins `ref-x86-64` by T06 amendment H-1 (§7.4): the registry's single `cpu_model` becomes the list
`cpu_models`, with the 5965WX first and the 2950X second. Wherever T06 compares host blocks to decide that a
regeneration must be byte-identical, it compares them by class. The two blocks are equal in every member but
`cpu_model`, and both models are listed. The class is not moved and not renamed. The 5965WX stays listed because the
committed starts, holdout and run files name it under `ref-x86-64`.

The admission rests on a measurement, not on an assumption. On TR09, every judgement conditioned on the class holds
with its committed expectation unchanged: F0's M4, M6 trails and M7 modes (H11), and A25, A99 (a), A89, A90 and W28
(H12). WO-H5's proof repeats these measurements through the real code path and adds RC step 6's ensemble leg.

### 7.3 The proof (WO-H5)

On TR09, at the commit that applies H-1, without any measurement wrapper:
1. the ten modules of H12 give 0 failed and exactly 2 skipped, both R-150 history. No skip or early return
   conditioned on the reference class remains (HM-36);
2. `scripts/corpus_identity.py --check` prints `F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85,
   M7 52/52, M8 105/105, M9 35/35`. If `benchmarks/f0/corpus.json` has changed since `c57c2ca0`, every measure prints
   `PASS`, with M4 judged (HM-37);
3. `scripts/t06_ensemble.py check` and `check --holdout` print the new identical-but-for-`host.cpu_model` line and exit
   0 (HM-34);
4. `scripts/t08_rc.py ensemble --out <scratch>` writes `rc-ensemble-ref-x86-64.json` with every check `pass`:
   `a46.registered_class`, `a46.run_and_report`, `a46.gate`, `a47.no_verified_outside_s3`,
   `a34.ensemble_certificates`, `a46.t06_a34_same_class_replay` and `a46.registered_runs_untouched` (HM-38).

Any failure stops WO-H5 for the design lane, with the failing assertion and its values. The class does not move, and
no expectation is edited.

### 7.4 T06 amendment H-1 (verbatim, for `docs/derivations/T06-corpus-spec.md`, applied by WO-H5)

> **Amended 2026-11-11 (Amendment H-1, R-1020)**: the reference machine class lists its CPU models. SMM-TRS2, the
> reference host, is retired (Frank, 2026-11-10), and release cuts move to SMM-TR09. On SMM-TR09 every judgement
> conditioned on `ref-x86-64` was measured to hold with its committed expectation unchanged
> (`docs/reviews/HOSTMOVE-ruling.md` H11, H12, §7.3). Nothing that scores a start changes. No registered value, starts
> file or run file changes, and `generator.py` is not touched.
> 1. §7.5 (A5) item 2 reads: "Otherwise the class is `ref-x86-64` iff `platform.machine()` is `x86_64` and the CPU
>    model (`/proc/cpuinfo`'s `model name`, read as `generator._cpu_model` reads it) is one of the registry's
>    `ensemble.machine_classes.ref-x86-64.cpu_models`: `AMD Ryzen Threadripper PRO 5965WX 24-Cores` (SMM-TRS2, where
>    the published starts and the holdout were generated and the local legs of the committed runs were scored) and `AMD Ryzen Threadripper 2950X 16-Core Processor` (SMM-TR09, R-1020). A CPU model joins the list only by
>    R-1020's proof: every judgement this specification conditions on `ref-x86-64` holds on it with its committed
>    expectation unchanged."
> 2. §6.5's "`--check` regenerates on the reference machine class and must reproduce the file byte for byte", A25 and
>    A99 (a) read: on `ref-x86-64`, the regenerated document, with its `host.cpu_model` replaced by the published
>    file's, is the published file byte for byte. Every other member of `host` is compared. Any other difference on
>    `ref-x86-64` is a defect. On another class the report is unchanged.
> 3. A89's (T08-1) "the registered `ref-x86-64` CPU model" reads "a listed `ref-x86-64` CPU model". A90's "Expected on
>    `ref-x86-64`" holds on every listed model.
> 4. A98 (b)'s "the same machine and the same numerics" describes run 2r on SMM-TRS2. Run 2r is a committed record and
>    is not re-run.

### 7.5 Rejected

- *Replace the 5965WX by the 2950X.* The committed starts, holdout and local run files name the 5965WX under
  `ref-x86-64`. The registry would then disagree with them, and A97 (e) reads that pairing.
- *Register a new class (`ref2-x86-64`) for TR09.* Every text that names the reference class would need re-pointing:
  ADR 0014's gate, T08.A46, RP §6.1, and F0's `reference_platform`. A25, A89, A90 and F0's M4 would never be judged
  again on any running host.
- *Drop the CPU condition, so that any local x86-64 machine is the reference.* That admits machines without proof.
- *Leave TR09 unregistered.* Step 6 fails at the first TR09 cut, and F0 and five T06 assertions stay silently
  weakened.
- *Rewrite the published files' `host.cpu_model`.* The starts are generated once and never edited (§6.5). A
  re-emission is admitted only for a moved provider identity (A3).

## 8. Bindings examined and found not to need a change

- **M07's journey.** It is recorded at each cut's J on the host of §7.1's re-takes and replayed by step 15 on that host
  (A-11 item 2). The first TR09 J is recorded on TR09. The committed journeys are archival.
- **The M02 and M04 files that hold TRS2's reactor-fingerprint digest** (S-6 F10). Step 12 reads them by SHA-256
  (A-5) and never replays them against the live reactor.
- **`tests/test_m02_pymrm_env.py`'s A47 (a).** It skips with a registered reason on another environment block, by
  design ("M01.A47 (b) decides").
- **M04's machine class.** It is equal on both hosts (H14).
- **OPT-A2's replay fixtures** (`os_release` 6.12.113 in their run manifests). The R1 replay does not compare it, and
  the full gate passed on TR09.
- **G11's `cpu_count` and T08 v19's `c1-reactor.json` host block.** They are descriptive. Their tests read the
  committed record and run nothing live.
- **The W27 archive.** It is input data, identified by its SHA-256, which was verified on TR09.
- **Records under `evidence/**`.** They are archival. No step replays them.
- **The platform literals in `tests/test_m05_retake_digest_only.py` and `tests/test_rel_rc_local.py`.** They are
  synthetic, and the running platform is patched (S-6 §11.4's rule).

## 9. RP amendment A-13 (verbatim; added as §17.6, with the section edits it names)

> ### 17.6 Amendment A-13 (HOSTMOVE ruling, 2026-11-11)
>
> - **A-13 (§5.3, §7.1, §7.4, §12, §14; R-1020; `docs/reviews/HOSTMOVE-ruling.md`).** A move of the RC host to
>   another machine is a re-take with proof. A host joins T06's reference class only by proof. Nothing else in RP
>   changes.
>   1. §7.1, the five's sub-bullet: "proved with `scripts/m05_retake_diff.py --digest-only --old-version <the
>      committed records' version>` (R-458)" becomes "proved with `scripts/m05_retake_diff.py --digest-only
>      --old-version <the committed records' version> --old-host <h>` (R-458, R-1020), where h is the committed
>      environment sidecars' `machine`. The proof must print `PASS` with `platform=0` and `other=0`."
>   2. §7.1, REAL's sub-bullet: "`--old-platform <p>`" becomes "`--old-platform <p> --old-host <h>`", with "and h is as above" added to the sentence that defines p, and
>      "with `version=0`, `other=0` and `environment=equal`" becomes "with `version=0`, `other=0` and `environment`
>      `equal` or `host`".
>   3. §7.1's paragraph after the bullets gains, after its fourth sentence: "The reactor's fingerprint also holds the
>      host's CPU model, the digest of its CPU flags and the pinned environment's absolute directory
>      (`env_allowlist.NUMBA_CACHE_DIR`), and each attempt's cheap fingerprint holds the CPU model. Each M05 record's
>      environment sidecar holds the host name, the CPU model and the CPU count. These, with the platform strings, are
>      R-1020's host-identity leaves. `--old-host` admits exactly them, each from its committed value to the value the
>      running host measures, together with the digests they feed under the one-to-one map. Every other leaf, every
>      number included, stays bitwise equal. A move of the RC host to another machine is therefore a re-take at K3
>      like any other, and a re-take whose numbers move with the host stops the cut (§12)."
>   4. §7.4's third bullet: "it re-takes the five in-process G10 records (R-458)." becomes "it re-takes the five
>      in-process G10 records (R-458), proved as §7.1 states, with `--old-host` (R-1020)."
>   5. §5.3 gains: "(P6) The host that takes §7.1's re-takes, and runs steps 6, 11, 14 and 15, is a member of T06's
>      `ref-x86-64`: `t08_rc.machine_class()` prints `ref-x86-64` there. A host joins the class only by R-1020's
>      proof (`docs/reviews/HOSTMOVE-ruling.md` §7). Otherwise step 6's `a46.registered_class` fails at C, and F0
>      does not judge M4 there."
>   6. §12 gains: "- (P6) does not hold at K3: the RC host is not a member of `ref-x86-64`. The cut stops before J (R-1020)."
>   7. §14 gains the row: "| R-1020 | a move of the RC host: host-identity leaves admitted by `--old-host` in §7.1's
>      proofs; the RC host a member of `ref-x86-64` before K3 | §7.1, §7.4, §5.3, §12 |".
>
>   Unchanged: R-1008's IDAES proof and §6.5's inventory rule. The inventory tool's comparator changes by R-1020
>   (WO-H3), not by RP.
>
>   Why: development moved permanently from SMM-TRS2 to SMM-TR09 on 2026-11-10 (Frank). The five in-process records
>   failed their after-tag proof on TR09 only in the sidecar's host name, CPU model and CPU count, with `other=0`.
>   REAL holds the CPU model, the CPU flags and the environment path in 76 fingerprint leaves, which R-1008's proof
>   holds equal. T06's reference class names TRS2's CPU model, so on TR09 step 6 fails and F0 stops judging M4.

## 10. Register entry R-1020

R-1020 is appended to `docs/decision-register.md` in the same commit as this note. Its text is not repeated here, so
that there are not two copies to drift apart. It is R-1020 because R-1017 to R-1019 lie in X04's reserved block
R-1010…1019 (`docs/roadmap/decisions.md`), and no other block names R-1020.

## 11. Work orders and numbered assertions

### 11.0 Rules for every test of these work orders

- S-6 §11.4's rule holds: no assertion depends on the host or on the date at which a committed record was taken. A
  committed host value is read from the record, or set synthetically on the committed side. Every new host value is a
  made-up literal, for example `host-hm02`, `cpu-hm02` or `Linux-0.0.0-hm10`. The module asserts at import that each
  literal differs from the committed values and from the running host's values.
- The running host's values are read through one function per tool, which the tests patch. A test never reads
  `/proc/cpuinfo`.
- Every existing test of a touched module stays unchanged and passing, unless a work order below names it.
- Branch: `wp/V04-after`, in the order WO-H1, WO-H2, WO-H3, WO-H5, WO-H6. The package's single `reviewer` pass covers
  WO-H1, WO-H3 and WO-H5. WO-H4 is part of the first TR09 cut.

### WO-H1: `scripts/m05_retake_diff.py --digest-only --old-host <h>`, the `host` class (Opus)

- (a) **Running values.** `tests/support/m05_replay.py` gains `host_identity() -> dict[str, Any]`, which returns
  `{"machine": platform.node(), "cpu": <the first "model name" of /proc/cpuinfo, or None>, "cpu_count":
  os.cpu_count()}`, in that order. `_cpu_model` moves there from `scripts/m05_wo8_runs.py`.
  `m05_wo8_runs.environment_fingerprint()` builds its last three members from `host_identity()`, so its output is
  unchanged. The proof reads every running value through one function, `_running_host()`: the three sidecar values
  from `host_identity()`, `cpu_model` and `cpu_flags_sha256` from `_cpu()` of
  `src/openflowsheet/adapters/pymrm/child.py` (loaded by file path; it imports no `openflowsheet` module), and the
  environment root from `openflowsheet.adapters.experiments.backends.external_root()`.
- (b) **The sidecar.** With `--old-host h`:
  - the committed sidecar's `machine` must equal h, also when the bytes are equal;
  - the differing keys must lie in `{distributions_sha256} ∪ {machine, cpu, cpu_count}`, with both key lists equal and
    in the same order;
  - if a host key differs, all three re-take values must equal `_running_host()`'s, and the re-take bytes must equal
    `json.dumps({**committed, **{k: retake[k] for k in differing}}, indent=1) + "\n"`. The committed bytes must equal
    `json.dumps(committed, indent=1) + "\n"`;
  - `distributions_sha256` keeps today's rule.

  The result is `equal`, `distributions`, `host` or `distributions+host`. Without `--old-host`, the behaviour and
  every printed line are those of the tool at `c57c2ca0`.
- (c) **The reactor fingerprint**, on the coupling pairs that hold `PLATFORM_PATH`. With `--old-host`, these three
  leaves are class `host`. Each is compared before the digest class and never enters the map:
  - `cpu_model`: the re-take side equals `_cpu()[0]`;
  - `cpu_flags_sha256`: the re-take side equals `_cpu()[1]`;
  - `env_allowlist.NUMBA_CACHE_DIR`: both sides have the same last two path components, and the re-take side equals
    `str(external_root() / <those two components>)`.

  Across all pairs, each committed role holds one value. Without `--old-host` the three are held equal, as today. The
  binding `fingerprint_sha256 == document_sha256(fingerprint)` holds on both sides, as today, and every other
  fingerprint leaf stays equal.
- (d) **Attempts.** With `--old-host`, a leaf at a path ending `.execution.fingerprint.cpu_model` is class `host`
  wherever it is walked: in a coupling record's iterations or in an archived attempt. Its committed side equals the
  committed reactor `cpu_model`, and its re-take side equals `_cpu()[0]`. Without `--old-host` it is compared as
  today.
- (e) **Summary.** With `--old-host`, the line gains ` host=<n>` after `environment=<e>`. n counts the differing
  leaves admitted by (b) to (d). Without it, the line is byte-identical to today's.
- (f) A-11's N-3 rule is unchanged: `--old-version` is refused beside the platform. For REAL, `environment` is
  therefore `equal` or `host`.

Assertions, in `tests/test_m05_retake_digest_only.py`, on synthetic stems in the file's pattern:
- **HM-01**: `environment_fingerprint()`'s key list is SIDECAR_KEYS of `hostmove_host_leaves.py`, in that order, and
  its last three values are `host_identity()`'s. This runs where `tests/test_m05_wo8_gates.py` runs, or in the nlp tier
  if `m05_wo8_runs` does not import in the default environment.
- **HM-02**: an in-process pair whose sidecars differ only in the three host keys, the running host patched to the
  re-take side, `--old-host` the committed `machine` → `PASS`, `environment=host`, `host=3`. Every other count equals
  the same pair without the move.
- **HM-03**: HM-02 without `--old-host` → `FAIL`. The summary line and the line `environment: differs outside
  distributions_sha256 (['cpu', 'cpu_count', 'machine'])` are byte-identical to the tool's at `c57c2ca0`.
- **HM-04**: `--old-host` other than the committed `machine` → `FAIL`, and the problem names both values. The same holds
  for byte-equal sidecars.
- **HM-05**: the running host patched so that one of the three values differs from the re-take side → `FAIL`. Three
  cases, one per key.
- **HM-06**: HM-02 with one more differing key → `FAIL`, `environment=differs`, naming the key. Five cases:
  `omp_num_threads` `"1"` → `"2"`, `python`, `distributions`, `conda_builds`, `conda_builds_sha256`.
- **HM-07**: host keys and `distributions_sha256` differ. With `_distributions_sha256` patched to reproduce the
  committed value → `PASS`, `environment=distributions+host`. With it patched not to → `FAIL`.
- **HM-08**: the re-take sidecar holds the right host values, but its bytes are not the writer's (indent 2, or two
  keys swapped) → `FAIL`.
- **HM-09**: byte-equal sidecars with `--old-host` equal to the committed `machine` → `PASS`, `environment=equal`,
  `host=0`.
- **HM-10**: a REAL-like pair, built with S6R-01's synthetic reactor. Between the two sides, `platform`, `cpu_model`,
  `cpu_flags_sha256` and the `NUMBA_CACHE_DIR` root move in every coupling record's frozen fingerprint, and every
  `execution.fingerprint.cpu_model` moves, in coupling iterations and archived attempts. The sidecar's host keys move.
  Bindings are recomputed, the fingerprint digest and every key are relabelled, and `_running_host()` and
  `platform.platform()` are patched. Expected: `PASS`, `platform=<coupling count>`, `other=0`, `environment=host`, and
  `host` = the number of host leaves that the test counts on its own stems.
- **HM-11**: HM-10 without `--old-host` → `FAIL`, with `other` naming `cpu_model`, `cpu_flags_sha256` and
  `NUMBA_CACHE_DIR` leaves.
- **HM-12**: HM-10 with the `NUMBA_CACHE_DIR` environment directory changed (`pymrm-…-<another lock>`) → `FAIL`.
- **HM-13**: HM-10 with one archived attempt's re-take `cpu_model` other than the running one → `FAIL`. Separately,
  with one committed attempt's `cpu_model` other than the committed frozen value → `FAIL`.
- **HM-14**: HM-10 plus one change, with the binding recomputed, of `lock_sha256`, `python`, one `packages` member or
  `thread_env.OMP_NUM_THREADS` → `FAIL`, `other` naming it. Four cases.
- **HM-15**: HM-10 with `cpu_flags_sha256` moved and `fingerprint_sha256` kept → `FAIL` (the binding).
- **HM-16**: HM-10 plus one archived result float moved by one ulp (`math.nextafter`) → `FAIL`, naming the leaf. The
  rule exists for this case: a number never moves with the host.
- **HM-17**: HM-10 with the made-up CPU model also written into the record at a path outside the fingerprints and the
  sidecar → `FAIL`, `other`.
- **HM-18**: every existing test in the module passes unchanged. S6R-10's two cases and S77's pair print the same
  summary lines as at `c57c2ca0`.

### WO-H2: the five, re-baselined on TR09 and committed (V04-after; Sonnet, TR09)

- Use the re-takes of H3, if they are still in the session scratch with their recipe. Otherwise re-take them by that
  recipe from a new clean worktree at the branch head, and record the `git status --porcelain --ignored` check in the
  build log.
- Run §3's proof with the tool at WO-H1, from `git archive HEAD benchmarks/m05/records`.
- **HM-19** (live): five lines `RETAKE-DIGEST-ONLY PASS trust-region-study-<case>: changed-digests=<c> digest=<d>
  timing=<t> path=0 version=<v> platform=0 other=0 environment=host host=3`, each with exit 0. (c, d, v) is (41, 146,
  4) for TR-E2, (79, 320, 7) for TR-E2-FAR, (70, 215, 4) for TR-E2-FD, (91, 285, 3) for LOOP-R and (37, 124, 4) for
  LOOP-S. On H3's files t is H3's. On new re-takes t is recorded and not predicted.

  Why these counts must reappear: WO-H1 changes only the sidecar's classification. The walk over record, ledger,
  coupling records and store index is unchanged, and its counts are deterministic for fixed files. They are regression
  values, measured by the tool itself (H3), and are not an independent expectation of the numbers. The independent
  part is `other=0`: every non-digest leaf is bitwise equal to the 0.4.0 records.
- Copy the 36 files over the five stems in one commit, whose message holds the five lines.
- **HM-20** (live): at that commit on TR09, `-m nlp tests/test_m05_g10_replay.py` in `.venv-nlp` (OMP 1,
  `PYOMO_CONFIG_DIR`, `PYTHONNOUSERSITE=1`, the nlp-test-tools) → 5 passed. At its parent the same command → 5 failed,
  each naming an `environment` difference (the control).
- **HM-21** (live): at that commit, `tests/test_m05_wo8_gates.py` and the M05 record tests of the default tier pass.
  `git diff --name-only HEAD~1 HEAD` lists only files under `benchmarks/m05/records/trust-region-study-{tr-e2,
  tr-e2-far,tr-e2-fd,loop-r,loop-s}.*`.

### WO-H3: the inventory's host state (Sonnet)

- In `scripts/m03_ipopt_inventory.py`, `_comparable` sets aside `pynumero_asl_lookup_without_pyomo_config_dir`, as it
  sets aside `host.libc`. `--check` prints `host state (not compared): pynumero_asl_lookup_without_pyomo_config_dir
  '<committed>' -> '<now>'` when the two differ, and nothing when they are equal. The record still writes the member.
  The module docstring states the class and cites R-1020.
- Do not edit `docs/m03-ipopt-audit.md`, `benchmarks/m03/ipopt-inventory-*.json` or `scripts/build-m03-ipopt-env.sh`.
  They are M03 N1's scope.
- Assertions, in a new default-tier module `tests/test_m03_inventory_host_state.py`, which loads the script as
  `tests/test_m03_nlp_greybox.py` does, on copies of the committed inventory:
  - **HM-22**: two records that differ only in the member compare equal under `_comparable`, and `--check`'s printing
    function emits the host-state line with both values;
  - **HM-23** (control): two records that differ in `workload.<order>.pynumero_asl` compare unequal;
  - **HM-24** (control): two records that differ in `host.machine` compare unequal, and two that differ in `host.libc`
    compare equal, as today.
- **HM-25** (live, TR09): `scripts/m03_nlp_check.sh` with its inventory checks exits 0. The NLP-1 output holds
  `host state (not compared): pynumero_asl_lookup_without_pyomo_config_dir '~/.pyomo/lib/libpynumero_ASL.so' ->
  '(none)'`.
- **HM-26**: `git diff --quiet c57c2ca0 HEAD -- docs/m03-ipopt-audit.md benchmarks/m03/ scripts/build-m03-ipopt-env.sh`
  exits 0, so M03 N1's fingerprint is unchanged.

### WO-H4: REAL and IDAES at the first TR09 K3 (the cut; no new code)

- RP §7.1 as amended by A-13, with `--old-host SMM-TRS2` for REAL and `--old-platform
  'Linux-6.12.113+deb13-amd64-x86_64-with-glibc2.41'` for both.
- **HM-27**: REAL → `RETAKE-DIGEST-ONLY PASS trust-region-study-real: … version=0 platform=4 other=0 environment=host
  host=79`. 79 and 4 are `hostmove_host_leaves.json`'s `host_leaves_if_every_host_value_moves` and `platform_leaves`.
  They hold when the K3 host's CPU model, CPU flags, environment root, host name and platform all differ from TRS2's,
  as they do on TR09 (H1).
- **HM-28**: IDAES → `IDAES-RETAKE PASS differing=environment.platform platform=1 inputs=0 other=0`. If an input file
  changed after `c57c2ca0`, `inputs` counts it and its hash must be the file's at K3 (R-1008).
- **HM-29**: at C, step 14's `a60.w24.m05_g10_real_replay` passes with `host_platform` = `record_platform`, and step
  15's `a21.replay` passes.
- If HM-27 fails with `other` > 0, that is RP §12's stop. The design lane rules with the proof's lines in hand (§13
  O-H1).

### WO-H5: T06's reference class (Opus; design-adjacent, reviewed)

- `benchmarks/registry.yaml`: `ensemble.machine_classes.ref-x86-64` loses `cpu_model` and gains `cpu_models:
  [AMD Ryzen Threadripper PRO 5965WX 24-Cores, AMD Ryzen Threadripper 2950X 16-Core Processor]`.
- `benchmarks/t06/ensemble.py`: `machine_class()` tests membership. One helper decides "same reference host":
  `same_class_host(a, b)` is true iff the two host blocks are equal in every member but `cpu_model`, and both models are
  listed for `ref-x86-64`. `scripts/t06_ensemble.py check` uses it in place of `regenerated["host"] ==
  recorded["host"]`. On `ref-x86-64` it compares the regenerated document, with `host.cpu_model` set to the
  published one, byte for byte, and exits 1 on any difference. It prints `identical but for host.cpu_model
  (<regenerated model>)` when only that member differs.
- Tests that change with H-1, and only these:
  - `tests/test_t06_w6_generator.py::test_a25…` and `tests/test_t06_w30_holdout.py::test_a99a…`: the byte identity on
    `ref-x86-64`, with `host.cpu_model` replaced;
  - `tests/test_t06_w28_records.py::test_a97b…`: `cpu_models` pinned to the two models in order, and `host` equal to
    the published one but for a listed `cpu_model`;
  - `tests/test_t06_w28_records.py`'s `machine_class` cases, which gain the 2950X → `ref-x86-64`;
  - `tests/test_t06_w18_policy.py::_on_the_reference_cpu`: membership;
  - `tests/test_t06_w29_runs.py:113`: the local v1 run's `cpu_model` is a listed model.
- Apply §7.4's H-1 to `docs/derivations/T06-corpus-spec.md` in Amendment T08-1's form: a last section `## Amendment
  H-1 (2026-11-11): the reference class lists its CPU models`, with the Author, Authority and Changes lines and §7.4's
  text; then the four edits in §6.5, §7.5 (A5), A25, A89 and A99, each marked **(H-1)**.
- Assertions:
  - **HM-30**: the registry entry is exactly the two models in that order, with no `cpu_model` key;
  - **HM-31**: `machine_class()` with `generator._cpu_model` patched: each listed model → `ref-x86-64`; a made-up model
    → `unregistered(x86_64)`; the CI cases unchanged;
  - **HM-32**: `same_class_host`: equal blocks → true; blocks that differ only in `cpu_model`, both listed → true; one
    model not listed → false; `numpy` differs → false;
  - **HM-33**: `t06_ensemble.py check` on a synthetic published document whose one other member differs (a start's
    `u` by one ulp) on `ref-x86-64` → exit 1;
  - **HM-34** (live, TR09): `scripts/t06_ensemble.py check` and `check --holdout` → exit 0, each printing the
    identical-but-for line with the 2950X;
  - **HM-35** (live, TR09, the control showing that the class still separates): with `generator._cpu_model` patched
    to a made-up model in the test process, the class-conditioned assertions take their reporting branches. The
    junit property `a89_refinement_asserted` is `false`, `A25 on` and `A99 (a) on` are printed, and the generate
    test skips with its reason;
  - **HM-36** (live, TR09): the ten modules of H12, unpatched, with `-s` and a junit file → 0 failed, exactly 2
    skipped (R-150 history). The junit property `a89_refinement_asserted` is `true` in all six A89 cases, and the output
    holds no `A25 on` and no `A99 (a) on` report line, so A25, A99 (a) and A89 took their asserting branches;
  - **HM-37** (live, TR09): F0 as §7.3 item 2;
  - **HM-38** (live, TR09): step 6's ensemble leg as §7.3 item 4.

### WO-H6: documents (Sonnet)

- `docs/RELEASING.md`, after the R-1008 paragraph (`:198-201`): "When the RC host moves to another machine, the same
  re-takes carry the records across. Their proofs name the committed host (`--old-host`) and admit only R-1020's
  host-identity leaves: the host name, the CPU model, the CPU count, the CPU flags, the platform string and the
  pinned environment's directory. Every number must stay bitwise equal. The new host must first be a member of T06's
  `ref-x86-64` (RP (P6))."
- `docs/NEW_HOST_SETUP.md` §6: replace the steps with a pointer to this note's §3 to §7 and WO-H1 to WO-H5, and
  correct "`scripts/m05_retake_diff.py --digest-only`" to the A-13 form. Keep the sentence "Do not carry TRS2's records
  across as if they matched TR09".
- `docs/RP_DECISIONS.md` (the build log) records each WO's lines.
- A default-tier test, `tests/test_hostmove_host_leaves.py`, runs `docs/derivations/scripts/hostmove_host_leaves.py
  --check` and expects exit 0, so that this note's claims about the 0.4.0 records stay executable. CI clones with
  `fetch-depth: 0`, so the pinned commit is present there.
- Check: `tests/test_rel_release_gate.py` passes, because it checks RP's §14 rows.

## 12. Frank

No question for Frank. This is procedure: no criterion, claim or scope changes, and no standing acceptance lapses
(WO-H3 keeps M03 N1's scope byte-equal). One information line goes into the first TR09 cut's message (RP §8.5), not
onto the decision board:

> For information, no decision: after the move to SMM-TR09, the stored results that name the machine (the
> optimisation study records, the reactor study, the IDAES cross-check) are re-taken there, and a check confirms that
> every number is unchanged. The new machine also becomes the reference machine for the robustness ensemble after the
> same kind of check. If any number had changed, the work would stop and come back to the design lane.

## 13. Open questions, each with a default

- **O-H1 (fact, measured at `c57c2ca0`): do REAL's numbers reproduce bitwise on the 2950X?** Yes, by §4.3. K3's code
  can still differ. If HM-27 fails with an `other` line outside the registered paths at K3, the cut stops (RP §12),
  and the design lane rules on the moved leaves. This ruling does not pre-decide a tolerance. G10 is bitwise.
- **O-H2 (needs a fact): does step 6's ensemble leg pass on TR09?** HM-38 measures it. Default: yes, by H12, which ran
  A90's expected counts and the A34-type checks in the test suite. If it fails, WO-H5 stops, and the class does not
  move.
- **O-H3 (preference, design lane): where `host_identity()` lives.** Default: `tests/support/m05_replay.py`, which
  both the writer and the proof already import. Alternative: the proof computes the values itself, with a test that
  they equal the writer's.
- **O-H4 (preference): should `--old-host` be optional at an unchanged-host cut?** Default: no. RP names it at every
  cut. It costs nothing, and it removes a diagnosis branch.
- **O-H5 (needs the user's preference, not Frank's attention now): keep the 5965WX listed after TRS2 is wiped.**
  Default: yes. The committed files name it, and listing a model admits nothing that runs.

## 14. What this ruling does not establish

- That the host cannot move a number in general. Each proof shows equality between two specific hosts, for the
  records it walks, and nothing more. A third machine needs its own proof.
- That any record is right. The re-take proofs are regression identity with the committed records, and validity rests
  on M05's, M01's and T06's own evidence.
- That REAL reproduces on TR09 at K3's code. §4.3 measured it at `c57c2ca0`, with R-1008's tool and a scratch
  classifier, not with WO-H1's tool. K3's proof decides it at K3.
- That the synthetic assertions (HM-01 to HM-18, HM-22 to HM-24, HM-30 to HM-33) measure a host move. They test the
  tools' logic. HM-19 to HM-21, HM-25, HM-27 to HM-29 and HM-34 to HM-38 measure.
- That the T06 reference class is right for any CPU outside its list, or that `ci-x86-64` runners match it.
- That the inventory member's value is irrelevant to users who run Pyomo without `PYOMO_CONFIG_DIR`. The adapter's
  refusal covers that case, and this ruling relies on that refusal.
- That `hostmove_host_leaves.json` describes any commit but `b6cdf552`. It is a fact about the 0.4.0 records. Its
  generator's refusals are exercised only by the committed bytes; no negative control mutates them.
- Anything about TRS2's own state: its 67 stale worktrees, its `~/.pyomo` leftover, or its retirement.
