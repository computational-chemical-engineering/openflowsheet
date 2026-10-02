# T01 review — the structural analysis, against `docs/derivations/T01-structural-spec.md`

**Reviewer:** Fable 5.1 (`fable-reviewer`), 2026-09-23. Plan §1.3: Fable reviews every Opus package
that touches residuals, derivatives, phase logic, scaling, certificates or replay identity; this one
touches certificates, the attempt signature and the R0 identity.
**Brief:** `docs/briefs/T01-implementation-review.md`.
**Reviewed at:** `wp/T01` = `a7c3f54`; commit range `f603e9b..df779b8`; the gate
`PATH=.venv/bin:$PATH ./scripts/check.sh` green at 1397; `t01_reference.py --check` passes.
**Environment here:** x86-64 Linux 6.12.86, Python 3.13.5, the repository's `.venv`.
**Measured:** every finding marked *measured* was produced by a probe script against the code at
this commit, run in this session. Nothing below is inferred from reading alone where it could be run.
**The specification is mine.** Where a finding turns on the specification's own wording, it is
numbered as a finding against the specification, not re-derived (brief §6).

---

## 1. Verdict

**The implementation is faithful to the specification on every registered object, and the agreement
with the reference is genuine** — the reference's Kuhn matching, alternating-path DM, oracle-built
canonical matching, Tarjan SCC and least-first-row block order are written from the definitions and
share no code with the graph layer, so block-for-block agreement on 24 blocks with every `depends_on`
list, the signature's lifted-block indices and the twelve ancestor blocks is two derivations meeting,
not a fixture matching itself. Two places are exceptions and are named below: the copy-row shape test
is loose in both the reference and the implementation (M4, a shared misreading of my §8.2), and the
*set* of phase-selecting units is named by hand in the reference (`PHASE_SELECTING_UNITS`), so only
the ancestry rule is independently derived, not the identification (N1).

**It is not done.** Outside the registered cases there are three paths that return a wrong result
silently, and one that returns `READY_FOR_SIMULATION` without having looked — each *measured*, each
reproducible from the repository, each the kind of thing the repository's rules name: no placeholder
success paths, no silent pass.

1. A flowsheet with two recycle loops through one unit — the most common industrial topology after a
   single loop — gets a single tear that leaves a recycle in the "inner" system; the reference has the
   correct criterion and the implementation does not (M1).
2. A SYN-001 revision with the flash at 150 kPa — K03 §7.2's registered conflict, expressed as a
   revision document — validates `READY_FOR_SIMULATION` with both certificates "consistent", because
   the binding feeds the flowsheet one pressure and drops the flash's value (M2).
3. A revision the analysis cannot bind or trace validates `READY_FOR_SIMULATION` with every `STR`
   check `NOT_RUN`, against §12.4 and A20(a) (M3).
4. A two-column pressure row with two `+1` coefficients is accepted as a copy row and given a
   certificate whose identity is false at every state (M4).

The verification has holes the manifest does not show: A20(b) has no test and is recorded `pass`;
A19 has no test at all and is recorded `unsupported` for a reason the specification rejects; one
test contains a `pytest.raises` that raises what it catches; the "not ready" test never asserts the
status; the manifest lacks six of the twenty-six assertion entries (M5).

The four rulings in brief §3 were implemented as I meant them. The refinement in §3 (an inconsistent
row is not in `E`) is correct. The `_Forest` re-rooting is correct (N2). The certificate without K03's
two-state witness is sound exactly to the extent M4 is fixed (N3). The signature ancestry reading is
the one §9.6 intends (N5). On brief Q5, the row-kind criterion for a phase-selecting unit is an
acceptable T01 answer and not a coincidence, with an obligation attached (N1).

What I did not examine: `scripts/t01_evidence_manifest.py` beyond what it claims for A19/A20/A25;
the K06 CLI beyond the diff; `docs/T01_STATE.md`; whether K03's own `_Forest` shares M4 (out of
scope per brief §6, but see T02 §6).

---

## 2. Must-fix findings

### M1 — `breaks_loop` tests the wrong thing, so a second recycle through a unit is torn once and left looped

**Where.** `src/process_runtime/graph/tear.py:230-238`:

```python
still_looped = any(
    set(component) == inside
    for component in _strongly_connected(list(units), remaining)
)
```

