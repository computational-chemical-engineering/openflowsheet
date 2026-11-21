"""Line 0.5's RC item `WHEEL-F1-F3` (`docs/briefs/REL050-line-0.5.md` D-5, WF-1 to WF-5).

`scripts/wheel_data_check.py --f1-f3` probes F1's registry and F3's legacy records through the
Python binding of an installed package and of the checkout. WF-4 is as the design-lane review
REL050-R restated it (Ruling 1): each side's legacy `(id, record_sha256)` list equals the index's
own `(id, sha256)` list over that side's files, every file for the checkout (N records) and the
package-data files for the installed package (N_pkg records, ADR 0061 D8). WF-5's six controls,
each of which must fail its check:

- (a) `openflowsheet/registry/builtin/core.json` deleted from an installed package: WF-3;
- (b) the installed `openflowsheet/records/legacy_index.json` deleted: WF-4;
- (c) a probe document whose digest is replaced by another 64-hex value: WF-3;
- (d) an installed probe document with one item dropped: WF-4;
- (e) the installed `openflowsheet/_data/benchmarks/m01/components.yaml` deleted: WF-4 (4 records
  listed against N_pkg = 9, so the expected list does not follow the installed package);
- (f) a checkout probe document with one item dropped: WF-4.

The installed package of (a), (b) and (e) is, as in `tests/test_x05_replay_from_the_wheel.py`,
the checkout's `src/openflowsheet` copied (links followed) into a scratch `site-packages`; the
probe runs there as the item runs it in the wheel's venv, by `wheel_data_check.py probe --f1-f3`.
The reference is the probe in the checkout (`--in-checkout`). The expected lists are derived from
the checkout's tree by the item's own `legacy_expectations` (the item reads `git archive` of C).
The documents of (c), (d) and (f) are edits of the intact pair, which passes every clause, so each
failure is the edit's. The copy carries files a wheel omits, so it models deletions only; that the
wheel passes is the item's own run at C (REL050-R Ruling 2).
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import wheel_data_check  # noqa: E402

SCRIPT = REPO_ROOT / "scripts" / "wheel_data_check.py"
LEGACY, PACKAGE_PATHS = wheel_data_check.legacy_expectations(REPO_ROOT)
INDEX_PAIRS = wheel_data_check.legacy_index_pairs(LEGACY)
PACKAGE_PAIRS = wheel_data_check.legacy_index_pairs(LEGACY, PACKAGE_PATHS)
N, N_PKG = len(INDEX_PAIRS), len(PACKAGE_PAIRS)
CORE = Path("registry/builtin/core.json")
INDEX = Path("records/legacy_index.json")
M01 = Path("_data/benchmarks/m01/components.yaml")


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
    """The checkout's probe, and the probe of an installed copy: intact, (a), (b) and (e)."""
    tmp = tmp_path_factory.mktemp("f1f3")
    empty = tmp / "cwd"
    empty.mkdir()
    found = {
        "checkout": _probe(
            tmp / "checkout.json", cwd=REPO_ROOT, pythonpath=REPO_ROOT / "src", checkout=True
        )
    }
    for name, deleted in (("intact", None), ("a", CORE), ("b", INDEX), ("e", M01)):
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


def test_the_index_and_its_package_data_at_c() -> None:
    assert N == 149  # 9 + 5 + 1 + 123 + 4 + 4 + 3, measured at d29f1a50 (D-5, WF-4)
    # REL050-R Ruling 1: only the m01 and s10 component files are package data (ADR 0061 D8).
    assert PACKAGE_PATHS == ["benchmarks/m01/components.yaml", "benchmarks/s10/records.yaml"]
    assert N_PKG == 9  # 5 + 4
    assert wheel_data_check.page_bound(N) == 2


def test_the_checkout_probe(probes: dict[str, dict[str, Any]]) -> None:
    checkout = probes["checkout"]
    assert checkout["module_file"] == str(REPO_ROOT / "src" / "openflowsheet" / "__init__.py")
    assert checkout["entry_points"] == []
    assert checkout["capabilities"]["page"] == "CapabilityPage"
    assert wheel_data_check.HEX64.fullmatch(checkout["capabilities"]["registry_sha256"])
    items = checkout["records"]["items"]
    assert len(items) == len({item["record_sha256"] for item in items}) == N
    assert {item["store"] for item in items} == {"legacy"}


