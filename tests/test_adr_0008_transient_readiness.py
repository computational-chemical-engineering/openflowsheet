"""ADR 0008 — transient-extension readiness: the pins, not the numerics.

Every assertion in this module pins a *decision* recorded in
`docs/adr/0008-transient-extension-readiness.md`. None of them is a numerical result, and none
establishes that anything works. They exist so that a later session cannot silently undo a choice
that was made deliberately: a time coordinate at the evaluation boundary (group A, D1), a state
hash that stops covering all of `x` (group H, D2), or a relabelled accumulation declaration in a
SYN-001 manifest (group M, D3). Amendment 1 adds group U: a physical holdup that turns into an
enthalpy, or a module outside the PTC path that imports the residence-time pseudo-holdup mapping.
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
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml

import openflowsheet.models as models_package

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
from openflowsheet.canonical import state_sha256 as _production_state_sha256
from openflowsheet.compiled import (
    CompiledProblem,
    EvaluationContext,
    EvaluationResult,
    JacobianResult,
)
from openflowsheet.models import DeclaredEquation, Holdup
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
#: was written. Discovery may find more; it may not find fewer.
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
    }
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


def unit_library_holdups() -> tuple[list[tuple[str, str, Holdup, Any]], list[str]]:
    """Every `holdup_balance` row of every model module, in every configuration it declares, and
    the modules with a `MODEL_ID` whose `EQUATIONS` has a form U1 cannot read (review F6)."""
    rows: list[tuple[str, str, Holdup, Any]] = []
    unreadable: list[str] = []
    for info in pkgutil.walk_packages(models_package.__path__, "openflowsheet.models."):
        module = importlib.import_module(info.name)
        model_id = getattr(module, "MODEL_ID", None)
        if not isinstance(model_id, str):
            continue
        configurations = equation_configurations(getattr(module, "EQUATIONS", None))
        if configurations is None:
            unreadable.append(info.name)
            continue
        for configuration in configurations:
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
