"""T06 W18 (c): `T06-revision-v2`, the revision path's policy from run 2 on (spec §6.6 (A4); ADR
0018 D6), A86, and its effect on THM-09's run-1 `F-OTHER-ROOT` starts, A89.

`T06-revision-v2` is `T06-revision-v1` with exactly `globalization.eo_core = "newton_refined"`;
v1 stays defined as run 1's policy (A95). A89 re-runs six published THM-09 starts under it: run
1's four `F-OTHER-ROOT`s (1, 2, 5, 10; 1.005, 3.447, 1.010, 1.429 of S3's allowance under v1)
and two of its successes (6, 19; 0.37 and 0.97). Each must end `CONVERGED`, `VERIFIED`, `SUCCESS`,
with S3's worst ratio `≤ 0.1` — ADR 0018's first-order promise (allowance / 10) — on every host.
The refinement clause (exactly one fired on `S3.T` or `S4.T` and kept, chord `ρ_max` > 1 before)
is asserted only on the registered `ref-x86-64` CPU model and recorded elsewhere (T06 spec
Amendment T08-1, R-141): whether ADR 0018 fires is a floating-point decision that is not portable.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest
from t06_ensemble_support import STARTS_FILE, ensemble_cases
from t06_support import T06_REVISION_POLICY, T06_REVISION_POLICY_V1
from test_k03_schemas import errors_for
from test_t06_w4_registry import CONSTRUCTED, REGISTRY

from benchmarks.t06 import ensemble, generator
from openflowsheet.orchestrator.trace import GlobalizationPolicy, SolvePolicy
from openflowsheet.run.manifest import policy_sha256

V2 = "T06-revision-v2"


def _differing(a: object, b: object, kind: type) -> list[str]:
    return [f.name for f in dataclasses.fields(kind) if getattr(a, f.name) != getattr(b, f.name)]


def test_a86_v2_differs_from_v1_in_exactly_the_policy_id_and_the_core() -> None:
    v2, v1 = T06_REVISION_POLICY, T06_REVISION_POLICY_V1
    assert _differing(v2, v1, SolvePolicy) == ["policy_id", "globalization"]
    assert _differing(v2.globalization, v1.globalization, GlobalizationPolicy) == ["eo_core"]
    assert (v2.policy_id, v2.globalization.eo_core) == (V2, "newton_refined")
    assert (v1.policy_id, v1.globalization.eo_core) == ("T06-revision-v1", "newton")
    document, registered = v2.as_document(), v1.as_document()
    assert {key for key in document if document[key] != registered[key]} == {
        "policy_id",
        "globalization",
    }
    assert {
        key
        for key in document["globalization"]
        if document["globalization"][key] != registered["globalization"][key]
    } == {"eo_core"}


def test_a86_the_schema_accepts_v2_and_every_registered_policy_validates_unchanged() -> None:
    """Every policy the registry names: schema-valid, and its canonical hash the registered one
    (v1's `27b6c8d6…` included, so the widening moved no registered document)."""
    assert errors_for("solve_policy", T06_REVISION_POLICY.as_document()) == []
    registered = REGISTRY["policies"]
    for name, policy in CONSTRUCTED.items():
        assert errors_for("solve_policy", policy.as_document()) == [], name
        if name in registered:
            assert policy_sha256(policy) == registered[name]["sha256"], name
    assert registered[V2]["sha256"] == policy_sha256(T06_REVISION_POLICY)
    assert REGISTRY["ensemble"]["policies"]["revision_eo"] == V2
    assert REGISTRY["reference_fixtures"]["policy"] == V2
    # Only the new policy selects the new value.
    selecting = [name for name, p in CONSTRUCTED.items() if p.globalization.eo_core != "newton"]
    assert sorted(selecting) == sorted(
        [V2, *(name for name, p in CONSTRUCTED.items() if p.globalization.eo_core == "ptc")]
    )


#: A89's six starts: run 1's four `F-OTHER-ROOT`s, then two of its THM-09 successes.
A89_STARTS = (1, 2, 5, 10, 6, 19)


def _thm09(index: int) -> tuple[Any, dict[str, Any]]:
    (case,) = [c for c in ensemble_cases() if c.case == "THM-09"]
    published = json.loads(STARTS_FILE.read_bytes())
    (starts,) = [e for e in published["cases"] if e["case"] == "THM-09"]
    (start,) = [s for s in starts["starts"] if s["start"] == index]
    return case, start


def _on_the_reference_cpu() -> bool:
    """Amendment T08-1: the host's CPU model is `ref-x86-64`'s registered one."""
    reference = ensemble.registered()["machine_classes"][ensemble.REFERENCE_CLASS]
    return bool(generator._cpu_model() == reference["cpu_model"])


@pytest.mark.parametrize("index", A89_STARTS)
def test_a89_thm09_ends_within_a_tenth_of_s3s_allowance(
    index: int, monkeypatch: pytest.MonkeyPatch, record_property: Any
) -> None:
    case, start = _thm09(index)
    assert case.policy is T06_REVISION_POLICY
    runs: list[Any] = []
    real = ensemble.execute_plan

    def keeping(**kwargs: Any) -> Any:
        runs.append(real(**kwargs))
        return runs[-1]

    monkeypatch.setattr(ensemble, "execute_plan", keeping)
    record = ensemble.run_start(case, start)
    assert record["crash"] is None, record["crash"]
    assert record["outcome"] == "CONVERGED"
    assert record["certificate"]["verdict"] == "VERIFIED"
    ratio, where = record["worst"]
    assert ratio <= 0.1, (ratio, where)
    assert ensemble.classify(record) == "SUCCESS"
    (run,) = runs
    fired = [e.message for e in run.trace.events if e.message.startswith("terminal_refinement(")]
    asserted = _on_the_reference_cpu()
    record_property("a89_cpu_model", generator._cpu_model())
    record_property("a89_refinement_asserted", asserted)
    record_property("a89_refinement_count", len(fired))
    record_property("a89_refinements", fired)
    if not asserted:
        return
    assert len(fired) == 1, fired
    (message,) = fired
    assert message.startswith("terminal_refinement(accepted: chord ")
    assert message.endswith((" at S3.T", " at S4.T"))
    before = float(message.rsplit("): chord ", 1)[1].split(" at ")[0])
    assert before > 1.0
