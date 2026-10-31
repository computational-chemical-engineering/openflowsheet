"""V03 spec §6.1 (Amendment 4, R-913): the controls (c1)–(c10) of S13's generator
(`scripts/s13_evidence_manifest.py`) on WO-8's acyclic route.

S13's manifest never judges step 18 (A08's check is its tests, A27's is `_self`, `--step18-log` is
refused); A25 (a) admits only ADRs 0053 and 0054 open, each Proposed; ADR.0053 and ADR.0054 judge
their conditions other than the manifest's own status and pass Proposed or Accepted; a guard fails
one marked Accepted while another check does not pass; A26 carries the gate's `policy` over ADR
0053. Each control calls the generator's functions with `docs/adr/` and the check list substituted;
none runs the full generator.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from typing import Any

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import s13_evidence_manifest as s13  # noqa: E402
import v0_2_gate  # noqa: E402

C = "a3e508e35fc5451fe56fa7b70941621992d35b50"
#: The tree of the WO-8 stop, with ADRs 0053 and 0054 Proposed (spec §6.1 (c1)).
AT_STOP = "2fa00ff6"
ADR_0053 = s13.GATE_SET.policy_adr
ACCEPTED = "**Status:** **Accepted, 2026-10-31** — its condition holds (control)."


@pytest.fixture(scope="module")
def at_stop() -> dict[str, str]:
    """`docs/adr/*.md` at `2fa00ff6`, as `_working_files("docs/adr")` reads them."""

    def git(*args: str) -> str:
        done = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
        return done.stdout

    names = git("ls-tree", "--name-only", f"{AT_STOP}:docs/adr").split()
    return {
        f"docs/adr/{name}": git("show", f"{AT_STOP}:docs/adr/{name}")
        for name in sorted(names)
        if name.endswith(".md")
    }


@pytest.fixture
def adrs(monkeypatch: pytest.MonkeyPatch, at_stop: dict[str, str]) -> Callable[..., dict[str, str]]:
    """Substitute `docs/adr/`: the tree at `2fa00ff6` with the given status lines and edits."""

    def substitute(
        statuses: dict[str, str] | None = None, edits: dict[str, Callable[[str], str]] | None = None
    ) -> dict[str, str]:
        files = dict(at_stop)
        for number, line in (statuses or {}).items():
            (path,) = [p for p in files if p.startswith(f"docs/adr/{number}-")]
            old = v0_2_gate.status_line(files[path])
            assert old is not None
            files[path] = files[path].replace(old, line, 1)
        for path, edit in (edits or {}).items():
            changed = edit(files[path])
            assert changed != files[path], f"the edit of {path} changed nothing"
            files[path] = changed

        def working_files(prefix: str) -> dict[str, str]:
            assert prefix == "docs/adr"
            return files

        monkeypatch.setattr(s13, "_working_files", working_files)
        return files

    return substitute


def inputs(commands: int = 1) -> s13.Inputs:
    return s13.Inputs(C, commands=commands)


def check(entry_id: str) -> dict[str, Any]:
    """One of the ADR checks, or a §7 check, decided over the substituted `docs/adr/`."""
    if entry_id.startswith("ADR."):
        (entry,) = [e for e in s13.adr_checks(inputs(), "pass") if e["id"] == entry_id]
        return entry
    (spec,) = [spec for spec in s13.SPECS if f"V03.{spec.id}" == entry_id]
    return s13.decide(spec, entry_id, entry_id, inputs())


def a25() -> tuple[str, dict[str, Any]]:
    return s13._m_adrs(inputs())


def pending_answer(text: str) -> str:
    """Frank's answer to M03 N1 (a decisions-table cell) set to `pending`."""
    return re.sub(r"^(\| M03 N1 \|[^|]*\|)[^\n]*$", r"\1 pending |", text, count=1, flags=re.M)


def d3_dated(day: str) -> Callable[[str], str]:
    def edit(text: str) -> str:
        return text.replace("| V14 (b) | accepted, 2026-10-30", f"| V14 (b) | accepted, {day}", 1)

    return edit


# ----------------------------------------------------------------------------- A25 (a): (c1)–(c4)


def test_c1_a25_passes_at_the_stop_with_0053_and_0054_proposed(adrs: Callable[..., Any]) -> None:
    adrs()
    result, value = a25()
    assert result == "pass"
    assert len(value["at_wo8"]) == 2 and value["at_wo8"] == value["problems"]
    assert [p.split(" is not")[0] for p in value["at_wo8"]] == ["ADR 0053", "ADR 0054"]


def test_c2_a25_fails_with_another_required_adr_proposed(adrs: Callable[..., Any]) -> None:
    adrs({"0046": "**Status:** **Proposed, 2026-10-29**"})
    result, value = a25()
    assert result == "fail"
    assert any(p.startswith("ADR 0046 is not Accepted") for p in value["problems"])


def test_c3_a25_fails_with_0053_rejected(adrs: Callable[..., Any]) -> None:
    adrs({"0053": "**Status:** **Rejected, 2026-10-31**"})
    result, value = a25()
    assert result == "fail"
    assert not any(p.startswith("ADR 0053") for p in value["at_wo8"])


