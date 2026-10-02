"""Emit, or check, T05b's B02 baseline: every registered `ph_state` call of T05, bit for bit.

T05b spec §5.4 and §14 B02 (`docs/derivations/T05b-limitations-spec.md`): the kernel's new
acceptance (§5.3) and its band route may change an answer only where T05's answer failed the
closure's rows, and no registered call is such a place. B02 asserts it on the outputs: every
`ph_state` call T05 registers returns bitwise what it returned before T05b touched the kernel
(W0.1). This script is the committed generator of that baseline (R-015: a fixture nothing
regenerates is not allowed to exist), and `tests/test_t05b_kernel_inert.py` compares a live run
with the committed file.

**What is recorded.** Every call the three PH-type models make to `ph_state` while
(1) evaluating each registered unit case of `syn001.ph_flash`, `syn001.valve` and
`syn001.conversion_reactor` (`ref.unit_cases` of T05, by the model tests' own `unit_for`), and
(2) solving C1, C2, C3 and C3X through the general path (`test_t05_coupled.solve`, policy
`T05-W13`; the traversals' causal calls, and any other). Per call: the inputs and every field of
the answer (status, code, message, temperature, route, evaluations, residual, and the split's
signature, streams, vapour fraction, enthalpy, K-values and counters). Per unit case also the
unit's own answer (status, message, outlets, duty, work, extent, signature). Floats are written
as `float.hex()`, so the comparison is exact, signed zeros included.

Usage (from the repository root):
    PYTHONPATH=src:. .venv/bin/python scripts/t05b_ph_baseline.py --emit
    PYTHONPATH=src:. .venv/bin/python scripts/t05b_ph_baseline.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

FIXTURE = ROOT / "tests" / "fixtures" / "t05b" / "ph_state_baseline.json"

#: The model modules that call the kernel, each through its own imported name.
CALLERS = (
    "openflowsheet.models.syn001.ph_flash",
    "openflowsheet.models.syn001.valve",
    "openflowsheet.models.syn001.conversion_reactor",
)
#: T05's coupled cases (design note §6), solved as its gate solves them.
COUPLED = ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3", "SYN-001-UL-C3X")


def _x(value: float | None) -> str | None:
    return None if value is None else float(value).hex()


def _stream(state: Any) -> dict[str, Any] | None:
    if state is None:
        return None
    return {
        "n": [_x(v) for v in state.n],
        "T": _x(state.temperature),
        "P": _x(state.pressure),
    }


def _split(split: Any) -> dict[str, Any] | None:
    if split is None:
        return None
    return {
        "status": split.status,
        "phase_signature": split.phase_signature,
        "vapor": _stream(split.vapor),
        "liquid": _stream(split.liquid),
        "vapor_fraction": _x(split.vapor_fraction),
        "enthalpy_flow": _x(split.enthalpy_flow),
        "k_values": {name: _x(v) for name, v in sorted(split.k_values.items())},
        "iterations": split.iterations,
        "provider_id": split.provider_id,
        "reference_convention": split.reference_convention,
        "message": split.message,
    }


def _answer(state: Any) -> dict[str, Any]:
    return {
        "status": state.status,
        "code": state.code,
        "message": state.message,
        "temperature": _x(state.temperature),
        "route": state.route,
        "evaluations": state.evaluations,
        "residual": _x(state.residual),
        "split": _split(state.split),
    }


def _unit_answer(result: Any) -> dict[str, Any]:
    return {
        "status": result.status,
        "message": result.message,
        "phase_signature": result.phase_signature,
        "outlets": {port: _stream(state) for port, state in sorted(result.outlets.items())},
        "duty": _x(result.duty),
        "work": _x(result.work),
        "extent": _x(result.extent),
    }


@contextmanager
def recording(calls: list[dict[str, Any]]) -> Iterator[None]:
    """Route every model's `ph_state` through a recorder; restore the originals on exit."""
    import importlib  # noqa: PLC0415

    modules = [importlib.import_module(name) for name in CALLERS]
    originals = [module.ph_state for module in modules]

    def recorder(original: Callable[..., Any], caller: str) -> Callable[..., Any]:
        def ph_state(
            provider: Any,
            flows: Sequence[float],
            pressure: float,
            target: float,
            context: Any,
            **keywords: Any,
        ) -> Any:
            answer = original(provider, flows, pressure, target, context, **keywords)
            calls.append(
                {
                    "caller": caller.rsplit(".", 1)[-1],
                    "inputs": {
                        "flows": [_x(v) for v in flows],
                        "pressure": _x(pressure),
                        "target": _x(target),
                        "keywords": {k: repr(v) for k, v in sorted(keywords.items())},
                    },
                    "answer": _answer(answer),
                }
            )
            return answer

        return ph_state

    try:
        for module, original, name in zip(modules, originals, CALLERS, strict=True):
            module.ph_state = recorder(original, name)  # type: ignore[attr-defined]
        yield
    finally:
        for module, original in zip(modules, originals, strict=True):
            module.ph_state = original  # type: ignore[attr-defined]


