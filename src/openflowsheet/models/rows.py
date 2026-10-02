"""The row shapes every SYN-001 unit is built from, written once.

Six of these were duplicated across two to four unit modules, and the Fable review of K02 found
a defect that hid behind exactly that: the heater's equilibrium row was never evaluated at a
state where it could fail, and its near-identical twin in the flash was, so a reader comparing
the two saw agreement and moved on. A shape defined once is a shape with one place to test.

**Every builder here is a closure over ids, not over values.** It is called at assembly time and
returns a `RowBuilder` that the compiler traces symbolically and that
`openflowsheet.compile.reference` evaluates on floats. Nothing here knows a number.

**The orientation of a balance row is ADR 0008 D3.3's**: `inflow - outflow + sources`, so that
`d(holdup)/dt = +F_row`. The steady-state content does not depend on the sign but the Jacobian
row does, which is why it is fixed in one place rather than re-derived per unit.
"""

from __future__ import annotations

from collections.abc import Mapping

from openflowsheet.compile.spec import Algebra, Expr, RowBuilder

__all__ = [
    "balance_row",
    "cooling_row",
    "definition_row",
    "energy_row",
    "equilibrium_row",
    "extent_row",
    "kinetic_balance_row",
    "offset_row",
    "reaction_balance_row",
    "scaled_row",
    "specification_row",
    "work_row",
]


def balance_row(inflow: tuple[str, ...], outflow: tuple[str, ...]) -> RowBuilder:
    """`sum(inflow) - sum(outflow)` over free variables — ADR 0008 D3.3's orientation.

    Used for every conservation row, and for the plain two-term differences that are the same
    arithmetic: a splitter copying a temperature, a mixer equating pressures, a lifted split
    accounting for its whole stream.
    """
    if not inflow:
        raise ValueError("a balance row needs at least one inflow term")

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        accumulated = variables[inflow[0]]
        for name in inflow[1:]:
            accumulated = accumulated + variables[name]
        for name in outflow:
            accumulated = accumulated - variables[name]
        return accumulated

    return build


def definition_row(defined: str, parts: tuple[str, ...]) -> RowBuilder:
    """`defined - sum(parts)`: a lifting row that gives a name to a sum, P02's `Vdef`/`Ldef`.

    Arithmetically a `balance_row`, and deliberately a separate name: it conserves nothing, it
    defines something, and ADR 0008 D4.4 requires a self-authored row to be declared `algebraic`
    rather than inheriting a balance kind by resemblance.
    """
    return balance_row((defined,), parts)


def specification_row(variable: str, parameter: str) -> RowBuilder:
    """`variable - parameter`: a free variable pinned to a specification.

    The specification is a *pinned input* (ADR 0008 D1.3), so it arrives through `parameters` and
    is covered by `constants_sha256`, never as a literal baked into the expression.
    """

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        return variables[variable] - parameters[parameter]

    return build


def offset_row(outlet: str, inlet: str, offset: str) -> RowBuilder:
    """`outlet - inlet + offset`, the shape of a declared pressure drop.

    ADR 0001 D4.5: a unit with zero declared drop copies its inlet pressure as an *equation*, not
    as an assumption baked into the state, so the row exists even when the offset is zero.
    """

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        return variables[outlet] - variables[inlet] + parameters[offset]

    return build


def scaled_row(outlet: str, inlet: str, fraction: str, *, complement: bool) -> RowBuilder:
    """`outlet - r inlet`, or `outlet - (1 - r) inlet` when `complement`.

    The splitter's two rows. The complement is formed here rather than pinned as a second
    parameter because `SPLIT-purge` declares its dependency as `parameters.split_fraction`: there
    is one pinned input, and `1 - r` is arithmetic on it.
    """

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        factor = parameters[fraction]
        if complement:
            factor = 1.0 - factor
        return variables[outlet] - factor * variables[inlet]

    return build


def equilibrium_row(
    vapor: str, liquid: str, total_vapor: str, total_liquid: str, ln_k_key: str
) -> RowBuilder:
    """`v_i L - K_i l_i V`, with `K_i = exp(lnK_i)` from a property block.

    The division-free form of `y_i = K_i x_i`, which ADR 0001 D3.2 requires because a
    mole-fraction form divides by a total flow. Exact at an absent component and at a vanished
    phase — and, for the same reason, satisfied identically by the trivial splits `V = 0` and
    `L = 0`, which no residual can exclude and which K03 must reject by other means (see
    `tp_state`'s note and `tests/test_k02_flowsheet.py`).
    """

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        k_value = algebra.exp(blocks[ln_k_key])
        return (
            variables[vapor] * variables[total_liquid]
            - k_value * variables[liquid] * variables[total_vapor]
        )

    return build


