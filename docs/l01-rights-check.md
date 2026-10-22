# L01 rights check: the sources of the nine `pr-lib-v1` component records (C12)

**Status:** build lane (C12, branch `wp/C12`), 2026-10-22. **Facts and quoted terms, not a legal opinion.** Whether
the records ship is Frank's decision (`docs/FRANK_QUESTIONS.md:18`, L01-Q4); amending T08.A32 is the design lane's
next step (§5). Attribution text: `docs/attributions/pr-lib-v1.md`. Choices: `docs/C12_DECISIONS.md`.

**Records checked:** `benchmarks/l01/components.yaml` (H2, N2, Ar, CH4, H2O, CO2, O2, C2H6, C3H8; `rights` blocks at
:132, :243, :354, :465, :576, :687, :798, :909, :1020). H2, N2, Ar, CH4 are the same mappings as in
`benchmarks/m01/components.yaml` (T08.A32 (v)). The cross-check record `benchmarks/l01/components-crosscheck.json`
and the literature table in `docs/derivations/scripts/l01_projection.json` are covered in RC-09…RC-12. They hold
numbers that are not in any record.

**How the terms were read.**
- *Local:* licence files and data-file headers of the installed packages in `/home/user/venv-l01-sources`
  (`lib/python3.13/site-packages/`, abbreviated `SP/`), read as text. Nothing from a data file was executed.
- *Public pages:* fetched 2026-10-22 between 19:34 and 19:36 UTC with `curl` through the session proxy, then with
  the WebFetch tool. Every terms host was refused, so **no public terms page could be read from this session.**
  - `curl` returned `CONNECT tunnel failed, response 403` for ntrs.nasa.gov, atct.anl.gov, janaf.nist.gov,
    kinetics.nist.gov, www.nist.gov, shepherd.caltech.edu, www.nasa.gov, www.ciaaw.org, iupac.org, doi.org,
    pubchem.ncbi.nlm.nih.gov, www.cas.org, www.inchi-trust.org, cantera.org, coolprop.org and web.archive.org.
    The proxy status logged these as `connect_rejected` (policy denial).
  - WebFetch returned `getaddrinfo ENOTFOUND` for ntrs.nasa.gov, atct.anl.gov and www.nist.gov.
  - raw.githubusercontent.com was reachable. It was used only to read the `chemicals` README, which matches the
    installed package's METADATA.
- Every source whose terms rest on such a page is therefore marked **`unresolved`** below, with that reason.
  Nothing is assumed permitted.

## 1. Verdict vocabulary

- **permitted with conditions**: the governing licence text was read, it permits redistribution, and the conditions
  are listed.
- **unresolved**: the governing terms could not be established from what this session could read. The reason is
  stated. This is not a finding that redistribution is forbidden.

## 2. Rights-check rows

