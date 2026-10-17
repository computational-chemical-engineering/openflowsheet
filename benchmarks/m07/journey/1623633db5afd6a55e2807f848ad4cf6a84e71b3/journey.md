# M07 reference journey — C1-LOOP-M02-v1

## 1. Summary

Case `C1-LOOP-M02-v1`, decision SPEC-S3-T on [653.15, 693.15] K, objective `c1-obj-nh3-liquid-v1` (mol/s, maximized).
The journey's decision: T_in = 653.1500351610193 K, `refined`, bound activity INTERIOR.

Limitations stated by this record:

- `R2:SURROGATE_NOT_PROMOTABLE`: R2 is SURROGATE_NOT_PROMOTABLE: M04's verdict for the bound parent is NOT_PROMOTABLE (band_not_finite); no surrogate evaluation was made.
- `bound:R1`: R1: The decision lies at the lower bound of the reactor model's registered domain (653.15 K, R-315). The objective may improve beyond it; no model in this journey is registered there, and nothing is claimed about it.

## 2. Case and decision

- Case: `C1-LOOP-M02-v1`
- Loop `real`: `benchmarks/m02/c1-loop-real.json` sha256 `cb907173780e988aad12a44e6cf85a37a10641b8e0aa73769d3e1c8505695174`
- Loop `standin`: `benchmarks/m02/c1-loop-standin.json` sha256 `51152d15dd55600fa603d4ad5f39cd5eed647b1ccd183324bbf3f456287aae71`
- Decision: SPEC-S3-T, box [653.15, 693.15] K, nominal 673.15 K, decision tolerance 0.5 K
- Parent: `c1.reactor` `pymrm-6089593-g2-nz800-s123-v3` sha256 `8b92540adc772a454e212b7054a98da4f7995899955a43a54d07669a70aa203c`

## 3. Rungs and their decisions

- R0: outcome `INDIFFERENT`, decision 673.15 K, bound activity INTERIOR
- R1: outcome `DECIDED`, decision 653.15 K, bound activity BOUND_LOWER
- R2: outcome `SURROGATE_NOT_PROMOTABLE`, decision — K, bound activity —
- R3: outcome `DECISION_STABLE`, decision 653.1500351610193 K, bound activity INTERIOR
- R2 reads M04's verdict `NOT_PROMOTABLE` for `m04q7-pymrm-6089593-g2-nz800-s123-v3-b2-it1`, reasons `band_not_finite`; record `benchmarks/m04/wo11-b2-it1-v3/manifest.json` sha256 `d65bb0225f36780cebe63c211b7706aa42613ef8edc4714218b1ddec58be1717`; surrogate evaluations 0.
- R3 study status `DECISION_STABLE`; record `benchmarks/m07/journey/1623633db5afd6a55e2807f848ad4cf6a84e71b3/m05/trust-region-study-real.json` sha256 `8e795c01645e627af1325839f67a68e31a08395ff464cd39ca946004f7b68d35` (carried from rerun); candidate T* = 653.1500351610193 K, status `PARENT_LOCAL_EVIDENCE`, J* = 0.4524965242483627 mol/s, e* = 1.85395193012364e-06 mol/s.
- R1: The decision lies at the lower bound of the reactor model's registered domain (653.15 K, R-315). The objective may improve beyond it; no model in this journey is registered there, and nothing is claimed about it.

## 4. The grid comparison

