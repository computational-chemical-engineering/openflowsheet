"""K04-F9 W1: the verifier's Newton projection as a function (spec §5.1; ADR 0013 D1; X02).

`verify.projection.project` is driven here with a stub declaration — one stream `S1` of five
columns and linear rows `x_j − c_j` — so that each precondition can be made to fail on its own and
in combination: the first failing precondition names the refusal, in §5.1's order, and a refused
projection hands back the certified state itself (every category judged at `x_final`). The matrix
and scaled residual are passed in, as the certificate passes the screen's; the stub's rows are
unit-scaled, so `F̂ = F`.

The certificate-level assertions (X01, X03–X25) are `test_k04f9_certificates.py`.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp

from openflowsheet.verify import CheckResult
from openflowsheet.verify.checks import KIND_TOLERANCE, residual_checks
from openflowsheet.verify.projection import PROJECTED_CATEGORIES, Projection, project
from openflowsheet.verify.zero_flow import ZeroFlowSplit

COLUMNS = ("S1.n.A", "S1.n.B", "S1.n.C", "S1.T", "S1.P")
KINDS = {
    "S1.n.A": "molar_flow",
    "S1.n.B": "molar_flow",
    "S1.n.C": "molar_flow",
    "S1.T": "temperature",
    "S1.P": "pressure",
}
DOMAIN = {"T": (280.0, 440.0), "P": (5.0e4, 2.0e5)}
#: The rows' targets: a flowing liquid-like stream inside the domain, C absent.
TARGET = {"S1.n.A": 1.0, "S1.n.B": 0.5, "S1.n.C": 0.0, "S1.T": 350.0, "S1.P": 1.0e5}


@dataclass(frozen=True)
class _Evaluation:
    status: str
    values: tuple[float, ...] | None
    equation_ids: tuple[str, ...]
    state_sha256: str


@dataclass
class _Compiled:
    """Rows `r_j = x_j − c_j`, one per column, named `row.<column>`."""

    targets: Mapping[str, float]
    status: str = "ok"
    columns: tuple[str, ...] = COLUMNS

    def residual(self, vector: Any, context: Any) -> _Evaluation:
        values = tuple(
            float(v) - self.targets[name] for name, v in zip(self.columns, vector, strict=True)
        )
        digest = hashlib.sha256(repr(values).encode()).hexdigest()
        return _Evaluation(
            status=self.status,
            values=values if self.status == "ok" else None,
            equation_ids=tuple(f"row.{name}" for name in self.columns),
            state_sha256=digest,
        )


def _target(
    targets: Mapping[str, float] = TARGET,
    status: str = "ok",
    kinds: Mapping[str, str] = KINDS,
) -> Any:
    columns = tuple(kinds)
    spec = SimpleNamespace(
        variable_ids=columns,
        variable_kinds=dict(kinds),
        row_kinds={f"row.{name}": kinds[name] for name in columns},
    )
    return SimpleNamespace(
        spec=spec,
        compiled=_Compiled(dict(targets), status=status, columns=columns),
        context=None,
        scaling=SimpleNamespace(column={name: 1.0 for name in columns}),
    )


def _rows(target: Any, state: Mapping[str, float]) -> list[CheckResult]:
    rows, _ = residual_checks(
        target.compiled, target.spec, state, None, target.spec.row_kinds, KIND_TOLERANCE
    )
    return rows


def _residual(state: Mapping[str, float], targets: Mapping[str, float] = TARGET) -> np.ndarray:
    return np.array([state[name] - targets[name] for name in COLUMNS])


def _project(
    state: Mapping[str, float],
    *,
    target: Any = None,
    status: str = "NO_RANK_LOSS_DETECTED",
    matrix: Any = None,
    residual: Sequence[CheckResult] | None = None,
    scaled: np.ndarray | None = None,
    zero_flow: Sequence[ZeroFlowSplit] = (),
) -> Projection:
    target = target or _target()
    return project(
        target,
        state,
        residual=_rows(target, state) if residual is None else residual,
        regularity_status=status,
        matrix=sp.csc_matrix(np.eye(len(COLUMNS))) if matrix is None else matrix,
        scaled_residual=_residual(state) if scaled is None else scaled,
        zero_flow=zero_flow,
        streams=("S1",),
        domain=DOMAIN,
        tolerances=KIND_TOLERANCE,
    )


def _near(**offsets: float) -> dict[str, float]:
    """The targets moved by `offsets` (column name with dots as `__`)."""
    state = dict(TARGET)
    for key, offset in offsets.items():
        state[key.replace("__", ".")] += offset
    return state


def _refused(projection: Projection, state: Mapping[str, float], reason: str) -> None:
    assert projection.judged_at == "final_state"
    assert projection.reason == reason
    assert projection.state is state  # every category judged at x_final
    assert projection.as_document() == {
        "judged_at": "final_state",
        "reason": reason,
        "categories": list(PROJECTED_CATEGORIES),
    }


def test_x02_a_state_inside_its_tolerances_is_projected_onto_its_root() -> None:
    state = _near(S1__n__A=2.0e-8, S1__T=4.0e-7, S1__P=5.0e-3)
    projection = _project(state)
    assert projection.judged_at == "projection" and projection.reason == ""
    assert projection.as_document() == {
        "judged_at": "projection",
        "reason": "",
        "categories": ["energy_balance", "phase_admissibility", "independent_split"],
    }
    assert projection.state == TARGET  # linear rows: one Newton step is exact
    # Python floats only (spec §5.1; finding F5: a NumPy scalar breaks canonicalization).
    assert all(type(value) is float for value in projection.state.values())
    assert state == _near(S1__n__A=2.0e-8, S1__T=4.0e-7, S1__P=5.0e-3)  # x_final untouched


def test_x02_a_failing_residual_refuses_first() -> None:
    state = _near(S1__n__A=4.0e-8)  # 1.3 τ_flow
    _refused(_project(state), state, "residual_not_passed")
    # First in §5.1's order: also irregular and unfactorizable, still `residual_not_passed`.
    singular = sp.csc_matrix((len(COLUMNS), len(COLUMNS)))
    _refused(
        _project(state, status="RANK_DEFICIENT", matrix=singular), state, "residual_not_passed"
    )


@pytest.mark.parametrize("status", ["RANK_DEFICIENT", "ILL_CONDITIONED", "INCONCLUSIVE"])
def test_x02_each_regularity_status_names_its_refusal(status: str) -> None:
    state = _near(S1__n__A=2.0e-8)
    _refused(_project(state, status=status), state, f"regularity_{status}")
    # Before the solve: a singular matrix under the same status is still the status's refusal.
    singular = sp.csc_matrix((len(COLUMNS), len(COLUMNS)))
    _refused(_project(state, status=status, matrix=singular), state, f"regularity_{status}")


def test_x02_a_factorization_that_raises_is_linear_solve_failed() -> None:
    state = _near(S1__n__A=2.0e-8)
    singular = sp.csc_matrix(np.diag([1.0, 1.0, 0.0, 1.0, 1.0]))  # structurally singular
    _refused(_project(state, matrix=singular), state, "linear_solve_failed")


def test_x02_a_step_that_makes_a_flow_negative_is_outside_the_domain() -> None:
    targets = dict(TARGET, **{"S1.n.B": -1.0e-8})
    state = dict(TARGET, **{"S1.n.B": 1.0e-9})  # row 1.1e-8 < τ_flow: passes
    target = _target(targets)
    projection = _project(state, target=target, scaled=_residual(state, targets))
    _refused(projection, state, "projection_outside_domain")


def test_x02_a_negative_step_on_a_flow_kind_column_that_is_no_stream_flow_is_inside() -> None:
    """Ruled 2026-09-25 (Q-S5 (2); K04-F9 §5.1 guard 4): "flow" is K04 §4.6's stream-flow
    predicate, not the `molar_flow` kind. A reaction extent (`<U>.xi`, kind `molar_flow`, signed:
    a reverse reaction) stepping negative at `x̃` is not `projection_outside_domain`; the
    projection is issued with the extent at its row's root."""
    kinds = dict(KINDS, **{"U-RX.xi": "molar_flow"})
    targets = dict(TARGET, **{"U-RX.xi": -1.0e-8})
    state = dict(TARGET, **{"U-RX.xi": 1.0e-9})  # row 1.1e-8 < τ_flow: passes
    target = _target(targets, kinds=kinds)
    projection = _project(
        state,
        target=target,
        matrix=sp.csc_matrix(np.eye(len(kinds))),
        scaled=np.array([state[name] - targets[name] for name in kinds]),
    )
    assert projection.judged_at == "projection" and projection.reason == ""
    assert projection.state["U-RX.xi"] == pytest.approx(-1.0e-8, rel=1e-12)
    assert projection.state["U-RX.xi"] < 0.0


