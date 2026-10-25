# S10 rights check: the sources of the `wilson-ig-v1` real records (WO-S10-3, updated WO-S10-7)

**Status:** build lane (S10, branch `wp/S10`), 2026-10-25; brought up to the state after WO-S10-6 by WO-S10-7
(final review, S-2). **Facts and quoted terms, not a legal opinion.** Whether
any S10 file ships is Frank's decision (S10 spec §9.1 shipping rule, Q-F3). Format and verdict vocabulary: C12's
`docs/l01-rights-check.md`. Choices: `docs/S10_DECISIONS.md` (B-19…B-29).

**Files checked:** `benchmarks/s10/records.yaml`, `benchmarks/s10/fit-report.json`, `benchmarks/s10/records-lineage.json`,
`benchmarks/s10/saturation-points.json`, `benchmarks/s10/nasa7-low.json`, `benchmarks/s10/vle/kurihara1993_binaries{,.A,.B}.csv`,
`benchmarks/s10/vle/kurihara1993_ternary{,.A,.B}.csv`, `benchmarks/s10/validation/val3-eos.json`,
`benchmarks/s10/validation/report.json`, `docs/s10-validation-report.md`, `benchmarks/s10/reference_values_real.yaml`,
`benchmarks/s10/{idaes,dwsim}/inputs.json`, `benchmarks/s10/verification-records.yaml`. Not checked here: the tool
records `benchmarks/s10/{idaes,dwsim}/{qualification,comparison}.json` (IDAES and DWSIM output; no row covers those
tools' terms).

**How the terms were read.**
- *Local:* licence files and data-file headers in `~/.cache/of-rca-6fec822/venv-xcheck/lib/python3.13/site-packages/`
  (`SP/`), read as text. The licence hashes equal those C12 recorded for the same package versions.
- *The fit paper:* the PDF Frank supplied (2026-10-25), read page by page. It is not committed and no page of it is
  reproduced; only the transcribed numbers of Table II are in the repository.
- *Public pages:* none fetched in this work order. Rows that rest on a public terms page quote C12's workstation fetch
  of 2026-10-22 (`docs/l01-rights-check.md`, rows RC-01, RC-03, RC-04, RC-08).

## 1. Verdict vocabulary

- **permitted with conditions**: the governing licence text was read, it permits redistribution, and the conditions
  are listed.
- **permitted**: project-authored; no third-party source.
- **unresolved**: the governing terms could not be established from what was read. The reason is stated. This is not
  a finding that redistribution is forbidden.

## 2. Rights-check rows

| Row | Source | What S10 takes, and from where | Governing terms (quoted, with location) | Verdict | Open doubts |
| --- | --- | --- | --- | --- | --- |
| S10-RC-01 | **NASA TM-4513**: McBride, Gordon, Reno (1993) | Low-range NASA-7 a₁…a₆ of CH3OH (note `L 8/88`), C2H5OH (`L 8/88`), H2O (`L 8/89`), giving b₀…b₄ (5 × 3 = **15 values**) and Δ_fH (**3 values**, the polynomial's H(298.15 K)). Copied as the file's literals into `nasa7-low.json` from `SP/cantera/data/nasa_gas.yaml` (SHA-256 `4de6199d…67e4db`, checked by `s10_records.py --extract-nasa`). | `nasa_gas.yaml:1-14`: "The original source is: B.J. McBride, S. Gordon, and M.A. Reno, … NASA Report TM-4513, October 1993. https://ntrs.nasa.gov/citations/19940013151". NTRS record (C12 workstation fetch 2026-10-22, C12 RC-03): "Work of the US Gov. Public Use Permitted." | **permitted with conditions** (cite TM-4513): C12 RC-03 | None for these three species. |
| S10-RC-02 | **Cantera 3.2.0** (retrieval tool for RC-01) | No value is Cantera's own. Named in `provenance` and `rights.source`. | `SP/cantera-3.2.0.dist-info/licenses/License.txt` (SHA-256 `e92980b9…79c41bb`, the file C12 read), BSD-3-Clause: redistribution "permitted provided that … Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer". | **permitted with conditions**: C12 RC-04 | The licence does not speak for the data the tool carries (RC-01 does). |
| S10-RC-03 | **CoolProp 8.0.0** (MIT) and the reference EOSs it evaluates: methanol `deReuck-BOOK-1993`, ethanol `Schroeder-JPCRD-2014`, water `Wagner-JPCRD-2002` (`CP.get_BibTeXKey(fluid, "EOS")`, recorded in the points file) | `saturation-points.json`: **183 computed pressures** (61 per component), tool output of `PropsSI("P","T",T,"Q",0,fluid)`. The records hold only the **12 project-fitted** coefficients a…d (RC-07). `validation/val3-eos.json` (WO-S10-6, B-70, B-72): **66 computed values**, ΔH_vap = HMOLAR(Q=1) − HMOLAR(Q=0) and CPMOLAR(Q=0) at 11 temperatures per component (33 × 2), plus the **3 computed T_b**(101 325 Pa), the comparison side of VAL-3. No EOS coefficient is reproduced anywhere. | `SP/coolprop-8.0.0.dist-info/licenses/LICENSE` (SHA-256 `9bf83533…a4719b2`, the file C12 read), MIT, "Copyright (c) 2012-2018 Ian H. Bell and other CoolProp developers": "Permission is hereby granted, free of charge, … to deal in the Software without restriction, including … the rights to use, copy, modify, merge, publish, distribute … subject to the following conditions: The above copyright notice and this permission notice shall be included …". | **permitted with conditions** (spec §15 A2-4, R-715): (1) cite CoolProp 8.0.0 with its MIT notice, kept as attribution (the MIT condition binds "copies or substantial portions of the Software", and neither the 183 computed pressures nor the 12 fitted coefficients are); (2) cite the three EOS sources by their BibTeX keys (S10 reproduces no coefficient, form or table of those papers); (3) IAPWS attribution for the water points (`Wagner-JPCRD-2002` is IAPWS-95; as RC-04, ADR 0045, R-616). The design lane's technical reading, not legal advice | None for the saturation points (C12 A32-Q3 ruled by A2-4). `val3-eos.json` is the same kind of tool output; that A2-4's conditions carry over to it is this update's reading (WO-S10-7), not a ruling. |
| S10-RC-04 | **IAPWS-95** via `iapws95-v1` | Cross-check of the water saturation points only (5 values in `saturation-points.json`); nothing in the records | ADR 0045, R-616: shipped with IAPWS's attribution in NOTICE. | **permitted with conditions** (IAPWS attribution) | None. |
| S10-RC-05 | **Fit VLE data:** Kurihara, Nakamichi, Kojima, *J. Chem. Eng. Data* 38 (1993) 446-449, Table II | Transcribed T, x₁, y₁ of the three binaries at 101.3 kPa: **49 points, 147 values** (`benchmarks/s10/vle/`), and the six Λ fitted to them (RC-07). | The paper itself (p. 446, foot): "© 1993 American Chemical Society", with the article code "0021-9568/93/1738-0446$04.00/0". It contains no statement on reuse of its data, and no licence. ACS's permissions page was not reachable on C12's fetch (C12 RC-01: "ACS unreachable"). | **unresolved**, as C12 RC-01: individual published numbers, publisher's terms not read | Whether transcribed measurements (facts) are covered by the article's copyright is a legal question this check cannot settle. |
| S10-RC-06 | **Validation VLE data** (§9.6): VAL-1 the same paper's Table V (ternary); VAL-2 Kurihara, Minoura, Takeda, Kojima, *J. Chem. Eng. Data* 40 (1995) 679-684 | VAL-1 (WO-S10-6): Table V transcribed and double-entered, T, x₁, x₂, y₁, y₂ at 101.3 kPa: **38 points, 190 values** (`vle/kurihara1993_ternary{,.A,.B}.csv`). `validation/report.json` echoes every T_exp and y_exp of Table V beside the predictions (`per_row`); `docs/s10-validation-report.md` holds only aggregates. VAL-2: nothing (the paper has not been obtained). | VAL-1: as RC-05 (the same 1993 paper). VAL-2: the paper has not been obtained. | **unresolved**, as RC-05 | Table V: as RC-05. VAL-2 unread. |
| S10-RC-07 | **The project's fits**: P^sat a…d (12 values) and Λ (6 values), and what is derived from them | `records.yaml`, produced by `s10_records.py`; derived and project-generated: `reference_values_real.yaml` (`s10_reference.py --real`), both `inputs.json` (the records' parameters and the I-states, `--write-inputs`), `records-lineage.json` (hashes and the `uncertainty` strings) | Project-authored. | **permitted** | The inputs' rows (RC-03, RC-05) govern whether the inputs ship. |
| S10-RC-08 | **Molar masses** (ComponentRecord requires them; the provider does not use them) | 3 values from CIAAW 2021 conventional atomic weights H 1.008, C 12.011, O 15.999 (Q-N6 default: TM-4513 was not read for an atomic-weight table) | C12 RC-08 (CIAAW page, workstation fetch 2026-10-22): no terms of use or licence; footer "© CIAAW, 2007-2024". | **unresolved**, as C12 RC-08 | Q-N6: if TM-4513 tabulates atomic weights, RC-01's status would apply instead. |
| S10-RC-09 | `verification-records.yaml` | Invented by the S10 design lane | Project-authored. | **permitted** | None. |

**Identifiers:** name and formula only. No CAS RN (CAS: "license is required", C12 RC-07). No InChI or InChIKey.
`records.yaml` carries no `identifiers` key (B-22).

## 3. Per-file map (file → rows)

| File | Rows | Ships? |
| --- | --- | --- |
| `benchmarks/s10/records.yaml` | RC-01, 02, 03 (via the fit), 05 (via the fit), 07, 08 | No: RC-05 and RC-08 unresolved; Frank decides (Q-F3) |
| `benchmarks/s10/fit-report.json` | RC-05 (residuals per transcribed point), 07 | No, as above |
| `benchmarks/s10/records-lineage.json` | RC-07 | Repository only |
| `benchmarks/s10/records-vetting.json` | RC-07 (project-generated by `s10_records_vetting.py`, S10 spec §18 A5-1) | Repository only |
| `benchmarks/s10/saturation-points.json` | RC-03, 04 | Repository only |
| `benchmarks/s10/nasa7-low.json` | RC-01, 02 | Repository only |
| `benchmarks/s10/vle/kurihara1993_binaries{,.A,.B}.csv` | RC-05 | No: unresolved |
| `benchmarks/s10/vle/kurihara1993_ternary{,.A,.B}.csv` | RC-06 | No: unresolved |
| `benchmarks/s10/validation/val3-eos.json` | RC-03 (condition 3, IAPWS attribution, covers the water values) | Repository only |
| `benchmarks/s10/validation/report.json` | RC-06 (echoes Table V's T_exp, y_exp), 07 | No: RC-06 unresolved |
| `docs/s10-validation-report.md` | RC-06 (aggregates only), 03, 07 | Repository only (documentation) |
| `benchmarks/s10/reference_values_real.yaml` | RC-07 (derived from `records.yaml`) | Repository only |
| `benchmarks/s10/{idaes,dwsim}/inputs.json` | RC-07 (derived from `records.yaml`) | Repository only |
| `benchmarks/s10/verification-records.yaml` | RC-09 | Not a packaged path either (library-only provider) |

**Summary.** Every real record depends on two **unresolved** rows: RC-05 (the 1993 paper; ACS copyright, no reuse
statement in the paper) and RC-08 (atomic weights). The validation data, Table V of the same paper, are RC-06 and
unresolved in the same way; `validation/report.json` reproduces them. RC-01 and RC-02 are permitted with citation and notice. RC-03 is
permitted with conditions (spec §15 A2-4): the CoolProp MIT notice, the three EOS citations, and IAPWS attribution
for water. No S10 file enters a `PACKAGED` path (spec §9.1).
