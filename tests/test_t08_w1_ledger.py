"""T08.A02: the gate ledger, `docs/requirements.yaml`, carries the release evidence (T08 W1.1).

T08 release spec §9, T08.A02: V11–V20's `evidence` lists at least the §3.1 manifests of each gate's
"gates it serves", and `evidence/T08/<C>/manifest.json` for V18–V20; a `verdict` is set only to the
value in `docs/reviews/T08-verdicts.md`. The §3.1 table is read from the specification itself, so a
gate the table names cannot be dropped from the ledger by editing one of the two.

W1.1 also backfills G00–G06 (spec Q8, FD2), which were `null` although v0.0.0 was tagged "all seven
gates met": each verdict is what `scripts/v0_0_gate.py` reports — `met` and `met_with_limitations`
are PASS (spec §3.3: a gate met with limitations is PASS, and the limitations travel) — and each
evidence list is the gate's owner manifests, the ones that script reads.

The T08 manifest does not exist until W5.3; its clause is checked from the moment one is committed.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "derivations" / "T08-release-spec.md"
VERDICTS = ROOT / "docs" / "reviews" / "T08-verdicts.md"
V_GATES = tuple(f"V{n}" for n in range(11, 21))
_ROW = re.compile(
    r"^\| (?P<package>[PKT]\d{2}b?) \| `(?P<prefix>[0-9a-f]{7})…` \|.*\| (?P<serves>[^|]*) \|$"
)


def _ledger() -> dict[str, Any]:
    loaded = yaml.safe_load((ROOT / "docs" / "requirements.yaml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _gates() -> dict[str, dict[str, Any]]:
    return {gate["id"]: gate for gate in _ledger()["gates"]}


def _served() -> dict[str, set[str]]:
    """Spec §3.1: gate -> the manifests (by path) whose row names it under "gates it serves"."""
    text = SPEC.read_text(encoding="utf-8")
    section = text[text.index("### 3.1") : text.index("### 3.2")]
    served: dict[str, set[str]] = {gate: set() for gate in V_GATES}
    rows = 0
    for line in section.splitlines():
        match = _ROW.match(line)
        if match is None:
            continue
        rows += 1
        package = ROOT / "evidence" / match["package"]
        found = sorted(package.glob(f"{match['prefix']}*/manifest.json"))
        assert len(found) == 1, (match["package"], match["prefix"], found)
        path = found[0].relative_to(ROOT).as_posix()
        for gate in re.findall(r"V\d{2}", match["serves"]):
            served[gate].add(path)
    assert rows == 14, f"§3.1 names fourteen manifests (T08.A01); parsed {rows}"
    return served


def _v0_0_gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("v0_0_gate", ROOT / "scripts" / "v0_0_gate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("gate", V_GATES)
def test_a02_v_gate_evidence_lists_the_manifests_of_section_3_1(gate: str) -> None:
    listed = set(_gates()[gate]["evidence"])
    missing = _served()[gate] - listed
    assert not missing, f"{gate} lacks §3.1's {sorted(missing)}"


@pytest.mark.parametrize("gate", ("V18", "V19", "V20"))
def test_a02_the_t08_manifest_is_listed_once_it_exists(gate: str) -> None:
    manifests = sorted((ROOT / "evidence" / "T08").glob("*/manifest.json"))
    if gate == "V19" or not manifests:
        # V19 is not in A02's T08 clause; the T08 manifest is W5.3's.
        pytest.skip("no evidence/T08 manifest yet (W5.3)" if not manifests else "not in A02")
    listed = set(_gates()[gate]["evidence"])
    assert {path.relative_to(ROOT).as_posix() for path in manifests} & listed


def _recorded_verdicts() -> dict[str, str]:
    """`docs/reviews/T08-verdicts.md`: gate -> the first PASS/FAIL/BLOCKED on its table row."""
    if not VERDICTS.is_file():
        return {}
    found: dict[str, str] = {}
    for line in VERDICTS.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*\**(V\d{2})\**\s*\|(.*)$", line)
        if match is None:
            continue
        verdict = re.search(r"\b(PASS|FAIL|BLOCKED)\b", match[2])
        if verdict is not None:
            found.setdefault(match[1], verdict[1])
    return found


def test_a02_v_gate_verdicts_are_only_the_recorded_ones() -> None:
    recorded = _recorded_verdicts()
    got = {gate: _gates()[gate]["verdict"] for gate in V_GATES}
    assert got == {gate: recorded.get(gate) for gate in V_GATES}


def test_q8_g_gate_verdicts_and_evidence_are_the_v0_0_gate_report() -> None:
    gate_script = _v0_0_gate()
    evidence = gate_script.manifests()
    report = gate_script.build()["gates"]
    gates = _gates()
    for gate, _, owners in gate_script.GATES:
        expected = "PASS" if report[gate]["status"] in ("met", "met_with_limitations") else "FAIL"
        assert gates[gate]["verdict"] == expected, gate
        assert gates[gate]["evidence"] == [evidence[owner]["_path"] for owner in owners], gate