def test_x02_a_step_that_takes_a_flowing_temperature_off_the_domain_is_outside_it() -> None:
    targets = dict(TARGET, **{"S1.T": 440.0000005})
    state = dict(TARGET, **{"S1.T": 440.0})  # row −5e-7 K < τ_T: passes
    target = _target(targets)
    projection = _project(state, target=target, scaled=_residual(state, targets))
    _refused(projection, state, "projection_outside_domain")
    # The same step on a dormant stream is not judged: its T and P are labels (ADR 0001 D3.1).
    dormant_targets = dict(targets, **{"S1.n.A": 0.0, "S1.n.B": 0.0})
    dormant_state = dict(state, **{"S1.n.A": 0.0, "S1.n.B": 0.0})
    projection = _project(
        dormant_state,
        target=_target(dormant_targets),
        scaled=_residual(dormant_state, dormant_targets),
    )
    assert projection.judged_at == "projection"
    assert projection.state["S1.T"] == 440.0000005


def test_x02_a_step_after_which_a_row_fails_is_refused() -> None:
    state = _near(S1__n__A=2.0e-8)
    # A matrix that is not the rows' Jacobian: the step overshoots by a factor of ten.
    wrong = sp.csc_matrix(np.eye(len(COLUMNS)) * 0.1)
    _refused(_project(state, matrix=wrong), state, "projection_rows_not_passed")


