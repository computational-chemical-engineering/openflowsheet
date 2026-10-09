"""Generate `evidence/M02/<C>/manifest.json` by measuring, not by transcribing. M02 WO-13.

Design note `docs/design/M02-pymrm-adapter.md` §9 (WO-13), §10 (gates G1–G12) as amended by
§14.2–§14.7, and the design-lane review `docs/reviews/M02-review.md` (F10's manifest items). The
manifest carries one check per gate, read from §10 itself, so that a gate cannot be left out: a
gate without a rule here, or a rule without a gate there, stops the script. Each check is decided
from what this script ran or read at `C`:

1. **The M02 tests**, run once here (`pytest --junitxml` over `tests/test_m02_*.py`) with
   `-m "pymrm or not pymrm"`, so the two opt-in `pymrm` tests (the reactor environment's pins and
   A47 (a), bitwise) run as well and fail if the reactor environment is absent. Every node is
   assigned to at least one gate by `SELECTORS` (an unassigned node stops the script); a failed or
   skipped node fails its gates, and a selector that matches no node fails its gate.
2. **The gate**: the stdout of `scripts/check.sh` at `C`, required to end `check.sh: PASSED`.
3. **G2's corpus dump** (`scripts/m02_g2_corpus.py`), run here: its SHA-256 must carry the prefix
   every earlier M02 run recorded (`659748576adb9730`, build log D127), i.e. byte-identical.
4. **The served MCP tool list**, digested here as `test_t08_w2_surface_digest` digests it: the
   full served digest (M02's own, registered at the merge commit, R-234) and the digest without
   M02's additions, which must be Amendment 3's registered `6c4375b4…`.
5. **The opt-in records** (G10–G12, WO-12/WO-12a/WO-12b), read, never re-run here: each check
   names the record, its SHA-256, `judged: false`, and the numbers the gate is decided by.

Status is `tested` only if every check is `pass` and every command exited 0; otherwise
`implemented`. `reviewed` is never set, and both review fields stay `pending`.

`--harvest` rewrites the M02 entries of `benchmarks/t08/support_envelope.yaml#harvest`
(T08.A21: every limitation classified) and regenerates `docs/support-matrix.md` with
`t08_support_matrix.py --emit`.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/m02_evidence_manifest.py --commit C \\
        --gate-log GATE_STDOUT [--harvest]
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
NOTE = ROOT / "docs" / "design" / "M02-pymrm-adapter.md"
ENVELOPE = ROOT / "benchmarks" / "t08" / "support_envelope.yaml"
M02 = ROOT / "benchmarks" / "m02"
REQUIREMENTS = ("D10",)
#: The default gate's selection plus the opt-in `pymrm` tests (`pyproject.toml` deselects them).
PYMRM_TOO = "pymrm or not pymrm"
#: The G2 dump's identity as every M02 run since WO-8 recorded it (build log D127: 16 hex digits).
G2_DUMP_PREFIX = "659748576adb9730"
#: ADR 0019 Amendment 3's served digest (R-192), which M02's surface decomposes onto (R-234).
M02_BASE_SERVED_SHA256 = "6c4375b478d71c12b1211c17fafe7e58e9dfc0a05e11def2106799a6917631c9"

#: Each gate's test nodes: `module::function-pattern` (fnmatch on the function name, parameters
#: stripped). Every node of `tests/test_m02_*.py` must fall under at least one gate.
SELECTORS: Mapping[str, tuple[str, ...]] = {
    "G1": ("test_m02_schemas.py::*",),
    "G2": (
        "test_m02_join.py::*",
        "test_m02_wo7_binding.py::*",
        "test_m02_wo8_registries.py::*",
        "test_m02_wo8_verifier.py::test_g2i_*",
    ),
    "G3": ("test_m02_kill_chain.py::*",),
    "G4": ("test_m02_experiments.py::*", "test_m02_experiment_job.py::test_g4i_*"),
    "G5": ("test_m02_experiment_job.py::*", "test_m02_experiment_body_isolation.py::*"),
    "G6": (
        "test_m02_variants.py::*",
        "test_m02_wo7_binding.py::test_g6a_*",
        "test_m02_wo10_coupled.py::test_g6c_*",
    ),
    "G7": (
        "test_m02_wo8_g7.py::*",
        "test_m02_wo8_blocks.py::*",
        "test_m02_wo8_region.py::*",
        "test_m02_wo8_units.py::*",
        "test_m02_wo8_verifier.py::*",
        "test_m02_wo9_reactor.py::test_g7f_*",
    ),
    "G8": (
        "test_m02_wo9_reactor.py::*",
        "test_m02_wo10_driver.py::*",
        "test_m02_wo10_coupled.py::*",
        "test_m02_wo14.py::*",
    ),
    "G9": ("test_m02_wo11_promotion.py::*",),
    "G10": (
        "test_m02_g10_record.py::*",
        "test_m02_pymrm_child.py::*",
        "test_m02_pymrm_env.py::*",
    ),
    "G11": ("test_m02_wo12b_v3.py::*", "test_m02_experiments.py::test_g11v3_*"),
    "G12": ("test_m02_wo14.py::test_rp1_*",),
}

#: The manifest's limitations and their T08.A21 class (all stay in the manifest: P).
LIMITATIONS: tuple[tuple[str, str], ...] = (
    (
        "W21 ('PyMRM boundary/accuracy/execution and provenance') and W22 are v0.2 requirement "
        "ids the manifest schema's `requirements` pattern ([DA]nn) cannot carry. This evidence "
        "bears on W21 (design note §10.4 lists which gates bear on which part); its verdict is "
        "the `verdict` lane's, not this manifest's.",
        "W21 outside the requirements pattern; its verdict is the verdict lane's",
    ),
    (
        "The real-reactor evidence (G10–G12) is opt-in: it needs the separately built, pinned "
        "reactor environment (design note §2.4), runs on Linux only (macOS best effort, Windows "
        "refused before spawn; ADR 0033 D2) and is R3. Its records were measured on one machine "
        "(the records name the CPU model and the environment fingerprint) and are read here, not "
        "re-run (only the two `pymrm` environment tests, A47 (a) bitwise among them, run here); "
        "they carry `judged: false`. No second registered architecture was available, so "
        "G12's cross-architecture `compatible_reproduction` was not run.",
        "real-reactor runs opt-in, Linux-only, R3, one machine, read not re-run",
    ),
    (
        "`external-subprocess-v1` is not a sandbox: no filesystem confinement, network "
        "isolation, memory or CPU quota, or syscall filtering; trust rests on provenance "
        "(ADR 0033 D2; design note §12 N1, accepted for v0.2 local use as the default pending "
        "Frank).",
        "isolation profile not a sandbox (stated in the envelope's external_execution axis)",
    ),
    (
        "v3's inert floor y_inert >= 0.035 sits just above a measured S1 failure (0.03 at "
        "653.15 K, 11 MPa, H2/N2 2.5; build log D105). G11 samples only the corners and the "
        "centre of the hard domain; the real loop's smallest request is 1.116 x the floor (D115). "
        "An in-domain S1 failure ends in a refusal and then an honest COUPLING_NOT_CONVERGED, "
        "never a false success (M02 review F10).",
        "v3's inert floor near a measured S1 failure; corners and centre only (review F10)",
    ),
    (
        "G8 (c)'s sequential-substitution oracle is independent of the EO machinery in flowsheet "
        "structure, not in thermodynamics: it shares `thermo.pr_c1` with the code under test, "
        "which M01's evidence covers (M02 review F10).",
        "G8 (c) oracle shares pr_c1 (review F10)",
    ),
    (
        "Self-generated outputs are regression fixtures, not validation: the G10/G11 records are "
        "judged against M01's bounds and the probe record; G8 (f) against the design lane's table "
        "through an independent replica; G12 by its certificate, with its record a regression "
        "fixture. This is numerical verification, not empirical validation of the reactor model.",
        "self-generated records are regression fixtures (review F10)",
    ),
    (
        "Cross-platform reproduction of a coupled run rests on the per-float rules of R-317 "
        "(the coupling record) and build log D130 (a failure bundle's compact copy, a session "
        "decision not yet ruled by the design lane), tested by perturbing the last bits on one "
        "machine (RP-2, RP-2b, D130), not by a run on a second architecture.",
        "coupled cross-platform replay tested by a one-ulp seam only; D130 unruled",
    ),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def catalogue() -> list[str]:
    """`G1`…`G12`: every gate of §10 (`- **Gnn …**` bullets), in order."""
    text = NOTE.read_text(encoding="utf-8")
    section = text[text.index("## 10. Verification gates") : text.index("### 10.3")]
    found = re.findall(r"^- \*\*(G\d+) ", section, re.MULTILINE)
    if len(found) != len(set(found)):
        raise SystemExit(f"duplicate gate ids in {NOTE.name} §10")
    return found


def _description(gate: str) -> str:
    text = NOTE.read_text(encoding="utf-8")
    section = text[text.index("## 10. Verification gates") : text.index("### 10.3")]
    match = re.search(rf"^- \*\*{gate} ([^*]+)\*\*", section, re.MULTILINE)
    assert match is not None
    return f"M02 design note §10, {gate} ({match[1].rstrip('.')}), as amended by §14.2–§14.7."


# ----------------------------------------------------------------------------- the tests


def _nodeid(classname: str, name: str) -> str:
    parts = classname.split(".")
    for index, part in enumerate(parts):
        if part.startswith("test_"):
            return "::".join(["/".join(parts[: index + 1]) + ".py", *parts[index + 1 :], name])
    return f"collection::{classname}::{name}"


def run_tests(artifacts: Path) -> tuple[dict[str, str], dict[str, Any]]:
    modules = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.glob("tests/test_m02_*.py"))
    junit, stdout = artifacts / "m02-tests.junit.xml", artifacts / "m02-tests.stdout.txt"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", PYMRM_TOO]
        + [f"--junitxml={junit}", *modules],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    nodes: dict[str, str] = {}
    for case in ElementTree.parse(junit).getroot().iter("testcase"):
        node = _nodeid(case.get("classname", ""), case.get("name", ""))
        tags = {child.tag for child in case}
        if tags & {"failure", "error"} or nodes.get(node) == "failed":
            nodes[node] = "failed"
        else:
            nodes[node] = "skipped" if "skipped" in tags else "passed"
    command = {
        "cmd": "PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider "
        f"-m '{PYMRM_TOO}' --junitxml=ARTIFACTS/m02-tests.junit.xml tests/test_m02_*.py",
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": _sha256(stdout),
    }
    return nodes, command


def _matches(node: str, selector: str) -> bool:
    module, _, pattern = selector.partition("::")
    path, _, name = node.partition("::")
    return path == f"tests/{module}" and fnmatch.fnmatchcase(name.split("[", 1)[0], pattern)


def assigned(nodes: Mapping[str, str]) -> dict[str, dict[str, str]]:
    by_gate = {
        gate: {n: o for n, o in nodes.items() if any(_matches(n, s) for s in selectors)}
        for gate, selectors in SELECTORS.items()
    }
    loose = sorted(set(nodes) - {n for picked in by_gate.values() for n in picked})
    if loose:
        raise SystemExit(f"test nodes assigned to no gate: {loose}")
    return by_gate


def _tests_value(
    picked: Mapping[str, str], selectors: Sequence[str]
) -> tuple[dict[str, Any], bool]:
    counts = {o: sum(v == o for v in picked.values()) for o in ("passed", "failed", "skipped")}
    empty = [s for s in selectors if not any(_matches(n, s) for n in picked)]
    value = {"selectors": [f"tests/{s}" for s in selectors], **counts}
    if empty:
        value["selectors_matching_no_node"] = empty
    return value, bool(picked) and counts["failed"] == counts["skipped"] == 0 and not empty


# ----------------------------------------------------------------------------- the inputs


def read_gate(log: Path) -> dict[str, Any]:
    text = log.read_text(encoding="utf-8")
    verdicts = [line for line in text.splitlines() if line.startswith("=== check.sh: ")]
    summary = re.findall(r"^(\d+ passed.*) in [\d.]+s", text, re.MULTILINE)
    return {
        "passed": verdicts[-1:] == ["=== check.sh: PASSED ==="],
        "pytest": summary[-1] if summary else None,
        "stdout_sha256": _sha256(log),
    }


def g2_dump(artifacts: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    out = artifacts / "m02-g2-corpus.json"
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}:{ROOT / 'tests'}"}
    with out.open("wb") as handle:
        completed = subprocess.run(
            [sys.executable, "scripts/m02_g2_corpus.py"],
            cwd=ROOT,
            env=env,
            stdout=handle,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    digest = _sha256(out)
    value = {
        "sha256": digest,
        "expected_prefix": G2_DUMP_PREFIX,
        "byte_identical": digest.startswith(G2_DUMP_PREFIX),
    }
    command = {
        "cmd": "PYTHONPATH=src:tests .venv/bin/python scripts/m02_g2_corpus.py "
        "> ARTIFACTS/m02-g2-corpus.json",
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": digest,
    }
    return value, command


def mcp_digest() -> dict[str, Any]:
    """The served MCP tool list digested as `harness.tool_descriptions_sha256` and
    `test_t08_w2_surface_digest` digest it, in full and without M02's additions (R-234)."""
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT)]
    from m02_schema_support import without_m02

    from openflowsheet.application.bindings import mcp
    from openflowsheet.canonical import canonical_json

    mcp.tools.cache_clear()
    tools = [tool.model_dump(mode="json", exclude_none=True) for tool in mcp.tools()]
    served = hashlib.sha256(canonical_json(tools)).hexdigest()
    base = hashlib.sha256(canonical_json(without_m02(tools))).hexdigest()
    from benchmarks.t07.v17 import harness

    return {
        "served_sha256": served,
        "harness_tool_descriptions_sha256": harness.tool_descriptions_sha256(),
        "without_m02_sha256": base,
        "registered_base": M02_BASE_SERVED_SHA256,
        "decomposes_onto_base": base == M02_BASE_SERVED_SHA256,
        "tools": len(tools),
        "note": "M02's own served digest is registered at the merge commit on the combined tree "
        "(R-234); this value is evidence, not a pin.",
    }


