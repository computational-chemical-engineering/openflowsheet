# PrISMa (Charalambous et al., Nature 632, 2024) as an OpenFlowsheet test case: scoping digest

Research date 2026-10-27. Read-only. "[SI §x / p. S-n]" cites the Supplementary Information PDF. "[Zenodo]" cites
files I downloaded and inspected. **UNVERIFIED** marks anything not confirmed from a primary source.

## 0. Sources
- Paper (open access): https://doi.org/10.1038/s41586-024-07683-8 and https://pmc.ncbi.nlm.nih.gov/articles/PMC11291289/
- SI PDF, 265 pp., 20.9 MB:
  https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-024-07683-8/MediaObjects/41586_2024_7683_MOESM1_ESM.pdf
  (the PMC copy is at /articles/instance/11291289/bin/41586_2024_7683_MOESM1_ESM.pdf)
- Other ESM on PMC: MOESM3 (CSV, 102 KB, isotherms for SI Figs. 8–26), MOESM4 (XLSX, breakthrough), MOESM2 (review).
- Data: https://doi.org/10.5281/zenodo.11244258 (v. 2024-05-22; concept DOI 10.5281/zenodo.8042598).
- Tool: https://prisma.materialscloud.io/ (**connection refused 2026-10-27; not checked**). Preprint: ChemRxiv
  10.26434/chemrxiv-2023-sn90q.

## 1. Process model (SI §3.2, pp. S-23–S-38; KPI definitions in SI §6.2)
**Scope.** The model covers a single column. The TEA layer scales it out to N_columns × N_trains. Pre-treatment is
excluded apart from the direct-contact cooler (DCC) that brings the flue gas to T_feed [SI §3.2]. The layer includes
the vacuum pump and the CO2 compressor train to the sink [SI §3.2].

**Cycles [SI §3.2.1, Fig. S3].**
- 3-step TSA: adsorption (AS) → heating (HS) → cooling/pressurisation with feed (CS). 5-step TVSA: AS → vacuum
  (VS) → intermediate heating (IHS) → HS → CS.
- Screening conditions are fixed: T_LOW = T_feed = 37 °C, T_MED = 47 °C, T_HIGH = 120 °C, P_feed ≈ 1.013 bar.
  P_vac = 0.2 or 0.6 bar for TVSA; TSA desorbs at 1.01325 bar [SI §3.2.1; Eq. S37 text].
- Column: a packed multi-tubular heat exchanger, 8 m long, L/D = 1.3. Pellet porosity ε_pellet = 0.35, bed porosity
  ε_bed = 0.37. ρ_bulk = (1−ε_bed)(1−ε_pellet)ρ_crystal [Eqs. S51–S52].
- Tornado base values [SI §10.1]: column inside diameter 6.15 m, tube ID 0.025 m, tube wall 2.1 mm, superficial
  velocity 1.75 m/s, U = 0.04 kW m⁻² K⁻¹, η_sat = 1.

**"Ideal" equilibrium shortcut assumptions [SI §3.2.1].**
- Instantaneous equilibrium, ideal step (shock) front; no radial gradients, axial or thermal dispersion, or pressure
  drop; homogeneous heat-exchange fluid temperature. AS runs to incipient CO2 breakthrough; evaluated at CSS.
- VS: an instantaneous "frozen adsorbed phase" depressurisation, repeated stepwise until dP/step from the last
  three steps falls below a threshold, which gives P_VAC-MED. After that the bed re-equilibrates by mass balance
  plus isotherm.
- IHS: ten T sub-steps to T_MED (pressure drops to P_vac in the first). HS: ten sub-steps to T_HIGH, product
  collected at P_vac. CS: ten sub-steps cooling and repressurising with feed, no gas out; feed amount from mass balance.
- References for the step models: the TSA model follows Ajenifuja, Joss & Jobson, IECR 59 (2020) 3485,
  10.1021/acs.iecr.9b05579 [SI ref S70]. The VS follows Santori et al., Energy 162 (2018) 1158 [S52] and
  Charalambous's PhD thesis (Edinburgh 2018, open: https://era.lib.ed.ac.uk/handle/1842/33311) [S67].