def _findings(installed: dict[str, Any], checkout: dict[str, Any]) -> dict[str, bool]:
    return wheel_data_check.f1f3_findings(installed, checkout, INDEX_PAIRS, PACKAGE_PAIRS)


def _passing(probes: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Copies of the intact installed copy's probe and the checkout's: a pair that passes."""
    installed, checkout = copy.deepcopy(probes["intact"]), copy.deepcopy(probes["checkout"])
    found = _findings(installed, checkout)
    assert found == dict.fromkeys(found, True)
    return installed, checkout


def test_an_intact_installed_copy_passes_wf2_and_wf3(probes: dict[str, dict[str, Any]]) -> None:
    found = _findings(probes["intact"], probes["checkout"])
    assert {key: found[key] for key in ("site_packages", "no_extensions", "registry_sha256")} == {
        "site_packages": True,
        "no_extensions": True,
        "registry_sha256": True,
    }


def test_an_intact_installed_copy_passes_wf4(probes: dict[str, dict[str, Any]]) -> None:
    listed = probes["intact"]["records"]["items"]
    assert len(listed) == N_PKG, f"{len(listed)} legacy records installed, {N_PKG} packaged"
    assert _findings(probes["intact"], probes["checkout"])["legacy_records"] is True


def test_control_a_core_json_deleted_from_the_installed_package(
    probes: dict[str, dict[str, Any]],
) -> None:
    installed = probes["a"]
    assert probes["intact"]["capabilities"] == probes["checkout"]["capabilities"]
    raised = installed["capabilities"].get("error")
    digest = installed["capabilities"].get("registry_sha256")
    assert raised is not None or digest != probes["checkout"]["capabilities"]["registry_sha256"]
    assert _findings(installed, probes["checkout"])["registry_sha256"] is False


def test_control_b_legacy_index_deleted_from_the_installed_package(
    probes: dict[str, dict[str, Any]],
) -> None:
    # The installed copy's lookup raises (not merely lists fewer records).
    assert probes["b"]["records"]["error"]["type"] == "FileNotFoundError"
    assert _findings(probes["b"], probes["checkout"])["legacy_records"] is False


def test_control_c_another_digest(probes: dict[str, dict[str, Any]]) -> None:
    installed, checkout = _passing(probes)
    digest = installed["capabilities"]["registry_sha256"]
    installed["capabilities"]["registry_sha256"] = ("0" if digest[0] != "0" else "1") + digest[1:]
    found = _findings(installed, checkout)
    assert found["registry_sha256"] is False
    assert {key: value for key, value in found.items() if key != "registry_sha256"} == {
        "site_packages": True,
        "no_extensions": True,
        "legacy_records": True,
    }


def _dropped(
    probes: dict[str, dict[str, Any]], side: str
) -> tuple[dict[str, Any], dict[str, Any], tuple[str, str]]:
    """The passing pair with `side`'s first item dropped; the dropped pair."""
    pair = dict(zip(("installed", "checkout"), _passing(probes), strict=True))
    item = pair[side]["records"]["items"].pop(0)
    return pair["installed"], pair["checkout"], (item["id"], item["record_sha256"])


def test_control_d_one_installed_item_dropped(probes: dict[str, dict[str, Any]]) -> None:
    installed, checkout, dropped = _dropped(probes, "installed")
    found = _findings(installed, checkout)
    assert found["legacy_records"] is False
    assert {key for key, value in found.items() if value} == {
        "site_packages",
        "no_extensions",
        "registry_sha256",
    }
    # The installed side is compared with its own index list: without that pair there, it passes.
    package = list(PACKAGE_PAIRS)
    package.remove(dropped)
    assert wheel_data_check.f1f3_findings(installed, checkout, INDEX_PAIRS, package)[
        "legacy_records"
    ]


def test_control_e_m01_deleted_from_the_installed_package(
    probes: dict[str, dict[str, Any]],
) -> None:
    listed = probes["e"]["records"]["items"]
    assert len(listed) == 4  # s10's four; m01's five are no longer available
    assert {item["store"] for item in listed} == {"legacy"}
    assert _findings(probes["e"], probes["checkout"])["legacy_records"] is False


def test_control_f_one_checkout_item_dropped(probes: dict[str, dict[str, Any]]) -> None:
    installed, checkout, dropped = _dropped(probes, "checkout")
    assert _findings(installed, checkout)["legacy_records"] is False
    index = list(INDEX_PAIRS)
    index.remove(dropped)
    assert wheel_data_check.f1f3_findings(installed, checkout, index, PACKAGE_PAIRS)[
        "legacy_records"
    ]


def test_a_record_both_sides_answer_wrongly_alike_fails_wf4(
    probes: dict[str, dict[str, Any]],
) -> None:
    # REL050-R amendment (i): each side is compared with the index, not only with the other.
    installed, checkout = _passing(probes)
    wrong = []
    for document in (installed, checkout):
        item = next(
            item
            for item in document["records"]["items"]
            if (item["id"], item["record_sha256"]) == PACKAGE_PAIRS[0]
        )
        digest = item["record_sha256"]
        item["record_sha256"] = ("0" if digest[0] != "0" else "1") + digest[1:]
        wrong.append((item["id"], item["record_sha256"]))
    assert wrong[0] == wrong[1]
    assert _findings(installed, checkout)["legacy_records"] is False


@pytest.mark.parametrize("side", ["installed", "checkout"])
def test_more_pages_than_the_bound_fail_wf4(probes: dict[str, dict[str, Any]], side: str) -> None:
    pair = dict(zip(("installed", "checkout"), _passing(probes), strict=True))
    pair[side]["records"]["pages"] = wheel_data_check.page_bound(N) + 1
    assert _findings(pair["installed"], pair["checkout"])["legacy_records"] is False


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
        ("legacy_records", lambda d: d["records"].pop("pages")),
    ],
)
def test_each_further_clause_fails_its_check(
    probes: dict[str, dict[str, Any]], clause: str, edit: Any
) -> None:
    installed, checkout = _passing(probes)
    edit(installed)
    assert _findings(installed, checkout)[clause] is False