| Row | Source | What L01 takes, and from where | Governing terms (quoted, with location) | Verdict | Open doubts |
| --- | --- | --- | --- | --- | --- |
| RC-01 | **Reference equations of state**, one paper per record (§3) | T_c, P_c, ω for all nine records: **27 values**. Retrieved as `chemicals` 1.5.2 method `HEOS` from `SP/chemicals/Misc/heos_constants.tsv` (SHA-256 `1deebc94…8accc0`, 145 data rows). The record cites the paper. | Publishers' terms (AIP/NIST for J. Phys. Chem. Ref. Data; ACS for J. Chem. Eng. Data; Elsevier for Fluid Phase Equilib.) **not read**: doi.org refused (403). | **unresolved**: no terms page reachable | The records say the values are "published numerical constants quoted with their citations". This is the records' own statement; no publisher text was read to confirm or contradict it. |
| RC-02 | **NIST REFPROP**, the stated origin of `chemicals`' `HEOS` table | Same 27 values as RC-01. They reached L01 through this table, not by transcription from the papers. | `SP/chemicals/critical.py:370-372` and `acentric.py:137`: "'HEOS', a series of values from the NIST REFPROP Database for Highly Accurate Properties of Industrially Important Fluids (and other high-precision fundamental equations of state)". `acentric.py:164-166` cites Huber, Lemmon, Bell, McLinden, Ind. Eng. Chem. Res. 61 (2022) 15449, doi:10.1021/acs.iecr.2c01427. NIST SRD terms (`https://www.nist.gov/srd/public-law`) **not read** (403). | **unresolved**: NIST terms page unreachable | Records name the primary papers, not REFPROP. Whether the REFPROP route attaches any NIST SRD condition to these 27 numbers is open (A32-Q3). |
| RC-03 | **NASA TM-4513**: McBride, Gordon, Reno (1993) | Low-range NASA-7 coefficients as b_k: 5 × 9 = **45 values**. Range bounds 200 and 1000 K: **18 values**. All nine records. Retrieved from `SP/cantera/data/nasa_gas.yaml` (SHA-256 `4de6199d…67e4db`). | The file header (`nasa_gas.yaml:1-14`) quotes the citation, not terms: "This file contains data for gas phase species from the NASA thermodynamic database, which is available for download from https://shepherd.caltech.edu/EDL/PublicResources/sdt/thermo.html. The original source is: B.J. McBride, S. Gordon, and M.A. Reno, … NASA Report TM-4513, October 1993. https://ntrs.nasa.gov/citations/19940013151". NTRS record and the Caltech page **not read** (403). | **unresolved**: NTRS and the distribution page unreachable | The records state "NASA TM-4513 is a work of the United States Government". That was not checked against the NTRS record's copyright field. The species `note` codes (e.g. `L 8/89`, `TPIS89`) name upstream data sources inside the report; their status was not examined. |
| RC-04 | **Cantera 3.2.0** (retrieval tool for RC-03) | No value is Cantera's own: it ships the NASA-7 data in `nasa_gas.yaml`. Records name it in `provenance` and `rights.redistribution`. | `SP/cantera-3.2.0.dist-info/licenses/License.txt` (1796 B, SHA-256 `e92980b9…79c41bb`), BSD-3-Clause: "Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met: - Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer. - Redistributions in binary form must reproduce the above copyright notice … in the documentation … - Neither the name of the California Institute of Technology, Sandia Corporation nor the names of other contributors may be used to endorse or promote products derived from this software without specific prior written permission." Metadata `License-Expression: BSD-3-Clause`. | **permitted with conditions**: reproduce the three copyright lines, the conditions and the disclaimer; no endorsement use of the names | The licence covers Cantera's copyright. It does not speak for the NASA data inside the file (RC-03 governs those). |
| RC-05 | **Active Thermochemical Tables (ATcT) 1.112**, Ruscic and Bross, Argonne | Gas formation enthalpies at 298.15 K for CH4, H2O, CO2, C2H6, C3H8: **5 values**, plus their 5 uncertainties quoted in `provenance`. Retrieved as `chemicals` method `ATCT_G` from `SP/chemicals/Reactions/ATcT 1.112 (g).tsv` (SHA-256 `b7d4dd12…cfdc90`, 595 data rows). H2, N2, Ar, O2 take zero by definition. | The TSV has no header text, only columns `CAS Chemical Formula Hfg_0K Hfg uncertainty`. `SP/chemicals/reaction.py:373-377` cites Ruscic et al., J. Phys. Conf. Ser. 16 (2005) 561, doi:10.1088/1742-6596/16/1/078. ATcT terms and citation request at `https://atct.anl.gov/` **not read** (403). | **unresolved**: ATcT site unreachable | ATcT is known to ask for a specific citation form for each version. It was not read, so the attribution file carries the records' citation marked "wording not confirmed". |
| RC-06 | **`chemicals` 1.5.2** (Caleb Bell et al.; retrieval tool) | Retrieval of RC-01/02, RC-05, RC-07 and RC-08 data: **36 identifier strings** and the **9 molar masses** computed from its atomic-weight table. | `SP/chemicals-1.5.2.dist-info/licenses/LICENSE.txt` (1127 B, SHA-256 `dc8d90b7…854edb`), MIT: "Permission is hereby granted, free of charge, … to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, … subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software." METADATA:360-362: "Although not required by the chemicals license, if it is convenient for you, please cite chemicals if used in your work." Its README: "it is a collection of cited and openly published data and equations". | **permitted with conditions**: include the MIT copyright and permission notice; citation requested, not required | The MIT grant covers the authors' rights. Its data tables reproduce third-party data (RC-01/02, RC-05, RC-07, RC-08), and the grant cannot speak for those. |
| RC-07 | **PubChem**, origin of `chemicals`' identifier database | CAS RN, InChI, InChIKey and formula for nine records: **36 strings**. | `SP/chemicals/identifiers.py:22`: "This module contains a database of metadata on ~70000 chemicals from the PubChem…". Data file `SP/chemicals/Identifiers/chemical identifiers pubchem small.tsv`. PubChem policies, CAS terms and InChI Trust pages **not read** (403). | **unresolved**: PubChem, CAS and InChI Trust pages unreachable | `rights.source` attributes identifiers to "chemicals 1.5.2 (MIT)" only and does not name PubChem. CAS Registry Numbers are assigned by CAS; their terms were not read. |
| RC-08 | **Standard atomic weights**, which the records attribute to IUPAC (CIAAW) | Atomic weights of H, C, N, O, Ar, used for the **9 molar masses** (computed as Σ n_e A_e / 1000). | `chemicals/elements.py` (SHA-256 `d574e155…faf52`) names no source for its atomic weights: grep for `CIAAW`, `IUPAC`, `Meija`, `isotopic` returns nothing. The CIAAW site **not read** (403). | **unresolved**: the source the record names cannot be traced through the tool, and its terms page is unreachable | The provenance text "IUPAC (CIAAW) standard atomic weights as tabulated by chemicals 1.5.2" is a statement in the records. It has not been confirmed from the tool (A32-Q4). |
| RC-09 | **CoolProp 8.0.0** (cross-check tool) | **Nothing in the records.** The cross-check JSON holds CoolProp-computed T_c, P_c, ω, c_p deviations and EOS bibliography keys. | `SP/coolprop-8.0.0.dist-info/licenses/LICENSE` (1103 B, SHA-256 `9bf83533…a4719b2`), MIT, "Copyright (c) 2012-2018 Ian H. Bell and other CoolProp developers", same grant and condition as RC-06. | **permitted with conditions** (cross-check file only): MIT notice | None for the records. |
| RC-10 | **`thermo` 0.6.1** (cross-check tool; JANAF c_p method) | **Nothing in the records.** Cross-check deviations only. | `SP/thermo-0.6.1.dist-info/licenses/LICENSE.txt` (SHA-256 `8344e0d8…34f8f40`), MIT, "Copyright (C) 2016, 2017, 2018, 2019, 2020, Caleb Bell". | **permitted with conditions** (cross-check file only): MIT notice | None for the records. |
| RC-11 | **NIST-JANAF Thermochemical Tables**, 4th ed. (Chase 1998) | **Nothing in the records.** The cross-check JSON holds absolute JANAF formation enthalpies (e.g. H2O `dHf_janaf_J_mol: -241826.0`) and c_p deviations. Read through `chemicals/Reactions/JANAF_1998.tsv` (SHA-256 `0bf01a51…ff242d33`, no header text) and `thermo`. | janaf.nist.gov and the NIST SRD terms page **not read** (403). | **unresolved** (cross-check file only): NIST pages unreachable | Applies only if the cross-check JSON ships (A32-Q5). |
| RC-12 | **Literature table** sources: CODATA key values (Cox, Wagman, Medvedev 1989), Chao, Wilhoit and Hall (1973), Pittam and Pilcher (1972), Prosen and Rossini (1945), JANAF | **Nothing in the records.** † values in `l01_projection.json` (:881-913) and in the cross-check JSON `literature` block. | Not read. These are printed sources, and no terms page was attempted beyond the hosts above. | **unresolved** (projection and cross-check files only) | Applies only if those files ship (A32-Q5). |