**Water co-adsorption [SI §3.2.1, Eqs. S1–S4, S43–S44, S50].** The bed splits into a water-loaded zone and a dry
zone.
- Penetration length: L_H2O = t_AS·ṅ_feed·y_H2O / (A_bed·ρ_bulk·(q_H2O,sat,geom − q_H2O,des)). Here q_sat,geom
  comes from the Zeo++ pore volume and q_des from a single-point GCMC run at 120 °C.
- t_AS is taken from the dry case (no iteration). α = L_H2O/L_CO2 = wet bed fraction.
- In the wet zone the CO2 loading is WRC·q_dry, where WRC = q_CO2(ternary GCMC)/q_CO2(binary) at feed conditions.
- Working capacity = α·WC_wet + (1−α)·WC_dry.
- Water regeneration heat: H_H2O = −Δh_H2O·ρ_bulk·A·L_H2O·Δq [S12].
- Sensitivity check [SI §9.3]: using 3×L_H2O raises nCAC by 4–16%.

**Energy terms [SI §3.2.3].**
- Heating: q_th = (Q_sens + H_ads)/n_HS,CO2 [S9]. Q_sens = m_solid·c_p,solid·(T_HIGH − T_LOW) [S10]. It counts the sorbent only; the gas phases are neglected and
    no wall or tube metal is included.
  - H_ads = Σ(−Δh_i)·n_i [S11], with a constant average isosteric heat per component, plus H_H2O.
- Cooling: q_th,cool = (Q_CS + Q_compr intercoolers + Q_DCC + Q_condenser)/n_HS,CO2 [S13–S22]. Water knock-out uses
  y_H2O,sat = P_sat(T_cool)/P [S22], with T_cool = 313 K.
- Electricity: w_el = (W_vac + W_comp)/n_HS,CO2 [S23]. Polytropic work: W = n₁RT₁(1/η_p)(n/(n−1))[(P₂/P₁)^((n−1)/n) − 1], (n−1)/n = ((γ−1)/γ)/η_p, η_p = 0.86 [S24–S26, §10.1].
  - Stages added until first-stage outlet T < 200 °C; equal pressure ratios, intercooling to 313 K, no intercooler
    ΔP, ideal gas with constant c_p [S26–S29]. TVSA adds a P_vac→1 atm compressor; SI §6.2.8 also names a booster fan.
- Sink: purity ≥ 96% before compression, 110 bar, compression at 40 °C [Table S2].

**Cycle time [SI §3.2.2].**
- t_AS = η_sat·n_AS,CO2/(ṅ_feed·y_feed) [S6]; t_VS = V_out/(υ_out·A_tubes) [S7]; heating and cooling steps: t = (c_p,bed·V_bed·|ΔT| + H_ads)/(U·A·V_bed·(T_HEX − T̄)) [S8].
  **UNVERIFIED:** the SI gives no numerical value for A (m²/m³), T_HEX or υ_out.

**KPIs [SI §6.2].**
- Purity [S39] at the compressor-train outlet; recovery [S40] = n_CO2,HS/(n_CO2,in,AS + n_CO2,in,CS); effective
  recovery [S41] = recovery·(1 − CC).
- Working capacity [S42/S44]: the SI states mol m⁻³, but the Zenodo column holds values around 1–4. These match the
  "3.96 mol kg⁻¹" quoted in SI §9.3.1, so the CSV column is most likely mol kg⁻¹ (inferred).
- Productivity [S45]: mol kg⁻¹ h⁻¹.

**Isotherms and mixtures [SI §3.1.2, §11.1.2].** PrISMa uses no fitted isotherm model.
- Pure CO2/N2 isotherms: GCMC at T_ref = 298.15 K (TraPPE CO2/N2, TIP4P/2005 H2O, UFF framework, rigid crystals).
- Isotherms at other temperatures come from the Clausius–Clapeyron relation, using the loading-dependent GCMC heat of
  adsorption (Moubarak et al., IECR 2023, 10.1021/acs.iecr.3c01358 [S44]). The heat includes a non-ideal-gas
  correction that the SI describes as new in this work.
