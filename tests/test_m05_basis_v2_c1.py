"""M05 WO-8d on C1 (design note §20.1, §20.7; R-400): `M05-basis-v2` at TR-E2's S0 through the
parent's own decision path — the open-loop direction is 20 K along T_in, and the stencil's
curvature agrees with the analytic gradient's directional derivative.

Marked `nlp`: the projection needs Pyomo. Uses `scripts/m05_wo8_runs.py`'s TR-E2 parent on a
fresh experiment store.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

pytestmark = pytest.mark.nlp

#: §20.7 WO-8d (iii): the oracle's step along v, in scaled decision units.
TAU = 1e-4


@pytest.fixture(scope="module")
def tr_e2_at_s0(tmp_path_factory: pytest.TempPathFactory) -> tuple[Any, Any, Any]:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import m05_wo8_runs as wo8

    from openflowsheet.studies.trust_region.basis import m05_basis_v2

    parent, _ = wo8.c1_parent(wo8.CASES["TR-E2"], Path(tmp_path_factory.mktemp("store")))
    (decision,) = parent.decisions
    s0 = parent.solve({decision.name: wo8.START_K}, solve_id="S0", purpose="start")
    projection = parent.project_at(s0)
    basis = m05_basis_v2(projection, path=parent.decision_path(s0))
    return parent, projection, basis


def test_wo8d_i_the_direction_is_20_k_along_the_inlet_temperature(tr_e2_at_s0: Any) -> None:
    """§20.7 WO-8d (i): v_T = 20 K within 1e-8 relative, |v_j|/S_j ≤ 1e-8 for every other input
    (the flows do not depend on T_in with X̂ and ΔT̂ pinned); the stencil is central."""
    _, projection, basis = tr_e2_at_s0
    (entry, *_) = projection.source_map["external_links"]
    ids = entry["input_variable_ids"]
    (link,) = basis.record["links"].values()
    assert (link["stencil"], link["status"], link["solves"]) == (
        "central",
        "ok",
        ["CONVERGED", "CONVERGED"],
    )
    for j, name in enumerate(ids):
        value = link["v"][j]
        if name.endswith(".T"):
            assert abs(value - 20.0) <= 1e-8 * 20.0, (name, value)
        else:
            assert abs(value) / projection.scaling.column[name] <= 1e-8, (name, value)


def test_wo8d_iii_the_curvature_matches_the_analytic_directional_derivative(
    tr_e2_at_s0: Any,
) -> None:
    """§20.7 WO-8d (iii): |c_k − c_ref,k| ≤ 1e-3 |c_ref,k| with
    c_ref,k = vᵀ[∇d_k(w₀ + τv) − ∇d_k(w₀ − τv)]/(2τ), τ = 1e-4, from the analytic gradient;
    c_X < 0 (G5 (a))."""
    parent, projection, basis = tr_e2_at_s0
    (link,) = basis.record["links"].values()
    state = projection.state_of()
    (entry, *_) = projection.source_map["external_links"]
    w0 = [state[name] for name in entry["input_variable_ids"]]
    v = link["v"]
    plus = parent.truth.gradient([w + TAU * vj for w, vj in zip(w0, v, strict=True)])
    minus = parent.truth.gradient([w - TAU * vj for w, vj in zip(w0, v, strict=True)])
    for k, c in enumerate(link["c"]):
        reference = sum(vj * (p - m) for vj, p, m in zip(v, plus[k], minus[k], strict=True)) / (
            2 * TAU
        )
        assert abs(c - reference) <= 1e-3 * abs(reference), (k, c, reference)
    assert link["c"][0] < 0.0
