"""SYN-001 as a `ProblemSpec`: K01's conformance fixture, in the lifted form.

This is a **fixture, not a unit model.** Plan §1.3 gives unit-model implementation to K02; K01
delivers the compiler, and needs one real problem to demonstrate it on. Nothing here belongs in
`src/`, and K02 is free to arrive at a different structure for the production models.

**What is independent of what.** The block closed forms are imported from `benchmarks.p02.expected`,
which is backend-free and was written for P02. So the *values* a block returns share a source with
one of the things the conformance test compares against, and a test that only compared those would
be circular. The acceptance comparison is therefore against
`benchmarks/p02/reference_values.yaml` — Fable's 20-digit values, computed with mpmath from the
SYN-001 derivation with no backend and no oracle import. Two things are genuinely independent there
and they are the two that matter:

* the **composition** — the compiler assembles 17 rows from declarations, where the reference was
  evaluated as whole closed-form residuals;
* the **derivatives** — the compiler obtains every Jacobian entry by algorithmic differentiation
  through an opaque callback's declared-sparse chain rule, where the reference was differentiated
  by hand.

The lifted form is the one P02 matched across both backends (17 variables, 17 equations, 60
structural nonzeros), so it is the form with a registered expectation to be judged against.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from benchmarks.p02.expected import (
    C_P,
    COMPONENTS,
    EQUATION_IDS_I,
    EQUATION_IDS_L,
    L_VAP,
    T_REF,
    V_MOLAR,
    VARIABLE_IDS_I,
    VARIABLE_IDS_L,
    Parameters,
    d_ln_k_d_pressure,
    d_ln_k_d_temperature,
    h_liquid,
    ln_k,
)
from benchmarks.p02.expected import COLUMN_SCALES as _COLUMN_SCALES
from benchmarks.p02.expected import ROW_SCALES as _ROW_SCALES
from benchmarks.p02.expected import DomainError as ExpectedDomainError
from openflowsheet.compile.spec import (
    Algebra,
    DomainError,
    EquationSpec,
    Expr,
    ProblemSpec,
    RowBuilder,
)

LABEL_L = "SYN-001-L-1"
LABEL_I = "SYN-001-I-1"

#: The pinned-input vector, in the order `constants_sha256` hashes it (ADR 0008 D4.1). Feed,
#: feed enthalpy and the two specification values — *all* of it, not only the physical constants:
#: two instances that differ in `t_spec` alone are different problems and must hash differently.
PARAMETER_IDS: tuple[str, ...] = (
    "feed_A",
    "feed_B",
    "feed_C",
    "h_feed",
    "t_spec",
    "p_spec",
)


def parameters_of(parameters: Parameters) -> dict[str, float]:
    """Flatten a registered state's `Parameters` into the named pinned-input vector."""
    return {
        "feed_A": parameters.feed[0],
        "feed_B": parameters.feed[1],
        "feed_C": parameters.feed[2],
        "h_feed": parameters.h_feed,
        "t_spec": parameters.t_spec,
        "p_spec": parameters.p_spec,
    }


class KBlock:
    """`(T, P) -> (lnK_A, lnK_B, lnK_C)`. Every output depends on both inputs: dense 3x2."""

    block_id = "blockK"
    input_ids = ("T", "P")
    output_ids = tuple(f"lnK_{component}" for component in COMPONENTS)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return tuple((row, column) for row in range(3) for column in range(2))

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        try:
            return list(ln_k(inputs[0], inputs[1]))
        except ExpectedDomainError as error:
            raise DomainError(str(error)) from error

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        temperature, pressure = inputs[0], inputs[1]
        try:
            d_temperature = d_ln_k_d_temperature(temperature, pressure)
            d_pressure = d_ln_k_d_pressure(temperature, pressure)
        except ExpectedDomainError as error:
            raise DomainError(str(error)) from error
        triples: list[tuple[int, int, float]] = []
        for row in range(3):
            triples.append((row, 0, d_temperature[row]))
            triples.append((row, 1, d_pressure[row]))
        return triples


