"""V03 RC job (`docs/derivations/V03-release-spec.md` §4): the `t08-rc-v1` records of step 15 and of
step 17's items 17a–17e at `C`, and the A19 probe that step 17e runs in a fresh venv.

The local steps run as labelled commands of a runner script whose one-line-per-command summary
(`<label> exit <code> :: <command>`) and per-label logs (`<logs>/<label>.log`) this script reads,
as 0.2.0's `m07_rc_external.py` did (`evidence/M07/ce99365…/tools/`). Each record is written
through `t08_rc.finish`, so it carries `commit`, `tree_clean`, the lock's SHA-256 and the machine
class of the checkout this script lives in; the script refuses to run from a checkout that is not
at `--commit`. Records go to `<rc>/step15/rc-step15.json` and `<rc>/step17/rc-step17{a..e}.json`.

- **step15** (V03.A21; §3.4 and WO-5's carry): `v0_3_gate.py --rc C --carry-journey J` printed
  `RC step 15: … carried`; `m07_journey.py check` and `replay` (the `nlp` environment) exit 0.
- **step17a** (E01 G10, A48): `e01_evidence_manifest.a48_release_check()`, called here, returns
  `pass` with `unverified_primary_ranges == 0`.
- **step17b** (S07 F-8; the local cross-check of CI's `rc-coolprop`): the S07 and S11 CoolProp
  modules, with `requirements-coolprop.lock` installed after the main lock and
  `OPENFLOWSHEET_REQUIRE_COOLPROP=1`, exit 0 with 0 skipped.
- **step17c** (MR-12 v03, §9.3; review F-V3): one check per `MR12_AUDITS_V03` entry, its id the
  entry's `check` command and its result that command's exit status; then
  `m07a_evidence_manifest.mr12_extras_v03_at(C, record)` over the record being written must be
  `pass` with `new_since_v0_2_0 == ["coolprop", "lca"]`. The S13 manifest calls the measure again
  over the committed record; a missing record fails it.
- **step17d** (E01's opt-in tiers): A24 and A25 in the `lca` environment, A33–A36 in the audited
  `nlp` environment: every node citing the assertion (E01's own `cited`) passed, at least one.
- **step17e** (T08.A43, V03.A17, A19): `t08_dist.py` built and checked the wheel; the wheel holds
  each §9.1 ship-set file once with the repository's SHA-256, E01's seven data files with
  `docs/e01-data-licences.json`'s, and no §9.1 repository-only file; the probe, run in a fresh venv
  installed from that wheel, gives A19 (a)–(d), and its (c) answers equal the checkout's (bitwise:
  every float as `float.hex`).

    python scripts/v03_rc.py step15 --rc RC --commit C --summary S --logs L --journey J
    python scripts/v03_rc.py step17a --rc RC --commit C
    python scripts/v03_rc.py step17b --rc RC --commit C --summary S --modules FILE
    python scripts/v03_rc.py step17c --rc RC --commit C --summary S --logs L
    python scripts/v03_rc.py step17d --rc RC --commit C --summary S --logs L
    python scripts/v03_rc.py step17e --rc RC --commit C --summary S --dist D \
        --installed J1 --checkout J2
    <venv>/bin/python -I scripts/v03_rc.py probe --out J1            # in the fresh venv (A19)
    python scripts/v03_rc.py probe --in-checkout --out J2            # the checkout's, A19 (c)

The probe imports only the standard library and the installed `openflowsheet`.
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import hashlib
import json
import re
import sys
import zipfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
REGISTRATION = Path("benchmarks/v03/registration.json")
E01_DATA = Path("docs/e01-data-licences.json")
#: §9.3: the extras new since v0.2.0 that MR-12 v03 must find, each with its entry.
NEW_SINCE_V0_2_0 = ["coolprop", "lca"]
#: The summary labels of step 17c's two checks, by extra.
STEP17C_LABELS = {"coolprop": "step17c-coolprop", "lca": "step17c-lca"}
#: Step 17d: the assertions each environment's run must show passed.
LCA_ASSERTIONS = ("A24", "A25")
NLP_ASSERTIONS = ("A33", "A34", "A35", "A36")
#: A19 (c)'s states: S10's real-records reference states RE1–RE3
#: (`benchmarks/s10/reference_values_real.yaml` `closed_form.evaluate_phase`, n in the records'
#: order CH3OH, C2H5OH, H2O) and V03.A12's state (`tests/test_v03_wilson_ship.py`). The probe runs
#: where `benchmarks/` is not installed, so they are written here; a test pins them to the file.
A19_STATES: dict[str, tuple[tuple[float, float, float], float, float]] = {
    "RE1": ((0.6, 0.4, 1.0), 350.0, 101325.0),
    "RE2": ((1.0, 0.0, 1.0), 345.0, 101325.0),
    "RE3": ((0.0, 0.0, 1.0), 360.0, 80000.0),
    "A12": ((0.3, 0.3, 0.4), 350.0, 101325.0),
}
SUMMARY_LINE = re.compile(r"^(\S+) exit (\d+) :: ")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# -- the runner's outputs ------------------------------------------------------------------------


def exit_codes(summary: Path) -> dict[str, int]:
    """The last exit code of each label in the runner's summary."""
    codes: dict[str, int] = {}
    for line in summary.read_text(encoding="utf-8").splitlines():
        match = SUMMARY_LINE.match(line)
        if match:
            codes[match[1]] = int(match[2])
    return codes