| T (K) | J R0 (mol/s) | J R1 (mol/s) | e R1 (mol/s) | J R0 − J R1 | relative | X_pass R1 | Q preheater R1 (W) | Q flash R1 (W) | recycle R1 (mol/s) | purge NH3 R1 (mol/s) | extrapolated R1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 653.15 | 0.4670595849251301 | 0.45249653242215776 | 1.8584736226293888e-06 | 0.014563052502972351 | 0.032183788072403866 | 0.17915625041804964 | 66076.48475723989 | -89630.61183034228 | 4.496475451865026 | 0.0032421300155814005 | 0 |
| 658.15 | 0.46705958492513017 | 0.4517660385569772 | 2.0172174278828334e-06 | 0.015293546368152944 | 0.03385280225358088 | 0.17656773646080334 | 67780.23017530216 | -90891.45487462854 | 4.565698492834906 | 0.0032904026241086922 | 0 |
| 663.15 | 0.4670595849251301 | 0.4509970651662342 | 2.130994422134794e-06 | 0.016062519758895888 | 0.035615574910615795 | 0.17391444517563795 | 69551.07663089513 | -92220.71373743357 | 4.63856788502746 | 0.003341218952685586 | 1 |
| 668.15 | 0.4670595849251301 | 0.45018521455134886 | 2.3129542364822804e-06 | 0.016874370373781256 | 0.037483173210382144 | 0.17118969464052441 | 71395.98058784014 | -93626.28120790598 | 4.715500357889517 | 0.0033948697158833695 | 1 |
| 673.15 | 0.46705958492513017 | 0.4493259489134928 | 2.7362344749387417e-06 | 0.017733636011637355 | 0.039467197597910265 | 0.16838783124946866 | 73322.32445795691 | -95116.3614515672 | 4.796925916180313 | 0.0034516549040283623 | 0 |
| 678.15 | 0.46705958492513017 | 0.44840928033094013 | 4.249733741514625e-06 | 0.018650304594190037 | 0.0415921467558065 | 0.1654877478483562 | 75344.43601386942 | -96708.90176402639 | 4.883791026787794 | 0.003512234709796899 | 0 |
| 683.15 | 0.46705958492513017 | 0.4474420876904195 | 3.4014887939588737e-07 | 0.01961749723471068 | 0.04384365658575199 | 0.16252288096003023 | 77456.30443458485 | -98391.85417517774 | 4.975443827853015 | 0.0035761546629773755 | 1 |
| 688.15 | 0.4670595849251301 | 0.4464092508301251 | 1.7852787585727607e-08 | 0.020650334095004996 | 0.046258750365509776 | 0.15945946095802896 | 79679.12633621853 | -100192.47841633974 | 5.073317124325032 | 0.0036444141698509297 | 0 |
| 693.15 | 0.4670595849251301 | 0.4453069553640254 | 5.369826897031689e-08 | 0.021752629561104686 | 0.04884861846211799 | 0.1563012256695307 | 82020.62759076866 | -102117.93050729309 | 5.177772365254235 | 0.0037172654912508173 | 1 |

Verification status per point (outcome / certificate): 653.15 R0 CONVERGED/VERIFIED; 658.15 R0 CONVERGED/VERIFIED; 663.15 R0 CONVERGED/VERIFIED; 668.15 R0 CONVERGED/VERIFIED; 673.15 R0 CONVERGED/VERIFIED; 678.15 R0 CONVERGED/VERIFIED; 683.15 R0 CONVERGED/VERIFIED; 688.15 R0 CONVERGED/VERIFIED; 693.15 R0 CONVERGED/VERIFIED; 653.15 R1 CONVERGED/VERIFIED; 658.15 R1 CONVERGED/VERIFIED; 663.15 R1 CONVERGED/VERIFIED; 668.15 R1 CONVERGED/VERIFIED; 673.15 R1 CONVERGED/VERIFIED; 678.15 R1 CONVERGED/VERIFIED; 683.15 R1 CONVERGED/VERIFIED; 688.15 R1 CONVERGED/VERIFIED; 693.15 R1 CONVERGED/VERIFIED.

## 5. Surrogate discrepancy

No surrogate evaluation: R2 is `SURROGATE_NOT_PROMOTABLE` (M04 verdict `NOT_PROMOTABLE`).

## 6. Refinement

| pair | t_before | t_after | j_before | j_after | e_before | e_after | class | missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P01 | 673.15 | 653.15 | 0.4493259489134928 | 0.45249653242215776 | 2.7362344749387417e-06 | 1.8584736226293888e-06 | `FE_CHANGED` | — |
| P13 | 653.15 | 653.1500351610193 | 0.45249653242215776 | 0.4524965242483627 | 1.8584736226293888e-06 | 1.85395193012364e-06 | `FE_UNCHANGED` | — |

## 7. Truth checks

