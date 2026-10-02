# Brief — T08 release spec, Amendment R3: the rulings left before the release candidate

**To:** `specifier` (design lane). **From:** build lane, 2026-10-01. **Branch:** `wp/T08` at HEAD.
**Deliverable:** an "Amendment R3" section appended to `docs/derivations/T08-release-spec.md` (with in-place markers
"*(amended 2026-10-01, Amendment R3 n)*"), any amendment it needs in another authority document (appended, dated),
the generator `docs/derivations/scripts/t08_reference.py` + `benchmarks/t08/reference_values.yaml` updated so
`--check` passes byte-reproducibly, and register entry text (from **R-136**). Do not commit; no production code.

**Budget.** Frank is near his weekly usage limit. Eight bounded rulings; for each: decision, rejected alternative,
exact text. Do not re-derive.

## Context (one paragraph)

T08 is near its release candidate. Done: Phases 1–4 (record fixes; the kinetic CSTR and PTC-R1, V14 (b) FAIL accepted
by Frank, ADR 0021 D3 row; warm starts, V13 (e) B40–B49 MET, B50 amended by Frank R-134; envelope, harvest,
recovery-edge inventory with every row evidenced; the MCP description review, V17 carried R-133; A30 PASS on both
architectures after ADR 0006 Amendment 1 / R-135; A31, A32, A35 met; A89 20/20 aarch64 + 1 local; Phase 3 V19 facts
(being redone on the released reactor code); Phase 4 RC machinery: `scripts/t08_rc.py`, `scripts/t08_dist.py`,
`scripts/v0_1_gate.py`, CI dispatch inputs `rc`, `rc_distribution`). History: `docs/T08_DECISIONS.md` (grep the
dates/entries named below).

## Rule on these

1. **A45 — the T06 A34 set** (`T08-release-spec.md:477`). T06 A34 is a record replay on the same machine class and
   writes no bundles; per-start outcomes are not promised across architectures (L07). The engineer left A45 failing
   on it rather than shrink the set (Phase 4 entry). What stands for that part of the bundle set, or how is A45 read?
   The engineer's reading of the rest: "K05's registered SYN-001 runs" = the 5 registered variants via CLI `solve`;
   "G8" = the 47 eligible revisions — confirm.
2. **A49** (`:481`) names the descriptions digest `6d13e13d…`; the served surface is `171dd768…` (R-133, Frank's carry;
   R-134 amended B50 the same way, build-first spec Amendment 3). Amend A49 consistently.
3. **`docs/reviews/T08-verdicts.md` table shape** that `scripts/v0_1_gate.py` reads (one row per gate, a `Verdict`
   column, `Vnn (x)` clause ids and envelope L-ids in the row). Fix it in the spec so Phase 5's `verdict` writes it.
4. **ADR 0021 D2.4's tree check**: the engineer includes `pyproject.toml`, allowing only the version string to differ
   (`__init__.py`, `pyproject.toml`). Confirm or correct.
5. **An installed wheel has no `requirements.lock`** (`src/process_runtime/run/manifest.py:182`), so bundles written by
   an installed package replay `NOT_RUN` ("dependency set unknown on both sides"). An ADR 0007 D4 question: record a
   lock hash in the wheel, or a registered limitation for v0.1?
6. **T06 A89** (spec §6.1, Q4 default "amend A89 to the outcome with the count reported"): A89's case repeated 20× on
   `ci-aarch64` (CI 36868221999) and 1× on `ref-x86-64`, all CONVERGED, VERIFIED, ratio 2.166302692785393e-05, one
   refinement each (`benchmarks/t08/a89/`). Write the A89 amendment (append to the T06 spec).
7. **ADR 0006 D4 on aarch64**: CasADi's aarch64 wheel has two unresolved-notice objects not on x86-64
   (`libgfortran-8de1544a.so.5.0.0`, `libgomp-7eb2fb8b.so.1.0.0`), outside the required closure (A30 aarch64 PASS,
   `docs/t08-a30/t08-a30-aarch64.json`). Write the D4 addendum (ADR 0006 was never audited on aarch64).
8. **V19 H4 and A61's reading.** (a) The IDAES PR reference route works with the light gases vapour-only (IDAES's
   HC_PR convention); full PR VLE with all components in both phases lands on the trivial solution or fails
   (`benchmarks/t08/v19/c1-idaes.json`). Does vapour-only satisfy H4, or must M01's provider and reference handle
   dissolved gases (then root selection is an M01 derivation item)? (b) T08.A61 says "its own regression reference
   reproduced within the group's regression tolerance"; on the released reactor code (`main` @ `6089593`, v1.1.0) the
   group's suite is 72 pytest tests with no separate regression harness. Read A61 accordingly.

## Out of scope

Anything already ruled; Phases 1–4 internals; the dossier's scoring (after the W3.2 redo); tagging.

## Addendum (2026-10-01, after the W3.2 redo `1f7bc0d`)

Item 8 (b) facts on `main` @ `6089593`: the group suite collects 72 tests, **69 passed, 3 skipped** by their own
guards for data not shipped (`test_cp_closure.py:57` needs the 2D sweep's closure fit; `test_paper_pipeline.py:115`,
`:127` need the git-ignored `Dataset_paper/`); no test solves a full reactor. Tag `v1.1.0` points at `d78fbfb`, the
parent of `6089593`; model code identical. Also rule: (c) is 69/72 with 3 data-guarded skips enough for A61, or must a
published 4TU result be re-run and compared; (d) pin `6089593` or the tag commit `d78fbfb`; (e) may dossier item 5 and
H2 read `met` while Frank's K_NH3 check against Rossetti 2006 is pending (`benchmarks/t08/v19/c1-provenance.json`
keeps it a `discrepancy`)?