def log_text(logs: Path, label: str) -> str:
    path = logs / f"{label}.log"
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def last_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


def junit_outcomes(path: Path) -> dict[str, str]:
    """Each node of a pytest junit file (`tests/x.py::name[param]`) and its outcome: `failed`
    (a failure or error element), `skipped`, or `passed`."""
    outcomes: dict[str, str] = {}
    for case in ElementTree.parse(path).getroot().iter("testcase"):
        node = f"{case.get('classname', '').replace('.', '/')}.py::{case.get('name', '')}"
        if case.find("failure") is not None or case.find("error") is not None:
            outcomes[node] = "failed"
        elif case.find("skipped") is not None:
            outcomes[node] = "skipped"
        else:
            outcomes[node] = "passed"
    return outcomes


def totals(outcomes: Mapping[str, str]) -> dict[str, int]:
    counted = {"passed": 0, "failed": 0, "skipped": 0}
    for outcome in outcomes.values():
        counted[outcome] += 1
    return counted


def cited_nodes(
    outcomes: Mapping[str, str], assertion: str, cited: Callable[[str], Sequence[str]]
) -> dict[str, str]:
    return {node: outcome for node, outcome in outcomes.items() if assertion in cited(node)}


# -- the records ---------------------------------------------------------------------------------


def _modules(rc_checkout: Path) -> tuple[ModuleType, ModuleType]:
    """`t08_rc` and `m07a_evidence_manifest` of the checkout this script lives in."""
    sys.path.insert(0, str(rc_checkout / "scripts"))
    import m07a_evidence_manifest  # noqa: PLC0415
    import t08_rc  # noqa: PLC0415

    return t08_rc, m07a_evidence_manifest


def _finish(t08_rc: ModuleType, out: Path, step: str, checks: list[dict[str, Any]]) -> int:
    provenance = {**t08_rc.provenance(), "machine_class": t08_rc.machine_class()}
    return int(t08_rc.finish(out, step, checks, provenance=provenance))


def step15(
    t08_rc: ModuleType, out: Path, codes: Mapping[str, int], logs: Path, c: str, journey: str
) -> int:
    """V03.A21: the journey recorded at `journey` carried to C; `check` and `replay` at C."""
    checks: list[dict[str, Any]] = []
    line = last_line(log_text(logs, "step15-carry"))
    t08_rc.check(
        checks,
        "a21.carry_journey",
        codes.get("step15-carry") == 0
        and line.startswith("RC step 15: ")
        and line.endswith(" carried"),
        exit_code=codes.get("step15-carry"),
        line=line,
        command=f"python scripts/v0_3_gate.py --rc {c} --carry-journey {journey}",
    )
    for name, label, command in (
        ("check", "step15-check", f"python scripts/m07_journey.py check {journey}"),
        (
            "replay",
            "step15-replay",
            f"nlp env, OMP_NUM_THREADS=1: python scripts/m07_journey.py replay {journey}",
        ),
    ):
        t08_rc.check(
            checks,
            f"a21.{name}",
            codes.get(label) == 0,
            exit_code=codes.get(label),
            last_line=last_line(log_text(logs, label)),
            command=command,
        )
    return _finish(t08_rc, out / "step15" / "rc-step15.json", "w25-journey", checks)


def a48_check(result: str, value: Mapping[str, Any]) -> bool:
    return result == "pass" and value.get("unverified_primary_ranges") == 0


