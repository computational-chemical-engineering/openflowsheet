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
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT

EXAMPLES = REPO_ROOT / "examples"
SITE = REPO_ROOT / "docs-site"
CHANGE_SET = EXAMPLES / "rankine-cycle.changeset.json"

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
        (
            "'model_unsupported(thermal.pump)' if 'model_unsupported(thermal.pump)' in "
            "check.message else check.message",
            "model_unsupported(thermal.pump)",
        ),
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


def _blocks(page: Path, language: str) -> list[str]:
    """The fenced code blocks of `language` in a documentation page, in order."""
    blocks, current = [], None
    for line in page.read_text(encoding="utf-8").splitlines():
        if current is None and line.strip() == f"```{language}":
            current = []
        elif current is not None and line.strip() == "```":
            blocks.append("\n".join(current))
            current = None
        elif current is not None:
            current.append(line)
    return blocks


def _run(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        arguments, cwd=cwd, env=environment, capture_output=True, text=True, timeout=900
    )


def test_the_change_set_creates_the_rankine_notebooks_revision() -> None:
    """The quickstart's change set is the Rankine notebook's document, member for member."""
    namespace: dict[str, object] = {}
    for source in _cells(EXAMPLES / "rankine-cycle.ipynb", "code")[:2]:
        exec(compile(source, "rankine-cycle.ipynb", "exec"), namespace)
    document = namespace["rankine"]
    assert isinstance(document, dict)
    change_set = json.loads(CHANGE_SET.read_text(encoding="utf-8"))
    edits = {edit["path"][0]: edit["value"] for edit in change_set["edits"]}
    assert all(edit["operation"] == "set" for edit in change_set["edits"])
    assert edits == document


def test_the_quickstart_python_block_runs(tmp_path: Path) -> None:
    (python,) = [block for block in _blocks(SITE / "getting-started/quickstart.md", "python")][:1]
    (tmp_path / CHANGE_SET.name).write_bytes(CHANGE_SET.read_bytes())
    completed = _run([sys.executable, "-c", python], tmp_path)
    assert completed.returncode == 0, completed.stderr[-4000:]
    lines = completed.stdout.splitlines()
    assert lines[:2] == ["READY_FOR_SIMULATION", "CONVERGED VERIFIED"]
    work, duty = (float(value) for value in lines[2].split())
    assert (f"{work:.1f}", f"{duty:.1f}") == ("-15905.1", "54752.5")


def test_the_quickstart_command_lines_run(tmp_path: Path) -> None:
    """Every `openflowsheet` command of the quickstart's CLI section, in order."""
    (tmp_path / CHANGE_SET.name).write_bytes(CHANGE_SET.read_bytes())
    commands = " ".join(
        block.replace("\\\n", " ")
        for block in _blocks(SITE / "getting-started/quickstart.md", "bash")
    )
    responses = []
    for line in commands.split("openflowsheet ")[1:]:
        arguments = shlex.split(line)
        completed = _run(
            [sys.executable, "-m", "openflowsheet.application.cli", *arguments], tmp_path
        )
        assert completed.returncode == 0, (line, completed.stderr[-2000:])
        responses.append(completed.stdout)
    assert len(responses) == 5
    solve, work, verdict = (json.loads(r) for r in responses[2:])
    assert (solve["outcome"], solve["verification_status"]) == ("CONVERGED", "VERIFIED")
    assert f"{work['value']:.2f}" == "-15905.09" and verdict["value"] == "VERIFIED"


def test_the_first_flowsheet_tutorial_runs(tmp_path: Path) -> None:
    source = "\n\n".join(_blocks(SITE / "tutorials/first-flowsheet.md", "python"))
    completed = _run([sys.executable, "-c", source], tmp_path)
    assert completed.returncode == 0, completed.stderr[-4000:]
    assert completed.stdout.splitlines()[-1] == "CONVERGED VERIFIED", completed.stdout
