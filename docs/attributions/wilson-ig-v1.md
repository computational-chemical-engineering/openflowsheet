# Attribution for the `wilson-ig-v1` records and the points they are fitted to

This file states the citations and the terms that go with the two S10 files the 0.3.0 wheel carries:
`benchmarks/s10/records.yaml`, the real records the property providers `wilson-ig-v1` and `wilson-ig-v2` read, and
`benchmarks/s10/vle/kurihara1993_binaries.csv`, the measured points their Wilson parameters are fitted to. It is the
provider's attribution page, after `iapws95-v1.md` (V03 spec §9.1, R-880). It states facts and quoted terms; it is not a
legal opinion. The rows it cites are those of `docs/s10-rights-check.md` §2. `tests/test_v03_wilson_ship.py` (V03.A12–A14)
checks the files, NOTICE and the rights-check table against each other.

## The files

| Repository path | Package path | SHA-256 |
| --- | --- | --- |
| `benchmarks/s10/records.yaml` | `openflowsheet/_data/benchmarks/s10/records.yaml` | `033e10b3f151a83ddb6235a04e7349458a38baf6968962577bfe24099eb7c9a6` (the providers' `data_sha256`) |
| `benchmarks/s10/vle/kurihara1993_binaries.csv` | `openflowsheet/_data/benchmarks/s10/vle/kurihara1993_binaries.csv` | `986641d8a6d6b6d44ac1eb3cfc8f35e39d71d72fe549978d34197a4449eb1cd3` |

Each package path is a symbolic link to the single repository copy; the sdist and the wheel carry the file's bytes. The
bytes are those S10 committed, so `data_sha256` does not move. The records file's header still says it is "Not package
data and not shipped until every row is permitted and Frank decides": that sentence was true until Frank's decision of
2026-10-29 and is a recorded erratum, not an edit, because an edit would move `data_sha256` (the R-310 pattern, as for
`iapws95-v1`'s module, R-616).

Provider ids: `wilson-ig-v2` is selectable in a revision (S11, ADR 0051); `wilson-ig-v1` is library-only. Both read the
same records.

## Frank's decision

Frank, 2026-10-29, Q-F3 ("Ship params + points"; `docs/FRANK_QUESTIONS.md`): the 0.3.0 wheel ships the fitted parameters
and the transcribed Kurihara 1993 points, with the three CIAAW atomic weights. That settles S10-RC-05 and S10-RC-08 for
these two files. S10-RC-06 is not settled: the 1993 ternary (Table V), the 1995 isotherms, `validation/report.json` that
echoes them, the double entries and `fit-report.json` stay in the repository only (R-880). R-811's refusal of the Wilson
basis in a wheel is removed with the same decision.

## What the records take, and the citation each needs

| Row | Source | In `records.yaml` | Condition met in NOTICE |
| --- | --- | --- | --- |
| S10-RC-01 | NASA TM-4513: B.J. McBride, S. Gordon and M.A. Reno, October 1993; read through Cantera 3.2.0's `nasa_gas.yaml` | 15 heat-capacity coefficients b₀…b₄ and 3 formation enthalpies | cite TM-4513 (NTRS: "Work of the US Gov. Public Use Permitted.") |
| S10-RC-03 | CoolProp 8.0.0 (MIT; "Copyright (c) 2012-2018 Ian H. Bell and other CoolProp developers") evaluating `deReuck-BOOK-1993` (methanol), `Schroeder-JPCRD-2014` (ethanol), `Wagner-JPCRD-2002` (water) | none of its values: the 12 vapour-pressure coefficients are this project's fit to 183 computed pressures (RC-07) | (1) cite CoolProp 8.0.0 with its MIT notice; (2) cite the three EOS keys; (3) IAPWS attribution for water, which NOTICE's IAPWS block gives (RC-04, R-616) |
| S10-RC-05 | K. Kurihara, M. Nakamichi, K. Kojima, *J. Chem. Eng. Data* 38 (1993) 446-449, Table II (© 1993 American Chemical Society) | none of its values: the 6 Wilson Λ are this project's fit to its 49 points (RC-07) | cite the paper; ship decided by Frank |
| S10-RC-08 | CIAAW 2021 conventional atomic weights H 1.008, C 12.011, O 15.999 | 3 molar masses (unused by the providers) | cite CIAAW 2021; ship decided by Frank |
| S10-RC-07 | this project's fits | the 12 P^sat and 6 Λ values | project-authored |

## What the points file takes

`kurihara1993_binaries.csv` transcribes Table II of the same paper: T, x₁, y₁ of methanol–ethanol, methanol–water and
ethanol–water at 101.3 kPa, 49 points and 147 values (S10-RC-05). The paper was read from the PDF Frank supplied
(2026-10-25); no page of it is reproduced, only the transcribed numbers. The transcription was double-entered and
reconciled (`kurihara1993_binaries.{A,B}.csv`, which stay in the repository).

## The attribution in NOTICE

NOTICE, which both the sdist and the wheel carry, has one section for these files, "Third-party data: the Wilson records
and the points they are fitted to". It names both package paths and gives: NASA TM-4513; CoolProp 8.0.0 with its
copyright line and licence; the keys `deReuck-BOOK-1993`, `Schroeder-JPCRD-2014` and `Wagner-JPCRD-2002`, the last
pointing at the IAPWS block above it; the paper as *J. Chem. Eng. Data* 38 (1993) 446-449, Table II; and the CIAAW 2021
conventional atomic weights.

## Using the provider from the library

V03 spec §9.1 and §10.4 (R-883). Three facts:

- The records are package data. `benchmarks/s10/records.yaml` ships in the wheel as
  `openflowsheet/_data/benchmarks/s10/records.yaml` (R-880), so a revision whose `record_source` names it binds
  `wilson-ig-v2` in a wheel; the binder and the verifier pass the packaged path.
- The no-argument constructors `WilsonIdealGasProvider()` and `WilsonIdealGasProviderV2()` read a source checkout only.
  Elsewhere they refuse `RecordError("records_missing: …")`, never a fallback. The refusal's text still says the records
  are read from a "source checkout only": `thermo/wilson_ig.py`'s bytes are pinned (S11.A75) and enter both providers'
  identity, so the stale message stays (R-883).
- A library user passes the packaged path:

  ```python
  from openflowsheet import resources
  from openflowsheet.thermo import wilson_ig

  provider = wilson_ig.WilsonIdealGasProvider(resources.packaged_path(wilson_ig.RECORDS_PATH))
  ```
