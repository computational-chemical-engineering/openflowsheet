# Attributions for the `pr-lib-v1` component records

This file states the citations and notices that go with the nine records in `benchmarks/l01/components.yaml`
(H2, N2, Ar, CH4, H2O, CO2, O2, C2H6, C3H8). The rights check behind it is `docs/l01-rights-check.md`, and each
section below names its rows there (RC-xx). **Shipping status:** the records are not released. A section marked
**unresolved** has a citation but no established terms (the reason is in the rights check), and the citation
wording it gives has not been confirmed against the source's own request. This file states facts and quoted
licence texts; it is not a legal opinion. Built by C12 on 2026-10-22. `tests/test_l01_attribution.py` checks
that every source a record names in `rights.source`, and every DOI in a record's `provenance`, appears here.

## Reference equations of state: critical constants and acentric factors (RC-01, RC-02) — unresolved

T_c, P_c and ω of each record are the critical point and acentric factor of that substance's reference equation of
state. They were retrieved through `chemicals` 1.5.2 method `HEOS`, which describes its table as values "from the
NIST REFPROP Database" (RC-02). Cite the primary paper:

| Record | `rights.source` names | Citation |
| --- | --- | --- |
| H2 | Leachman et al. reference EOS | Leachman, Jacobsen, Penoncello and Lemmon, J. Phys. Chem. Ref. Data 38 (2009) 721-748, doi:10.1063/1.3160306 (normal hydrogen) |
| N2 | Span et al. reference EOS | Span, Lemmon, Jacobsen, Wagner and Yokozeki, J. Phys. Chem. Ref. Data 29 (2000) 1361-1433, doi:10.1063/1.1349047 |
| Ar | Tegeler et al. reference EOS | Tegeler, Span and Wagner, J. Phys. Chem. Ref. Data 28 (1999) 779-850, doi:10.1063/1.556037 |
| CH4 | Setzmann and Wagner et al. reference EOS | Setzmann and Wagner, J. Phys. Chem. Ref. Data 20 (1991) 1061-1151, doi:10.1063/1.555898 |
| H2O | Wagner and Pruss (IAPWS-95) reference EOS | Wagner and Pruss, J. Phys. Chem. Ref. Data 31 (2002) 387-535, doi:10.1063/1.1461829 (IAPWS-95) |
| CO2 | Span and Wagner reference EOS | Span and Wagner, J. Phys. Chem. Ref. Data 25 (1996) 1509-1596, doi:10.1063/1.555991 |
| O2 | Schmidt and Wagner reference EOS | Schmidt and Wagner, Fluid Phase Equilib. 19 (1985) 175-200, doi:10.1016/0378-3812(85)87016-3 |
| C2H6 | Buecker and Wagner reference EOS | Buecker and Wagner, J. Phys. Chem. Ref. Data 35 (2006) 205-266, doi:10.1063/1.1859286 |
| C3H8 | Lemmon, McLinden and Wagner reference EOS | Lemmon, McLinden and Wagner, J. Chem. Eng. Data 54 (2009) 3141-3180, doi:10.1021/je900217v |

Route (RC-02): Huber, Lemmon, Bell and McLinden, "The NIST REFPROP Database for Highly
Accurate Properties of Industrially Important Fluids", Industrial & Engineering Chemistry Research 61 (2022) 15449-72,
doi:10.1021/acs.iecr.2c01427, as cited by `chemicals` 1.5.2 `acentric.py`.

## Ideal-gas heat capacities: NASA TM-4513 (1993) (RC-03) — unresolved

The b_k of every record are the low-range (200-1000 K) NASA-7 coefficients scaled by 1000^k. Citation:
McBride, Gordon and Reno, "Coefficients for Calculating Thermodynamic and Transport Properties of
Individual Species", NASA Report TM-4513, October 1993, https://ntrs.nasa.gov/citations/19940013151.
Species notes as recorded in each record's `provenance` (e.g. `L 8/89`, `TPIS89`). The records state "NASA TM-4513
is a work of the United States Government"; the NTRS record was not reachable to confirm it.

## Formation enthalpies: ATcT 1.112 (RC-05) — unresolved