- Binary CO2/N2 uses IAST, chosen over extended dual-site Langmuir because it was more accurate [SI §11.1.2]. An IAST
  flag compares IAST with single-point binary GCMC [Eq. S38].
- Wet zone: ternary GCMC at adsorption conditions. At desorption, water comes from pure-H2O GCMC (treated as
  independent) and is combined with IAST for CO2/N2.
- A Langmuir fit is used only for the uncertainty propagation [SI §5.6].

**Optimisation [SI §10.2–10.3, Table S9].**
- Objective: minimise nCAC as an NLP (KNITRO SQP). Degrees of freedom: 7 for TSA, 9 for TVSA. They include T_high (108–150 °C), T_low (lower bound 27.5 °C), d_col
  (6–10 m), d_tube (0.025–0.1 m), T_cool,lim, P_vac (0.1–1.01325 bar) and T_med (32.5–65 °C).
- Constraints: purity ≥ 96%, recovery ≥ 90% [S75–S76], pinch/utility limits [S77–S78], T_med − T_low ≥ 5 K [S79].
- Applied to UK cement, TSA and TVSA 0.6 bar, for the top 30 materials. TVSA optimisation lowers nCAC by about
  €7/t (about 12%) [main text].

**Validation [SI §3.2.4]:** TSA vs Ajenifuja (13X, 12% CO2); TVSA vs in-house gPROMS (Young et al., EES 2021);
water after Li/Webley, AIChE J. 2014 [S63] and Leperi, IECR 2016 [S64]. No numbers in the SI.

## 2. Case studies (SI §1, Tables S1–S3)
66 cases = 22 source–sink–region–utility combinations × {TSA, TVSA 0.6 bar, TVSA 0.2 bar}. Sink: geological storage.

| Source | wet y (CO2, H2O, N2, O2, Ar) | T_feed | P_feed | F (wet) | Notes |
|---|---|---|---|---|---|
| NGCC | 0.0396, 0.0838, 0.7438, 0.1239, 0.0089 | 86.8 °C | 1.01 bar | 1330.6 kg/s | LP steam 205 kg/s; 830 MW |
| Coal | 0.1373, 0.0973, 0.72855, 0.0365, 0.00005 | 50 °C | 1.016 bar | 735.12 kg/s | 758.6 MW |
| Cement | 0.18, 0.09, 0.63, 0.10, 0.00 | 110 °C | 1.013 bar | 107.81 kg/s | waste heat 8.2 MW (clinker cooler air at 285 °C) |

- The model lumps O2 and Ar into N2. The dry/wet compositions used are in Table S2 (e.g. cement dry 0.1978/0.8022).
- Regions: UK (2019, 2022 prices), US, CH, CN-GD, CN-SD; no CH coal case. Utility options: steam extraction, NG boiler, electric boiler (CH), waste heat (cement), existing or additional
  cooling, onsite power or grid [Table S1].
- Plant data [Table S2]: lifetime 25 y (NGCC, cement) or 40 y (coal); 3 y construction; operating-hours ramp
  3500/5700/7500 h (power) or 7998 h (cement).
- Data sources: S1 = Sanchez Fernandez et al., Fuel 2014 (EBTF); S2 = Manzolini et al., Appl. Energy 2015;
  S3/S4 = CEMCAP D3.2/D4.2.

## 3. Techno-economic layer (SI §3.3, §4.1, §6.3)
- **CAPEX** (Woods bare-module method) [S30–S32]:
  - TDC = Σ FOB·LM; EPC = (1+P1)(1+P2)(1+P3)·TDC; CAPEX = (1+P4)·EPC; P1 = 0.10, P2 = 0.14, P3 = 0.30, P4 = 0.07
    (contingencies from Rubin et al. 2021).
  - FOB and LM costs come from **Aspen Capital Cost Estimator (commercial)** and Woods (2007) [S72–S73].
  - Equipment: shell-and-tube packed column, sorbent inventory, vacuum pump, intercooled compressor, DCC, boilers,
    coolers, cooling tower [Table S4].
  - Calibration sources are listed, but **the cost correlations themselves are not printed in the SI**.
  - Location factor: 1 (UK/CH/US), 0.77 (CN). CEPCI: US2019 607.5, US2022 804.6 [Table S3].
