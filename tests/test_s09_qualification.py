"""S09 WO-S09-2: tool-free checks of the BioSTEAM harness and its committed records.

Spec `docs/derivations/S09-spec.md` §11: A03 (blindness: the harness's self-scan, at HEAD and at
the qualification commit), A06 (ladder conformance), A07 (solve path) and A08 (L2(c) conformance),
read from `benchmarks/s09/references/qualification/biosteam.json` and the per-pair records. No tool
runs and nothing of BioSTEAM is imported. WO-S09-3's gate test (`tests/test_s09_references.py`)
carries the classification assertions.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

REFERENCES = REPO_ROOT / "spikes" / "references"
CASES9 = json.loads(
    (REPO_ROOT / "docs" / "derivations" / "scripts" / "s09_cases.json").read_text(encoding="utf-8")
)
CASES3 = json.loads(
    (REPO_ROOT / "docs" / "derivations" / "scripts" / "s03_cases.json").read_text(encoding="utf-8")
)
TOOL_SCRIPTS = ("s09_qualify_biosteam.py", "s09_biosteam_syn001.py", "s09_qualify.sh")
OUT = REPO_ROOT / "benchmarks" / "s09" / "references"
QUAL = OUT / "qualification" / "biosteam.json"
BLIND = CASES9["blindness"]
SETTINGS = CASES9["tool_settings"]["BioSTEAM"]
RUNG_NAMES = ["R1", "R2", "R3", "R4"]
FORBIDDEN_PATHS = ("s09_spike/", "benchmarks/s03/references/results/", "benchmarks/s09/")
ALLOWED_JSON = {"s03_cases.json", "s09_cases.json", "biosteam.json"}


# ---- A03: blindness (§9.2 point 4) -----------------------------------------------------------


def _imports(text: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def scanned_set(read: Any) -> dict[str, str]:
    """The S09 tool scripts and their in-repo imports, transitively: {relative path: text}."""
    todo = [f"spikes/references/{s}" for s in TOOL_SCRIPTS]
    seen: dict[str, str] = {}
    while todo:
        rel = todo.pop()
        if rel in seen:
            continue
        text = read(rel)
        seen[rel] = text
        if rel.endswith(".py"):
            for name in sorted(_imports(text)):
                cand = f"spikes/references/{name}.py"
                if (REPO_ROOT / cand).exists():
                    todo.append(cand)
    return seen


def scan(files: dict[str, str], sha_of: Any) -> list[str]:
    problems = []
    exempt = BLIND["exempt_modules_sha256"]
    for rel, text in sorted(files.items()):
        low = text.lower()
        strings = list(BLIND["forbidden_strings"])
        if rel in exempt:
            if sha_of(rel) != exempt[rel]:
                problems.append(f"{rel}: SHA-256 is not the pinned {exempt[rel]}")
            strings = [s for s in strings if s not in BLIND["exempt_strings"]]
        problems += [f"{rel}: forbidden string {s!r}" for s in strings if s.lower() in low]
        problems += [f"{rel}: forbidden path {p!r}" for p in FORBIDDEN_PATHS if p in text]
        if rel.endswith(tuple(TOOL_SCRIPTS)):
            for token in sorted(set(_json_names(text))):
                if token not in ALLOWED_JSON and not token.startswith("biosteam-{"):
                    problems.append(f"{rel}: input file {token!r} is not registered")
    return problems


def _json_names(text: str) -> list[str]:
    """Every `.json` file name the text mentions (the directory part dropped)."""
    return [f"{m}.json" for m in re.findall(r"([A-Za-z0-9_{}.\-]+)\.json", text)]


def test_a03_inputs_registered() -> None:
    assert sorted(BLIND["input_files"]) == [
        "docs/derivations/scripts/s03_cases.json",
        "docs/derivations/scripts/s09_cases.json",
    ]
    for word in ("s09_spike", "compare_ours", "1.2341901"):
        assert word in BLIND["forbidden_strings"]


def test_a03_blindness_at_head() -> None:
    files = scanned_set(lambda rel: (REPO_ROOT / rel).read_text(encoding="utf-8"))
    assert "spikes/references/t06_fixtures.py" in files
    assert scan(files, lambda rel: hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()) == []


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=True
    ).stdout


def _qualification_commit() -> str:
    try:
        shallow = _git("rev-parse", "--is-shallow-repository").strip()
        commit = _git("log", "-1", "--format=%H", "--", str(QUAL.relative_to(REPO_ROOT))).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:  # explicit refusal
        pytest.fail(f"A03/A16 need git history (R-555's pattern); none: {exc}")
    if shallow == "true" or not commit:
        pytest.fail(
            "A03 needs the qualification commit from git history (R-555's pattern); "
            f"shallow={shallow}, commit={commit!r}"
        )
    return commit


def _records_or_skip() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if not QUAL.exists():
        pytest.skip("WO-S09-2's records are not committed yet")
    qual = json.loads(QUAL.read_text(encoding="utf-8"))
    recs = {
        cid: json.loads((OUT / "results" / f"biosteam-{cid}.json").read_text(encoding="utf-8"))
        for cid in CASES9["pairs"]
    }
    return qual, recs


def test_a03_blindness_at_qualification_commit() -> None:
    qual, _ = _records_or_skip()
    for commit in (_qualification_commit(), qual["harness"]["head"]):
        files = scanned_set(lambda rel, c=commit: _git("show", f"{c}:{rel}"))
        shas = {rel: hashlib.sha256(text.encode()).hexdigest() for rel, text in files.items()}
        assert scan(files, lambda rel, s=shas: s[rel]) == [], commit
    assert qual["harness"]["scripts_clean_at_head"] is True


# ---- A06: ladder conformance -----------------------------------------------------------------


def _attempted(rec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(n, lev) for n, lev in rec["levels"].items() if lev.get("attempted")]


def test_a06_ladder_conformance() -> None:
    _, recs = _records_or_skip()
    reg_rungs = [list(r) for r in SETTINGS["rungs"]]
    for cid, rec in recs.items():
        assert rec["settings"]["registered"] == SETTINGS, cid
        assert rec["levels"]["L2(a)"]["applicable"] is False
        assert rec["levels"]["L2(b)"]["admissible"] is False
        assert rec["levels"]["L3"]["admissible"] is False
        attempted = _attempted(rec)
        assert attempted, f"{cid}: no level attempted"
        for name, lev in attempted:
            rs = lev["rungs"]
            assert [e["rung"] for e in rs] == RUNG_NAMES, (cid, name)
            assert [[e["algorithm"], e["method"]] for e in rs] == reg_rungs, (cid, name)
            src = lev["inspection"]["ladder_source"]
            assert src["matches"] is True and src["registered_rungs"] == reg_rungs, cid
            assert [
                list(p) for p in zip(src["default_algorithms"], src["default_methods"], strict=True)
            ] == reg_rungs
            for e in rs:
                for run in _runs(e):
                    app = run["path"]["applied"]
                    assert app["algorithms"] == [e["algorithm"]] and app["methods"] == [e["method"]]
                    assert app["early_termination"] is False
                    assert app["maxiter"] == SETTINGS["common"]["maxiter"]
                    assert app["max_attempts"] == SETTINGS["common"]["max_attempts"]
                    assert app["use_cache"] is True and app["specifications_by_weight"] is False
                    assert app["tolerance"] == app["relative_tolerance"]
            passing = [e["rung"] for e in rs if e["passes"]]
            if lev["passes"]:
                assert lev["selected_rung"] == passing[0], cid
                assert lev["path_dependence"]["fires"] is False
        if rec["available"]:
            assert rec["selected_rung"] == rec["levels"][rec["level"]]["selected_rung"]
        else:
            for name in ("L1", "L2(c)"):
                lev = rec["levels"][name]
                expressible = lev["realization"].get("expressible")
                if lev.get("attempted"):
                    assert len(lev["rungs"]) == 4
                elif expressible:
                    assert name == "L2(c)" and rec["levels"]["L1"]["realization"]["expressible"]


def _runs(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Every complete run of an attempt that was recorded with its path: the rung's (L1) or its
    final outer evaluation (L2(c)), and the accuracy rerun's."""
    out = [
        r
        for r in (entry.get("run"), (entry.get("accuracy_rerun") or {}).get("run"))
        if r is not None and "path" in r
    ]
    return out


