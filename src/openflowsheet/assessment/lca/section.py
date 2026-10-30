"""The LCA report section and the `lca` contributor (E01 design §4.2.2, §4.8, §4.8.6, §4.11).

The contributor runs after `cost` (§4.2.2): it resolves the tables, plans the inventory
(`inventory.<k>.rate`) and the impacts (`impact.<m>.rate|annual|per_fu`), and returns its section:
the tables it used, each as `{id, sha256, rights}` only (`tables.reference`), so a table whose
rights forbid redistribution never puts a score into a report (§4.8.6). The report's
`lca.inventory` and `lca.impacts` rows are the outputs themselves (`report.py`).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from openflowsheet.assessment.lca.impact import categories_of, plan_impacts
from openflowsheet.assessment.lca.inventory import plan_inventory
from openflowsheet.assessment.lca.tables import LcaTable, reference, resolve_tables
from openflowsheet.assessment.program import (
    BuildContext,
    ContributionPlan,
    OutputDef,
    declared_sections,
    register_contributor,
)

__all__ = ["LcaContributor", "lca_section"]


def lca_section(
    tables: Mapping[str, LcaTable],
    defaulted: list[dict[str, Any]],
    restricted: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The section: `tables` (id, sha256, rights; never a score), `defaulted_inputs`, and
    `restricted_theta` (θ id → reason) — the θ whose values the report withholds (§4.8.6)."""
    return {
        "tables": [reference(table) for table in tables.values()],
        "defaulted_inputs": list(defaulted),
        "restricted_theta": dict(restricted or {}),
    }


class LcaContributor:
    """The `lca` contributor (§4.2.2)."""

    name = "lca"

    def plan(self, ctx: BuildContext, state: Mapping[str, float]) -> ContributionPlan:
        document = ctx.spec.document
        if "lca" not in declared_sections(document):
            return ContributionPlan()
        tables, refused = resolve_tables(document)
        inventory = plan_inventory(ctx, state, tables, refused)
        impacts = plan_impacts(ctx, state, inventory, tables, categories_of(document, tables))
        outputs = [OutputDef(e.output_id, e.unit, e.build) for e in inventory.exchanges]
        section = lca_section(tables, impacts.defaulted, impacts.restricted)
        listed_refusals = {r.target for r in inventory.refusals}
        refusals = [
            *inventory.refusals,
            *impacts.refusals,
            # A refused table no exchange names is still reported once.
            *(r for t, r in refused.items() if not any(x.startswith(t) for x in listed_refusals)),
        ]
        return ContributionPlan(
            outputs=(*outputs, *impacts.outputs),
            theta=(*inventory.theta, *impacts.theta),
            refusals=tuple(refusals),
            limitations=(*inventory.limitations, *impacts.limitations),
            section=lambda values: section,
            unavailable=tuple(impacts.unavailable),
        )


register_contributor("lca", LcaContributor)
