# C12 — rights check of the `pr-lib-v1` record sources, attribution file, then T08.A32 (build lane, then design lane)

Branch `wp/C12` from `main` `f880582`. Source: `docs/CLOUD_WORK.md` C12; Frank's answer L01-Q4
(`docs/FRANK_QUESTIONS.md:18`): no release ships the nine `pr-lib-v1` records until a **per-source rights check**
(JANAF/NIST, NASA via Cantera, Cantera, CoolProp, `chemicals`, ATcT citation) and an **attribution file** exist and the
design lane amends T08.A32; then they may ship. Register numbering: **R-575…R-579**.

## Facts with anchors
- Records: `benchmarks/l01/components.yaml` (nine records; each has `rights: {source, redistribution, notes}`, e.g.
  H2O at :469-485); cross-check record `benchmarks/l01/components-crosscheck.json` and script
  `benchmarks/l01/components_crosscheck.py` (which values came from which tool/version).
- Policy: ADR 0006 (`docs/adr/0006-distribution-data-rights.md`; D1 what may be distributed, D5 notice obligations
  :90-97); `NOTICE`; M01's precedent (M01 spec §3.4, `docs/derivations/M01-spec.md`).
- T08.A32 as amended by S04 (R-529; `tests/test_t08_w2_inventory.py` A32) admits a second vetted record file with a
  rights statement per record; packaging of the records waits (R-541, L01-Q4).
- The source packages are installed in `/home/user/venv-l01-sources` (chemicals 1.5.2, Cantera 3.2.0, CoolProp 8.0.0):
  their licence files and the data files' headers can be read there. Public terms pages (NIST/JANAF, ATcT, NASA
  TM-4513) may be fetched read-only; quote what they say with the URL and retrieval date.

## Do (build lane)
1. `docs/l01-rights-check.md`: one row per source × what L01 takes from it (which values, how many, which records),
   the licence or terms text that governs it (quoted, with file path or URL + date), whether redistribution of those
   values is permitted and under which conditions (attribution, notice), and open doubts. State facts; this is not a
   legal opinion. A source whose terms cannot be established is marked `unresolved`, never assumed permitted.
2. An attribution file (`docs/attributions/pr-lib-v1.md`, or a NOTICE section — DECISION) listing each source with the
   required citation/notice text, and a test that every source named in any record's `rights.source` appears in it.
3. A short work order / question list for the design lane: what A32 should additionally require (e.g. the
   rights-check row ids per record, the attribution file), for the follow-up specifier step.

## Exit test
The two documents, the test, `tests/test_l01_*.py` and `tests/test_t08_w2_inventory.py` pass; ruff/format clean.

## Out of scope
Packaging or releasing the records; amending A32 (design-lane step after this); legal conclusions beyond quoting terms.
