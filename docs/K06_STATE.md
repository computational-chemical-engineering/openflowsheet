# K06 — campaign state

**Rewritten in place, never appended.** A position, not a diary.

| | |
| --- | --- |
| Objective | Local transactions, Python/CLI entry points, the integrated example and the v0.0 gate (plan §4.2 row K06) |
| Branch | `main` |
| Gate | `PATH=.venv/bin:$PATH ./scripts/check.sh` — **green at 1314 tests** on both architectures |
| Lead | **Opus.** The only package with no Fable column: it touches no residual, derivative, phase, scale, certificate or replay identity |
| Manifest | `evidence/K06/cda68cd446be27992051d43422336ad5f9430fe8/manifest.json` — `status: tested`, 6 pass / 0 fail / 1 unsupported / 1 not applicable |
| Requirements | D15, D16 — both `implemented` in the ledger |

## Where we are now

**All seven v0.0 gates are met.** `PYTHONPATH=. python scripts/v0_0_gate.py` reads the
committed evidence manifests and reports:

| Gate | Status | Owners |
| --- | --- | --- |
| G00 three-component process, one numerical tear | met with limitations | K02/K03 |
| G01 damped Newton plus interface fixtures | met with limitations | K01/K03 |
| G02 canonical revision, locks, source mapping, Python/CLI | met with limitations | K01/K06 |
| G03 serialized manifests, events, certificates, failures, replay bundle | met with limitations | K04/K05 |
| G04 balances, phase transition, bad spec, numerical failure | met with limitations | K04 |
| G05 dependency change detected, two-platform structural equality | met with limitations | K05 |
| G06 end-to-end example inspectable without unrelated code | **met** | K06 |

A gate **inherits** its packages' `unsupported` checks as limitations rather than shedding
them; none is upgraded and none is averaged. G06 is the one gate that re-runs live, because its
claim is about what a reader can do rather than what a file says.

## The three commands that are G06

    python -m process_runtime.application.cli solve SYN-001-nominal --out ./bundle
    python -m process_runtime.application.cli inspect ./bundle
    python -m process_runtime.application.cli replay ./bundle

`inspect` prints what ran, the environment it ran in, the certificate and its checks, the
trace — and a section headed **what this certificate does not claim**, carrying the three
required statements and the [A09] shared-provider qualification in full.

## Next action

**v0.0 is feature-complete and is not a release.** What stands between here and one is human
sign-off — `review.numerical` and `review.process_model` are `pending` in all nine
manifests and no agent may set them — and the three notes for Frank in `docs/progress.md`.

## Open items

| # | Item | State |
| --- | --- | --- |
| 1 | Structural over-specification | Not detected. The registered conflicting-heater revision validates `READY_FOR_SIMULATION` and the solver rejects it with `SPECIFICATION_CONFLICT`. The validator says so in its own report as an `unsupported` check; detecting it needs §4.3's matching, which is T01's |
| 2 | Jobs, HTTP/MCP, authorization | Not implemented. Blueprint §11 describes all three and plan §4.2 puts them in T07 |
| 3 | The revision store is in memory | No persistence, no concurrent access across processes, no durability claim |
| 4 | The CLI solves registered cases only | There is no path from an arbitrary revision document to a solve; the compiler binding for a general revision is T01's |
