# Fable brief — T01 implementation review

**To:** `fable-reviewer`
**From:** the Opus session (Opus 5)
**Date:** 2026-09-23
**Design note under review:** `docs/derivations/T01-structural-spec.md` (yours, 2026-09-23)
**Commit range:** `f603e9b..df779b8` on branch `wp/T01`
**Evidence:** `evidence/T01/6f1f86d9c2dead94580032377af0be5e9b3b1e2e/manifest.json` — 19 pass, 0
fail, 1 unsupported, `status: tested`, `review` pending
**Deliverable:** `docs/reviews/T01-review.md`

---

## 1. What was built

Both increments of §12.4. `src/process_runtime/graph/` (new, 7 modules, ~1900 lines):

| Module | Specification |
| --- | --- |
| `trace.py` | §3.3 declaration-traced incidence: a set-valued structural algebra with the parameters opaque, and the affine-with-literal-coefficients classification |
| `matching.py` | §6 maximum matching, the lexicographically least maximum matching, the coarse DM partition |
| `certificates.py` | §8.2 the affine-copy certificate, issued from the declaration and the parameters |
| `dof.py` | §8.3 unit-local degrees of freedom and the bookkeeping identity |
| `blocks.py` | §7 Tarjan SCC, the canonical block order, block metrics |
| `tear.py` | §9 process loops, candidates, the score chain, the inner system, the signature rule |
| `report.py`, `analysis.py` | §11 the six statements; §8.1 the finding rule; §12.2 `StructuralReport` |

Plus `application/binding.py` (§5 the revision binding and specification promotion),
`application/validation.py` (§12.3 `STR-01`…`STR-05`), and the report written into every run
bundle and projected into R0 (§18 Q4, A22).

## 2. What I ran, and what it produced

Gate `PATH=.venv/bin:$PATH ./scripts/check.sh` green at **1397** (was 1320 before T01);
`tests/test_t01_structural.py` is 70 of those. `docs/derivations/scripts/t01_reference.py --check`
passes, 42 self-checks.

Every registered value reproduces. The agreement went further than I expected: the canonical
block order matches your reference **block for block including every `depends_on` list**, and the
signature's lifted-block indices (15, 19) and the twelve ancestor blocks of the tear rows are
identical. Since your reference is a hand transcription with algorithms written from their
definitions and no `process_runtime` import, I read that as two independent derivations agreeing
rather than as a fixture matching itself — but you are better placed than I am to say whether any
of it could agree for a bad reason.

Specifically: counts `{47, 49, 47, 2}` and `{47, 50, 47, 3}`; nnz 170 / 171; DM 7×5 and 44×41;
both certificates with `m_e = 0.0` exactly and their signed-row sets; 41×40 after certificates;
10 candidate rows over 9 specification ids; the unit-DOF table; `10 + 1 − 11 = 0` and
`11 + 1 − 11 = 1`; 24 blocks `[17, 8, 1×22]` with `largest_block_fraction` the registered double;
one loop, four candidates of dimension 3 at distances 2/3/4/1, `S6` by `boundary_distance`; inner
44×44 with 30 blocks `[8, 8, 1×28]`; `signature_units == (U-FLASH,)`, which a test asserts equals
K03's hard-coded `SIGNATURE_UNITS`.

## 3. Your four rulings, and what I did with them

- **4.1 overturned.** Confirmed independently before implementing: `r = 0` gives nnz 167 with
  exactly the three `SPLIT-recycle:i × S5.n.i` entries gone. The trace passes the builders
  *opaque parameter tokens*, because handing them real floats would reproduce the folding inside
  my own module. Registered as R-018.
- **4.2 confirmed.** §8.1's order, with one refinement I made and want checked: **an inconsistent
  row is not certified**. Your reference has `certified_rows: []` for the 150 kPa case, which I
  took to mean `E` admits a row only when `|m_e| ≤ τ`; my first version put both in
  `certified_rows` with a `consistent` flag, which would have let the closure count remove a row
  nothing justifies removing.
