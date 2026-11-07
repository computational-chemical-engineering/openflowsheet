"""OPT §9 A-3 (WO-5b): a split's margin is its region closure's own test; phase rows only where
they equal it (guarded). Gate G24 (a)–(d), and V4's identity clause.

- (a) the analytic cases' LIQUID splits (ideal K): the closure margin equals `tp_margin` within
  1e-12 absolute, and their rows are guarded;
- (b) C-MW's 19 TWO_PHASE stages: margin = min(Σ vapour, Σ liquid) / N0, recomputed here from the
  state by column name, bit for bit; all at least `τ_regime`; no single-phase split;
- (c) a γ–φ VAPOR-held split (GP-C3's heater above its dew point, `wilson-ig-v2`): unguarded,
  admitted, named in `regimes_unguarded`, margin `1 − ΣW` of the incipient liquid;
- (d) a LIQUID split whose closure value is moved by 1e-9: unguarded.
"""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from s11_gp_support import gp_c3

from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001 import gamma_phi
from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.revision import instances_of
from openflowsheet.orchestrator.splits import region_splits
from openflowsheet.studies.nlp import revision as revision_module
from openflowsheet.studies.nlp import revision_host
from openflowsheet.studies.nlp.host import CertifiedPoint
from openflowsheet.studies.nlp.phase import CLOSURE_IDENTITY
from openflowsheet.studies.nlp.revision_host import (
    DecisionBox,
    DecisionMap,
    RevisionNlpHost,
    decision_map,
)
from openflowsheet.studies.nlp.verification import _not_closure_test, _phase_terms, _regimes
from openflowsheet.studies.sensitivity import TAU_REGIME, SplitRegime
from openflowsheet.studies.syn001 import tp_margin
from openflowsheet.verify.certificate import CheckPolicy

REPO = Path(__file__).resolve().parents[1]
OPT = REPO / "benchmarks" / "opt"
C_MW = REPO / "benchmarks" / "s11" / "flowsheets" / "C-MW.json"
C_MW_FEED_T = 348.6155803604359
POLICY = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
assert POLICY is not None
#: K03's registered `molar_flow` nominal (D-35's N0), stated here, not read from the code.
N0 = 3.0
#: GP-C3's heater outlet temperature above the stream's dew point at 101 325 Pa: held VAPOR.
GP_C3_VAPOR_T = 385.0


def _host(document: Mapping[str, Any], boxes: list[DecisionBox]) -> RevisionNlpHost:
    found = decision_map(document, boxes)
    assert isinstance(found, DecisionMap), found
    assert POLICY is not None
    return RevisionNlpHost(document, found, solve_policy=POLICY, check_policy=CheckPolicy())


def _context(host: RevisionNlpHost, point: CertifiedPoint) -> EvaluationContext:
    metadata = host._compiled_at(point).metadata
    return EvaluationContext(
        model_version=metadata.model_version,
        constants_sha256=metadata.constants_sha256,
        phase_signature=None,
    )


@cache
def _analytic(flowsheet: str) -> tuple[RevisionNlpHost, CertifiedPoint]:
    """The analytic flowsheet's host (decision: its duty `SPEC-Q`) at the revision's values."""
    document = json.loads((OPT / "flowsheets" / f"{flowsheet}.json").read_bytes())
    box = (
        DecisionBox("SPEC-T", 305.0, 336.0, "K")
        if flowsheet == "OPT-A2b"
        else DecisionBox("SPEC-Q", 500.0, 20000.0, "W")
    )
    host = _host(document, [box])
    (parameter,) = host.decisions.parameters.values()
    point = host.certify({parameter: host.base_spec().parameters[parameter]})
    assert point.verified, (flowsheet, point.outcome)
    return host, point


# -- G24 (a) ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("flowsheet", ["OPT-A1", "OPT-A2", "OPT-A2b"])
def test_g24a_an_ideal_liquid_split_has_tp_margins_and_a_guarded_row(flowsheet: str) -> None:
    host, point = _analytic(flowsheet)
    assert point.state is not None
    flowsheet_object = host.bound_flowsheet(point)
    lifted = {
        split.unit: split
        for split in region_splits(
            instances_of(flowsheet_object), flowsheet_object.units(), flowsheet_object.components
        ).splits
    }
    liquid = [split for split in host.regimes(point).splits if split.regime == "LIQUID"]
    assert liquid
    for split in liquid:
        lifted_split = lifted[split.unit_id]
        _, expected = tp_margin(
            flowsheet_object.provider,
            [float(point.state[name]) for name in lifted_split.feed],
            float(point.state[lifted_split.temperature]),
            float(point.state[lifted_split.pressure]),
            _context(host, point),
            flowsheet_object.components,
        )
        assert split.margin is not None and expected is not None
        assert abs(split.margin - expected) <= 1e-12, (split.unit_id, split.margin, expected)
    rows = host.phase_rows(point)
    assert rows.unguarded == () and rows.undefined == ()
    assert {row.unit for row in rows.rows if row.split} == {split.unit_id for split in liquid}


# -- G24 (b) ---------------------------------------------------------------------------------------


def test_g24b_c_mw_two_phase_margins_are_the_smaller_phase_flow() -> None:
    document = json.loads(C_MW.read_bytes())
    host = _host(document, [DecisionBox("SPEC-S-IN1-T", 335.0, C_MW_FEED_T, "K")])
    point = host.certify({"U-FEED1.T_spec": C_MW_FEED_T})
    assert point.verified and point.state is not None
    state = point.state
    splits = host.regimes(point).splits
    assert len(splits) == 19
    assert {(split.kind, split.regime) for split in splits} == {("PH", "TWO_PHASE")}
    components = ("CH3OH", "C2H5OH", "H2O")
    for split in splits:
        vapour = math.fsum(state[f"{split.unit_id}.v.{name}"] for name in components)
        liquid = math.fsum(state[f"{split.unit_id}.l.{name}"] for name in components)
        assert split.margin == min(vapour, liquid) / N0, split.unit_id
        assert split.margin >= TAU_REGIME
    rows = host.phase_rows(point)
    assert rows.rows == () and rows.undefined == () and rows.unguarded == ()