- **OPEX** [S33, discounted]: fixed (EBTF guidelines; operator €61,180/y) + variable utilities + sorbent replacement
  every 5 y at €30/kg for every MOF. Cooling water €2/m³ [SI §10.1].
- **Finance:** discount 8%, IDC 8%, TCR = CAPEX + IDC (EBTF) [SI §6.3.3, §10.1]. **Currency/year:** euros. Prices are 2019 annual averages, plus Jan–Sep 2022 for the UK. The MEA benchmark was
  escalated from 2008 to 2019 with the Euro-area HICP [SI §4.1].
- **Utility prices** (€/MWh, 2019):

  | | UK | CH | US | CN-GD | CN-SD |
  |---|---|---|---|---|---|
  | Electricity | 131.7 | 107.0 | 60.9 | 98.25 | 80.80 |
  | Natural gas | 24.63 | 59.65 | 11.52 | 37.12 | 37.12 |
  | Coal | 9.42 | – | 5.43 | 10.91 | 10.97 |

  UK 2022: electricity 216.3, natural gas 54.99, coal 32.14 [Table S3].
- **Metrics:** CAC [S53/S54] (energy-related life-cycle emissions only); LCOC [S57] = (TCR + Σ OPEX/(1+r)^y) /
  Σ (ṁ_captured·h)/(1+r)^y; CCC [S58–S59] = (LCOE_cc − LCOE_ref)/(ṁ_captured/Ẇ_cc) for power, CCC = LCOC for industry.
  - **nCAC = CCC_system/(1 − CC) [S55–S56]**, where CC is the LCA climate-change score in kgCO2e/kgCO2 captured.
    nCAC uses the system perspective, so a power plant's parasitic loss is compensated at market electricity price.
    SPECCA is defined in [S6.3.10].
- **MEA reference:**
  - Power: EBTF (Sanchez Fernandez 2014; Manzolini 2015) moved to 2019 €, PrISMa contingencies, UK 2019 fuel prices.
    Cement: CEMCAP D3.2/D4.2 (Anantharaman et al. 2016/2017). ±50% sensitivity on MEA CAPEX/OPEX [SI §4.1, §4.3].
  - **Numerical MEA nCAC values are not stated in the text I read.** The main text says only that cement nCAC is
    "about a factor of two lower than the benchmark" and that no material beats MEA for NGCC. The values are probably
    plotted in figures (UNVERIFIED).

## 4. LCA layer (SI §3.4, §4.2)
- Cradle-to-gate, functional unit **1 kg CO2 captured**, transport/storage excluded [SI §3.4.1]. Method:
  **Environmental Footprint 3.0** (EC-JRC), 28 categories (16 main + 12 sub) [SI §3.4.3].
- Background data: **ecoinvent v3.8, APOS system model** (commercial), with region-specific LCIA scores [SI §2,
  §3.4.3].
- Foreground: a predictive model for MOF synthesis.
  - Linker proxy by PubChem similarity; metal-precursor market process by hierarchy; solvent selection; disposal and
    recycling; plant construction; use-phase utilities from the TEA.
- MEA LCA uses Singh et al. (NGCC) and Koornneef et al. (coal) LCI data [SI §4.2].
- **Licensing:** reproducing the background requires an ecoinvent 3.8 licence. EF 3.0 characterisation factors are
  public from JRC. The published per-material LCA results (all 28 categories) are in the CC-BY Zenodo KPI tables, so
  comparing against them is not blocked. Whether ecoinvent-derived per-utility factors may be redistributed in an
  open repository: **UNVERIFIED (check the ecoinvent EULA)**.

