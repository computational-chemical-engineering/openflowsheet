# ADR 0006 — Distribution and data rights: what the project may ship, given what the selected backend's distribution actually contains

**Status:** Accepted as the project's working distribution policy — Fable verdict on the P03 audit, 2026-09-17 (plan §4.1 row P03; decision register R-A06). **Q1 was answered by Frank Peters on 2026-09-17: the LGPL is allowed.** The D3 reading is therefore confirmed rather than provisional, and ADR 0003 trigger T4 cannot fire on that ground. **Q2 was answered by Frank Peters on 2026-09-22: the recommended default is confirmed and neither R4 nor R5 is pursued.** **Nothing here asserts the project's right to distribute its own contributions** (blueprint §15; `docs/progress.md` "Notes for Frank" 2); the `LICENSE` file question stays with Frank. This is a procedural determination from notices read off shipped artifacts, not a legal opinion.  
**Date:** 2026-09-17  
**Author:** Fable 5.1, as `fable-verdict` (Fable owns every ADR, plan §1.3). Inventory and reproduction produced by the Opus 5 session (`docs/p03-binary-audit.md`); judged here.  
**Affected requirements:** D04 (licensing — "exact binary/data inventory and distribution verdict": this is the verdict), A10 (binary-license audit — the inventory's disabled-bytes count is discharged and its refresh obligation is fixed here), D03 (SuperLU stays the linear solver; now also a distribution constraint, D2.4), D20 and blueprint §8.3 (replay bundles reference the backend by hash; D1.3), blueprint §15 (Apache-2.0 core; "default install must not require GPL-licensed components"; "disabling a bundled plugin does not itself establish that distributing its bytes meets this policy"; "portable exports may omit restricted bytes and retain references"; "unknown rights are not assumed redistributable").  
**Affected packages:** K01 (declares the dependency and the notice statement, D5.1), K03 and ADR 0004 (no CasADi `Linsol` on a default path, D2.4), K05 (replay bundles by reference; second-platform inventory), M03 (no bundled Ipopt without a refreshed audit), T08 (owns D04 at release: the refreshed audit, the notice bundle for any vendored artifact, and gate V18 "distribution/data gates"), and any package that would build a container image or installer.  
**Blueprint authority:** §15, quoted above. §3.1 [A10] and §15 [A10] make the inventory and this verdict Phase-0 deliverables "refreshed when the selected binaries change".  
**Companion:** ADR 0003 selects CasADi 3.8.0; this ADR fixes the terms on which the project may distribute anything that depends on or contains it.  
**Evidence judged:** `docs/p03-binary-audit.md` §1–§6 (measured / declared / inferred grades as marked there), `spikes/p03/results/{casadi,pyomo}-inventory.json`, `spikes/p03/results/reproduction.json`, `docs/backend-environments.md` §4–§5, and a re-reading of `DT_NEEDED` entries off the installed objects on 2026-09-17 (see "Acceptance evidence").

## Decision in one sentence

The project may distribute its software as source plus a pinned PyPI dependency on `casadi==3.8.0`, with an LGPL notice statement, and may build replay bundles that reference that wheel by hash; it may **not** put the unmodified wheel's bytes inside anything it distributes — a container image, an installer, a batteries-included bundle, a mirror — until the METIS 4.0 object is removed from that artifact and the unresolved notices of D4 are settled, and no default execution path may load any object in the METIS closure.

## Context

The CasADi 3.8.0 manylinux wheel installs 2 384 files, 268 509 671 bytes, of which 240 481 560 bytes are 232 compiled objects (119 distinct; 126 628 591 bytes are duplicated SONAME copies because the wheel ships no symlinks). The route ADR 0003 selects loads exactly the `DT_NEEDED` closure of `_casadi.so` — `_casadi.so` and `libcasadi.so.3.7`, 19 384 616 bytes, both CasADi's own code — and system libraries; the remaining 215 424 720 bytes of shared objects are downloaded, installed and never executed on that route. The audit found, measured and declared: no proprietary vendor library; twelve disabled objects (ten plugin shims and two adaptor stubs, 1 885 160 bytes) that cannot run; 81 notice files across 40 components in the package tree and none in `dist-info/`; CasADi's own licence LGPL-3.0-or-later; **one restrictive notice** (METIS 4.0, compiled into `libcoinmetis.so.2.0.0`); and **eight compiled objects, 5 723 463 bytes, with no notice anywhere**. The download was reproduced byte-identically from PyPI in a clean environment. The rejected Pyomo route is recorded for completeness where it bears on a D04 obligation and nowhere else.

The architecture already distinguishes the distribution modes this ADR rules on. Blueprint §15 starts the project as "one installable package with optional extras", so the default deliverable is a Python package whose dependencies the *installer* fetches from PyPI. Blueprint §15 also says "portable exports may omit restricted bytes and retain references; report replay dependencies clearly", and K05's replay bundles detect a changed dependency by hash — so a replay bundle is a *reference* to the backend, not a copy of it, by design. Nothing in the plan through v0.2 requires a container image or an installer, but nothing forbids one either, so the vendored mode is ruled on now rather than discovered later.

## Decision

### D1. What the project may distribute

| Mode | What is conveyed | Ruling | Obligations |
| --- | --- | --- | --- |
| **A. Source plus pinned dependency** — the project's own package (sdist / wheel) declaring `casadi==3.8.0`; the user's `pip` fetches the CasADi wheel from PyPI | The project's own bytes only. No CasADi byte is redistributed by the project. | **Permitted**, conditional on the project's own rights (D6.1). | LGPL notice statement (D3.2, D5.1); pin recorded with the wheel's audited per-file hashes (D5.3); the [A10] audit refreshed on any pin change (D5.4). |
| **B. Vendored bytes** — a container image, an installer, an offline or "batteries-included" bundle, a package mirror, or a wheelhouse committed or published by the project, containing the CasADi wheel or its installed tree | All 240 481 560 compiled bytes unless pruned, including `libcoinmetis.so*` and the eight unresolved objects. | **Not permitted with the unmodified wheel.** Permitted only after (i) the METIS remedy of D2.3 is applied to *that artifact*, (ii) every D4 item that artifact still contains is resolved, and (iii) the notice bundle of D5.2 is included. | D2.3; D4; D5.2; the artifact's own inventory run with `scripts/p03_binary_inventory.py` and stored with its hashes. |
| **C. Replay bundles** (K05, ADR 0007) | The run's inputs, manifests, events, artifacts, and the dependency inventory with hashes. | **Permitted, by reference only:** the bundle records `casadi==3.8.0` and the wheel's audited hashes and does not embed the wheel. A bundle that embeds the wheel is mode B and is ruled by mode B. | "Report replay dependencies clearly" (blueprint §15): the bundle states that exact replay requires the same wheel, obtained by the replayer. |
| **D. Source only** — the project's own code with no backend dependency declared | The project's own bytes. | Trivially unconstrained by anything in this ADR; it is the project's own rights question (D6.1) and nothing else. | None from this ADR. |

Two rules cut across the modes:

- **D1.5 Use restriction on the default path.** The METIS 4.0 notice restricts *use*, not only redistribution: outside non-profit institutions and US government agencies it permits evaluation only. The project cannot know its users' status. Therefore **no default execution path may load an object in the METIS closure**. That closure, derived mechanically from the per-object `DT_NEEDED` lists in `casadi-inventory.json` (audit §2.6, which is the authoritative enumeration and is regenerated with the inventory), is: the direct namers `libcoinmumps`, `libipopt`, `libsipopt`, `libuno` and the `cbc` and `clp` executables; transitively `libbonmin`, `libCbc`, `libCbcSolver`, `libCgl`, `libClp`, `libClpSolver`, `libOsiCbc`, `libOsiClp`, `libsleqp`; and **seven CasADi plugins — `conic:cbc`, `conic:clp`, `linsol:mumps`, `nlpsol:bonmin`, `nlpsol:ipopt`, `nlpsol:sleqp`, `nlpsol:uno`** — every one of which loads successfully today, so this is a use rule and not a breakage report. A future session that wants to enable any plugin re-derives this list from the current inventory rather than trusting the names here. This holds in mode A too, where the bytes are the user's download: the restriction is on what the project *makes its software require*. D03's explicit SuperLU choice already satisfies this and is now load-bearing for D04 (D2.4).
- **D1.6 "Disabled" is not "cleared".** The twelve disabled objects (1 885 160 bytes) and the 215 424 720 dormant bytes are still *redistributed* in mode B. Blueprint §15 says so in terms, and this ADR does not read dormancy as permission. In mode A they are not redistributed by the project at all, which is the only reason mode A is clean.

### D2. The METIS 4.0 disposition

**D2.1 Scope, measured.** Exactly one distinct object carries METIS code: `libcoinmetis.so.2.0.0`, 306 208 bytes, SHA-256 `1166d99729c03357…`, shipped three times under its SONAME spellings (`libcoinmetis.so`, `libcoinmetis.so.2`, `libcoinmetis.so.2.0.0`), **918 624 bytes of the download**. The attribution to METIS 4.x is from the binary, not the filename: it defines `METIS_EstimateMemory`, `METIS_mCPartGraphKway` and `METIS_EdgeND` (removed in METIS 5) and neither `METIS_SetDefaultOptions` nor `METIS_Free` (introduced in METIS 5). No other shipped object exports a `METIS_` symbol. HiGHS vendors a *different* METIS under Apache-2.0 and is not affected.

**D2.2 The notice, declared.** `casadi/include/licenses/metis-external/metis-4.0/LICENSE` (889 bytes, SHA-256 `2ecd4c415834a03b…`): "The software may not be sold or redistributed without prior approval", with use limited to non-profit and US-government educational and research purposes and to evaluation elsewhere. The EPL-1.0 `metis-external/LICENSE` beside it covers the Coin-OR `ThirdParty-Metis` wrapper, not the METIS code, and does not relicense it.

**D2.3 Remedies, in the order they are to be tried.** Each is adequate on its own for the mode it names; none is required for mode A.

| Order | Remedy | Adequate for | Cost | Verified by |
| --- | --- | --- | --- | --- |
| R1 | **Ship no CasADi bytes.** Mode A for the package, mode C for replay. This is the default and the state of the repository today. | Modes A, C | None | `pyproject.toml` declares the pin and the repository contains no wheel bytes (a test that no `*.so`/`*.whl` from the CasADi tree is tracked is cheap and recommended, D5.5). |
| R2 | **Prune the artifact.** Before any mode-B artifact is published, delete `libcoinmetis.so`, `libcoinmetis.so.2` and `libcoinmetis.so.2.0.0` from the installed tree in that artifact. Consequence, to be stated in the artifact's notice: every object in the D1.5 closure — `libcoinmumps`, `libipopt`, `libsipopt`, `libuno`, the `cbc` and `clp` executables, their dependents, and the seven plugins `conic:cbc`, `conic:clp`, `linsol:mumps`, `nlpsol:bonmin`, `nlpsol:ipopt`, `nlpsol:sleqp`, `nlpsol:uno` — will fail to load; none is on a project path (D1.5, audit §2.6). | Mode B | Minutes; a scripted step in the image or installer build | Re-run `scripts/p03_binary_inventory.py` on the artifact: zero `METIS_` exporters; **all seven** plugins named in D1.5 reported as failing to load (a plugin in the closure that still loads means the prune missed a copy); the derived METIS closure empty; `_casadi.so` closure unchanged at 19 384 616 bytes. |
| R3 | **Obtain or build a CasADi 3.8.0 wheel without METIS 4** — against METIS 5.x (Apache-2.0) or with MUMPS's ordering configured away from METIS. | Mode B, when R2's loss of Ipopt/MUMPS is unacceptable for a *non-default* optional path | A build pipeline the project does not have; a new [A10] audit of the resulting wheel | Full inventory and reproduction of the new wheel as in `docs/p03-binary-audit.md`. |
| R4 | **Prior approval from the copyright holder** (Regents of the University of Minnesota) for redistribution in the project's artifacts. | Mode B with the unmodified wheel | Outward-facing correspondence — Frank's action, never an agent's (CLAUDE.md "Escalation to Frank") | The approval recorded in the repository and cited by the artifact's notice. |
| R5 | **Report upstream to CasADi** that the wheel carries METIS 4 under a no-redistribution notice. Courtesy; the project depends on nothing here. | — | A message — Frank's call | — |

**D2.4 Consequence for numerical policy.** The linear solver stays SciPy SuperLU with explicit options (D03, ADR 0004); K03 must not route the linear solve through a CasADi `Linsol`; M03 must not use CasADi's bundled `nlpsol:ipopt` (Q3 of ADR 0003) and, if it needs Ipopt, obtains it from a separately distributed package whose own [A10] audit is run first. Any future proposal to enable a CasADi plugin on a default path re-runs the reachability check against `libcoinmetis` before it is merged.

**D2.5 What this is not.** Not a numerical defect; not evidence against CasADi as a backend; not a reason to prefer a route that fails installability (ADR 0003 D1.3, R3). And not nothing: without R1–R4, mode B is closed.

### D3. The LGPL-3.0-or-later position

**D3.1 The facts.** CasADi declares `License: GNU Lesser General Public License v3 or later (LGPLv3+)` in its wheel metadata and ships its text at `casadi/LICENSE/LICENSE.txt`. The project's intended core licence is Apache-2.0 (blueprint §15; `pyproject.toml`), with the licence file deliberately withheld pending Frank's rights confirmation. The project's code uses CasADi through its Python API only: the interpreter loads `_casadi.so` and `libcasadi.so.3.7` at run time from a wheel the user installed; the project compiles nothing against CasADi headers and links nothing against its libraries at build time; a user can substitute any other build of CasADi 3.8.0 by replacing the installed package. This is the dynamic-loading case, and the "suitable shared library mechanism" of LGPL-3.0 §4(d)(1) is the mechanism the project relies on to leave the library replaceable.

**D3.2 The obligations this creates for the project**, as read from the licence text and stated for Frank to confirm (Q1):

1. **Prominent notice** that the software uses CasADi and that CasADi is covered by the LGPL-3.0-or-later, in the project's documentation and in every distributed artifact (modes A, B, C). Mode A carries this today as a statement in the README and in the package metadata's third-party notice (D5.1); mode B additionally conveys the LGPL-3.0 and GPL-3.0 texts alongside the bytes (D5.2).
2. **No terms that prevent modification or relinking of the library.** Apache-2.0 on the project's own code imposes none, and the project imposes no additional terms. The project's code is not required to be LGPL: the additional permissions of the LGPL exist precisely to let works under other licences use the library through a replaceable interface, and the project's Apache-2.0 core is therefore *not* changed by this dependency. This is the mainstream reading of Python packages depending on LGPL wheels; it is a reading, and it is recorded as such.
3. **Stay on the Python API.** If any package ever compiles C or C++ against CasADi headers or incorporates header material beyond the small-macro / template allowance of LGPL-3.0 §3, D3 must be re-examined in a new ADR before that code is merged.
4. **Blueprint §15's "no GPL-licensed components" line.** LGPL-3.0 is GPL-3.0 with additional permissions; it is a distinct licence whose purpose is to permit exactly this use. The reading adopted here is that the policy names the GPL and does not exclude the LGPL, and that the default install's *required* components — the `_casadi.so` closure — are LGPL-3.0-or-later (CasADi's own) and system libraries only. The other LGPL objects in the wheel (`qpOASES` LGPL-2.1, `alpaqa` and `sleqp` LGPL-3.0) and the CeCILL-C MUMPS are outside that closure and are mode-B notice items. **If Frank reads the policy line as excluding the LGPL, this ADR's mode A ruling and ADR 0003's selection both reverse** (ADR 0003 trigger T4); that is why Q1 is the first open question rather than a footnote.

**D3.3 Not asserted.** Nothing in D3 speaks to whether the project holds the rights to distribute its own contributions under Apache-2.0 (D6.1). D3 only says what CasADi's licence asks of a work that uses it in this way.

### D4. The unresolved components, individually

The audit found eight compiled objects, 5 723 463 bytes, with no notice in the package tree, no notice in `dist-info/`, and no embedded copyright or licence text. Unresolved is not permissive, and no row below may be cited as a clearance. **None of them is in the `_casadi.so` closure, so none is loaded on the selected route and none is redistributed in modes A and C.** They matter for mode B and are each an open item with a recommended default. Only the first five are hash-suffixed in the `auditwheel` style — host libraries copied into the wheel by the wheel builder without their notices.

| Object | Bytes | Loaded on the selected route? | Where it is reached from | Open item | Recommended default |
| --- | ---: | --- | --- | --- | --- |
| `libgfortran-8f1e9814.so.5.0.0` | 2 714 697 | No | `libcoinmumps`, `libipopt`, `libsipopt`, `libuno` (`DT_NEEDED`), i.e. inside the METIS closure | Toolchain runtime; terms unresolved from the artifact. | Resolve from the toolchain that built the wheel (the manylinux image's GCC) before any mode-B artifact; do not assert "runtime exception" from general knowledge. Under R2 the artifact still contains it, so it is a notice item even after pruning METIS. |
| `libquadmath-828275a7.so.0.0.0` | 272 193 | No | Same as above | Toolchain runtime; unresolved. | Same as `libgfortran`. |
| `libgomp-870cb1d0.so.1.0.0` | 253 289 | No | `libuno` (`DT_NEEDED`) | Toolchain runtime; unresolved. | Same as `libgfortran`. |
| `libmvec-2-583a17db.28.so` | 181 969 | No | Vendored glibc vector math | glibc component; unresolved from the artifact. | Resolve from the glibc version the manylinux image carries before mode B. |
| `libspral.a` | 2 232 218 | No — a static archive; not loadable at run time by anything shipped | Not in any `DT_NEEDED` chain | SPRAL; no notice shipped. | Obtain SPRAL's notice upstream before mode B, or prune the archive from mode-B artifacts (nothing on any path links against it). |
| `libmatlab_ipc.so` | 30 281 | No | No shipped dependent found | No notice, no embedded text. | Treat as CasADi-own code pending confirmation from upstream; prune from mode-B artifacts if not confirmed — nothing on a Python path uses it. |
| `libcplex_adaptor.so` | 21 624 | No (loads, then fails registration, emitting a diagnostic on import) | `conic:cplex` plugin | Adaptor stub; no notice. | Treat as CasADi-own; prune from mode-B artifacts together with the ten disabled plugin shims (D1.6) — they cannot run and they emit diagnostics. |
| `libgurobi_adaptor.so` | 17 192 | No (same) | `conic:gurobi` plugin | Adaptor stub; no notice. | Same as `libcplex_adaptor.so`. |

Also open, from the audit's detector limits, and needed before mode B only: six notices whose title the pattern set did not recognise (`bonmin-external`, `ghc-external`, three `openblas-external` netlib-BLAS notices, `proxqp-external/cmake-module`) — default: a human reads them and records the identifier in the inventory; and thirteen notice components that matched no object under the name rule and are statically linked into the `libcasadi_*` plugin objects — default: attribute them wholesale to the plugin objects in the mode-B notice bundle, which is what the audit's mapping already does.

For the rejected route, recorded once and not maintained: PyNumero's ASL library is built by the user and its terms are unresolved from the installed artifacts (`~/.pyomo` carries only `src/mcpp/LICENSE`); the Pyomo wheel itself is BSD-3-Clause with its notice shipped. No obligation follows, because the project does not depend on it.

### D5. Notice obligations the project takes on, and who owns them

1. **Now, at K01, mode A (Opus session, with the dependency pin):** a third-party notice statement in the README and in the package's documentation saying that the software uses CasADi 3.8.0, licensed under the GNU LGPL v3 or later, with a pointer to the licence text the wheel ships (`casadi/LICENSE/LICENSE.txt`) and to `docs/p03-binary-audit.md`. This is the D3.2(1) obligation and it is small.
2. **Before any mode-B artifact (T08, which owns D04 at release; gate V18):** a notice bundle assembled from the 81 files under `casadi/include/licenses/` (430 274 bytes; the audit lists all 40 components with their declared identifiers), plus the LGPL-3.0 and GPL-3.0 texts, plus the resolved terms for every D4 item still present in the artifact, plus a statement of what R2 removed and what therefore does not load. The bundle ships beside the bytes it describes.
3. **Pin discipline (K01, then K05):** `casadi==3.8.0` is the pin; the wheel's per-file SHA-256 record in `spikes/p03/results/casadi-inventory.json` is the audited baseline; K05's dependency inventory carries the pin and the `_casadi.so` closure hashes, and a mismatch fails exact replay.
4. **Refresh trigger (T08; blueprint §15 [A10]):** any change of the CasADi pin, any second-platform wheel (K05), and any mode-B artifact re-runs `scripts/p03_binary_inventory.py` and updates `docs/p03-binary-audit.md` *before* the change merges. A refreshed inventory that puts a restrictive, GPL, or unresolved object into the `_casadi.so` closure reopens ADR 0003 (its trigger T3).
5. **Hygiene test (recommended to the Opus session, not required by this ADR):** a test asserting that no file from a CasADi tree (`*.so*`, `*.whl`, `casadi/`) is tracked by git, so mode B cannot begin by accident.

### D6. Reproduction, and the limits of what the audit proves

1. **The project's own rights are not asserted here.** Every ruling in D1 is conditional on the project having the right to distribute its own contributions under its intended Apache-2.0 licence (blueprint §15). That confirmation, and the copyright line, are Frank's; this ADR neither supplies them nor treats their absence as a blocker for P03.
2. **What the reproduction establishes.** Installed again from PyPI with `--no-cache-dir` into fresh environments, the CasADi wheel reproduced 2 376 of 2 384 files byte-identically — all 232 compiled objects, all 81 notices, all 1 681 headers; the eight differences are install-generated `__pycache__/*.pyc`. The Pyomo wheel's compiled object and licence file reproduced. So the bytes this ADR rules on are the bytes PyPI served for `casadi==3.8.0` on Linux x86-64 on 2026-09-17.
3. **What it does not establish.** It is not a supply-chain guarantee (no signature or provenance chain was checked); it says nothing about any other platform's wheel; it does not make any D4 item more resolved; and PyNumero's ASL library was deliberately not re-derived, because rebuilding would overwrite the artifact the P02 manifest references by hash and would test compile reproducibility, which is not a P03 question.

## Alternatives considered

- **Treat the METIS finding as a blocker for CasADi.** Rejected: the project ships none of the bytes in its default mode, the object is outside the route's closure, and R2 is a three-file deletion for any vendored artifact. Over-reacting would select a route that fails installability (ADR 0003 D1.4).
- **Treat the METIS finding as irrelevant because the route never loads it.** Rejected: blueprint §15 says in terms that disabling a bundled plugin does not establish that distributing its bytes is acceptable, and the notice restricts use as well as redistribution (D1.5). Under-reacting would leave a container image or installer to be built later on a false premise.
- **Assert the terms of the toolchain runtimes from general knowledge** (GCC runtime exception, LGPL glibc). Rejected: the audit's rule is that a term is read from a shipped notice or recorded unresolved, and this ADR keeps that rule; the defaults in D4 say where to read them.
- **Assemble the notices from upstream.** Withdrawn already in the audit (§2.5): 81 notices are in the wheel; only D4's items need upstream reading.
- **Declare the project's code LGPL, or add the `LICENSE` file, to simplify D3.** Rejected: the first is not required by the reading in D3.2 and would change the blueprint's licence intent; the second is a rights assertion only Frank can make (§3 of the brief; D6.1).
- **Vendor a pruned wheel now so mode B is ready.** Rejected: no package through v0.2 requires mode B; building it now would create bytes to maintain and audit for no deliverable. The remedy order (D2.3) is recorded so that mode B can be opened when a package needs it.

## Consequences

- K01 declares `casadi==3.8.0` and adds the D5.1 notice statement; it vendors nothing.
- K03 / ADR 0004 keep the linear solve in SciPy SuperLU; no CasADi `Linsol` on a default path (D2.4).
- K05 builds replay bundles by reference (mode C), records the pin and closure hashes, and runs the inventory on the second platform's wheel.
- M03 obtains Ipopt, if it needs it, from a separately distributed package with its own audit, not from the CasADi wheel.
- T08 inherits D04 at release: the refresh (D5.4), the mode-B notice bundle (D5.2) if any mode-B artifact is planned, gate V18, and the resolution of the D4 items that artifact would contain.
- The requirements ledger: this ADR is D04's "distribution verdict" and, with the audit, discharges A10's minimum evidence for the selected binaries; the Opus session records the evidence pointer and the honest status (recommended in the P03 report; the session owns the manifest).

## Acceptance evidence

- **Measured inventory:** `docs/p03-binary-audit.md` §2–§4, regenerable by `.venv-casadi/bin/python scripts/p03_binary_inventory.py --out spikes/p03/results`; `spikes/p03/results/{casadi,pyomo}-inventory.json` with every hash cited here.
- **Reproduction:** `docs/p03-binary-audit.md` §5 and `spikes/p03/results/reproduction.json`. (The audit's §5 quotes `/tmp/repro-*` environment paths while the JSON records scratchpad paths; the result is the same and the discrepancy is cosmetic — reported, not corrected here.)
- **Reachability:** the `DT_NEEDED` chain in D1.5 and D4 was re-read from the installed objects with `readelf -d` on 2026-09-17 and matches audit §2.6: `libcoinmumps.so.3`, `libipopt.so.3`, `libsipopt.so.3` and `libuno.so` each name `libcoinmetis.so.2` directly; `libbonmin.so.4` reaches it through `libcoinmumps.so.3` and `libipopt.so.3`; `_casadi.so` and `libcasadi.so.3.7` name only each other and system libraries. When this note was written on 2026-09-17, `casadi-inventory.json` did not store per-object `DT_NEEDED` lists (only the plugin probes and the `_casadi.so` closure), so the chain was not reproducible from the JSON alone; recording it was recommended to the Opus session. *Resolved the same day:* the script now records every ELF's own `DT_NEEDED` list (225 objects), audit §2.6 derives the closure from the record, and the derived closure is longer than the prose chain above — direct namers also include the `cbc` and `clp` executables, the transitive set adds `libCbcSolver`, `libClpSolver`, `libOsiClp`, and **seven** plugins are in the closure where D1.5 and R2 originally named one. Both clauses were corrected from the derived list. The lesson that travels with this ADR: a dependency graph that lives only in prose hid six plugin names from an operational rule; the refresh of D5.4 must always re-derive the closure from the record.
- **Status:** `implemented` when this file exists on `wp/P03`; `tested` when the D5.5 hygiene test and K01's notice statement are in the gate; `reviewed` requires Frank's confirmation of Q1 and Q2 and is not set here.

## What this ADR does not establish

- **No rights assertion about the project's own contributions** is made here (D6.1); the `LICENSE` file, the copyright line and the Apache-2.0 adoption remain Frank's.
- It is **not a legal opinion**: D2 and D3 are an agent's procedural reading of notices read off shipped artifacts, flagged for human confirmation (Q1, Q2).
- It does **not** clear any D4 item; unresolved stays unresolved until read from the source the default names.
- It does **not** open mode B; it records what opening it would take.
- It establishes the wheel's contents on **one platform, one host, one date**; the second K05 platform's wheel is unaudited, and the reproduction is not a supply-chain guarantee.
- It says nothing about **data rights** beyond the blueprint's rule that unknown rights are not assumed redistributable: parameter records with source, rights metadata and distribution policy are K02's and M01's schemas to carry, and the v0.2 real-chemistry dossier (T08, V19) is where data rights are first decided in earnest. The title's "data rights" is discharged here only by restating that rule and the mode-C rule that a replay bundle omits restricted bytes and retains references.
- It does not change any requirement status, tolerance, test inventory or gate.

## Open questions with recommended defaults

| ID | Question | Label | Recommended default |
| --- | --- | --- | --- |
| Q1 | Does blueprint §15's "default install must not require GPL-licensed components" exclude the LGPL-3.0-or-later `_casadi.so` closure? | **needs Frank's ruling** (a value judgment about his own policy line; if he consults counsel, theirs) | No — the line names the GPL; the LGPL's additional permissions exist for this use; the project's core stays Apache-2.0 with the D3.2 notice obligation. If yes: ADR 0003 T4 fires and the outcome is "neither works" with the smallest blocker named there. |
| Q2 | **Closed 2026-09-22 by Frank Peters: yes, and no.** Is the METIS disposition (R1 default; R2 before any mode-B artifact; R3/R4 only if R2's loss of Ipopt/MUMPS matters for a non-default path) acceptable, and should R4 or R5 be pursued now? | needs Frank's preference; R4 and R5 are outward-facing actions only he takes | R1 now, R2 documented for T08, R4 and R5 not pursued until a package needs mode B with Ipopt. **Default confirmed in full; see the status note above.** |
| Q3 | Will any package before v0.2 ship a mode-B artifact (container image, installer)? | needs Frank's preference on scope | No; if one is scheduled, T08 opens mode B under D2.3 and D5.2 and resolves the D4 items it contains first. |
| Q4 | Should `requirements.lock` carry the CasADi wheel's hash (`pip --require-hashes`) so that mode A's "the audited bytes are the installed bytes" is enforced rather than assumed? | needs a tooling call — Opus at K01/K05 | Yes, for the x86-64 wheel now and for each K05 platform's wheel once audited; the hash is the wheel file's, which the inventory does not yet record and should. |

**Q2 answered by Frank Peters, 2026-09-22: R1 stands; R4 and R5 are not pursued.**
The recommended default is confirmed in full — R1 now, R2 documented for T08, and neither the
approach to the Regents of the University of Minnesota (R4) nor the courtesy report upstream to
CasADi (R5) is to be made. Frank's stated criterion was "no problems, but also no hassle", and
the default is what satisfies both: **the project redistributes none of the bytes**, so the
notice on `libcoinmetis.so*` has nothing to bind — mode A ships source plus a pinned PyPI
dependency, and the user's own resolver fetches the wheel from its publisher. D1.5 already
records that no object in the METIS closure is on a project path, and ADR 0004 D1 keeps the
linear solve in SciPy SuperLU, so nothing we run reaches it either.

**No file changes as a result, and nothing is cleared that was not already clear.** This records
an answer; it does not alter a decision, and it is not a legal opinion — D2 and D3 remain a
procedural reading of notices read off shipped artifacts. In particular Q2 being closed does
**not** license a mode-B artifact: the first package that proposes a container image or an
installer applies R2 (delete `libcoinmetis.so`, `libcoinmetis.so.2`, `libcoinmetis.so.2.0.0`,
and state the seven plugins that consequently fail to load), resolves the D4 unresolved-notice
items it would contain, and re-reads this question before publishing. Q2 is closed for mode A
and reopens on its own terms the day mode B is scheduled. **Q3 is unaffected and still open.**

**Q1 answered by Frank Peters, 2026-09-17: the LGPL is allowed.** Blueprint §15's "the default
install must not require GPL-licensed components" names the GPL and does **not** exclude the
LGPL-3.0-or-later `_casadi.so` closure. The recommended default therefore stands: D3's reading is
confirmed, mode A is permitted as ruled in D1, the project's core stays Apache-2.0, and the
D3.2 notice obligation K01 carries is unchanged. **No file changes as a result** — this records an
answer, it does not alter a decision. ADR 0003 **trigger T4 can no longer fire on the LGPL ground**;
its METIS clause is untouched and depends on Q2. Q1 is closed.

This is an interpretation of §15, not an amendment to it: the blueprint text is unchanged and its
recorded hash still matches. The conditions under which the reading holds are D3.2's, and D3.2(3)
still binds — if any package compiles against CasADi headers or goes beyond the Python API, D3 is
re-examined in a new ADR before that code merges. Q1 being closed does not relax that.

## Changing this ADR

D1, D2.4 and D5.4 bind every package that declares, vendors or bundles the backend. Opening mode B, enabling any CasADi plugin on a default path, changing the pin without a refreshed audit, embedding the wheel in a replay bundle, or adopting a different reading of D3 requires a new Fable-authored ADR stating reason, affected requirements, migration impact and acceptance evidence, with a decision-register entry. A ruling by Frank on Q1 or Q2 is recorded in this ADR's status line and in the register the way ADR 0008 Q1 was recorded, without reopening the rest.

## Amendment 1 (2026-10-01) — the GCC runtime library in numpy and scipy, and LGPL-2.1

**Status:** Accepted on Frank's answers of 2026-10-01. Register R-135.

**Finding (T08.A30, `docs/t08-a30/t08-a30-x86_64.json`).** The default install's required closure contains
`libgfortran` (`numpy.libs/libgfortran-040039e1-0352e75f.so.5.0.0`, `scipy.libs/libgfortran-040039e1-0352e75f.so.5.0.0`,
`scipy.libs/libgfortran-040039e1.so.5.0.0`), declared in numpy's and scipy's `dist-info/LICENSE.txt` as
**GPL-3.0-with-GCC-exception**; numpy's `_multiarray_umath` → `libscipy_openblas64_` → `libgfortran`, and the
project loads two of the copies on every solve. The same closure contains `libquadmath`, LGPL-2.1-or-later.

**D7 (new). Frank's reading of blueprint §15, 2026-10-01.**
1. **The GCC Runtime Library Exception is outside §15's "no GPL-licensed components".** The exception exists so that
   programs using the compiler's runtime library are not covered by the GPL; the project neither modifies nor
   redistributes these objects. In mode A the user's `pip` installs numpy and scipy from PyPI and the project ships
   none of their bytes. The objects above are dispositioned by this amendment ("ADR 0006 Amendment 1").
2. **Q1 ("the LGPL is allowed") covers LGPL-2.1-or-later as well as LGPL-3.0**, so `libquadmath` is in the allowed
   class, like CasADi's LGPL objects.

**What this does not change.** Modes B and C (any artifact that contains numpy or scipy bytes) carry these objects'
notices, as D5 requires for CasADi's; a new GPL-family object without such an exception, or any change of these
objects' licences at a pin change, is a new finding (D5.4). Not a legal opinion; a procedural reading by the
maintainer.

## Amendment 2 (2026-10-01) — D4 on the aarch64 wheel

**Status:** design-lane amendment (T08 release spec Amendment R3 7); register R-142. Adds D4 rows; changes no disposition, mode, default or requirement.

**Finding (T08.A30 aarch64, `docs/t08-a30/t08-a30-aarch64.json`; lock `ead4edf1…`; verdict PASS).** CasADi 3.8.0's aarch64 wheel carries two compiled objects with no notice in the package tree or `dist-info/` and no embedded licence text, absent from the x86-64 wheel under these names. Neither is loaded by the project nor in a required closure.

| Object (aarch64 wheel) | Bytes | SHA-256 | Loaded on the selected route? | Open item | Recommended default |
| --- | ---: | --- | --- | --- | --- |
| `libgfortran-8de1544a.so.5.0.0` | 5 413 232 | `f84fe298f615936bd25cf8a41130eaec46ff05ca62f9e2b9a9b8080a0d87e43a` | No | Toolchain runtime, `auditwheel`-style suffix; terms unresolved from the artifact. | As D4's `libgfortran-8f1e9814.so.5.0.0`: resolve from the toolchain that built the aarch64 wheel before any mode-B artifact containing it. Amendment 1's reading concerns numpy's and scipy's copies, whose licence their `LICENSE.txt` declares; it does not transfer to a copy that declares none. |
| `libgomp-7eb2fb8b.so.1.0.0` | 1 194 968 | `5e688427525a6c3fee9077533941f107b2d61f6e5892439144cfb597e354c681` | No | Toolchain runtime; unresolved. | As D4's `libgomp-870cb1d0.so.1.0.0`. |

**The rest of D4 on aarch64.** `libcplex_adaptor.so`, `libgurobi_adaptor.so` and `libmatlab_ipc.so` are present (other bytes; their D4 defaults apply unchanged); `libquadmath-828275a7.so.0.0.0`, `libmvec-2-583a17db.28.so` and `libspral.a` are absent. So the aarch64 wheel's D4 items are five: the two above and the three adaptor/IPC objects. D2's METIS carrier is present (`casadi/libcoinmetis.so*`) and unreachable from every project path; D4's statement that no D4 object is in the `_casadi.so` closure holds on aarch64.

**Amendment 1 on aarch64.** numpy's and scipy's aarch64 `libgfortran` copies — `numpy.libs/libgfortran-daac5196-038a5e3c.so.5.0.0`, `scipy.libs/libgfortran-daac5196-038a5e3c.so.5.0.0`, `scipy.libs/libgfortran-daac5196.so.5.0.0` — declare the same licence (GPL-3.0-with-GCC-exception, their `dist-info/LICENSE.txt`) and are dispositioned by Amendment 1's D7.1, which ruled on that licence class; the aarch64 numpy and scipy carry no `libquadmath`.

**Effect.** Modes A and C: none. Mode B on aarch64: these five D4 items, D5.2's notice bundle, and D2.3's METIS remedy. The [A10] inventory attributes the two new objects to "ADR 0006 Amendment 2". This ADR's "does not establish" bullet on "the second K05 platform's wheel is unaudited" is superseded for the object-level inventory only (T08.A30 aarch64).

**Does not establish.** Any licence term of the two objects (unresolved stays unresolved); that the aarch64 wheel's notice set equals the x86-64 one beyond T08.A30's per-object attribution; a supply-chain guarantee. Not a legal opinion.