def step17a(t08_rc: ModuleType, out: Path) -> int:
    """17a: E01 G10, `a48_release_check()` → `("pass", {"unverified_primary_ranges": 0, …})`."""
    import e01_evidence_manifest  # noqa: PLC0415

    result, value = e01_evidence_manifest.a48_release_check()
    checks: list[dict[str, Any]] = []
    t08_rc.check(
        checks,
        "a22.17a.a48_release_check",
        a48_check(result, value),
        returned=[result, value],
        command="e01_evidence_manifest.a48_release_check()",
    )
    return _finish(t08_rc, out / "step17" / "rc-step17a.json", "17a", checks)


def step17b(t08_rc: ModuleType, out: Path, codes: Mapping[str, int], modules: Path) -> int:
    """17b, the local cross-check of CI's `rc-coolprop`: exit 0, nodes ran, 0 skipped."""
    junit = out / "step17" / "17b.junit.xml"
    outcomes = junit_outcomes(junit) if junit.exists() else {}
    counted = totals(outcomes)
    checks: list[dict[str, Any]] = []
    t08_rc.check(
        checks,
        "a22.17b.coolprop_modules",
        codes.get("step17b-tests") == 0
        and counted["passed"] > 0
        and counted["failed"] == counted["skipped"] == 0,
        exit_code=codes.get("step17b-tests"),
        junit=counted,
        junit_sha256=sha256(junit.read_bytes()) if junit.exists() else None,
        modules=modules.read_text(encoding="utf-8").split(),
        command="rc venv + requirements-coolprop.lock (--no-deps --require-hashes), "
        "OPENFLOWSHEET_REQUIRE_COOLPROP=1, OFS_S07_BUILD_PYTHON: pytest -rs <modules>",
    )
    return _finish(t08_rc, out / "step17" / "rc-step17b.json", "17b", checks)


def mr12_v03_check(result: str, value: Mapping[str, Any]) -> bool:
    """17c's verdict on the measure: `pass`, the two extras, each entry's check `pass`."""
    extras = value.get("extras", {})
    return (
        result == "pass"
        and value.get("new_since_v0_2_0") == NEW_SINCE_V0_2_0
        and all(extras.get(extra, {}).get("check_result") == "pass" for extra in NEW_SINCE_V0_2_0)
    )


def step17c(
    t08_rc: ModuleType, m07a: ModuleType, out: Path, codes: Mapping[str, int], logs: Path, c: str
) -> int:
    """17c (MR-12 v03; F-V3): each audit's check by its command, then the measure on the record."""
    checks: list[dict[str, Any]] = []
    for extra, audit in m07a.MR12_AUDITS_V03.items():
        label = STEP17C_LABELS.get(extra, f"step17c-{extra}")
        t08_rc.check(
            checks,
            audit["check"],
            codes.get(label) == 0,
            exit_code=codes.get(label),
            last_line=last_line(log_text(logs, label)),
            extra=extra,
        )
    provenance = {**t08_rc.provenance(), "machine_class": t08_rc.machine_class()}
    result, value = m07a.mr12_extras_v03_at(c, {"checks": checks, "provenance": provenance})
    t08_rc.check(
        checks,
        "a22.17c.mr12_extras_v03",
        mr12_v03_check(result, value),
        measure_result=result,
        measure=value,
        expected_new_since_v0_2_0=NEW_SINCE_V0_2_0,
    )
    out_file = out / Path(m07a.STEP17C_RECORD)
    return int(t08_rc.finish(out_file, "17c", checks, provenance=provenance))


def assertion_checks(
    t08_rc: ModuleType,
    checks: list[dict[str, Any]],
    outcomes: Mapping[str, str],
    assertions: Sequence[str],
    cited: Callable[[str], Sequence[str]],
    environment: str,
) -> None:
    for assertion in assertions:
        nodes = cited_nodes(outcomes, assertion, cited)
        t08_rc.check(
            checks,
            f"a22.17d.{assertion.lower()}",
            bool(nodes) and all(outcome == "passed" for outcome in nodes.values()),
            environment=environment,
            nodes=nodes,
        )


