"""Sizing models per unit family (E01 design §4.4; ADR 0052 D3).

A *family* turns one host unit into its costable *items* (§4.4.0): the `size.<item>.<q>` outputs
(each a functional of the solved state), the θ its inputs become (`asm:item.<item>.<input>`), the
volumetric-flow blocks it needs (§4.4.3), its regime entries (service, utility, approach, argmax,
dormant; §4.3.1), and its refusals and limitations. The `size` regime of an item belongs to the
cost entry that prices it (WO-A3/A4), which reads `SizedItem`.

`FAMILIES` maps a host model id to its family; `register_family` is the extension point for later
unit packages. The model ids, ports and variable ids the families read are those of the model
registry (verified by WO-A2, recorded in `docs/E01A_DECISIONS.md`).

Every choice is made on floats at the planning state (`SizingContext.value`) or taken from the
held regime, and handed to the builders as data: a builder never branches on a symbol (§4.2.2).
"""

from __future__ import annotations

from collections.abc import Mapping

from openflowsheet.assessment.linearization import Refusal
from openflowsheet.assessment.program import BuildContext, FunctionalBuilder
from openflowsheet.assessment.sizing.core import FAMILIES as FAMILIES
from openflowsheet.assessment.sizing.core import GRAVITY as GRAVITY
from openflowsheet.assessment.sizing.core import LIQUID_VOLUME_THETA as LIQUID_VOLUME_THETA
from openflowsheet.assessment.sizing.core import Family as Family
from openflowsheet.assessment.sizing.core import ItemFamily as ItemFamily
from openflowsheet.assessment.sizing.core import SizedItem as SizedItem
from openflowsheet.assessment.sizing.core import SizingContext as SizingContext
from openflowsheet.assessment.sizing.core import SizingInput as SizingInput
from openflowsheet.assessment.sizing.core import SizingPlan as SizingPlan
from openflowsheet.assessment.sizing.core import StreamFlow as StreamFlow
from openflowsheet.assessment.sizing.core import argmax_rows as argmax_rows
from openflowsheet.assessment.sizing.core import nominal as nominal
from openflowsheet.assessment.sizing.core import register_family as register_family
from openflowsheet.assessment.sizing.core import size_output as size_output
from openflowsheet.assessment.sizing.core import sub_item as sub_item

__all__ = [
    "FAMILIES",
    "GRAVITY",
    "LIQUID_VOLUME_THETA",
    "Family",
    "ItemFamily",
    "SizedItem",
    "SizingContext",
    "SizingInput",
    "SizingPlan",
    "StreamFlow",
    "argmax_rows",
    "family_of",
    "nominal",
    "plan_sizing",
    "register_family",
    "size_output",
    "sub_item",
]


def family_of(model_id: str) -> Family | None:
    _load_builtin()
    return FAMILIES.get(model_id)


_LOADED: list[bool] = []


def _load_builtin() -> None:
    if not _LOADED:
        from openflowsheet.assessment.sizing import families  # noqa: F401, PLC0415

        _LOADED.append(True)


def plan_sizing(
    ctx: BuildContext,
    state: Mapping[str, float],
    *,
    families: Mapping[str, Family] | None = None,
) -> tuple[SizingPlan, SizingContext]:
    """Every unit's items, in the host's unit declaration order (§4.2.4 step 1).

    A unit whose model id no family covers is refused `NO_SIZING_MODEL(<U>)` unless its item
    carries a `quote` or `exclude` (the cost contributor reads those, §4.4.0)."""
    _load_builtin()
    table = FAMILIES if families is None else families
    sctx = SizingContext(ctx, state)
    plan = SizingPlan()
    for unit in ctx.view.units():
        family = table.get(unit.model_id)
        if family is None:
            doc = sctx.item(unit.unit_id)
            if "quote" in doc or "exclude" in doc:
                continue
            plan = plan.merged(
                SizingPlan(
                    refusals=(Refusal("NO_SIZING_MODEL", unit.unit_id, unit.model_id),),
                )
            )
            continue
        plan = plan.merged(family.plan(sctx, unit))
    return SizingPlan(
        items=plan.items,
        outputs=plan.outputs,
        theta=(*plan.theta, *sctx.document_theta),
        blocks=sctx.blocks,
        regime_entries=plan.regime_entries,
        refusals=plan.refusals,
        limitations=plan.limitations,
        no_equipment=plan.no_equipment,
    ), sctx


#: `(symbols, algebra) -> constant` builder.
def constant(value: float) -> FunctionalBuilder:
    return lambda s, a: value
