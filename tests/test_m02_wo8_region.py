"""M02 WO-8.3: a `pr-c1-v1` split in the region and in `check_agreement` (design note §14.2 B12–B14;
register R-254–R-256; gates G7 (g), (i)).

- B14: the kernel and the single-phase admissibility of a PR split read M01 §7 rule 3 with τ_dew
  (`classify`); a band VAPOR opens as a VAPOR restart pins it; `admissibility_epsilon` is unread.
- B12/B13: in a TWO_PHASE attempt the light-gas liquid flows are pinned at `+0.0` by the split's
  `VapourOnlyForm` — G7 (g), at every evaluated state of a solve that iterates.
- B13: `check_agreement` passes on the C1 flash's flowsheets and raises its specific code on
  each of G7 (i)'s five mutated flashes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

import pytest
from m02_c1_support import connection, feed_specifications, instance, revision, specification
from m02_wo8_support import (
    POLICY,
    bind,
    flash_revision,
    is_positive_zero,
    light_liquid_columns,
    recording,
    solve,
)

from openflowsheet.application import revision_binding
from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.compile.spec import EquationSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models import Contribution
from openflowsheet.models.c1 import TAU_DEW
from openflowsheet.orchestrator.execution import declaration_identity
from openflowsheet.orchestrator.region import (
    LiftedSplit,
    VapourOnlyForm,
    _admissible,
    _dropped,
    _kernel,
    _pinned,
)
from openflowsheet.orchestrator.revision import instances_of, plan_revision
from openflowsheet.orchestrator.splits import (
    check_agreement,
    closure_types,
    dormancy_forms,
    lifted_splits,
    vapour_only_forms,
    zero_flow_forms,
)
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider

CONTEXT = EvaluationContext(model_version="m02-wo8-region", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()
F1 = (0.6, 0.2, 0.165, 0.015, 0.02)
F4 = (0.6, 0.2, 0.05476219349459947, 0.015, 0.02)
V1 = (0.7, 0.235, 0.03, 0.015, 0.02)


def _raised(n: tuple[float, ...], delta: float) -> tuple[float, ...]:
    """F4-like feed with NH3 multiplied by `1 + δ` (G7 (k): `l/n_tot ≈ 0.0616 δ`)."""
    return (*n[:2], n[2] * (1.0 + delta), *n[3:])


def _split() -> LiftedSplit:
    binding = bind(flash_revision(F1, 268.15))
    (split,) = lifted_splits(instances_of(binding.flowsheet), COMPONENTS)
    return split


def _state(split: LiftedSplit, n: tuple[float, ...], t: float = 268.15) -> dict[str, float]:
    state = dict.fromkeys((*split.vapor, *split.liquid, split.vapor_total, split.liquid_total), 1.0)
    state.update(dict(zip(split.feed, n, strict=True)))
    state[split.temperature] = t
    state[split.pressure] = 1.0e7
    return state


# -- the forms ---------------------------------------------------------------------------------


def test_the_flashs_vapour_only_form_is_its_light_gas_liquid_flows_and_zero_rows() -> None:
    binding = bind(flash_revision(F1, 268.15))
    instances = instances_of(binding.flowsheet)
    splits = lifted_splits(instances, COMPONENTS)
    assert vapour_only_forms(instances, splits, COMPONENTS) == {
        "U": VapourOnlyForm(
            "U",
            light_liquid_columns(),
            tuple(f"U:C1FL-equilibrium:{c}" for c in ("H2", "N2", "Ar", "CH4")),
        )
    }


def test_the_form_acts_in_two_phase_only() -> None:
    split = _split()
    forms = {"U": VapourOnlyForm("U", light_liquid_columns(), ("r1", "r2", "r3", "r4"))}
    assert _pinned(split, "TWO_PHASE", {}, forms) == light_liquid_columns()
    assert _dropped(split, "TWO_PHASE", {}, forms) == ("r1", "r2", "r3", "r4")
    for regime in ("VAPOR", "LIQUID"):
        assert _pinned(split, regime, {}, forms) == split.pinned(regime)  # type: ignore[arg-type]
        assert _dropped(split, regime, {}, forms) == split.dropped(regime)  # type: ignore[arg-type]
    assert _pinned(split, "TWO_PHASE", {}) == () == _dropped(split, "TWO_PHASE", {})


# -- B14: the kernel and the admissibility ---------------------------------------------------------


def test_the_kernel_pins_a_band_vapour_as_a_vapour_restart_does() -> None:
    """F4's feed with NH3 × (1 + 8.1e-10): the flash answers TWO_PHASE with an ulp-sized liquid;
    the kernel answers VAPOR, the vapour the feed bitwise and the liquid `+0.0`."""
    split = _split()
    for delta in (0.0, 8.1e-10):
        n = _raised(F4, delta)
        regime, values = _kernel(PROVIDER, CONTEXT, split, _state(split, n))
        assert regime == "VAPOR"
        assert tuple(values[name] for name in split.vapor) == n
        assert all(is_positive_zero(values[name]) for name in split.liquid)
        assert values[split.vapor_total] == float(sum(n))
        assert is_positive_zero(values[split.liquid_total])


def test_the_kernel_past_the_band_is_the_flashs_split() -> None:
    split = _split()
    regime, values = _kernel(PROVIDER, CONTEXT, split, _state(split, _raised(F4, 3.2e-9)))
    assert regime == "TWO_PHASE"
    assert 0.0 < values["S3.n.NH3"] and values[split.liquid_total] == values["S3.n.NH3"]
    assert all(is_positive_zero(values[name]) for name in light_liquid_columns())


@pytest.mark.parametrize("epsilon", [0.0, 1.0e9])
def test_vapour_admissibility_is_the_band_and_epsilon_is_unread(epsilon: float) -> None:
    split = _split()
    inside = _admissible(
        PROVIDER, CONTEXT, split, "VAPOR", _state(split, _raised(F4, 8.1e-10)), epsilon
    )
    past = _admissible(
        PROVIDER, CONTEXT, split, "VAPOR", _state(split, _raised(F4, 3.2e-9)), epsilon
    )
    assert inside[0] is True and 0.0 < inside[1] <= TAU_DEW
    assert past[0] is False and past[1] > TAU_DEW
    assert _admissible(PROVIDER, CONTEXT, split, "VAPOR", _state(split, V1, 673.15), epsilon) == (
        True,
        0.0,
    )


def test_liquid_admissibility_needs_a_pure_nh3_liquid_feed() -> None:
    split = _split()
    pure = (0.0, 0.0, 1.0, 0.0, 0.0)
    assert _admissible(PROVIDER, CONTEXT, split, "LIQUID", _state(split, pure), 0.0) == (True, 0.0)
    ok, value = _admissible(PROVIDER, CONTEXT, split, "LIQUID", _state(split, F1), 0.0)
    assert ok is False and value == sum((0.6, 0.2, 0.015, 0.02)) / sum(F1)


# -- agreement ---------------------------------------------------------------------------------


def _loop() -> dict[str, Any]:
    """A reactor-less C1 loop: makeup with NH3 → mixer (with the recycle) → heater to 300 K →
    flash at 253.15 K → splitter (r = 0.98) → recycle; the purge and the liquid to sinks. Newton
    iterates from the traversal's start (the recycle is torn)."""
    fraction = {
        "value": 0.98,
        "unit": "1",
        "dimension": [0] * 7,
        "kind": "dimensionless",
        "meaning": "test",
        "role": "fixed",
    }
    return revision(
        [
            instance("F", "c1.feed_source"),
            instance("M", "c1.adiabatic_mixer"),
            instance("H", "c1.tp_heater"),
            instance("U", "c1.tp_flash"),
            instance("SP", "c1.stream_splitter", {"split_fraction": fraction}),
            instance("K", "c1.product_sink"),
            instance("L", "c1.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("M", "inlet")),
            connection("S7", ("SP", "recycle"), ("M", "inlet")),
            connection("S2", ("M", "outlet"), ("H", "inlet")),
            connection("S8", ("H", "outlet"), ("U", "inlet")),
            connection("S4", ("U", "vapor"), ("SP", "inlet")),
            connection("S3", ("U", "liquid"), ("L", "inlet"), "liquid"),
            connection("S6", ("SP", "purge"), ("K", "inlet")),
        ],
        [
            *feed_specifications("S1", (0.74625, 0.24875, 0.05, 0.002, 0.003), 300.0, 1.0e7),
            specification("SPEC-S8-T", "connection", "S8", "state.T", 300.0, "temperature"),
            specification("SPEC-S4-T", "connection", "S4", "state.T", 253.15, "temperature"),
            specification("SPEC-S4-P", "connection", "S4", "state.P", 1.0e7, "pressure"),
            specification("SPEC-S3-T", "connection", "S3", "state.T", 253.15, "temperature"),
            specification("SPEC-S3-P", "connection", "S3", "state.P", 1.0e7, "pressure"),
        ],
    )


FLOWSHEETS: dict[str, Callable[[], dict[str, Any]]] = {
    "F1": lambda: flash_revision(F1, 268.15),
    "F11": lambda: flash_revision(F1, 250.0, 2.5e7),
    "V1": lambda: flash_revision(V1, 673.15),
    "F4": lambda: flash_revision(F4, 268.15),
    "zero": lambda: flash_revision((0.0,) * 5, 268.15),
    "loop": _loop,
}


@pytest.mark.parametrize("name", list(FLOWSHEETS))
def test_agreement_holds_on_each_c1_flowsheet(name: str) -> None:
    """`plan_revision` runs `check_agreement` with every form, (h) included, and plans."""
    from openflowsheet.orchestrator.execution import ExecutionPlan

    plan, _ = plan_revision(bind(FLOWSHEETS[name]()), POLICY)
    assert isinstance(plan, ExecutionPlan), plan


def _inputs(binding: RevisionBinding) -> dict[str, Any]:
    """What `plan_revision` hands `check_agreement`."""
    spec = binding.spec
    model_version, constants = declaration_identity(spec)
    declaration = trace_declaration(
        spec,
        model_version=model_version,
        constants_sha256=constants,
        specification_ids={},
        row_units=binding.row_units,
    )
    instances = instances_of(binding.flowsheet)
    splits = lifted_splits(instances, COMPONENTS)
    units = binding.flowsheet.units()
    return {
        "instances": instances,
        "splits": splits,
        "spec": spec,
        "row_units": binding.row_units,
        "declaration": declaration,
        "forms": zero_flow_forms(instances, splits, closure_types(units), COMPONENTS),
        "dormancy": dormancy_forms(instances, units, COMPONENTS),
        "vapour_only": vapour_only_forms(instances, splits, COMPONENTS),
    }


class _Mutant:
    """A `c1.tp_flash` whose contribution `alter` rewrites (G7 (i))."""

    def __init__(self, unit: Any, alter: Callable[[Contribution], Contribution]) -> None:
        self._unit, self._alter = unit, alter

    def __getattr__(self, name: str) -> Any:
        return getattr(self._unit, name)

    def contribute(self, wiring: Any, components: Any) -> Contribution:
        return self._alter(self._unit.contribute(wiring, components))


def _mutated(
    monkeypatch: pytest.MonkeyPatch, alter: Callable[[Contribution], Contribution]
) -> RevisionBinding:
    builder = revision_binding.C1_MODEL_BUILDERS["c1.tp_flash"]

    def build(*arguments: Any) -> Any:
        unit, configuration = builder(*arguments)
        return _Mutant(unit, alter), configuration

    monkeypatch.setitem(revision_binding.C1_MODEL_BUILDERS, "c1.tp_flash", build)  # type: ignore[arg-type]
    return bind(flash_revision(F1, 268.15))


def _without(row: str) -> Callable[[Contribution], Contribution]:
    def alter(contribution: Contribution) -> Contribution:
        return replace(
            contribution,
            equations=tuple(e for e in contribution.equations if e.equation_id != row),
            row_kinds={k: v for k, v in contribution.row_kinds.items() if k != row},
        )

    return alter


def _reading_vapour(row: str, liquid: str, vapour: str) -> Callable[[Contribution], Contribution]:
    def build(variables: Mapping[str, Any], blocks: Any, parameters: Any, algebra: Any) -> Any:
        return variables[liquid] * (1.0 + variables[vapour])

    def alter(contribution: Contribution) -> Contribution:
        return replace(
            contribution,
            equations=tuple(
                EquationSpec(e.equation_id, build, e.accumulation, e.origin)
                if e.equation_id == row
                else e
                for e in contribution.equations
            ),
        )

    return alter


def _kind(row: str, kind: str) -> Callable[[Contribution], Contribution]:
    def alter(contribution: Contribution) -> Contribution:
        return replace(contribution, row_kinds={**contribution.row_kinds, row: kind})

    return alter


def _check(inputs: Mapping[str, Any]) -> None:
    check_agreement(
        inputs["instances"],
        inputs["splits"],
        inputs["spec"],
        inputs["row_units"],
        inputs["declaration"],
        inputs["forms"],
        inputs["dormancy"],
        inputs["vapour_only"],
    )


def test_g7i_the_unmutated_flash_agrees() -> None:
    _check(_inputs(bind(flash_revision(F1, 268.15))))


@pytest.mark.parametrize(
    ("alter", "code"),
    [
        (_without("U:C1FL-equilibrium:H2"), r"^lifted_split_rows_disagree\(U\)"),
        (
            _reading_vapour("U:C1FL-equilibrium:N2", "S3.n.N2", "S2.n.N2"),
            r"^lifted_split_equilibrium_disagrees\(U, U:C1FL-equilibrium:N2\)",
        ),
        (_kind("U:C1FL-equilibrium:NH3", "molar_flow"), r"^lifted_split_without_rows\(U\)$"),
    ],
    ids=["zero-row-removed", "zero-row-reads-v", "E-molar-flow"],
)
def test_g7i_a_mutated_flash_raises_its_code(
    monkeypatch: pytest.MonkeyPatch, alter: Callable[[Contribution], Contribution], code: str
) -> None:
    inputs = _inputs(_mutated(monkeypatch, alter))
    with pytest.raises(ValueError, match=code):
        _check(inputs)


def test_g7i_no_vapour_only_form_supplied() -> None:
    inputs = {**_inputs(bind(flash_revision(F1, 268.15))), "vapour_only": {}}
    with pytest.raises(ValueError, match=r"^vapour_only_form_disagrees\(U\): no form$"):
        _check(inputs)


def test_g7i_a_form_naming_the_nh3_column() -> None:
    inputs = _inputs(bind(flash_revision(F1, 268.15)))
    form = inputs["vapour_only"]["U"]
    wrong = VapourOnlyForm("U", (*form.columns, "S3.n.NH3"), (*form.rows, "U:C1FL-equilibrium:NH3"))
    with pytest.raises(ValueError, match=r"^vapour_only_form_disagrees\(U\): the form names"):
        _check({**inputs, "vapour_only": {"U": wrong}})


def test_agreement_without_the_forms_argument_runs_as_before() -> None:
    """(h) runs only when `check_agreement` is given `vapour_only` (as `forms`, `dormancy`)."""
    inputs = _inputs(bind(flash_revision(F1, 268.15)))
    check_agreement(
        inputs["instances"],
        inputs["splits"],
        inputs["spec"],
        inputs["row_units"],
        inputs["declaration"],
    )


# -- G7 (g): the light-gas liquid columns at every evaluated state ---------------------------------


@pytest.mark.parametrize("name", list(FLOWSHEETS))
def test_g7g_light_gas_liquid_columns_are_bitwise_positive_zero(name: str) -> None:
    """Every state the compiled residual is evaluated at — every Newton iterate and trial of every
    attempt — and `x_final` carry the four light-gas liquid columns bitwise `+0.0`."""
    with recording() as states:
        solved = solve(FLOWSHEETS[name]())
    assert solved.run.outcome == "CONVERGED", solved.run.message
    assert states
    if name == "loop":
        assert len(states) > 2  # the recycle is torn: Newton iterates
    columns = light_liquid_columns()
    for state in states:
        assert all(is_positive_zero(state[column]) for column in columns)
    assert solved.run.state is not None
    assert all(is_positive_zero(solved.run.state[column]) for column in columns)
