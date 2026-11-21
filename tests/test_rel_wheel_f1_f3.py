"""Line 0.5's RC item `WHEEL-F1-F3` (`docs/briefs/REL050-line-0.5.md` D-5, WF-1 to WF-5).

`scripts/wheel_data_check.py --f1-f3` probes F1's registry and F3's legacy records through the
Python binding of an installed package and of the checkout. WF-5's four controls, each of which
must fail its check:

- (a) `openflowsheet/registry/builtin/core.json` deleted from an installed package: WF-3;
- (b) the installed `openflowsheet/records/legacy_index.json` deleted: WF-4;
- (c) a probe document whose digest is replaced by another 64-hex value: WF-3;
- (d) a probe document with one item dropped: WF-4's count.

The installed package of (a) and (b) is, as in `tests/test_x05_replay_from_the_wheel.py`, the
checkout's `src/openflowsheet` copied (links followed) into a scratch `site-packages`; the probe
runs there as the item runs it in the wheel's venv, by `wheel_data_check.py probe --f1-f3`. The
reference is the probe in the checkout (`--in-checkout`). N is read from the committed index, as
the item does. The documents of (c) and (d) are the checkout's probe as an installed one, a pair
that passes every clause, so each failure is the edit's.

**Finding (REL050-WF).** The same copy unedited passes WF-2 and WF-3 but not WF-4: an installed
package lists 9 legacy records (the `m01` and `s10` files, the only legacy files that are package
data), the checkout 149. ADR 0061 D8 says so ("only the `m01` and `s10` component files are
package data ... so on a wheel the `l01` and `s07` records are otherwise `data_unavailable`"), so
WF-4 as written cannot pass on a correct wheel. The test is a strict `xfail` until the design lane
restates WF-4; nothing in the check is relaxed here.
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
N = wheel_data_check.legacy_index_count(
    json.loads((REPO_ROOT / wheel_data_check.LEGACY_INDEX).read_text(encoding="utf-8"))
)
CORE = Path("registry/builtin/core.json")
INDEX = Path("records/legacy_index.json")


def _probe(out: Path, *, cwd: Path, pythonpath: Path, checkout: bool) -> dict[str, Any]:
    """`wheel_data_check.py probe --f1-f3` with only `pythonpath` on the path; its document."""
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment["PYTHONPATH"] = str(pythonpath)
    flags = ["--in-checkout"] if checkout else []
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "probe", "--f1-f3", *flags, "--out", str(out)],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    document: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
    return document


@pytest.fixture(scope="module")
def probes(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, Any]]:
    """The checkout's probe, and the probe of an installed copy: intact, (a) and (b)."""
    tmp = tmp_path_factory.mktemp("f1f3")
    empty = tmp / "cwd"
    empty.mkdir()
    found = {
        "checkout": _probe(
            tmp / "checkout.json", cwd=REPO_ROOT, pythonpath=REPO_ROOT / "src", checkout=True
        )
    }
    for name, deleted in (("intact", None), ("a", CORE), ("b", INDEX)):
        site = tmp / name / "venv" / "lib" / "python3.13" / "site-packages"
        shutil.copytree(
            REPO_ROOT / "src" / "openflowsheet",
            site / "openflowsheet",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        if deleted is not None:
            (site / "openflowsheet" / deleted).unlink()
        found[name] = _probe(tmp / f"{name}.json", cwd=empty, pythonpath=site, checkout=False)
        assert found[name]["module_file"] == str(site / "openflowsheet" / "__init__.py")
    return found


def test_the_index_count_is_the_committed_index_s() -> None:
    assert N == 149  # 9 + 5 + 1 + 123 + 4 + 4 + 3, measured at d29f1a50 (D-5, WF-4)


def test_the_checkout_probe(probes: dict[str, dict[str, Any]]) -> None:
    checkout = probes["checkout"]
    assert checkout["module_file"] == str(REPO_ROOT / "src" / "openflowsheet" / "__init__.py")
    assert checkout["entry_points"] == []
    assert checkout["capabilities"]["page"] == "CapabilityPage"
    assert wheel_data_check.HEX64.fullmatch(checkout["capabilities"]["registry_sha256"])
    items = checkout["records"]["items"]
    assert len(items) == len({item["record_sha256"] for item in items}) == N
    assert {item["store"] for item in items} == {"legacy"}


def _passing(probes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The checkout's probe document as an installed one: with the checkout's, it passes."""
    installed = copy.deepcopy(probes["checkout"])
    installed["module_file"] = probes["intact"]["module_file"]
    found = wheel_data_check.f1f3_findings(installed, probes["checkout"], N)
    assert found == dict.fromkeys(found, True)
    return installed


def test_an_intact_installed_copy_passes_wf2_and_wf3(probes: dict[str, dict[str, Any]]) -> None:
    found = wheel_data_check.f1f3_findings(probes["intact"], probes["checkout"], N)
    assert {key: found[key] for key in ("site_packages", "no_extensions", "registry_sha256")} == {
        "site_packages": True,
        "no_extensions": True,
        "registry_sha256": True,
    }


@pytest.mark.xfail(
    strict=True,
    reason="REL050-WF finding: an installed package lists only the packaged legacy files' "
    "records (9 of 149, ADR 0061 D8); WF-4 awaits the design lane",
)
def test_an_intact_installed_copy_passes_wf4(probes: dict[str, dict[str, Any]]) -> None:
    listed = probes["intact"]["records"]["items"]
    assert len(listed) == N, f"{len(listed)} legacy records installed, {N} in the index"


def test_control_a_core_json_deleted_from_the_installed_package(
    probes: dict[str, dict[str, Any]],
) -> None:
    installed = probes["a"]
    assert probes["intact"]["capabilities"] == probes["checkout"]["capabilities"]
    raised = installed["capabilities"].get("error")
    digest = installed["capabilities"].get("registry_sha256")
    assert raised is not None or digest != probes["checkout"]["capabilities"]["registry_sha256"]
    assert (
        wheel_data_check.f1f3_findings(installed, probes["checkout"], N)["registry_sha256"] is False
    )


def test_control_b_legacy_index_deleted_from_the_installed_package(
    probes: dict[str, dict[str, Any]],
) -> None:
    # The installed copy's lookup raises (not merely lists fewer records, which the finding does).
    assert probes["b"]["records"]["error"]["type"] == "FileNotFoundError"
    found = wheel_data_check.f1f3_findings(probes["b"], probes["checkout"], N)
    assert found["legacy_records"] is False


def test_control_c_another_digest(probes: dict[str, dict[str, Any]]) -> None:
    installed = _passing(probes)
    digest = installed["capabilities"]["registry_sha256"]
    installed["capabilities"]["registry_sha256"] = ("0" if digest[0] != "0" else "1") + digest[1:]
    found = wheel_data_check.f1f3_findings(installed, probes["checkout"], N)
    assert found["registry_sha256"] is False
    assert {key: value for key, value in found.items() if key != "registry_sha256"} == {
        "site_packages": True,
        "no_extensions": True,
        "legacy_records": True,
    }


def test_control_d_one_item_dropped(probes: dict[str, dict[str, Any]]) -> None:
    installed = _passing(probes)
    del installed["records"]["items"][0]
    found = wheel_data_check.f1f3_findings(installed, probes["checkout"], N)
    assert found["legacy_records"] is False
    # Dropped from both sides, the lists agree and only the count against the index fails.
    checkout = copy.deepcopy(probes["checkout"])
    dropped = installed["records"]["items"]
    checkout["records"]["items"] = [
        item for item in checkout["records"]["items"] if item in dropped
    ]
    assert wheel_data_check.f1f3_findings(installed, checkout, N)["legacy_records"] is False
    assert wheel_data_check.f1f3_findings(installed, checkout, N - 1)["legacy_records"] is True


@pytest.mark.parametrize(
    ("clause", "edit"),
    [
        ("site_packages", lambda d: d.update(module_file="/repo/src/openflowsheet/__init__.py")),
        ("no_extensions", lambda d: d.update(entry_points=["x = pkg.module:Plugin"])),
        ("registry_sha256", lambda d: d["capabilities"].update(page="dict")),
        ("registry_sha256", lambda d: d["capabilities"].update(registry_sha256="F" * 64)),
        ("registry_sha256", lambda d: d.update(capabilities={"error": {"type": "OSError"}})),
        ("legacy_records", lambda d: d["records"]["items"][0].update(store="project")),
        ("legacy_records", lambda d: d.update(records={"error": {"type": "OSError"}})),
    ],
)
def test_each_further_clause_fails_its_check(
    probes: dict[str, dict[str, Any]], clause: str, edit: Any
) -> None:
    installed = _passing(probes)
    edit(installed)
    assert wheel_data_check.f1f3_findings(installed, probes["checkout"], N)[clause] is False


def test_no_index_record_fails_wf4(probes: dict[str, dict[str, Any]]) -> None:
    empty = _passing(probes)
    empty["records"]["items"] = []
    assert wheel_data_check.f1f3_findings(empty, empty, 0)["legacy_records"] is False


def test_the_item_refuses_a_checkout_not_at_c() -> None:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--commit", "0" * 40, "--f1-f3"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 2
    assert "not at " + "0" * 40 in done.stderr