def _record(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    path = M02 / name
    document = json.loads(path.read_text(encoding="utf-8"))
    head = {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _sha256(path),
        "judged": document.get("judged"),
        "variant": document.get("variant", {}).get("variant_id"),
    }
    return document, head


def _worst(values: Any) -> float:
    if isinstance(values, dict):
        return max(float(v) for v in values.values())
    if isinstance(values, list):
        return max(float(v) for v in values)
    return float(values)


def g10() -> tuple[dict[str, Any], bool]:
    document, head = _record("g10-adapter-halves-v3.json")
    a = document["assertions"]
    value = {
        "record": head,
        "G10v3_met": document["G10v3"]["met"],
        "round2_ran": document["G10v3"]["round2_ran"],
        "A41_accepted": a["A41"]["accepted"],
        "A42_max_rel_diff": a["A42"]["max_rel_diff"],
        "A42_bound": a["A42"]["bound"],
        "A43_repeat_bitwise_equal": a["A43"]["repeat_bitwise_equal"],
        "A44_bitwise_identical": a["A44"]["bitwise_identical"],
        "A45_element_defect_max": _worst(a["A45"]["element_defect_max"]),
        "A45_bound": a["A45"]["bound"],
        "A46_dP_over_P_max": _worst(a["A46"]["dP_over_P"]),
        "A46_bound": a["A46"]["bound"],
        "A47_a_environment_block_equal": a["A47"]["a_environment_block_equal"],
        "A47_a_bitwise": a["A47"]["a_bitwise"],
        "A47_b_max_rel_diff": a["A47"]["b_max_rel_diff"],
        "A47_b_bound": a["A47"]["b_bound"],
        "A48_estimates_equal_reference": a["A48"]["estimates_equal_reference"],
    }
    ok = (
        head["judged"] is False
        and value["G10v3_met"] is True
        and all(value["A41_accepted"])
        and value["A42_max_rel_diff"] <= value["A42_bound"]
        and all(value["A43_repeat_bitwise_equal"])
        and value["A44_bitwise_identical"] is True
        and value["A45_element_defect_max"] <= value["A45_bound"]
        and value["A46_dP_over_P_max"] <= value["A46_bound"]
        and value["A47_a_bitwise"] is True
        and value["A47_b_max_rel_diff"] <= value["A47_b_bound"]
        and all(value["A48_estimates_equal_reference"])
    )
    return value, ok


def g11() -> tuple[dict[str, Any], bool]:
    document, head = _record("g11-coverage-v3.json")
    _, first = _record("g11-coverage.json")
    summary = document["summary"]
    met = {
        key: item["met"]
        for key, item in summary.items()
        if isinstance(item, dict) and "met" in item
    }
    value = {
        "record": head,
        "superseded_record": first,
        "met": met,
        "G11v3-4_selected": summary["G11v3-4"]["selected"],
        "G11v3-5_runs": summary["G11v3-5"]["runs"],
        "G11v3-5_points_per_run": summary["G11v3-5"]["points_per_run"],
        "G11v3-5_all_equal": summary["G11v3-5"]["all_equal"],
        "variant_timeout_s": document["variant"].get("timeout_s"),
    }
    ok = (
        head["judged"] is False
        and all(met.values())
        and value["G11v3-4_selected"] == "V5"
        and value["G11v3-5_all_equal"] is True
    )
    return value, ok


def g12() -> tuple[dict[str, Any], bool]:
    document, head = _record("g12-real-loop-v3.json")
    edges, edges_head = _record("g12-real-loop-v3-edges.json")
    s = document["summary"]
    accepted = len(document["iterations"])
    inlet = s["reactor_inlet"]
    value = {
        "record": head,
        "edges_record": edges_head,
        "outcome": s["outcome"],
        "verification_status": s["verification_status"],
        "reproducibility_class": s["reproducibility_class"],
        # Review F10: the code's meaning (accepted iterates, as `max_outer` counts them); the
        # record's `outer_iterations` is the final k.
        "outer_iterations": accepted,
        "final_k": s["outer_iterations"],
        "rho_final": s["rho_final"],
        "floor_ratio_xi_final": s["floor_ratio_xi_final"],
        "floor_ratio_T_final": s["floor_ratio_T_final"],
        "experiments": s["experiments"],
        "reactor_inlet_hard_domain_violations": inlet["hard_domain_violations"],
        "reactor_inlet_per_tube_multiple_of_F_nom": inlet["per_tube_multiple_of_F_nom"],
        "rp1_constants_equal": s["rp1_constants_sha256"]["equal"],
        "reproduce": {k: s["reproduce"][k] for k in ("verdict", "bitwise_floats", "reasons")},
        "live_rerun_repeat_bitwise_equal": s["live_rerun"]["repeat_bitwise_equal"],
        "solve_wall_s": s["solve_wall_s"],
        "edges": edges["summary"],
    }
    ok = (
        head["judged"] is False
        and value["outcome"] == "CONVERGED"
        and value["verification_status"] == "VERIFIED"
        and accepted <= 15
        and value["rho_final"] <= 1.0
        and min(value["floor_ratio_xi_final"], value["floor_ratio_T_final"]) >= 10.0
        and inlet["hard_domain_violations"] == []
        and 0.5 <= inlet["per_tube_multiple_of_F_nom"] <= 2.0
        and value["rp1_constants_equal"] is True
        and value["reproduce"]["verdict"] == "MATCH"
        and all(value["live_rerun_repeat_bitwise_equal"])
        and edges["summary"]["a_converged_verified"] is True
        and edges["summary"]["b_no_out_of_domain"] is True
    )
    return value, ok


# ----------------------------------------------------------------------------- the checks


def checks(
    nodes: Mapping[str, str],
    gate: Mapping[str, Any],
    dump: Mapping[str, Any],
    surface: Mapping[str, Any],
) -> list[dict[str, Any]]:
    gates = catalogue()
    if set(gates) != set(SELECTORS):
        raise SystemExit(f"gates {gates} and selectors {sorted(SELECTORS)} differ")
    by_gate = assigned(nodes)
    records = {"G10": g10(), "G11": g11(), "G12": g12()}
    out: list[dict[str, Any]] = []
    for gid in gates:
        tests, ok = _tests_value(by_gate[gid], SELECTORS[gid])
        value: dict[str, Any] = {"tests": tests}
        if gid == "G1":
            value["mcp_tool_list"] = surface
            ok = ok and surface["decomposes_onto_base"]
        if gid == "G2":
            value["g2_corpus_dump"] = dump
            value["gate"] = gate
            ok = ok and dump["byte_identical"] and gate["passed"]
        if gid in records:
            measured, recorded_ok = records[gid]
            value["measured"] = measured
            ok = ok and recorded_ok
        out.append(
            {
                "id": f"M02.{gid}",
                "description": _description(gid),
                "result": "pass" if ok else "fail",
                "value": value,
            }
        )
    return out


def status(checks_: Sequence[Mapping[str, Any]], commands: Sequence[Mapping[str, Any]]) -> str:
    every = all(c["result"] == "pass" for c in checks_)
    return "tested" if every and all(c["exit_code"] == 0 for c in commands) else "implemented"


# ----------------------------------------------------------------------------- harvest


def harvest_entries(path: str, manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    from t08_support_matrix import text_sha256

    table = dict(LIMITATIONS)
    entries = [
        {
            "manifest": path,
            "item": f"limitations[{index}]",
            "sha256": text_sha256(text),
            "class": "P",
            "to": [],
            "note": table[text],
        }
        for index, text in enumerate(manifest["limitations"])
    ]
    failing = [c["id"] for c in manifest["checks"] if c["result"] != "pass"]
    if failing:
        raise SystemExit(f"{failing} not pass: not classified; fix them first")
    return entries


def _yaml_entry(entry: Mapping[str, Any]) -> str:
    lines = [f"- manifest: {entry['manifest']}", f"  item: {entry['item']}"]
    lines += [f"  sha256: {entry['sha256']}", f"  class: {entry['class']}", "  to: []"]
    lines.append(f"  note: {entry['note']}")
    return "\n".join(lines) + "\n"


def write_harvest(entries: Sequence[Mapping[str, Any]]) -> None:
    """Replace the envelope's `evidence/M02/` harvest entries with `entries`, at the end of the
    list (the file's last section), leaving every other byte as it is."""
    text = ENVELOPE.read_text(encoding="utf-8")
    head, marker, body = text.partition("\nharvest:\n")
    if not marker:
        raise SystemExit("support_envelope.yaml has no harvest section")
    blocks = re.split(r"(?m)^(?=- manifest: )", body)
    kept = [b for b in blocks if b and not b.startswith("- manifest: evidence/M02/")]
    if any(not b.startswith("- manifest: ") for b in kept):
        raise SystemExit("support_envelope.yaml: unexpected text in the harvest section")
    ENVELOPE.write_text(
        head + marker + "".join(kept) + "".join(_yaml_entry(e) for e in entries), encoding="utf-8"
    )
    loaded = yaml.safe_load(ENVELOPE.read_text(encoding="utf-8"))["harvest"]
    written = [e for e in loaded if str(e.get("manifest", "")).startswith("evidence/M02/")]
    if written != [dict(e) for e in entries]:
        raise SystemExit("support_envelope.yaml: the harvest entries did not round-trip")


# ----------------------------------------------------------------------------- main


def _artifact(path: str, description: str) -> dict[str, str]:
    return {"path": path, "sha256": _sha256(ROOT / path), "description": description}


ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("docs/design/M02-pymrm-adapter.md", "The design note (gates §10, amendments §14.2–§14.7)."),
    ("docs/reviews/M02-review.md", "The design-lane review (F1–F10, rulings R-317, R-318)."),
    ("docs/design/M02-build-decisions.md", "The build log (D-entries with the measured values)."),
    ("benchmarks/m02/numerical_policy_external.yaml", "M02's numerical-policy addendum (R-317)."),
    ("benchmarks/m02/g10-adapter-halves-v3.json", "G10v3: adapter halves of M01.A41-A48."),
    ("benchmarks/m02/g11-coverage-v3.json", "G11v3: coverage, box selection, timing."),
    ("benchmarks/m02/g11-coverage.json", "G11 under v2 (superseded by v3, §14.5)."),
    ("benchmarks/m02/g12-real-loop-v3.json", "G12 under v3: the real loop, replay, live rerun."),
    ("benchmarks/m02/g12-real-loop-v3-edges.json", "G12v3-2: the loop at the T edges."),
    ("benchmarks/m02/c1-loop-standin.json", "C1-LOOP-M02-v1 with the stand-in (G8)."),
    ("benchmarks/m02/c1-loop-real.json", "C1-LOOP-M02-v1 with the real reactor, v3 (G12)."),
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--commit", required=True)
    parser.add_argument("--gate-log", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--harvest", action="store_true")
    args = parser.parse_args(argv)
    commit = _git("rev-parse", args.commit).strip()
    if _git("rev-parse", "HEAD").strip() != commit:
        raise SystemExit(f"HEAD is not {commit}: check it out first")
    if _git("status", "--porcelain", "--untracked-files=no").strip():
        raise SystemExit("the working tree has changes: the manifest must describe C")
    out = args.out or ROOT / "evidence" / "M02" / commit / "manifest.json"
    with tempfile.TemporaryDirectory(prefix="m02-evidence-") as scratch:
        artifacts = Path(scratch)
        nodes, test_command = run_tests(artifacts)
        dump, dump_command = g2_dump(artifacts)
        surface = mcp_digest()
        gate = read_gate(args.gate_log)
        commands = [
            {
                "cmd": "PYTHONPATH=src PATH=.venv/bin:$PATH ./scripts/gate.sh",
                "cwd": ".",
                "exit_code": 0 if gate["passed"] else 1,
                "stdout_sha256": gate["stdout_sha256"],
            },
            test_command,
            dump_command,
        ]
        result = checks(nodes, gate, dump, surface)
    lock = ROOT / "requirements.lock"
    manifest = {
        "work_package": "M02",
        "commit": commit,
        "requirements": list(REQUIREMENTS),
        "status": status(result, commands),
        "inputs": {
            "case_id": "C1-LOOP-M02-v1 (stand-in and real reactor v3), the registered variants, "
            "the T07 corpus (G2), M01's registered states (G7), the opt-in records G10-G12",
            "case_hash": _sha256(M02 / "c1-loop-standin.json"),
            "environment_lock_hash": _sha256(lock),
        },
        "commands": commands,
        "checks": result,
        "artifacts": [_artifact(path, text) for path, text in ARTIFACTS],
        "limitations": [text for text, _ in LIMITATIONS],
        "review": {"numerical": "pending", "process_model": "pending"},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.harvest:
        sys.path.insert(0, str(ROOT / "scripts"))
        write_harvest(harvest_entries(out.relative_to(ROOT).as_posix(), manifest))
        subprocess.run(
            [sys.executable, "scripts/t08_support_matrix.py", "--emit"], cwd=ROOT, check=True
        )
    failed = [c["id"] for c in result if c["result"] != "pass"]
    print(f"{manifest['status']}: {len(result) - len(failed)}/{len(result)} pass {failed or ''}")
    return 0 if manifest["status"] == "tested" else 1


if __name__ == "__main__":
    raise SystemExit(main())