class HBlock:
    """`(l_A, l_B, l_C, T, P) -> (hL_A, hL_B, hL_C)` with `hL_i = l_i * h_i^L(T, P)`.

    Sparse by physics, not by convenience: an output depends on *its own* liquid flow and on the
    two intensive inputs, never on another component's flow. That is 9 of the 15 entries, and the
    six structural zeros are the ones the assembled 60-nonzero pattern depends on surviving.
    """

    block_id = "blockH"
    input_ids = (*(f"l_{component}" for component in COMPONENTS), "T", "P")
    output_ids = tuple(f"hL_{component}" for component in COMPONENTS)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return tuple((row, column) for row in range(3) for column in (row, 3, 4))

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        molar = h_liquid(inputs[3], inputs[4])
        return [inputs[index] * molar[index] for index in range(3)]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        temperature, pressure = inputs[3], inputs[4]
        molar = h_liquid(temperature, pressure)
        triples: list[tuple[int, int, float]] = []
        for row in range(3):
            flow = inputs[row]
            triples.append((row, row, molar[row]))
            triples.append((row, 3, flow * C_P))
            triples.append((row, 4, flow * V_MOLAR[row]))
        return triples


def _balance(component: str) -> RowBuilder:
    def build(
        v: Mapping[str, Expr], o: Mapping[str, Expr], p: Mapping[str, float], alg: Algebra
    ) -> Expr:
        del o, alg
        return v[f"v_{component}"] + v[f"l_{component}"] - p[f"feed_{component}"]

    return build


def _equilibrium(component: str, *, inlined: bool = False) -> RowBuilder:
    """`v_i L − exp(lnK_i) l_i V`.

    In the lifted form `lnK_i` is a variable and the block reaches this row only through the
    definitional `kdef` row, where it appears once with coefficient −1. In the **inlined** form the
    block output is substituted here, so `d(row)/dT` is `−exp(lnK_i) · dlnK_i/dT · l_i V` — the
    callback's declared-sparse chain rule composed with a non-unit outer derivative. That
    composition is what the lifted form never exercises.
    """

    def build(
        v: Mapping[str, Expr], o: Mapping[str, Expr], p: Mapping[str, float], alg: Algebra
    ) -> Expr:
        del p
        ln_k_value = o[f"blockK.lnK_{component}"] if inlined else v[f"lnK_{component}"]
        return v[f"v_{component}"] * v["L"] - alg.exp(ln_k_value) * v[f"l_{component}"] * v["V"]

    return build


def _k_definition(component: str) -> RowBuilder:
    def build(
        v: Mapping[str, Expr], o: Mapping[str, Expr], p: Mapping[str, float], alg: Algebra
    ) -> Expr:
        del p, alg
        return v[f"lnK_{component}"] - o[f"blockK.lnK_{component}"]

    return build


def _h_definition(component: str) -> RowBuilder:
    def build(
        v: Mapping[str, Expr], o: Mapping[str, Expr], p: Mapping[str, float], alg: Algebra
    ) -> Expr:
        del p, alg
        return v[f"hL_{component}"] - o[f"blockH.hL_{component}"]

    return build


def _v_definition(
    v: Mapping[str, Expr], o: Mapping[str, Expr], p: Mapping[str, float], alg: Algebra
) -> Expr:
    del o, p, alg
    return v["V"] - (v["v_A"] + v["v_B"] + v["v_C"])


def _l_definition(
    v: Mapping[str, Expr], o: Mapping[str, Expr], p: Mapping[str, float], alg: Algebra
) -> Expr:
    del o, p, alg
    return v["L"] - (v["l_A"] + v["l_B"] + v["l_C"])


def _energy_builder(*, inlined: bool = False) -> RowBuilder:
    def _energy(
        v: Mapping[str, Expr], o: Mapping[str, Expr], p: Mapping[str, float], alg: Algebra
    ) -> Expr:
        """Vapour enthalpy is written inline: it is a closed form in `T` alone.

        Putting it behind an opaque callback would hide a derivative the compiler can take
        exactly, and would cost a block call per evaluation for nothing.
        """
        del alg
        total = 0.0
        for index, component in enumerate(COMPONENTS):
            vapour = C_P * (v["T"] - T_REF) + L_VAP[index]
            total = total + v[f"v_{component}"] * vapour
        for component in COMPONENTS:
            total = total + (o[f"blockH.hL_{component}"] if inlined else v[f"hL_{component}"])
        return total - p["h_feed"] - v["Q"]

    return _energy


def _t_spec(
    v: Mapping[str, Expr], o: Mapping[str, Expr], p: Mapping[str, float], alg: Algebra
) -> Expr:
    del o, alg
    return v["T"] - p["t_spec"]


def _p_spec(
    v: Mapping[str, Expr], o: Mapping[str, Expr], p: Mapping[str, float], alg: Algebra
) -> Expr:
    del o, alg
    return v["P"] - p["p_spec"]