## 5. Zenodo 10.5281/zenodo.11244258: licence **CC-BY-4.0**, 8 files (inspected)
| File | Size | Content |
|---|---|---|
| KPIs_Simulated.zip | 180 MB (461 MB unzipped) | 141 CSVs: 66 cases × dry plus 75 wet, including 6 "Feedback_" files. About 1185 materials per file. |
| KPIs_Experimental.zip | 243 KB | Same columns for experimental-isotherm materials (e.g. CALF20_exp_powder, CuAlPyC_exp); wet only. |
| Material_Properties.zip | 2.1 MB | Isotherm-Simulated.csv (2676 rows = 1338 materials × CO2/N2) and Isotherm-Experimental (CALF-20, CuAlPyC, 13X). Material_KPIs (Henry constants, uptakes, Qavg), Water_{Cement,Coal,NGCC} (H2O q_sat, Henry, q_des, heats, binary/ternary CO2 uptake, WRC), Zeo++ (density, POAVF, Cp). |
| Optimization.zip | 114 KB | Optimised KPIs and optimal x (normalised) for UK cement TSA-wet and TVSA06-wet, plus a feedback variant. |
| Uncertainty.zip | 11 KB | Perturbed isotherms (e.g. MgMOF74) and nCAC for UK cement TVSA06-wet. |
| Flags.zip | 62 KB | IAST flag per source; flexibility data. |
| Cifs.zip | 4.5 MB | Structures. |
| Experimental_Validation_Data.csv | 104 KB | Experimental vs computed isotherms (CO2, N2, H2O) with source DOIs. |

- **Isotherm format:** raw GCMC points, not fitted parameters. Each row holds Henry constant, a pressure list (bar),
  an uptake list (mol/kg), a loading-dependent heat list (kJ/mol) and T_ref = 298.15 K. There is one temperature per
  material; other temperatures are reached through the Clausius–Clapeyron relation.
- **KPI columns (75):**
  purity, recovery, working_capacity, productivity, spec_heat, spec_cool, el_energy; **product_out, n_out_vac,
  time_steps, vac_decay** (per-step states); rho_b, alpha; CAPEX, OPEX, CAC, CCC, LCOC, LCOE, spec_*_tot,
  CO2_avoided/captured, SPECCA; **CAPEX_bd/OPEX_bd/CAC_bd/cool_bd/power_bd** (breakdowns); 28 EF 3.0 categories;
  nCAC, eff_recovery, *_system variants.
- **Units are not documented in the deposit.** Inferred: spec_heat in MJ/mol, so 0.0709 MJ/mol × 1000/44 =
  1.61 = spec_heat_tot in GJ/t; CAPEX in M€.
- **Cross-checks hold:** MgMOF74, cement UK TVSA06-wet, nCAC 51.60 and WC 3.96 = SI §9.3.1 minimum "51.6 €/t";
  CALF20, same case, nCAC 72.47 = main text "€72/t".
- Sample reference numbers (wet, simulated structures; P = purity %, R = recovery %, WC = working capacity, q_tot =
  spec_heat_tot in GJ/t):

  | Case | Material | P | R | WC | q_tot | CCC (€/t) | nCAC (€/t) | CC |
  |---|---|---|---|---|---|---|---|---|
  | Cement UK TVSA06 | 13X | 99.41 | 99.37 | 1.99 | 2.10 | 52.7 | 63.7 | 0.172 |
  | Cement UK TVSA06 | MgMOF74 | 99.15 | 99.30 | 3.96 | 1.61 | 44.6 | 51.6 | 0.136 |
  | Cement UK TSA (dry) | MgMOF74 | 96.92 | 99.92 | 3.02 | 1.31 | 38.6 | 43.5 | – |
  | Cement UK TSA (dry) | 13X | 98.05 | 99.93 | 1.87 | 1.63 | 44.2 | 51.1 | – |
  | NGCC UK TVSA02 | MgMOF74 | – | – | – | 4.60 | – | 129.5 | – |

- **Caveat:** materials with CC > 1 give negative nCAC (e.g. RSM1382 in NGCC TVSA02, nCAC −1271). Filter on
  CC < 1 before ranking.

## 6. Code and related open models
- **PrISMa platform code is not public.** The paper's Code availability says the layer software is "available from
  the corresponding authors on request" [PMC page].
