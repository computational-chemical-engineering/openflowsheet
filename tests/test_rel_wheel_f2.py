"""Line 0.6's RC item `WHEEL-F2` (`docs/briefs/REL060-line-0.6.md` D-5, WV-1 to WV-6).

`scripts/wheel_data_check.py --f2` runs F2's v2 route through the Python binding of an installed
package and of the checkout: the raised twins of `g8/SYN-001-T06-NET02` and `s11-gp/GP-C1` solve
as their v1 documents (WV-3), with F0's registered M3 `artifact_r0_sha256` (WV-4, read from
`benchmarks/f0/corpus.json`, never through the code under test), and N, the base's twin with
`thermal_coordinate` `h_mass`, is refused (WV-5). WV-6's five controls, each of which must fail
its check:

- (a) the installed `openflowsheet/_data/schemas/process-revision-v2.schema.json` deleted: WV-3;
- (b) the installed `openflowsheet/records/legacy_index.json` with GP-C1's `CH3OH` record SHA-256
  altered: WV-3 (the lowering refuses `component:CH3OH`);
- (c) a probe document whose v2 `artifact_r0_sha256` is replaced by another 64-hex value: WV-3
  and WV-4;
- (d) a probe document with the refusal string altered: WV-5;
- (e) N built with `thermal_coordinate` `T`: WV-5 (it is admitted).

The installed package of (a), (b) and (e) is, as in `tests/test_rel_wheel_f1_f3.py`, the
checkout's `src/openflowsheet` copied (links followed) into a scratch `site-packages`, probed by
`wheel_data_check.py probe --f2` from an empty directory with only that copy on the path. The
reference is the probe in the checkout (`--in-checkout`). The documents of (c) and (d) are edits
of the intact pair, which passes every clause, so each failure is the edit's. That the wheel
passes is the item's own run at C.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import wheel_data_check  # noqa: E402

SCRIPT = REPO_ROOT / "scripts" / "wheel_data_check.py"
REGISTERED = wheel_data_check.registered_r0(
    (REPO_ROOT / wheel_data_check.F0_REGISTRY).read_text(encoding="utf-8")
)
SCHEMA = Path("_data/schemas/process-revision-v2.schema.json")
INDEX = Path("records/legacy_index.json")
GP_RECORDS = "benchmarks/s10/records.yaml"
KEYS = sorted(f"{s}/{n}" for s, n in wheel_data_check.F2_STATES)


def _probe(
    out: Path, inputs: Path, *, cwd: Path, pythonpath: Path, checkout: bool
) -> dict[str, Any]:
    """`wheel_data_check.py probe --f2` with only `pythonpath` on the path and the thread
    variables at 1, as the item runs it; its document."""
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment |= dict.fromkeys(wheel_data_check.F2_THREADS, "1")
    environment["PYTHONPATH"] = str(pythonpath)
    flags = ["--in-checkout"] if checkout else []
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "probe", "--f2", *flags, "--inputs", str(inputs)]
        + ["--out", str(out)],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    document: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
    return document


def _altered(digest: str) -> str:
    return ("0" if digest[0] != "0" else "1") + digest[1:]


def _alter_gp_c1_record(index_path: Path) -> None:
    """(b): GP-C1's `CH3OH` record SHA-256 in an installed legacy index, altered."""
    index = json.loads(index_path.read_text(encoding="utf-8"))
    (entry,) = (entry for entry in index["files"] if entry["path"] == GP_RECORDS)
    (record,) = (record for record in entry["records"] if record["id"] == "CH3OH")
    record["sha256"] = _altered(record["sha256"])
    index_path.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def inputs() -> dict[str, dict[str, Any]]:
    """The item's inputs (N with `h_mass`) and control (e)'s (N with `T`)."""
    return {"item": wheel_data_check.f2_inputs(), "e": wheel_data_check.f2_inputs("T")}