## 3. Per-record map (record → rows)

| Record | Reference EOS (RC-01) | Formation enthalpy | Rows |
| --- | --- | --- | --- |
| H2 | Leachman, Jacobsen, Penoncello, Lemmon, JPCRD 38 (2009) 721, doi:10.1063/1.3160306 | zero by definition | RC-01, 02, 03, 04, 06, 07, 08 |
| N2 | Span, Lemmon, Jacobsen, Wagner, Yokozeki, JPCRD 29 (2000) 1361, doi:10.1063/1.1349047 | zero by definition | RC-01, 02, 03, 04, 06, 07, 08 |
| Ar | Tegeler, Span, Wagner, JPCRD 28 (1999) 779, doi:10.1063/1.556037 | zero by definition | RC-01, 02, 03, 04, 06, 07, 08 |
| CH4 | Setzmann, Wagner, JPCRD 20 (1991) 1061, doi:10.1063/1.555898 | ATcT 1.112 | RC-01, 02, 03, 04, 05, 06, 07, 08 |
| H2O | Wagner, Pruss (IAPWS-95), JPCRD 31 (2002) 387, doi:10.1063/1.1461829 | ATcT 1.112 | RC-01, 02, 03, 04, 05, 06, 07, 08 |
| CO2 | Span, Wagner, JPCRD 25 (1996) 1509, doi:10.1063/1.555991 | ATcT 1.112 | RC-01, 02, 03, 04, 05, 06, 07, 08 |
| O2 | Schmidt, Wagner, Fluid Phase Equilib. 19 (1985) 175, doi:10.1016/0378-3812(85)87016-3 | zero by definition | RC-01, 02, 03, 04, 06, 07, 08 |
| C2H6 | Buecker, Wagner, JPCRD 35 (2006) 205, doi:10.1063/1.1859286 | ATcT 1.112 | RC-01, 02, 03, 04, 05, 06, 07, 08 |
| C3H8 | Lemmon, McLinden, Wagner, J. Chem. Eng. Data 54 (2009) 3141, doi:10.1021/je900217v | ATcT 1.112 | RC-01, 02, 03, 04, 05, 06, 07, 08 |

