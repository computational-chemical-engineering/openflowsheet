"""The revision builder of `syn001.column` (S11 design note §4.7.1, §4.7.2; WO-B2).

`_COLUMN` is the model's signature and `build_column` its builder, in the `Builder` shape of
`revision_binding`. They are registered in `MODEL_BUILDERS`/`MODEL_SIGNATURES` by I1, not here;
until then a test registers the builder in a monkeypatched table, as `test_m02_wo8_region` does.

The builder parses the instance (`column_unit.column_structure`), applies the structural items of
S02 §5 and S06 §5 at bind (`column_unit.structural_refusal`), and returns the unit with its
configuration: which end specification each end reads. It consumes no pin: the column's end
specifications are instance parameters `condenser_<kind>[.<attr>]`/`reboiler_<kind>[.<attr>]`
(§10.5, R-824; `column_unit.END_PARAMETERS`), so a pin routed to a column instance is left
unconsumed and refused by the binder.
"""

from __future__ import annotations

from typing import Final

from openflowsheet.application.revision_binding import Configuration, ModelSignature
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import UnitModel
from openflowsheet.models.revision_flowsheet import InstanceView
from openflowsheet.models.syn001.column import CONDENSER, MODEL_ID, REBOILER, EndSpecification
from openflowsheet.models.syn001.column_unit import (
    PORTS,
    STAGE_COUNT,
    ColumnUnit,
    column_staged_splits,
    column_structure,
    structural_refusal,
)
from openflowsheet.thermo import PropertyProvider

#: The column's signature (§4.7.1). Its end specifications are not `PinColumn`s (a pin is a
#: stream quantity or a duty), so the signature names its one fixed parameter and no choice; the
#: rest is `column_unit`'s to read and refuse. Its optional parameters — `stage_pressure.<j>`,
#: `stage_duty.<j>`, `feed_stage.<stream>` and the twelve end parameters `END_PARAMETERS`
#: (§10.5) — have no `ModelSignature` field to be listed in (build decision,
#: `docs/S11B_DECISIONS.md`).
_COLUMN: Final = ModelSignature(model_id=MODEL_ID, ports=PORTS, required=(STAGE_COUNT,))


def _label(end: str, given: EndSpecification | None) -> str | None:
    """The configuration label of an end: the parameter that specifies it, or `None`."""
    if given is None:
        return None
    attribute = given.component if given.component is not None else given.stage
    return f"{end}_{given.kind}" + ("" if attribute is None else f".{attribute}")


def build_column(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """§4.7.1–§4.7.2: the column instance, or the typed refusal of its structure."""
    structure = column_structure(view, components)
    structural_refusal(structure, provider)
    unit = ColumnUnit(
        unit_id=view.unit_id,
        structure=structure,
        provider=provider,
        context=context,
        staged=column_staged_splits(structure),
    )
    configuration = {
        CONDENSER: _label(CONDENSER, structure.condenser_spec),
        REBOILER: _label(REBOILER, structure.reboiler_spec),
    }
    return unit, configuration
