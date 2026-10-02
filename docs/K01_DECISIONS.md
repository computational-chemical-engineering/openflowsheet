# K01 — decisions log

Append-only. Never read whole; grepped for a specific question. Each entry: the question, the
options, the choice, the reasoning, and the commit that carries it.

## 2026-09-17

**Q: Spend K01's Fable design pass on ADR 0002 (canonicalization), or implement it?**
Options: (a) Fable authors ADR 0002 first; (b) Opus implements, Fable reviews.
**Chose (b).** Announced (a) first and reversed it on evidence: plan §51 puts canonicalization
explicitly in Opus's lane, and CLAUDE.md routes work whose failure a test would catch to Opus with
Fable review where it touches replay identity. Encoding isolated behind `ENCODING_ID`.
Commit `5ff3ec9`.

**Q: Refactor the two existing hash implementations to call the promoted one?**
**No.** The judge's copy was written separately so a harness cannot certify its own hash;
collapsing them destroys the property that makes them evidence. Assert agreement instead.
Commit `5ff3ec9`.

**Q: CasADi 3.8.0 ships a `casadi.pyi` that mypy cannot parse (three parameters named `INOUT`).**
Options: (a) disable mypy on the adapter; (b) `follow_imports=skip` (tried, does not work — mypy
parses the stub regardless); (c) shadow it with a local stub.
**Chose (c).** `stubs/casadi/__init__.pyi` declares the dependency untyped, which is a true
statement rather than a relaxation; `--strict` still applies to every line of `process_runtime`.
A test fails when upstream fixes the defect, so the shim cannot outlive it. Commit `1950a3c`.

**Q: Where does SYN-001's physics live for the K01 conformance fixture?**
Options: (a) `src/models/`; (b) `benchmarks/k01/`.
**Chose (b).** Plan §51 gives unit-model implementation to K02; K01 is the compiler and must not
pre-empt it. The fixture reuses the closed forms in `benchmarks/p02/expected.py` and is judged
against Fable's independent 20-digit `reference_values.yaml`, so the composition and the
derivatives are checked independently even though block values share a source.

## 2026-09-18

**Q: What metric compares the assembled residual against the references?**
First attempt normalized by the reference value and reported 100% deviation at S1–S4.
**That was the metric's fault, not the compiler's**: those states sit on the solution, so their
reference residuals are round-off at 1e-17, and a relative comparison demands that two correct
implementations agree on noise. **Chose** the registered form, reused verbatim from
`benchmarks/p02/judge.py`: `1e-13 * (|expected| + scale)`, floored by the row scale. Commit
`fffed24`.

**Q: Promote `PropertyCapabilities`, the fourth schema on the plan §2.2 P02/K01 row?**
**No.** No `PropertyProvider` exists, and plan §2.2 says a schema is added when the object it
describes is used, not in advance. Deferred to K02 and recorded as `not_applicable` in the manifest
rather than omitted. Commit `5fe0a3b`.

**Q: Do the cross-field document checks earn their place beside the JSON Schemas?**
Measured rather than assumed: of the sixteen invalid fixtures, five are caught by a schema, two by
both, and **nine only by the checks**. A document can satisfy all three schemas and still describe a
matrix that does not exist. Commit `5fe0a3b`.

**Q: A mutation sorting CSC by `(row, column)` survived all 23 unit tests.**
Cause: the first fixture's Jacobian is diagonal, so column-major and row-major orderings coincide
and every ordering assertion was vacuous. **Fixed** by adding a fixture with two rows per column and
two columns per row, with the arrays written out by hand and an anti-vacuity test asserting the
shape can tell the orderings apart. Commit `1950a3c`.

**Q: Are other K01 tests vacuous the way the CSC-ordering ones were?**
Answered by measurement rather than reading: a sweep of thirteen mutations across
`canonical.py`, `casadi_backend.py` and `spec.py`. **Two survived all 580 tests**, both the same
class — an assertion true of the right answer and of a wrong one because the fixture is too
symmetric.

- `state_sha256(x * 0.0, ...)`: a *constant* state hash satisfies every pairing and
  workspace-inertness assertion, because those compare the field with another copy of itself.
  Nothing asserted the hash was of the state actually evaluated. That field is replay identity.
- `ca.jtimes(..., tr=False)`: the reverse product computed forward. The two-variable fixture's
  Jacobian is diagonal, so `Jᵀ == J` and the mutation is invisible there.

Both closed: `state_sha256` is now recomputed independently and asserted distinct across distinct
states, and the reverse product is tested on the non-symmetric dense fixture with an anti-vacuity
assertion that the fixture is not symmetric. **13 of 13 mutations now caught.**

**Q: Ratify `%.17g` as the identity encoding, or change it?**
The Fable review of K01 recommended against ratifying it; **Frank agreed on 2026-09-18**.
**Changed** to big-endian IEEE-754 binary64 bytes, `ENCODING_ID = "ieee754-be-v1"`. The deciding
argument is portability, not speed: `%g` is C's and its stripping, exponent width and nan/inf
spellings are not fixed across languages, so a text digest makes replay identity depend on how one
C library prints a double. The measured 30–38× speedup points the same way but is the weaker
argument, since the release horizon's problems are too small for it to matter.

Identity semantics are unchanged, and `tests/test_adr_0008_transient_readiness.py` H1–H6 now run
against **both** implementations so every D2 rule is pinned on each. The legacy encoder is kept, not
as dead code but as the live evidence that the P02 artifacts can still be checked against the two
independent implementations that hashed them. Registered as **R-006**; ADR 0002 must still ratify.
