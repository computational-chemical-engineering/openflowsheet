# K01 — campaign state

**Rewritten in place, never appended.** A position, not a diary. History is in
`docs/K01_DECISIONS.md` (append-only) and in the git log.

| | |
| --- | --- |
| Objective | Turn the P02 CasADi spike into the production `CompiledProblem` compiler (plan §4.2 row K01) |
| Branch | `wp/K01`, merged to `main` at each milestone per Frank's standing instruction |
| Gate | `PATH=.venv/bin:$PATH ./scripts/check.sh` — **green at 645 tests** (444 when K01 began) |
| Lead | Opus. **Fable review complete and acted on**; all findings closed (plan §4.2) |
| Manifest | `evidence/K01/43653b5…/manifest.json`, `tested`; 10 pass, 1 unsupported, 1 not applicable |

## Where we are now

**K01 is functionally complete and its evidence is recorded.** Six milestones are merged to `main`:

1. `canonical.py` — the identity encoding promoted from P02 spec §10.4, three implementations
   agreeing; `parameter_ids` and `row_accumulation` added to metadata in the one-shot schema
   promotion window (ADR 0008 Q2).
2. `casadi==3.8.0` pinned; README and NOTICE written; the pin proved to install the audited bytes
   and importing the backend proved not to load the METIS closure.
3. `compile/spec.py` (backend-free) and `compile/casadi_backend.py` (the only CasADi import), with
   ADR 0003 D5.1–D5.5, D5.7 and ADR 0008 D4.1/D4.2/D4.4 under test and mutation-checked.
4. **SYN-001 conformance** — the acceptance evidence plan §4.2 names.
5. The three CompiledProblem JSON schemas, a serializer, and 16 invalid fixtures.
6. Evidence manifest, requirements ledger, and the review brief.

### The numbers that matter

Worst over the six registered states **and both compiled forms**, as a ratio to the registered
tolerance (1.0 is the tolerance):

| | |
| --- | --- |
| Residual vs the 20-digit references | **0.0134** at S2, lifted, `kdef_A` |
| Jacobian vs the 20-digit references | **0.0086** at S2, inlined, `eq_A\|l_A` |
| Assembled patterns | `(17, 17, 60)` lifted and `(11, 11, 43)` inlined, at every state |
| Block calls per assembled Jacobian | 1 value + 1 Jacobian, both blocks, every state |
| Mutations caught | **20 of 20** |

### What the Fable review changed

Two defects: `jacobian()` was O(nnz²) — 424 ms at 5998 nonzeros, now 2.66 ms — and a non-finite
state was reported `ok`, which the package's own serializer refused. Five contracts the adapter
stated and nothing exercised (context pins, accuracy policy, phase signature, declared-entry
supply, `parameter_ids` order). And the **inlined form**, which is where the callback chain rule is
actually composed rather than passed through at ±1: the lifted form never exercised it.

## Next action

**Act on the Fable review**, then update this file, `docs/progress.md` and the manifest if anything
changes. After that K01 is done and the next package is **K02** (property-provider plumbing and
caches, unit-model implementation from Fable-approved equations — plan §4.2).

Two items K01 hands forward, neither blocking: ADR 0006 Q4 asks that `requirements.lock` carry the
CasADi *wheel file's* hash for `pip --require-hashes`; the inventory records per-file hashes but not
the wheel's own, and the wheel is not retained after install, so this is K05's. And ADR 0003 Q1
(second-platform wheel and its inventory) is K05's.

## Gates and their current numbers

| Gate | Now |
| --- | --- |
| `scripts/check.sh` | green, 645 tests |
| SYN-001 residual vs 20-digit reference | 0.0134 of tolerance, six states x two forms |
| SYN-001 Jacobian vs 20-digit reference | 0.0086 of tolerance, six states x two forms |
| Assembled patterns | (17, 17, 60) lifted, (11, 11, 43) inlined — as registered |
| Block call accounting | 1 + 1, both blocks |
| Second platform (G05) | **not run** — K05 owns it |
| CI | **has never executed** |

## Open decisions, with their defaults

| # | Question | Default taken |
| --- | --- | --- |
| 1 | Where does SYN-001's physics live? | `benchmarks/k01/`, as a fixture. Unit models are K02's |
| 2 | ADR 0002 (canonicalization) not written | Encoding decided and ratified by Frank as **R-006** (IEEE-754 bytes); ADR 0002 must still be authored and must carry R-006's anonymity clause |
| 3 | CasADi ships an unparseable type stub | Shadowed by `stubs/casadi/`; a test fails when upstream fixes it |
| 4 | `PropertyCapabilities` schema | Deferred to K02 — no `PropertyProvider` exists and a schema is added when its object is used |

## Anchors

- `src/process_runtime/compile/casadi_backend.py` — the adapter; the only CasADi import
- `src/process_runtime/compile/casadi_backend.py` `_csc_from_triplets` — the permutation defence
- `src/process_runtime/canonical.py` — the promoted identity encoding, behind `ENCODING_ID`
- `benchmarks/k01/syn001.py` — the conformance fixture
- `benchmarks/p02/reference_values.yaml` — Fable's 20-digit references, six states
