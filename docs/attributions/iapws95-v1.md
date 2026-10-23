# Attribution for the `iapws95-v1` coefficient file

This file states the citation and the terms that go with `benchmarks/s05/iapws95_coefficients.json`, the data the
library-only property provider `iapws95-v1` reads. It is the provider's documentation that ADR 0045's release
condition asks for (S05 spec §16.3, R-616). It states facts and quoted terms; it is not a legal opinion.
`tests/test_s05_envelope.py` (S05.A31) checks that the strings below appear here, in NOTICE and in
`docs/C10_DECISIONS.md`.

## The file

- Repository path: `benchmarks/s05/iapws95_coefficients.json`.
- Package path: `openflowsheet/_data/benchmarks/s05/iapws95_coefficients.json`, a symbolic link to the repository
  copy (S05.A26); the wheel carries the file's bytes.
- SHA-256: `b9e93877e37874f1b3a483e298a45692e264d70686d4c158372084b96abbe6ed` (the provider's `data_sha256`).
- Provider id: `iapws95-v1`. It is library-only: no revision can select it (R-568, R-569, spec §16.4).

## The release and its terms

The file reproduces the coefficients and constants of the IAPWS-95 formulation as published in IAPWS R6-95(2018).
Three strings, verbatim from the release's cover page:

- © 2018 International Association for the Properties of Water and Steam
- Publication in whole or in part is allowed in all countries provided that attribution is given to the International Association for the Properties of Water and Steam
- Please cite as: International Association for the Properties of Water and Steam, IAPWS R6-95(2018), Revised Release on the IAPWS Formulation 1995 for the Thermodynamic Properties of Ordinary Water Substance for General and Scientific Use (2018)

Attribution is given in NOTICE, which both the sdist and the wheel carry.

## What was read, and the check against it

The release that was read is the PDF with SHA-256 `512879217b94f4d0741c88cab743d41098268914d538d73e680a736cb1c3aad7`.
Its Tables 1, 2 and 6-8 were compared with the committed values: 385 values, 0 mismatches (`af04961e`; spec §15.1).
The release's derivative relations (Tables 3-5) were used, not compared. The molar mass M = 0.018015268 kg/mol
(IAPWS G5-01) is cited as Q-7 leaves it: not compared with a printed copy.

## The transcription route

The values were taken from CoolProp 8.0.0 (MIT licence); none of CoolProp's code or text ships here. They were
checked equal to `iapws` 1.5.5 (GPL-3), which was executed only, with nothing copied (R-594). The terms above are
IAPWS's, and the values were confirmed against the printed release.
