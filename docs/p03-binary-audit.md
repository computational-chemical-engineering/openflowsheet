# P03 exact binary, plugin and notice audit

**Package:** P03. **Requirements:** D04 (licensing — "exact binary/data inventory and distribution
verdict") and **[A10]** (binary-license audit — "bundled plugin inventory including disabled
distributed bytes"). **Authority:** plan §4.1 row P03, §8.1 days 8–9. **Recorded by:** Opus 5,
2026-09-17. **Continues** the inventory begun in `docs/backend-environments.md` §5, and corrects one
statement made there.

This document is the **inventory**, not the verdict. It establishes what the two candidate
distributions actually contain, byte for byte; whether the project may ship it, and which backend is
selected, are ADR 0006 and ADR 0003.

Regenerate everything below with:

```bash
.venv-casadi/bin/python scripts/p03_binary_inventory.py --out spikes/p03/results
```

which writes `spikes/p03/results/{casadi,pyomo}-inventory.json`. Every number and hash quoted here
is read from those two files. The script separates three grades of statement and so does this
document:

| Grade | Means |
| --- | --- |
| **measured** | A size, a SHA-256, an ELF `DT_NEEDED` entry, an exported symbol, whether `dlopen` succeeded. |
| **declared** | What a notice file or a wheel `METADATA` field says about itself. |
| **inferred** | An attribution of a binary to an upstream component. Always labelled. |

No upstream project's licence is asserted here from general knowledge of that project. It is either
read from a notice the distribution actually ships, or it is recorded as **unresolved**.

---

## 1. Host and provenance

Debian 13, x86-64 (`Linux-6.12.86+deb13-amd64`), glibc 2.41, Python 3.13.5. Candidates as installed
by `scripts/build-backend-envs.sh` into `.venv-casadi` and `.venv-pyomo`: casadi 3.8.0 (manylinux
wheel), Pyomo 6.10.1 plus a locally built PyNumero ASL extension. One host, one platform — the
whole audit inherits that limitation.

---

## 2. Candidate A — the CasADi wheel

### 2.1 What is in the package (measured)

`casadi/` holds **2 384 files, 268 509 671 bytes** installed.

| Kind | Files | Bytes |
| --- | ---: | ---: |
| ELF shared object | 221 | 234 809 336 |
| Header | 1 681 | 19 856 200 |
| Static archive | 7 | 5 020 360 |
| Python | 18 | 3 536 402 |
| ELF executable | 4 | 651 864 |
| Build metadata (`.cmake`, `.pc`) | 281 | 397 462 |
| Libtool archive (`.la`) | 15 | 17 344 |
| Other | 157 | 4 220 703 |

The 221 shared objects and their 234 809 336 bytes reproduce the figure in
`docs/backend-environments.md` §5 exactly.

### 2.2 The wheel ships no symlinks (measured)

**Zero** of the 2 384 entries is a symbolic link. The SONAME variants of a library —
`libcasadi.so`, `libcasadi.so.3.7`, or `libcoinmetis.so`, `libcoinmetis.so.2`,
`libcoinmetis.so.2.0.0` — are full byte-identical copies.

Across the 232 compiled objects (shared + static + executable, 240 481 560 bytes) there are only
**119 distinct contents totalling 113 852 969 bytes**. **126 628 591 bytes — 53% of the compiled
payload — is duplicated content.** This is a property of the wheel, not of CasADi, and it matters
only to download and image size.

### 2.3 What an import actually touches (measured)

CasADi resolves a plugin with `dlopen` on first use, so no plugin is in the link-time closure of the
extension module. The `DT_NEEDED` closure of `_casadi.so`, restricted to objects the package ships:

| | Bytes |
| --- | ---: |
| `_casadi.so` | 6 807 768 |
| `libcasadi.so.3.7` | 12 576 848 |
| **Closure total** | **19 384 616** |

Everything outside that closure is external and system-provided: `libstdc++.so.6`, `libm.so.6`,
`libgcc_s.so.1`, `libpthread.so.0`, `libdl.so.2`, `libc.so.6`, `ld-linux-x86-64.so.2`.

**So the P02 route — import CasADi, build an `MX` graph through a `Callback`, call `ca.jacobian`,
evaluate — loads 19.4 MB of the 234.8 MB shipped. The remaining 215.4 MB is downloaded, installed
and redistributed, and never executed on that route.** That is a distribution fact, not a
performance one; nothing in §3 of `docs/p02-measurements.md` changes because of it.

### 2.4 Plugin inventory, and the disabled distributed bytes ([A10])

66 plugin objects match `libcasadi_<type>_<name>.so`. Each was probed by calling CasADi's own
`load_<type>(<name>)`. Four plugin types have no `load_*` entry point in 3.8.0
(`importer`, `onnx`, `sundials`, `xmlfile`, 562 680 bytes) and are recorded as **not probed** rather
than given an invented result.

| Probe result | Objects | Bytes |
| --- | ---: | ---: |
| Loads | 52 | 15 929 381 |
| **Fails — vendor library absent** | **10** | **1 846 344** |
| Not probed (no loader API) | 4 | 562 680 |

The ten that cannot load, with the library each binds to and whether that library is shipped:

| Plugin | Object bytes | Needs | Shipped? | Failure |
| --- | ---: | --- | --- | --- |
| `nlpsol:knitro` | 183 073 | `libknitro` | no | `dlopen` fails: cannot load shared library |
| `nlpsol:snopt` | 183 697 | `libsnopt` | no | `dlopen` fails |
| `nlpsol:worhp` | 178 025 | `libworhp` | no | `dlopen` fails |
| `nlpsol:madnlp` | 192 377 | `libmadnlp` | no | `dlopen` fails |
| `nlpsol:ccopt` | 205 793 | `libccopt` | no | `dlopen` fails |
| `conic:mosek` | 203 697 | `libmosek` | no | `dlopen` fails |
| `conic:xpress` | 233 825 | `libxprs` | no | `dlopen` fails |
| `linsol:ma27` | 63 313 | `libhsl` / `libcoinhsl` | no | `dlopen` fails |
| `conic:cplex` | 200 104 | `libcplex` | adaptor only | loads, **registration fails** |
| `conic:gurobi` | 202 440 | `libgurobi` | adaptor only | loads, **registration fails** |

CPLEX and Gurobi differ from the other eight: the wheel ships a loader stub for each —
`libcplex_adaptor.so` (21 624 bytes, `58d34c86…`) and `libgurobi_adaptor.so` (17 192 bytes,
`2aa00698…`) — which emits a diagnostic on import and then fails registration:

> `Failed to load CPLEX adaptor: CPLEX load adaptor needs an environmental variable <CPLEX_VERSION>
> such that libcplex<CPLEX_VERSION>.so can be found.`

**Disabled distributed bytes: 1 885 160** (10 plugin objects plus the 2 adaptor stubs). No vendor
library is present, confirming §5 of `docs/backend-environments.md`: these are adaptor shims, and
nothing proprietary is redistributed. They are bytes a user downloads and can never run.

### 2.5 Notices — and a correction to the P02 record

`docs/backend-environments.md` §5 states that the distribution "ships no LICENSE, NOTICE or COPYING
file". **That is true of the metadata directory and false of the package tree**, and the difference
matters to ADR 0006. Corrected, measured:

- `casadi-3.8.0.dist-info/` contains exactly `INSTALLER`, `METADATA`, `RECORD`, `REQUESTED`,
  `WHEEL` — **no notice file**, while `METADATA` declares
  `License: GNU Lesser General Public License v3 or later (LGPLv3+)`.
- `casadi/include/licenses/` contains **81 notice files across 40 component directories,
  430 274 bytes**, including CasADi's own LGPL-3.0 text at `casadi/LICENSE/LICENSE.txt`.

So the notices exist; they sit in an include directory rather than beside the metadata that names
the licence. The earlier statement that notices "must be assembled from upstream" is withdrawn: most
of them are already here. What replaces it is narrower and worse, and is §2.6.

The 37 component-level notices, with the identifier matched in the text (`declared`):

| Component | Notice | Declared identifier |
| --- | --- | --- |
| `casadi` (own) | `casadi/LICENSE/LICENSE.txt` | LGPL-3.0 |
| `alpaqa-external` | `alpaqa-external/LICENSE` | LGPL-3.0 |
| `sleqp-external` | `sleqp-external/LICENSE` | LGPL-3.0 |
| `qpOASES` | `qpOASES/LICENSE.txt` | LGPL-2.1 |
| `cbc-external`, `cgl-external`, `clp-external`, `coinutils-external`, `osi-external` | `*/LICENSE` | EPL-2.0 (with an EPL-1.0 text nested one level down) |
| `ipopt-external`, `mumps-external`, `fatrop-external` | `*/LICENSE` | EPL-2.0 |
| `mumps-external` (MUMPS itself) | `mumps-external/MUMPS/LICENSE` | **CeCILL-C** |
| `metis-external` (Coin-OR wrapper) | `metis-external/LICENSE` | EPL-1.0 |
| `metis-external` (METIS itself) | `metis-external/metis-4.0/LICENSE` | **restrictive — see §2.6** |
| `bonmin-external` | `bonmin-external/Bonmin/LICENSE` | EPL-1.0 |
| `onnx-external`, `osqp-external` | `*/LICENSE` | Apache-2.0 |
| `openblas-external`, `protobuf-external`, `BQPD` | `*/LICENSE` | BSD-3-Clause |
| `blasfeo-external`, `hpipm-external`, `piqp-external`, `proxqp-external`, `libzip-external`, `casadi-sundials`, `FMI-Standard-2.0.2`, `FMI-Standard-3.0` | `*/LICENSE*` | BSD-2-Clause |
| `daqp-external`, `highs-external`, `lacemodelica-external`, `mockups-external`, `superscs-external`, `trlib-external`, `uno-external` | `*/LICENSE` | MIT |
| `libz-external`, `tinyxml2-9.0.0` | `*/LICENSE*` | Zlib |
| `ghc-external` | `ghc-external/LICENSE` | MIT-shaped text, no title line — pattern-unidentified |

*Detector limitation, stated so the table is not over-read:* the BSD-3-Clause pattern is a superset
match of the BSD-2-Clause one, so a BSD-3 text matches both and the table reports the stronger of
the two. Six further notices carry no title line the pattern set recognises (`bonmin-external`,
`ghc-external`, three `openblas-external` netlib-BLAS notices, `proxqp-external/cmake-module`) and
are recorded as unidentified rather than guessed. The machine-readable record keeps both the raw
match list and each file's SHA-256.

### 2.6 Finding — METIS 4.0 object code is shipped under a no-redistribution notice

This is the one finding in the audit that is not bookkeeping.

**Declared.** `casadi/include/licenses/metis-external/metis-4.0/LICENSE` (889 bytes, SHA-256
`2ecd4c415834a03b…`) reads, in full and verbatim:

> The METIS package is copyrighted by the Regents of the University of Minnesota. It can be freely
> used for educational and research purposes by non-profit institutions and US government agencies
> only. Other organizations are allowed to use METIS only for evaluation purposes, and any further
> uses will require prior approval. **The software may not be sold or redistributed without prior
> approval.** One may make copies of the software for their use provided that the copies, are not
> sold or distributed, are used under the same terms and conditions.

This is METIS 4's licence. METIS 5.1.0 was relicensed Apache-2.0; METIS 4 was not. The
`metis-external/LICENSE` beside it is EPL-1.0, but that is the Coin-OR `ThirdParty-Metis` *wrapper*,
not the METIS code.

**Measured, not assumed.** A notice in a build tree does not prove the code reached a shipped
object, so the attribution was made from the binary. `libcoinmetis.so.2.0.0` (306 208 bytes, SHA-256
`1166d99729c03357…`) defines `METIS_EstimateMemory`, `METIS_mCPartGraphKway` and `METIS_EdgeND` —
all removed from the METIS 5 API — and defines neither `METIS_SetDefaultOptions` nor `METIS_Free`,
both introduced in METIS 5. (`METIS_PartGraphKway` exists in both lines with different signatures
and discriminates nothing, so it is not used as evidence.) The conclusion **METIS 4.x** is recorded
in `attribution_probes` in the inventory JSON with the symbol lists that produced it.

**Scope.** Exactly one distinct object carries METIS code, shipped three times under its three
SONAME spellings: `libcoinmetis.so`, `libcoinmetis.so.2`, `libcoinmetis.so.2.0.0`, identical
content, **918 624 bytes of the download**. No other shipped object exports a `METIS_` symbol.

**Reachability, derivable from the record.** The inventory stores each ELF's own `DT_NEEDED` list,
so the chain below is checkable from `casadi-inventory.json` alone rather than taken on trust.
`libcoinmetis.so.2` is named directly by `libcoinmumps`, `libipopt`, `libsipopt`, `libuno` and the
`cbc` and `clp` executables, and transitively by `libbonmin`, `libCbc`, `libCbcSolver`, `libCgl`,
`libClp`, `libClpSolver`, `libOsiCbc`, `libOsiClp` and `libsleqp`.

**Seven CasADi plugins sit in that closure**, and this is the operationally important list:

| | |
| --- | --- |
| `conic:cbc`, `conic:clp` | through `libCbc` / `libClp` → `libcoinmumps` |
| `linsol:mumps` | through `libcoinmumps` |
| `nlpsol:ipopt`, `nlpsol:bonmin`, `nlpsol:sleqp`, `nlpsol:uno` | through `libipopt` / `libbonmin` / `libsleqp` / `libuno` |

All seven load successfully (§2.4) — reachability here is a *use* question, not a breakage one.
`libcoinmetis` is **not** in the closure of `_casadi.so` (§2.3), so nothing on the P02 route loads
it. An earlier draft of this section named only `linsol:mumps`; the complete list is the seven
above, and it is the list any rule of the form "no default path may load the METIS closure" has to
name.

**What this does and does not mean.** It is not a numerical defect and not a reason against CasADi
as a *backend*: the P02 route never touches this code. It is a constraint on what the project may
put inside anything it distributes, and it is squarely ADR 0006's question. The audit states the
fact and stops.

*Unrelated and non-restrictive, recorded to prevent confusion:* HiGHS vendors a **different** METIS
(`highs-external/extern/metis/LICENSE.txt`, "Copyright 1995-2013, Regents of the University of
Minnesota", Apache-2.0). Only the Coin-OR METIS 4.0 is restrictive.

### 2.7 Compiled objects with no notice anywhere in the distribution

Mapping each of the 119 distinct compiled objects to a shipped notice directory by name
(**inferred**, and the mapping rule is in this document only), 111 objects / 108 129 506 bytes are
attributable. **Eight objects / 5 723 463 bytes are not**, and no notice for them exists anywhere in
the package — `strings` finds no embedded copyright or licence text in them either:

| Object | Bytes | Status |
| --- | ---: | --- |
| `libgfortran-8f1e9814.so.5.0.0` | 2 714 697 | Toolchain runtime, vendored by the wheel builder. Terms **unresolved**. |
| `libspral.a` | 2 232 218 | SPRAL (symbols `__spral_core_analyse_MOD_*`). No notice shipped. **Unresolved.** |
| `libquadmath-828275a7.so.0.0.0` | 272 193 | Toolchain runtime. **Unresolved.** |
| `libgomp-870cb1d0.so.1.0.0` | 253 289 | Toolchain runtime. **Unresolved.** |
| `libmvec-2-583a17db.28.so` | 181 969 | glibc vector math, vendored. **Unresolved.** |
| `libmatlab_ipc.so` | 30 281 | No notice, no embedded text. **Unresolved.** |
| `libcplex_adaptor.so` | 21 624 | Adaptor stub (§2.4). No notice. |
| `libgurobi_adaptor.so` | 17 192 | Adaptor stub (§2.4). No notice. |

The hash-suffixed names of the first five are the signature of `auditwheel`, which copies host
libraries into a wheel to make it manylinux-portable; it does not copy their notices. Their terms
are recorded as unresolved because settling them means going to the toolchain that built the wheel,
which is outside this repository. **This is a notice-completeness gap, not evidence of a
restriction.** It is stated so that ADR 0006 knows the difference between "audited and permissive"
and "audited and unknown".

*Mapping caveat.* Thirteen notice components matched no object under the crude name rule —
`casadi-sundials`, `qpOASES`, `proxqp-external`, `tinyxml2-9.0.0`, `libzip-external`,
`ghc-external`, `protobuf-external`, `BQPD`, the two FMI standards and three `*-build` directories.
These are components statically linked into the `libcasadi_*` plugin objects, which the rule
attributes wholesale to `casadi`. That is a limitation of the mapping, not a second gap.

---

## 3. Candidate B — Pyomo plus a locally built PyNumero ASL

### 3.1 What the wheel ships (measured)

The `pyomo` package is **47 516 130 bytes**, of which 45 834 446 is Python source across 2 782
files. It ships exactly **one** compiled object:
`contrib/appsi/cmodel/appsi_cmodel.cpython-313-x86_64-linux-gnu.so`, 1 367 496 bytes, SHA-256
`2cf52b15480ea9b7…`. No static archives, no bundled solvers, no plugin shims, and therefore **no
disabled distributed bytes**: the [A10] count for this candidate is zero.

`pyomo-6.10.1.dist-info/` declares `License-Expression: BSD-3-Clause` and **carries its notice**, at
`licenses/LICENSE.md` (16 947 bytes, SHA-256 `a57ea3ac2d2dec65…`, copyright National Technology and
Engineering Solutions of Sandia, LLC). On notice hygiene this candidate is clean where CasADi is
not.

### 3.2 What the installing machine builds (measured)

PyNumero's ASL interface is **not distributed**. `pyomo build-extensions` compiles it on the host
into `~/.pyomo/lib` (see `docs/backend-environments.md` §4 for the build sequence and its nonzero
exit):

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `libasl.a` | 3 112 408 | `5247eaf10b4c27d7…` |
| `libasl2.a` | 2 775 730 | `5f29d81e60d6f402…` |
| `mcppInterface.so` | 640 000 | `df71365f1a85320a…` |
| **`libpynumero_ASL.so`** | **479 520** | **`a63bc651c1c34967…`** |
| `libcspline_external.so` | 147 072 | `5e737b3016a9dde6…` |
| `libaslfunctions.so` | 20 472 | `fcd8d47c9701f505…` |
| `libasl_external_demo.so` | 15 576 | `35fb5a478bb457e0…` |

`libpynumero_ASL.so` reproduces the size and hash recorded in `docs/backend-environments.md` §4
exactly. It needs only `libstdc++`, `libm`, `libgcc_s` and `libc`, and embeds the AMPL Solver
Library (`ASL_alloc`, `AMPL_version_ASL`, `addfunc_ASL`, …).

**These bytes are a product of the installing machine, not bytes this project would redistribute** —
which changes the shape of the distribution question rather than removing it. The build leaves **no
notice file for the ASL itself**; the only notice anywhere under `~/.pyomo` is `src/mcpp/LICENSE`.
The ASL's terms are therefore **unresolved from the installed artifacts** and would have to be read
from the upstream `ampl/asl` source the build fetched. This audit does not guess them.

---

## 4. Summary table

| | CasADi 3.8.0 | Pyomo 6.10.1 + built ASL |
| --- | --- | --- |
| Compiled objects distributed | 232 (119 distinct), 240 481 560 B | 1, 1 367 496 B |
| Loaded by the P02 route | 19 384 616 B | ASL built on the host |
| **Disabled distributed bytes [A10]** | **1 885 160 B, 12 objects** | **0** |
| Notice in the metadata directory | **none** | `licenses/LICENSE.md` present |
| Notices in the package tree | 81 files, 40 components, 430 274 B | none |
| Declared own licence | LGPL-3.0-or-later | BSD-3-Clause |
| Restrictive notice found | **METIS 4.0, in `libcoinmetis.so*` (918 624 B)** | none |
| Compiled bytes with no notice | 5 723 463 B, 8 objects | ASL terms unresolved |
| Proprietary vendor code shipped | none | none |

## 5. Reproduction in a clean environment

Plan §8.1 day 9. An inventory that only describes the machine that produced it is a description,
not evidence. Both wheels were installed again from PyPI at their pinned versions into fresh virtual
environments with `pip install --no-cache-dir` — so the wheel was re-downloaded rather than taken
from the local cache — and every file was compared against the hashes recorded in §2 and §3:

```bash
python3 -m venv /tmp/repro-casadi && /tmp/repro-casadi/bin/pip install --no-cache-dir casadi==3.8.0
python3 -m venv /tmp/repro-pyomo  && /tmp/repro-pyomo/bin/pip  install --no-cache-dir Pyomo==6.10.1
.venv/bin/python scripts/p03_verify_reproduction.py \
    --casadi-root /tmp/repro-casadi --pyomo-root /tmp/repro-pyomo
```

Result, in `spikes/p03/results/reproduction.json`:

| | CasADi | Pyomo wheel |
| --- | --- | --- |
| Files recorded | 2 384 | — |
| Present in the clean install | 2 384 | — |
| **Byte-identical** | **2 376** | 2 of 2 artifacts |
| Shipped files that differ | **0** | 0 |
| Install-generated files that differ | 8 | — |
| Missing / unexpected | 0 / 0 | — |

**Every one of the 232 compiled objects, all 81 notices and all 1 681 headers reproduce byte for
byte.** The eight differences are all `__pycache__/*.pyc` bytecode caches, which CPython writes on
first import and which embed the source path and mtime; they are generated by the install, not
shipped in the wheel. The script reports them in their own category and prints the count, so the
exemption is visible rather than silent.

For Pyomo, `appsi_cmodel.cpython-313-x86_64-linux-gnu.so` and `dist-info/licenses/LICENSE.md` both
match their recorded hashes.

**Not attempted:** re-deriving PyNumero's ASL library. `pyomo build-extensions` writes into the
shared `~/.pyomo`, so rebuilding it would overwrite the exact artifact the P02 evidence manifest
references by hash. It is recorded as **not re-derived**, not as verified. Re-deriving it would also
test something different from the above — whether a *compile* is reproducible on this host, not
whether a download is — and compilation reproducibility is not a P03 question.

## 6. What this audit does not establish

It does not select a backend and does not decide whether the project may distribute either
candidate: those are ADR 0003 and ADR 0006. It measures no performance and verifies no derivative.
Every figure comes from one host and one platform, from the two environments
`scripts/build-backend-envs.sh` produces, and the P02 limitation that no CI has ever run applies
here too. Where a component's terms could not be read off a shipped artifact, this document says
**unresolved**; unresolved is not a synonym for permissive, and no entry in §2.7 or §3.2 may be
cited as a clearance.