# -- G24 (c) ---------------------------------------------------------------------------------------


@cache
def _gp_c3_vapour() -> tuple[RevisionNlpHost, CertifiedPoint]:
    """GP-C3 with its heater above the dew point: the solve converges with H held VAPOR, but K04's
    certificate is UNVERIFIED there — the derivative witness's stencil steps the held, exactly
    zero liquid side negative (`witness_stencil_invalid_trial_state(S4.liq.CH3OH)`), as on every
    single-phase held split on `wilson-ig-v2` (OPT_DECISIONS D-42). So no OPT start can certify
    here today; the point is relabelled converged to judge A-3's rule on its converged state."""
    document = gp_c3(GP_C3_VAPOR_T)
    host = _host(document, [DecisionBox("SPEC-H-T", 380.0, 390.0, "K")])
    (parameter,) = host.decisions.parameters.values()
    point = host.certify({parameter: GP_C3_VAPOR_T})
    assert point.outcome == "CERTIFICATE_NOT_VERIFIED" and point.signature == (("H", "VAPOR"),)
    assert point.certificate is not None
    reasons = {
        item.get("reason") for item in point.certificate.as_document().get("limitations", [])
    }
    assert "witness_stencil_invalid_trial_state(S4.liq.CH3OH)" in reasons
    return host, dataclasses.replace(point, outcome="CONVERGED")


def test_g24c_a_gamma_phi_vapour_split_is_unguarded_and_admitted() -> None:
    host, point = _gp_c3_vapour()
    assert point.state is not None
    flowsheet = host.bound_flowsheet(point)
    assert flowsheet.provider.describe().provider_id == "wilson-ig-v2"
    (split,) = host.regimes(point).splits
    assert (split.unit_id, split.regime) == ("H", "VAPOR")
    (lifted,) = region_splits(
        instances_of(flowsheet), flowsheet.units(), flowsheet.components
    ).splits
    amounts = [point.state[name] for name in lifted.vapor]
    total = sum(amounts)
    value, _ = gamma_phi.incipient_liquid(
        flowsheet.provider,
        point.state[lifted.temperature],
        point.state[lifted.pressure],
        tuple(amount / total for amount in amounts),
        _context(host, point),
    )
    assert split.margin == 1.0 - value and split.margin >= TAU_REGIME
    rows = host.phase_rows(point)
    assert rows.unguarded == ("H",) and rows.undefined == () and rows.rows == ()
    # The start record names it (§9 A-3); the start is not refused.
    readiness = SimpleNamespace(point=point, start=(GP_C3_VAPOR_T,))
    formulation = SimpleNamespace(decision_values=lambda start: {"SPEC-H-T": start[0]})
    record = revision_module._start_record(formulation, readiness, None, 0, host)  # type: ignore[arg-type]
    assert record["regimes_unguarded"] == ["H"]
    assert "zero_subsystem" not in record or record["zero_subsystem"]["status"] == "held"


# -- G24 (d) ---------------------------------------------------------------------------------------


def test_g24d_a_perturbed_closure_value_leaves_the_split_unguarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = json.loads((OPT / "flowsheets" / "OPT-A1.json").read_bytes())
    host = _host(document, [DecisionBox("SPEC-Q", 500.0, 20000.0, "W")])
    original = region_module.admissibility_value

    def moved(*args: Any) -> float | None:
        value = original(*args)
        return None if value is None else value + 1e-9

    monkeypatch.setattr(revision_host, "admissibility_value", moved)
    (parameter,) = host.decisions.parameters.values()
    point = host.certify({parameter: host.base_spec().parameters[parameter]})
    assert point.verified
    liquid = [split.unit_id for split in host.regimes(point).splits if split.regime == "LIQUID"]
    rows = host.phase_rows(point)
    assert liquid and rows.unguarded == tuple(liquid)
    assert rows.undefined == () and not [row for row in rows.rows if row.split]


# -- V4's identity clause at the candidate ---------------------------------------------------------


def test_v4_fails_a_guarded_row_that_is_no_longer_the_closure_test() -> None:
    host, point = _analytic("OPT-A1")
    assert point.state is not None and point.spec is not None
    phase = host.phase_rows(point)
    record = host.regimes(point)
    terms = _phase_terms(point.spec, phase, point.state, dict(point.parameters))
    assert not isinstance(terms, str)
    assert _not_closure_test(phase, record, point.state, terms) == ()
    (row,) = [row for row in phase.rows if row.split]
    shifted = type(record)(
        record.signature,
        tuple(
            SplitRegime(s.unit_id, s.streams, s.kind, s.regime, s.margin + 2 * CLOSURE_IDENTITY)
            if s.unit_id == row.unit and s.margin is not None
            else s
            for s in record.splits
        ),
    )
    failing = _not_closure_test(phase, shifted, point.state, terms)
    assert failing == (row.unit,)
    check = _regimes(
        shifted, record.declared(), None, point.signature, phase_active=(), not_closure_test=failing
    )
    assert check.outcome == "fail"
    assert check.detail["phase_row_not_closure_test"] == [f"phase_row_not_closure_test({row.unit})"]
