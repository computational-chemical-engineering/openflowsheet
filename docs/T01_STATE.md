# T01 — campaign state

**Closed: merged to `main` at `6b7a153` on 2026-09-24.** Kept for what T02 inherits.

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`.

| | |
| --- | --- |
| Objective | Process and equation graphs, fixed/alias elimination, DM/SCC/BTF, source-mapped counts and tear candidates (plan §4.2 row T01) |
| Authority | **`docs/derivations/T01-structural-spec.md`** — Fable's specification, 19 sections, assertions A00–A25. Implement against it; do not re-decide what it decided |
| Reference | `benchmarks/t01/reference_values.yaml` (SHA-256 `71d5ec92…`), regenerated only by `docs/derivations/scripts/t01_reference.py --emit`; `--check` runs 42 self-checks |
| Branch | `wp/T01`. F1 decision at `00a71f4`, review fixes at `b9f4e6a`, increment 2 at `00fbca4`, increment 1 at `3674d30`, spec at `f0e005a` |
| Layer | `src/process_runtime/graph/` — `trace`, `matching`, `certificates`, `dof`, `report`, `analysis`, `process` |
| Gate | `PATH=.venv/bin:$PATH ./scripts/check.sh` — green at **1411** (83 T01 tests) |

## Where we are

**Both increments are done.** `src/process_runtime/graph/` holds the declaration trace, maximum
and canonical matching, the coarse DM partition, the affine-copy certificate, unit-local degrees
of freedom, strongly connected components with the block-triangular form, process loops with the
tear rule, the attempt-signature rule, and the report with its six statements.
`application/binding.py` binds a SYN-001 revision and promotes §5.1's specification rows;
`application/validation.py` emits `STR-01`…`STR-05`; `run/session.py` writes the report into every
run bundle and `run/identity.py` projects it into R0, so gate G05 compares it across both CI
architectures on every push.

Evidence: `evidence/T01/00a71f4562b7bd80441df50cf64b53064d832b78/manifest.json`, **26 pass, 0
fail, 0 unsupported**, status `tested`, `review` pending. Every value in it is measured at
generation time against Fable's independently derived reference.

**The Fable review is done** (`docs/reviews/T01-review.md`): four must-fixes, all reproduced
before being fixed, all closed; should-fixes S1, S2, S3, S4 and S7 closed; the rest recorded
below. One item needs Frank — see the table.

**What T01 closed.** The conflicting-heater revision is rejected at validation with the registered
finding; `structural_counts` is computed; STR-03 is a real check; the K02 rank report exists; and
K03 §9.1's general signature rule is derived rather than declared — `signature_units == (U-FLASH,)`
now comes out of the graph and a test asserts it equals K03's hard-coded instance.

**What is still open**, and named in the manifest's limitations: the revision→declaration binding
covers the registered SYN-001 revisions only (ADR 0002 D2.7's obligation travels with whoever
generalizes it); the certificate class covers pressure and temperature copies because ADR 0001 D6
registers a tolerance for those two kinds and no other; multi-edge feedback sets are reported
`unsupported` and not torn; and structural results remain diagnostic under D05.

**Next:** Fable review of T01, then merge to `main`. After that the plan's next row is T02.

## The three things a fresh session would otherwise get wrong

**Do not read the structure from `jacobian()`.** It was my recommendation in the brief and Fable
overturned it on a measurement: the backend pattern is *parameter-dependent*. At `r = 0` CasADi
constant-folds `0.0 · S5.n_i` and the three `SPLIT-recycle:i × S5.n.i` entries vanish — nnz 167,
not 170. Verified independently. The source is the **declaration-traced** incidence of spec §3.3:
run the row builders under a set-valued structural algebra with parameters opaque. The backend
pattern is a cross-check only (A02), and the `r = 0` difference is registered *because* it
vanishes.

**Over-determination is not a defect.** The nominal, valid SYN-001 is over-determined: 49 × 47,
structural rank 47, a 7-row DM block confined to the pressure subgraph. The discriminator (§8.1)
is closure *after removing the certified rows*, not the emptiness of the DM block.

**The DM alone cannot name the heater.** After certificates the conflicting case's
over-determined part holds ten specification rows, and relaxing *any one* closes the system. So
the report lists all candidates and says so (statement S4), and the heater is named by a second
layer: unit-local degrees of freedom, `specs_u > dof_u`, 2 > 1 (§8.3), with an executable
bookkeeping identity `Σspecs + Σlocal − Σdof = excess − deficit` tying the layers together.

## Open questions, defaults adopted (spec §18)

Fable recorded `FOR FRANK: none` in §17 and gave every question a default. Adopted as written
unless Frank says otherwise; each is reversible in one commit.

| | Question | Adopted |
| --- | --- | --- |
| Q1 | A fourth `ValidationReport.status`, `UNSUPPORTED`? | **No** — a frozen-schema migration for a distinction the check already carries |
| Q2 | `rank.py` consumes T01's declaration-sourced certificates? | **Later**, once A06 is green. Not in T01's increments |
| Q3 | Tear-score terms beyond dimension and boundary distance? | **T02**, which can measure them |
| Q4 | `StructuralReport` in every run bundle? | **Yes** — small, and A22 needs it in the G05 identity comparison |
| Q5 | `unmatched` counts columns as well as rows? | **Yes** — one integer serves both findings, and `SQ-1` must not read as 0 |

## Next action

**Merge `wp/T01` to `main`.** The condition is met: the evidence manifest exists with
`status: tested`, the Fable review is complete and every must-fix is closed with a regression
test. After that the plan's next row is T02.

## F1, decided

**Frank decided on 2026-09-24 (register R-022)** that the status depends on why the analysis did
not run: contradictory specifications are `INVALID` with an `STR-04` conflict naming both; a
missing specification is `DRAFT`, as blueprint §4.3 says; a revision the binding cannot read is
`DRAFT` as an interim. The fourth status that would say "not analysed" exactly is T01 Q1 and needs
an ADR, deferred until a second consumer needs the distinction at status level.

## Should-fixes left open, recorded not dropped

| | Item |
| --- | --- |
| S5 | A valve — any pressure row that is not a literal-coefficient copy — is listed `uncertified_affine` with a `STR-06` warning. Correct but noisy once a real unit library exists; T06 generalizes the certificate class |
| S6 | An inner system that is not perfectly matched yields a silent empty signature rather than a typed result |
| S8 | Structural under-specification is unreachable through `validate()`: the narrow binding needs every specification the flowsheet is parameterized by, so a revision omitting one is `DRAFT` naming what is missing, rather than reaching `STR-02` |
| S9 | Three compiles per run in `session.py`, and quadratic matching and lookups. Not a problem at 47 columns; T02 should budget for it |

## What the adversarial assertions caught

1. **A15 found a defect rather than confirming the code.** The row-to-unit attribution parsed the
   `U-` id prefix, so relabelling every id by a bijection emptied it *silently* — which would have
   emptied the unit-local degree-of-freedom count and with it the localization that names an
   over-specified unit. The graph layer now parses no id at all (register R-019).
2. **`U-PRODUCT` vs `U-PROD`.** `benchmarks/t01/reference_values.yaml` calls the vapour-product
   sink `U-PRODUCT`; the repository's constant (`models/syn001/flowsheet.py:57`) is `U-PROD`. The
   unit owns no column and authors no row, so no number moves. `tests/test_t01_structural.py`
   names the mapping rather than silently applying it.
3. **`Check` did not match its own frozen schema.** `validation-report.schema.json` requires
   `stage`, `result`, `message` and `implicated_objects` with `additionalProperties: false`; K06
   emitted `id`/`passed`/`detail`/`scope`. Nothing validated a *produced* report against the
   schema, so it never surfaced. Fixed here; `passed` and `scope` survive as derived properties.

## Open items that are *not* T01

| # | Item | State |
| --- | --- | --- |
| 1 | Repository is private | v0.0.0 tagged in it. Making it public and publishing to PyPI were offered on 2026-09-23 and not taken; both irreversible, neither implied by the tag |
| 2 | ADR 0006 Q3 | Whether any package before v0.2 ships a mode-B artifact. The trigger that reopens METIS |
| 3 | P03's two unresolved licence findings | 5 723 463 bytes with no notice; ASL terms unreadable from any installed artifact. `unsupported`, not cleared. Only bites if binaries ship |
| 4 | ADR 0005 | Pre-allocated, unwritten. K03 §9 is interim normative text (R-A05); T01 §9.6 derives its structural half, T03 generalises |
| 5 | ADR 0001 D6 | No `heat_rate` certificate class (spec §19 finding 9), and no lifted equilibrium row kind. Two one-line amendments when D6 is next touched |
| 6 | ADR 0002 D2.7 | The v2 structure document is owed by whichever package first assembles unit rows from manifests. T01 assembles only specification-promotion rows, so it does not trigger (spec §19 finding 3) |
| 7 | K03 A30's `equals` | Should read "as a set": a union-find traversal order is not part of the identity (spec §19 finding 5). One word, when K03's document is next touched |

4. **The review found four more, all of which the registered cases hide.** M1: `breaks_loop` was
   "the component is no longer the whole set", so two recycles sharing a unit left a loop inside
   the inner system — SYN-001's simple cycle cannot tell the two tests apart. M2: the flash
   pressure specification was never read, so K03's registered 150 kPa conflict validated clean.
   M3: a revision nobody could analyse validated `READY_FOR_SIMULATION`. M4: a copy row's
   coefficients were not required to cancel, so `P_a + P_b − P_spec` was certified as
   `P_a − P_spec`, false at every state — and that one was in the specification, the reference
   generator and the implementation at once, because SYN-001 declares no row of that shape.
   K03's `rank.py` shared it and was saved by its two-state numerical witness (R-021).