- **4.3 confirmed.** Declaration order throughout; the canonical matching is built by the
  constructive definition (least admissible row per column, feasibility tested by a matching
  oracle), and a test proves minimality by enumeration on the small fixtures.
- **4.4 confirmed.** Increment 1 carried matching + DM + certificate + unit DOF together.

## 4. Where I am least sure — please spend your time here

1. **The structural algebra (`trace.py`).** `_Term` carries `columns`, `coefficients` (`None` when
   not affine-with-literal-coefficients) and a `_Constant` with `literal: float | None`. The line
   between a literal and a parameter is `literal is not None`, and it is what decides whether a
   coefficient survives multiplication. I believe `columns` is never pruned by value and that a
   cancelling coefficient keeps its column, but that is the property the whole package rests on.
   Also: `__bool__`, `__lt__` and `__float__` raise, so a builder that branches on a value fails
   loudly — is that the complete set of escapes?
2. **The certificate without K03's two-state witness.** Your §8.2 argues the variable parts
   telescope identically because every path row has exactly two `±1` columns, so two probe states
   are not needed. I implemented that. If the argument has a gap, this is where it bites, and
   `certificates.py` is the file.
3. **`_Forest.link` and `path`.** I re-rooted the attached tree rather than reusing K03's
   `_Forest`, to keep the graph layer free of orchestrator imports. The signed paths agree with
   K03's at all five variants (A06) and with your reference as sets, but the re-rooting sign
   handling is the fiddliest code here.
4. **The signature rule's ancestry (`tear.py`).** "Its lifted block is an ancestor of a block the
   tear rows read." I read "a block the tear rows read" as the blocks containing the columns the
   tear rows reference, then closed under `depends_on`. It reproduces your registered indices, but
   the reading is mine.
5. **Phase-selecting units are detected by the `molar_flow_squared` row kind.** §9.6 defines them
   as "one that lifts a split" and your reference names them. I needed a criterion that survives
   A15's relabelling, and a declared kind seemed better than an id convention — it picks out
   exactly the two units. Is that the right structural definition, or is it a coincidence of
   SYN-001 that every phase-selecting unit declares an equilibrium row of that kind?

## 5. Two things I changed outside the specification, and why

- **`ValidationReport.Check` did not conform to its own frozen schema.**
  `schemas/validation-report.schema.json` requires `stage`, `result`, `message` and
  `implicated_objects` with `additionalProperties: false`; K06 emitted `id`/`passed`/`detail`/
  `scope`. Nothing validated a *produced* report against the schema, only the hand-authored
  fixtures, so it never surfaced. I made `Check` emit the schema's shape and kept `passed` and
  `scope` as derived properties. This is a conformance fix, not a schema change.
- **Assertion A15 found a real defect.** Row-to-unit attribution parsed the `U-` id prefix;
  relabelling emptied it *silently*, which would have emptied the unit-local count and with it
  the localization. The graph layer now parses no id at all and imports no unit model, with a
  grep asserting it (R-019). I mention it because it changed a signature: `trace_declaration` and
  `analyse` take `row_units`, and `Connection` carries `state_columns`.

## 6. What not to spend time on

Style and formatting (ruff and mypy strict are in the gate). The K03, K04, K05 and K06 code
outside the diff. The specification itself — it is yours and settled; if you now think a ruling
was wrong, say so as a finding rather than re-deriving it. The `U-PRODUCT`/`U-PROD` naming
difference between your reference and the repository: noted, affects nothing, recorded in
`docs/T01_STATE.md`.

## 7. Deliverable

`docs/reviews/T01-review.md`, in the shape of your K03 and K05 reviews: must-fixes numbered and
each reproducible from what is in the repository, should-fixes separately, and a closing section
on what T02 inherits. If a finding needs Frank, put it under `FOR FRANK` with options and a
recommended default and continue; I relay verbatim.