This asks whether the SCC is *still exactly the original set*. §9.2 asks whether the edge is a
single-edge feedback set — whether removing it leaves the loop's subgraph acyclic. The reference has
the correct criterion, `docs/derivations/scripts/t01_reference.py:1065`:
`breaks = not any(len(c) > 1 and set(c) & loop_set for c in scc(units, oe))`. SYN-001's loop is a
simple cycle, so the two criteria agree on every registered case and A14 cannot separate them.

**Measured.** Units `F, A, B, C`; connections `F→A, A→B, B→A, B→C, C→B` (two edge-disjoint cycles
sharing `B`: a unit with two recycles). SCC `{A, B, C}`. Removing any one of the four cycle edges
leaves a two-node SCC — the reference says `breaks_loop = False` for all four and the loop is a
`multi_edge_feedback_set`; the implementation says `breaks_loop = True` for all four, chooses one
by the score chain, removes its tear rows, and the "inner" system still contains a recycle. If that
inner system happens to be perfectly matched, `signature_units` is computed on it as if it were
acyclic; if not, S6 applies and the signature is silently `()`.

**Consequences.** The `multi_edge_feedback_set` result of §9.4/§12.4 is reachable only for a loop
that stays strongly connected after *any* single edge removal (a bidirectional triangle), which is
not the case the rule was written for. Nothing in `tests/test_t01_structural.py` reaches it — there
is no A20(b) test — and the manifest records `T01.A20: pass` from the nominal and conflicting cases
alone (`scripts/t01_evidence_manifest.py:530`).

**Correction.** `still_looped = any(len(component) > 1 for component in _strongly_connected(list(units), remaining))`
(the edges are already restricted to the loop's units). Add the fixture above as the A20(b) test
asserting `loop.unsupported == "multi_edge_feedback_set"`, `chosen_stream is None`, and that the
report's `unsupported` carries the loop; add one positive fixture where exactly one edge breaks a
two-cycle loop: `A→B, B→A, B→C, C→A` — only `A→B` is a single-edge feedback set (removing `B→C`,
`B→A` or `C→A` each leaves a cycle), while the current code calls all four "breaking" — so that the
criterion is pinned from both sides.

### M2 — A revision's flash pressure is dropped by the binding; K03's registered conflict validates as closed

**Where.** `src/process_runtime/application/binding.py:378-424` (`_flowsheet_settings`) reads one
`pressure` from the specification targeting `S1.P` and passes it to `Syn001Flowsheet`, which uses it
for the feed *and* the flash. The specification targeting the flash's `outlet.P` (`SPEC-flash-P`,
columns `S4.P`, `S5.P`) is used only to *match* the unit's existing `FLASH-P:*` rows to a
specification id (`binding.py:261-266`); its **value is never read**.

**Measured.** `SYN-001-nominal.yaml` with `SPEC-flash-P.value` changed from `100000.0` to
`150000.0`, through `validate()`:

```
status: READY_FOR_SIMULATION
STR-04 PASS  2 certified redundant rows, all consistent.
bound U-FLASH.P_spec = 100000.0   (the revision said 150000.0)
```

This is the state K03 §7.2 registers as `SPECIFICATION_CONFLICT` with `m_e = −50 000 Pa`, and the
specification's §13 lists it as a case that reaches `SPECIFICATION_CONFLICT` "at validation" with
`STR-04 FAIL` and status `INVALID` (A07). The A07 test bypasses `validate()` by substituting the
parameter on the `ProblemSpec` directly, and its docstring says "no revision can express it". A
revision document expresses it in one field; the binding discards the field. A07 as registered —
`STR-04 FAIL`, `INVALID`, no solve attempted — is not met by any test.

**Correction.** The specification's value is the authority (ADR 0008 D1.3: specification values are
pinned parameters). After `flowsheet.spec()`, for every unit-pinned row whose column a `role: fixed`
specification targets, set that row's pinning parameter to the specification's value. The parameter
a pinned row reads can be discovered without naming it: evaluate `row.constant(recorder)` with a
mapping that records the keys it is asked for (`_Constant.parameter` reads `parameters[name]`), and
override those keys. For SYN-001 today that is `U-FLASH.P_spec ← value(SPEC-flash-P)`, and the
existing A07 fixture then runs through `validate()` and asserts `STR-04 FAIL`, `INVALID`, and the
compile spy of A03. If the override is judged out of scope for the narrow binding, the *minimum* is
`return None` with a reason whenever two specifications that the flowsheet folds into one parameter
disagree — an explicit unsupported result rather than a silent one — but that keeps A07 unreachable
through `validate()`, so I would do the override.

### M3 — A revision the analysis could not examine validates `READY_FOR_SIMULATION`

