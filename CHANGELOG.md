# Changelog

## v0.1.0 — release candidate `C` = `67c66d9` (`0.1.0rc1`), version-only change to `0.1.0`; tag and publication by Frank

*ADR 0021 D4. The gate table below is what `scripts/v0_1_gate.py --markdown` prints for the release
candidate `C` = `67c66d98587f23bd7dfe8da28a8facccc92da21e` after the design lane's verdicts
(`docs/reviews/T08-verdicts.md`); T08's evidence is `evidence/T08/67c66d9…/manifest.json` (`tested`). The tag
commit differs from `C` only in the version (ADR 0021 D2.4); the tag and every publication are Frank's (ADR 0021 D5).*

**What it does.** A process simulator for ideal three-component processes that an agent or a
person drives through one application contract — Python, CLI, HTTP and MCP over stdio, twenty
operations — in which every solve ends in a certificate or a typed failure and writes a replay
bundle. A flowsheet is a content-addressed revision of thirteen unit models (mixer, splitter, TP
and PH flashes, heater, exchanger, pump, valve, component separator, conversion reactor, kinetic
CSTR, feed and sink). Validation reports structure (DM/BTF), units and components before a solve.
The planner tears recycles with safeguarded Anderson acceleration or merges them into
equation-oriented regions, promotes cross-unit specifications into EO, and runs bounded phase
attempts and the bounded recovery edges of `docs/recovery-edges.yaml`. A verifier that shares no
factorization with the solver issues a `SolutionCertificate` (residuals, balances, regularity,
alias certificates) or a failure bundle. Compatible warm starts and pseudo-transient continuation
are offered by explicit policy only (`T08-warm-v1`, `T08-ptc-v1`). The supported envelope is
`docs/support-matrix.md`: **unlisted is unsupported**.

**Name.** The project is **OpenFlowsheet**: distribution, import package and console script are
`openflowsheet` (they were the provisional `process-runtime` and `process_runtime`; there is no
alias), and the environment variables are `OPENFLOWSHEET_*` (R-149). Install the server extra with
`pip install 'openflowsheet[server]'`; solve with
`openflowsheet solve SYN-001-nominal --out ./bundle`.
The schema `$id`s keep their v0.1 URLs. The rename moved the SYN-001 provider's self-hash and so the
registered identity values that cover it, by substitution only (R-149).

**Gates (V11–V20), as `scripts/v0_1_gate.py` prints them.** A FAIL is printed FAIL; a released
FAIL is only a clause ADR 0021 D3 lists with Frank's acceptance.

| Gate | Verdict at C | Required evidence | Clauses and travelling limitations |
| --- | --- | --- | --- |
| V11 | PASS | Semantic diff, drafts, task validation, units/references, real migration when applicable | limitations: L38 |
| V12 | PASS | Required unit library with per-model definition of done | limitations: L02, L26, L27, L28, L29, L30, L-CSTR-1, L-CSTR-2, L-CSTR-3 |
| V13 | PASS | DM/SCC/BTF, tear and EO, scaling and initialization | limitations: L10, L22, L23, L24, L36, L38, L-WS-1, L-WS-2 |
| V14 | FAIL | Homotopy, qualified PTC/SER and three bounded recovery edges | failing: V14 (b); V14 (b) FAIL, accepted by Frank 2026-09-29 (ADR 0021 D3); limitations: L01, L08, L20, L21 |
| V15 | PASS | Frozen phases, EO cross-unit spec, multiple-root evidence | limitations: L02, L14, L19, L20, L33 |
| V16 | PASS | 30+ distinct cases, eight shared comparisons, two both-reference cases where feasible, registered 20x20 ensemble | limitations: L16, L17, L18, L32 |
| V17 | PASS | Local/HTTP/MCP, ten agent tasks, >=80% success, zero unauthorized actions/false verification | limitations: L11, L12, L13 |
| V18 | PASS | Distribution/data gates, local rank evidence, qualified energy checks, all recovery edges tested | limitations: L03, L05, L06, L15, L19, L25, L34, L37, L39, L40, L41 |
| V19 | PASS | Real-chemistry dossier with usable data/kinetics/property/reference route | — |
| V20 | PASS | >=95% nominal robustness, correct invalid-structure handling, no adversarial false verification | limitations: L04, L07, L09, L31, L32, L38 |

**What it is not.**

- **Not empirically validated.** SYN-001 is synthetic — three pseudo-components with invented
  constants and ideal VLE — and every result is numerical verification against the same
  equations (L18).
- **Not a guarantee.** A human sign-off records that someone with the relevant expertise
  examined the evidence and raised no objection, not that the content is correct (R-017).
- **Not general beyond the support matrix.** What `docs/support-matrix.md` does not list is
  unsupported, and each unsupported capability ends typed (U01–U14).
- **Not a certificate of solution accuracy.** `VERIFIED` certifies residual accuracy at the
  registered tolerances; the solution-error bound is recorded and disclosed, never promised
  (ADR 0007 F3; L05).
- **PTC is experimental.** No PTC family is qualified: V14 (b) is FAIL (on PTC-R1, PTC ends at
  the saddle from 149 of 441 starts) and carried by Frank's acceptance (ADR 0021 D3, L01).
- **The agent evidence is narrow.** One pinned model and configuration, MCP only, not out of
  sample (L12).

