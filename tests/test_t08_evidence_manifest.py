"""T08 close (§15 W5.3, §8.1 item 5): the evidence manifest generator
(`scripts/t08_evidence_manifest.py`) and the manifest it wrote.

The generator's expensive inputs (the tests it runs, CI, the gate script's run) are replaced here by
stated ones; what it reads from the repository (the two catalogues, the committed RC records, the
verdict documents, ADR 0021, the ledger, the envelope, git) is read for real. Asserted: one check
per catalogue assertion and no other; the output validates and holds no angle-bracketed text;
`tested` only when every check passes or is a FAIL whose clause ADR 0021 D3 accepts (V14 (b):
T08.A70 and B23); a failed, skipped or missing node, a CI run at another head, a tampered RC record
or an unaccepted FAIL keeps the status `implemented`; `reviewed` is never set. Once committed, the
manifest at `C` is checked as written.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from conftest import REPO_ROOT

C = "67c66d98587f23bd7dfe8da28a8facccc92da21e"
MANIFEST = REPO_ROOT / "evidence" / "T08" / C / "manifest.json"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t08_evidence_manifest", REPO_ROOT / "scripts" / "t08_evidence_manifest.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


generator = _load()
PENDING = f"no T08 manifest: evidence/T08/{C}/manifest.json does not exist (§8.1 item 5)"


def _node(selector: str) -> str:
    path, _, name = selector.partition("::")
    if not name:
        return f"{path}::test_stated"
    if name.endswith("*"):
        return f"{path}::{name[:-1]}stated"
    return f"{path}::{name}"


def _tests(**outcomes: tuple[str, str]) -> Any:
    """One passing node per selector of the catalogue's checks, with `outcomes` replacing some."""
    nodes = {_node(s): ("passed", "") for spec in generator.SPECS for s in spec.tests}
    nodes.update(outcomes)
    return generator.TestRun(nodes, 0)


def _ci(head: str = C) -> list[dict[str, Any]]:
    jobs = sorted({job for spec in generator.SPECS for job in spec.jobs})
    return [
        {
            "databaseId": 1,
            "headSha": head,
            "event": "workflow_dispatch",
            "conclusion": "success",
            "jobs": [{"name": name, "conclusion": "success"} for name in jobs],
        },
        {"databaseId": 2, "headSha": head, "event": "push", "conclusion": "success", "jobs": []},
    ]


def _inputs(**overrides: Any) -> Any:
    stated: dict[str, Any] = {
        "commit": C,
        "tests": _tests(),
        "ci": _ci(),
        "gate": {"exit_code": 1, "reasons": [PENDING]},
    }
    stated.update(overrides)
    return generator.Inputs(**stated)


def _check(manifest: dict[str, Any], identifier: str) -> dict[str, Any]:
    (found,) = [entry for entry in manifest["checks"] if entry["id"] == identifier]
    return found


@pytest.fixture(scope="module")
def stated() -> dict[str, Any]:
    manifest: dict[str, Any] = generator.build(_inputs())
    return manifest


def test_one_check_per_catalogue_assertion_and_no_other(stated: dict[str, Any]) -> None:
    listed = generator.catalogue()
    assert [entry["id"] for entry in stated["checks"]] == [f"T08.{i}" for i in listed]
    assert sum(i.startswith("A") for i in listed) == 44
    assert sum(i.startswith("B") for i in listed) == 41


def test_the_manifest_validates_and_holds_no_angle_bracketed_text(stated: dict[str, Any]) -> None:
    assert generator.problems(stated) == []
    assert stated["work_package"] == "T08" and stated["commit"] == C
    assert stated["requirements"] == ["D04", "A10", "D17", "D20"]


def test_tested_with_v14_b_the_only_fail_and_accepted(stated: dict[str, Any]) -> None:
    assert stated["status"] == "tested"
    failed = {entry["id"] for entry in stated["checks"] if entry["result"] != "pass"}
    assert failed == {"T08.A70", "T08.B23"}
    for identifier in failed:
        entry = _check(stated, identifier)
        assert entry["result"] == "fail" and entry["value"]["accepted_fail"] is True
    assert stated["review"] == {"numerical": "pending", "process_model": "pending"}
    assert any(text.startswith("FAIL: V14 (b)") for text in stated["limitations"])


def test_b20_carries_the_attestation_and_its_disclosures(stated: dict[str, Any]) -> None:
    measured = _check(stated, "T08.B20")["value"]["measured"]
    assert all(measured["links"].values()) and all(measured["result_files_added_by"].values())
    for phrase in ("§A4.6 attestation", "LOW-root probe", "aborted first", "found inert"):
        assert phrase in measured["attestation"]
    assert measured["attestation"] in stated["limitations"]


