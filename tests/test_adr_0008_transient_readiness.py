"""ADR 0008 — transient-extension readiness: the pins, not the numerics.

Every assertion in this module pins a *decision* recorded in
`docs/adr/0008-transient-extension-readiness.md`. None of them is a numerical result, and none
establishes that anything works. They exist so that a later session cannot silently undo a choice
that was made deliberately: a time coordinate at the evaluation boundary (group A, D1), a state
hash that stops covering all of `x` (group H, D2), or a relabelled accumulation declaration in a
SYN-001 manifest (group M, D3). Amendment 1 adds group U: a physical holdup that turns into an
enthalpy, or a module outside the PTC path that imports the residence-time pseudo-holdup mapping.
Amendment 2 adds group E and widens U1's reach: every model id the binder can instantiate — the
external C1 reactor, its stand-in and its surrogate included — has declarations U1 reads, and the
C1 units conserve what their SYN-001 namesakes conserve, and the three C1 reactor ids hold
the same amounts and internal energy.
A failure here is a design regression, and the message points at the ADR rule it violates.

Blueprint §2.2 defers dynamics and this module does not change that: nothing below evaluates a
transient problem, and no holdup variable exists.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import math
import pkgutil
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml

import openflowsheet.models as models_package
import openflowsheet.studies.surrogate as surrogate_package

# D2's rules are pinned on both implementations that exist. The judge's is the independent witness
# for the P02 artifacts, still on the §10.4 text encoding; production moved to big-endian IEEE-754
# bytes when Frank ratified the Fable review's recommendation on 2026-09-18. The *rules* below are
# properties of any admissible encoding, so both must satisfy every one of them, and parametrizing
# says so rather than leaving production pinned by nothing here.
#
# `_state_sha256` is imported deliberately despite the leading underscore: ADR 0008 D2 fixes what
# the state hash *covers*, ADR 0002 fixes how the doubles are *encoded*, and until ADR 0002 closes
# the convention in force is the P02 one. The judge's independent recomputation of it is the honest
# thing to assert against. K01 must port group H to the canonical hash when it lands; no digest
# value is pinned here (D2.1).
from benchmarks.p02.judge import _state_sha256 as _judge_state_sha256
from openflowsheet.application.revision_binding import MODEL_BUILDERS
from openflowsheet.canonical import state_sha256 as _production_state_sha256
from openflowsheet.compiled import (
    CompiledProblem,
    EvaluationContext,
    EvaluationResult,
    JacobianResult,
)
from openflowsheet.models import Accumulation, DeclaredEquation, Holdup
from openflowsheet.models.syn001 import ENERGY, MOLE
from openflowsheet.units import DIMENSION_ORDER

MANIFEST_DIR = REPO_ROOT / "tests" / "fixtures" / "schemas" / "model_manifest" / "valid"

ADR = "docs/adr/0008-transient-extension-readiness.md"


# ------------------------------------------------------------------------------------------
# A — the shape of the evaluation boundary (D1)
# ------------------------------------------------------------------------------------------


def test_a1_evaluation_context_field_set_is_exactly_the_frozen_one() -> None:
    """D1.1: no field of `EvaluationContext` carries time, pseudo-time, a step or a history."""
    assert tuple(f.name for f in fields(EvaluationContext)) == (
        "model_version",
        "constants_sha256",
        "phase_signature",
        "accuracy_policy",
        "workspace",
    ), (
        "EvaluationContext's field set is frozen by ADR 0008 D1.1. A time-like field (`time`, "
        f"`t`, `tau`, `dt`) is exactly what that rule forbids: a time-varying specification "
        f"reaches the boundary as a pinned input, not as a context field. See {ADR}."
    )


@pytest.mark.parametrize("method_name", ["residual", "jacobian", "reconstruct"])
def test_a2_protocol_methods_take_exactly_x_and_context(method_name: str) -> None:
    """D1.1: no `xdot`, `x_prev`, `h` or `t` argument reaches the compiled problem."""
    method = getattr(CompiledProblem, method_name)
    assert tuple(inspect.signature(method).parameters) == ("self", "x", "context"), (
        f"CompiledProblem.{method_name} has the arity frozen by docs/interfaces-frozen.md §1 and "
        f"ADR 0008 D1.1. The accumulation term of a transient problem is formed outside this "
        f"boundary from the Jacobian and the model-declared mass matrix. See {ADR}."
    )


@pytest.mark.parametrize("result_type", [EvaluationResult, JacobianResult])
def test_a3_both_result_types_carry_the_four_pairing_fields(result_type: type) -> None:
    """D2.4: pairing identity is exactly these four fields, echoed on both results."""
    names = {f.name for f in fields(result_type)}
    assert {
        "model_version",
        "constants_sha256",
        "state_sha256",
        "phase_signature",
    } <= names, f"{result_type.__name__} lost a pairing field of ADR 0008 D2.4. See {ADR}."


# ------------------------------------------------------------------------------------------
# H — what the state hash covers (D2)
# ------------------------------------------------------------------------------------------

#: Registered state for group H. Five distinct values so a swap is detectable; `c` is registered
#: *because* it is zero (H3 tests signed zero there, H1 that the one-ulp step from 0.0 — the
#: smallest subnormal — still registers); `d` and `e` span eleven decades so that H1 exercises a
#: one-ulp change at 1e5 (1.4551915228366852e-11 absolute), which a hash quantized on any fixed
#: absolute or 1e-15-relative grid would miss.
HASHERS = (_judge_state_sha256, _production_state_sha256)
HASHER_IDS = ("judge-p02-10.4", "production-ieee754-be-v1")

ORDER = ("a", "b", "c", "d", "e")
X0 = {"a": 1.5, "b": -2.25, "c": 0.0, "d": 3.0e-7, "e": 1.0e5}


@pytest.mark.parametrize(("hasher", "hasher_id"), zip(HASHERS, HASHER_IDS, strict=True))
@pytest.mark.parametrize("name", ORDER)
def test_h1_every_coordinate_participates_at_full_precision(
    name: str, hasher: Any, hasher_id: str
) -> None:
    """D2.6: a hash invariant under a one-ulp change of any coordinate is a quantized hash."""
    perturbed = dict(X0)
    perturbed[name] = math.nextafter(X0[name], math.inf)
    assert hasher(perturbed, ORDER) != hasher(X0, ORDER), (
        f"{hasher_id}: a one-ulp change of {name!r} left the state hash unchanged. Quantizing "
        f"state coordinates is forbidden on the exact path (blueprint §6.4, ADR 0008 D2.6). "
        f"See {ADR}."
    )


@pytest.mark.parametrize(("hasher", "hasher_id"), zip(HASHERS, HASHER_IDS, strict=True))
def test_h2_variable_order_participates(hasher: Any, hasher_id: str) -> None:
    """D2.1: the order of `variable_ids` is part of the covered content."""
    swapped = dict(X0)
    swapped["a"], swapped["b"] = X0["b"], X0["a"]
    assert hasher(swapped, ORDER) != hasher(X0, ORDER), hasher_id


@pytest.mark.parametrize(("hasher", "hasher_id"), zip(HASHERS, HASHER_IDS, strict=True))
def test_h3_signed_zero_is_normalized(hasher: Any, hasher_id: str) -> None:
    """D2.1 with ADR 0001 D1.5: −0.0 and +0.0 are the same state."""
    negative_zero = dict(X0)
    negative_zero["c"] = -0.0
    assert hasher(negative_zero, ORDER) == hasher(X0, ORDER), hasher_id


@pytest.mark.parametrize(("hasher", "hasher_id"), zip(HASHERS, HASHER_IDS, strict=True))
def test_h4_nothing_outside_the_ordered_state_participates(hasher: Any, hasher_id: str) -> None:
    """D2.2: context fields and integrator internals are excluded by construction."""
    with_time = dict(X0)
    with_time["t"] = 12.5
    with_time["tau"] = 0.75
    assert hasher(with_time, ORDER) == hasher(X0, ORDER), (
        f"{hasher_id}: a key outside `variable_ids` reached the state hash. ADR 0008 D2.2 excludes "
        f"time, pseudo-time and every other non-state quantity by construction. See {ADR}."
    )


@pytest.mark.parametrize(("hasher", "hasher_id"), zip(HASHERS, HASHER_IDS, strict=True))
def test_h5_state_length_participates(hasher: Any, hasher_id: str) -> None:
    """D2.1: a shorter ordering is a different state, not a prefix of the same one."""
    assert hasher(X0, ORDER[:-1]) != hasher(X0, ORDER), hasher_id


@pytest.mark.parametrize(("hasher", "hasher_id"), zip(HASHERS, HASHER_IDS, strict=True))
def test_h6_the_hash_is_a_pure_function_of_state_and_order(hasher: Any, hasher_id: str) -> None:
    """D2.1: nothing else is in scope to be hashed."""
    assert tuple(inspect.signature(hasher).parameters) == ("x", "order"), hasher_id


# ------------------------------------------------------------------------------------------
# M — the registered accumulation classification (D3)
# ------------------------------------------------------------------------------------------

#: ADR 0008 D3.5, normative. Relabelling a row requires a new Fable-authored ADR.
REGISTERED_KINDS: dict[tuple[str, str], str] = {
    ("syn001.feed_source", "FEED-n"): "algebraic",
    ("syn001.feed_source", "FEED-T"): "algebraic",
    ("syn001.feed_source", "FEED-P"): "algebraic",
    ("syn001.adiabatic_mixer", "MIX-mole"): "zero_holdup_balance",
    ("syn001.adiabatic_mixer", "MIX-energy"): "zero_holdup_balance",
    ("syn001.adiabatic_mixer", "MIX-pressure"): "algebraic",
    ("syn001.adiabatic_mixer", "MIX-dormant-inlet"): "algebraic",
    ("syn001.tp_heater", "HEAT-mole"): "holdup_balance",
    ("syn001.tp_heater", "HEAT-duty"): "holdup_balance",
    ("syn001.tp_heater", "HEAT-T"): "algebraic",
    ("syn001.tp_heater", "HEAT-pressure"): "algebraic",
    ("syn001.tp_heater", "HEAT-equilibrium"): "algebraic",
    ("syn001.tp_flash", "FLASH-mole"): "holdup_balance",
    ("syn001.tp_flash", "FLASH-duty"): "holdup_balance",
    ("syn001.tp_flash", "FLASH-equilibrium"): "algebraic",
    ("syn001.tp_flash", "FLASH-T"): "algebraic",
    ("syn001.tp_flash", "FLASH-P"): "algebraic",
    ("syn001.stream_splitter", "SPLIT-recycle"): "algebraic",
    ("syn001.stream_splitter", "SPLIT-purge"): "algebraic",
    ("syn001.stream_splitter", "SPLIT-T"): "algebraic",
    ("syn001.stream_splitter", "SPLIT-P"): "algebraic",
}

#: ADR 0008 D3.5: the holdup a row would accumulate, and its ADR 0001 D1.2 dimension.
REGISTERED_HOLDUPS: dict[str, tuple[str, list[int]]] = {
    "HEAT-mole": ("N_i", [0, 0, 0, 0, 1, 0, 0]),
    "FLASH-mole": ("N_i", [0, 0, 0, 0, 1, 0, 0]),
    "HEAT-duty": ("U", [2, 1, -2, 0, 0, 0, 0]),
    "FLASH-duty": ("U", [2, 1, -2, 0, 0, 0, 0]),
}

#: ADR 0008 D3.3: every balance row is written `inflow − outflow + sources`.
REGISTERED_STATEMENTS: dict[str, str] = {
    "MIX-mole": "sum_k n_in(k),i - n_out,i = 0 for every component i",
    "MIX-energy": "sum_k Hdot_in(k) - Hdot_out = 0 (adiabatic: Q = 0, W = 0)",
    "HEAT-mole": "n_in,i - n_out,i = 0 for every component i",
    "HEAT-duty": "Q - (Hdot_out - Hdot_in) = 0, Q positive into the unit",
    "FLASH-mole": "n_in,i - n_vap,i - n_liq,i = 0 for every component i",
    "FLASH-duty": "Q - (Hdot_vap + Hdot_liq - Hdot_in) = 0, Q positive into the unit",
}

TIME_INDEX = DIMENSION_ORDER.index("time")


def declared_equations() -> dict[tuple[str, str], dict[str, Any]]:
    """Every equation of the six declared SYN-001 manifests, keyed by (model id, equation id)."""
    equations: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(MANIFEST_DIR.glob("*.yaml")):
        document = load_yaml(path)
        for equation in (document.get("mathematics") or {}).get("equations") or []:
            equations[(document["id"], equation["id"])] = equation
    return equations


def test_m1_the_registered_classification_is_exactly_the_adr_table() -> None:
    """D3.5: the classification table is normative; a relabelled row fails here."""
    actual = {
        key: equation["accumulation"]["kind"] for key, equation in declared_equations().items()
    }
    assert actual == REGISTERED_KINDS, (
        "the accumulation classification of the SYN-001 manifests no longer matches the table "
        f"registered in ADR 0008 D3.5. Reclassifying a row needs a new Fable-authored ADR. "
        f"See {ADR}."
    )


@pytest.mark.parametrize("equation_id", sorted(REGISTERED_HOLDUPS))
def test_m2_holdup_symbol_and_dimension_are_the_registered_ones(equation_id: str) -> None:
    """D3.2 and D3.5: the named holdup, and the row dimension it implies."""
    equation = next(eq for (_, eq_id), eq in declared_equations().items() if eq_id == equation_id)
    holdup = equation["accumulation"]["holdup"]
    symbol, dimension = REGISTERED_HOLDUPS[equation_id]
    assert (holdup["symbol"], holdup["dimension"]) == (symbol, dimension)
    expected_row = list(dimension)
    expected_row[TIME_INDEX] -= 1
    assert equation["dimension"] == expected_row, (
        f"{equation_id}: a holdup_balance row's dimension is its holdup's dimension with the "
        f"time exponent lowered by one (ADR 0008 D3.2)."
    )


def test_m3_the_whole_vocabulary_is_exercised_with_the_registered_counts() -> None:
    """D3.5: 15 algebraic, 2 zero_holdup_balance, 4 holdup_balance, 21 rows."""
    counts = Counter(equation["accumulation"]["kind"] for equation in declared_equations().values())
    assert counts == Counter({"algebraic": 15, "zero_holdup_balance": 2, "holdup_balance": 4})
    assert sum(counts.values()) == 21


@pytest.mark.parametrize("equation_id", sorted(REGISTERED_STATEMENTS))
def test_m4_balance_rows_are_written_inflow_minus_outflow(equation_id: str) -> None:
    """D3.3: the sign convention, pinned in the manifest text itself.

    The steady-state content of a balance row does not depend on its sign, but its Jacobian row
    does, and `d(holdup)/dt = +F_row` only holds in this orientation. This is pinned before K02
    implements a residual, not after.
    """
    equation = next(eq for (_, eq_id), eq in declared_equations().items() if eq_id == equation_id)
    assert equation["statement"] == REGISTERED_STATEMENTS[equation_id], (
        f"{equation_id}: ADR 0008 D3.3 writes every balance row as inflow − outflow + sources."
    )


def test_m5_every_zero_holdup_balance_states_why_its_holdup_is_zero() -> None:
    """D3.1: a zero row by physics, never by omission."""
    for (model_id, equation_id), equation in declared_equations().items():
        accumulation = equation["accumulation"]
        if accumulation["kind"] != "zero_holdup_balance":
            continue
        reason = accumulation["reason"]
        assert "junction" in reason.lower(), (
            f"{model_id}.{equation_id}: a zero_holdup_balance row states why its holdup is "
            f"identically zero by the model's definition (ADR 0008 D3.1); got {reason!r}."
        )


def test_the_adr_this_module_pins_is_present() -> None:
    """A pin whose ADR has been deleted is not a pin."""
    assert (REPO_ROOT / Path(ADR)).is_file()


# ------------------------------------------------------------------------------------------
# U — physical holdups and the PTC pseudo-holdup (Amendment 1, C3 and U–H)
# ------------------------------------------------------------------------------------------

#: ADR 0008 A1 C3: the `holdup_balance` rows of the unit library registered when the amendment
#: was written (the first twelve), and the twelve Amendment 2 registered at the 0.2.0 cut (T08's
#: kinetic CSTR, the C1 heater and flash, and the three C1 reactor ids: external, stand-in,
#: surrogate). Discovery may find more; it may not find fewer.
REGISTERED_HOLDUP_ROWS: frozenset[tuple[str, str]] = frozenset(
    {
        ("syn001.tp_heater", "HEAT-mole"),
        ("syn001.tp_heater", "HEAT-duty"),
        ("syn001.tp_flash", "FLASH-mole"),
        ("syn001.tp_flash", "FLASH-duty"),
        ("syn001.ph_flash", "PHF-mole"),
        ("syn001.ph_flash", "PHF-duty"),
        ("syn001.conversion_reactor", "RX-mole"),
        ("syn001.conversion_reactor", "RX-duty"),
        ("syn001.heat_exchanger", "HX-mole-hot"),
        ("syn001.heat_exchanger", "HX-mole-cold"),
        ("syn001.heat_exchanger", "HX-energy-hot"),
        ("syn001.heat_exchanger", "HX-energy-cold"),
        # Amendment 2 (A2-F2).
        ("syn001.kinetic_cstr", "CSTR-mole"),
        ("syn001.kinetic_cstr", "CSTR-duty"),
        ("c1.tp_heater", "C1HEAT-mole"),
        ("c1.tp_heater", "C1HEAT-duty"),
        ("c1.tp_flash", "C1FL-mole"),
        ("c1.tp_flash", "C1FL-duty"),
        ("c1.reactor", "C1RX-mole"),
        ("c1.reactor", "C1RX-duty"),
        ("c1.reactor_standin", "C1RX-mole"),
        ("c1.reactor_standin", "C1RX-duty"),
        ("c1.reactor_surrogate", "C1RX-mole"),
        ("c1.reactor_surrogate", "C1RX-duty"),
    }
)

#: ADR 0008 A2 E1: the packages whose modules declare the equations of a bindable model. The
#: surrogate unit's module lives beside its study, outside `openflowsheet.models` (A2-F1).
DECLARATION_PACKAGES: tuple[tuple[Any, str], ...] = (
    (models_package, "openflowsheet.models."),
    (surrogate_package, "openflowsheet.studies.surrogate."),
)

#: The residence-time pseudo-holdup mapping (T04 §6.2), and the PTC-path modules that import it.
PSEUDO_HOLDUP_MODULE = "openflowsheet.orchestrator.mass"
REGISTERED_MASS_IMPORTERS = frozenset(
    {"openflowsheet.orchestrator.executor", "openflowsheet.orchestrator.region"}
)

PACKAGE_ROOT = REPO_ROOT / "src" / "openflowsheet"


def physical_holdup_problems(pairs: Iterable[tuple[str, Holdup]]) -> list[str]:
    """U–H.1: a physical holdup is a rigid vessel's internal energy or its component amounts.

    Returns one message per `(row label, Holdup)` pair that breaks the rule; empty means none.
    """
    problems: list[str] = []
    for label, holdup in pairs:
        symbol, quantity = holdup.symbol, holdup.quantity
        if holdup.dimension == ENERGY:
            if not re.fullmatch(r"U(_[a-z]+)?", symbol):
                problems.append(f"{label}: energy holdup symbol {symbol!r} is not U or U_<side>")
            if not quantity.startswith("internal energy of the "):
                problems.append(f"{label}: energy holdup {quantity!r} is not an internal energy")
            if "enthalpy" in quantity.lower():
                problems.append(f"{label}: energy holdup {quantity!r} names an enthalpy")
        elif holdup.dimension == MOLE:
            if not re.fullmatch(r"N(_[a-z]+)?_i", symbol):
                problems.append(
                    f"{label}: amount holdup symbol {symbol!r} is not N_i or N_<side>_i"
                )
            if not quantity.startswith("component moles held "):
                problems.append(f"{label}: amount holdup {quantity!r} is not component moles held")
        else:
            problems.append(
                f"{label}: holdup {symbol!r} has dimension {holdup.dimension}, neither energy "
                "nor amount"
            )
    return problems


def _is_equation_tuple(value: object) -> bool:
    return isinstance(value, tuple) and all(isinstance(eq, DeclaredEquation) for eq in value)


def equation_configurations(equations: object) -> tuple[Any, ...] | None:
    """A module's `EQUATIONS` as its configurations, or `None` for a form U1 does not know."""
    if _is_equation_tuple(equations):
        return (equations,)
    if isinstance(equations, Mapping) and all(
        _is_equation_tuple(value) for value in equations.values()
    ):
        return tuple(equations.values())
    return None


