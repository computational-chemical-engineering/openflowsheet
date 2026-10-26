# S10-C brief: the liquid-mixture method in the PH flash and the column (design lane, `architect`)

Branch `wp/S10C`, worktree `.claude/worktrees/s10c`, from `main` `ffcb387f`. Scope: S10 spec `docs/derivations/S10-spec.md`
§10 (l.965-985), ADR 0047 (Proposed; l.31, l.161-163: "S10-C takes the PH flash and the column, with an `architect` pass,
because K(x) changes the cascade's Jacobian structure"), R-709, R-711. S10 (`wilson-ig-v1`) is merged and `tested`;
S08 (one-phase column sections, Stage B) is merged (ADR 0048 Proposed).

## 1. The question

How do the PH kernel and the SYN-001 column consume a φ-provider whose K depends on composition (`wilson-ig-v1`), with
residual and Jacobian describing the same function, so that the registered column cases C-MW and C-EW can be solved —
and what replaces the S11 refusal for this provider? Return a design note with an ADR (if a frozen interface or an
accepted ADR changes), work orders and verification gates, leaving the build lane nothing scientific to choose.

## 2. Why the architect

It changes the compiled column graph (a new ∂K/∂x Jacobian block where today K depends on (T, P) only), generalises a
kernel that five unit models and the orchestrator's column-split closure share, and touches the phase contract's
assumptions (S08's Stage B builds openings from K(T, P)). A wrong choice regresses every SYN-001 case.

## 3. Current state (recon digest, main `ffcb387f`)

**PH kernel** `src/openflowsheet/models/syn001/ph_kernel.py`: asks the provider only for a TP flash, `h` and `lnK`
(ADR 0011 D1/D3). `ph_state(provider, flows, pressure, target, context, *, max_evaluations=200) -> PHState` (l.250-380):
P-domain check; saturation route for exactly one flowing component (`_saturation_temperature` l.497 solves ln K = 0 via
`_ln_k` l.474, `PropertyRequest(..., phase="LIQUID", properties=("lnK",))`; `_saturation_split` l.536); temperature
(bracket) route `f(T)` (l.304-313) over `tp_state` and `enthalpy_flow − target`; band fallback `_band_route` l.382
(bisection in β, `band_temperature`, `band_split(n, k_values, β)`) only after the temperature route fails, ≥ 2 flowing
components. `_closure_rows` l.196 reads `lnK_<c>`. SYN-001-specific: the `lnK_<c>` keys (ph_kernel 227, 494;
`saturation_band.py:113-114`; `tp_state.py:349-350`), `h_<c>` (`tp_state.py:109, 169-170`), `REFERENCE_CONVENTION`
stamped on every UnitEvaluation (ph_kernel 48, 623, 629, 692). The bracket argument (§4.2) is stated for SYN-001
(strictly increasing Ḣ_TP). No derivative supplied (sensitivity `unavailable`).
Consumers: `PHFlash` (`ph_flash.py:225`), `Valve` (`valve.py:150`), `ConversionReactor`, `LiquidPump`, `KineticCSTR`
(`port_enthalpy`), and the orchestrator's column-split closure `region.py:619` `_ph_closure`.

**Providers** (`thermo/__init__.py`: `PropertyCapabilities` l.62, `PropertyRequest` l.133, `PropertyResult` l.150,
`FlashRequest` l.174, `PropertyProvider` Protocol l.210, frozen per `docs/interfaces-frozen.md` §1):
- SYN-001 (`thermo/syn001.py:74`): properties `h`, `lnK`; derivatives ∂T, ∂P only (∂/∂n refused); TP flash.
- `wilson-ig-v1` (`thermo/wilson_ig.py:433`): properties `h` and `lnphi_<c>` only (**no `lnK`**); ln φ^L = ln γ + ln P^sat
  − ln P, ln φ^V = 0, so K = γ P^sat / P; derivatives ∂T, ∂P and **∂/∂n_<c>** (projected, l.424, l.553-567); h^E = 0;
  TP flash only, flash derivatives refused, PH flash not a provider capability (`FlashRequest` carries no enthalpy,
  limitation l.1014-1016); `stability()` l.705 outside the frozen Protocol (R-703).

**Column / cascade K path:** `cascade.py:423-445` `_k_values` probes K at a composition-neutral unit flow
`n=(1.0,)*N` with `properties=("lnK",)`. `LnKBlock` (`blocks.py:50`): `input_ids = ("T","P")`, Jacobian columns T, P only,
`_PROBE_FLOW = 1.0`. Equilibrium row `models/rows.py:137`: `v_i L − exp(lnK_i) l_i V`; no ∂K/∂x block exists.
Column graph: `column.py:1176` (LnKBlock), `:1398`, `:1659` `_k_values(... profile[j-1], spec.pressures[j-1])`;
`column_solve.py:844`; S08's `column_blocks.py:231` (Thomas path, K at (T_j, P_j)). Cascade `cascade.py:681-721`, 816,
1085-1092. The only property cache is `thermo/cache.py:123` `ExactPropertyCache`, keyed on the full canonical state
including composition. **S11** (`cascade.py:397-420`, called at `cascade.py:495` and `column.py:630`): identity check on
`provider_id == "syn001"` and the SYN-001 reference convention — "a provider with composition-dependent K would declare
what SYN-001 declares and be answered silently wrong".

**S10's TP flash** (`wilson_ig.py:580`): closed-form vapour trial, liquid-trial successive substitution, two-phase SS with
Rachford–Rice; EPS_TPD 1e-10, δ_K 1e-13, δ_SS 1e-13, SS_MAX 1000; failure → `not_converged`, UNKNOWN, no outlets.
**E-2 / R-711** (spec l.1082-1110): near an azeotrope the SS step has a noise floor ≈ u‖G‖/min|K_i − 1|, above δ_K once
|K_i − 1| ≲ 1e-4; 7 of 20 measured near-azeotrope states hit the cap. "The remedy is S10-C's: a stop tied to the
conditioning, or an iteration that does not pass x through β. S10-C's PH flash searches inside this sliver."

**Registration:** `LIBRARY_ONLY_PROVIDERS["wilson-ig-v1"] = "S10"` lives in `tests/test_t08_w2_support_envelope.py:337-342`
(the commit that makes a provider selectable removes it and reclassifies U02 items); U02 rows
`benchmarks/t08/support_envelope.yaml:5622-5866`. `SELECTABLE_BASES` (`application/revision_binding.py:1540`; 
`models/revision_flowsheet.py:135` returns SYN-001 and C1 only); `MODEL_BASES` (`revision_binding.py:1461-1464`).
**Flowsheet admission is Frank's call** (R-709, Q-F2); the default is library-level only.

**Registered column cases** (S10 spec §10, definitions only; S10-C's specifier may amend them to the column's
specification set):
- C-MW: methanol–water at 101 325 Pa; 20 equilibrium stages incl. a total condenser and a partial reboiler; feed
  1.0 mol/s saturated liquid, z_M = 0.4, stage 10 from the top; distillate 0.4 mol/s; molar reflux ratio 1.5.
- C-EW: ethanol–water, same configuration; z_E = 0.2; distillate 0.18 mol/s; reflux ratio 3; distillate must stay below
  the azeotrope composition (azeotrope-limited).

## 4. Constraints and invariants

- Every registered SYN-001 case (T05/T05b flash cases, S01/S02/S06/S03/S08 column and cascade cases, flowsheet cases)
  stays bit-identical unless you state and justify a change; prove it as S08 did (G1-style digests against the merge
  base, an empty diff on frozen paths).
- The `PropertyProvider` Protocol and schemas are frozen; a change needs an ADR.
- Residual and Jacobian describe the same function at the same state; exact caches key on exact inputs.
- No placeholder success path; anything not covered ends typed.

## 5. Already decided, and what is open

Decided: library-only stays the default until Frank decides admission; S11 stays for every other non-SYN-001 provider;
C-MW and C-EW are the driving cases (binaries — the methanol+ethanol Λ identifiability issue, S10 review S-4, does not
bear on them; it matters only for ternary column claims, which are out of scope); VAL-3's latent-heat miss
(methanol Δh +5.72 %) is a stated limitation (Q-N5: whether S10-C's energy balances need a vapour non-ideality term is
the specifier's to rule — say whether the design needs it).

Open (decide):
1. **The PH kernel:** generalise it to φ-providers (K from `lnphi`), or a provider-specific PH route for `wilson-ig-v1`;
   how the bracket argument and the band route hold for K(x) (Ḣ_TP monotonicity, the band's K(T)); the saturation route
   for a pure component.
2. **The column:** how K(x) enters the compiled graph (a block with inputs (T, P, x) and its ∂K/∂x Jacobian; where the
   composition comes from — the liquid on the stage), the initialisation (the Thomas path and S08's Stage B build
   openings from K(T, P)), and the phase contract's band/kernel calls.
3. **What replaces S11 for `wilson-ig-v1`:** a capability check (provider declares composition derivatives), an
   allow-list, or another rule; every other provider stays refused.
4. **E-2:** the conditioning-tied stop or the alternative iteration, and whether it lives in the provider's TP flash or
   in the PH flash.
5. **Registration of C-MW/C-EW references:** whether a generator can give their roots independently (50-digit, as S08's
   WO-G did) and whether IDAES (already qualified for S10's flash) can serve as a column reference.
6. The work orders (each ~150k context) with acceptance tests, and which parts need a `specifier` (derivations,
   registered states) versus the build lane.

## 6. Verification

Name: the bit-identity proof for SYN-001; derivative checks (finite differences or mpmath) for the new K(x) block; C-MW
and C-EW roots against an independent expectation; E-2's remedy on the measured near-azeotrope states; mutation tests
showing the new path does the work (for example, dropping ∂K/∂x must break convergence or a derivative check).

## 7. Deliverable

- `docs/derivations/S10C-design.md`; an ADR `docs/adr/0049-…md` (Proposed) only if a frozen interface or an accepted
  ADR changes; register entries after the last R-number on `main` (R-736) **plus** the S09 block (R-740…R-752, on
  `wp/S09`, merging soon): start at **R-760** and note the gap.
- A docs-only commit on `wp/S10C`. Do not push. Report in at most 25 lines, including questions that turn on Frank's
  preference (flowsheet admission at least), each with a recommended default.

## 8. Out of scope

Ternary column claims and the methanol+ethanol refit (S-4); S08b; flowsheet binding beyond stating the admission
question; any change to S10's TP flash results on its registered states except E-2's remedy.