@pytest.fixture(scope="module")
def probes(
    tmp_path_factory: pytest.TempPathFactory, inputs: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """The checkout's probe, and the probe of an installed copy: intact, (a), (b) and (e)."""
    tmp = tmp_path_factory.mktemp("f2")
    empty = tmp / "cwd"
    empty.mkdir()
    paths = {}
    for name, document in inputs.items():
        paths[name] = tmp / f"inputs-{name}.json"
        paths[name].write_bytes(wheel_data_check.canonical(document))
    found = {
        "checkout": _probe(
            tmp / "checkout.json",
            paths["item"],
            cwd=REPO_ROOT,
            pythonpath=REPO_ROOT / "src",
            checkout=True,
        )
    }
    sites: dict[str, Path] = {}
    for name in ("intact", "a", "b"):
        site = tmp / name / "venv" / "lib" / "python3.13" / "site-packages"
        shutil.copytree(
            REPO_ROOT / "src" / "openflowsheet",
            site / "openflowsheet",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        sites[name] = site
    (sites["a"] / "openflowsheet" / SCHEMA).unlink()
    _alter_gp_c1_record(sites["b"] / "openflowsheet" / INDEX)
    for name, site, given in (
        ("intact", sites["intact"], "item"),
        ("a", sites["a"], "item"),
        ("b", sites["b"], "item"),
        ("e", sites["intact"], "e"),
    ):
        found[name] = _probe(
            tmp / f"{name}.json", paths[given], cwd=empty, pythonpath=site, checkout=False
        )
        assert found[name]["module_file"] == str(site / "openflowsheet" / "__init__.py")
    return found


def _findings(installed: dict[str, Any], checkout: dict[str, Any]) -> dict[str, bool]:
    return wheel_data_check.f2_findings(installed, checkout, REGISTERED)


def _passing(probes: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Copies of the intact installed copy's probe and the checkout's: a pair that passes."""
    installed, checkout = copy.deepcopy(probes["intact"]), copy.deepcopy(probes["checkout"])
    found = _findings(installed, checkout)
    assert found == dict.fromkeys(found, True)
    return installed, checkout


def _only_failing(found: dict[str, bool]) -> set[str]:
    return {clause for clause, ok in found.items() if not ok}


def test_the_registered_m3_at_c() -> None:
    # F0's registry (D-5's sanity values, measured at 43f0b7f5, are these).
    assert REGISTERED == {
        "g8/SYN-001-T06-NET02": "414fba515c51d5477b25c21a8395616a9c04b2b76bb0365772c7cd4b865a78e7",
        "s11-gp/GP-C1": "6e6ab158c5c1b7a52067bab786a5f3c0bc64c9600995f6be64605ad0d7e56f88",
    }


def test_the_inputs(inputs: dict[str, dict[str, Any]]) -> None:
    said = wheel_data_check.inputs_findings(inputs["item"])
    assert said["ok"] is True
    assert said["differences"] == [wheel_data_check.THERMAL_COORDINATE]
    assert sorted(said["documents"]) == sorted(
        [f"{key}:{version}" for key in KEYS for version in ("v1", "v2")] + ["N"]
    )
    assert len(set(said["documents"].values())) == 5
    assert all(wheel_data_check.HEX64.fullmatch(d) for d in said["documents"].values())
    # (e)'s N is the base's twin itself: the inputs check fails too, beside WV-5.
    said_e = wheel_data_check.inputs_findings(inputs["e"])
    assert (said_e["ok"], said_e["differences"]) == (False, [])


def test_canonical_bytes_and_differences() -> None:
    assert wheel_data_check.canonical({"b": 1, "a": ["é", 2.5]}) == '{"a":["é",2.5],"b":1}'.encode()
    differ = wheel_data_check.differences
    assert differ({"a": {"b/c": 1}}, {"a": {"b/c": 2}}) == ["/a/b~1c"]
    assert differ({"a": [1, 2]}, {"a": [1, 2, 3]}) == ["/a"]
    assert differ({"a": 1}, {"a": 1.0}) == ["/a"]
    assert differ({"a": 1}, {"b": 1}) == ["/a", "/b"]
    assert differ({"x": [{"y": True}]}, {"x": [{"y": True}]}) == []


def test_the_checkout_probe(probes: dict[str, dict[str, Any]]) -> None:
    checkout = probes["checkout"]
    assert checkout["module_file"] == str(REPO_ROOT / "src" / "openflowsheet" / "__init__.py")
    assert checkout["entry_points"] == []
    assert checkout["threads"] == dict.fromkeys(wheel_data_check.F2_THREADS, "1")
    assert sorted(checkout["runs"]) == KEYS
    for key in KEYS:
        assert checkout["runs"][key]["v2"]["artifact_r0_sha256"] == REGISTERED[key]


def test_an_intact_installed_copy_passes(probes: dict[str, dict[str, Any]]) -> None:
    found = _findings(probes["intact"], probes["checkout"])
    assert found == dict.fromkeys(found, True)
    assert probes["intact"]["runs"] == probes["checkout"]["runs"]


def test_control_a_v2_schema_deleted_from_the_installed_package(
    probes: dict[str, dict[str, Any]],
) -> None:
    runs = probes["a"]["runs"]
    assert all(not wheel_data_check._ran(runs[key]["v2"]) for key in KEYS)
    assert all(wheel_data_check._ran(runs[key]["v1"]) for key in KEYS)
    assert "v2_runs_as_v1" in _only_failing(_findings(probes["a"], probes["checkout"]))


def test_control_b_a_gp_c1_record_altered_in_the_installed_index(
    probes: dict[str, dict[str, Any]],
) -> None:
    run = probes["b"]["runs"]["s11-gp/GP-C1"]["v2"]
    assert not wheel_data_check._ran(run)
    assert "component:CH3OH" in json.dumps(run)
    assert "v2_runs_as_v1" in _only_failing(_findings(probes["b"], probes["checkout"]))


@pytest.mark.parametrize("side", ["installed", "checkout"])
def test_control_c_another_v2_r0(probes: dict[str, dict[str, Any]], side: str) -> None:
    pair = dict(zip(("installed", "checkout"), _passing(probes), strict=True))
    run = pair[side]["runs"]["s11-gp/GP-C1"]["v2"]
    run["artifact_r0_sha256"] = _altered(run["artifact_r0_sha256"])
    found = _findings(pair["installed"], pair["checkout"])
    assert _only_failing(found) == {"v2_runs_as_v1", "r0_registered"}


def test_a_run_both_versions_answer_wrongly_alike_fails_wv4(
    probes: dict[str, dict[str, Any]],
) -> None:
    # WV-4 is the independent expectation: v1 and v2 agreeing with each other is not enough.
    installed, checkout = _passing(probes)
    for document in (installed, checkout):
        for version in ("v1", "v2"):
            run = document["runs"]["g8/SYN-001-T06-NET02"][version]
            run["artifact_r0_sha256"] = _altered(run["artifact_r0_sha256"])
    assert _only_failing(_findings(installed, checkout)) == {"r0_registered"}


@pytest.mark.parametrize("side", ["installed", "checkout"])
def test_control_d_the_refusal_string_altered(probes: dict[str, dict[str, Any]], side: str) -> None:
    pair = dict(zip(("installed", "checkout"), _passing(probes), strict=True))
    raised = pair[side]["refusal"]["N"]["raised"]
    raised["unbound"] = raised["unbound"].replace("h_mass", "h_molar")
    assert _only_failing(_findings(pair["installed"], pair["checkout"])) == {"refusal"}


def test_control_e_n_with_t_is_admitted(probes: dict[str, dict[str, Any]]) -> None:
    assert probes["e"]["refusal"]["N"] == {"admitted": "AdmissionReport"}
    assert _only_failing(_findings(probes["e"], probes["checkout"])) == {"refusal"}


@pytest.mark.parametrize(
    ("clause", "edit"),
    [
        ("site_packages", lambda d: d.update(module_file="/repo/src/openflowsheet/__init__.py")),
        ("no_extensions", lambda d: d.update(entry_points=["x = pkg.module:Plugin"])),
        ("threads", lambda d: d["threads"].update(OMP_NUM_THREADS=None)),
        (
            "v2_runs_as_v1",
            lambda d: d["runs"]["g8/SYN-001-T06-NET02"]["v2"]["artifacts"].pop(
                "solution-state.json"
            ),
        ),
        ("v2_runs_as_v1", lambda d: d["runs"]["s11-gp/GP-C1"]["v1"].update(outcome="FAILED")),
        ("v2_runs_as_v1", lambda d: d["runs"]["s11-gp/GP-C1"]["v2"].update(validation="INVALID")),
        ("v2_runs_as_v1", lambda d: d["runs"].pop("s11-gp/GP-C1")),
        ("refusal", lambda d: d["refusal"]["N"]["raised"].update(code="invalid_request")),
        ("refusal", lambda d: d["refusal"].update(v2={"raised": {"code": "x", "unbound": "y"}})),
    ],
)
def test_each_further_clause_fails_its_check(
    probes: dict[str, dict[str, Any]], clause: str, edit: Any
) -> None:
    installed, checkout = _passing(probes)
    edit(installed)
    assert clause in _only_failing(_findings(installed, checkout))


def test_an_artifact_index_unequal_to_v1s_fails_wv3(probes: dict[str, dict[str, Any]]) -> None:
    installed, checkout = _passing(probes)
    artifacts = installed["runs"]["s11-gp/GP-C1"]["v2"]["artifacts"]
    artifacts["solution-state.json"] = _altered(artifacts["solution-state.json"])
    assert _only_failing(_findings(installed, checkout)) == {"v2_runs_as_v1"}


def test_no_registered_value_fails_wv4(probes: dict[str, dict[str, Any]]) -> None:
    installed, checkout = _passing(probes)
    for registered in ({}, wheel_data_check.registered_r0("{}")):
        assert (
            wheel_data_check.f2_findings(installed, checkout, registered)["r0_registered"] is False
        )


def test_the_item_refuses_a_checkout_not_at_c() -> None:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--commit", "0" * 40, "--f2"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 2
    assert "not at " + "0" * 40 in done.stderr