- kjappelbaum/prisma-adosorbaphore: persistence-image ML analysis; no licence file; last push 2023-06-15.
  ElMouba/PrISMa_VisTool: visualisation app; no licence; last push 2024-06-25; its "Upload" only e-mails the CIF to
  the team. **No process model in either repository.**
- github.com/lsmo-epfl/aiida-lsmo: AiiDA workflows for DFT and GCMC (materials layer) [SI §3.1.1].
- pyIAST (CorySimon/pyIAST, MIT) is usable for the IAST step. Moubarak's Clausius–Clapeyron workflow code: **not
  found (UNVERIFIED)**.
- Shortcut literature (equations public, no released code found): Ajenifuja 2020 [S70] (TSA basis); Joss et al.,
  IECR 54 (2015) 3027; Maring & Webley, IJGGC 2013 (cited by Ajenifuja per AIChE 2019 abstract; **not in PrISMa SI refs**).
- The only open implementation found: **IDAES `FixedBedTSA0D`** (a 0-D equilibrium shortcut after Joss 2015;
  4-step heat/cool/pressurise/adsorb cycle; default zeolite 13X; no H2O stated).
  https://idaes-pse.readthedocs.io/en/stable/reference_guides/model_libraries/models_extra/temperature_swing_adsorption/fixed_bed_tsa0d.html
  GitHub reports the licence as "NOASSERTION/Other" (IDAES's own BSD-style licence; not inspected).
- Riboldi et al., "Advanced methodology for screening of novel adsorption materials…", GHGT-15, SSRN 3815636: **not fetched.**

## 7. Updates since 2024
- Wang, Charalambous, … Garcia, "Crossing the Valley of Death: …", GHGT-17 (Oct 2024), SSRN 5068028: same 1200
  MOFs / 60+ cases; content not read (SSRN 403).
- **No 2025–2026 PrISMa journal follow-up, DAC extension or new Zenodo version found**; prisma.hw.ac.uk/publications
  stops at 2023. Same-group DAC work predates the paper (Young et al., EES 2021; CEJ 2023; One Earth 2023).
  Materials Cloud tool changes: **UNVERIFIED** (unreachable).

## 8. Assessment: a minimal faithful reproduction
**Needed:**
- (a) Isotherm reconstruction: Clausius–Clapeyron extrapolation of the 298.15 K GCMC points using the
  loading-dependent q_st, plus IAST for CO2/N2. Interpolation of tabulated points must be smooth, because an NLP
  needs derivatives.
- (b) The equilibrium-stage cycle model of §1: VS by repeated flash, IHS/HS/CS in 10 sub-steps each. These are
  algebraic mass/energy balances per sub-step, so they map onto OpenFlowsheet as a sequence of equilibrium "flash"
  units on a sorbent phase.
- (c) Compression train: polytropic stages with intercoolers and knock-out. This can be checked against
  OpenFlowsheet's compressor and flash units with CoolProp CO2/H2O properties; note that PrISMa uses ideal gas with
  constant c_p.
- (d) Material inputs per material: ρ_crystal, Cp, Qavg, and H2O q_sat/q_des/Δh/WRC. All are in Zenodo.

**Cheapest first targets:**
1. Cement UK **TSA-dry**, 3–5 named materials (MgMOF74, Zeolite_13X, CALF20): binary, no vacuum, no water;
   compare purity, recovery, WC, spec_heat. 2. **TVSA06-dry**: add VS/IHS; compare vac_decay, product_out per step.
3. **Wet**: add L_H2O/α/WRC (inputs in Water_*.csv). 4. Compression: el_energy, power_bd, cool_bd.

Process-layer outputs (purity, recovery, working capacity, q_th, w_el) do not depend on TEA or LCA, so they make a
clean independent expectation.

**Blocked or partly blocked:**
- Cycle time/productivity (A, T_HEX, υ_out not given). TEA CAPEX (Aspen ACCE data commercial, correlations not
  printed; CAPEX_bd could serve as given inputs). LCA (ecoinvent 3.8 licensed, MOF-synthesis model unpublished; nCAC
  only with CC from Zenodo as input). Platform code: on request only. CSV units: undocumented, confirm first.
