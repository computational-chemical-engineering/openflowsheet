"""T07 G12: a requested check tolerance is compared, never routed on (ruling round 5, M1).

Design note `docs/design/T07-jobs-and-bindings.md`, ruling round 5 M1 (G12.1–G12.10, which replace
§16's G12 row) and §10.5 as amended; ADR 0013 Amendment 2; K04-F9 spec §5.1 and §5.3;
K04 certificate spec §5.4. Every routing decision of the verifier reads
ρ_k = max(τ_k(policy), τ_k(registered)) (`verify.checks.routing_tolerances`), so a policy that only
tightens yields the registered certificate's checks, values and projection with stricter
tolerances: it can turn a pass into a fail, never remove a check.

Through `Application.submit_job` under the inline executor: 5 revisions × 12 policies (`P0`,
`P1`, and each factor applied to `molar_flow` alone and to every kind). Every comparison is exact:
the check policy reaches neither the solve nor any route, so both certificates are the same
arithmetic on the same state (the probe measured 440 of 440 equal, `r5/m1_rho_probe.py`).

Discrimination (recorded as the gate's evidence, not a test): at `b36a018`, before the fix, G12.3
fails for each of the five revisions under `P_1e-6,flow`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import commit, lifecycle_violations, response_schema_violations

from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.types import JobRequest, SolveBody
from openflowsheet.verify.certificate import CheckPolicy
from openflowsheet.verify.checks import KIND_TOLERANCE, routing_tolerances

#: The ruling's five revisions, each `VERIFIED` at the registered policy (measured).
REVISIONS = (
    "SYN-001-nominal",
    "SYN-001-T06-NET03",
    "SYN-001-once-through",
    "SYN-001-T06-REF03",
    "T05b:DZ-3",
)
FACTORS = (0.5, 0.1, 0.01, 1e-6, 1e-12)
#: `check_policy_sha256` of the registered policy (K05, `docs/t07-measurements.md` §W0.1).
REGISTERED_CHECK_POLICY_SHA256 = "21c44e105a1b78428047258af3030b8502957aab5d27f0389c2f143bcb3cf390"
#: The members a tightened check may change (G12.4); `grade` derives the verdict from them.
JUDGED = ("tolerance", "result", "near_threshold")


def _tightened() -> dict[str, dict[str, float]]:
    """`P_f,flow` and `P_f,all` for every factor, by name."""
    policies: dict[str, dict[str, float]] = {}
    for factor in FACTORS:
        policies[f"flow-{factor:g}"] = {"molar_flow": KIND_TOLERANCE["molar_flow"] * factor}
        policies[f"all-{factor:g}"] = {k: v * factor for k, v in KIND_TOLERANCE.items()}
    return policies


TIGHTENED = _tightened()


class _Run:
    """One solve's verdict and certificate, read back from the job's outputs."""

    def __init__(self, app: LocalApplication, revision_id: str, key: str, tolerances: Any) -> None:
        body = (
            SolveBody(revision_id)
            if tolerances is None
            else SolveBody(revision_id, check_tolerances=tolerances)
        )
        job = app.submit_job(JobRequest("solve", key, body)).job
        assert job.status == "completed", (key, job.status, job.error)
        result = app.get_job_result(job.job_id).run_result
        assert result is not None
        (certificate,) = [o for o in result.outputs if o.kind == "solution_certificate"]
        row = app.store.artifact(certificate.artifact_id)
        assert row is not None
        self.verdict = result.verification_status
        self.check_policy_sha256 = result.check_policy_sha256
        self.raw = (app.files_root / row.relpath).read_bytes()
        self.document: dict[str, Any] = json.loads(self.raw)


@pytest.fixture(scope="module")
def app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LocalApplication]:
    application = LocalApplication.create(
        tmp_path_factory.mktemp("g12") / "project", project_id="g12"
    )
    yield application
    try:
        assert lifecycle_violations(application) == {}  # G3
        assert response_schema_violations(application) == []  # R4-G3
    finally:
        application.close()


class _Runs(dict[str, dict[str, _Run]]):
    """Revision -> policy name (`P0`, `P1`, `flow-<f>`, `all-<f>`) -> its run, solved on first
    use: 5 × 12 = 60 solves for the module."""

    def __init__(self, app: LocalApplication) -> None:
        super().__init__()
        self.app = app

    def __missing__(self, name: str) -> dict[str, _Run]:
        revision_id = commit(self.app, CORPUS[name]())
        solved = {
            "P0": _Run(self.app, revision_id, f"{name}:P0", None),
            "P1": _Run(self.app, revision_id, f"{name}:P1", dict(KIND_TOLERANCE)),
        }
        for policy, tolerances in TIGHTENED.items():
            solved[policy] = _Run(self.app, revision_id, f"{name}:{policy}", tolerances)
        self[name] = solved
        return solved


@pytest.fixture(scope="module")
def runs(app: LocalApplication) -> _Runs:
    return _Runs(app)


def _bits(value: Any) -> Any:
    return None if value is None else float(value).hex()


# -- routing_tolerances (the unit test the ruling names) ----------------------------------------


def test_routing_tolerances_is_the_larger_of_the_policy_and_the_registered_value() -> None:
    registered = routing_tolerances(dict(KIND_TOLERANCE))
    assert registered == dict(KIND_TOLERANCE)
    assert all(registered[kind] is value for kind, value in KIND_TOLERANCE.items())
    halved = {kind: value * 0.5 for kind, value in KIND_TOLERANCE.items()}
    assert routing_tolerances(halved) == dict(KIND_TOLERANCE)
    looser = routing_tolerances({"molar_flow": 1e-6})
    assert looser == {**KIND_TOLERANCE, "molar_flow": 1e-6}
    assert routing_tolerances(None) == dict(KIND_TOLERANCE)


# -- G12.1–G12.9 ----------------------------------------------------------------------------------


@pytest.mark.parametrize("name", REVISIONS)
def test_g12_1_factor_one_is_the_registered_certificate(runs: _Runs, name: str) -> None:
    p0, p1 = runs[name]["P0"], runs[name]["P1"]
    assert p1.raw == p0.raw
    assert (p0.verdict, p0.check_policy_sha256) == ("VERIFIED", REGISTERED_CHECK_POLICY_SHA256)
    assert p0.document["check_policy_sha256"] == REGISTERED_CHECK_POLICY_SHA256


@pytest.mark.parametrize("policy", sorted(TIGHTENED))
@pytest.mark.parametrize("name", REVISIONS)
def test_g12_2_to_8_a_tightened_certificate_is_the_registered_one_judged_stricter(
    runs: _Runs, name: str, policy: str
) -> None:
    registered, tight = runs[name]["P0"].document, runs[name][policy].document
    # G12.2: the solve does not read the check policy.
    assert tight["target_state_sha256"] == registered["target_state_sha256"]
    # G12.3: the same check ids, in the same order and number.
    assert [c["id"] for c in tight["checks"]] == [c["id"] for c in registered["checks"]]
    stricter = False
    for a, b in zip(registered["checks"], tight["checks"], strict=True):
        # G12.4: every member except the judged ones is equal; values bitwise.
        assert set(a) == set(b), a["id"]
        for member in set(a) - set(JUDGED):
            if member == "value":
                assert _bits(b["value"]) == _bits(a["value"]), a["id"]
            else:
                assert b[member] == a[member], (a["id"], member)
        # G12.5: never a looser tolerance.
        if a.get("tolerance") is not None and b.get("tolerance") is not None:
            assert b["tolerance"] <= a["tolerance"], a["id"]
            stricter = stricter or b["tolerance"] < a["tolerance"]
        # G12.6: a tightened pass is a registered pass.
        assert b["result"] != "pass" or a["result"] == "pass", a["id"]
    assert stricter, "the tightened policy was not applied"
    # G12.7: judged at the same state.
    assert tight["transformations"]["projection"] == registered["transformations"]["projection"]
    # G12.8: never VERIFIED, never a relaxation; RELAXED only over a registered VERIFIED.
    run = runs[name][policy]
    assert run.verdict == tight["verification_status"]
    assert run.verdict in ("RELAXED", "UNVERIFIED", "FAILED")
    assert run.verdict != "RELAXED" or runs[name]["P0"].verdict == "VERIFIED"
    assert [item for item in tight["limitations"] if item["kind"] == "relaxation"] == []
    admitted = CheckPolicy(tolerances={**KIND_TOLERANCE, **TIGHTENED[policy]})
    assert admitted.relaxations() == []
    assert run.check_policy_sha256 == admitted.sha256 != REGISTERED_CHECK_POLICY_SHA256


def test_g12_9_the_grid_is_not_vacuous(runs: _Runs) -> None:
    """Under `P_1e-6,flow` the restored independent split fails at its resolution floor on
    once-through and REF03 (it fails; it does not vanish), and nominal keeps its split, RELAXED."""
    verdicts = {name: runs[name]["flow-1e-06"].verdict for name in REVISIONS[:4]}
    assert verdicts["SYN-001-once-through"] == "FAILED"
    assert verdicts["SYN-001-T06-REF03"] == "FAILED"
    assert verdicts["SYN-001-nominal"] == "RELAXED"
    for name in ("SYN-001-once-through", "SYN-001-T06-REF03"):
        failing = [
            c["id"] for c in runs[name]["flow-1e-06"].document["checks"] if c["result"] == "fail"
        ]
        assert failing and all(i.startswith("independent_split.") for i in failing), failing
    nominal = [c["id"] for c in runs["SYN-001-nominal"]["flow-1e-06"].document["checks"]]
    assert "independent_split.flash.S3.total" in nominal


# -- G12.10 ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(KIND_TOLERANCE))
def test_g12_10_a_looser_value_is_refused(app: LocalApplication, kind: str) -> None:
    revision_id = commit(app, CORPUS["SYN-001-nominal"]())
    looser = {kind: KIND_TOLERANCE[kind] * 2}
    with pytest.raises(ApplicationError) as raised:
        app.submit_job(
            JobRequest("solve", f"looser-{kind}", SolveBody(revision_id, check_tolerances=looser))
        )
    assert raised.value.code == "verification_weakening_refused"


def test_the_registered_hash_is_the_registered_policys() -> None:
    assert CheckPolicy().sha256 == REGISTERED_CHECK_POLICY_SHA256