Gas formation enthalpies at 298.15 K of CH4, H2O, CO2, C2H6 and C3H8. H2, N2, Ar and O2 are zero by definition.
Citation as the records give it: Active Thermochemical Tables (ATcT) version 1.112,
B. Ruscic and D. H. Bross, Argonne National Laboratory (ATcT.anl.gov). Method reference cited by
`chemicals`: Ruscic, Pinzon, von Laszewski, Kodeboyina, Burcat, Leahy, Montoy and Wagner, "Active Thermochemical Tables: Thermochemistry for the 21st Century", J. Phys.:
Conf. Ser. 16 (2005) 561, doi:10.1088/1742-6596/16/1/078. ATcT's own citation request was not readable from this
session; the wording above is to be replaced by the one ATcT asks for.

## Identifiers: CAS RN, InChI, InChIKey, formula — PubChem via `chemicals` (RC-07) — unresolved

Retrieved from `chemicals` 1.5.2, whose identifier database is "metadata on ~70000 chemicals from the PubChem"
(`chemicals/identifiers.py:22`). Source: PubChem, National Center for Biotechnology Information,
https://pubchem.ncbi.nlm.nih.gov. CAS Registry Numbers are assigned by CAS, a division of the American Chemical
Society. InChI and InChIKey are IUPAC identifiers (InChI Trust).

## Molar masses: standard atomic weights (RC-08) — unresolved

Each molar mass is Σ n_e A_e / 1000 with the atomic weights tabulated by `chemicals` 1.5.2. The records attribute
them to IUPAC (CIAAW) standard atomic weights, https://www.ciaaw.org; the tool itself names no source.

## Retrieval tool: chemicals 1.5.2 (MIT) (RC-06) — permitted with conditions

Condition: the copyright notice and permission notice below, in all copies or substantial portions. Citation
requested by the authors (not required): Caleb Bell, Yoel Rene Cortes-Pena, and Contributors (2016-2025).
Chemicals: Chemical properties component of Chemical Engineering Design Library (ChEDL),
https://github.com/CalebBell/chemicals. Licence text, verbatim from
`chemicals-1.5.2.dist-info/licenses/LICENSE.txt`:

```text
MIT License

Copyright (C) 2016, 2017, 2018, 2019, 2020, 2021 Caleb Bell <Caleb.Andrew.Bell@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Retrieval tool: Cantera 3.2.0 (BSD-3-Clause) (RC-04) — permitted with conditions

Cantera 3.2.0 `data/nasa_gas.yaml` carried the NASA TM-4513 coefficients (the data are governed by RC-03, not by
this licence). Conditions: retain or reproduce the copyright notice, the list of conditions and the disclaimer; do
not use the names of the California Institute of Technology, Sandia Corporation or other contributors to endorse
or promote derived products. Licence text, verbatim from `cantera-3.2.0.dist-info/licenses/License.txt`:

```text
Copyright (c) 2001-2009, California Institute of Technology
All rights reserved.

Copyright (c) 2009 Sandia Corporation. Under the terms of
Contract AC04-94AL85000 with Sandia Corporation, the U.S. Government
retains certain rights in this software.

Copyright (c) 2011-2025, Cantera Developers.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

- Redistributions of source code must retain the above copyright
  notice, this list of conditions and the following disclaimer.

- Redistributions in binary form must reproduce the above copyright
  notice, this list of conditions and the following disclaimer in the
  documentation and/or other materials provided with the distribution.

- Neither the name of the California Institute of Technology, Sandia
  Corporation nor the names of other  contributors may be used to
  endorse or promote products derived from this software without
  specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## Only if the cross-check record ships

`benchmarks/l01/components-crosscheck.json` contains no record value but carries numbers computed with CoolProp
8.0.0 and `thermo` 0.6.1 (RC-09, RC-10, permitted with conditions: the MIT notices below) and quotes NIST-JANAF and
literature values (RC-11, RC-12, unresolved). NIST-JANAF Thermochemical Tables, 4th ed.; the literature table
cites it as "JANAF 4th ed. (Chase 1998)", and the full citation NIST asks for is to be confirmed (RC-11).

CoolProp 8.0.0, verbatim from `coolprop-8.0.0.dist-info/licenses/LICENSE`:

```text
MIT License

Copyright (c) 2012-2018 Ian H. Bell and other CoolProp developers

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

`thermo` 0.6.1, verbatim from `thermo-0.6.1.dist-info/licenses/LICENSE.txt`:

```text
MIT License

Copyright (C) 2016, 2017, 2018, 2019, 2020, Caleb Bell <Caleb.Andrew.Bell@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