**Where.** `src/process_runtime/application/validation.py`: status is `INVALID` iff any check is
`FAIL`; `_structural` returns five `NOT_RUN` checks for an unbindable or untraceable revision; the
status set earlier (`READY_FOR_SIMULATION`) survives.

**Measured.** `SYN-001-nominal.yaml` with every `model.id` set to `unknown.model` →
`status: READY_FOR_SIMULATION`, `STR-01..05: NOT_RUN`. The same revision with `SPEC-feed-T`
removed (a genuinely under-specified declaration) → `READY_FOR_SIMULATION`, `structural_counts: None`,
reason "binding an arbitrary revision ... is not implemented".

**Against.** §12.4 row 1: "status not `READY_*`". A20(a): "status not `READY_*`". Blueprint §4.3:
`READY_FOR_SIMULATION` is conditional on a closed system. Before T01, K06 reported `READY` with an
explicit "not checked: ... needs T01" check, which was the honest form of "nobody can look yet". Now
that a look exists, `READY` with `NOT_RUN` reads as "looked and found closed".

**A finding against my own specification.** §12.3 says "`NOT_RUN` with the reason when the
analysis is unsupported. Status: ... otherwise the task status", which contradicts §12.4 and A20(a).
§12.4 and A20(a) govern; §12.3's sentence is amended to "status as F1 decides, never `READY_*`".
The test `test_a20_a_revision_that_cannot_be_bound_is_not_run_and_not_ready` has "not ready" in
its name and does not assert the status.

**Correction.** When any `structural_analysis` check is `NOT_RUN` and the task is a simulation, the
status is not `READY_*`. Which non-`READY` value is **F1** (§5); my default is `INVALID`, with
`STR-01`'s message stating that closure could not be established and why, and §11's sentence extended
to "*as declared, this is not shown to be a closed simulation task*". Add the status assertion to
the test that claims it, and one for the untraceable-row path through `validate()`.

### M4 — A two-column row with same-sign coefficients is accepted as a copy row and certified on a false identity

**Where.** `src/process_runtime/graph/certificates.py:192-197`:

```python
if len(over) > 2 or any(abs(value) != 1.0 for value in over.values()):
    uncertified.append(row_id); continue
positive = next((name for name, value in over.items() if value > 0.0), CONST)
negative = next((name for name, value in over.items() if value < 0.0), CONST)
```

`P1 + P2 − s` passes the shape test (two columns, both `±1`), is read as the edge `P1 − CONST`, and
`P2` is dropped. The same test is in `trace.py:305` (`is_copy_row`) and — a finding against my own
work — in `t01_reference.py:852` and in §8.2's wording "all `±1`, over at most two columns". The
telescoping argument of §8.2 needs *one `+1` and one `−1`* per two-column row; the wording does not
say so.

**Measured.** Rows of kind `pressure`: `p1: P1 − a`, `p2: P2 − b`, `p3: P1 + P2 − s`, parameters
`a = 100, b = 200, s = 300`. Result: `p3` certified with `equals = ((p1, +1),)`,
`constant_mismatch = −200`, `consistent = False` → `SPECIFICATION_CONFLICT`. With `s = 100` it would
be `consistent = True`, `p3` would join `E` and be removed from the closure count on the identity
`p3 ≡ p1`, which is false wherever `P2 ≠ 0`. Both outcomes are wrong; the second violates blueprint
§7.7 (a row discharged without a valid certificate). `UNC-1` does not reach this because `p4` has
three columns.

**Correction.** In `certify` and `is_copy_row`: a two-column row is a copy only if its two
coefficients sum to zero; a one-column row is a copy if its coefficient is `±1`. Amend §8.2's
sentence to "one `+1` and one `−1` (or a single `±1` column)" and `t01_reference.py:852` to match;
register the fixture above as `UNC-2` (`uncertified_affine == [p3]`, nothing certified). The
registered values do not change — `--check` confirms it — because no SYN-001 row has the shape.

### M5 — Tests and manifest entries that do not verify what they record

Each item is small; together they are why M1 and M2 survived a green gate.

- **(a) A20(b) has no test; the manifest says `pass`.** `grep multi_edge tests/` is empty. The
  manifest's `T01.A20` value is built from the nominal and conflicting cases only. Fix with M1.
