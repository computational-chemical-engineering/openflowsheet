# Brief — Fable review of the completed K01

**To:** `fable-reviewer`. **From:** the Opus 5 session, 2026-09-18. **Branch:** `wp/K01`.
**Plan authority:** §4.2 row K01 — Opus lead, **Fable review**.

## 1. What was built, and against what

K01 turns the P02 CasADi spike into the production `CompiledProblem` compiler. It was built against
three authorities, all already written and none of them open for you to reopen:

- **ADR 0003 D5** — the eight obligations the backend selection puts on K01.
- **ADR 0008 D4.1, D4.2, D4.4** — pinned-input identity, the inert workspace, row accumulation.
- **ADR 0006 D5.1, D5.3, D5.5** — the dependency pin, the notice, the hygiene test.
- **`docs/interfaces-frozen.md` §1** — the frozen `CompiledProblem` boundary, unchanged.

Commit range: `fffed24..HEAD` on `wp/K01` (the five K01 milestones after P03 landed).
Evidence manifest: `evidence/K01/efc1f23d79fae0fc8cd971e9572d8aac741d8fa7/manifest.json`, `tested`.

## 2. What I actually ran, and the numbers it produced

Gate: `PATH=.venv/bin:$PATH ./scripts/check.sh` — ruff, ruff format, mypy --strict, pytest.
**Green at 574 tests** (444 before K01 began).

SYN-001 lifted form, 17 variables, 17 equations, compiled by the production compiler and compared
against `benchmarks/p02/reference_values.yaml` (Fable's mpmath values at 40 digits, generated from
the SYN-001 derivation with no backend and no oracle import) at all six registered states:

| | Worst over S1–S6, as a ratio to the registered tolerance |
| --- | --- |
| Residual | **0.0134** at S2 `kdef_A` |
| Jacobian | **0.00174** at S6 `eq_A|l_A` |
| Assembled pattern | `(17, 17, 60)` at every state; no missing, no unexpected entries |
| Block calls per Jacobian | 1 value + 1 Jacobian, both blocks, every state |

Tolerance is the registered one, reused verbatim from `benchmarks/p02/judge.py`:
`1e-13 * (|expected| + scale)`, the scale being the row scale for a residual and the row/column
scale ratio for a Jacobian entry.

**Mutation checks I ran, and what they caught.** Declaring block H dense fails 13 conformance
tests; perturbing the energy row by 1e-9 relative fails 12; flipping the sign of `dlnK/dP` fails 6.
On the unit fixture: removing `has_jac_sparsity` fails 3; claiming an exact Hessian fails 1.

## 3. The three things I am least sure of

Look here first. Each is somewhere a wrong answer would still look plausible.

1. **`_csc_from_triplets` and the two permutation hazards.** CasADi fills a sparse `DM` in
   column-major order rather than triplet order, and a row's identity is its equation id rather than
   its position. I read the assembled matrix out through CasADi's own `sparse().get_triplet()` and
   re-sort by `(column, row)`. **A mutation sorting by `(row, column)` originally survived all 23
   unit tests**, because that fixture's Jacobian is diagonal and the two orderings coincide on it —
   every CSC ordering assertion was vacuous. I added a second fixture with two rows per column and
   two columns per row and the mutation now fails. I would like you to check whether any *other*
   assertion in that module is vacuous for the same kind of reason, and whether the SYN-001
   conformance comparison — which reads entries back by `(row_id, col_id)` — could pass under a
   permutation I have not thought of.

2. **What the conformance test is actually independent of.** `benchmarks/k01/syn001.py` imports the
   block closed forms from `benchmarks/p02/expected.py`, so the *values* a block returns share a
   source with one of the things being compared. My claim is that the composition and the
   derivatives remain independent, because the compiler assembles 17 rows from separate
   declarations and differentiates algorithmically while the reference evaluated whole closed-form
   residuals and differentiated by hand. **Is that claim sound, and is it strong enough to call this
   verification rather than a regression fixture?** If not, say what would have to change.

3. **The identity encoding, promoted without ADR 0002.** `src/process_runtime/canonical.py` promotes
   the P02 specification §10.4 encoding — `%.17g`, comma-joined, signed zeros normalized, SHA-256 —
   to production, for both `state_sha256` and `constants_sha256`, written as two uses of one
   primitive. The specification calls its own encoding "P02-local, replaced by ADR 0002", and
   ADR 0002 does not exist. I judged this Opus's lane (plan §51 puts canonicalization there;
   CLAUDE.md routes work whose failure a test catches to Opus with Fable review where it touches
   replay identity) and isolated it behind `ENCODING_ID`. **Is `%.17g` the right encoding to ratify,
   and is `constants_sha256` covering the full pinned-input vector in `parameter_ids` order the
   right reading of ADR 0008 D4.1?** If you want a different encoding, now is the cheap moment:
   nothing is released and changing it regenerates fixtures rather than migrating stored hashes.

## 4. Decisions I took that you may disagree with

- The two existing hash implementations (`spikes/p02/common/export.py`, `benchmarks/p02/judge.py`)
  were **not** refactored to call the promoted one. The judge's copy was written separately so a
  harness cannot certify its own hash, and collapsing them would destroy the property that makes
  them evidence. `tests/test_canonical.py` asserts all three agree instead.
- `benchmarks/k01/syn001.py` is a **fixture, not a unit model**: plan §1.3 gives unit-model
  implementation to K02 and I did not want K01 to pre-empt it.
- `PropertyCapabilities`, the fourth schema on the plan §2.2 P02/K01 row, is **not promoted**. No
  `PropertyProvider` exists and the plan says to add a schema when its object is used.
- CasADi 3.8.0 ships a `casadi.pyi` that mypy cannot parse (`Sparsity.dfs` declares three parameters
  named `INOUT`, four times). `stubs/casadi/__init__.pyi` shadows it with an explicit untyped
  declaration. `--strict` still applies to every line of `process_runtime`; what is lost is static
  checking of arguments passed into CasADi from the one adapter module.
- An undeclared nonzero returned by a block is **refused**, not dropped. CasADi discards the Python
  message and substitutes its own, so the adapter records the block's reason on the way out.

## 5. What not to spend time on

The backend selection (ADR 0003, closed), the distribution policy (ADR 0006, closed, Q1 answered by
Frank), the P02 measurements, the plan or the blueprint, and formatting or style — ruff and mypy
already gate those. Do not review the P03 audit; it is merged and reviewed-adjacent work is done.

## 6. Deliverable

A review report to me: what is wrong, what is weakly evidenced, and what is over-claimed, ordered by
how much it matters. Name the file and line. If you believe a test is vacuous, say which mutation
would survive it — that is the form I can act on directly.

**Do not edit any file.** I own the branch and will act on your findings. **Do not set `reviewed`**
in any manifest; human numerical and process-modeling sign-off is separate and no agent may claim
it.
