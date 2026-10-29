"""DOC (S14): the example notebooks in `examples/` run, and say what they compute.

Each notebook is executed here — its code cells in order, in a fresh interpreter, from the
repository root — and the numbers its closing cell states in bold are recomputed and compared,
digit for digit at the precision the page prints. A change to the code that moves a stated
number fails this test until the page is updated, so the published examples cannot drift from
what the software does. The documentation build (`mkdocs build`, `.github/workflows/site.yml`)
executes the same notebooks again to render their output.

The comparison is of a demonstration with its own text. It is regression of the documentation,
not verification or validation of the numbers (the evidence manifests carry those).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT

EXAMPLES = REPO_ROOT / "examples"

#: Notebook -> (Python expression over the notebook's names, the text its closing cell states).
STATED: dict[str, list[tuple[str, str]]] = {
    "rankine-cycle.ipynb": [
        ("f'{efficiency:.4f}'", "0.2892"),
        ("f'{-w_turbine:.1f} W'", "15905.1 W"),
        ("f'{q_boiler:.1f} W'", "54752.5 W"),
        ("f\"{state['S4.sat.V']:.4f}\"", "0.9017"),
        ("certificate['verification_status']", "VERIFIED"),
    ],
    "refrigeration-cycle.ipynb": [
        ("f'{cop:.3f}'", "2.959"),
        ("f'{w_compressor:.1f} W'", "4728.6 W"),
        ("f'{q_evaporator:.1f} W'", "13990.9 W"),
        ("f\"{state['S4.sat.V']:.4f}\"", "0.3344"),
    ],
    "methanol-water-column.ipynb": [
        ("f'{d_total:.4f} mol/s'", "0.4000 mol/s"),
        ("f\"{x_d['CH3OH']:.4f}\"", "0.9941"),
        ("f\"{x_b['CH3OH']:.6f}\"", "0.003916"),
        ("run.verification_status", "VERIFIED"),
    ],
    "what-if-and-refusals.ipynb": [
        ("f'{efficiencies[573.15]:.4f}'", "0.2786"),
        ("f'{efficiencies[773.15]:.4f}'", "0.3020"),
        ("run.outcome", "INITIALIZATION_FAILED"),
        ("'model_unsupported(thermal.pump)' if 'model_unsupported(thermal.pump)' in "
         "check.message else check.message", "model_unsupported(thermal.pump)"),
    ],
}

#: Notebook -> the optional module it needs; without it the notebook prints a stated skip.
NEEDS: dict[str, str] = {"refrigeration-cycle.ipynb": "CoolProp"}

_DRIVER = """
import json, sys
notebook = json.load(open(sys.argv[1], encoding="utf-8"))
expressions = json.loads(sys.argv[2])
namespace = {"__name__": "__main__"}
for cell in notebook["cells"]:
    if cell["cell_type"] == "code":
        exec(compile("".join(cell["source"]), sys.argv[1], "exec"), namespace)
print("\\n@@STATED@@" + json.dumps([str(eval(e, namespace)) for e in expressions]))
"""


def _cells(path: Path, kind: str) -> list[str]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    return ["".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == kind]


def test_every_example_notebook_is_registered_and_carries_no_output() -> None:
    notebooks = sorted(path.name for path in EXAMPLES.glob("*.ipynb"))
    assert notebooks == sorted(STATED)
    for name in notebooks:
        notebook = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                assert cell["outputs"] == [] and cell["execution_count"] is None, name


@pytest.mark.parametrize("name", sorted(STATED))
def test_the_page_states_each_number_it_checks(name: str) -> None:
    closing = _cells(EXAMPLES / name, "markdown")[-1]
    for _, stated in STATED[name]:
        if stated[0].isdigit():
            assert f"**{stated}**" in closing, (name, stated)


@pytest.mark.parametrize("name", sorted(STATED))
def test_the_example_runs_and_reproduces_its_stated_numbers(name: str) -> None:
    module = NEEDS.get(name)
    if module is not None and importlib.util.find_spec(module) is None:
        pytest.skip(f"{name} needs the optional {module!r} package, which is not installed")
    expressions = [expression for expression, _ in STATED[name]]
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join([str(REPO_ROOT / "src")])}
    completed = subprocess.run(
        [sys.executable, "-c", _DRIVER, str(EXAMPLES / name), json.dumps(expressions)],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-4000:]
    computed = json.loads(completed.stdout.rsplit("@@STATED@@", 1)[1])
    assert computed == [stated for _, stated in STATED[name]], completed.stdout[-2000:]
