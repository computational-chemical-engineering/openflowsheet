"""Row shapes of the `thermal.*` units that `models.rows` does not have (S11 units design §4.4).

`models.rows` may gain functions only through track B until B merges (S11 design §10.7, R-826);
the thermal family's own shapes live here. Like `models.rows`, every builder is a closure over
ids, never over values, and a balance row is `inflow - outflow` (ADR 0008 D3.3).
"""

from __future__ import annotations

from collections.abc import Mapping

from openflowsheet.compile.spec import Algebra, Expr, RowBuilder

__all__ = [
    "expansion_work_row",
    "quality_row",
    "saturation_temperature_row",
    "vanishing_row",
]


def saturation_temperature_row(temperature: str, tsat_key: str) -> RowBuilder:
    """`sat-T`: `T_S - PFsat_<S>.Tsat`, a temperature variable against the saturated block."""

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        return variables[temperature] - blocks[tsat_key]

    return build


def quality_row(vapour: str, fraction: str, flows: tuple[str, ...]) -> RowBuilder:
    """`TH-quality`: `V - beta_spec sum(n)`, beta_spec a pinned input (kind `molar_flow`)."""
    if not flows:
        raise ValueError("a quality row needs the stream's flows")

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        total = variables[flows[0]]
        for name in flows[1:]:
            total = total + variables[name]
        return variables[vapour] - parameters[fraction] * total

    return build


def vanishing_row(variable: str) -> RowBuilder:
    """`sat-fix`: a carried flow fixed at zero (the drum's vapour product carries no liquid)."""

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        return variables[variable]

    return build


def expansion_work_row(
    work: str, efficiency: str, isentropic_key: str, base_keys: tuple[str, ...]
) -> RowBuilder:
    """`TTU-work`: `W - eta (Hs - sum(base))`, the turbine's work (W < 0) against its ideal work.

    The expansion counterpart of `models.rows.work_row`, whose efficiency divides the ideal work.
    """
    if not base_keys:
        raise ValueError("an expansion work row needs the inlet's enthalpy terms")

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        base = blocks[base_keys[0]]
        for key in base_keys[1:]:
            base = base + blocks[key]
        return variables[work] - parameters[efficiency] * (blocks[isentropic_key] - base)

    return build
