"""T05 review S4: R-016 for the verifier table, pinned by its imports.

Spec `docs/derivations/T05-unit-models-spec.md` §12.1 and design note
`docs/design/T05-generalization.md` §4.1: `verify/table.py` shares ids and the revision's values
with the solver and nothing else — no row builder, causal evaluator, kernel, `admission.py` or
unit class. The cross-validation compares legacy with general, not general with the solver, so a
later edit that called, say, `ph_kernel.port_enthalpy` would pass every other test. This one reads
the module's import statements (anywhere in the file, function bodies included):

- from `openflowsheet.models…` only the id helpers and the revision view types are named;
- `openflowsheet.models.rows`, `models.syn001.{ph_kernel, admission, blocks}` and
  `openflowsheet.compile…` are not imported at all, nor is any `openflowsheet.models…` module
  as a module;
- `openflowsheet.orchestrator…` only for `LiftedSplit`, and only under `TYPE_CHECKING`.

Shared ids are sanctioned (note §4.1); shared functions are not, and copying the helpers into the
table would defeat the point (review §7), so the allow-list names them where they live.

T05b W1 (spec §9.5, R-016) extends the rule to the verifier's own saturation band,
`verify/saturation.py`, and adds the unit layer's band (`models.syn001.saturation_band`) and the
bisection it shares with the kernel (`models.syn001.bisection`) to the forbidden modules. The band
module needs no id at all, so it is held to the stricter rule: nothing from the models.

T05b W4 (spec §9.3, §9.5) extends it to the verifier's zero-flow form, `verify/zero_flow.py`, held
to the table's rule: the split descriptor (`LiftedSplit`, typing only), the revision's views and
the id helpers — now including `row_id`, the row-id helper beside the column ones — and nothing
of the solver's (no region, splits registry or model). The table's new degeneracy judgement
(§9.1–§9.2) reads only `verify.saturation`, which the earlier rule already covers.

K04-F9 W1 (ADR 0013 D1; R-016 as amended by R-059) extends it to the verifier's Newton
projection, `verify/projection.py`, held to the strictest rule: nothing from the models, the
orchestrator or the compiler, and from the numerics only `numerics.linear.factorize` — the
factorization the regularity screen itself uses. Its matrix, residual and rows are the
certificate's own, passed in.
"""

from __future__ import annotations

import ast
from pathlib import Path

VERIFY = Path(__file__).resolve().parents[1] / "src" / "openflowsheet" / "verify"
TABLE = VERIFY / "table.py"
SATURATION = VERIFY / "saturation.py"
ZERO_FLOW = VERIFY / "zero_flow.py"
PROJECTION = VERIFY / "projection.py"

#: Review S4's allow-list: the id helpers and the revision view types.
ALLOWED_MODEL_NAMES = frozenset(
    {
        "duty_id",
        "flow_id",
        "pressure_id",
        "temperature_id",
        "extent_id",
        "total_flow_id",
        "work_id",
        "vapor_flow_id",
        "liquid_flow_id",
        "vapor_total_id",
        "liquid_total_id",
        "row_id",
        "InstanceView",
        "RevisionView",
    }
)
#: Never imported, in any form.
FORBIDDEN_MODULES = (
    "openflowsheet.models.rows",
    "openflowsheet.models.syn001.ph_kernel",
    "openflowsheet.models.syn001.admission",
    "openflowsheet.models.syn001.blocks",
    "openflowsheet.models.syn001.saturation_band",
    "openflowsheet.models.syn001.bisection",
    "openflowsheet.compile",
)
ALLOWED_ORCHESTRATOR_NAMES = frozenset({"LiftedSplit"})


def _within(module: str, package: str) -> bool:
    return module == package or module.startswith(package + ".")


