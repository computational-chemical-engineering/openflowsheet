# Distillation column

`syn001.column` is a countercurrent equilibrium-stage column with a total condenser and a partial
reboiler, solved by Newton's method on the stage equations (MESH) as one unit of the flowsheet. It
binds on the SYN-001 and Wilson bases. The
[methanol–water example](../examples/methanol-water-column.ipynb) solves one.

## Ports

| Port | Direction | Use |
| --- | --- | --- |
| `feed` | inlet, one or more | side feeds, each on its own stage |
| `top`, `bottom` | inlet | optional end feeds (a stripping or absorption section) |
| `distillate`, `bottoms` | outlet | the products |

## Parameters

| Parameter | Meaning |
| --- | --- |
| `stage_count` | number of equilibrium stages, counted from the top |
| `feed_stage.<connection id>` | the stage each side feed enters |
| `stage_pressure.<k>` | the pressure of stage `k`, for every stage |
| one `condenser_<kind>` | `condenser_reflux_ratio`, `condenser_distillate_rate`, `condenser_duty`, or (SYN-001 only) `condenser_purity.<component>`, `condenser_recovery.<component>`, `condenser_temperature.<stage>` |
| one `reboiler_<kind>` | `reboiler_boilup_ratio`, `reboiler_bottoms_rate`, `reboiler_duty`, or (SYN-001 only) the same three inverse kinds |

The end specifications are instance parameters, so a change set edits them like any other
parameter. Two specifications for one end are refused `specification_conflict`; an end
specification not offered (for example a mole fraction or a reflux rate) is refused by name.

## What the column does not do

- No side draws, pump-arounds, stage efficiencies or hydraulics; no inside-out or rate-based
  method.
- A total condenser returns saturated liquid (no subcooling); there is no total reboiler.
- Side feeds are single-phase and declared, one per stage.
- On the Wilson basis, purity, recovery and temperature ends are refused at binding.
- No uniqueness or multiplicity claim: a certificate holds at the converged state.
- A column under the PTC policy (`T08-ptc-v1`) is refused before any attempt.

SYN-001 columns are synthetic, so their results are verified, never validated. Columns were
compared blind with IDAES, DWSIM and BioSTEAM on shared cases; those tools share the equations, so
the agreement is verification too.
