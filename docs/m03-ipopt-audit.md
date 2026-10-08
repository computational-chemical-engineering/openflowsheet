# M03 [A10] audit of the Ipopt distribution for the optional general-NLP path

**Package:** M03, work order WO-6. **Requirement:** [A10] (binary-licence audit) for the new binary
closure of the A06 bridge; gate **G-A10** of `docs/derivations/M03-studies-spec.md` §9; assertion
A41. **Authority:** ADR 0032 D5; ADR 0006 D1.5, D2.1, D2.4 and Amendment 1 (R-135); specification
§14 Q-F5, N1, N3. **Recorded by:** the build lane (Opus 5.5), 2026-10-08, branch `wp/M03-audit`.
**Precedent followed:** `docs/p03-binary-audit.md` and `scripts/p03_binary_inventory.py`, whose
helpers the inventory script reuses.

This document is the inventory and the gate verdict. It is not a legal opinion, and it does not
accept the licences: that is Frank's N1 (§7). Every number and hash quoted here is read from
`benchmarks/m03/ipopt-inventory-x86_64.json`, which the script writes and checks:

```bash
scripts/build-m03-ipopt-env.sh [prefix] [cache]          # default .venv-nlp, .reference-downloads/m03-ipopt
.venv/bin/python scripts/m03_ipopt_inventory.py --env .venv-nlp            # write the inventory
.venv/bin/python scripts/m03_ipopt_inventory.py --env .venv-nlp --check    # reproduce it (NLP-1, §9)
```

As in P03, three grades of statement are kept apart: **measured** (a size, a SHA-256, a `DT_NEEDED`
entry, an exported symbol, a mapped path), **declared** (what a package's metadata says about its
licence), and **read** (a licence identified in a notice file). An object's licence is read from a
notice the package ships, or from the upstream source the package's own recipe names and hashes
(three objects, §6.5), or it is recorded `unresolved`. No upstream licence is asserted from general
knowledge.

---

## 1. Verdict

**Verdict: PASS** — for linux x86-64, CPython 3.13.5, on the route of §3.1 (a user-space conda-forge
environment built by `scripts/build-m03-ipopt-env.sh`). Q-F5 is answered: an auditable Ipopt + ASL
distribution exists for this platform. WO-8 declared the `nlp` extra on branch `wp/M03` in a commit
of its own, which is not merged before Frank answers N1 and reverts alone if he declines.

