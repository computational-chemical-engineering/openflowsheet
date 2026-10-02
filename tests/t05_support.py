"""Shared support for T05's unit-model tests: the registered reference and how to read it.

Not collected as tests. Every expected number the T05 tests use comes from
`benchmarks/t05/reference_values.yaml` (the design lane's 40-digit twin, T05 spec §16), read here
once; no test copies a registered value into its source. Tolerances are T05 spec §14's, taken from
the YAML's `constants.tolerances` where it registers them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from conftest import load_yaml

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.syn001 import Syn001Provider

REPO_ROOT = Path(__file__).resolve().parents[1]
REF: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "t05" / "reference_values.yaml")

PROVIDER = Syn001Provider()
#: The context unit blocks are built with. The compiled path checks its own context against the
#: compiled metadata; the causal evaluators and the provider do not read it.
CONTEXT = EvaluationContext(
    model_version="T05-unit-evaluator@" + "0" * 64, constants_sha256="0" * 64
)

_TOLERANCES = REF["constants"]["tolerances"]
#: T05 spec §14: unit-case `T`, flows and extent, duty and work, pressure.
TEMPERATURE_TOLERANCE = float(_TOLERANCES["temperature"])
FLOW_TOLERANCE = float(_TOLERANCES["molar_flow"])
ENERGY_TOLERANCE = float(_TOLERANCES["heat_rate"])
PRESSURE_TOLERANCE = float(_TOLERANCES["pressure"])
#: T05 spec §14: unit-case `beta`, ADR 0001 D6's composition tolerance. The YAML's tolerance table
#: is per row kind and has no vapour-fraction entry, so this one is the document's.
BETA_TOLERANCE = 1e-10


def cases(model_id: str) -> list[str]:
    """The registered unit cases of one model, in the YAML's order."""
    return [key for key, case in REF["unit_cases"].items() if case["model"] == model_id]


def specification_errors(model_id: str) -> list[str]:
    return [key for key, case in REF["specification_errors"].items() if case["model"] == model_id]


def stream(document: Mapping[str, Any]) -> StreamState:
    """A registered stream (`n_mol_per_s`, `T_K`, `P_Pa`) as the doubles its strings round to."""
    return StreamState(
        n=tuple(float(value) for value in document["n_mol_per_s"]),
        temperature=float(document["T_K"]),
        pressure=float(document["P_Pa"]),
    )


def error(got: float, expected: str) -> float:
    """`|got - expected|` with the registered 20-digit string taken at its full precision."""
    return float(abs(Decimal(got) - Decimal(expected)))


def first_line(message: str) -> str:
    """The typed-failure code: the message's first line, or `""` for an empty message (§3.5)."""
    lines = message.splitlines()
    return lines[0] if lines else ""


def assert_flows(got: Sequence[float], expected: Sequence[str], what: str) -> None:
    """Flows within §14's tolerance; a registered `0.0` must be exactly `0.0` (§14, A14)."""
    assert len(got) == len(expected), what
    for index, (value, registered) in enumerate(zip(got, expected, strict=True)):
        if Decimal(registered) == 0:
            assert value == 0.0, f"{what}[{index}] = {value!r}, registered exactly zero"
        else:
            assert error(value, registered) <= FLOW_TOLERANCE, (
                f"{what}[{index}] = {value!r}, registered {registered}"
            )


def assert_close(got: float | None, expected: str, tolerance: float, what: str) -> None:
    assert got is not None, f"{what} missing"
    assert error(got, expected) <= tolerance, f"{what} = {got!r}, registered {expected}"
