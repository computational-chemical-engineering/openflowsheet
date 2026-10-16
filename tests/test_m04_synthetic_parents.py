"""M04 WO-4: the test-only synthetic parents (spec §9.1) behave as registered, through M02's runner.

The parents are what M04.A16–A23 are judged against, so they are checked here on their own: their
variants are synthetic, carry the stand-in's boundary block and are not registered; an evaluation
through `ExperimentRunner` and M01's boundary returns X = ξ/n_N2,in and ΔT = T_out − T_in equal to
the closed form at the request's own z; the failure region is a deterministic, cached
`reactor_not_accepted(synthetic_failure_region)`; and the transient parent's designated request
fails on every attempt, is retried once and is never cached.

Tolerance of the closed-form check: 10⁻¹² relative. Floor: the boundary's projection and the
per-tube scaling (n/n_tot, F·y) round a handful of times (≈ 10⁻¹⁵); the parent's z is formed from
the tube's composition where the closed form uses the request's flows (≈ 10⁻¹⁵ in z, × |a| < 1).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m04_synthetic_parents as parents  # noqa: E402

STANDIN = variants.registered_variant("standin-x025-v1")
CONTEXT = EvaluationContext(model_version="m04-wo4", constants_sha256="0" * 64)
#: Spec §3.1's box centres: the nominal request and one in the failure region (z_T = z_F = 0.9).
CENTRE = (673.15, 9.5e6, 2.75, 0.03, 0.02, 0.025, 0.00715)
FAILING = (691.15, 9.5e6, 2.75, 0.03, 0.02, 0.025, 0.00715 + 0.9 * 0.00145)


def _request(u: tuple[float, ...]) -> StreamState:
    """Spec §5.1's request of a draw u (one tube)."""
    t, p, r, y_nh3, y_ar, y_ch4, f = u
    y_n2 = (1.0 - y_nh3 - y_ar - y_ch4) / (1.0 + r)
    n = (f * r * y_n2, f * y_n2, f * y_nh3, f * y_ar, f * y_ch4)
    return StreamState(n=n, temperature=t, pressure=p)


def _z(state: StreamState) -> tuple[float, ...]:
    n = state.n
    total = math.fsum(n)
    u = (state.temperature, state.pressure, n[0] / n[1], n[2] / total, n[3] / total, n[4] / total)
    u = (*u, total)
    return tuple(
        (value - (lo + hi) * 0.5) / ((hi - lo) * 0.5)
        for value, (lo, hi) in zip(u, parents.BOX, strict=True)
    )


def _runner(root: Path, transient: tuple[StreamState, ...] = ()) -> ExperimentRunner:
    return ExperimentRunner(
        ExperimentStore(root, ListArtifactSink()),
        PrC1Provider(),
        CONTEXT,
        backend_for=parents.backend_for(transient),
    )


@pytest.mark.parametrize("variant_id", sorted(parents.AMPLITUDE))
def test_the_parents_are_synthetic_unregistered_variants_with_the_standins_boundary(
    variant_id: str,
) -> None:
    variant = parents.synthetic_variant(variant_id)
    assert variant.synthetic and variant.kind == "in_process"
    assert variant.boundary == STANDIN.boundary
    assert variant_id not in variants.registry()
    assert variants.resolve(variant.model_id, variant.variant_id, variant.sha256) is None
    others = {parents.synthetic_variant(v).sha256 for v in parents.AMPLITUDE if v != variant_id}
    assert variant.sha256 not in others


@pytest.mark.parametrize("variant_id", [parents.SMOOTH_ID, parents.ROUGH_ID])
@pytest.mark.parametrize(
    "u",
    [
        CENTRE,
        (661.7, 9.37e6, 2.61, 0.0273, 0.0188, 0.0321, 0.00653),
        (690.0, 9.9e6, 2.95, 0.039, 0.011, 0.039, 0.0060),
    ],
)
def test_an_ok_evaluation_returns_the_closed_form(
    tmp_path: Path, variant_id: str, u: tuple[float, ...]
) -> None:
    variant = parents.synthetic_variant(variant_id)
    state = _request(u)
    outcome = _runner(tmp_path).run(variant, state, COMPONENTS, 1.0)
    assert outcome.result is not None and not outcome.cache_hit
    envelope = outcome.result["envelope"]
    assert (envelope["status"], envelope["domain_status"]) == ("ok", "within_data_domain")
    assert envelope["identity"]["synthetic"] is True
    truth = parents.synthetic_truth(_z(state), parents.AMPLITUDE[variant_id])
    assert truth is not None
    x = envelope["xi"] / state.n[1]
    dt = envelope["outlet"]["T"] - state.temperature
    assert x == pytest.approx(truth[0], rel=1e-12)
    assert dt == pytest.approx(truth[1], rel=1e-12)
    # The inerts pass unchanged and the outlet conserves elements (the boundary's projection).
    assert envelope["outlet"]["n"][3:] == list(state.n[3:])
    assert envelope["defect_rel"] <= 1e-14


def test_the_failure_region_is_a_deterministic_cached_refusal(tmp_path: Path) -> None:
    variant = parents.synthetic_variant(parents.SMOOTH_ID)
    state = _request(FAILING)
    z = _z(state)
    assert z[0] + z[6] == pytest.approx(1.8, rel=1e-12)
    runner = _runner(tmp_path)
    first = runner.run(variant, state, COMPONENTS, 1.0)
    assert first.result is not None
    envelope = first.result["envelope"]
    assert envelope["status"] == "not_converged"
    assert envelope["code"] == "reactor_not_accepted(synthetic_failure_region)"
    assert envelope["outlet"] is None and envelope["xi"] is None
    again = runner.run(variant, state, COMPONENTS, 1.0)
    assert again.cache_hit and again.attempts == ()


def test_the_transient_parent_fails_its_designated_request_on_every_attempt(
    tmp_path: Path,
) -> None:
    variant = parents.synthetic_variant(parents.TRANSIENT_ID)
    designated, other = _request(CENTRE), _request(FAILING)
    runner = _runner(tmp_path, (designated,))
    outcome = runner.run(variant, designated, COMPONENTS, 1.0)
    assert outcome.transient
    assert [a["execution"]["status"] for a in outcome.attempts] == ["crashed", "crashed"]
    assert outcome.envelope["code"] == "external_crashed"
    assert runner.records.result(outcome.key) is None
    retried = runner.run(variant, designated, COMPONENTS, 1.0)
    assert retried.transient and not retried.cache_hit and len(retried.attempts) == 2
    # Every other request is the smooth parent's.
    assert runner.run(variant, other, COMPONENTS, 1.0).result is not None


def test_transient_failures_belong_to_the_transient_parent_only() -> None:
    with pytest.raises(ValueError, match="transient"):
        parents.SyntheticBackend(parents.synthetic_variant(parents.SMOOTH_ID), (_request(CENTRE),))
    with pytest.raises(ValueError, match="not an M04 synthetic parent"):
        parents.synthetic_variant("standin-x025-v1")