def energy_row(
    inflow_keys: tuple[str, ...],
    outflow_keys: tuple[str, ...],
    *,
    source: str | None = None,
    sink: str | None = None,
) -> RowBuilder:
    """`source + sum(inflow enthalpies) - sum(outflow enthalpies)`, over *block outputs*.

    `source` is a duty variable where the unit has one and `None` where it is adiabatic; ADR 0001
    D4.1 makes a duty positive into the unit, so it enters with `+`. The enthalpies are block
    outputs rather than variables because an enthalpy flow is a property, and a block is what
    carries a declared-sparse derivative for one.

    `sink` is the other sign, for a heat that *leaves* the balanced contents: T05's exchanger
    writes its hot side as `-Q + Hdot_hot_in - Hdot_hot_out`, `Q` the heat moved to the cold side
    (T05 spec §10.1). A row has a source or a sink, not both. With `sink=None` the builder is the
    one K02's units have always used, term for term.

    The accumulation order — source (or sink) first, then each inflow, then each outflow, left to
    right — is fixed, not incidental. Floating-point addition does not associate, so a reordering
    here would change the last bits of every duty row, and this module was introduced as an
    *inert* consolidation of builders that already existed.
    """
    if source is not None and sink is not None:
        raise ValueError("an energy row takes a source or a sink, not both")
    if not inflow_keys and source is None and sink is None:
        raise ValueError("an energy row with no inflow and no source has nothing to balance")

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        if source is not None:
            accumulated = variables[source]
            remaining = inflow_keys
        elif sink is not None:
            accumulated = -variables[sink]
            remaining = inflow_keys
        else:
            accumulated = blocks[inflow_keys[0]]
            remaining = inflow_keys[1:]
        for key in remaining:
            accumulated = accumulated + blocks[key]
        for key in outflow_keys:
            accumulated = accumulated - blocks[key]
        return accumulated

    return build


def work_row(
    work: str, efficiency: str, raised_keys: tuple[str, ...], base_keys: tuple[str, ...]
) -> RowBuilder:
    """`eta W - [sum(raised) - sum(base)]`: a machine's shaft work against its ideal work.

    T05's `PUMP-work` (spec §9.1): `eta W - [Hdot^L(n_in, T_in, P_out) - Hdot^L(n_in, T_in, P_in)]`,
    with `W` a free variable and `eta` a pinned input. `raised_keys` and `base_keys` are the two
    enthalpy blocks' outputs, **paired by component**, and the bracket is summed pair by pair:
    `(raised_i - base_i)` per component, then the sum. For SYN-001 the rise does not depend on
    `T_in` at all, and pairing makes its `T_in` partial cancel exactly per component instead of
    to within the rounding of two differently ordered sums (the one registered cancelling partial,
    spec §13.4).
    """
    if not raised_keys or len(raised_keys) != len(base_keys):
        raise ValueError("a work row pairs one raised and one base enthalpy term per component")

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        rise = blocks[raised_keys[0]] - blocks[base_keys[0]]
        for raised, base in zip(raised_keys[1:], base_keys[1:], strict=True):
            rise = rise + (blocks[raised] - blocks[base])
        return parameters[efficiency] * variables[work] - rise

    return build


def reaction_balance_row(inflow: str, coefficient: str, extent: str, outflow: str) -> RowBuilder:
    """`inflow + nu extent - outflow`: one component's balance across a reaction.

    T05's `RX-mole` (spec §6.2), ADR 0008 D3.3's orientation with the reaction as the source term:
    `n_in,i + nu_i xi - n_out,i`, with `xi` a free variable and `nu_i` a pinned input. The terms
    are accumulated in that order, the order the spec writes and its reference generator sums.
    """

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        return variables[inflow] + parameters[coefficient] * variables[extent] - variables[outflow]

    return build


def extent_row(extent: str, conversion: str, key_flow: str, key_coefficient: str) -> RowBuilder:
    """`xi - X n_in,k / (-nu_k)`: a reaction's extent fixed by the conversion of its key reactant.

    T05's `RX-conversion` (spec §6.2). `X` and `nu_k` are pinned inputs, `nu_k < 0` by the
    reactor's construction check. The product and quotient are formed in the order the causal
    evaluator forms the extent, `X * n_k / (-nu_k)`, so the row vanishes at the evaluator's
    answer to the last bit.
    """

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        return variables[extent] - parameters[conversion] * variables[key_flow] / (
            -parameters[key_coefficient]
        )

    return build


def kinetic_balance_row(
    inflow: str,
    outflow: str,
    coefficient: str,
    damkohler: str,
    temperature: str,
    reference_temperature: str,
    temperature_scale: str,
    key_flow: str,
) -> RowBuilder:
    """`inflow - outflow + nu r`, `r = Da exp((T - T_ref)/T_s) n_k`: a component across a CSTR.

    T08's `CSTR-mole` (build-first spec §A1.3): the rate is substituted, never owned (§A1.1 (4)),
    so the row is nonlinear in the outlet temperature and the key's outlet flow. `nu`, `Da`,
    `T_ref` and `T_s` are pinned inputs. The rate is formed `(Da * exp(.)) * n_k`, the order the
    causal evaluator forms it, and the terms are accumulated in the order the spec writes them.
    """

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        exponent = (variables[temperature] - parameters[reference_temperature]) / parameters[
            temperature_scale
        ]
        rate = parameters[damkohler] * algebra.exp(exponent) * variables[key_flow]
        return variables[inflow] - variables[outflow] + parameters[coefficient] * rate

    return build


def cooling_row(
    duty: str, coolant_flow: str, coolant_cp: str, coolant_temperature: str, temperature: str
) -> RowBuilder:
    """`Q - F_c c_c (T_c - T)`: the heat a coolant leaving at the vessel temperature removes.

    T08's `CSTR-cooling` (build-first spec §A1.3): the high-NTU limit of a coolant stream of
    capacity rate `F_c c_c`, all three pinned inputs. The capacity rate is formed first, as the
    causal evaluator forms it, so the row vanishes at the evaluator's answer to the last bit.
    """

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        capacity = parameters[coolant_flow] * parameters[coolant_cp]
        return variables[duty] - capacity * (
            parameters[coolant_temperature] - variables[temperature]
        )

    return build