- **(b) A19 has no test; the manifest says `unsupported` with the reason "expected: a registered
  revision that declares an uncertified affine redundancy".** The specification registers `UNC-1` as
  a *synthetic* on purpose (§13: "because unsupported must be a result"), the branch is reachable in
  ten lines (my probe built a `Declaration` by hand), and `STR-06` — the check that carries "not
  established" — is exercised by nothing. `grep -n "uncertified\|UNC-1\|STR-06" tests/` finds one
  assertion, that SYN-001 has none. Add the `UNC-1` test through `analyse_declaration` and a
  `validate()`-level test via a small hook that accepts a `Binding` (or assert on the check builder
  directly); record `T01.A19: pass`.
- **(c) `test_a21_...` contains a block that cannot fail:**
  `with pytest.raises(SpecificationError): raise SpecificationError(...)`. The assertion A21 wants —
  the bound heater has no `specified_duty` — is provable: `bind_revision` returning a `Binding` already
  proves the constructor did not raise; assert additionally that the bound flowsheet's heater has
  `specified_duty is None`, and delete the vacuous block.
- **(d) `test_a20_a_revision_that_cannot_be_bound_is_not_run_and_not_ready`** asserts neither the
  status nor its negation. Fix with M3.
- **(e) A25 says one `checks[]` entry per `T01.<AID>` including unsupported ones.** The manifest has
  twenty; A00, A12, A18, A21, A24 and A25 are absent (the limitation text says they are "covered by
  tests rather than by a manifest check", which is the thing A25 forbids). An entry whose evidence is
  a named test is still an entry.

---

## 3. Should-fix

### S1 — The trace conflates "no columns" with "is a literal constant"

`trace.py:203-206, 219-220, 229-230`. The literal test is `not columns and constant.literal is not None`.
`_Term.opaque(frozenset())` — a block output whose declared pattern names no input — has no columns,
`coefficients=None`, and `constant=_ZERO` with `literal=0.0`. *Measured:* `x * opaque(∅)` gives
`coefficients {x: 0.0}` (a literal scaling by zero); `x − exp(opaque(∅))` gives `coefficients {x: 1.0}`
with a non-literal constant that evaluates to `0.0`, and `TracedRow.is_specification_row` is **True**
for it. That is a block output silently promoted to a specification row with the wrong constant, and
from there to a certificate. SYN-001 has no such output (*measured:* every one of the nine blocks
declares inputs for every output), so it is latent; the day a block is evaluated at a parameter
temperature it is live. Correction: literal-ness requires `coefficients is not None`; `_Term.opaque`
carries a constant with `literal=None` whose `evaluate` raises, so nothing downstream can read a
number out of an opaque term.

### S2 — `==` and `!=` are silent escapes from the trace (brief §4.1's question)

`_Term` is a frozen dataclass with the generated `__eq__`. *Measured:* `token == 0.0` → `False`,
`token != 0.0` → `True`, no exception; a builder that writes `if parameters["r"] == 0.0:` takes the
`else` branch silently and the trace records the wrong incidence. The complete escape set, measured:
`bool`, `<`/`>`/`min`/`max`, `float`, `int`, `round`, `abs`, `**`, `%`, `//`, `hash`, `in` on a
set, `math.exp` all raise; `==`, `!=`, `is` and `isinstance` do not. Correction:
`@dataclass(frozen=True, eq=False)` with explicit `__eq__`/`__ne__` raising `TypeError`. `is` and
`isinstance` cannot be caught and should be named in the module docstring as the residual.

### S3 — Gate G05 compares a hand-picked subset of the report, not the R0 projection §12.2 defines

`run/identity.py:90-124` builds `projection["structural"]` from thirteen chosen fields. It omits the
block *order* and `depends_on` (the order-canonical object G05 exists to compare, §6.4), the DM parts,
the candidate rows, the unit-DOF table, `phase_selecting` and `ancestor_blocks_of_tear_rows`.
`StructuralReport.r0_projection()` (`report.py:398`) implements §12.2's definition — the whole
document minus the floats — and is used only by tests (A17). Two projections of one object, and the
gate uses the smaller. Correction: one dict→dict function (the body of `r0_projection`) used by both;
A17 and A22 then compare the same document, and a platform difference in the block order becomes
visible to G05.

### S4 — `ProcessGraph.column_owner` parses the column id, against R-019's text

`graph/process.py:283-288`: `head = column_id.split(".", 1)[0]`. R-019 says "No module under
`src/process_runtime/graph/` parses a unit, stream or row id". A15's bijection `id ↦ "X-" + id`
preserves the dot, and the grep looks for names, so neither test can see this. Ownership is what
§8.3 counts over, so a column named without the convention (`Q_heater`) would be owned by nobody and
vanish from the DOF table silently. Correction: `ProcessGraph` takes `column_owners: Mapping[str, str]`
supplied by the binding (which legitimately knows the convention; `_pinned_columns` and
`_state_columns` already live there); or narrow R-019's wording to what is true. I would move it.

### S5 — Every non-literal-affine row of a certifiable kind is reported `uncertified_affine`

`certificates.py:181-183`: `coefficients is None` → `uncertified`. The trace returns `None` both for
a parameter-scaled linear row (`P2 − r·P1`, which §8.2 wants listed) and for a nonlinear one (a valve,
`P1 − P2 − k·F²`, which is an ordinary equation). A valve of kind `pressure` would be listed as an
uncertified redundancy and `STR-06` would warn "consistency not established" about a row that is not
a redundancy at all. Correction: `_Term` carries `linear: bool` (true when every product involved at
most one variable-bearing factor and no transcendental of a variable-bearing term), and
`uncertified_affine` is issued only for `linear` rows.

### S6 — An inner system that is not perfectly matched yields an empty signature silently

`tear.py:302-313`: `inner_form is None` → `signature_units = ()`, `phase_selecting = ()`, with no
`unsupported` entry; the report reads "no phase-selecting unit upstream of the tear". With M1 fixed
this is reachable only through a defective tear; it should still be a named result:
`Unsupported(kind="inner_system_not_closed")` and `STR-05` saying so.

### S7 — `not_implemented` is used to mean "not applicable"

`analysis.py:170-178` records `kind="not_implemented"` when the finding is not closed, and
`test_a20_what_is_not_applicable_is_named_rather_than_left_out` pins the label. A20(c)'s
`not_implemented` is for an increment that has not shipped. Add `not_applicable` to `Unsupported.kind`.

### S8 — `STRUCTURAL_UNDER_SPECIFICATION` is unreachable through `validate()` for any revision

`_flowsheet_settings` returns `None` when any of the nine SYN-001 parameters is missing, so a revision
that omits a specification — the under-specified case — is "unbindable" (M3's path) rather than
`STR-02 FAIL`. The finding exists and is tested only on `UND-1` at the partition level. Record it in
the manifest's `limitations` now; the fix belongs to the general binding (K06/T02, with ADR 0002
D2.7's obligation).

### S9 — Compile count and complexity notes

- `run/session.py:70` and `:99` each construct `Syn001TearProblem(flowsheet)`, a compile each, on top
  of the one inside `solve_tear`: three compiles per run where one would do. Pass the metadata from
  line 99 into `_structural_report`.
- `matching.canonical_matching` is `O(C · deg · M)` with `M` a full augmenting-path matching per
  trial; `maximum_matching` builds `by_column` in `O(R·C)`; `BlockTriangularForm.index_of_row/column`
  are linear scans called per column in `_signature` and `_in_coupled_block`. Trivial at 47 × 49;
  quadratic-and-worse at the flowsheet sizes T02 will meet. Not a T01 defect; T02 should budget it.

---

## 4. Notes (no change required)

- **N1 — brief Q5, the phase-selecting criterion.** Detecting a phase-selecting unit by a declared row
  of kind `molar_flow_squared` is a declaration-based criterion and not a name, so it survives A15 and
  is a defensible T01 answer; it is also the structurally right proxy today, because that kind exists
  for the division-free equilibrium row and that row is what a phase regime governs. It is a proxy:
  a second-order kinetics row could carry the same kind without selecting a phase, and the reference
  names the units by hand (`PHASE_SELECTING_UNITS`), so the agreement on the *set* is not independent
  — only the ancestry given the set is. Record the criterion in `provenance`
  (`phase_selecting_criterion: "row kind molar_flow_squared"`) and hand T03 the obligation to replace
  it with an explicit declaration on the unit, in the same place K03's `SIGNATURE_UNITS` lives.
- **N2 — `_Forest.link`/`path` (brief §4.3).** Verified by derivation: `_edge[node] = (row, s)` means
  the row's variable part is `s·(parent − node)`; re-rooting reverses each edge with `−s`, reading
  each edge before it is overwritten; `path` walks both sides to the meeting node with signs `−1`
  and `+1`, so the signed sum is `(meeting − negative) − (meeting − positive) = positive − negative`.
  Correct, and A06 confirms it against K03 at five variants.
- **N3 — the certificate without the two-state witness (brief §4.2).** Sound, given M4: with one
  `+1` and one `−1` per path row the variable parts telescope identically and
  `m_e = c_e − Σ σ_k c_k` is what `certify` computes. The `CONST` node handles the single-column
  rows as edges to the constant. The gap is exactly M4 and nothing else.
- **N4 — brief §3, "an inconsistent row is not certified".** Correct reading of §8.2; the reference's
  `certified_rows: []` at 150 kPa means exactly that.
- **N5 — the ancestry reading (brief §4.4).** "A block the tear rows read" = the blocks containing
  the columns the tear rows reference, closed under `depends_on`; `ancestors_of` includes the seeds,
  which is §9.6's "or contains". Correct.
- **N6 — small inconsistencies.** `validation.py` provenance says "increment 1"; `Check.evidence_class`
  defaults to `"structural"` on `SCHEMA-01`, `GRAPH-*`, `COMP-*` and `COND-01`, where the schema's
  description reserves it for rank/conflict searches — emit it only on `structural_analysis` checks;
  `STR-06` is outside §12.3's table (acceptable; the specification will list it when next touched).
- **N7 — A11 on SYN-001.** Minimality is by the oracle construction, which the implementation *is*;
  enumeration covers `TIE-1` and `SQ-1` only. Fine; the test docstring should say so.
- **N8 — A12.** The test checks DM invariance under twenty permuted matchings, not the full order-class
  table with `model_version` changing; the manifest says so. Acceptable for T01.
- **N9 — `trace.py` `__mul__` with a parameter token.** A parameter times a variable-bearing term
  correctly loses the literal-affine form and keeps the incidence; `x − x` keeps its column with a
  zero coefficient, as the docstring promises. *Measured.*

---

## 5. FOR FRANK

### F1 — What status does a revision get when the structural analysis could not run? (M3)

The frozen `validation-report` schema has three statuses. When the analysis is `NOT_RUN` (revision
not bindable in v0.1; a builder the trace cannot follow):

- **(a) `INVALID`, with `STR-01 NOT_RUN` carrying the reason** — *recommended default.* Honest:
  closure was not established, so the task is not ready. Consequence: `validate` exits 1 for every
  non-SYN-001 revision until the general binding exists, and §11's sentence becomes "as declared,
  this is not *shown to be* a closed simulation task".
- **(b) `DRAFT`** — reuses a status whose meaning is "no specifications"; misleading.
- **(c) A fourth status (`NOT_ANALYSED`) by Fable ADR** — the clean answer, a frozen-schema migration
  (specification Q1). Recommended when a second consumer needs the distinction at status level; not
  now.

Nothing else in this review needs a decision of yours.

---

## 6. What T02 inherits

1. **The tear rule is single-edge by design (§9.4) and must be single-edge in fact (M1).** Until M1
   lands, `breaks_loop` is not a feedback-set test and T02 must not build a sequencing strategy on it.
   After M1, a `multi_edge_feedback_set` loop is T02's to sequence (nested loops, minimum feedback
   sets), and the report names the loop.
2. **The attempt-signature rule is derived, and its "phase-selecting" premise is a proxy (N1).** T03
   owes the explicit declaration; until then K03's `SIGNATURE_UNITS` and T01's `signature_units`
   agree by a test, not by construction.
3. **`structural-report.json` is in every bundle** (Q4 decided yes). After S3, G05 compares the whole
   R0 projection including the block order. T02's execution plan should cite the report's
   `block_triangular_form` and `tear` rather than recompute them.
4. **Specification values are parameters and the binding must honour every one of them (M2).** The
   general revision binding (K06/T02) inherits the recorder-mapping mechanism for discovering which
   parameter a pinned row reads, and ADR 0002 D2.7's `compiled-problem-structure-v2` obligation.
5. **`STRUCTURAL_UNDER_SPECIFICATION` is reachable only synthetically until the general binding (S8).**
6. **Q2 — K03's `rank.py` consuming T01's certificates.** A06 is green at five variants with the
   mismatches agreeing to `1e-6 Pa` (floor `1e-11`). The route is open *after* M4, and K03's own
   copy-row test should be checked for the same same-sign gap when it is next touched.
7. **The trace's contract for unit authors:** a builder may not compare a parameter, branch on it,
   or convert it; after S2 the trace refuses `==` as well. Blocks evaluated at parameter-only inputs
   need S1 first. Parameter-scaled linear rows need S5 if T06 wants them listed.
8. **Performance envelope (S9):** matching and block lookups are quadratic; adequate to a few
   hundred variables, not to a plant. T02 should measure before the first large flowsheet.