def step17d(t08_rc: ModuleType, out: Path, codes: Mapping[str, int], logs: Path) -> int:
    """17d: A24, A25 in the `lca` environment; A33–A36 in the audited `nlp` environment."""
    import e01_evidence_manifest  # noqa: PLC0415

    checks: list[dict[str, Any]] = []
    runs = (
        ("lca", "step17d-lca-tests", out / "step17" / "17d-lca.junit.xml", LCA_ASSERTIONS),
        ("nlp", "step17d-nlp-check", out / "step17" / "17d-nlp.junit.xml", NLP_ASSERTIONS),
    )
    for environment, label, junit, assertions in runs:
        outcomes = junit_outcomes(junit) if junit.exists() else {}
        counted = totals(outcomes)
        text = log_text(logs, label)
        ran = codes.get(label) == 0 and counted["passed"] > 0 and counted["failed"] == 0
        if environment == "nlp":
            ran = ran and all(
                line in text
                for line in (
                    "--- pytest -m nlp: exit 0",
                    "--- inventory --check: exit 0",
                    "--- inventory --check (trsp-exe): exit 0",
                )
            )
        t08_rc.check(
            checks,
            f"a22.17d.{environment}_run",
            ran,
            exit_code=codes.get(label),
            junit=counted,
            junit_sha256=sha256(junit.read_bytes()) if junit.exists() else None,
        )
        assertion_checks(
            t08_rc, checks, outcomes, assertions, e01_evidence_manifest.cited, environment
        )
    return _finish(t08_rc, out / "step17" / "rc-step17d.json", "17d", checks)


def wheel_findings(
    members: Mapping[str, bytes],
    ships: Mapping[str, str],
    e01_files: Mapping[str, str],
    repository_only: Sequence[str],
) -> dict[str, Any]:
    """V03.A17 over a wheel's `members` (name → bytes): `ships` maps each ship-set repository path
    to its SHA-256 (packaged at `openflowsheet/_data/<path>`), `e01_files` each E01 wheel path to
    its recorded SHA-256; no member may end in a repository-only path."""

    def found(name: str, digest: str) -> dict[str, Any]:
        present = [member for member in members if member == name]
        return {
            "member": name,
            "count": len(present),
            "sha256": sha256(members[name]) if present else None,
            "expected": digest,
            "ok": len(present) == 1 and sha256(members[name]) == digest,
        }

    ship_rows = {path: found(f"openflowsheet/_data/{path}", sha) for path, sha in ships.items()}
    e01_rows = {path: found(path, digest) for path, digest in e01_files.items()}
    present = sorted(
        member for member in members for path in repository_only if member.endswith(path)
    )
    return {"ship_set": ship_rows, "e01_data": e01_rows, "repository_only_present": present}


def wheel_members(dist: Path) -> tuple[Path | None, dict[str, bytes]]:
    wheels = sorted((dist / "dist").glob("*.whl"))
    if len(wheels) != 1:
        return None, {}
    with zipfile.ZipFile(wheels[0]) as archive:
        return wheels[0], {name: archive.read(name) for name in archive.namelist()}


def a19_findings(
    installed: Mapping[str, Any], checkout: Mapping[str, Any], records_sha256: str
) -> dict[str, bool]:
    """V03.A19 (a)–(d) from the two probes' outputs and the repository's records SHA-256."""
    a = installed.get("a", {})
    b = installed.get("b", {})
    d = installed.get("d", {})
    return {
        "site_packages": "site-packages" in str(installed.get("module_file", ""))
        and not installed.get("checkout_records"),
        "a": a.get("is_file") is True and a.get("sha256") == records_sha256,
        "b": b.get("provider_id") == "wilson-ig-v2"
        and b.get("data_sha256") == records_sha256
        and b.get("certificate_describes_equal") is True,
        "c": bool(installed.get("c")) and installed.get("c") == checkout.get("c"),
        "d": d.get("type") == "RecordError"
        and str(d.get("message", "")).startswith("records_missing: "),
    }