**Summary.** Every record depends on at least five `unresolved` rows: RC-01, 02, 03, 07, 08, and RC-05 for five of
them. **No record can be called cleared from this session.** The two tool licences that could be read (RC-04
Cantera BSD-3, RC-06 `chemicals` MIT) permit redistribution with notice. Neither speaks for the third-party data the
tools carry.

## 4. Findings in the records (stated, not changed)

- **F-1.** H2, N2 and Ar give `rights.source` "formation enthalpy: ATcT 1.112", but their `provenance` says "zero by
  definition" (`components.yaml:75`, `:186`, `:297`). O2 says "zero by definition" in both places (`:741`, `:799`). The H2, N2 and Ar text is shared with `benchmarks/m01/components.yaml` (T08.A32 (v)), so any edit
  touches both files.
- **F-2.** `rights.source` names neither PubChem (RC-07) nor the REFPROP route (RC-02), although the retrieval
  passed through both.
- **F-3.** CH4's `rights.source` reads "Setzmann and Wagner et al. reference EOS". The paper has two authors, so
  "et al." does not fit.
- **To finish the unresolved rows,** a machine with open web access (the workstation) needs to read and quote:
  - the NTRS record for 19940013151;
  - `https://atct.anl.gov/` (terms and citation request for 1.112);
  - `https://www.nist.gov/srd/public-law`;
  - `https://janaf.nist.gov/`;
  - PubChem's data policy;
  - CAS's terms for CAS RN use;
  - the CIAAW atomic-weights page;
  - the publishers' terms for the nine papers.

## 5. Work order for the design lane (T08.A32 amendment, register R-575…R-579)

- **A32-Q1.** Should A32 (iii) also require every real record's `rights` to name its rights-check row ids (RC-xx)?
  The alternative is a map kept in this document. Proposed: a required `rights.check_rows` list, which changes
  the record schema and so needs an ADR. The cheaper option is a test that maps each record id to rows in §3.
- **A32-Q2.** Should A32 require the attribution file to exist, cover every `rights.source` segment and every
  provenance DOI (the C12 test does this now), and ship beside the records in any sdist or wheel that contains
  them? `docs/` is not in the wheel. A packaged copy or a NOTICE section would be needed.
- **A32-Q3.** Is a value retrieved through a REFPROP-derived table (RC-02) but cited to the primary paper governed
  by the paper alone? This is a scientific-provenance question as well as a rights one.
- **A32-Q4.** Does the molar-mass provenance need a traceable atomic-weight source (RC-08)? The tool cites none.
- **A32-Q5.** Do `components-crosscheck.json` and `l01_projection.json` ship? If so, RC-09…RC-12 apply to them.
- **A32-Q6.** Should F-1 and F-3 be corrected? Any edit changes the record bytes in both vetted files, and with
  them the cross-check record's `records_sha256`.
- **A32-Q7.** Should A32 forbid shipping while any row a record depends on is `unresolved`? This is what Frank's
  L01-Q4 answer implies.
