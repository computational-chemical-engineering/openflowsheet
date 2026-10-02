"""K04-F9 X00: the reference file and its generator (spec §9; ADR 0013 acceptance evidence).

The fast half of X00 is here: the committed YAML's SHA-256 is the specification's, the generator
(`docs/derivations/scripts/k04f9_reference.py`) imports nothing from `openflowsheet` or
`benchmarks` — nor do the sibling twins it imports — and the four reference files it builds on
are the ones their specifications registered before F9 (T04, T05, T05b) or their last emission
(K04). The slow half — `--check` re-deriving the 25 claims and `--emit` twice byte-identical,
about three minutes each — is run for the evidence manifest (W0, W7), not on every gate.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "docs" / "derivations" / "scripts"
GENERATOR = SCRIPTS / "k04f9_reference.py"
REFERENCE = ROOT / "benchmarks" / "k04f9" / "reference_values.yaml"
#: Spec header and §9.
REFERENCE_SHA256 = "73be8df910d13425273f1ef2ad87d4771e4e1c92e66bd128e69231b98a13e3b7"
#: The files F9 does not move (X00): T04, T05, T05b as their specifications register them; K04's
#: as last emitted (T03 W8, `5fb5da6`). T05b's moved on its specification's re-emission of
#: 2026-09-25 (Q-S9 addendum, `6019d6a`: the section `downstream_flash_cases` added, claims
#: 585 → 630; the claim count is the only existing line that moved).
UNCHANGED = {
    "t04": "4dda7ebe0d7255724e1632487a0a488ed6536b179ed424f29846f22cd27f9467",
    "t05": "af4a543f8dab3d95c32764117be00afbc9e8d49478998e8538a1daf359385a6a",
    "t05b": "cf1a86067f3de92266b1e121ee9711e6e5f235d0bf87657afd231996f5fc807b",
    "k04": "2a1b5ecb25da26f5e381e73e189f21848ce6f2a4fe4a4a47878351d605424c9e",
}
#: The generator's sibling twins (its `import k04_reference as k04` and the like), transitively.
TWINS = ("k04f9_reference", "k04_reference", "t04_reference", "t05b_reference")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_x00_the_committed_reference_is_the_specifications() -> None:
    assert _sha256(REFERENCE) == REFERENCE_SHA256
    document = yaml.safe_load(REFERENCE.read_text())
    assert document["generator"] == "docs/derivations/scripts/k04f9_reference.py"
    assert document["generator_claims"]["count"] == 25
    assert len(document["generator_claims"]["names"]) == 25


@pytest.mark.parametrize("name", sorted(UNCHANGED))
def test_x00_the_reference_files_f9_builds_on_are_unchanged(name: str) -> None:
    assert _sha256(ROOT / "benchmarks" / name / "reference_values.yaml") == UNCHANGED[name]


def _imported(source: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def _closure() -> dict[str, set[str]]:
    """Each twin reachable from the generator through sibling imports, with its imports."""
    pending, seen = ["k04f9_reference"], {}
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen[name] = _imported((SCRIPTS / f"{name}.py").read_text())
        pending += [module for module in seen[name] if (SCRIPTS / f"{module}.py").exists()]
    return seen


def test_x00_the_generator_imports_nothing_from_the_implementation() -> None:
    closure = _closure()
    assert set(TWINS) <= set(closure)  # not vacuous: the siblings are followed
    for name, modules in closure.items():
        leaked = sorted(
            module for module in modules if module.split(".")[0] in ("openflowsheet", "benchmarks")
        )
        assert leaked == [], (name, leaked)


def test_x00_an_implementation_import_is_caught() -> None:
    for line in ("from openflowsheet.verify import checks", "import benchmarks.syn001"):
        modules = _imported(GENERATOR.read_text() + f"\n{line}\n")
        assert any(module.split(".")[0] in ("openflowsheet", "benchmarks") for module in modules)
