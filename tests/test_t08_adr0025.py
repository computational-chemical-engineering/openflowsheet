"""ADR 0025: replay comparison under `T08-numerical-policy-v2` (T08.A45; R-146, R-147).

The assertions of ADR 0025 §9 that are not CI's: A1 (the policy file's generator), A3 (dispatch,
with Frank's answer to Q4 replacing D1.3's refusal: a record is compared under the policy it
names, and only an unknown id is refused), A4–A11 (the comparator, case by case), A12 (v1
frozen: F2's pairs), A13 (labels) and the schema half of A15. A2 is K04 A32, parameterized
(`tests/test_k04_schemas.py`); A14 is the RC job's controls.

The comparator cases test presence or absence of a difference, exactly: every "none" pair sits at
least 10× inside its v2 tolerance and every "difference" pair at least 10× outside it (§9), so no
outcome depends on rounding. A difference is asserted by its path; its text is A13's.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from jsonschema import Draft202012Validator

from openflowsheet.run.compare import CURRENT_POLICY_ID, V1_POLICY_ID, differences

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_numerical_policy  # noqa: E402

V1 = "K04-numerical-policy-v1"
V2 = "T08-numerical-policy-v2"
#: ADR 0007 D4's two compared modes; which one depends on this machine's thread pins.
COMPARED = ("exact_replay", "compatible_reproduction")


def v2(emitted: Any, committed: Any, **kwargs: Any) -> list[str]:
    return differences(emitted, committed, policy_id=V2, **kwargs)


def paths(found: list[str]) -> list[str]:
    """Each difference's path: the text before its first `: ` (a message path keeps its
    parenthesised token index)."""
    return [entry.split(": ", 1)[0] for entry in found]


# ------------------------------------------------------------------------------------------ A1


def test_a1_the_policy_file_is_what_its_generator_emits() -> None:
    assert t08_numerical_policy.main(["--check"]) == 0


@pytest.mark.parametrize(
    ("attribute", "value", "condition"),
    [
        ("KINDS", {**t08_numerical_policy.KINDS, "heat_rate": (1e-5, 1e-8, 1e4)}, "(a)"),
        ("POST_PIVOTING", ("u_diag_min_abs", "u_diagonal_ratio"), "(b)"),
        ("TOKEN", r"-?\d+\.\d+", "(c)"),
        ("FLOAT_DIGESTS", ("state_sha256", "full_state_sha256"), "(d)"),
    ],
)
def test_a1_the_generator_refuses_each_condition(
    monkeypatch: pytest.MonkeyPatch, attribute: str, value: Any, condition: str
) -> None:
    monkeypatch.setattr(t08_numerical_policy, attribute, value)
    problems: list[str] = []
    t08_numerical_policy.build(problems)
    assert any(problem.startswith(condition) for problem in problems), problems


def test_a1_an_unclassified_sha256_name_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """D2.3: a new `sha256` name in a schema is never defaulted to either class."""
    declared = t08_numerical_policy.schema_sha256_names()
    monkeypatch.setattr(
        t08_numerical_policy, "schema_sha256_names", lambda: declared | {"fourth_sha256"}
    )
    problems: list[str] = []
    t08_numerical_policy.build(problems)
    assert any(p.startswith("(d)") and "fourth_sha256" in p for p in problems), problems


def test_a1_a_tampered_policy_file_fails_its_audit() -> None:
    import copy

    import yaml

    committed = yaml.safe_load(t08_numerical_policy.V2.read_text(encoding="utf-8"))
    policy = committed["numerical_policy"]
    v1 = t08_numerical_policy.v1_policy()
    declared = t08_numerical_policy.schema_sha256_names()
    assert t08_numerical_policy.audit(policy, v1, declared) == []

    def tampered(edit: Any) -> list[str]:
        copied = copy.deepcopy(policy)
        edit(copied)
        return t08_numerical_policy.audit(copied, v1, declared)

    assert any(
        p.startswith("(a)")
        for p in tampered(lambda d: d["kind_floors"]["pressure"].update(floor="0.1"))
    )
    assert any(p.startswith("(b)") for p in tampered(lambda d: d.update(relative="1e-8")))
    assert any(p.startswith("(b)") for p in tampered(lambda d: d["floors"].pop("merit")))
    assert any(
        p.startswith("(c)") for p in tampered(lambda d: d["text_with_floats"].update(token=r"\d+"))
    )
    assert any(
        p.startswith("(d)") for p in tampered(lambda d: d["exact_sha256"].append("state_sha256"))
    )


def test_n5_exact_fields_is_documented_as_not_enforced() -> None:
    """T08 review 3, N5: v2 carries v1's `exact_fields` and no comparator enforces it, so the
    policy file says so where the key is, as a comment (the data stay v1's, A1 (b)). The note
    stays true only while neither comparator reads the key."""
    lines = t08_numerical_policy.V2.read_text(encoding="utf-8").splitlines(keepends=True)
    at = lines.index(t08_numerical_policy.EXACT_FIELDS_KEY)
    note = t08_numerical_policy.EXACT_FIELDS_NOTE.splitlines(keepends=True)
    assert lines[at - len(note) : at] == note
    assert all(line.lstrip().startswith("#") for line in note)
    assert "Inert" in note[0] and "enforced by neither comparator" in note[0]
    compare = REPO_ROOT / "src" / "openflowsheet" / "run" / "compare.py"
    replay = REPO_ROOT / "src" / "openflowsheet" / "run" / "replay.py"
    for source in (compare, replay):
        assert "exact_fields" not in source.read_text(encoding="utf-8"), source


# ------------------------------------------------------------------------------------------ A3


def test_a3_c_the_policy_is_required_and_known() -> None:
    with pytest.raises(TypeError):
        differences({"a": 1.0}, {"a": 1.0})  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="unknown numerical policy"):
        differences({"a": 1.0}, {"a": 1.0}, policy_id="K04-numerical-policy-v3")
    with pytest.raises(TypeError):
        differences({"a": 1.0}, {"a": 1.0}, policy_id=V1, variable_kinds={})
    assert (V1_POLICY_ID, CURRENT_POLICY_ID) == (V1, V2)


@pytest.fixture(scope="module")
def high_recycle(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    """K05's registered SYN-001-high-recycle, written by this build, and a fresh rerun of it."""
    from openflowsheet.application.revision_run import registered_case, rerun_registered

    case = registered_case("SYN-001-high-recycle")
    assert case is not None
    directory = tmp_path_factory.mktemp("archive")
    rerun_registered(case, directory, run_id="SYN-001-high-recycle")
    fresh = rerun_registered(case, tmp_path_factory.mktemp("rerun"), run_id="rerun")
    return directory, dict(fresh.artifacts)


def reseal(source: Path, target: Path, policy_id: str) -> Path:
    """`source`'s bundle written again by the project's own writer, naming `policy_id` in its
    manifest and in every document that records one (the certificate), as a record made under
    that policy would."""
    from openflowsheet.run.bundle import read_artifact, read_manifest, write_bundle

    manifest, _ = read_manifest(source)
    artifacts = {name: read_artifact(source, name) for name in manifest.artifacts}
    for document in artifacts.values():
        if isinstance(document, dict) and "numerical_policy_id" in document:
            document["numerical_policy_id"] = policy_id
    write_bundle(target, replace(manifest, numerical_policy_id=policy_id), artifacts)
    return target


def _u_diag_moved(artifacts: dict[str, Any]) -> dict[str, Any]:
    """The rerun with one event's `u_diag_min_abs` × 0.6: a pivot-path change (D4)."""
    moved = json.loads(json.dumps(artifacts))
    event = next(
        e
        for e in moved["solve-events.json"]
        if isinstance(e.get("linear"), dict) and e["linear"].get("u_diag_min_abs")
    )
    event["linear"]["u_diag_min_abs"] *= 0.6
    return moved


def test_a3_a_a_v1_record_is_compared_under_v1(
    high_recycle: tuple[Path, Any], tmp_path: Path
) -> None:
    """Frank's Q4: not refused. v1's comparator, frozen, still flags the pivot diagnostic. The
    rerun's certificate names the policy this build records; the archive's names v1, and that
    field alone is read as the archive's (`replay._as_recorded`)."""
    from openflowsheet.run.replay import Rerun, replay

    directory, fresh = high_recycle
    assert fresh["solution-certificate.json"]["numerical_policy_id"] == V2
    v1_record = reseal(directory, tmp_path / "v1", V1)
    clean = replay(v1_record, Rerun(fresh))
    assert clean.mode in COMPARED and clean.verdict == "MATCH", clean.differences
    assert clean.bitwise_floats is True
    moved = replay(v1_record, Rerun(_u_diag_moved(fresh)))
    assert moved.verdict == "MISMATCH"
    assert [entry for entry in moved.differences if "u_diag_min_abs" in entry] == list(
        moved.differences
    )
    foreign = json.loads(json.dumps(fresh))
    foreign["solution-certificate.json"]["numerical_policy_id"] = "K04-numerical-policy-v3"
    named = replay(v1_record, Rerun(foreign))
    assert named.verdict == "MISMATCH"
    assert paths(list(named.differences)) == ["solution-certificate.json<root>.numerical_policy_id"]


def test_a15_this_build_records_v2(high_recycle: tuple[Path, Any]) -> None:
    """A15's recording half: the run manifest and the certificate of a run by this build."""
    from openflowsheet.run.bundle import read_artifact, read_manifest

    directory, _ = high_recycle
    assert read_manifest(directory)[0].numerical_policy_id == V2
    assert read_artifact(directory, "solution-certificate.json")["numerical_policy_id"] == V2


def test_a3_b_the_same_record_resealed_with_v2_is_compared_under_v2(
    high_recycle: tuple[Path, Any], tmp_path: Path
) -> None:
    from openflowsheet.run.bundle import verify_bundle
    from openflowsheet.run.replay import Rerun, replay

    directory, fresh = high_recycle
    resealed = reseal(directory, tmp_path / "v2", V2)
    assert verify_bundle(resealed).ok
    report = replay(resealed, Rerun(_u_diag_moved(fresh)))
    assert report.mode in COMPARED and report.verdict == "MATCH", report.differences
    assert report.bitwise_floats is False


def test_a3_an_unknown_policy_is_refused_and_not_rerun(
    high_recycle: tuple[Path, Any], tmp_path: Path
) -> None:
    from openflowsheet.application.revision_run import reproduce_bundle
    from openflowsheet.run.bundle import verify_bundle
    from openflowsheet.run.replay import Rerun, replay

    directory, fresh = high_recycle
    unknown = reseal(directory, tmp_path / "v3", "K04-numerical-policy-v3")
    assert verify_bundle(unknown).ok
    report = replay(unknown, Rerun(fresh))
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert any(
        "recorded under numerical policy 'K04-numerical-policy-v3'" in reason
        for reason in report.reasons
    ), report.reasons
    assert report.differences == ()

    reproduction = reproduce_bundle(
        unknown, rerun=True, rerun_directory=tmp_path / "never", run_id="SYN-001-high-recycle"
    )
    assert reproduction.report.verdict == "NOT_RUN"
    assert reproduction.rerun_manifest is None and not (tmp_path / "never").exists()


# ------------------------------------------------------------------------------------------ A4

T1, T2 = "1cd3ed009947" + "0" * 52, "1cf23ff02335" + "1" * 52


def certificate(certificate_id: str, target: str, plan_id: str = "FSR1-plan") -> dict[str, Any]:
    return {"certificate_id": certificate_id, "plan_id": plan_id, "target_state_sha256": target}


def test_a4_the_certificate_id_by_how_it_was_built() -> None:
    digest_1, digest_2 = f"cert-{T1[:12]}", f"cert-{T2[:12]}"
    assert v2(certificate(digest_1, T1), certificate(digest_2, T2)) == []
    assert paths(v2(certificate(digest_1, T2), certificate(digest_2, T2))) == [
        "<root>.certificate_id"
    ]
    assert paths(v2(certificate("cert-P1", T1), certificate("cert-P2", T1))) == [
        "<root>.certificate_id"
    ]
    assert paths(v2(certificate("cert-P1", T1), certificate(digest_1, T1))) == [
        "<root>.certificate_id"
    ]
    # (e) v1 frozen (G1a): its exemption keys on an empty plan_id.
    found = differences(certificate(digest_1, T1), certificate(digest_2, T2), policy_id=V1)
    assert paths(found) == ["<root>.certificate_id"]


# ------------------------------------------------------------------------------------------ A5


def test_a5_level_constants_sha256_is_a_float_digest() -> None:
    def event(value: Any) -> dict[str, Any]:
        return {"level_constants_sha256": value}

    assert v2(event("a" * 64), event("b" * 64)) == []
    assert paths(v2(event("XYZ"), event("b" * 64))) == ["<root>.level_constants_sha256"]
    assert v2(event(None), event(None)) == []
    assert paths(v2(event(None), event("b" * 64))) == ["<root>.level_constants_sha256"]


# ------------------------------------------------------------------------------------------ A6


def limitation(value: float, check: str = "residual.U-MIX:MIX-energy") -> dict[str, Any]:
    return {
        "limitations": [
            {"check": check, "kind": "near_threshold", "threshold": 1.01e-3, "value": value}
        ]
    }


def test_a6_a_limitation_value_is_floored_at_its_threshold() -> None:
    assert v2(limitation(-4.4157060619909316e-4), limitation(-4.4157064985483885e-4)) == []
    assert paths(v2(limitation(4.0e-4 + 1.01e-2), limitation(4.0e-4))) == [
        "<root>.limitations[0].value"
    ]
    assert paths(v2(limitation(4.0e-4, "residual.other"), limitation(4.0e-4))) == [
        "<root>.limitations[0].check"
    ]


# ------------------------------------------------------------------------------------------ A7

KINDS = {
    "U-FLASH.Q": "heat_rate",
    "S3.T": "temperature",
    "S3.n.A": "molar_flow",
    "S3.P": "pressure",
    "X.eff": "dimensionless",
}


def state(**variables: float) -> dict[str, Any]:
    return {
        "schema_version": "solution-state-v1",
        "state_sha256": "c" * 64,
        "variable_ids": list(variables),
        "variables": dict(variables),
    }


@pytest.mark.parametrize(
    ("name", "none", "difference"),
    [
        ("U-FLASH.Q", (1.6328084717631697e-16, -4.530826668708299e-15), (0.0, 1.01e-2)),
        ("S3.T", (360.0, 360.0 + 1e-7), (360.0, 360.0 + 1e-5)),
        ("S3.n.A", (1.0, 1.0 + 3.1e-9), (1.0, 1.0 + 3.1e-7)),
        ("S3.P", (1e5, 1e5 + 1e-3), (1e5, 1e5 + 1e-1)),
        ("X.eff", (0.75, 0.75 * (1 + 1e-11)), (0.75, 0.75 * (1 + 1e-7))),
    ],
)
def test_a7_a_state_variable_is_floored_at_its_kinds_tau(
    name: str, none: tuple[float, float], difference: tuple[float, float]
) -> None:
    def compare(pair: tuple[float, float]) -> list[str]:
        return v2(state(**{name: pair[1]}), state(**{name: pair[0]}), variable_kinds=KINDS)

    assert compare(none) == []
    assert paths(compare(difference)) == [f"<root>.variables.{name}"]


def test_a7_g_h_kinds_are_required_and_every_variable_is_compared() -> None:
    found = v2(state(**{"U-FLASH.Q": 1.0}), state(**{"U-FLASH.Q": 1.0}))
    assert len(found) == 1 and "declared kinds not supplied" in found[0]
    absent = v2(
        state(**{"S3.T": 360.0}), state(**{"S3.T": 360.0, "S3.P": 1e5}), variable_kinds=KINDS
    )
    assert "<root>.variables.S3.P" in paths(absent)


# ------------------------------------------------------------------------------------------ A8


def split(total: float, label: str = "FLOWING") -> dict[str, Any]:
    return {"phase_branch": {"S3": label, "S3_split": {"vapor_total": total, "vapor": [total]}}}


def test_a8_phase_branch_flows_are_molar_flows() -> None:
    assert v2(split(1e-17), split(0.0)) == []
    assert paths(v2(split(3.1e-7), split(0.0))) == [
        "<root>.phase_branch.S3_split.vapor[0]",
        "<root>.phase_branch.S3_split.vapor_total",
    ]
    assert paths(v2(split(0.0, "ZERO_FLOW"), split(0.0))) == ["<root>.phase_branch.S3"]


# ------------------------------------------------------------------------------------------ A9


def linear(minimum: Any, maximum: Any = 1.0) -> dict[str, Any]:
    return {"linear": {"u_diag_min_abs": minimum, "u_diag_max_abs": maximum}}


def test_a9_the_pivot_path_diagnostics_are_checked_for_kind_only() -> None:
    assert v2(linear(0.04477807556912964), linear(0.0731916085271539)) == []
    for emitted in (-1.0, math.nan, "0.1", True):
        assert paths(v2(linear(emitted), linear(0.1))) == ["<root>.linear.u_diag_min_abs"], emitted
    assert paths(v2(linear(2.0, 1.0), linear(0.1, 1.0))) == ["<root>.linear.u_diag_min_abs"]
    ratio = v2({"regularity": {"u_diagonal_ratio": 1.5}}, {"regularity": {"u_diagonal_ratio": 0.2}})
    assert paths(ratio) == ["<root>.regularity.u_diagonal_ratio"]
    assert paths(v2(linear(None), linear(0.1))) == ["<root>.linear.u_diag_min_abs"]


# ----------------------------------------------------------------------------------------- A10

F2_MESSAGE = "H_S3_vapor: H_S3_vapor: temperature {} K outside [280.0, 440.0] K"


def message(text: str) -> dict[str, Any]:
    return {"message": text}


def test_a10_a_float_in_text_is_compared_as_a_float() -> None:
    committed = F2_MESSAGE.format("52.114475231324604")
    assert v2(message(F2_MESSAGE.format("52.11447523132472")), message(committed)) == []
    moved = F2_MESSAGE.format(repr(52.114475231324604 * (1 + 1e-6)))
    differing = [
        (moved, committed),
        (committed.replace("outside", "inside"), committed),
        (committed + " 1.5", committed),
        (
            "FSR1-e3f2d5372330-syn001-67e472816d4d-44f894ff62f9",
            "FSR1-e3f2d5372330-syn001-67e472816d4d-44f894ff62fa",
        ),
        ("no trial accepted in 21 steps", "no trial accepted in 22 steps"),
        ("not an overshoot (§4.6)", "not an overshoot (§4.7)"),
        ("chord -0.5", "chord 0.5"),
    ]
    for emitted, reference in differing:
        found = v2(message(emitted), message(reference))
        assert found and all(path.startswith("<root>.message") for path in paths(found)), (
            emitted,
            found,
        )
    cause = v2({"cause": "chord 0.5"}, {"cause": "chord 0.5000000000001"})
    assert cause == []


# ----------------------------------------------------------------------------------------- A11


@pytest.mark.parametrize(
    ("key", "none", "difference"),
    [
        ("residual_normalized", (1e-13, 5e-13), (1e-10, 2e-10)),
        ("merit", (1e-18, 2e-18), (1e-10, 2e-10)),
        ("step_inf_scaled", (1e-10, 5e-10), (0.5, 0.6)),
        ("rcond_1", (1.33e-4, 1.33e-4 * (1 + 1e-11)), (1.33e-4, 1.5e-4)),
    ],
)
def test_a11_the_carried_rows_are_not_vacuous(
    key: str, none: tuple[float, float], difference: tuple[float, float]
) -> None:
    assert v2({key: none[1]}, {key: none[0]}) == []
    assert paths(v2({key: difference[1]}, {key: difference[0]})) == [f"<root>.{key}"]


def test_a11_a_check_value_is_floored_at_its_tolerance() -> None:
    def check(value: float) -> dict[str, Any]:
        return {"checks": [{"id": "c", "tolerance": 3.1e-8, "value": value}]}

    assert v2(check(3.1e-9), check(0.0)) == []
    assert paths(v2(check(3.1e-7), check(0.0))) == ["<root>.checks[0].value"]


# ----------------------------------------------------------------------------------------- A12


def test_a12_b_the_f2_pairs_differ_under_v1_and_not_under_v2() -> None:
    """`docs/t08-rc-record.md` F2, transcribed (recorded value against archived value); NET02's
    thresholds and check ids as its certificate records them."""
    net02 = [
        ("residual.U-MIX:MIX-energy", 1.01e-3, -0.00044157064985483885, -0.00044157060619909316),
        ("residual.U-HEAT:HEAT-duty", 1.01e-3, 0.0004971807647962123, 0.0004971807211404666),
        (
            "residual.U-PHF:PHF-equilibrium:A",
            9.3e-8,
            1.1384663878288848e-08,
            1.1384653220147811e-08,
        ),
    ]

    def limitations(column: int) -> dict[str, Any]:
        return {
            "limitations": [
                {"check": c, "kind": "near_threshold", "threshold": t, "value": row[column]}
                for c, t, *row in net02
            ]
        }

    net03_kinds = {"U-FL2.Q": "heat_rate"}
    pairs: list[tuple[str, Any, Any, dict[str, Any]]] = [
        (
            "certificate_id",
            certificate("cert-1cd3ed009947", T1),
            certificate("cert-1cf23ff02335", T2),
            {},
        ),
        (
            "U-FL2.Q",
            state(**{"U-FL2.Q": -3.9700052307840726e-11}),
            state(**{"U-FL2.Q": 1.1073945456610047e-11}),
            {"variable_kinds": net03_kinds},
        ),
        ("u_diag_min_abs", linear(0.12785732202141917), linear(0.13970043213598085), {}),
        (
            "message",
            message(F2_MESSAGE.format("52.11447523132472")),
            message(F2_MESSAGE.format("52.114475231324604")),
            {},
        ),
        (
            "level_constants_sha256",
            {"level_constants_sha256": "d" * 64},
            {"level_constants_sha256": "e" * 64},
            {},
        ),
        ("limitations", limitations(0), limitations(1), {}),
    ]
    for label, emitted, committed, kwargs in pairs:
        under_v1 = differences(emitted, committed, policy_id=V1)
        assert under_v1 and all(label in entry for entry in under_v1), (label, under_v1)
        assert v2(emitted, committed, **kwargs) == [], label
    assert len(differences(limitations(0), limitations(1), policy_id=V1)) == 3


# ----------------------------------------------------------------------------------------- A13


def test_a13_every_float_difference_names_the_policy_and_the_floor_used() -> None:
    floats = [
        (v2({"residual_normalized": 2e-10}, {"residual_normalized": 1e-10}), 1e-12),
        (v2(limitation(4.0e-4 + 1.01e-2), limitation(4.0e-4)), 1.01e-3),
        (
            v2(state(**{"S3.T": 361.0}), state(**{"S3.T": 360.0}), variable_kinds=KINDS),
            1e-6,
        ),
        (v2(split(3.1e-7), split(0.0))[:1], 3.1000000000000006e-08),
        (v2(message("chord -0.5"), message("chord 0.5")), 0.0),
        (v2({"one_norm": 2.0}, {"one_norm": 1.0}), 0.0),
    ]
    for found, floor in floats:
        assert len(found) == 1, found
        assert V2 in found[0] and f"{floor!r} absolute" in found[0], found
    every = [entry for found, _ in floats for entry in found]
    every += v2(linear(-1.0), linear(0.1)) + v2(certificate("cert-P1", T1), certificate("x", T1))
    assert not [entry for entry in every if "interim" in entry]


# ----------------------------------------------------------------------------------------- A15


@pytest.mark.parametrize(
    ("schema", "fixture"),
    [
        ("run-manifest.schema.json", "run_manifest/valid/syn001_nominal.json"),
        (
            "solution-certificate.schema.json",
            "solution_certificate/valid/syn001_nominal_verified.json",
        ),
    ],
)
def test_a15_both_schemas_accept_v1_and_v2_and_refuse_another(schema: str, fixture: str) -> None:
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    from openflowsheet.application.types import published_schemas

    registry = Registry().with_resources(
        (schema_id, Resource(contents=dict(document), specification=DRAFT202012))
        for schema_id, document in published_schemas().items()
    )
    validator = Draft202012Validator(load_json(REPO_ROOT / "schemas" / schema), registry=registry)
    document = load_json(REPO_ROOT / "tests" / "fixtures" / "schemas" / fixture)
    for policy_id, valid in ((V1, True), (V2, True), ("K04-numerical-policy-v3", False)):
        errors = list(validator.iter_errors({**document, "numerical_policy_id": policy_id}))
        assert (not errors) is valid, (policy_id, [error.message for error in errors])


# ----------------------------------------------------------------------------------------- A14


@pytest.fixture(scope="module")
def rc_bundles(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The two A14 source bundles, as `bundles-write` lays them out, re-sealed to name v2 (the
    records a build recording v2 writes; this build's recording switch is held)."""
    from t07_corpus import CORPUS

    from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
    from openflowsheet.application.revision_run import (
        Route,
        registered_case,
        rerun_registered,
        run_revision_session,
        select_route,
    )
    from openflowsheet.verify.certificate import CheckPolicy

    written = tmp_path_factory.mktemp("written")
    document = CORPUS["SYN-001-nominal"]()
    route = select_route(document)
    assert isinstance(route, Route)
    policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
    assert policy is not None
    run_revision_session(
        route,
        document,
        written / "g8",
        run_id="run-SYN-001-nominal",
        policy=policy,
        check_policy=CheckPolicy(),
        policy_requested=DEFAULT_POLICY_ID,
    )
    case = registered_case("SYN-001-high-recycle")
    assert case is not None
    rerun_registered(case, written / "k05", run_id="SYN-001-high-recycle")

    bundles = tmp_path_factory.mktemp("bundles")
    reseal(written / "g8", bundles / "g8" / "SYN-001-nominal", V2)
    reseal(written / "k05", bundles / "k05" / "SYN-001-high-recycle", V2)
    return bundles


@pytest.mark.parametrize(
    ("control", "verdict"), [("c1", "MISMATCH"), ("c2", "MISMATCH"), ("c3", "MATCH")]
)
def test_a14_the_rc_controls(rc_bundles: Path, tmp_path: Path, control: str, verdict: str) -> None:
    import t08_rc

    set_name, bundle = t08_rc.A14_CONTROL_BUNDLES[control]
    row = t08_rc.run_control(control, rc_bundles / set_name / bundle, tmp_path)
    assert row["integrity_ok"], row
    assert row["numerical_policy_id"] == V2
    assert row["verdict"] == verdict and row["passed"], row
    if verdict == "MISMATCH":
        assert paths(row["differences"]) == [row["mutated"]], row["differences"]
    if control == "c3":
        # Review 3, N6: the moved pivot was read and forgiven, so the floats are not bitwise.
        assert row["bitwise_floats"] is False, row


def test_a14_c3_fails_if_the_events_go_unread(
    rc_bundles: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review 3, N6: a `MATCH` with bitwise floats is what a replay that stopped reading
    `solve-events.json` would report for C3; the control does not pass on it."""
    from types import SimpleNamespace

    import t08_rc

    from openflowsheet.application import revision_run

    report = SimpleNamespace(
        mode="compatible_reproduction", verdict="MATCH", differences=(), bitwise_floats=True
    )
    monkeypatch.setattr(
        revision_run, "reproduce_bundle", lambda *args, **kwargs: SimpleNamespace(report=report)
    )
    set_name, bundle = t08_rc.A14_CONTROL_BUNDLES["c3"]
    row = t08_rc.run_control("c3", rc_bundles / set_name / bundle, tmp_path)
    assert row["integrity_ok"] and row["verdict"] == "MATCH" and row["bitwise_floats"] is True
    assert not row["passed"], row


C2_PRECONDITION_PROBE = """
import sys
sys.path.insert(0, sys.argv[1])
import t08_rc
cases = {
    "a near_threshold limitation": {"limitations": [{"kind": "near_threshold"}], "checks": []},
    "a near-threshold check": {"limitations": [], "checks": [{"near_threshold": True}]},
    "a FAILED verdict": {"limitations": [], "checks": [], "verification_status": "FAILED"},
}
for label, fields in cases.items():
    certificate = {"verification_status": "VERIFIED", **fields}
    try:
        t08_rc.c2_fail_the_verdict({"solution-certificate.json": certificate})
    except ValueError as error:
        print(label, "->", error)
    else:
        print(label, "-> NOT RAISED")
"""


def test_a14_c2_preconditions_raise_under_python_o() -> None:
    """Review 3, N6: C2's preconditions are raised errors, which `python -O` does not strip."""
    found = subprocess.run(
        [sys.executable, "-O", "-c", C2_PRECONDITION_PROBE, str(REPO_ROOT / "scripts")],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    ).stdout.splitlines()
    assert len(found) == 3 and not any("NOT RAISED" in line for line in found), found
    assert all("C2's precondition" in line for line in found), found