def test_no_index_record_fails_wf4(probes: dict[str, dict[str, Any]]) -> None:
    installed, checkout = _passing(probes)
    for document in (installed, checkout):
        document["records"]["items"] = []
    assert wheel_data_check.f1f3_findings(installed, checkout, [], [])["legacy_records"] is False
    # No package-data record: N_pkg >= 1 fails, although the installed side lists none either.
    installed["records"]["items"] = []
    _, checkout = _passing(probes)
    assert (
        wheel_data_check.f1f3_findings(installed, checkout, INDEX_PAIRS, [])["legacy_records"]
        is False
    )


class _Endless:
    """A `LocalApplication` whose record cursor never ends (REL050-R F-3)."""

    def __enter__(self) -> _Endless:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def list_capabilities(self) -> Any:
        raise OSError("not needed here")

    def search_records(self, limit: int, cursor: str | None) -> Any:
        item = {"id": "X", "record_sha256": "0" * 64, "store": "legacy"}
        return SimpleNamespace(items=[item], next_cursor=f"{cursor or ''}+")


def test_a_cursor_that_never_ends_fails_wf4(monkeypatch: pytest.MonkeyPatch) -> None:
    from openflowsheet.application.local import LocalApplication

    monkeypatch.setattr(LocalApplication, "in_memory", classmethod(lambda cls: _Endless()))
    started = time.monotonic()
    found = wheel_data_check.probe_f1f3(checkout=False)
    assert time.monotonic() - started < 10
    records = found["records"]
    assert records["error"] == {"type": "Pagination", "message": "pagination did not end"}
    assert records["pages"] == wheel_data_check.PROBE_MAX_PAGES
    assert _findings(found, found)["legacy_records"] is False


def test_the_item_refuses_a_checkout_not_at_c() -> None:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--commit", "0" * 40, "--f1-f3"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 2
    assert "not at " + "0" * 40 in done.stderr
