# T06 M6 — blind reference qualification (DWSIM 9.0.5, IDAES 2.13.0)

**Package:** T06, work order **M6** (`docs/derivations/T06-corpus-spec.md` §17). **Lane:** build.
**Recorded:** 2026-09-25, on `wp/T06` at `792c594`; harness committed in `ce416ce`.
**Authority:** spec §9.2 (fixtures REF-01 … REF-08), §9.3 (matched semantics, registered solver
settings), §9.4 (positive controls PC-1, PC-2), §9.5 rule 1 (fingerprint) and rule 2 (the tool's own
overall component balance, 3.1e-8 mol/s), §9.6 (blindness).

**Blind.** This record holds, per tool and fixture, only: did the tool accept the model, did it
converge, does its own component balance close (rule 2), further tool-internal self-consistency,
versions, fingerprints, wall time, and the hashes of the raw outputs. The harness reads nothing of this
project and not the twin; no tool number has been compared with anything but the same tool's other
numbers, and none is quoted here. Comparison, classification and verdict are W8 and phase V.

## 1. Environment

Both environments were rebuilt with `scripts/build-reference-envs.sh all` in this worktree: **36 s**
(download cache copied from an earlier worktree and re-verified by the script's pinned hashes; warm
pip wheel cache). The fingerprint printed by the build equals `docs/reference-environments.md` §3 on
all seven lines, and each record re-measures it (pip freeze, tree and binary hashes) and finds it equal
(`environment_fingerprint.matches = true` in all 19 run records): §9.5 rule 1 does not fire.

| Tool | Versions recorded in every record |
| --- | --- |
| DWSIM | DWSIM 9.0.5.0, .NET runtime 8.0.31, pythonnet 3.1.0, CPython 3.13.5; Raoult's Law, `UniversalFlash` |
| IDAES | idaes-pse 2.13.0, Pyomo 6.10.1, Ipopt 3.13.2 with **MUMPS** in every final solve (each Ipopt log says "running with linear solver mumps"), CPython 3.13.5 |

## 2. Reproduction

```bash
scripts/build-reference-envs.sh                     # if .venv-idaes / .venv-dwsim are absent
spikes/references/t06_qualify.sh all [OUT]          # default OUT: evidence/T06/artifacts/m6-qualification
```

`t06_qualify.sh` runs `t06_qualify_idaes.py` and `t06_qualify_dwsim.py` (inputs and settings in
`t06_fixtures.py`), writes `OUT/<tool>-<fixture>.json` and the Ipopt logs, and prints the flag table
of `t06_qualification_summary.py`. None of it is part of `scripts/check.sh`. Raw records are git-ignored
(`evidence/**/artifacts/`); spec §9.6's committed `benchmarks/t06/references/results/` is W8's.

**Reproducibility, measured:** a second full run gave identical flags and identical record content
with the wall-time fields removed (the third hash column of §5), for all 20 records.

## 3. Results

Accepted: DWSIM — every object created, connected and configured without an exception; IDAES — the
model built with zero degrees of freedom. Converged: DWSIM — every object calculated, no solver error,
and for REF-08 the `Recycle` block reports convergence within its iteration limit; IDAES — Ipopt ends
**"Optimal Solution Found"** (Pyomo also calls "Solved To Acceptable Level" optimal; the harness does
not). Rule 2 column: the tool's largest per-component residual of inlets (+ ν ξ for REF-07; fresh
feed for REF-08) minus outlets, from its own streams/ports, against 3.1e-8 mol/s.

