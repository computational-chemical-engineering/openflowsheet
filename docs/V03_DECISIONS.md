# V03 build decisions

Build-lane choices the release specification (`docs/derivations/V03-release-spec.md`, ADR 0053 Proposed) left to the
engineer. One line each, as `DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.`; each sits in its own
commit. Questions for the design lane are under "Open questions"; measurements under "Run log".

## WO-1: `scripts/v0_3_gate.py`, the registration, A10's pairs

- DECISION: how are the registry, the line name and the specification texts made parameters of `v0_2_gate.py`'s
  engine? → a `ReleaseLine(name, gate_sets, description)` passed as an optional last argument to `gate_set_of`,
  `not_covered`, `build`, `text`, `markdown` and `main`, resolved at the call (`None` is v0.2's line over the module's
  current `GATE_SETS`, so M07.A30's monkeypatch still bites); and an optional `GateSet.specification_texts` that
  overrides the `_SPECIFICATION_TEXTS` lookup (S13's `("the V03 release specification", "§4")`). `v0_3_gate.py` wraps
  each function with its own line. Alternative: add S13 to `_SPECIFICATION_TEXTS` and copy the report functions.
  Reversible by: `fba31939` (engine) and `c5b2486b` (script).
- DECISION: the shape of `benchmarks/v03/registration.json` → `gate_set` holds the M07 `_fields` keys plus `name` and
  `specification_texts`; `versions` is T-V3 as M07's `{version, gate_set}` rows; `rc_steps` M07's `{step, what,
  assertion}`; `ship_set` is `{ships, repository_only}` with §9.1's brace patterns expanded to the ten files. Written by
  hand (the spec says "transcribes"); no generator. Alternative: a generator with `--check`. Reversible by: editing the
  file and `tests/test_v03_v0_3_gate.py`.

## WO-2: the Wilson ship set

- DECISION D-1: how does a wheel read the packaged records without editing `thermo/wilson_ig.py` (S11.A75 pins its
  bytes; its `implementation_sha256` enters v1's and v2's identity)? → the callers resolve the path:
  `revision_binding.basis_provider`, `_wilson_refusal` and `certificate._wilson_provider` pass
  `resources.packaged_path(wilson_ig.RECORDS_PATH)` (a checkout resolves it through the `_data` link to the same bytes).
  Consequence: `WilsonIdealGasProvider()` with no argument still finds a source checkout only; a library user of the
  library-only v1 passes `packaged_path(RECORDS_PATH)`. Alternative: make `load_records(None)` read package data (pr_c1's
  pattern), which edits v1, moves both providers' `implementation_sha256` and breaks S11.A75. Reversible by: `365607f2`.
- DECISION D-4: what is "R-811's wheel refusal row"? → the wheel case of `_wilson_refusal`'s `basis_unavailable`: a wheel
  now has the records, so it binds. The typed refusal stays for an installation with neither copy, its hint naming R-880
  instead of "repository-only until Frank's Q-F3". Alternative: delete the branch, so a missing file raises untyped out
  of the binder. Reversible by: `365607f2`.
- DECISION D-2: T08.A32 (no third-party data in the artifacts) → Wilson's two files join `ATTRIBUTED_DATA` under R-617's
  rule, each with its hash and its own NOTICE strings, with per-file controls (pre-Wilson NOTICE, changed bytes), in
  wp/E01's structure. Alternative: a design-lane erratum first, as R-617 was for S05. Reversible by: `0977e3aa`.
- DECISION D-3: S10.A28 ("no S10 records file is packaged") → inverted for the ship set as S05.A26 was for R-616: S10's
  `PACKAGED` entries are exactly the two §9.1 files, and every other file under `benchmarks/s10/` stays out.
  Alternative: the design lane rewrites A28. Reversible by: `9bd23e9a`.
- DECISION: NOTICE's IPCC block → not added by WO-2: wp/E01's NOTICE already carries it (`IPCC AR6 WG1 Chapter 7, Table
  7.15`), so adding one here would print it twice after E01's merge. `test_v03_wilson_ship.py` asserts each IPCC string
  once exactly when E01's GWP file is in `PACKAGED`, and zero times before. Alternative: add it now and drop E01's on
  merge. Reversible by: appending the block.
- DECISION: the envelope's texts that WO-2 makes stale (L40, "one third-party data file"; L-S11-3, "in a wheel binding is
  refused `basis_unavailable`") → left to WO-4, which edits the envelope's U02 text at K3 after E01's merge (E01 rewrites
  L40 too, so editing it here would conflict). Alternative: edit both texts and re-emit `docs/support-matrix.md` now.
  Reversible by: n/a (no change made).
- The records file's header ("Not package data and not shipped until … Frank decides") is left as a recorded erratum in
  `docs/attributions/wilson-ig-v1.md`: an edit would move `data_sha256`, which R-880 keeps.
- `docs/s10-rights-check.md` §3 already agrees with §9.1 (the spec author's edit at `d60f7f73`); no change.

## WO-3: the roles (ADR 0054), MR-12 v03, the RC CoolProp step

- The roles (§10.3 steps 1–4) are `0461c6ec`, 0054 in `required_adrs` is `d5586f29`; both as the spec prescribes, no
  choice made.
- DECISION: where MR-12 v03 lives and where its check results come from → `mr12_extras_v03` and
  `_m_mr12_extras_v03` in `scripts/m07a_evidence_manifest.py` beside the v02 measure (`MEASURES["mr12_extras_v03"]`,
  not in `SPECS`), over its own table `MR12_AUDITS_V03` (R-879 rejects editing the v02 table). Each entry is §9.3's
  audit (file + `audit_section`), inventory, decision, and `check` = the command; the check's result is read from
  step 17c's RC record `step17/rc-step17c.json` (`checks[].id` = the command, provenance commit = C), in step 14's
  pattern. `test_the_git_backed_measure_at_head` (node name kept; S07's manifest maps it to A44) now runs the v03
  measure at HEAD over a synthetic 17c record. Alternative: the measure runs the two check scripts itself at the
  checkout. Reversible by: reverting the MR-12 v03 commit.
- DECISION: what is "the RC's test step" of F-8 (V03.A15, step 17b)? → a new CI job `rc-coolprop` (RC dispatch,
  `inputs.rc`, both architectures): `requirements.lock`, then `requirements-coolprop.lock` with `--no-deps
  --require-hashes`, then the project; T08.A43's build Python as `OFS_S07_BUILD_PYTHON` (else S07.A29's
  sdist/wheel test skips); then `pytest -rs` over every `tests/test_s07_*.py`/`tests/test_s11_*.py` naming CoolProp
  (`grep -lE 'CoolProp|s07_coolprop_support'`, 14 modules today) with `OPENFLOWSHEET_REQUIRE_COOLPROP=1`, failing on a
  non-zero exit or any `N skipped`. `tests/test_v03_rc_coolprop.py` reads the job (A15) with three controls. A job of
  its own so `rc-steps`' A30 inventory still reads the base install. (The `check` job, RC step 1, already has the two
  lines; its suite does not set the build Python, so its S07.A29 skip remains.) Alternative: add the steps to
  `rc-steps`. Reversible by: reverting the RC CoolProp commit.
- DECISION: `tests/test_t07_w5c_signatures.py::test_binding_outcome_is_unchanged[S11:TH-C1|TH-R1|GP-M1]` pin a SHA-256
  of the binding's structure, which includes `revision_sha256` (= the document's SHA-256), so the role correction moves
  them (spec §9.4 expects `revision_sha256` to move; its "no committed file contains the nine files' SHA-256" missed
  this indirect pin). → re-pinned, after proving that of the pinned structure only `revision_sha256` differs between
  the predecessor and the regenerated document for each of the three (and the predecessor reproduces the old pin).
  Alternative: stop for the design lane. Reversible by: reverting the re-pin commit (with `0461c6ec`).