# ---- A07: the solve path ---------------------------------------------------------------------


def test_a07_solve_path() -> None:
    _, recs = _records_or_skip()
    for cid, rec in recs.items():
        for name, lev in _attempted(rec):
            for e in lev["rungs"]:
                runs = _runs(e)
                if e["passes"]:
                    assert len(runs) == 2, (cid, name, e["rung"])
                for run in runs:
                    path = run["path"]
                    assert "pass1" in path and "pass2" in path
                    assert "iter" in path["pass1"] and "iter" in path["pass2"]
                    # §18.3: per pass, whether fsolve ran (object identity) and its counts.
                    for p in ("pass1", "pass2"):
                        fs = path[p]["fsolve"]
                        assert set(fs) == {"ran", "nfev", "ier", "mesg"}
                        assert (fs["nfev"] is None) == (not fs["ran"]), (cid, e["rung"], p)
                    b2 = run["rule2"]["checks"]["B2"]
                    assert b2["counter"] == ("fsolve nfev" if e["rung"] == "R3" else "iter")
                    resp = path["respecification"]
                    assert resp["route"] == "attribute_setter"
                    specs = path["stage_specifications"]
                    assert sorted(int(s["stage"]) for s in resp["set"]) == sorted(
                        int(k) for k in specs
                    )
                    rb = run["rule2c"]["checks"]["specification_readback"]
                    assert len(
                        [r for r in rb["rows"] if r["specification"] != "bottom_side_draw"]
                    ) == len(specs)
                    for row in rb["rows"]:
                        assert row["passes"] == (
                            row["stored"] == row["expected_stored"]
                            and (
                                row["specification"] == "bottom_side_draw"
                                or row["specified_variable"] == row["expected_variable"]
                            )
                        )
                    if e["passes"]:
                        assert rb["passes"] is True, (cid, e["rung"])