def module_model_ids(module: object) -> tuple[str, ...] | None:
    """The model ids a module names: its `MODEL_ID`, and every id of a `MODEL_IDS` tuple — one
    class may serve several ids (`models/c1/reactor.py`, A2-F1). `None` when it names none."""
    ids: list[str] = []
    model_id = getattr(module, "MODEL_ID", None)
    if isinstance(model_id, str):
        ids.append(model_id)
    model_ids = getattr(module, "MODEL_IDS", None)
    if isinstance(model_ids, tuple) and all(isinstance(item, str) for item in model_ids):
        ids.extend(item for item in model_ids if item not in ids)
    return tuple(ids) or None


def unit_library_declarations() -> tuple[dict[str, list[tuple[str, Any]]], list[str]]:
    """Every declared configuration, by model id, as `(module, equations)` pairs, over every
    module of `DECLARATION_PACKAGES` that defines `EQUATIONS`; and the modules U1 cannot read —
    an `EQUATIONS` of a form U1 does not know (review F6) or one that names no model id (A2-F1).
    Neither is ever a skip; a bindable model with no declaring module fails E1."""
    declarations: dict[str, list[tuple[str, Any]]] = {}
    unreadable: list[str] = []
    for package, prefix in DECLARATION_PACKAGES:
        for info in pkgutil.walk_packages(package.__path__, prefix):
            module = importlib.import_module(info.name)
            if not hasattr(module, "EQUATIONS"):
                continue
            model_ids = module_model_ids(module)
            configurations = equation_configurations(module.EQUATIONS)
            if model_ids is None or configurations is None:
                unreadable.append(info.name)
                continue
            for model_id in model_ids:
                for configuration in configurations:
                    declarations.setdefault(model_id, []).append((info.name, configuration))
    return declarations, unreadable