def _type_checking_nodes(tree: ast.Module) -> set[int]:
    """The ids of every node inside an `if TYPE_CHECKING:` block."""
    inside: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and (
            (isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING")
            or (isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING")
        ):
            for statement in node.body:
                inside.update(id(child) for child in ast.walk(statement))
    return inside


def violations(source: str) -> list[str]:
    """Every import of `source` the rule above does not admit, as `line: statement`."""
    tree = ast.parse(source)
    typing_only = _type_checking_nodes(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _within(alias.name, "openflowsheet.models") or any(
                    _within(alias.name, forbidden) for forbidden in FORBIDDEN_MODULES
                ):
                    found.append(f"{node.lineno}: import {alias.name}")
                if _within(alias.name, "openflowsheet.orchestrator") or alias.name == "importlib":
                    found.append(f"{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            where = f"{node.lineno}: from {module} import {', '.join(names)}"
            if node.level or module == "importlib":
                found.append(where)
            elif any(_within(module, forbidden) for forbidden in FORBIDDEN_MODULES):
                found.append(where)
            elif _within(module, "openflowsheet.models"):
                if any(name not in ALLOWED_MODEL_NAMES for name in names):
                    found.append(where)
            elif _within(module, "openflowsheet.orchestrator") and (
                id(node) not in typing_only
                or any(name not in ALLOWED_ORCHESTRATOR_NAMES for name in names)
            ):
                found.append(where)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "__import__":
                found.append(f"{node.lineno}: __import__(...)")
    return found


def test_the_table_imports_only_ids_and_views_from_the_models() -> None:
    source = TABLE.read_text()
    assert violations(source) == []
    # The rule is not vacuous on the file as it stands: it does import from the models.
    assert "from openflowsheet.models.syn001.pump import work_id" in source


def test_a_kernel_import_fails_it() -> None:
    """The review's falsifiable test, and one per forbidden route."""
    source = TABLE.read_text()
    injected = {
        "from openflowsheet.models.syn001.ph_kernel import port_enthalpy": "ph_kernel",
        "from openflowsheet.models.syn001.admission import admitted_enthalpy": "admission",
        "from openflowsheet.models.syn001.pump import LiquidPump": "LiquidPump",
        "from openflowsheet.models.rows import balance_row": "rows",
        "from openflowsheet.models.syn001 import blocks": "blocks",
        "import openflowsheet.models.syn001.valve": "valve",
        "from openflowsheet.compile.casadi_backend import compile_problem": "compile",
        "from openflowsheet.orchestrator.revision import initial_state": "initial_state",
    }
    for line, name in injected.items():
        found = violations(source + f"\n\ndef _smuggled() -> None:\n    {line}\n")
        assert len(found) == 1 and name in found[0], (line, found)


def test_the_verifiers_saturation_band_imports_nothing_from_the_models() -> None:
    """T05b W1: the verifier's bubble and dew temperatures are its own code (R-016)."""
    source = SATURATION.read_text()
    assert violations(source) == []
    tree = ast.parse(source)
    imported = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ] + [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    assert not any(_within(module, "openflowsheet.models") for module in imported), imported
    assert not any(_within(module, "openflowsheet.orchestrator") for module in imported), imported
    # The rule is not vacuous on the file: it does read a provider.
    assert "from openflowsheet.thermo import" in source


def test_a_unit_layer_band_import_fails_both_verifier_modules() -> None:
    injected = {
        "from openflowsheet.models.syn001.saturation_band import band_split": "saturation_band",
        "from openflowsheet.models.syn001.bisection import bracketed_root": "bisection",
        "import openflowsheet.models.syn001.saturation_band": "saturation_band",
    }
    for path in (TABLE, SATURATION):
        source = path.read_text()
        for line, name in injected.items():
            found = violations(source + f"\n\ndef _smuggled() -> None:\n    {line}\n")
            assert len(found) >= 1 and all(name in entry for entry in found), (path, line, found)


def test_the_verifiers_zero_flow_form_imports_only_ids_views_and_the_descriptor() -> None:
    """T05b W4: the zero-flow reduction is the verifier's own reading of spec §7.2 (R-016)."""
    source = ZERO_FLOW.read_text()
    assert violations(source) == []
    # The rule is not vacuous on the file: it does read ids and views from the models.
    assert "from openflowsheet.models import" in source
    assert "from openflowsheet.models.revision_flowsheet import" in source


def test_a_solver_side_zero_flow_import_fails_it() -> None:
    source = ZERO_FLOW.read_text()
    injected = {
        "from openflowsheet.orchestrator.splits import SPLIT_RULES": "SPLIT_RULES",
        "from openflowsheet.orchestrator.region import _admissible": "_admissible",
        "from openflowsheet.orchestrator.roots import branch_found": "branch_found",
        "from openflowsheet.models.syn001.valve import Valve": "Valve",
        "from openflowsheet.models.syn001.tp_state import lifted_rows": "lifted_rows",
        # T05b W7b: the solver's dormancy-form registry and forms.
        "from openflowsheet.orchestrator.splits import DORMANCY_RULES": "DORMANCY_RULES",
        "from openflowsheet.orchestrator.splits import dormancy_forms": "dormancy_forms",
        "from openflowsheet.orchestrator.region import DormancyForm": "DormancyForm",
    }
    for line, name in injected.items():
        found = violations(source + f"\n\ndef _smuggled() -> None:\n    {line}\n")
        assert len(found) == 1 and name in found[0], (line, found)


def test_the_verifiers_dormant_outlets_are_the_solvers_as_data() -> None:
    """T05b W7b (spec §9.3, B23): the verifier's own transcription of spec §7.6's table names the
    same outlets, trigger ports, swapped rows and label rows as the solver's registry, for every
    model and configuration — compared as data here, never imported by the verifier."""
    from openflowsheet.orchestrator.splits import DORMANCY_RULES
    from openflowsheet.verify.zero_flow import DORMANT_OUTLETS

    solver = {
        key: [(rule.outlet, rule.trigger, rule.swapped, rule.side) for rule in rules]
        for key, rules in DORMANCY_RULES.items()
    }
    configurations: dict[str, list[str | None]] = {
        "syn001.liquid_pump": [None],
        "syn001.adiabatic_mixer": [None],
        "syn001.heat_exchanger": ["duty", "hot_outlet_temperature", "cold_outlet_temperature"],
    }
    assert set(DORMANT_OUTLETS) == set(configurations)
    verifier = {
        (model, configuration): [
            (entry.outlet, entry.trigger, entry.swapped, entry.side)
            for entry in DORMANT_OUTLETS[model]
            if entry.unless is None or entry.unless != configuration
        ]
        for model, keys in configurations.items()
        for configuration in keys
    }
    assert verifier == solver


def _imports(source: str) -> list[tuple[str, list[str]]]:
    """Every `(module, names)` a source imports, function bodies and `TYPE_CHECKING` included."""
    found: list[tuple[str, list[str]]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            found.append((node.module or "", [alias.name for alias in node.names]))
        elif isinstance(node, ast.Import):
            found.extend((alias.name, []) for alias in node.names)
    return found


def projection_violations(source: str) -> list[str]:
    """The table's rule, plus: no models, orchestrator or compiler module at all, and from the
    numerics only `factorize` from `numerics.linear`."""
    found = violations(source)
    for module, names in _imports(source):
        if any(
            _within(module, package)
            for package in (
                "openflowsheet.models",
                "openflowsheet.orchestrator",
                "openflowsheet.compile",
            )
        ):
            found.append(f"{module}: {names}")
        elif _within(module, "openflowsheet.numerics") and (
            module != "openflowsheet.numerics.linear" or names != ["factorize"]
        ):
            found.append(f"{module}: {names}")
    return found


def test_the_verifiers_projection_reads_only_the_screens_factorization() -> None:
    """K04-F9 W1 (R-016, R-059): the projection solves with the screen's `factorize` and reads
    nothing of the solver's."""
    source = PROJECTION.read_text()
    assert projection_violations(source) == []
    # The rule is not vacuous on the file: it does factorize, and reads the verifier's rows.
    assert "from openflowsheet.numerics.linear import factorize" in source
    assert "from openflowsheet.verify.checks import" in source


def test_a_solver_side_import_fails_the_projection() -> None:
    source = PROJECTION.read_text()
    injected = {
        "from openflowsheet.numerics.newton import newton_step": "newton",
        "from openflowsheet.numerics.linear import solve_linear": "solve_linear",
        "from openflowsheet.numerics.scaling import Scaling": "scaling",
        "from openflowsheet.orchestrator.region import solve_region": "orchestrator",
        "from openflowsheet.models.syn001.tp_state import lifted_rows": "tp_state",
        "from openflowsheet.compile.reference import state_vector": "compile",
        "import openflowsheet.models.syn001.flash": "flash",
    }
    for line, name in injected.items():
        found = projection_violations(source + f"\n\ndef _smuggled() -> None:\n    {line}\n")
        assert len(found) >= 1 and all(name in entry for entry in found), (line, found)