# ---- A08: L2(c) conformance ------------------------------------------------------------------


def test_a08_l2c_conformance() -> None:
    _, recs = _records_or_skip()
    ol = SETTINGS["outer_loop"]
    for cid, rec in recs.items():
        lev = rec["levels"]["L2(c)"]
        l1 = rec["levels"]["L1"]["realization"]
        if not lev.get("attempted"):
            continue
        assert l1["expressible"] is False, cid
        real = lev["realization"]
        case = CASES3["cases"][rec["inputs_case"]]
        n = int(case["stage_count"])
        adj = real["adjusted"]
        if real["outer_end"] == "condenser":
            assert adj == {"name": "Reflux", "stage": 0}
        else:
            assert adj == {"name": "Boilup", "stage": n - 1}
        assert real["registered"] == case["specifications"][real["outer_end"]]
        kind = real["registered"]["kind"]
        tol2 = float(SETTINGS["floor_rerun"]["tolerance"])
        for e in lev["rungs"]:
            loop = e["outer"]
            ytol = float(ol["ytol"][kind][0])
            assert loop["ytol"] == ytol and loop["basis"] == ol["ytol"][kind][1]
            _check_loop(cid, loop, ytol)
            # §18.4(b): the accuracy rerun is one evaluation at the binary64 x of the rung's final
            # evaluation, at 1e-9, with no further outer evaluation.
            rerun = e.get("accuracy_rerun")
            if rerun is None:
                continue
            assert rerun["outer"] is None, (cid, e["rung"])
            assert rerun["form"].startswith("L2(c): ")
            x = e["run"]["x"]
            # JSON round-trips binary64 exactly, so == compares the bits (x > 0).
            assert x == loop["returned_x"] and rerun["run"]["x"] == x, (cid, e["rung"])
            assert rerun["tolerance"] == tol2
            app = rerun["run"]["path"]["applied"]
            assert app["tolerance"] == tol2 and app["relative_tolerance"] == tol2


def _check_loop(cid: str, loop: dict[str, Any], ytol: float) -> None:
    ev = loop["evaluations"]
    xs = [v["x"] for v in ev]
    assert xs[:1] == [1.0], cid
    if len(ev) > 1 and ev[0]["failed"] is None:
        assert xs[1] == 2.0, cid
    exp = [v for v in ev if v["role"] == "expansion"]
    if exp:
        up = abs(ev[1]["g"]) <= abs(ev[0]["g"])
        assert loop["expansion"] == ("up" if up else "down")
        prev = 2.0 if up else 1.0
        for v in exp:
            assert v["x"] == (prev * 2.0 if up else prev / 2.0), cid
            prev = v["x"]
        assert len(exp) <= 4
    if "solver_call" in loop:
        b = loop["bracket"]
        assert loop["solver_call"]["positional"] == [
            "g",
            b["a"],
            b["b"],
            b["g_a"],
            b["g_b"],
            None,
            0.0,
            ytol,
            [],
            50,
            False,
            True,
            True,
        ]
        assert b["g_a"] * b["g_b"] < 0
    if loop["passes"]:
        assert all(v["failed"] is None for v in ev), cid
        final = ev[-1]
        assert final["role"] == "final" and final["x"] == loop["returned_x"]
        assert math.isfinite(final["g"]) and abs(final["g"]) <= ytol
        assert loop["final_g"] == final["g"]
    else:
        assert loop["failure"], cid


def test_records_cover_the_registered_pairs() -> None:
    qual, recs = _records_or_skip()
    assert qual["pairs"] == CASES9["pairs"]
    assert sorted(qual["cases"]) == sorted(CASES9["pairs"])
    for cid, rec in recs.items():
        assert rec["case"] == cid and rec["tool"] == "BioSTEAM"
        assert rec["environment_fingerprint"]["matches"] is True, cid
    for cid in CASES9["not_applicable"]:
        assert not (OUT / "results" / f"biosteam-{cid}.json").exists()
    assert Path(QUAL).read_text(encoding="utf-8").endswith("\n")
