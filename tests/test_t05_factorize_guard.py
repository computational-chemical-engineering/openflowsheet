"""ADR 0004 D3.3 as amended 2026-09-25: `numerics.linear.factorize` is the only call of `splu`.

The structural refusal in front of SuperLU (T04 review S5) was once copied into K04's regularity
screen after T05 A28 found a second `splu` call site without it (a segfault on an 18 x 18 target of
structural rank 15). The narrow review asked for one guarded entry point; this pins that no module
imports or calls `splu` anywhere else, so a third call site cannot miss the guard.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest
import scipy.sparse as sp

from openflowsheet.numerics.linear import StructurallySingularError, factorize

SRC = Path(__file__).resolve().parent.parent / "src" / "openflowsheet"
GUARDED = SRC / "numerics" / "linear.py"


def _splu_sites(tree: ast.AST) -> list[int]:
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(a.name == "splu" for a in node.names):
            sites.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == "splu":
            sites.append(node.lineno)
    return sites


def test_splu_is_reached_only_through_factorize() -> None:
    offenders = {
        str(path.relative_to(SRC)): _splu_sites(ast.parse(path.read_text()))
        for path in sorted(SRC.rglob("*.py"))
        if path != GUARDED
    }
    assert {name: lines for name, lines in offenders.items() if lines} == {}


def test_the_scan_sees_an_injected_call() -> None:
    injected = ast.parse("from scipy.sparse.linalg import splu\nx = scipy.sparse.linalg.splu(a)\n")
    assert _splu_sites(injected) == [1, 2]


def test_a_structurally_singular_matrix_is_refused_before_superlu() -> None:
    matrix = sp.csc_matrix(np.array([[1.0, 2.0], [0.0, 0.0]]))
    with pytest.raises(StructurallySingularError, match=r"^structurally singular: rank 1 of 2$"):
        factorize(matrix)


def test_a_rectangular_matrix_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="square"):
        factorize(sp.csc_matrix(np.ones((3, 2))))
