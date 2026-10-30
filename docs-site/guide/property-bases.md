# Property bases

A revision's `component_set.record_source` selects one property basis; every stream and unit of
the revision evaluates on it, and streams of different bases never mix. Any value that is not a
registered key selects the synthetic SYN-001 basis, whose components are then the only ones
accepted.

| Basis | `record_source` | Components | Domain | Units that bind |
| --- | --- | --- | --- | --- |
| IAPWS-95 water (`iapws95-v1`) | `benchmarks/s05/components.yaml` | `H2O` | 273.16–1273.15 K, 10²–10⁸ Pa | `thermal.*`, routing models |
| CoolProp HEOS (`coolprop-heos-v1`) | `benchmarks/s07/components.yaml` | exactly one of 123 fluids | per fluid | `thermal.*`, routing models |
| Wilson γ–φ (`wilson-ig-v2`) | `benchmarks/s10/records.yaml` | `CH3OH`, `C2H5OH`, `H2O` | 300–400 K, 30–200 kPa | the column, five mixture units, the compressor and turbine, routing models |
| Peng–Robinson C1 (`pr-c1-v1`) | `benchmarks/m01/components.yaml` | `H2`, `N2`, `NH3`, `Ar`, `CH4` | 200–1000 K, 10⁴–3 × 10⁷ Pa | `c1.*` |
| SYN-001 (`syn001`) | any other value | `A`, `B`, `C` (synthetic) | 280–440 K, 50–200 kPa | `syn001.*` |

The [unit catalogue](units.md) lists, for every model, the bases it binds on. A model on a basis it
does not support is refused at binding, with the reason (`model_unsupported(thermal.pump)`:
the Wilson basis has no liquid volume, which a pump needs).

## IAPWS-95 water (`iapws95-v1`)

The IAPWS-95 formulation for ordinary water, implemented from the release's coefficients (IAPWS's
attribution is in [Licence and attributions](../licence.md)). Its reference state is the
formulation's own — internal energy and entropy zero for the saturated liquid at the triple point —
which is not a formation datum, so no reacting unit can be built on it. Stream regimes are declared
(`liquid`, `vapor`, or `vapor_liquid` for saturated states); saturated streams are produced only
by `thermal.*` units, and there is no phase-regime discovery. Close to the critical point the
near-critical rules of the provider apply.

## CoolProp pure fluids (`coolprop-heos-v1`)

CoolProp's Helmholtz-energy equations of state, one fluid per revision, named as the revision's
one component (for example `R134a`, `CO2`, `Nitrogen`). Needs the `coolprop` extra; the provider
imports CoolProp only when a revision selects it. Each fluid keeps its own domain and the
qualification tier it was admitted under. The `thermal.*` units' rules are those of IAPWS-95
above.

## Wilson activity model (`wilson-ig-v2`)

The Wilson activity-coefficient model for the liquid with an ideal-gas vapour (γ–φ), for methanol,
ethanol and water, with TP and PH flashes and molar entropy. Its records hold fitted binary
parameters and the measured points they were fitted to. Compared with measured vapour–liquid
equilibrium, it is within its pre-registered bands for methanol–ethanol–water (the ternary at
101.3 kPa; the binaries with water at 323–333 K); methanol's liquid enthalpy and heat capacity are
**not** within band against CoolProp. That comparison is the
[validation report](https://github.com/computational-chemical-engineering/openflowsheet/blob/main/docs/s10-validation-report.md).
On this basis the column takes reflux, rate and duty end specifications only, and the compressor
and turbine are single-phase vapour machines. The records are read from a source checkout of the
repository.

## Peng–Robinson for the ammonia loop (`pr-c1-v1`)

The Peng–Robinson route of the ammonia-synthesis loop: hydrogen, nitrogen, ammonia, argon and
methane, vapour only, with binary interaction parameters zero. It is validated for pure-component
behaviour only, with no mixture VLE validation; a liquid regime is reported unsupported. It binds
the `c1.*` models, including the PyMRM reactor, which runs out of process in its own pinned
environment.

## SYN-001 (`syn001`)

A synthetic three-component system (ideal vapour, incompressible ideal liquid, vapour–liquid
equilibrium) with closed-form references, used to verify the numerics. Its results are verified,
never validated: the components have no real chemical identity.