def _equations(*, inlined: bool = False) -> tuple[EquationSpec, ...]:
    """The rows of one form, in the registered order for that form.

    Every row is `"algebraic"`. That is a declaration, not a default: ADR 0008 D4.4 says a row the
    compiler authors must be declared explicitly rather than left `"absent"`, and none of these
    rows carries an accumulation term — SYN-001 is a steady-state flash and its holdup rows belong
    to the transient extension ADR 0008 defers.
    """
    equations: list[EquationSpec] = []
    for component in COMPONENTS:
        equations.append(
            EquationSpec(
                f"bal_{component}", _balance(component), "algebraic", origin="mole balance"
            )
        )
    equations.append(EquationSpec("Vdef", _v_definition, "algebraic", origin="total vapour flow"))
    equations.append(EquationSpec("Ldef", _l_definition, "algebraic", origin="total liquid flow"))
    for component in COMPONENTS:
        equations.append(
            EquationSpec(
                f"eq_{component}",
                _equilibrium(component, inlined=inlined),
                "algebraic",
                origin="K-value",
            )
        )
    if not inlined:
        for component in COMPONENTS:
            equations.append(
                EquationSpec(
                    f"kdef_{component}", _k_definition(component), "algebraic", origin="lifted lnK"
                )
            )
        for component in COMPONENTS:
            equations.append(
                EquationSpec(
                    f"hdef_{component}",
                    _h_definition(component),
                    "algebraic",
                    origin="lifted enthalpy",
                )
            )
    equations.append(
        EquationSpec(
            "energy", _energy_builder(inlined=inlined), "algebraic", origin="energy balance"
        )
    )
    equations.append(EquationSpec("tspec", _t_spec, "algebraic", origin="specification"))
    equations.append(EquationSpec("pspec", _p_spec, "algebraic", origin="specification"))
    return tuple(equations)


def syn001_spec(parameters: Parameters, *, form: str = "L") -> ProblemSpec:
    """The SYN-001 problem at one registered state's pinned inputs, in the lifted or inlined form.

    **`"L"`, lifted** — 17 variables, 17 equations, 60 structural nonzeros. `lnK_i` and `hL_i` are
    variables defined by their own rows, so each block output reaches the system once, with
    coefficient −1.

    **`"I"`, inlined** — 11 variables, 11 equations, 43 nonzeros. The block outputs are substituted
    into the equilibrium and energy rows, so the compiler must push the callback's declared-sparse
    derivative through a non-unit outer derivative: `d(eq_i)/dT` carries
    `exp(lnK_i)·dlnK_i/dT·l_i·V`.
    **That composition is the reason this form exists here.** The lifted form never exercises it —
    a gap the Fable review of K01 found between what the conformance evidence showed and what it
    was described as showing.
    """
    if form not in ("L", "I"):
        raise ValueError(f"form must be 'L' (lifted) or 'I' (inlined), not {form!r}")
    inlined = form == "I"
    spec = ProblemSpec(
        label=f"SYN-001-{form}-1",
        variable_ids=VARIABLE_IDS_I if inlined else VARIABLE_IDS_L,
        equations=_equations(inlined=inlined),
        parameter_ids=PARAMETER_IDS,
        parameters=parameters_of(parameters),
        blocks=(KBlock(), HBlock()),
        block_inputs={
            "blockK": ("T", "P"),
            "blockH": ("l_A", "l_B", "l_C", "T", "P"),
        },
        column_scales={
            name: value for name, value in _COLUMN_SCALES.items() if name in spec_variables(inlined)
        },
        row_scales={
            name: value for name, value in _ROW_SCALES.items() if name in spec_equations(inlined)
        },
    )
    registered = EQUATION_IDS_I if inlined else EQUATION_IDS_L
    if spec.equation_ids != registered:
        raise AssertionError(
            "the fixture's row order drifted from the registered ordering; the reference values "
            "are keyed by equation id but the assembled CSC row indices are positional, so a drift "
            f"here is a silent permutation.\n  fixture:    {spec.equation_ids}\n"
            f"  registered: {registered}"
        )
    return spec


def spec_variables(inlined: bool) -> frozenset[str]:
    return frozenset(VARIABLE_IDS_I if inlined else VARIABLE_IDS_L)


def spec_equations(inlined: bool) -> frozenset[str]:
    return frozenset(EQUATION_IDS_I if inlined else EQUATION_IDS_L)