| Item | Outcome | Evidence (details in §6) |
| --- | --- | --- |
| G1 | **PASS** | 178 mapped ELF objects (287 574 499 bytes, 178 distinct SHA-256), each with path, size, SHA-256, SONAME, `DT_NEEDED`, owner and licence; no object of unknown origin; both import orders map the same set; every conda-owned object equals its package's recorded bytes (five after conda's prefix relocation, verified by re-applying it) |
| G2 | **PASS** | Mapped from the CasADi package: `_casadi.so` and `libcasadi.so.3.7` only; neither is in the CasADi wheel's METIS closure (55 objects, derived from the wheel's own `DT_NEEDED` graph); no mapped CasADi path names `ipopt`/`mumps`/`metis`; `casadi.nlpsol` raised-if-called and was called 0 times in both orders |
| G3 | **PASS** | One `METIS_` exporter is mapped: conda-forge `metis-5.1.0` `libmetis.so` (`970cd095…`); it defines `METIS_SetDefaultOptions` and `METIS_Free` and none of `METIS_EstimateMemory`, `METIS_mCPartGraphKway`, `METIS_EdgeND`: METIS 5 by ADR 0006 D2.1's binary test |
| G4 | **PASS** | No mapped object defines or imports an `ma27`/`ma57`/`ma77`/`ma86`/`ma97` routine or is named `*hsl*`; Ipopt's own banner: `This is Ipopt version 3.14.20, running with linear solver MUMPS 5.8.2.`; `linear_solver = mumps` set and recorded |
| G5 | **PASS** | No mapped object is restrictive, GPL without an exception, or unresolved. Four are the GCC runtime under GPL-3.0 with the GCC Runtime Library Exception (R-135's class), five LGPL (ADR 0006 Q1, Amendment 1: CasADi's two, numpy's and scipy's `libquadmath`, conda-forge `libiconv`); numpy's and scipy's `libgfortran` are dispositioned by ADR 0006 Amendment 1 exactly as in T08.A30. Subject to Frank's N1 (§7) |
| G6 | **PASS** | `pyproject.toml` names `pyomo` and `cyipopt` only in the optional `nlp` extra (WO-8; at WO-6's audit, nowhere); `tests/test_m03_nlp_isolation.py` (default gate) imports every `openflowsheet` module but WO-8's adapter in a fresh interpreter and asserts neither is loaded |
| G7 | **PASS** | Exact versions and hashes: three committed locks (§8), micromamba and three upstream sources pinned by SHA-256 in the build script; route documented in `docs/reference-environments.md` §8. Measured: two builds at different prefixes and cache paths (the second with a cold download cache) give identical conda and pip fingerprints and the same `libpynumero_ASL.so` (`6646bbdd…`), and `--check` against the second build reproduces the committed inventory |
| G8 | **PASS** | This document, committed on `wp/M03-audit` before any `nlp` code |

What would turn the verdict: a pin change of any package in the locks (re-run the build and
`--check`; a licence change at a new pin is a new finding, R-135's last paragraph), WO-8's NLP-1
workload mapping an object this stand-in workload did not (§9.1; measured by WO-8: it maps the same
178 objects), or Frank declining N1.

---

## 2. Facts the probe already had (confirmed, not re-litigated)

- PyPI has no binary cyipopt wheel for linux/CPython 3.13; Pyomo 6.10.1's wheel carries no
  `libpynumero_ASL`; the host has no system Ipopt.
- conda-forge carries **no current `libpynumero_ASL` either**: `pynumero_libraries` was last built
  in 2020-05, for CPython ≤ 3.8 and numpy < 2 (measured from the conda-forge file list). Every route
  therefore compiles `libpynumero_ASL` from Pyomo's sources (§4.3).
- The CasADi wheel's Ipopt is in the METIS 4 closure and is neither used nor loaded (G2).
- The host already has a P03-era `~/.pyomo/lib/libpynumero_ASL.so` whose ASL terms P03 recorded as
  unresolved. **Measured:** with `PYOMO_CONFIG_DIR` unset, Pyomo's `find_library` in this
  environment resolves to `~/.pyomo/lib/libpynumero_ASL.so`, not the audited one. The route
  therefore sets `PYOMO_CONFIG_DIR` (§9.2).

---

## 3. Candidate routes

### 3.1 Chosen: a user-space conda-forge environment (specification N3's default)

micromamba 2.9.0 (conda-forge `micromamba-2.9.0-0.tar.bz2`, SHA-256 `8761c382…3040dd`, a static
binary; no root, nothing outside the prefix and the cache) creates the environment from an explicit
lock with no solve. Three layers:

1. **conda-forge** (`benchmarks/m03/nlp-conda-explicit.txt`, 41 packages): CPython 3.13.5, Ipopt
   3.14.20, MUMPS 5.8.2 (sequential, gfortran), METIS 5.1.0, Scotch 7.0.11, SPRAL 2025.09.18,
   OpenBLAS 0.3.34 (OpenMP), ampl-asl 1.0.0, cyipopt 1.7.0 and their runtimes. cyipopt is listed
   without its `numpy` dependency so that numpy comes from layer 2.
2. **PyPI wheels** (`benchmarks/m03/nlp-pip.lock`, 12 wheels, `--no-deps --require-hashes
   --only-binary`): the default runtime closure at `requirements.lock`'s versions (numpy 2.2.4,
   scipy 1.15.3, casadi 3.8.0, PyYAML, jsonschema and its closure), pyomo 6.10.1 and packaging
   26.3. **Measured:** numpy's, scipy's, casadi's, PyYAML's and rpds-py's compiled objects have the
   same per-distribution `objects_digest` as T08.A30's audit of the default install
   (`same_objects_as_t08_a30: true`), so the default numerical stack in this environment is the
   audited one, byte for byte.
3. **`libpynumero_ASL.so`**, compiled by the build script (§4.3).

Why the interpreter is conda-forge's: cyipopt's only binary distribution for CPython 3.13 is
conda-forge's, built against conda-forge's CPython; the interpreter and its standard-library
extensions (31 objects, 41 652 696 bytes) are therefore part of the inventory and of G5.

### 3.2 Evaluated and rejected: Debian packages plus cyipopt from sdist

Possible without root (`apt-get download`, `dpkg-deb -x` into a scratch tree; nothing installed).
The closure of `coinor-libipopt3` and `libamplsolver0` was downloaded (221 packages) and its
binaries inspected; it was not built into a solve, because route 3.1 passes and the measured
closure already decides against it:

- Debian's Ipopt (`coinor-libipopt3` 3.14.17-3) is linked against the **MPI** MUMPS: `libipopt.so.3`
  needs `libdmumps-5.7.so` **and `libmpi.so.40`**; `libdmumps-5.7.1.so` needs
  `libscalapack-openmpi.so.2.2` and `libmpi_mpifh.so.40`. The NLP path would load OpenMPI and
  ScaLAPACK and initialise MPI inside the Python process. Debian's sequential MUMPS
  (`libmumps-seq-5.7`) exists but Debian's Ipopt is not built against it.
- Debian has no cyipopt and no Pyomo; cyipopt would be compiled with the host compiler against a
  relocated `ipopt.pc`, and the extracted tree needs `LD_LIBRARY_PATH` — not an install mechanism a
  user would follow, and not pinned by the archive (Debian's pool moves with point releases).
- `libasl0t64` in Debian is a different "ASL" (the Advanced Simulation Library); the AMPL Solver
  Library is `libamplsolver0` 0~20190702-4 (2019 sources).

### 3.3 Not evaluated: a source build

The specification asks for it only if the first two routes fail. Route 3.1 compiles exactly one
object from source (`libpynumero_ASL`), which no binary distribution provides.

---

## 4. The audited environment

### 4.1 Host

Debian 13, x86-64, glibc 2.41. Platform objects mapped by the solve: `ld-linux-x86-64.so.2`,
`libc.so.6`, `libdl.so.2`, `libm.so.6`, `libpthread.so.0`, `librt.so.1`, `libutil.so.1` (dpkg
`libc6`). They are inventoried with hash and copyright notice but not judged under G5, as in
T08.A30: the C library is the platform every Python process runs on, not part of the route.
`--check` compares them by path and package only and prints hash drift without failing.

### 4.2 The workload

A fresh interpreter of the environment (`python -I`, `PYTHONNOUSERSITE=1`,
`PYOMO_CONFIG_DIR=<env>/share/pyomo`, an empty working directory) imports every `openflowsheet`
module (the three `server`-extra bindings, `http`, `mcp` and M06's `web`, are skipped: this
environment does not install that extra) and the NLP stack in **both orders**, replaces
`casadi.nlpsol` by a function that raises, and solves a two-variable PyNumero `ExternalGreyBoxModel` problem through Pyomo's `cyipopt` solver
(min a + 2b subject to ab = 1, a, b ≥ 0.1) whose residual and Jacobian are CasADi `Function`s, as the
adapter's will be. Options: `linear_solver = mumps`, `hessian_approximation = limited-memory`,
`limited_memory_max_history = 6`, `tol = 1e-10`. Outcome in both orders: `optimal`, maximum error
against (√2, 1/√2) 8.3e-13; Ipopt 3.14.20 with MUMPS 5.8.2; `libpynumero_ASL` loaded from
`$ENV/share/pyomo/lib/libpynumero_ASL.so`. The script then reads `/proc/self/maps`.

### 4.3 `libpynumero_ASL.so` — where it comes from

Compiled by `scripts/build-m03-ipopt-env.sh` from the **installed Pyomo 6.10.1's own sources**
(`pyomo/contrib/pynumero/src/AmplInterface.cpp` and the `FindASL.cmake` it includes; sources digest
`dedd8288…` in the build record) with the conda-forge GCC 15.3.0 toolchain of
`benchmarks/m03/nlp-build-conda-explicit.txt`, against the environment's **conda-forge `ampl-asl`
1.0.0 `libasl.so`** (not a GitHub download), with `ENABLE_HSL`, `BUILD_MA27`, `BUILD_MA57` and
`BUILD_AMPLASL` off. It needs `libasl.so`, `libstdc++.so.6`, `libm`, `libgcc_s`, `libc`; its only
search path is `$ORIGIN/../../../lib` (the toolchain's own `-rpath` to the build environment is
removed by a specs file, so no build path is embedded — checked by the script). SHA-256
`6646bbdd51332c3a5b306604fe0f6bd572d7cec352af994c76bfe1cdf550161c`, 43 952 bytes, reproduced
exactly by a second build at a different prefix and cache path.

Licence: the code is Pyomo's, BSD-3-Clause, read from `pyomo-6.10.1.dist-info/licenses/LICENSE.md`
(National Technology and Engineering Solutions of Sandia). The ASL it links is a separate object:
`libasl.so` from `ampl-asl-1.0.0-h5888daf_2`, declared `BSD-3-Clause AND SMLNJ`, notices read
`info/licenses/LICENSE` (BSD 3-Clause, AMPL Optimization, Inc., 2017–2023) and
`info/licenses/src/f2c/Notice` (AT&T, Lucent Technologies and Bellcore, a permissive
"permission to use, copy, modify, and distribute … without fee" notice). This resolves what P03
left unresolved for its own GitHub-fetched ASL build.

---

## 5. Loaded objects

| Origin | Objects | Bytes |
| --- | ---: | ---: |
| conda-forge packages | 60 | 144 570 819 |
| PyPI wheels (numpy 15, scipy 91, casadi 2, PyYAML 1, rpds-py 1) | 110 | 139 703 952 |
| built here (`libpynumero_ASL.so`) | 1 | 43 952 |
| platform (`libc6`) | 7 | 3 255 776 |
| **total** | **178** | **287 574 499** |

The conda-forge interpreter (`python-3.13.5-hec9711d_102_cp313`: `python3.13` and 30 `lib-dynload`
modules, Python-2.0, notice read) aside, every compiled object the NLP stack adds:

| Object | Package | Bytes | SHA-256 | Declared | Read from notice | Category |
| --- | --- | ---: | --- | --- | --- | --- |
| `libipopt.so.3.14.20` | ipopt-3.14.20-hec1326d_0 | 2811800 | `b9533a59f740964c…` | EPL-1.0 | EPL-2.0 | identified |
| `ipopt_wrapper.cpython-313-x86_64-linux-gnu.so` | cyipopt-1.7.0-py313hddd399a_1 | 329632 | `e4fec9aa97eee9b9…` | EPL-2.0 | EPL-2.0 | identified |
| `libdmumps_seq.so` | mumps-seq-5.8.2-gfortran_hfb83c00_3 | 2630993 | `293a78dde507e4bd…` | CECILL-C | CeCILL-C | identified |
| `libmumps_common_seq.so` | mumps-seq-5.8.2-gfortran_hfb83c00_3 | 666640 | `f1631e2f6df0db55…` | CECILL-C | CeCILL-C | identified |
| `libmpiseq_seq.so` | mumps-seq-5.8.2-gfortran_hfb83c00_3 | 64209 | `e89953fba8bf2d8b…` | CECILL-C | CeCILL-C | identified |
| `libpord_seq.so` | mumps-seq-5.8.2-gfortran_hfb83c00_3 | 116217 | `31218006068efc29…` | CECILL-C | public domain (§6.5) | identified |
| `libmetis.so` | metis-5.1.0-h86e3903_1008 | 511824 | `970cd0958ae3fe03…` | Apache-2.0 | Apache-2.0 | identified |
| `libscotch.so.7.0.11` | libscotch-7.0.11-int64_h807e49d_3 | 751656 | `c7e1ae3818d9af97…` | CECILL-C | CeCILL-C | identified |
| `libscotcherr.so.7.0.11` | libscotch-7.0.11-int64_h807e49d_3 | 15784 | `b9522b9ca5dd40d2…` | CECILL-C | CeCILL-C | identified |
| `libesmumps.so.7.0.11` | libscotch-7.0.11-int64_h807e49d_3 | 38624 | `e7137a8336bff9c9…` | CECILL-C | CeCILL-C | identified |
| `libspral.so` | libspral-2025.09.18-h74cae3c_2 | 964544 | `5d9dce52b5738f3c…` | BSD-3-Clause | BSD | identified |
| `libhwloc.so.15.10.2` | libhwloc-2.13.0-default_he001693_1000 | 430912 | `38b44ce502e69506…` | BSD-3-Clause | BSD | identified |
| `libxml2.so.16.1.4` | libxml2-16-2.15.4-hbdfff7e_1 | 1448664 | `7cfc6fe6fcd07e5f…` | MIT | MIT | identified |
| `libiconv.so.2.7.0` | libiconv-1.18-h0cb94f2_3 | 1182640 | `59b942b8a9dfabcf…` | LGPL-2.1-only | LGPL-2.1 | lgpl |
| `libopenblasp-r0.3.34.so` | libopenblas-0.3.34-openmp_h156ec52_2 | 41559024 | `5a345212e7311feb…` | BSD-3-Clause | BSD-3-Clause | identified |
| `libomp.so` | llvm-openmp-23.1.3-h7148c6a_0 | 1473824 | `96fa1d63fa1ee014…` | Apache-2.0 WITH LLVM-exception | Apache-2.0, LLVM exception | identified |
| `libgfortran.so.5.0.0` | libgfortran5-16.2.0-h6b99dfc_7 | 11532656 | `8b93406aef97f0f3…` | GPL-3.0-only WITH GCC-exception-3.1 | GCC exception text | gpl-with-gcc-runtime-exception |
| `libquadmath.so.0.0.0` | libgcc-16.2.0-ha9f2e26_7 | 991312 | `9fa4807097fa47da…` | GPL-3.0-only WITH GCC-exception-3.1 | GCC exception text | gpl-with-gcc-runtime-exception |
| `libgcc_s.so.1` | libgcc-16.2.0-ha9f2e26_7 | 922624 | `5444fbe71e8cfe3b…` | GPL-3.0-only WITH GCC-exception-3.1 | GCC exception text | gpl-with-gcc-runtime-exception |
| `libstdc++.so.6.0.36` | libstdcxx-16.2.0-h934c35e_7 | 23874544 | `10f0d3c46c070acd…` | GPL-3.0-only WITH GCC-exception-3.1 | GCC exception text | gpl-with-gcc-runtime-exception |
| `libasl.so` | ampl-asl-1.0.0-h5888daf_2 | 671208 | `bfe531a3e3afefcd…` | BSD-3-Clause AND SMLNJ | BSD-3-Clause; f2c notice | identified |
| `libpynumero_ASL.so` | built here (§4.3) | 43952 | `6646bbdd51332c3a…` | BSD-3-Clause (Pyomo) | BSD-3-Clause | identified |

Interpreter-closure objects from conda-forge (loaded by CPython's standard library, not by the NLP
stack): `libcrypto.so.3` (openssl, Apache-2.0), `libsqlite3.so.3.53.4` (blessing, §6.5, loaded by
`openflowsheet.application.store`), `libuuid.so.1.3.0` (BSD-3-Clause, §6.5), `libffi`, `libbz2`,
`liblzma`, `libmpdec`, `libz` — all `identified`. The full rows, with every notice path and hash,
are in the JSON.

"Read" identifiers are pattern hits on the notice text (P03's patterns plus a few added in the
script). P03's 2-clause pattern matches every BSD text, so a BSD-2 hit beside a BSD-3 declaration
is not a conflict and is written "BSD" above.

---

## 6. Gate evidence

### 6.1 G2 — CasADi's METIS closure

The closure is derived, not listed: every ELF in the installed CasADi package, its `DT_NEEDED`
graph, and the objects defining `METIS_EstimateMemory` or `METIS_mCPartGraphKway` (the 4.x API).
It has 55 members and contains all seven plugin families ADR 0006 D1.5 names (`conic:cbc`,
`conic:clp`, `linsol:mumps`, `nlpsol:bonmin`, `nlpsol:ipopt`, `nlpsol:sleqp`, `nlpsol:uno`);
`_casadi.so` and `libcasadi.so.3.7` are outside it. Negative control (read with `nm`, never
loaded): CasADi's `libcoinmetis.so.2` defines `METIS_EstimateMemory`, `METIS_mCPartGraphKway`,
`METIS_EdgeND` and neither 5.x symbol, so the G3 test does reject it. The conda-forge Ipopt and
MUMPS are distinct objects at distinct paths; nothing under `site-packages/casadi/` but the two
core objects is mapped.

### 6.2 G3 — which METIS

`libmetis.so`, conda-forge `metis-5.1.0-h86e3903_1008` (SHA-256
`970cd0958ae3fe03ea5ce223d7b3fd68e1b05d3be2106fb9bd256afe00cf22e3`), exports 21 `METIS_` symbols
including `METIS_SetDefaultOptions` and `METIS_Free`, and none of the three 4.x-only symbols:
**METIS 5** by ADR 0006 D2.1's test. It is needed by `libdmumps_seq.so`,
`libmumps_common_seq.so` and `libspral.so`; `libmumps_common_seq.so` and `libspral.so` import
`METIS_` symbols from it. No other mapped object exports a `METIS_` symbol. The 5.1.0 minor version
is the package's statement; the binary test establishes "5.x".

On disk but **not loaded**: Scotch's METIS-API emulation libraries `libscotchmetisv3.so` and
`libscotchmetisv5.so` (Scotch's own CeCILL-C code, not METIS). A future change that maps either is
caught by G3 (they export `METIS_` symbols).

### 6.3 G4 — no HSL, MUMPS

No mapped object defines or imports an HSL routine (`ma27*`, `ma57*`, `ma77*`, `ma86*`, `ma97*`,
Fortran or C names) and none is named `*hsl*`. `libipopt.so.3.14.20` does contain Ipopt's own EPL
**wrapper classes** for those routines (`Ipopt::Ma27TSolverInterface` … `Ma97SolverInterface`) and its
run-time loader for an `hsllib` library; they are not HSL code, and nothing is loaded through
them while `linear_solver = mumps` (recorded as `ipopt_hsl_interface_objects`). The banner Ipopt
prints names MUMPS 5.8.2 in both import orders. `libipopt` also links SPRAL (BSD-3-Clause), which
is loaded but not selected.

### 6.4 G5 — the licence findings

Categories over the 171 judged objects: 160 identified, 5 LGPL, 4 GCC runtime with exception,
2 GPL-family dispositioned (numpy's and scipy's vendored `libgfortran`, ADR 0006 Amendment 1, as
in T08.A30), 0 restrictive, 0 unresolved.

One declared licence disagrees with the notice its package ships: **conda-forge declares Ipopt
`EPL-1.0`; the shipped `LICENSE` is the Eclipse Public License 2.0** (Ipopt 3.14 is EPL-2.0
upstream; the recipe's metadata is stale). The notice is what this audit reads; N1 lists EPL-2.0.

### 6.5 Three objects whose package notice is missing or wrong

The rule is that an object's licence is read from a notice. For three objects the package-level
notice would attribute the wrong text or none, so the build script fetches the upstream source the
package's own recipe names and hashes, verifies the hash, and extracts the one notice:

| Object | Package notice | Read instead | Source (URL, SHA-256 = the recipe's) |
| --- | --- | --- | --- |
| `libsqlite3.so.3.53.4` | none shipped | the `sqlite3.h` header comment: public-domain dedication with the blessing | `sqlite-autoconf-3530400.tar.gz`, `0e948390…16eb9c` |
| `libuuid.so.1.3.0` | util-linux's top-level `COPYING`, the **GPL-2.0** — util-linux's default for code without its own licence | `libuuid/COPYING` → `Documentation/licenses/COPYING.BSD-3-Clause` | util-linux `v2.42.4.tar.gz`, `e1d38037…891fe7` |
| `libpord_seq.so` | MUMPS's `LICENSE`, which **excludes PORD** ("see PORD/README for License information") | `PORD/README`: "SPACE-1.0 (which includes PORD) is in the public domain" | `MUMPS_5.8.2.tar.gz`, `eb515aa6…4db7039` |

Without the libuuid correction the script's conflict rule (a shipped GPL text under a non-GPL
declaration) makes the object `unresolved`; this was measured, and is how the case was found.

### 6.6 G6 and G7

G6: `pyproject.toml` at WO-6's commit had no `nlp` extra and named neither library; since WO-8 it
names them only in that extra (the inventory's G6 record: `nlp_extra_declared: true`);
`tests/test_m03_nlp_isolation.py::test_the_default_modules_import_no_nlp_library` walks every module
except `openflowsheet.studies.nlp.greybox` (WO-8's adapter, the one module allowed to import them).

G7, measured on 2026-10-08:

| Build | Prefix / cache | conda fingerprint | pip-freeze fingerprint | `libpynumero_ASL.so` |
| --- | --- | --- | --- | --- |
| 1 | `…/nlp`, `…/cache` | `51a33c8d…537790b1` | `621262d4…565907a5` | `6646bbdd…550161c` |
| 2 | `…/nlp-second-prefix`, `…/cache-second-with-a-longer-path` (cold) | `51a33c8d…537790b1` | `621262d4…565907a5` | `6646bbdd…550161c` |

The inventory was written from build 1; `--check --env <build 2>` passed. Five conda objects
(`python3.13`, `libcrypto.so.3`, `libhwloc`, `libuuid`, `libxml2`) carry a prefix that conda
rewrites at install; their recorded SHA-256 is the package file's, and the script verifies that the
installed bytes equal that file relocated to the actual prefix. Every other conda-owned object
equals its package's recorded hash. A build takes about 25 s with a warm package cache.

---

## 7. N1 — the licences Frank is asked to accept for the optional `nlp` extra

Exactly as found on the objects the NLP path loads (beyond the default install, whose objects are
T08.A30's and unchanged here):

| Licence (as read) | Objects |
| --- | --- |
| EPL-2.0 | Ipopt 3.14.20 (`libipopt`; conda-forge's metadata says EPL-1.0, the shipped text is EPL-2.0), cyipopt 1.7.0 (`ipopt_wrapper`) |
| CeCILL-C | MUMPS 5.8.2 (`libdmumps_seq`, `libmumps_common_seq`, `libmpiseq_seq`), Scotch 7.0.11 (`libscotch`, `libscotcherr`, `libesmumps`) |
| Public domain | PORD (`libpord_seq`, MUMPS's bundled ordering), SQLite 3.53.4 (blessing) |
| Apache-2.0 | METIS 5.1.0 (`libmetis`), OpenSSL 3.6.5 (`libcrypto`) |
| Apache-2.0 WITH LLVM-exception | LLVM OpenMP 23.1.3 (`libomp`) |
| BSD-3-Clause | OpenBLAS 0.3.34 (with LAPACK's BSD notice), SPRAL 2025.09.18, hwloc 2.13.0, libuuid 2.42.4, Pyomo 6.10.1 (`libpynumero_ASL`, compiled here) |
| BSD-3-Clause and the f2c/AT&T permissive notice (conda-forge: `SMLNJ`) | AMPL Solver Library, ampl-asl 1.0.0 (`libasl`) |
| MIT | libxml2 2.15.4, libffi 3.4.6 |
| LGPL-2.1 (declared `-only`) | GNU libiconv 1.18 (needed by libxml2 ← hwloc ← SPRAL ← Ipopt) |
| GPL-3.0 WITH GCC Runtime Library Exception 3.1 | conda-forge GCC 16.2.0 runtime: `libstdc++`, `libgcc_s`, `libgfortran`, `libquadmath` (R-135's class; R-135 named numpy's and scipy's copies) |
| PSF-2.0 (Python-2.0) | conda-forge CPython 3.13.5 and its standard-library extensions |
| bzip2-1.0.6, 0BSD, BSD-2-Clause, Zlib | bzip2, xz `liblzma`, `libmpdec`, zlib (CPython's standard-library closure) |

Two items Frank may want to look at specifically: **LGPL-2.1-only** (`libiconv`) — ADR 0006 Q1 and
Amendment 1 cover "the LGPL" and named LGPL-2.1-or-later; and the **GCC runtime from conda-forge**
rather than from numpy/scipy, the same licence class R-135 ruled on. Not loaded but present in the
environment: `readline` 8.3 (GPL-3.0-only) and `ncurses`, which CPython loads only for an
interactive prompt (§9.3).

---

## 8. Pins

- `benchmarks/m03/nlp-conda-explicit.txt` — 41 conda-forge packages by URL and MD5 (SHA-256 of
  each in the inventory's `conda_packages`).
- `benchmarks/m03/nlp-pip.lock` — 12 PyPI wheels by version and SHA-256.
- `benchmarks/m03/nlp-build-conda-explicit.txt` — the build toolchain (GCC 15.3.0, CMake 4.4.4,
  make 4.4.1), never loaded at run time.
- In the build script: micromamba 2.9.0 and the three recipe-named upstream sources, by SHA-256.

The `nlp` extra was **not** added by WO-6 (N1 pending). Drafted for WO-8, which declared it verbatim
in a commit of its own on `wp/M03` (still pending N1):

```toml
# M03 ADR 0032 D5: the optional general-NLP bridge. Installable only into the audited environment
# of docs/m03-ipopt-audit.md (scripts/build-m03-ipopt-env.sh), which provides cyipopt 1.7.0 from
# conda-forge and libpynumero_ASL; PyPI has no cyipopt wheel for CPython 3.13.
nlp = [
    "pyomo==6.10.1",
    "cyipopt==1.7.0",
    "packaging==26.3",  # Pyomo detects numpy through packaging.version and does not declare it
]
```

`packaging` is in the draft because **measured**: without it, PyNumero reports numpy unavailable
(`DeferredImportError … No module named 'packaging'`).

---

## 9. Findings that bind WO-8 (recorded, not designed here)

1. **G1 was measured on a stand-in problem, not NLP-1** (WO-7/WO-8 do not exist yet). The workload
   imports every `openflowsheet` module, so the default stack's extension modules are loaded; an
   object NLP-1 maps that the stand-in did not would change the inventory. WO-8 should re-run
   `scripts/m03_ipopt_inventory.py --check` with NLP-1 as the workload, and A39 enforces G2 per run.
2. **`libpynumero_ASL` resolution.** Pyomo searches the working directory, then
   `$PYOMO_CONFIG_DIR/lib` (default `~/.pyomo/lib`), then `LD_LIBRARY_PATH` and `PATH`. On this host
   the default finds P03's unaudited build. The adapter should set or require
   `PYOMO_CONFIG_DIR=<env>/share/pyomo` and check `AmplInterface.libname`'s SHA-256 against the
   inventory before solving.
3. **User site-packages.** conda-forge's CPython enables the user site (`~/.local/lib/python3.13/
   site-packages`, which on this host holds unrelated packages). Run with `PYTHONNOUSERSITE=1`.
4. **Linear solver.** Keep `linear_solver = mumps` explicit (§8.4 of the specification already
   does): `libipopt` carries an `hsllib` loader that would load an HSL library if one were asked
   for and found. An A39-style per-run check that no `*hsl*` object is mapped costs nothing.
5. **Two BLAS and an OpenMP runtime in one process.** numpy/scipy use their vendored OpenBLAS;
   Ipopt and MUMPS use conda-forge's OpenMP OpenBLAS with LLVM `libomp`. Whether MUMPS/Ipopt results
   are bitwise reproducible run to run with threaded BLAS is a numerics question for WO-8's Q-F2
   measurements (for example under `OMP_NUM_THREADS=1`); this audit does not answer it.
6. **The interpreter differs from the default install's.** The NLP environment runs conda-forge's
   CPython 3.13.5, not the host's; the default numerical stack's binaries are identical (§3.1), but
   cross-environment bitwise claims (V1's re-solve compared with a default-install solve) are
   WO-8's to measure, not this audit's to assume.

**WO-8's answers (build lane, 2026-10-08, branch `wp/M03`).** Measured with the adapter
`openflowsheet.studies.nlp.greybox`; the numbers are in `benchmarks/m03/nlp-measurements.json` and
the inventory.

1. **G1 on NLP-1.** `scripts/m03_ipopt_inventory.py` now solves NLP-1 through the adapter with
   §8.4's options (its default workload; `--workload stand-in` reproduces WO-6's record). Both
   import orders map exactly the stand-in's 178 objects, no object is added or lost, and G1-G6
   stay PASS; the committed inventory carries the NLP-1 workload (status `KKT_POINT_VERIFIED`,
   decision error 2.7e-12 scaled) and `--check` reproduces it.
2. **`libpynumero_ASL`.** The adapter checks `AmplInterface.libname`'s SHA-256 against
   `closure.AUDITED_PYNUMERO_ASL_SHA256` (`6646bbdd…`, a default-gate test ties it to this
   inventory) before any solve, and refuses with `UNSUPPORTED(NLP_SOLVER_UNAVAILABLE)` naming
   `PYOMO_CONFIG_DIR` otherwise. `scripts/m03_nlp_check.sh` sets `PYOMO_CONFIG_DIR`.
3. **User site.** `scripts/m03_nlp_check.sh` sets `PYTHONNOUSERSITE=1`.
4. **Linear solver and HSL.** `linear_solver = mumps` is passed explicitly; before any solve the
   adapter refuses if a mapped object is named `*hsl*` or is a CasADi object naming
   `ipopt`/`mumps`/`metis`, and A39's test re-derives the CasADi METIS closure (55 objects) and
   finds none of it mapped after the NLP-1 solve.
5. **Threads.** With the default OpenMP thread count (48 on this host) MUMPS/OpenBLAS results
   differ run to run in the last bits: NLP-1's returned split fraction by 1 ulp, every verdict
   identical; NLP-INF's three starts take 498 iterations in one run and 597 under
   `OMP_NUM_THREADS=1`. `OPENBLAS_NUM_THREADS=1` alone does not make runs reproducible;
   `OMP_NUM_THREADS=1` does (four runs, every value but the wall times bitwise identical), and
   NLP-1's whole report then takes 1.7 s instead of 3.2-3.9 s. The check script, the NLP fixtures
   and the inventory's child set it.
6. **Across interpreters.** The V1-V6 verifier at NLP-1's reference optimum emits, in this
   environment's CPython 3.13.5, the byte-identical candidate document the default install emits
   (`tests/fixtures/schemas/optimization_report/candidate/valid/nlp_1_reference_optimum.json`).

---

## 10. What this audit does not establish

- It is not a legal opinion, and it does not accept any licence: N1 is Frank's.
- Mode B (an artifact that contains these bytes) is not covered: the route installs from
  conda-forge and PyPI into the user's own prefix (mode A). Vendoring any of it would need the
  notice bundle of ADR 0006 D5 and a fresh audit.
- aarch64 and any Python other than 3.13.5 are not audited.
- Object-level attribution inside a conda package is package-level (each object gets its package's
  notices), except for the three objects of §6.5; that is an inference, as P03's name rule was.
- It says nothing about Ipopt's numerical behaviour on NLP-1 (WO-8, Q-F2) or about PyNumero's
  evaluation-error path (Q-F4).