TC-1: `TC1_HOLDS`; best verified parent grid point 653.15 K.
- R0: grid_point, run sha256 `2e679ecaafcefbb7c71a32dbb55c8588cb6e3eceae5daadc1f9efdc1823f90ad`, constraints evaluated.
- R1: grid_point, run sha256 `e792e5bac4ad93c684c0be9b01046edcb67c8c66bf8dae72a6854ed23ecb4194`, constraints evaluated.
- R3: targeted_check, run sha256 `7cc6dd23f4fee8deb79ec5cb39416bef535e581c4ee4e928801f60937e80479b`, constraints evaluated.
- journey: targeted_check, run sha256 `7cc6dd23f4fee8deb79ec5cb39416bef535e581c4ee4e928801f60937e80479b`, constraints evaluated.

## 8. Uncertainty

Indifference set (R1): [653.15].
R3 noise floor e* = 1.85395193012364e-06 mol/s; indifference half-width — K.
Relative to the parent at its design grid (num_z = 800), whose NH3 output is estimated 1.0-1.4 % high (M01 §10.5); an estimate, not a bound.

## 9. Compute cost

| rung | cold reactor experiments | budget | wall (s) | budget (s) | experiments (cold / in-process / store hit) | exhausted |
| --- | --- | --- | --- | --- | --- | --- |
| R0 | 0 | 0 | 2.784435696026776 | 600.0 | 0 / 18 / 0 | no |
| R1 | 36 | 60 | 1557.4403980499628 | 5400.0 | 36 / 0 / 0 | no |
| R2 | 0 | 0 | 0.0 | 1200.0 | 0 / 0 / 0 | no |
| R3 | 48 | 400 | 1458.2779236859933 | 14400.0 | 48 / 0 / 0 | no |
| R3 re-solve at T* | 4 | — | 294.06272135299514 | — | 4 / 0 / 0 | — |
| journey | 88 | 460 | 3312.565478784978 | 21600.0 | | |

## 10. Verification, validation and optimality, kept apart

- Verification: every reported J is a certified coupled loop solve (outcome CONVERGED, certificate VERIFIED) of a registered test configuration; the labels are recomputed by `check` from the record's numbers.
- Validation: none. No number here is compared with plant or experimental data.
- Optimality: none claimed. The grid and the study give local evidence on the box only.

## 11. What this journey does not establish

1. No empirical validation: no number in this journey is compared with plant or experimental data.
2. Not a plant design: C1-LOOP-M02-v1 is a registered test configuration.
3. No global optimality.
4. Nothing is claimed for reactor inlet temperatures outside 653.15-693.15 K, the reactor model's registered domain.
5. Relative to the parent at its design grid (num_z = 800), whose NH3 output is estimated 1.0-1.4 % high (M01 §10.5); an estimate, not a bound.
6. The simple rung is synthetic (fixed per-pass N2 conversion 0.25, no temperature rise) and certifies nothing about the reactor.
7. Reactor results flagged extrapolated (R-169) are counted, not excluded.
8. No surrogate coverage claim at any operating point; the band-containment counts are not a coverage estimate.
9. The K_NH3 enthalpy term rests on Frank's decision (R-152); its check against Rossetti et al. 2006 was not made.
10. No reproduction of the reactor results on another architecture.
11. No pressure-drop or selectivity comparison: zero pressure drop by convention (ADR 0022 D2), one reaction.
12. No equilibrium-reactor rung: this journey does not show what an equilibrium model would decide.
13. No sensitivities of the decision: the coupled route refuses them (ADR 0031 C3); the poll's curvature is reported only.

## 12. Provenance and replay

- Record schema `m07-journey-v1`; commit `1623633db5afd6a55e2807f848ad4cf6a84e71b3`
- Registration sha256 `0fbcd73f00cf804b9a52ca9690c8690e3895717f425d964fa4fc8311500c1005`
- Environment: lock `ead4edf1ea3577287a7576d56a9e5db550e5a5be459dd634b10806fdc655b9c4`, reactor lock `032a050c6cf39e1eb2f01ebf03ea92a386f99967cb7fd0797c54431a33a60288`, Linux-x86_64-py3.13.5, tree clean yes, OMP_NUM_THREADS 1
- M05 record `benchmarks/m07/journey/1623633db5afd6a55e2807f848ad4cf6a84e71b3/m05/trust-region-study-real.json`, sha256 `8e795c01645e627af1325839f67a68e31a08395ff464cd39ca946004f7b68d35`, carried from `rerun`
- Synthetic dry run: no
- Replay: `python scripts/m07_journey.py replay <dir>`; check: `… check <dir>`.