| Fixture | DWSIM accept / converge | DWSIM rule 2 (mol/s) | DWSIM further self-checks | IDAES accept / converge | IDAES rule 2 (mol/s) | IDAES further self-checks |
| --- | --- | --- | --- | --- | --- | --- |
| REF-01 mixer | yes / yes | 2.2e-16 PASS | energy 0 | yes / yes | 2.2e-16 PASS | 6 it; max constraint violation 9.7e-11 |
| REF-02 splitter | yes / yes | 0 PASS | energy −1.7e-16 | yes / yes | 8.9e-16 PASS | 3 it; 6.5e-11 |
| REF-03 heater | yes / yes | 2.2e-16 PASS | energy 0; VLE 3.6e-17 | yes / yes | 0 PASS | 3 it; 9.5e-11 |
| REF-04 ideal flash | yes / yes | 4.4e-16 PASS | energy 0; VLE 0 | yes / yes **(adjusted)** | 2.2e-16 PASS | 3 it; 1.0e-10 |
| REF-05 valve | yes / yes | 2.2e-16 PASS | energy 3.3e-13; VLE 1.5e-16 | yes / yes **(adjusted)** | 5.4e-15 PASS | 3 it; 5.8e-10 |
| REF-06 liquid pump | yes / yes | 2.2e-16 PASS | energy 0 | yes / yes **(adjusted)** | 2.4e-15 PASS | 3 it; 2.1e-10 |
| REF-07 conversion reactor | yes / yes | 0 PASS | energy −3.1e-16 | yes / yes | 1.1e-16 PASS | 5 it; 9.4e-11 |
| REF-08 recycle | yes / yes (Recycle: 32 it) | 4.4e-12 PASS | energy 2.6e-12; VLE 1.8e-17 | yes / yes | 2.2e-16 PASS | 25 it; 9.5e-11 |
| PC-1 (REF-04, ΔH_vap = L_i) | yes / yes | 4.4e-16 PASS | energy −8.1e-17; VLE 0 | not applicable (§4 Q1) | — | — |
| PC-2 (TP flash 370 K, 1.5e5 Pa) | yes / yes | 1.4e-11 PASS | energy −1.6e-16; VLE 4.3e-11 | yes / yes | 0 PASS | 3 it; 4.4e-11 |

Further self-checks. DWSIM "energy": its own boundary balance Σṁh(in) + energy streams − Σṁh(out)
− ξ Σν_iΔH_f,ig,i (the last term only for REF-07, from the formation enthalpies DWSIM holds, since its
stream enthalpies carry none), relative to the largest term. DWSIM "VLE": max_i |y_i P − x_i Psat_i(T)|/P
over its own two-phase results with its own `AUX_PVAPi`. IDAES: Ipopt iterations, and the largest
violation over all active constraints of the solved model in the model's own units (W, Pa, mol/s).

Wall time per fixture (build + solve): DWSIM 0.01–0.62 s (runtime start 2.1 s once); IDAES 0.19–1.82 s.

## 4. For the design lane (before W8)