def step17e(
    t08_rc: ModuleType,
    out: Path,
    codes: Mapping[str, int],
    dist: Path,
    installed_path: Path,
    checkout_path: Path,
) -> int:
    """17e: T08.A43's build and checks, V03.A17 on the wheel, V03.A19 from the probes."""
    checks: list[dict[str, Any]] = []
    record_path = dist / "t08-a43-dist.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else {}
    t08_rc.check(
        checks,
        "a22.17e.t08_a43",
        codes.get("step17e-dist") == 0 and record.get("passed") is True,
        exit_code=codes.get("step17e-dist"),
        record_sha256=sha256(record_path.read_bytes()) if record_path.exists() else None,
    )
    registration = json.loads((ROOT / REGISTRATION).read_text(encoding="utf-8"))["ship_set"]
    ships = {path: sha256((ROOT / path).read_bytes()) for path in registration["ships"]}
    e01 = json.loads((ROOT / E01_DATA).read_text(encoding="utf-8"))["files"]
    wheel, members = wheel_members(dist)
    findings = wheel_findings(
        members, ships, {row["path"]: row["sha256"] for row in e01}, registration["repository_only"]
    )
    wheel_value = {"wheel": wheel.name if wheel else None, "members": len(members)}
    t08_rc.check(
        checks,
        "a17.ship_set",
        bool(members) and all(row["ok"] for row in findings["ship_set"].values()),
        **wheel_value,
        rows=findings["ship_set"],
    )
    t08_rc.check(
        checks,
        "a17.e01_data",
        len(findings["e01_data"]) == 7 and all(row["ok"] for row in findings["e01_data"].values()),
        rows=findings["e01_data"],
    )
    t08_rc.check(
        checks,
        "a17.no_repository_only_file",
        bool(members) and not findings["repository_only_present"],
        present=findings["repository_only_present"],
    )
    labels = ("step17e-venv", "step17e-lock", "step17e-wheel", "step17e-probe", "step17e-checkout")
    t08_rc.check(
        checks,
        "a19.fresh_venv",
        all(codes.get(label) == 0 for label in labels),
        exits={label: codes.get(label) for label in labels},
    )
    installed = (
        json.loads(installed_path.read_text(encoding="utf-8")) if installed_path.exists() else {}
    )
    checkout = (
        json.loads(checkout_path.read_text(encoding="utf-8")) if checkout_path.exists() else {}
    )
    records_sha256 = ships.get("benchmarks/s10/records.yaml", "")
    for name, ok in a19_findings(installed, checkout, records_sha256).items():
        if name == "c":
            said: dict[str, Any] = {
                "states": sorted(installed.get("c") or {}),
                "installed_sha256": sha256(json.dumps(installed.get("c"), sort_keys=True).encode()),
                "checkout_sha256": sha256(json.dumps(checkout.get("c"), sort_keys=True).encode()),
            }
        else:
            said = {name: installed.get(name)} if name in installed else {}
        t08_rc.check(checks, f"a19.{name}", ok, **said)
    t08_rc.check(
        checks,
        "a19.probe_outputs",
        installed_path.exists() and checkout_path.exists(),
        installed_sha256=sha256(installed_path.read_bytes()) if installed_path.exists() else None,
        checkout_sha256=sha256(checkout_path.read_bytes()) if checkout_path.exists() else None,
        module_file=installed.get("module_file"),
        version=installed.get("version"),
    )
    return _finish(t08_rc, out / "step17" / "rc-step17e.json", "17e", checks)


# -- the A19 probe (standard library and the installed package only) ----------------------------