def unit_library_holdups() -> tuple[list[tuple[str, str, Holdup, Any]], list[str]]:
    """Every `holdup_balance` row of every model id, in every configuration it declares, and the
    modules U1 cannot read (`unit_library_declarations`)."""
    declarations, unreadable = unit_library_declarations()
    rows: list[tuple[str, str, Holdup, Any]] = []
    for model_id, configurations in declarations.items():
        for _, configuration in configurations:
            for equation in configuration:
                accumulation = equation.accumulation
                if accumulation.kind == "holdup_balance" and accumulation.holdup is not None:
                    rows.append(
                        (model_id, equation.equation_id, accumulation.holdup, equation.dimension)
                    )
    return rows, unreadable


def holdup_row_dimension_problems(rows: Iterable[tuple[str, str, Holdup, Any]]) -> list[str]:
    """A1 W1 (review F6): a `holdup_balance` row's dimension is its holdup's per second — the one
    physical link a constant 0/1 mass matrix relies on."""
    time = DIMENSION_ORDER.index("time")
    problems: list[str] = []
    for model_id, equation_id, holdup, row_dimension in rows:
        expected = list(holdup.dimension)
        expected[time] -= 1
        if row_dimension is None or list(row_dimension) != expected:
            problems.append(
                f"{model_id}#{equation_id}: row dimension {row_dimension} is not the holdup "
                f"{holdup.symbol!r} dimension {list(holdup.dimension)} per second {expected}"
            )
    return problems