def test_x02_a_row_the_compiled_problem_cannot_evaluate_at_the_projection_does_not_pass() -> None:
    state = _near(S1__n__A=2.0e-8)
    target = _target()
    residual = _rows(target, state)
    target.compiled.status = "domain_error"
    _refused(_project(state, target=target, residual=residual), state, "projection_rows_not_passed")


def test_x02_a_failing_label_row_at_the_projection_is_refused() -> None:
    """A zero-flow label `T_out − T_label` is a row: at `x̃` it must pass as the compiled rows do.
    The label here reads `S1.T` against `S1.P` (a stub pairing: only its value matters)."""
    state = _near(S1__n__A=2.0e-8)
    label = ZeroFlowSplit(unit="U", columns=(), rows=(), label=("U:label", "S1.T", "S1.P"))
    projection = _project(state, residual=_rows(_target(), state), zero_flow=(label,))
    _refused(projection, state, "projection_rows_not_passed")


def test_x02_the_columns_must_be_the_screened_matrixs() -> None:
    state = _near(S1__n__A=2.0e-8)
    with pytest.raises(RuntimeError, match="not the screened matrix"):
        _project(state, matrix=sp.csc_matrix(np.eye(len(COLUMNS) - 1)))


def test_x03_an_exactly_zero_flow_stays_exactly_zero() -> None:
    """Spec §5.1: the step on an exactly-zero molar-flow column is discarded (the exact Newton
    step is zero there); a matrix that couples C to A would otherwise move it. A temperature at
    `0.0` would not be held — the rule is for molar flows only."""
    state = _near(S1__n__A=2.0e-8)
    coupled = np.eye(len(COLUMNS))
    coupled[2, 0] = 0.5  # row C reads A: δ_C = −0.5 δ_A ≠ 0
    projection = _project(state, matrix=sp.csc_matrix(coupled))
    assert projection.judged_at == "projection"
    assert projection.state["S1.n.C"] == 0.0 and math.copysign(1.0, projection.state["S1.n.C"]) > 0
    assert projection.discarded == pytest.approx(0.5 * 2.0e-8, rel=1e-12)
    # Signed zero is zero (ADR 0001 D1.5): a `-0.0` flow is held too.
    negative_zero = dict(state, **{"S1.n.C": -0.0})
    projection = _project(negative_zero, matrix=sp.csc_matrix(coupled))
    assert projection.state["S1.n.C"] == 0.0
    assert projection.discarded == pytest.approx(0.5 * 2.0e-8, rel=1e-12)
