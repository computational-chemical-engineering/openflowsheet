# Reference environments for T06 (DWSIM, IDAES)

**Package:** T06, reference acquisition (plan §4.3 row T06 "Start reference acquisition after P03",
§6.4 "Acquire DWSIM/IDAES examples early"). **Brief:** `docs/briefs/T06-reference-acquisition.md`.
**Requirement:** D19 (independent references: matched-model inputs, independence disclosure).
**Lane:** build. **Recorded:** 2026-09-24, branch `wp/T06-refs`.

This document records **environments and representability**: what can be built and run here, pinned
to the byte, and which plan §6.4 fixtures each tool can express with which equations. It contains
**no comparison** with this project, no tolerance and no verdict — those are T06's design-lane work
(`specifier`, `verdict`). Every number quoted from a tool below is that tool's raw output, recorded
as an environment check or as evidence that a model was built and solved.

## 1. Status

| Tool | Status | Headless route | Own example (smoke) | Plan §6.4 fixtures built on SYN-001 constants |
| --- | --- | --- | --- | --- |
| IDAES 2.13.0 | **works** | CPython + Pyomo + bundled Ipopt 3.13.2 | PASS | 8 of 8 solved (§5.1) |
| DWSIM 9.0.5 | **works** | CPython + pythonnet 3.1.0 on .NET 8.0.31 (CoreCLR), `Automation3` | PASS | 8 of 8 calculated (§5.2) |

Nothing needed an account, a licence acceptance, or a paid component. Nothing was installed
system-wide, and neither tool was modified.

## 2. Host

Debian 13, x86-64, Linux 6.12.86, glibc 2.41, Python 3.13.5 (the same host as
`docs/backend-environments.md`). No `sudo`. No display was used for any run (`DISPLAY` and
`WAYLAND_DISPLAY` unset).

## 3. Reproduction

```bash
scripts/build-reference-envs.sh            # both; or: idaes | dwsim; optional second arg = log file
.venv-idaes/bin/python spikes/references/idaes_smoke.py
.venv-dwsim/bin/python spikes/references/dwsim_smoke.py
.venv-idaes/bin/python spikes/references/idaes_representability.py --json out.json
.venv-dwsim/bin/python spikes/references/dwsim_representability.py --json out.json
```

The script rebuilds each environment from scratch, verifies every downloaded artifact against the
hash pinned in the script, and ends with a fingerprint. It is not part of `scripts/check.sh`, and
neither are the scripts under `spikes/references/`: the gate does not depend on external tools.

| Produced | Contents | Size |
| --- | --- | --- |
| `.venv-idaes/` | idaes-pse 2.13.0 closure from `spikes/references/idaes-requirements.lock` (28 packages, `--require-hashes`) | 693 MB with extensions |
| `.venv-idaes/idaes-data/bin/` | IDAES binary extensions 3.4.2 via `idaes get-extensions --release 3.4.2 --distro ubuntu2204`; `IDAES_DATA` points here (the scripts default it), so nothing is written to `~/.idaes` | (included above) |
| `.venv-dwsim/` | pythonnet 3.1.0 closure from `spikes/references/dwsim-requirements.lock` (4 packages, `--require-hashes`) | 866 MB with the two below |
| `.venv-dwsim/dotnet/` | .NET runtime 8.0.31 (Microsoft.NETCore.App only), unpacked | |
| `.venv-dwsim/dwsim/` | `usr/local/lib/dwsim` from the DWSIM .deb, unpacked (`dpkg-deb -x`), **not installed** | |
| `.reference-downloads/` | cache of the .deb and the .NET tarball, and the build logs (git-ignored) | 241 MB |

The lock files were compiled with `uv pip compile --generate-hashes --python-version 3.13
--python-platform x86_64-manylinux_2_28` from the one-line `.in` files beside them. pip is the one
bundled in the host Python's venv (25.1.1); no pip upgrade is downloaded.

**Build time and determinism, measured.** Run 1 (empty download cache, warm pip wheel cache): 41 s
(IDAES 32 s, DWSIM 8 s). Run 2 (cached downloads, re-verified): 33 s. The fingerprints of the two
runs are identical:

```
[.venv-idaes] pip freeze sha256: dfeec96faebeb6bedab5eb1c069df7344282d0002fe92fb191f2c55c73af82c6
[.venv-idaes] idaes-data/bin tree: 370a694825da3be3d7b0e68742bf2e704918260b05fa0f6c54d4d61458d1144d
[.venv-idaes] ipopt sha256: 8f8711b709b5f265ff7cb8b352c037bb999d88628384be8390f26530f08de94e
[.venv-dwsim] pip freeze sha256: d0a428cc7c06a7605bcfdaeb1e62ac3e9630b02c04224dea8e5928bc2e02635a
[.venv-dwsim] dotnet tree: f03ce7f0101336009c4bd090fd3006d187ba419b03bf86c84d0b56367b6e1058
[.venv-dwsim] dwsim tree: b8de32e026197858b552b7b310c621a9e919952288900a66c73ac2a0353ea87e
[.venv-dwsim] DWSIM.Automation.dll sha256: ce32c2a422e20c553769a355fdf6fc0cf94eac85ae6ba37d4df045cd2208aa31
```

Both representability probes, rerun on the rebuilt environments, wrote JSON byte-identical to the
first run's (`spikes/references/results/`). A cold pip wheel cache adds the download of the IDAES
closure (~110 MB of wheels); that was not timed.

## 4. Pinned artifacts and licences

Licences are as **stated by the source**, quoted where it matters; "free to download" is not an
open-source licence (blueprint D19). Bytes are not committed; hashes and URLs are.

### 4.1 Downloaded artifacts

| Artifact | URL | Hash (verified by the script) | Hash cross-check | Licence as stated |
| --- | --- | --- | --- | --- |
| DWSIM 9.0.5 Linux .deb (221 039 948 B) | `https://github.com/DanWBR/dwsim/releases/download/v9.0.5/dwsim_9.0.5-amd64.deb` | sha256 `52c041b1d659ea26e22750e8b7045c7bc68d3d95f6384abe28d07d967eafa20c` | equals the digest GitHub publishes for the release asset | GPL-3.0 (repository licence; source headers "GPL version 3 or (at your option) any later version"). The .deb's control file says "GNU Lesser General Public License (GPL) Version 3" — self-contradictory; its only top-level `license.txt` is the DockPanel Suite MIT text. See §4.3 |
| .NET runtime 8.0.31 linux-x64 | `https://builds.dotnet.microsoft.com/dotnet/Runtime/8.0.31/dotnet-runtime-8.0.31-linux-x64.tar.gz` | sha512 `f336bdec…2652fb` (full value in the script) | equals `releases.json` for 8.0 from Microsoft's release metadata | MIT (`LICENSE.txt`, ".NET Foundation and Contributors"), plus `ThirdPartyNotices.txt` |
| idaes-lib-ubuntu2204-x86_64.tar.gz (3.4.2) | `https://github.com/IDAES/idaes-ext/releases/download/3.4.2/…` | sha256 `341470b4b0b9d67758cfde6f3246ed3a3d08000e2306908186435262d5751184` | equals IDAES's `sha256sum_3.4.2.txt` | IDAES BSD 3-clause |
| idaes-solvers-ubuntu2204-x86_64.tar.gz (3.4.2) | same release | sha256 `f370fa258cc457cd84fd9fe4298bde55dfc03374b607e68aa4d38f24ad9730e5` | equals IDAES's `sha256sum_3.4.2.txt` | mixed — see §4.2 |

`idaes get-extensions` checks the tarballs against a checksum file it fetches from the **`main`
branch** of `IDAES/idaes-ext` (`raw.githubusercontent.com/.../main/releases/sha256sum_3.4.2.txt`),
which is mutable. The build script therefore re-checks both tarballs against the hashes pinned in the
script itself.

### 4.2 Solver binaries in the IDAES extensions — not all open source

The extension licence file (`idaes-data/bin/license.txt`) lists, for `idaes-solvers`: Ipopt, Clp,
Cbc, Cgl (EPL-2.0), Couenne, Bonmin, ADOL-C (EPL-1.0), MUMPS (CeCILL-C), METIS ≥ 5 (Apache-2.0), the
AMPL Solver Library (permissive notice), GCC runtime (GPL + runtime exception), and two entries that
are **not** open-source licences:

- **HSL**: only an acknowledgement requirement is stated ("All technical papers, sales and publicity
  material resulting from use of the HSL codes within IPOPT must contain the following
  acknowledgement…"); no licence text. The bundled Ipopt links MA27, MA57 and MA97 (each solved the
  smoke problem as `linear_solver`), and **its default linear solver is MA27** ("This is Ipopt
  version 3.13.2, running with linear solver ma27").
- **METIS 4**: "Included with permission".

This matters for D19 disclosure, not for this project's distribution: the IDAES environment is a
reference tool, never shipped. Any IDAES reference result computed with the default solver options
was computed with HSL MA27; `linear_solver=mumps` also works (§6.1).

### 4.3 Python closures and DWSIM's bundled components

| Environment | Packages and declared licences |
| --- | --- |
| `.venv-idaes` | idaes-pse 2.13.0 (BSD), pyomo 6.10.1 (BSD-3-Clause), numpy 2.5.3 (BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0), scipy 1.18.1 (BSD), pandas 3.0.6 (BSD), matplotlib 3.11.2 (PSF-based), sympy 1.14.0 (BSD), networkx 3.7 (BSD-3-Clause), pint 0.26.1 (BSD), pydantic 2.13.5 / pydantic-core 2.46.5 (MIT), pillow 12.3.0 (MIT-CMU), fonttools 4.66.0 (MIT), click 8.5.0 (BSD-3-Clause), packaging 26.3 (Apache-2.0 OR BSD-2-Clause), typing-extensions 4.16.0 (PSF-2.0), and small MIT/BSD dependencies — full list with hashes in the lock file |
| `.venv-dwsim` | pythonnet 3.1.0 (MIT), clr-loader 0.3.1 (MIT, per its `LICENSE`; no metadata field), cffi 2.1.1 (MIT-0), pycparser 3.0 (BSD-3-Clause) |

DWSIM's own licence index (`dwsim/data/licenses/licencas.txt`) lists its third-party components,
among them the **ChemSep database (Perl Artistic License 2.0)**, IPOPT (EPL), DotNumerics (GPLv3),
lp_solve, Flee, CUDAfy, FileHelpers, SyntaxBox, ZedGraph (LGPL), SharpZipLib (GPLv2), IKVM, Lua,
Nini, DockPanel (MIT). The package also ships `DWSIM.ProFeatures`, `DWSIM.Simulate365` (cloud
integration), a ThermoC bridge (`ThermoCS/`, external executables) and Reaktoro/Cantera interop
assemblies. **None of these is used** by the probes: the SYN-001 fixtures use only user-entered
compounds, the Raoult's Law package and core unit operations, so no DWSIM compound database, no
account-bound feature and no external thermodynamic program enters any result here.

## 5. Headless routes and representability

### 5.0 The SYN-001 component set in each tool

SYN-001 (`docs/derivations/SYN-001.md` §1–3) is synthetic: ideal VLE with
`K_i = (P_r/P) exp[(L_i/R)(1/T_b,i − 1/T) + v_i (P − P_r)/(RT)]`, `h_i^L = c_p (T − T_r) + v_i (P − P_r)`,
`h_i^V = c_p (T − T_r) + L_i`, T_r = 300 K, P_r = 1e5 Pa. **Neither tool shares a property package
or correlation with this project**; both accept the SYN-001 constants as user input, with the
equation differences listed here. The column "same at P = P_r" matters because every stream of the
SYN-001 reference flowsheet is at P_r.

| Property | This project (SYN-001) | IDAES 2.13.0 (modular framework, Ideal EoS) | DWSIM 9.0.5 (Raoult's Law, user compound) |
| --- | --- | --- | --- |
| How entered | — | `GenericParameterBlock`; user-written `pressure_sat_comp` class; `Constant` c_p, h_form, liquid density (`idaes_representability.py`) | `ConstantProperties` with `OriginalDB = "User"`; vapor pressure eq. 10, c_p eq. 1, ΔH_vap eq. 1, liquid density eq. 1 (`dwsim_representability.py`) |
| Psat_i(T) | `P_r exp[(L_i/R)(1/T_b,i − 1/T)]` | identical (user method) | identical (eq. 10, `exp(A − B/(T+C))`, A = ln P_r + L_i/(R T_b,i), B = L_i/R, C = 0); readback `Psat(T_b,i)` = 1e5 Pa to within 2e-15 relative |
| K_i | `(Psat_i/P) · exp[v_i (P − P_r)/(RT)]` | `Psat_i/P` — **no Poynting factor** (`eos/ideal.py`, liquid fugacity `x Psat`) | `Psat_i/P` — **no Poynting factor** (`Ideal.vb` `DW_CalcFugCoeff`; the PP's Poynting flag is not read by Raoult's Law) |
| same at P = P_r? | | yes | yes |
| h^V_i | `c_p (T − T_r) + L_i` | identical (`c_p (T − T_ref) + h_form,ig`, h_form,ig = L_i, T_ref = 300 K) | `c_p (T − 298.15 K)`, no formation term in stream enthalpies |
| h^L_i | `c_p (T − T_r) + v_i (P − P_r)` | identical (`c_p (T − T_ref) + h_form,liq + (P − P_ref)/ρ_L`, h_form,liq = 0, P_ref = P_r) | `c_p (T − 298.15 K) − ΔH_vap,i + P v_i`, ΔH_vap,i = L_i (constant) |
| h^V − h^L | `L_i − v_i (P − P_r)` | identical | `L_i − P v_i`: **smaller by P_r v_i = 10 J/mol** at every P. The datum differences (298.15 K, the −L_i) are per-component constants and cancel in every non-reacting balance; this one does not cancel when a phase changes |
| Liquid volume | `v_i`, incompressible | `1/ρ_L`, constant | constant **only with** `LiquidDensity_CorrectExpDataForPressure = False`; DWSIM's default multiplies it by a compressed-liquid factor built from T_c, P_c, ω and Psat (`PropertyPackage.vb`, `AUX_LIQDENS`). The probe switches it off |
| Fields SYN-001 does not define | — | `temperature_crit`, `pressure_crit` (required by the state-block initializer); 1000 K, 1e7 Pa | T_c, P_c, ω, normal boiling point; 1000 K, 1e7 Pa, 0, T_b,i. T_c must exceed 440 K (ΔH_vap is 0 at T ≥ T_c) |
| Influence of those placeholders (measured) | — | changing to 2500 K / 5e7 Pa moved results by ≤ 6e-16 relative (flash, recycle, mixer, heater; the critical-point rows join the NLP) | changing to 2500 K / 5e7 Pa / ω = 0.3: all nine fixture records **bit-identical** (with the density correction off; with it on, pump power moved 3e-5 relative and the valve outlet 1e-5 K) |

The ΔH_vap offset could be removed in DWSIM by entering ΔH_vap,i = L_i + P_r v_i, and the Poynting
factor could be added in IDAES only by a user-written EoS or phase-equilibrium form. **Neither was
done**: whether to map, and whether SYN-001 comparisons are restricted to P = P_r, are design-lane
decisions (§7).

### 5.1 IDAES route and results

pip + `idaes get-extensions`. IDAES 3.4.2 extensions have no Debian 13 build (`Unsupported
platform: debian13-x86_64`); the script passes `--distro ubuntu2204`, the build IDAES's own alias
table assigns to ubuntu2404 and el9. It runs here; `ipopt` links the host's `libgfortran.so.5`,
`libblas.so.3` and `libopenblas.so.0` (installed Debian packages, not provided by the script).

**Smoke** (`idaes_smoke.py`): IDAES's documented Flash example, benzene–toluene, BTX package in ideal
mode, solved by the bundled Ipopt 3.13.2. DOF 0, `optimal`, vapor 0.39612 mol/s — environment check
only. MUMPS, MA27, MA57 and MA97 each solved it as `linear_solver`.

**Representability probe** (`idaes_representability.py`, output
`spikes/references/results/idaes-representability.json`), SYN-001 constants, Pyomo's
`SolverFactory("ipopt")` with Ipopt defaults (tol 1e-8, MA27):

| Fixture | IDAES model and specification | DOF | Termination |
| --- | --- | --- | --- |
| mixer | `Mixer`, `MomentumMixingType.none` + outlet P fixed, energy `extensive` (adiabatic) | 0 | optimal |
| splitter | `Separator`, `SplittingType.totalFlow`, `equal_temperature`, r = 0.5 | 0 | optimal |
| heater | `Heater`, outlet T = 350 K, duty free, no ΔP | 0 | optimal |
| ideal flash | `Flash`, outlet T = 360 K, ΔP = 0, duty free | 0 | optimal |
| valve | `PressureChanger`, `adiabatic`, `compressor=False`, P_out = 1e5 Pa from 2e5 Pa | 0 | optimal |
| liquid pump | `PressureChanger`, `pump`: W_fluid = ΔP · V̇_out, W_mech = W_fluid/η, η = 0.75 | 0 | optimal |
| conversion reactor | `StoichiometricReactor` + `GenericReactionParameterBlock` (synthetic A → B, liquid), extent = 0.6 · F_A added as a constraint, isothermal | 0 | optimal |
| recycle | SYN-001 loop (mixer → heater → flash → splitter → mixer, `Arc`s), sequential initialization on a torn S6 guess, then one simultaneous (EO) solve | 0 | optimal; overall component balance closes to 2.2e-16 mol/s |

### 5.2 DWSIM route and results

**What was tried.** DWSIM 9.x on Linux targets .NET 8 (`DWSIM.UI.Desktop.runtimeconfig.json`:
`Microsoft.NETCore.App` 8.0.11, assemblies built for .NET Framework 4.6.2 and run on CoreCLR). Its
.deb depends on `dotnet-runtime-8.0` and `coinor-libipopt1v5` and its postinst runs
`chmod -R 0777 /usr/local/lib/dwsim`; installing it needs root, which is not available and not
wanted. Instead the .deb is unpacked and a pinned .NET 8 runtime tarball is unpacked beside it.
pythonnet 3.1.0's CoreCLR loader, started with DWSIM's own runtimeconfig, loads
`DWSIM.Automation.dll`; `Automation3` (DWSIM's GUI-less automation class) creates, loads, solves
and reads flowsheets **with no display**. This worked on the first attempt. Not tried, because not
needed: Mono (DWSIM 9 no longer targets it), a DWSIM CLI (the package's only launcher,
`usr/local/bin/dwsim`, starts the GUI), and the system `coinor-libipopt1v5` (DWSIM ships
`libIpopt39.so`; none of the fixtures calls an optimizer).

**Smoke** (`dwsim_smoke.py`): DWSIM's shipped sample `samples/Cavett's Problem.dwxmz` (20 material
streams, 4 vessels, 2 mixers, 3 valves, 3 compressors, 3 recycle blocks), loaded and solved headless:
every object calculated, no solver errors; .NET start 2.2 s, load 1.7 s, solve 0.7 s — environment
check only.

**Representability probe** (`dwsim_representability.py`, output
`spikes/references/results/dwsim-representability.json`, and `…-alt.json` with the alternative
placeholders). Raoult's Law package, default flash `UniversalFlash` with PT/PH flash loop tolerances
1e-4 (`flash_settings` in the JSON):

| Fixture | DWSIM unit and specification | Result |
| --- | --- | --- |
| mixer | `Mixer` (NodeIn); outlet P = `Minimum` of inlets (default); PH flash on the mixed enthalpy | calculated |
| splitter | `Splitter` (NodeOut), `SplitRatios`, ratio 0.5 (splits mass flow; equal to the molar split at equal composition) | calculated |
| heater | `Heater`, `CalcMode = OutletTemperature` 350 K, ΔP = 0, energy stream | calculated |
| ideal flash | `Vessel` with `OverrideT` 360 K (isothermal TP flash at the inlet pressure; duty from the energy stream) | calculated |
| valve | `Valve`, `CalcMode = OutletPressure` (isenthalpic PH flash) | calculated |
| liquid pump | `Pump`, `CalcMode = OutletPressure`, efficiency 75 %: W = ΔP/ρ_in/η · ṁ, H_out = H_in + W/ṁ, PH flash | calculated |
| conversion reactor | `RCT_Conversion`, conversion reaction A → B (liquid, 60 % of A), isothermic; heat of reaction from ideal-gas formation enthalpies at 298.15 K (entered as L_i so that the liquid datum matches SYN-001's, §4 of the script) | calculated; isothermal duty −9.1e-8 kW |
| recycle | SYN-001 loop, torn on S6 by a DWSIM `Recycle` block, sequential modular | calculated — see below |

**The DWSIM recycle defaults do not close this loop.** Default `Recycle` tolerances are absolute:
mass flow 0.01 kg/s (≈ 6 % of this 0.16 kg/s recycle), temperature 0.1 K, pressure 0.1 Pa; no
acceleration; 50 iterations. With them DWSIM stops after **1 iteration**, flags the recycle
converged, and the overall component balance (fresh feed = vapor product + purge) is off by
**0.0306 mol/s**. With tolerances tightened to 1e-10 kg/s, 1e-6 K, 1e-3 Pa (a probe setting, not a
registered choice) it takes **26 iterations** and the balance is off by **1.7e-5 mol/s**. The
convergence test compares total mass flow, T and P only — not composition (`Recycle.vb` lines
444–446 at v9.0.5). Recycle and flash tolerances are therefore part of any DWSIM reference's
registered inputs.

### 5.3 Representability table (plan §6.4)

"Same equations" means the tool's model equations, after the SYN-001 mapping of §5.0, are the ones
this project states for that unit. Mixer, splitter, heater, flash and recycle are specified by
SYN-001 §4; **valve, liquid pump and conversion reactor have no contract in this project yet** (T05),
so for those the tool's equations are recorded and sameness cannot be judged.

| Fixture | IDAES 2.13.0 | DWSIM 9.0.5 |
| --- | --- | --- |
| mixer | **expressible with the same equations** (component + adiabatic enthalpy balance; SYN-001 enthalpy exactly). Pressure closure written as an outlet spec (`none`); `equality` gives P_out = P_in per inlet (redundant for fixed equal inlets and in a closed loop), `minimize` a smoothed min. Outlet phase from SmoothVLE, not a subcooled-liquid domain with a typed failure (SYN-001 §4) | **expressible with the same equations** for an all-liquid outlet (per-component enthalpy offsets cancel); outlet P = min of inlets; outlet state by PH flash. A two-phase outlet would carry the P_r v_i latent offset |
| splitter | **same equations** | **same equations** (mass-based split = molar split at equal composition) |
| heater | **same equations at P = P_r**; at P ≠ P_r the outlet phase split lacks the Poynting factor | **different equations**: duty carries the latent offset P_r v_i per mole vaporized (§5.0); K without Poynting (same at P_r) |
| ideal flash | **same equations at P = P_r** (two-phase solution of SmoothVLE is `y P = x Psat`); K without Poynting at P ≠ P_r | **different equations**: K same at P = P_r, duty carries the P_r v_i latent offset; iterative flash converged to 1e-4 loop tolerances |
| valve | **expressible**; isenthalpic ΔP with specified P_out (IDAES's separate `Valve` adds a flow-coefficient relation). Our contract: T05, not yet specified | **expressible**; isenthalpic PH flash with specified P_out (or ΔP, or Kv modes). All-liquid: the enthalpy offsets cancel, same form as IDAES. Our contract: T05 |
| liquid pump | **expressible**; W_fluid = ΔP · V̇_out, W_mech = W_fluid/η into the energy balance. Our contract: T05 | **expressible**; W = ΔP/ρ_in/η · ṁ into the energy balance (incompressible liquid: equal to IDAES's form). Our contract: T05 |
| conversion reactor | **expressible**; `StoichiometricReactor` + reaction package, conversion as a user constraint on the extent; heat of reaction from the component enthalpies (formation terms per phase are user data). Our contract: T05; SYN-001 has no reaction | **expressible**; `RCT_Conversion`, conversion per reaction; heat of reaction from ideal-gas formation enthalpies at 298.15 K, fixed when the reaction is created. Our contract: T05 |
| recycle | **expressible with the same equations**, solved simultaneously (EO); SYN-001 loop DOF 0, balance closes to 2.2e-16 mol/s | **expressible**, sequential modular with a tear; same unit equations as the rows above (so the heater/flash latent offset applies), convergence set by the Recycle tolerances, whose defaults leave a 0.03 mol/s balance error here (§5.2) |
| synthetic component set with user constants | **yes** (user Psat method + `Constant` methods); needs inert T_c, P_c | **yes** (User compound, standard correlation numbers); needs T_c > 440 K, P_c, ω, NBP; density pressure correction must be switched off |

No cell is `not expressible` or `BLOCKED (access)`.

## 6. Platform notes and tool quirks found (recorded, not worked around)

1. **IDAES extensions**: no Debian 13 build; the ubuntu2204 build is used (§5.1). The checksum file
   `get-extensions` trusts is fetched from a mutable branch; the script pins its own hashes (§4.1).
2. **IDAES data directory**: importing `idaes` without `IDAES_DATA` creates `~/.idaes/{bin,testing}`.
   The spike scripts default `IDAES_DATA` to `.venv-idaes/idaes-data`. (One exploratory command
   created an empty `~/.idaes` on this host; it was removed.)
3. **IDAES initializer needs critical constants** that no Ideal-EoS equation reads (§5.0).
4. **DWSIM `AUX_HVAPi`** (the routine the property package uses) reads a "User" compound's
   vaporization-enthalpy equation only when `LiquidHeatCapacityEquation` is not `"0"` — it tests the
   wrong field; the probe sets the liquid-c_p equation (unused by the Ideal enthalpy mode) so that
   ΔH_vap is taken from the entered equation. Readback: 250.0 / 300.0 / 350.0 kJ/kg.
5. **DWSIM `ConstantProperties.GetEnthalpyOfVaporization`** takes a different code path (Watson
   scaling of `HVap_A`) from the property package and returns 2.444e7 (J/kmol, the unit of
   `HVap_A`) for A at 360 K where the package uses 2.5e7. The probe reads back through the package's own routines instead.
6. **DWSIM liquid density** is pressure-corrected by default (§5.0).
7. **DWSIM recycle defaults** are loose and composition-blind (§5.2).
8. **.NET 8 reaches end of support on 2026-11-10** (Microsoft release metadata, fetched 2026-09-24).
   DWSIM 9.0.5 requires `Microsoft.NETCore.App` 8.x; the pinned tarball stays downloadable, but it
   will receive no further fixes. A later DWSIM release may move the runtime.
9. `ipopt` from the IDAES extensions relies on host `libgfortran5`, `libblas3`, `libopenblas0`.

## 7. What this record does not establish, and what is open for the design lane

It does not compare any number with this project, choose a tolerance, designate the eight release
comparisons, or decide `AGREE`/`DISAGREE`/`NOT_COMPARABLE`. Tool outputs in the JSON files are
not reference values: they come from placeholder specifications chosen only to exercise each unit.

Open for T06's `specifier`/`verdict`, with the evidence above:

- Whether SYN-001 comparisons are restricted to P = P_r (where both tools' K equals SYN-001's), or
  the missing Poynting factor makes P ≠ P_r fixtures `NOT_COMPARABLE`.
- Whether the DWSIM latent-heat offset (P_r v_i = 10 J/mol) is absorbed by entering
  ΔH_vap,i = L_i + P_r v_i — an input mapping, not tuning, but it is a choice — or DWSIM heater/flash
  duties are declared different-equation cases.
- Which solver settings are registered inputs of a reference: DWSIM Recycle and flash tolerances;
  IDAES/Ipopt tolerance and linear solver (default MA27 is HSL — §4.2).
- The pressure-closure form for the IDAES mixer, and the reaction data (formation enthalpies) for a
  synthetic conversion-reactor case, once T05 fixes this project's valve, pump and reactor
  contracts.