def test_u1_physical_holdups_are_internal_energy_and_component_moles() -> None:
    """A1 C3, U–H.1: the unit library accumulates `U` and `N_i`, never an enthalpy."""
    rows, unreadable = unit_library_holdups()
    assert not unreadable, (
        f"model modules whose EQUATIONS U1 cannot read: {unreadable}. A row U1 cannot read is a "
        f"row it does not check; extend `equation_configurations` (ADR 0008 A1 review F6). "
        f"See {ADR}."
    )
    problems = physical_holdup_problems(
        (f"{model_id}#{equation_id}", holdup) for model_id, equation_id, holdup, _ in rows
    )
    assert not problems, (
        "a holdup_balance row declares something other than a control volume's internal energy or "
        "component amounts. The manifests name the physical holdup; the enthalpy content is the "
        f"PTC pseudo-vessel's (ADR 0008 A1 U–H.1, U–H.5). See {ADR}.\n" + "\n".join(problems)
    )
    mismatched = holdup_row_dimension_problems(rows)
    assert not mismatched, (
        "a holdup_balance row's dimension is not its holdup's per second (ADR 0008 A1 U–H, "
        f"W1). See {ADR}.\n" + "\n".join(mismatched)
    )
    missing = REGISTERED_HOLDUP_ROWS - {
        (model_id, equation_id) for model_id, equation_id, _, _ in rows
    }
    assert not missing, (
        f"registered holdup_balance rows were not discovered: {sorted(missing)}. U1 checks "
        f"nothing about a row it cannot find (ADR 0008 A1 U–H). See {ADR}."
    )