def test_the_envelope_rows_and_the_gate_words_travel(stated: dict[str, Any]) -> None:
    import yaml

    envelope = yaml.safe_load(generator.ENVELOPE.read_text(encoding="utf-8"))
    for row in envelope["limitations"]:
        assert any(text.startswith(f"{row['id']}: ") for text in stated["limitations"])
    (gates,) = [text for text in stated["limitations"] if text.startswith("Gates V11–V20")]
    assert "V14 FAIL (V14 (b))" in gates and "V19 PASS" in gates


@pytest.mark.parametrize(
    ("outcome", "result"),
    [(("failed", ""), "fail"), (("skipped", "a guard"), "unsupported")],
    ids=["failed", "skipped"],
)
def test_a_failed_or_skipped_node_keeps_the_status(outcome: tuple[str, str], result: str) -> None:
    manifest = generator.build(_inputs(tests=_tests(**{_node(f"{generator._KC}b12*"): outcome})))
    assert _check(manifest, "T08.B12")["result"] == result
    assert manifest["status"] == "implemented"


def test_a_selector_that_ran_nothing_fails() -> None:
    tests = _tests()
    del tests.nodes[_node("tests/test_t08_b24_ptc_job.py")]
    manifest = generator.build(_inputs(tests=tests))
    assert _check(manifest, "T08.B24")["result"] == "fail"
    assert manifest["status"] == "implemented"


def test_only_a02s_pending_clause_may_skip_before_the_manifest_exists() -> None:
    node = "tests/test_t08_w1_ledger.py::test_a02_the_t08_manifest_is_listed_once_it_exists[V18]"
    skipped = (node, ("skipped", generator.MANIFEST_PENDING_SKIP))
    before = generator.build(_inputs(tests=_tests(**dict([skipped]))))
    tests = _tests(**dict([skipped]))
    after = generator.build(_inputs(tests=tests, manifest_exists=True))
    assert _check(before, "T08.A02")["value"]["tests"]["skipped_by_design"] == {
        node: generator.MANIFEST_PENDING_SKIP
    }
    assert _check(after, "T08.A02")["result"] == "unsupported"


def test_ci_at_another_head_establishes_nothing() -> None:
    manifest = generator.build(_inputs(ci=_ci(head="e" * 40)))
    for identifier in ("T08.A41", "T08.A43", "T08.B25"):
        assert _check(manifest, identifier)["result"] == "unsupported"
    assert manifest["status"] == "implemented"


def test_the_gate_may_only_miss_the_manifest_being_written() -> None:
    manifest = generator.build(_inputs(gate={"exit_code": 1, "reasons": [PENDING, "V13: x"]}))
    assert _check(manifest, "T08.A50")["result"] == "fail"


def test_a_tampered_rc_record_fails_its_checks(tmp_path: Path) -> None:
    shutil.copytree(REPO_ROOT / "evidence" / "T08" / C / "rc", tmp_path / C / "rc")
    record = tmp_path / C / "rc" / "surface" / "rc-surface.json"
    document = json.loads(record.read_text(encoding="utf-8"))
    document["passed"] = False
    record.write_text(json.dumps(document), encoding="utf-8")
    manifest = generator.build(_inputs(evidence=tmp_path))
    assert _check(manifest, "T08.A49")["result"] == "fail"
    said = _check(manifest, "T08.A49")["value"]["records"]["rc_records"]
    assert said["surface/rc-surface.json"] == "sha256 differs from rc/records.json"


def test_an_unaccepted_fail_keeps_the_status(tmp_path: Path) -> None:
    adr = generator.ADR_0021.read_text(encoding="utf-8")
    unaccepted = tmp_path / "adr.md"
    unaccepted.write_text(adr.replace("Frank's acceptance", "Acceptance"), encoding="utf-8")
    manifest = generator.build(_inputs(adr_0021=unaccepted))
    assert _check(manifest, "T08.A70")["value"].get("accepted_fail") is not True
    assert manifest["status"] == "implemented"


def test_reviewed_is_never_set() -> None:
    entries = [{"id": "T08.A00", "result": "pass", "value": {}}]
    assert generator.status(entries) == "tested"
    assert generator.status([*entries, {"id": "x", "result": "unsupported", "value": {}}]) == (
        "implemented"
    )


@pytest.mark.skipif(not MANIFEST.is_file(), reason="the T08 manifest at C is not written yet")
def test_the_committed_manifest_at_c() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert generator.problems(manifest) == []
    assert manifest["commit"] == C and manifest["status"] == "tested"
    assert [entry["id"] for entry in manifest["checks"]] == [
        f"T08.{i}" for i in generator.catalogue()
    ]
    for entry in manifest["checks"]:
        accepted = entry["result"] == "fail" and entry["value"].get("accepted_fail") is True
        assert entry["result"] == "pass" or accepted, entry["id"]
    assert copy.deepcopy(manifest["review"]) == {"numerical": "pending", "process_model": "pending"}