**Known limitations, by support-matrix id** (the text of each is in `docs/support-matrix.md`):
`L01`, `L02`, `L03`, `L04`, `L05`, `L06`, `L07`, `L08`, `L09`, `L10`, `L11`, `L12`, `L13`, `L14`, `L15`, `L16`, `L17`, `L-CSTR-1`, `L-CSTR-2`, `L-CSTR-3`, `L-WS-1`, `L-WS-2`, `L18`, `L19`, `L20`, `L21`, `L22`, `L36`, `L37`, `L38`, `L39`, `L23`, `L24`, `L25`, `L26`, `L27`, `L28`, `L29`, `L30`, `L31`, `L32`, `L33`, `L34`, `L35`, `L40`, `L41`.

**Reproducibility.** In the words of ADR 0007 F1: "the project reports bitwise agreement and
never promises it, on any platform including a single machine; R0 bit-identity of structure plus
D2 agreement for floats is the promise." The registered platforms are Linux x86-64 and aarch64
with Python 3.13 and the one lock (`requirements.lock`, `ead4edf1…`); floats are compared under
`K04-numerical-policy-v1`.

**Review status of every package** (each manifest's `status`; human `review` fields as
recorded):

| Package | Status | Human review (numerical / process model) |
| --- | --- | --- |
| P00 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| P01 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| P02 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| P03 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K01 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K02 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K03 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K04 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K05 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| K06 | `reviewed` | signed 2026-09-23 (R-017) / signed 2026-09-23 (R-017) |
| T01 | `tested` | pending / pending |
| T02 | `tested` | pending / pending |
| T03 | `tested` | pending / pending |
| T04 | `tested` | pending / pending |
| T05 | `tested` | pending / pending |
| T05b | `tested` | pending / pending |
| T06 | `tested` | pending / pending |
| T07 | `tested` | pending / pending |
| T08 | `tested` | pending / pending |

`reviewed` on P00–K06 is Frank's sign-off of 2026-09-23 in R-017's qualified form: it records
examination without objection, not a guarantee of correctness. T01–T08 are `tested`: their
design-lane reviews are recorded under `docs/reviews/`, and their human `review` fields are
`pending`. T08's manifest is at the release candidate `C` = `67c66d9`
(`evidence/T08/67c66d98587f23bd7dfe8da28a8facccc92da21e/manifest.json`): 85 checks, 83 pass and
2 FAIL (T08.A70 and B23, V14 (b), accepted by Frank in ADR 0021 D3).

**Licensing.** Apache-2.0 (`LICENSE`, `NOTICE`). The sdist and the wheel carry the project's own
code, its package data and its licence files only (ADR 0006 mode A); CasADi (LGPL-3.0-or-later),
numpy and scipy are fetched by the installer from PyPI.

## v0.0.0 — 2026-09-23

The first vertical slice: an ideal three-component flash–recycle process, solved, independently
verified, replayable, and inspectable from the command line.

**What it does.** Compiles a declared flowsheet to a sparse residual and exact Jacobian
(CasADi 3.8.0); solves a three-variable tear with a damped Newton and bounded phase attempts;
verifies the answer with a verifier that shares no factorization, cache or intermediate with
the solver; issues a `SolutionCertificate` or a `FailureBundle`; writes a replay bundle that a
third party can re-run or, failing that, inspect.

    python -m process_runtime.application.cli solve SYN-001-nominal --out ./bundle
    python -m process_runtime.application.cli inspect ./bundle
    python -m process_runtime.application.cli replay ./bundle

**Acceptance.** All seven gates of plan §5.1 are met — `PYTHONPATH=. python
scripts/v0_0_gate.py` reads them from the committed evidence rather than re-deriving them. Six
of the seven are **met with limitations**, and the limitations are on the report rather than in
a footnote. 1320 tests, green on x86-64 and aarch64.

**What it is not.**

- **Not empirically validated.** SYN-001 is synthetic: three pseudo-components with invented
  constants. Nothing here has been compared against experiment or an independent simulator.
- **Not a guarantee.** The human sign-off on every evidence manifest records that someone with
  the relevant expertise examined it and raised no objection — register R-017, and the field
  says so itself. Defects are expected to surface in verification and validation studies.
- **Not general.** The check set, the balances and the tear are written for the SYN-001
  topology. A general structural decomposition is T01 and does not exist, which is what most of
  the recorded limitations are waiting on.
- **Not a certificate of solution accuracy.** `VERIFIED` certifies the residuals at the
  registered tolerances; the first-order solution-error bound is recorded and disclosed, never
  promised.

**Known limitations, by gate.** K01's second-order derivatives through an opaque callback
(`unsupported`, reported rather than fabricated); K02's rank report; K03's initializer chain,
of which only the registered local initializer is wired; K04 and K06's structural
over-specification, which needs T01's matching; K05's clean-container replay.

**Reproducibility.** Structural artifacts are bit-identical across x86-64 and aarch64 —
measured, in CI, every push. Floating-point agreement is *reported* and never promised: two
`ubuntu-latest` runners were measured disagreeing on a converged state's last bits, and the
project's promise is R0 structural identity plus agreement within the declared numerical
policy. A changed dependency cannot produce an exact replay, because the mode is decided from
the environment before anything runs.

**Licensing.** Apache-2.0. No third-party binaries are redistributed; CasADi is fetched from
PyPI by the installer.