def test_u1b_the_holdup_rule_rejects_an_enthalpy_holdup() -> None:
    """A1.7 gate 3: U1's rule can fail, on T04 F2's wording among others."""
    enthalpy = Holdup("H", "enthalpy content at the pinned pressure (U + PV)", ENERGY)
    wrong_dimension = Holdup("U", "internal energy of the contents", MOLE)
    shell_side = Holdup("U_shell", "internal energy of the shell-side contents", ENERGY)
    assert physical_holdup_problems([("F2", enthalpy)])
    # Review F6: an `EQUATIONS` of a form U1 does not know is reported, never skipped.
    assert equation_configurations({"steady": ["not a DeclaredEquation"]}) is None
    assert equation_configurations(None) is None
    # W1's dimension link can fail: an energy row per second declared per unit time squared.
    energy_rate = list(ENERGY)
    energy_rate[DIMENSION_ORDER.index("time")] -= 1
    assert not holdup_row_dimension_problems([("m", "ok", shell_side, tuple(energy_rate))])
    assert holdup_row_dimension_problems([("m", "same", shell_side, ENERGY)])
    assert holdup_row_dimension_problems([("m", "none", shell_side, None)])
    assert physical_holdup_problems([("wrong-dimension", wrong_dimension)])
    assert physical_holdup_problems([("shell-side", shell_side)]) == []


