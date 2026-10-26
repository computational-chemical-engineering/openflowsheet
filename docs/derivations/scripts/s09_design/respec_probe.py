"""S09 design probe (NOT evidence): the single-specification initializer overwrite and the two ways
to re-specify.

Non-registered refluxed absorber A1 of floor_probe.py (N = 4, vapour feed (0.25, 0.45, 0.30)
mol/s at 390 K on the bottom stage, partial condenser, Reflux 1, no reboiler). Pass 1 is the
tool's first simulate(); the initializer (biosteam/units/stage.py:3273-3298) overwrites a single
Reflux/Boilup specification. Pass 2 re-specifies either (a) through
StageEquilibrium.specify_variables(Reflux=1, P=P_r, wt=False), the constructor's call, or (b) by
re-storing stage.B = 1/Reflux through the attribute setter, then simulates again.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import floor_probe as fp  # noqa: E402

p = fp.PROBES["A1"]
sv = {0: ("Reflux", 1.0)}
for rung in (fp.RUNGS[1], fp.RUNGS[3]):
    for how in ("specify_variables", "attribute_setter"):
        col = fp.build(p, rung, 1e-10, sv)
        col.simulate()
        b1 = col.stages[0].B
        if how == "specify_variables":
            col.stages[0].specify_variables(Reflux=1.0, P=fp.P_R, wt=False)
        else:
            col.stages[0].B = 1.0
        b_set = col.stages[0].B
        col.simulate()
        r = fp.residuals(col)
        v1 = col.stages[0].partition.outs[0].F_mol / fp.K
        l1 = col.stages[0].partition.outs[1].F_mol / fp.K
        print(
            f"{rung[0]:<20} {how:<18} pass1 B {b1:.12g} | set B {b_set:.12g} | pass2 B "
            f"{col.stages[0].B:.12g} "
            f"L1/V1 {l1 / v1:.12g} V1 {v1:.12g} | adiabatic {r['adiabatic_W']:.3e} W "
            f"equilibrium {r['equilibrium']:.3e} stage balance {r['stage_component_mol_s']:.3e}"
        )