def exact(value: Any) -> Any:
    """`value` as JSON with every float as `float.hex`, so that equality is bitwise."""
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, enum.Enum):
        return exact(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {item.name: exact(getattr(value, item.name)) for item in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(key): exact(item) for key, item in sorted(value.items())}
    if isinstance(value, list | tuple):
        return [exact(item) for item in value]
    return value


def answers(provider: Any) -> dict[str, Any]:
    """A19 (c): each state's `evaluate_phase` (both phases, every property and derivative; the
    liquid's `lnphi` carries γ) and `flash` (its `k_values` are K)."""
    from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState  # noqa: PLC0415

    inputs = ("T", "P", "n_CH3OH", "n_C2H5OH", "n_H2O")
    found: dict[str, Any] = {}
    for name, (n, temperature, pressure) in A19_STATES.items():
        state = StreamState(n=n, temperature=temperature, pressure=pressure)
        phases = {
            phase: provider.evaluate_phase(
                PropertyRequest(
                    state=state,
                    phase=phase,
                    properties=provider.describe().properties,
                    derivatives=inputs,
                ),
                None,
            )
            for phase in ("LIQUID", "VAPOR")
        }
        flash = provider.flash(FlashRequest(state=state), None)
        found[name] = exact({"evaluate_phase": phases, "flash": flash})
    return found


def probe(checkout: bool) -> dict[str, Any]:
    import openflowsheet  # noqa: PLC0415
    from openflowsheet.thermo import wilson_ig  # noqa: PLC0415
    from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider  # noqa: PLC0415

    found: dict[str, Any] = {
        "module_file": openflowsheet.__file__,
        "version": openflowsheet.__version__,
        "checkout_records": str(wilson_ig._checkout_records() or ""),
    }
    if checkout:
        records = wilson_ig._checkout_records()
        if records is None:
            raise SystemExit("probe --checkout: openflowsheet is not imported from a checkout")
        found["c"] = answers(WilsonIdealGasProvider(records))
        return found
    from openflowsheet.application.binding import Unbound  # noqa: PLC0415
    from openflowsheet.application.revision_binding import provider_for  # noqa: PLC0415
    from openflowsheet.models.revision_flowsheet import WILSON_BASIS  # noqa: PLC0415
    from openflowsheet.resources import packaged_path  # noqa: PLC0415
    from openflowsheet.verify import certificate  # noqa: PLC0415

    path = packaged_path(wilson_ig.RECORDS_PATH)
    found["a"] = {
        "path": str(path),
        "is_file": path is not None and path.is_file(),
        "sha256": sha256(path.read_bytes()) if path is not None else None,
    }
    provider = provider_for(WILSON_BASIS)
    if isinstance(provider, Unbound):
        found["b"] = {"unbound": str(provider)}
    else:
        caps = provider.describe()
        found["b"] = {
            "provider_id": caps.provider_id,
            "data_sha256": caps.data_sha256,
            "certificate_describes_equal": certificate._wilson_provider().describe() == caps,
        }
    found["c"] = answers(WilsonIdealGasProvider(path)) if path is not None else {}
    try:
        WilsonIdealGasProvider()
    except Exception as error:  # noqa: BLE001 - (d) records which exception, if any, was raised
        found["d"] = {"type": type(error).__name__, "message": str(error)}
    else:
        found["d"] = {"type": None, "message": "no exception"}
    return found


# -- main ----------------------------------------------------------------------------------------


STEPS = ("step15", "step17a", "step17b", "step17c", "step17d", "step17e")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("step", choices=(*STEPS, "probe"))
    parser.add_argument("--rc", type=Path, help="the RC record directory (<…>/artifacts/rc)")
    parser.add_argument("--commit", help="C; the checkout must be at it")
    parser.add_argument("--summary", type=Path, help="the runner's summary")
    parser.add_argument("--logs", type=Path, help="the runner's log directory")
    parser.add_argument("--journey", help="step 15: the commit the journey was recorded at")
    parser.add_argument("--modules", type=Path, help="step 17b: the module list that ran")
    parser.add_argument("--dist", type=Path, help="step 17e: t08_dist.py's --out")
    parser.add_argument("--installed", type=Path, help="step 17e: the fresh venv's probe output")
    parser.add_argument("--checkout", type=Path, help="step 17e: the checkout's probe output")
    parser.add_argument("--out", type=Path, help="probe: where to write its JSON")
    parser.add_argument(
        "--in-checkout", action="store_true", help="probe: the checkout's (c) answers only"
    )
    arguments = parser.parse_args(argv)
    if arguments.step == "probe":
        if arguments.out is None:
            parser.error("probe needs --out")
        found = probe(arguments.in_checkout)
        arguments.out.write_text(json.dumps(found, indent=1, sort_keys=True) + "\n", "utf-8")
        return 0
    if arguments.rc is None or arguments.commit is None:
        parser.error(f"{arguments.step} needs --rc and --commit")
    t08_rc, m07a = _modules(ROOT)
    head = t08_rc.git("rev-parse", "HEAD").strip()
    if head != arguments.commit:
        print(f"refused: {ROOT} is at {head}, not at {arguments.commit}", file=sys.stderr)
        return 2
    out: Path = arguments.rc
    if arguments.step == "step17a":
        return step17a(t08_rc, out)
    codes = exit_codes(arguments.summary)
    if arguments.step == "step15":
        return step15(t08_rc, out, codes, arguments.logs, head, arguments.journey)
    if arguments.step == "step17b":
        return step17b(t08_rc, out, codes, arguments.modules)
    if arguments.step == "step17c":
        return step17c(t08_rc, m07a, out, codes, arguments.logs, head)
    if arguments.step == "step17d":
        return step17d(t08_rc, out, codes, arguments.logs)
    return step17e(t08_rc, out, codes, arguments.dist, arguments.installed, arguments.checkout)


if __name__ == "__main__":
    raise SystemExit(main())