def _resolve_from(node: ast.ImportFrom, module: str, is_package: bool) -> str:
    """The absolute module an `ImportFrom` names, relative levels resolved against `module`."""
    if node.level == 0:
        return node.module or ""
    package = module if is_package else module.rpartition(".")[0]
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def imports_pseudo_holdup_mapping(source: str, module: str, *, is_package: bool = False) -> bool:
    """U2's detector: does this module's source import `orchestrator/mass.py`, in any form?"""
    package, _, leaf = PSEUDO_HOLDUP_MODULE.rpartition(".")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            if any(alias.name == PSEUDO_HOLDUP_MODULE for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            target = _resolve_from(node, module, is_package)
            if target == PSEUDO_HOLDUP_MODULE:
                return True
            if target == package and any(alias.name == leaf for alias in node.names):
                return True
        elif isinstance(node, ast.Constant) and node.value == PSEUDO_HOLDUP_MODULE:
            return True
    return False


def test_u2_the_pseudo_holdup_mapping_is_imported_only_by_the_ptc_path() -> None:
    """A1 U–H.5: `mass.py` is a PTC preconditioner, never a physical mass matrix."""
    mass_file = PACKAGE_ROOT / "orchestrator" / "mass.py"
    importers: set[str] = set()
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        if path == mass_file:
            continue
        parts = path.relative_to(PACKAGE_ROOT.parent).with_suffix("").parts
        is_package = parts[-1] == "__init__"
        module = ".".join(parts[:-1] if is_package else parts)
        source = path.read_text(encoding="utf-8")
        if imports_pseudo_holdup_mapping(source, module, is_package=is_package):
            importers.add(module)
    assert importers == REGISTERED_MASS_IMPORTERS, (
        f"the modules importing {PSEUDO_HOLDUP_MODULE} are {sorted(importers)}, registered "
        f"{sorted(REGISTERED_MASS_IMPORTERS)}. A new PTC-path importer is registered here; a "
        f"physical-time integrator may not import it (ADR 0008 A1 U–H.5). See {ADR}."
    )


def test_u2b_the_import_detector_sees_every_form() -> None:
    """A1.7 gate 3: U2's detector can fail, on every import form it claims to see."""
    probe = "openflowsheet.orchestrator.probe"
    flagged = (
        "from openflowsheet.orchestrator.mass import RegionMass",
        "from .mass import resolve_mass",
        "from . import mass",
        "import openflowsheet.orchestrator.mass",
        'importlib.import_module("openflowsheet.orchestrator.mass")',
    )
    ignored = (
        "from openflowsheet.orchestrator.massive import x",
        "from openflowsheet.models import Holdup",
    )
    missed = [source for source in flagged if not imports_pseudo_holdup_mapping(source, probe)]
    false_hits = [source for source in ignored if imports_pseudo_holdup_mapping(source, probe)]
    assert not missed, f"U2's detector missed: {missed}"
    assert not false_hits, f"U2's detector flagged: {false_hits}"


# ------------------------------------------------------------------------------------------
# E — the pins reach every bindable model kind (Amendment 2)
# ------------------------------------------------------------------------------------------

#: ADR 0008 A2 E2: each C1 unit performs its SYN-001 namesake's function (M02 design note §8;
#: R-283), so it conserves the same quantities with the same accumulation kinds.
NAMESAKES: tuple[tuple[str, str], ...] = (
    ("syn001.feed_source", "c1.feed_source"),
    ("syn001.adiabatic_mixer", "c1.adiabatic_mixer"),
    ("syn001.tp_heater", "c1.tp_heater"),
    ("syn001.tp_flash", "c1.tp_flash"),
    ("syn001.stream_splitter", "c1.stream_splitter"),
    ("syn001.product_sink", "c1.product_sink"),
)

#: ADR 0008 A2 E3: the three C1 reactor ids (external, stand-in, surrogate; ADR 0034 D9, ADR 0037
#: D1) are one control volume holding `N_i` and `U`, whichever evaluates the map.
C1_REACTOR_IDS: tuple[str, ...] = ("c1.reactor", "c1.reactor_standin", "c1.reactor_surrogate")


def _per_second(dimension: tuple[int, ...]) -> tuple[int, ...]:
    rate = list(dimension)
    rate[TIME_INDEX] -= 1
    return tuple(rate)


#: What a reactor control volume conserves: amounts and internal energy, each per second.
REACTOR_SIGNATURE: Counter[tuple[Any, ...]] = Counter(
    {
        ("holdup_balance", "N_i", tuple(MOLE), _per_second(tuple(MOLE))): 1,
        ("holdup_balance", "U", tuple(ENERGY), _per_second(tuple(ENERGY))): 1,
    }
)


def conservation_signature(configuration: Iterable[DeclaredEquation]) -> Counter[tuple[Any, ...]]:
    """What a configuration conserves: one `(kind, holdup symbol, holdup dimension, row
    dimension)` per balance row. Algebraic rows conserve nothing and do not appear."""
    signature: Counter[tuple[Any, ...]] = Counter()
    for equation in configuration:
        accumulation = equation.accumulation
        if accumulation.kind == "algebraic":
            continue
        holdup = accumulation.holdup
        signature[
            (
                accumulation.kind,
                None if holdup is None else holdup.symbol,
                None if holdup is None else tuple(holdup.dimension),
                None if equation.dimension is None else tuple(equation.dimension),
            )
        ] += 1
    return signature


def model_signatures(model_id: str) -> set[frozenset[tuple[tuple[Any, ...], int]]]:
    """The distinct conservation signatures over every configuration a model id declares."""
    declarations, _ = unit_library_declarations()
    return {
        frozenset(conservation_signature(configuration).items())
        for _, configuration in declarations.get(model_id, [])
    }


def test_e1_every_bindable_model_has_declarations_u1_reads() -> None:
    """A2 E1 (A2-F1): U1 reads the declarations of every model id `MODEL_BUILDERS` can bind."""
    declarations, unreadable = unit_library_declarations()
    assert not unreadable, (
        f"modules defining EQUATIONS that U1 cannot read: {unreadable} (ADR 0008 A2 E1). See {ADR}."
    )
    missing = sorted(set(MODEL_BUILDERS) - set(declarations))
    assert not missing, (
        f"bindable model ids whose declarations no readiness check reads: {missing}. Add the "
        f"declaring package to DECLARATION_PACKAGES or name the id in the module's MODEL_ID or "
        f"MODEL_IDS (ADR 0008 A2 E1). See {ADR}."
    )


@pytest.mark.parametrize(("syn001_id", "c1_id"), NAMESAKES)
def test_e2_c1_units_conserve_what_their_syn001_namesakes_conserve(
    syn001_id: str, c1_id: str
) -> None:
    """A2 E2 (A2-F3): a relabelled C1 balance row — a junction's included — fails here."""
    expected = model_signatures(syn001_id)
    assert len(expected) == 1, f"{syn001_id}: its configurations disagree on what it conserves"
    assert model_signatures(c1_id) == expected, (
        f"{c1_id} no longer conserves what {syn001_id} conserves (kind, holdup, dimension per "
        f"balance row). Reclassifying a row needs a design-lane ADR (ADR 0008 D3, A2 E2). See "
        f"{ADR}."
    )


@pytest.mark.parametrize("model_id", C1_REACTOR_IDS)
def test_e3_every_c1_reactor_kind_holds_amounts_and_internal_energy(model_id: str) -> None:
    """A2 E3 (A2-F2, A2-F7): external, stand-in and surrogate declare one control volume."""
    assert model_signatures(model_id) == {frozenset(REACTOR_SIGNATURE.items())}, (
        f"{model_id}: every declared configuration of a C1 reactor id holds N_i and U on one "
        f"mole and one energy holdup_balance row (ADR 0008 A2 E3). See {ADR}."
    )


def test_e1b_e2b_the_reach_and_the_signature_can_fail() -> None:
    """A1.7 gate 3 for group E: each new check is shown able to fail."""
    assert module_model_ids(SimpleNamespace()) is None
    assert module_model_ids(SimpleNamespace(MODEL_ID="m", MODEL_IDS=("m", "n"))) == ("m", "n")
    assert module_model_ids(SimpleNamespace(MODEL_IDS=("m", 1))) is None
    declarations, _ = unit_library_declarations()
    (_, mixer), *_ = declarations["c1.adiabatic_mixer"]
    relabelled = tuple(
        replace(equation, accumulation=Accumulation(kind="algebraic"))
        if equation.accumulation.kind == "zero_holdup_balance"
        else equation
        for equation in mixer
    )
    assert conservation_signature(relabelled) != conservation_signature(mixer)
    (_, heater), *_ = declarations["c1.tp_heater"]
    enthalpy = Holdup("H", "enthalpy content at the pinned pressure (U + PV)", ENERGY)
    renamed = tuple(
        replace(equation, accumulation=Accumulation(kind="holdup_balance", holdup=enthalpy))
        if equation.accumulation.holdup is not None and equation.accumulation.holdup.symbol == "U"
        else equation
        for equation in heater
    )
    assert conservation_signature(renamed) != conservation_signature(heater)