**Adjustments (settings changed only to converge, judged on self-consistency).** DWSIM: **none**; §9.3
as registered. IDAES: **`constr_viol_tol` 1e-10 → 1e-9 on REF-04, REF-05, REF-06** (all else §9.3).
With 1e-10, REF-04 and REF-05 end "Search Direction is becoming Too Small" (Pyomo:
`internalSolverError`) with the unscaled violation stuck at 1.02e-10, and REF-06 ends "Solved To
Acceptable Level" at 1.16e-10; the scaled NLP error is ~1e-12 in all three. The largest residual is a
row in Pa of a state block at 1e5–1.8e5 Pa (REF-04, REF-05: the subcooled inlet's
`equilibrium_constraint`; REF-06: the outlet's `eq_temperature_bubble`), where 1e-10 Pa is ~1e-15
relative — the absolute tolerance is at that row's double-precision floor. 1e-9 is the smallest decade
that ends "Optimal Solution Found" (3 iterations each). Rule 2 closes to ≤ 1.5e-13 mol/s both before and
after. Proposed: register `constr_viol_tol = 1e-9` for IDAES (uniformly, or for these three).

**Questions, each with the choice made (isolated in `t06_fixtures.py`, reversible there).**

- **Q1 — PC-1 in IDAES.** §9.4 defines PC-1 as "DWSIM with ΔH_vap = L_i on REF-04"; IDAES's SYN-001
  mapping has no ΔH_vap input (its enthalpies are SYN-001's, `docs/reference-environments.md` §5.0), so
  there is no unmapped IDAES variant. Recorded `not_applicable`; not run. Alternative: an IDAES
  analogue (h_form,ig = L_i − P_r v_i), which would be a new control for §9.4 to define.
- **Q2 — PC-2's feed.** §9.4 names the flash (370 K, 1.5e5 Pa) and the equimolar composition only.
  Chosen: REF-04's feed (1, 1, 1) mol/s, 300 K, liquid, at 1.5e5 Pa, so the flash has no pressure
  change. Only a duty would depend on the inlet temperature; PC-2 compares `S2.n`.
- **Q3 — REF-08's tear/initialization guess** is not in §9.3. Chosen: the representability probe's S6
  stream, (0.2, 0.6, 0.8) mol/s, 360 K, P_r, set before any comparison existed; not this project's
  registered initializer (whose values come from the twin). DWSIM initializes its `Recycle` outlet with
  it; IDAES fixes it on the mixer's recycle inlet for the sequential initialization only.
- **Q4 — IDAES initializers.** They call `get_solver()`, whose Ipopt defaults to HSL MA27; the harness
  sets `idaes.cfg.ipopt.options.linear_solver = "mumps"`, so MA27 is used nowhere. Their other options
  stay IDAES defaults (tol 1e-6, max_iter 200); only the final solve carries §9.3's options.
- **Q5 — "converged" for IDAES** excludes Ipopt's "Solved To Acceptable Level" (see §3). This is what
  turned REF-06 into an adjustment rather than a pass.
- **Q6 — REF-07's extent in DWSIM** is not exposed by `RCT_Conversion`; rule 2 uses
  ξ = X_A(tool) · n_A,in / |ν_A| with X_A read from the reactor's `ComponentConversions`. The A row of
  rule 2 is then close to an identity; B and C carry the check.
- DWSIM's `Recycle` runs in its default `LegacyMode = true`; recorded, not changed.

## 5. Raw outputs (run 1; git-ignored, `evidence/T06/artifacts/m6-qualification/`)

The file hash identifies these bytes (they include wall times); the content hash is SHA-256 of the
record as canonical JSON (sorted keys, compact) with every `wall_time*` key removed — what a rerun must
reproduce, and did (§2).

| Record | SHA-256 of the file | SHA-256 of the content without wall times |
| --- | --- | --- |
| `dwsim-REF-01.json` | `8c58bc0cb7f863dc41c14932bcca2f065371f417cf149ec916e54c498404fd7c` | `261e41568eb18a566bbfc067d39a1e5d1e9de9b88976bba7ac53a27212721c56` |
| `dwsim-REF-02.json` | `af415d7d44b4092eb2181ec791feb0178ff4249d8ecf7cdba2057f3bb23f7c40` | `90ac7a800fba9cc4049b92d191c2b5562748adc61fb0e5b2c49f04cac9bee026` |
| `dwsim-REF-03.json` | `ed9eac7dc1ca35cf124d0155d2987774feb915e5bba9e6de3889094bcaf4c169` | `65b18ebcf469a7403fa695a0936c45bd43897df5ecfae7719b009641c2ae1a1b` |
| `dwsim-REF-04.json` | `a5de0c0528c59bad5a7cb0cf8007b1a7354ec46145900aba36a0b463ae532927` | `4bf051a687d9f3be72ca7c71d2f751832e146abfe6e90ed85e868f006052e163` |
| `dwsim-REF-05.json` | `6ab9c5a2436a3356b84e5858b4b38c8ec33775234dac24a0842a69844b699a5f` | `d9b4ace4c50a79e49340568809bdb5c4fe1237a86d4b93cd5123dec6be0bd157` |
| `dwsim-REF-06.json` | `66163e2f2b03760cf8a3899920ce62533b4759e473604711e7bfee95a15bfa59` | `0e8b13f8a330e6eaef7d04939fa76cb587e46ea4c1f47936e2e13236406111d2` |
| `dwsim-REF-07.json` | `51f39bdf1e5d81063e959bad8174e85622cdf89610be7dd2ff9a7d8e3a4415b3` | `336754825adff088073f474d883aa2e9e92b1703f0e9c9af5ab8b2c0b05d561e` |
| `dwsim-REF-08.json` | `5e04a4404aea5fe4d3e17937ef2eda38e4a885e0000c9a907185bd1a68ead9e1` | `024afd5307003b0552e566c33294a8649a5f2ce40864777237d18361b1dc142e` |
| `dwsim-PC-1.json` | `259eded445e6d427adf09af38a1fc40c3d41706238e068b19d9b747761e6c735` | `ed9714a1de2a123260c1f342190c66e9ded2c2dc60ecca9373c69d1b0b8af7ae` |
| `dwsim-PC-2.json` | `db36b097b620ec08566f700f144cb6857557e966563c4601887c3009c20d11b1` | `5d6b5471310780e10215f022b1a3c0799f3bd6562097b8a52d3772c0f110e27c` |
| `idaes-REF-01.json` | `6a11e61cace1a6310bec0a329bdd01b9b7055b83933d6c73633cc3997c472cc2` | `4caccbe2690ed795ded564577feb8f5598de2be58f92547ef832ae44a77bc774` |
| `idaes-REF-02.json` | `f6d857e317a8f787db06317cd98a009ba74f8708dec03f142d585b9f1daa7e9c` | `c9957f9ade987986a71b3059e0faa61db0c5335f83db3c9eab68326a92c335e0` |
| `idaes-REF-03.json` | `8f850cf9dfb03fac5044025fa978dfe7138b9b133b89f1d65f69a145594943a6` | `51e0af18d53dadfd76e1e1fd7116ed69ee8e29ee2ddca9141b0dc675f522813d` |
| `idaes-REF-04.json` | `dff7874b4141663a9c5bed166bf07aa8adc30ef3af80f44f3fde3dd668a741d2` | `66f387a9cef7c93b2bb084273a160211615857ec24fec6a7a0c604203a845f10` |
| `idaes-REF-05.json` | `52450131d77b8298f080f3aafb48c4b9b01d28c5aa302437530ca41073ef4dad` | `5a84346c80db2167ba957d16143f73a116adc537706ebfc7fdf1c6e14efad575` |
| `idaes-REF-06.json` | `64e9ee2bd4f54a5491ec53efb9f69b81cf1512816fd5b7499026e7bfde48dc80` | `cdf8840e37cd8e31184a14de165c4d61e31d23f6716b53bea7187d1313bec6c8` |
| `idaes-REF-07.json` | `d2c0160ef5987755682e8c3881630ec5f8f54550ebc78ee2229f67dec463b628` | `4df6f7e291b0e7980959f2279b7bc4f71fd17c715d26e065e9a6eaea2775bf71` |
| `idaes-REF-08.json` | `2e4ad06cc8a4a2f21c8fced6e38b2460a3f078c951e873fec2f34bcb1b90a2dc` | `aa370e708be7b0c402eeeab252a409874c8ee864cd0bef39f4f4ddc7bc44033e` |
| `idaes-PC-1.json` | `6b94212ac0b1c7962e2e2a58363b4461a03b7acef836b9e7779630ff0624a45f` | `e50aee43b3a9ec682a9ff427cb283a41125ab73acd4aa6a549d21a438d861383` |
| `idaes-PC-2.json` | `fd08e854f3adadde835e8ceddfd01dcc1ed9a27ccb7a13a04b3c6d66e3b8af2e` | `9ee2c38ce2c4577dc24ab1a3797638dc0300febf0416aa8078bad8f7dffa1bdc` |

## 6. What this does not establish

No comparison with this project or the twin, no `AGREE`/`DISAGREE`/`NOT_COMPARABLE` classification
beyond rules 1 and 2 not firing, and no statement that PC-1 or PC-2 will classify `DISAGREE` (that
needs our side, W8). Rule 2 passing establishes that each tool's own balance closed, not that it
solved the same equations as SYN-001 (that rests on the §9.3 mappings, `docs/reference-environments.md`
§5). Wall times are not compared across tools (plan §6.2).