## WO-4: ADR checks and flips, release texts

- DECISION: where "one check per ADR in S13's manifest" (spec §6) is recorded before S13's manifest exists (WO-6 writes
  it at C) → the table below; WO-6's generator transcribes it into `evidence/S13/<C>/manifest.json`. Alternative: a
  committed JSON for the generator to read. Reversible by: moving the rows.
- DECISION: what "the `COOLPROP-DEF-ref-v1` line of S07 spec §3.5" is (F-1) → §3.5's four definition bullets,
  verbatim, joined into one item (the fifth bullet only says F-1 writes the line), as ADR 0001 D5 item 5 and an S07
  paragraph in `interfaces-frozen.md` §3 in ADR 0045's pattern (`7ccb13a3`). Alternative: the identifier alone.
  Reversible by: reverting `7ccb13a3`.

| ADR | Condition (spec §6) | Checked 2026-10-30 against | Result |
| --- | --- | --- | --- |
| 0046 | manifest `tested` both architectures; reviewer passed provider and generator; Q-1 with its number; Q-S07-1; F-1 written; Amendment 1 in the manifest | `evidence/S07/7bfab70d…` (A01–A50 pass, A33–A35 pass; `S07.ci`: S07 steps success on both `check` jobs; `S07.gate` `unsupported` by design); `docs/reviews/S07-review.md`, `S07-generator-review.md`; ADR status Q-1 note (R-627); Frank 2026-10-23; `7ccb13a3` | met → **Accepted** |
| 0047 | WO-S10-1/2 manifest `tested` covering A01–A28; `s10_reference.py --check`; reviewer passed | `evidence/S10/c4f3751e…` (A01–A45 pass); `--check` at `wp/V03`: "113 claims hold; reference_values.yaml matches", exit 0 (again at C by the RC); `docs/reviews/S10-review-wo1-wo2.md`, `S10-review-final.md` | met → **Accepted** |
| 0048 | manifest `tested`; G1, G2; full gate and CI at merge; reviewer read the ADR | `evidence/S08/6d7d1a6d…` (G1, G2 pass); merge `d96c17ae`: gate PASS `f5565a34` 12356/3137, CI 40248543872 green both architectures; `docs/reviews/S08-review.md` | met → **Accepted** |
| 0049 | manifest `tested` with G1–G9; reviewer passed WO-1…4 | `evidence/S10c/2aedd250…`, `8f38f963…` (G1, G1-flowsheets, G2, G-R3, G-R7; G3 by A60/A61; G9 in WO-4); merge `8654aabc` gate PASS 13249/3137, CI 40315691647; `docs/reviews/S10C-review.md` (must-fix F1 carried by A60/A61) | met → **Accepted** |
| 0050, 0051 | Accepted **after** V03.A24 holds at C | — | not yet: stays Proposed until C |
| 0052 | after E01's merge (`05363060`) and V03.A24 | E01 merged | not yet: V03.A24 is at C |
| 0043 | stays Proposed | — | unchanged |
| 0053, 0054 | at WO-8 | — | unchanged |