def _unit_cases() -> dict[str, Any]:
    import t05_support as support  # noqa: PLC0415
    import test_t05_ph_flash  # noqa: PLC0415
    import test_t05_reactor  # noqa: PLC0415
    import test_t05_valve  # noqa: PLC0415

    builders: Mapping[str, Callable[[Mapping[str, Any]], Any]] = {
        "syn001.ph_flash": test_t05_ph_flash.unit_for,
        "syn001.valve": test_t05_valve.unit_for,
        "syn001.conversion_reactor": test_t05_reactor.unit_for,
    }
    document: dict[str, Any] = {}
    for model_id, build in builders.items():
        for case_id in support.cases(model_id):
            inputs = support.REF["unit_cases"][case_id]["inputs"]
            calls: list[dict[str, Any]] = []
            with recording(calls):
                result = build(inputs).evaluate(
                    {"inlet": [support.stream(inputs["inlet"])]}, support.CONTEXT
                )
            document[case_id] = {"model": model_id, "unit": _unit_answer(result), "calls": calls}
    return document


def _coupled_cases() -> dict[str, Any]:
    from test_t05_coupled import solve  # noqa: PLC0415

    document: dict[str, Any] = {}
    for case in COUPLED:
        calls: list[dict[str, Any]] = []
        with recording(calls):
            solved = solve(case)
        document[case] = {"outcome": solved.run.outcome, "calls": calls}
    return document


def _kernel_targets() -> dict[str, Any]:
    """T05 W0.4's direct calls (`test_t05_ph_kernel.PH_TYPE`, targets from the registered
    strings): the kernel alone, at the eight PH-type cases' registered closures."""
    import t05_support as support  # noqa: PLC0415
    import test_t05_ph_kernel as kernel  # noqa: PLC0415

    from openflowsheet.models.syn001.ph_kernel import ph_state  # noqa: PLC0415

    document: dict[str, Any] = {}
    for case_id in kernel.PH_TYPE:
        n, pressure, target = kernel.kernel_target(case_id)
        answer = ph_state(support.PROVIDER, n, pressure, target, support.CONTEXT)
        document[case_id] = {
            "inputs": {
                "flows": [_x(v) for v in n],
                "pressure": _x(pressure),
                "target": _x(target),
            },
            "answer": _answer(answer),
        }
    return document


def collect() -> dict[str, Any]:
    """The baseline document, from a live run of the code as it is."""
    return {
        "generator": "scripts/t05b_ph_baseline.py",
        "specification": "docs/derivations/T05b-limitations-spec.md §5.4, §14 B02",
        "unit_cases": _unit_cases(),
        "kernel_targets": _kernel_targets(),
        "coupled_cases": _coupled_cases(),
    }


def render(document: Mapping[str, Any]) -> str:
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--emit", action="store_true", help=f"write {FIXTURE.relative_to(ROOT)}")
    group.add_argument("--check", action="store_true", help="compare a live run with the file")
    args = parser.parse_args(argv)
    text = render(collect())
    if args.emit:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(text)
        print(f"wrote {FIXTURE.relative_to(ROOT)}")
        return 0
    if FIXTURE.read_text() != text:
        print(f"{FIXTURE.relative_to(ROOT)} differs from a live run")
        return 1
    print(f"{FIXTURE.relative_to(ROOT)} matches a live run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
