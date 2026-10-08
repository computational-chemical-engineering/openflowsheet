"""M05 gate G13 (design note §13; ADR 0038 D2; R-003, R-261): no second model and no backend.

The projection is the canonical `ProblemSpec` evaluated with a `PyomoAlgebra`; it must stay that.
Checked by inspection of the source (AST, so a commented or quoted name cannot pass or fail it):

- the glass-box modules import nothing from `openflowsheet.models` — a row or property equation
  re-authored there would be a second model;
- `pyomo` is imported only under `studies/nlp/` and `studies/trust_region/` (ADR 0038's
  allow-list), and under `studies/trust_region/` only by `projection`;
- nothing outside `studies/trust_region/` imports it or names `PyomoAlgebra`, so no route and no
  `compile_problem` path can reach it;
- the Pyomo-free modules of the package import with Pyomo blocked (M03 G6's rule; the walk of
  every other module is `tests/test_m03_nlp_isolation.py`'s).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from conftest import REPO_ROOT

SRC = REPO_ROOT / "src"
PACKAGE = SRC / "openflowsheet" / "studies" / "trust_region"
PYOMO_PACKAGES = (
    SRC / "openflowsheet" / "studies" / "nlp",
    PACKAGE,
)
PYOMO_MODULES_IN_PACKAGE = {"projection.py"}
GLASS_BOX_MODULES = ("projection.py", "holders.py")


def imported_modules(path: Path) -> set[str]:
    """Every module an `import` or `from … import` statement in `path` names (absolute or
    resolved relative), at any nesting depth."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = ".".join(path.relative_to(SRC).with_suffix("").parts[:-1])
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[: len(package.split(".")) - node.level + 1]
                module = ".".join([*base, node.module] if node.module else base)
            else:
                module = node.module or ""
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def names_used(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    found |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    found |= {
        alias.name.split(".")[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom | ast.Import)
        for alias in node.names
    }
    return found


def test_the_glass_box_imports_nothing_from_the_models() -> None:
    for name in GLASS_BOX_MODULES:
        offending = sorted(
            module
            for module in imported_modules(PACKAGE / name)
            if module == "openflowsheet.models" or module.startswith("openflowsheet.models.")
        )
        assert not offending, f"{name} imports {offending}: a second model (plan L271, R-003)"


def test_pyomo_is_imported_only_where_adr_0038_allows() -> None:
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        pyomo = {m for m in imported_modules(path) if m == "pyomo" or m.startswith("pyomo.")}
        if not pyomo:
            continue
        if not any(path.is_relative_to(allowed) for allowed in PYOMO_PACKAGES):
            offenders.append(str(path.relative_to(REPO_ROOT)))
        elif path.is_relative_to(PACKAGE) and path.name not in PYOMO_MODULES_IN_PACKAGE:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"{offenders} import Pyomo outside ADR 0038's allow-list"


def test_no_route_or_compile_path_reaches_the_projection() -> None:
    """`PyomoAlgebra` is named, and `studies.trust_region` imported, only inside the package."""
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path.is_relative_to(PACKAGE):
            continue
        reaches = any(
            module == "openflowsheet.studies.trust_region"
            or module.startswith("openflowsheet.studies.trust_region.")
            for module in imported_modules(path)
        )
        if reaches or "PyomoAlgebra" in names_used(path):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"{offenders} reach the trust-region projection (R-003)"


def test_the_import_detector_sees_every_form(tmp_path: Path) -> None:
    """The checks above are only as good as `imported_modules`; it must see each spelling."""
    sample = PACKAGE / "_detector_sample.py"
    text = (
        "import pyomo\n"
        "import pyomo.environ as pe\n"
        "from pyomo.opt import SolverFactory\n"
        "def late():\n"
        "    from openflowsheet.models.syn001 import flowsheet\n"
        "from . import projection\n"
        "from .holders import EFHolder\n"
    )
    try:
        sample.write_text(text, encoding="utf-8")
        found = imported_modules(sample)
    finally:
        sample.unlink()
    assert {"pyomo", "pyomo.environ", "pyomo.opt", "openflowsheet.models.syn001"} <= found
    assert "openflowsheet.studies.trust_region.projection" in found
    assert "openflowsheet.studies.trust_region.holders" in found


def test_the_pyomo_free_modules_import_with_pyomo_blocked() -> None:
    program = (
        "import sys\n"
        "sys.modules['pyomo'] = None\n"
        "import openflowsheet.studies.trust_region\n"
        "import openflowsheet.studies.trust_region.holders\n"
        "assert not [m for m in sys.modules if m.startswith('pyomo.')]\n"
        "print('ok')\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"