def test_c4_a25_passes_with_0053_and_0054_accepted(adrs: Callable[..., Any]) -> None:
    adrs({"0053": ACCEPTED, "0054": ACCEPTED})
    result, value = a25()
    assert result == "pass"
    assert value["problems"] == [] and value["at_wo8"] == []


# ----------------------------------------------------------------------------- ADR.0053/0054


def test_c5_adr_0053_proposed_passes_on_frank_s_six_cells(adrs: Callable[..., Any]) -> None:
    adrs()
    entry = check("ADR.0053")
    assert entry["result"] == "pass", entry["value"]
    assert entry["value"]["status"] == "Proposed"
    assert entry["value"]["listed"] == {"range": "V03.A01–A31", "missing": []}
    assert len(entry["value"]["policy"]["d3"]) == 2
    assert len(entry["value"]["policy"]["frank_items"]) == 4


def test_c5_adr_0053_fails_with_a_decisions_cell_pending(adrs: Callable[..., Any]) -> None:
    adrs(edits={ADR_0053: pending_answer})
    entry = check("ADR.0053")
    assert entry["result"] == "fail"
    assert any("M03 N1" in refusal for refusal in entry["value"]["policy"]["frank"])


def test_c5_adr_0053_fails_with_a_d3_cell_before_judged(adrs: Callable[..., Any]) -> None:
    adrs(edits={ADR_0053: d3_dated("2026-10-29")})
    entry = check("ADR.0053")
    assert entry["result"] == "fail"
    assert entry["value"]["policy"]["d3_not_accepted_on_time"] == [
        "V14 (b): " + entry["value"]["policy"]["d3"]["V14 (b)"]
    ]


def test_c6_adr_0054_proposed_passes_and_withdrawn_fails(adrs: Callable[..., Any]) -> None:
    adrs()
    entry = check("ADR.0054")
    assert entry["result"] == "pass", entry["value"]
    assert entry["value"]["status"] == "Proposed"
    assert entry["value"]["listed"] == {"range": "V03.A28–A31", "missing": []}
    adrs({"0054": "**Status:** **Withdrawn, 2026-10-31**"})
    entry = check("ADR.0054")
    assert entry["result"] == "fail"
    assert entry["value"]["status"] is None


# ----------------------------------------------------------------------------- the guard, _self


@pytest.mark.parametrize("number", ["0053", "0054"])
def test_c7_the_guard_fails_an_adr_accepted_early(adrs: Callable[..., Any], number: str) -> None:
    adrs({number: ACCEPTED})

    def decided(a24: str) -> list[dict[str, Any]]:
        (adr,) = [e for e in s13.adr_checks(inputs(), a24) if e["id"] == f"ADR.{number}"]
        assert adr["result"] == "pass" and adr["value"]["status"] == "Accepted"
        return [
            {"id": "V03.A01", "result": "pass", "value": {}},
            {"id": "V03.A24", "result": a24, "value": {}},
            {"id": "V03.A27", "result": "unsupported", "value": {}},
            adr,
        ]

    entries = decided("fail")
    s13.guard(entries, inputs())
    assert entries[-1]["result"] == "fail"
    assert entries[-1]["value"]["accepted_early"] is True

    entries = decided("pass")
    s13.guard(entries, inputs())
    assert entries[-1]["result"] == "pass"
    assert "accepted_early" not in entries[-1]["value"]


def test_c8_self_is_every_other_check_and_commands_run() -> None:
    others = [{"id": f"V03.A{n:02d}", "result": "pass", "value": {}} for n in (1, 2, 26)]

    def own(rows: list[dict[str, Any]], commands: int) -> dict[str, Any]:
        entry: dict[str, Any] = {"id": "V03.A27", "result": "unsupported", "value": {}}
        s13._self(entry, rows, inputs(commands))
        return entry

    entry = own(others, 1)
    assert entry["result"] == "pass"
    assert "step18" not in entry["value"]
    assert entry["value"]["self"] == {"other_checks": 3, "not_pass": [], "commands": 1}
    unsupported = [*others[:2], {"id": "V03.A26", "result": "unsupported", "value": {}}]
    assert own(unsupported, 1)["result"] == "fail"
    assert own(others, 0)["result"] == "fail"


def test_c9_step18_log_is_refused_and_not_a_measure() -> None:
    with pytest.raises(SystemExit) as refused:
        s13.main(["--step18-log", "x", "--commit", C])
    assert refused.value.code == 2
    assert "step18" not in s13.MEASURES
    specs = {spec.id: spec for spec in s13.SPECS}
    assert specs["A08"] == s13.Spec("A08", tests=True)
    assert specs["A27"] == s13.Spec("A27", measures=("self",))
    assert specs["A26"].measures == ("verdict_document", "policy")


def test_c10_a26_fails_with_an_adr_0053_cell_pending(adrs: Callable[..., Any]) -> None:
    adrs()
    assert check("V03.A26")["result"] == "pass"
    adrs(edits={ADR_0053: pending_answer})
    entry = check("V03.A26")
    assert entry["result"] == "fail"
    assert entry["value"]["verdict_document"]["rows"] == 17
    assert entry["value"]["policy"]["frank"]
