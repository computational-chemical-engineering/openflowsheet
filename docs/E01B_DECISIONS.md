# E01 track B — build decisions and facts

Normative: `docs/derivations/E01-design.md` (ADR 0052; R-850…R-867), §4.8, §5.3, §6, §9. One line per choice:
`DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.` Facts carry their source (file hashes for
packages; URL and retrieval date for data). The design-lane ruling round is folded into E01's single `reviewer` pass.

## WO-B1 (rights, extra, adapter)

### Facts (retrieved 2026-10-27; no personal identifier sent; user agent `OpenFlowsheet-build`)

- FACT (pins): bw2data **4.7** (PyPI 2026-05-14; wheel sha256 `e88f1ccd8266fb7a8d1ecd14abfe163a4533b1cd4b4b88269a569da1f8a2021c`)
  and bw2calc **2.5.0** (2026-05-16; wheel `2c26420e223871a50d45532e63a1506116cfede0a8fc071cbd043fc347f4beee`): the
  newest releases at least two weeks old (bw2data 4.8 of 2026-10-19, bw2calc 3.1.0/3.0.0 of 2026-10-18/14 are too new).
- FACT (licences): bw2data 4.7 `licenses/LICENSE` sha256 `966d484abb7c9601d38b3797695be4ccd24199e95b3c43346fc668204ad622d5`
  (BSD-3-Clause text, "Copyright 2024 Chris Mutel"; METADATA declares no licence); bw2calc 2.5.0 `licenses/LICENSE`
  sha256 `e3e590114822c8f110f6b0333ef0649494287680c2cb950d333f977e85bee2c8` (BSD-3-Clause, "Copyright (c) 2023, Chris
  Mutel"; `License-Expression: BSD-3-Clause`). Read from `pip download --no-deps` wheels in the scratchpad.
- FACT (closure): `benchmarks/e01/brightway/lca-pip.lock` = 32 distributions over requirements.lock, resolved by
  `uv pip compile --exclude-newer 2026-10-13` with requirements.lock as constraints, hash-pinned. No bw2io, pypardiso
  or MKL. `docs/e01-lca-licences.json`: 40 closure rows, 0 failures; 18 rows hand-audited (licence file read, SPDX id
  recorded with the file's sha256, `scripts/e01_d04_inventory.py` `AUDIT`). None GPL-family; tqdm is MPL-2.0 AND MIT
  (used unmodified, as certifi under T07 E5). Nothing of the extra is redistributed.
- FACT (IPCC): AR6 WG1 ch. 7 PDF (`IPCC_AR6_WGI_Chapter07.pdf`, sha256 `470d2662…febfa9`), Table 7.15 p. 1017, GWP-100:
  CO2 1.000, CH4-fossil 29.8 ± 11, CH4-non fossil 27.0 ± 11, N2O 273 ± 130 — all four §4.8.5 values confirmed.
  Rights: front matter (sha256 `e564ba9b…09e6`) says "© 2021 Intergovernmental Panel on Climate Change", no open licence;
  www.ipcc.ch/copyright/ returned HTTP 403 to every client tried. Shipped per D8 as five factual values with citation.
- FACT (USLCI, §7 Q6): the release repository `FLCAC-admin/uslci-content` (releases v1.2026-09.0 … ) is MIT, LICENSE
  sha256 `a680c9d5b66a37c42f309e2adff0af18aac3f379ac0b2b7d4153bb4801624649` ("Copyright (c) 2017 uslci-admin"); no CC0
  or US-public-domain statement in its README, docs or release notes; www.lcacommons.gov did not resolve (DNS). Also
  Brightway's import of USLCI needs bw2io, which the extra excludes. **Not shipped**; the recipe stays documentation.
- FACT (EF 3.1): eplca.jrc.ec.europa.eu's developer page redirects to knowledge-for-policy.ec.europa.eu, which states
  no terms for the EF reference package. Terms not confirmed → **EF factors not shipped** (D8 default).
- FACT (Brightway precision, blocks A24/A25 at their registered tolerances): bw_processing 1.6 stores every
  processed `amount` as float32 (`bw_processing/utils.py:79`), and `LCA.score` comes back float32: on
  test-background-v1 the adapter gives q_E 0.5472782254219055 (= 9181805/2²⁴), q_H 0.18911290168762207,
  q_X 0.9018649160861969, relative errors −7.0e-10, −8.1e-9, −3.6e-9 against the hand rationals. **A24 (rel ≤ 1e-12)
  FAILS** in the scratch lca env; A25 (rel ≤ 1e-10) cannot pass on this path either. Evidence for a remedy: the same
  system fed to bw2calc 2.5.0 as float64 datapackages (`bw_processing.add_persistent_vector`, float64 `data_array`)
  reproduces the hand values to 6e-17. See ESC-B1.

### Decisions

- DECISION: where the lca lock lives → `benchmarks/e01/brightway/lca-pip.lock` (B-owned path). Alternative:
  `requirements-lca.lock` at the root, like coolprop. Reversible by: moving the file and its two references.
- DECISION: the audited env → `scripts/build-lca-env.sh [prefix] [python]`, a venv of the project interpreter with
  requirements.lock (no hashes; it has none) and the hash-pinned increment, the checkout on `sys.path` by a `.pth` line
  (no build backend in the env). Built and used only as a scratch venv in this session, never in `.venv`.
  Alternative: conda. Reversible by: the script.
- DECISION: D04 records → `docs/e01-lca-licences.json` (packages, made in the lca env with T07's own `inventory`
  plus the hand audit) and `docs/e01-data-licences.json` (every file under `_data/assessment/**`, A's included);
  checker `scripts/e01_d04_inventory.py --check` (A42). Alternative: extend `t07_licence_inventory.py` (T07's file).
  Reversible by: deleting the script and records.
- DECISION: table files carry `format` (`unit-score-table-v1` | `direct-factor-table-v1`); `test-background-v1.json`
  carries its Brightway description as a member `brightway` inside the hashed table. Alternative: two files.
  Reversible by: `scripts/e01_lca_data.py`.
- DECISION: refusal codes for tables §4.12 does not name: a malformed table → `LCA_TABLE_INVALID` (new code); an absent
  or wrongly listed table → `LCA_ACTIVITY_UNKNOWN(<table>)`. Alternative: map both to `LCA_TABLE_HASH_MISMATCH`.
  Reversible by: `tables.py`. (Design lane to confirm the new code.)
- DECISION: adapter signatures gain keywords the note leaves open: `table_id` (both builders), `si_per_unit`
  overrides and `source`; `write_description(project, description)` added for the synthetic background; the A25
  check copies the project and deletes the copy (stronger than deleting the scratch database). Reversible by:
  `brightway.py`.
- DECISION: rights label in the report → `"<class>; redistribution <allowed|forbidden>; <licence>"` (the report schema
  has one string). Reversible by: `Rights.label`.
- DECISION: mypy override for `bw2data.*`, `bw2calc.*` (as M03's for pyomo). Reversible by: pyproject.

### Escalations (open, design lane)

- **ESC-B1 (A24, A25 tolerances vs Brightway's float32).** The registered tolerances (1e-12, 1e-10) are below what
  Brightway's standard path can deliver (float32 data and score; measured above). Options: (a) the adapter assembles
  A, B and C in float64 from the project's stored exchanges and characterisation factors (bw2data keeps float64 in
  SQLite) and hands them to bw2calc as float64 datapackages — then A24 passes (6e-17 measured on a hand-built
  datapackage), but A25's check shares that assembly; (b) restate A24/A25 at float32 data precision (~1e-7 rel); (c)
  keep A24/A25 and record them failed. Preferred: (a) for `build_unit_score_table` (the table is what the program
  uses; float32 tables would put 1e-8 errors into every impact), and for `foreground_check` keep Brightway's own
  processing with A25 restated at float32 precision so the check stays independent of our assembly. Not implemented:
  it changes how a frozen table's numbers are produced. A24 is committed at 1e-12 and fails in the lca env.
- **ESC-B2 (packaging of `_data/assessment/**`).** Adding the package-data glob breaks
  `test_t08_w4_package_data.py::test_the_package_data_patterns_cover_exactly_what_is_packaged` unless
  `resources.PACKAGED` gains the path, and T08's rule is that every packaged path is a *symlink* to a single
  repository copy (`test_each_packaged_path_is_a_link_to_the_single_repository_copy`), with directory entries
  matched by the test's own `DIRECTORY_FILES`. `_data/assessment/` holds real files (A's and B's). Doing it right
  moves the data to a repository path (proposal: top-level `assessment-data/`, `_data/assessment` a link to it),
  adds `"assessment"` to `PACKAGED`/`DIRECTORIES` (and `REPOSITORY_PATHS`), adds one line to the T08 test's
  `DIRECTORY_FILES`, and amends T08.A32 (`test_t08_w2_inventory.py` `ATTRIBUTED_DATA`/`SHIPPED_DATA`, with NOTICE
  attributions for SSLW/IDAES BSD, PrISMa CC BY, Eurostat CC BY and IPCC). It crosses A's files and T08's tests, so it
  is left to I1 with a ruling; nothing was changed. Until then a wheel does not carry the assessment data.
- **ESC-B3 (rights leak through θ listing).** The report's `uncertainty.parameters` lists the value of every θ that
  carries a declared range; a user who declares a range on `asm:lca.q.<forbidden table>.…` would print a forbidden
  score. B2 refuses such a range (see WO-B2), but `report.propagate` (A's) still lists it; a one-line redaction there
  is the fix.