## Open questions (for the design-lane review of WO-1–WO-4)

1. D-1: is "a bind of `wilson-ig-v1` from package data" (V03.A12, A19) satisfied by `WilsonIdealGasProvider(
   packaged_path(RECORDS_PATH))`, or must the no-argument constructor read package data (an edit to v1 that moves
   identity and needs S11.A75 amended)? Default taken: the former.
2. D-2, D-3: the build lane amended two other packages' assertions (T08.A32, S10.A28) by their established patterns
   (R-617, R-616). Confirm, or issue errata.

3. MR-12 v03's `lca` decision: spec §9.3 names R-870, which on `main` is "results computed from a restricted LCA
   table may reveal its scores" (E01 review item 3), not a licence decision for the `lca` extra. The register has no
   entry deciding the extra's licences (the audit is `docs/E01B_DECISIONS.md` D04; the extra itself is R-857).
   Default taken: transcribed R-870 as the spec says (the register check passes on it). Proposed: cite R-857, or
   register the WO-B1/D04 licence acceptance as its own entry and cite that.

## Merge notes for E01 (expected conflicts, all additive)

- `NOTICE`: E01 and WO-2 each append a block after the IAPWS block; keep both. `PRE_E01_NOTICE_BYTES` and
  `PRE_WILSON_NOTICE_BYTES` (both 2237) stay valid in either order.
- `tests/test_t08_w2_inventory.py`: `strings = …get(path, IAPWS_ATTRIBUTION)` becomes
  `{**E01_ATTRIBUTION, **WILSON_ATTRIBUTION}.get(path, IAPWS_ATTRIBUTION)`; the two loops of controls are kept.
- `src/openflowsheet/resources.py`, `pyproject.toml`, `tests/test_t08_w4_package_data.py`: both lists grow; the
  packaged-file count becomes 15.

## Run log

- 2026-10-29, WO-1: `v0_2_gate.py` output before/after the engine change, 18 runs (text, `--json`, `--markdown` over
  candidates v0.2.0, v0.2.0a1, HEAD and C; an uncovered version; the journey carry; a bad `--rc`): `diff -r` equal.
  `test_m07_v0_2_gate.py` + `test_m07a_v0_2_gate.py`: 296 passed before and after; with `test_v03_v0_3_gate.py` and
  AM-07 (`test_m07a_changelog.py`): 374 passed. Five mutations of the script or the registration fail 1–4 tests each.
- 2026-10-29, WO-2: packaging modules (T08 W2/W4, S10 provider/records, S11 bases/wilson v2, S05 envelope, L01/M01
  records, S07 registration, M07a harvest, T08 RC): 852 passed, 12 skipped, 1 failed (T08.A32 before the links were
  staged; passes after). `test_v03_wilson_ship.py`: 25 passed; three mutations (NOTICE, a rights cell, `PACKAGED`)
  each fail.
- 2026-10-29, WO-2: `scripts/s11_identity.py` at `162b0dd8` FAIL `changed=[]`, the branch-only shard non-zero:
  `test_s11_routing.py::test_a09_a_wilson_revision_without_its_records_is_unavailable` (the second test of the old
  refusal; fixed in the D-4 follow-up). At the follow-up: `S11-IDENTITY PASS n=54494 changed=[]`; every shard exit 0
  in both trees (branch 14417 passed, 3204 skipped; base 13288 passed, 3137 skipped).
