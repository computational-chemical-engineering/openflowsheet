"""T08 W3.2 (T08.A61, Q6): run the group's released ammonia reactor outside this environment.

Release spec `docs/derivations/T08-release-spec.md` §7.1 item 4, §7.5, §9 T08.A61, §12 Q6; briefs
`docs/briefs/T08-phase3-v19.md` item 1 and `docs/briefs/T08-W3.2-redo.md` item 1. The reactor is the
group's released code, `ammonia_synthesis_reactor` `main` @ 6089593 (MIT; tag `v1.1.0` is its
parent d78fbfb, see the record), read and run from a fresh clone only. Nothing here is imported by
`openflowsheet` or by the default test run; `tests/test_t08_w3_v19_records.py` checks the form of
the record this script writes, not the model.

**Environment.** Run with the Python of a separate virtual environment in which the fresh clone was
installed with ``pip install -e ".[test]"`` (it resolves `pymrm` and the other dependencies from
PyPI), never this project's `.venv`. The record of 2026-10-01 was made with a stdlib ``venv`` under
the session scratchpad (Python 3.13.5)::

    python3 -m venv <venv> && (cd <clone> && <venv>/bin/pip install -e ".[test]")
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \\
        <venv>/bin/python benchmarks/t08/v19/c1_reactor_run.py \\
        --group-repo <clone> --out benchmarks/t08/v19/c1-reactor.json

**What it runs.**

1. The group's test suite, ``python -m pytest tests/ -q`` in the clone (the package is installed
   from it), with ``-rs`` so the skip reasons are recorded and ``-p no:cacheprovider`` so nothing
   is written into the clone. On `main` this suite is the group's regression reference (there is
   no stored-field regression harness); the clone's tracked tree is checked clean before and after.
2. One non-isothermal 1D solve of a shipped case of the 52-case paper table
   (``data/inputs/cases_to_run.xlsx``) through the group's own pipeline entry point,
   ``reactor.paper.runner.run_case_1d`` (cold start, publication grid, its convergence certificate
   and element-balance check), timed ``--repeats`` times. The solves run in a ``git archive``
   export of the pinned commit so the pipeline's cache lands in a temporary directory, not in the
   clone.
3. The same case with every membrane permeance pre-factor set to zero (``P0_H2 = P0_N2 = P0_NH3 =
   0``, fields of ``ReactorConfig``; ``Perm_NH3`` is a removed field): no species crosses the
   membrane, which is the packed bed of Q6. The permeate tube still exchanges heat with the bed;
   the isothermal variant removes that coupling too and is compared with the equilibrium bound of
   the group's own rate law. The isothermal variant is run twice: from the pipeline's cold start
   (``DT_INIT_1D``) and from the start of the group's own isothermal path (``ROSSETTI_DT_INIT``).

It reports; it judges nothing (T08.A61's verdict is the design lane's).
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PINNED_COMMIT = "6089593464fc9bc2c0a0cb58e30ad5433ece6332"
ROOT_COMMIT = "d2b00336d621722fc25e7052883b79184b6736b5"
TAG = "v1.1.0"
CASE_ID = "G2 — GHSV sweep_1000"
RESOLUTION = "publication"
PACKAGES = (
    "pymrm",
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "h5py",
    "openpyxl",
    "numba",
    "llvmlite",
    "pytest",
)
ZERO_P0 = {"P0_H2": 0.0, "P0_N2": 0.0, "P0_NH3": 0.0}
# First pseudo-time steps of the isothermal no-membrane runs, each with why it is there.
ISOTHERMAL_STARTS = (
    (
        None,
        "the paper pipeline's cold start, settings.DT_INIT_1D (the pipeline itself solves "
        "only non-isothermal cases)",
    ),
    (
        1e-3,
        "the start of the group's own isothermal path, the Rossetti validation: "
        "ROSSETTI_DT_INIT (src/reactor/paper/validation.py:55, :155)",
    ),
    (1e-2, "one decade larger, to show whether the outcome depends on the start alone"),
)
# How the build lane reads T08.A61 on `main`; the verdict on that reading is the design lane's.
A61_READING = {
    "criterion": "its own regression reference reproduced within the group's regression "
    "tolerance; one-solve wall time recorded; PyMRM version recorded (spec §9 T08.A61)",
    "reading": "on main the group's regression reference is its pytest suite, tests/ (6 modules, "
    "72 tests); the group's regression tolerance is each test's own assertion tolerance (e.g. "
    "rtol=1e-12 on the 1D membrane-coupling conservation identity, test_1d_models.py:41, :98). "
    "Reproduced means the suite passes in the separate environment. main has no stored-field "
    "regression harness (no tests/regression_test.py, no regression_reference.npz).",
    "observations": [
        "On a fresh clone 3 of the 72 tests skip by their own skipif guards because they read "
        "data that is generated or archived, not shipped: the publication-tier closure fit "
        "results/paper/publication/screened_cp_fit.json (written by the 2D publication sweep) "
        "and the earlier study's archive Dataset_paper/ (git-ignored). See group_test_suite.",
        "No test in the suite solves a full reactor or compares a solved field with a stored "
        "one; the solved-case reference is the published dataset (4TU, in curation) with its "
        "SHA-256 manifest and reactor.paper.dataset.verify. Whether A61 needs that comparison "
        "is for the design lane.",
    ],
}
# Recorded as Frank's statements (2026-10-01, docs/T08_DECISIONS.md, brief T08-W3.2-redo), with
# the pointers he gave; `quoted_lines` carries the cited lines verbatim from the pinned commit.
FRANK_STATEMENTS = [
    {
        "statement": "the suite is 6 modules, 72 tests (test_1d_models, test_archive, "
        "test_cp_closure, test_dataset, test_paper_pipeline, test_validation)",
        "pointers": ["tests/"],
    },
    {
        "statement": "lambda_mem is evaluated at T at every call site",
        "pointers": [
            "src/reactor/membrane_reactor_1d.py:688",
            "src/reactor/membrane_reactor_1d_corrected.py:866",
            "src/reactor/membrane_reactor.py:2073",
            "src/reactor/membrane_reactor.py:2077",
        ],
    },
    {
        "statement": "the 52-case publication sweep is non-isothermal, with per-case convergence "
        "certificates and element_balance_ok in each kpis.json",
        "pointers": [],
        "note": "no pointer given; the record's own run goes through the same run_case_1d path",
    },
    {
        "statement": "lambda(q) is omitted deliberately: Weisz-Prater scan worst Phi_WP 0.099, "
        "nominal 0.0008; paper Fig. 2",
        "pointers": ["validation/weisz_prater_scan.json", "paper Fig. 2"],
        "note": "a pipeline output, not tracked: reactor.paper.validation.weisz_prater_scan "
        "writes it under the results cache (validation.py:266-268, :302-319)",
    },
    {
        "statement": "K_NH3 = 7000 cal/mol (29 288 J/mol) in the code is likely right and "
        "Gargiulo et al. 2025 Table 1's 29 228 J/mol a transposition (0.35 % relative effect "
        "at Rossetti Test 1); being checked against Rossetti et al. 2006",
        "pointers": ["src/reactor/ammonia_synthesis_kinetics.py (K_NH3)"],
    },
    {
        "statement": "genuine defect on main: the 'membrane-free' Rossetti validation sets "
        "cfg.Perm_NH3 (a removed field) and cfg.Nm (never read), so the P0_* permeances stay "
        "live; worst effect 0.26 % on outlet NH3; no reported number changes; logged by the "
        "group for its next version, not patched now because of the DOI/curation",
        "pointers": [
            "src/reactor/paper/validation.py:103",
            "src/reactor/config.py:51",
        ],
    },
]
SUPERSEDED = {
    "commit": "a6ee9efc85aee199b51e849467845b59bd5b1800",
    "line": "gitlab/master of the local clone ~/Codes/ammonia_synthesis_reactor: an abandoned "
    "line with no common ancestor with the released code",
    "disposition": "measurements dropped from this record; the C1 findings made on it are "
    "withdrawn (docs/T08_DECISIONS.md, 2026-10-01 CORRECTION). The withdrawn record is "
    "`git show 7c042a0:benchmarks/t08/v19/c1-reactor.json`.",
}
# Lines of the pinned commit behind Frank's statements, quoted verbatim into the record so the
# pointers can be checked without the clone (path, 1-based line numbers).
QUOTED_LINES = (
    ("src/reactor/membrane_reactor_1d.py", (688,)),
    ("src/reactor/membrane_reactor_1d_corrected.py", (866,)),
    ("src/reactor/membrane_reactor.py", (2073, 2077)),
    ("src/reactor/config.py", (51, 52, 54, 56, 71)),
    ("src/reactor/paper/validation.py", (103, 104)),
    ("src/reactor/membrane_reactor_1d.py", (172,)),
    ("src/reactor/membrane_reactor_1d_corrected.py", (179,)),
)


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def _export(repo: Path, commit: str, dest: Path) -> None:
    """Export ``commit`` of ``repo`` into ``dest`` with ``git archive`` (read-only on ``repo``)."""
    dest.mkdir(parents=True)
    tar_path = dest.parent / f"{dest.name}.tar"
    with tar_path.open("wb") as fh:
        subprocess.run(["git", "-C", str(repo), "archive", commit], check=True, stdout=fh)
    with tarfile.open(tar_path) as tar:
        tar.extractall(dest, filter="data")
    tar_path.unlink()


def _child_env() -> dict[str, str]:
    return {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def _run_suite(repo: Path) -> dict[str, Any]:
    """Collect, then run, the group's pytest suite in the clone; parse its summary lines."""
    base = [sys.executable, "-m", "pytest", "tests/", "-p", "no:cacheprovider"]
    collect = subprocess.run(
        [*base, "--collect-only", "-q"], cwd=repo, capture_output=True, text=True, env=_child_env()
    )
    node_ids = [ln for ln in collect.stdout.splitlines() if "::" in ln]
    per_module: dict[str, int] = {}
    for node in node_ids:
        module = node.split("::")[0].removeprefix("tests/").removesuffix(".py")
        per_module[module] = per_module.get(module, 0) + 1
    cmd = [*base, "-q", "-rs"]
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, env=_child_env())
    wall = time.perf_counter() - start
    lines = proc.stdout.strip().splitlines()
    summary = lines[-1] if lines else ""
    outcome_words = r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed)"
    counts = {word: int(num) for num, word in re.findall(outcome_words, summary)}
    skips = [ln.removeprefix("SKIPPED [1] ") for ln in lines if ln.startswith("SKIPPED")]
    return {
        "command": "python -m pytest tests/ -q -rs -p no:cacheprovider (cwd: the clone)",
        "collected": len(node_ids),
        "collected_per_module": dict(sorted(per_module.items())),
        "exit_code": proc.returncode,
        "summary_line": summary.strip("= "),
        "counts": counts,
        "skipped": skips,
        "wall_s": round(wall, 2),
    }


def _quote_lines(tree: Path) -> list[dict[str, Any]]:
    out = []
    for rel, numbers in QUOTED_LINES:
        text = (tree / rel).read_text(encoding="utf-8").splitlines()
        out.append({"path": rel, "lines": {str(n): text[n - 1].strip() for n in numbers}})
    return out


def _equilibrium_y_nh3(cfg: Any, feed: Any) -> float:
    """NH3 mole fraction where the group's own rate law vanishes, at ``T_ret_in`` and ``p_ret_out``.

    A limiting value for an isothermal run (the rate expression is zero at equilibrium); it uses
    the group's ``AmmoniaSynthesisKinetics`` (its ``K_eq`` and fugacity coefficients) unchanged.
    """
    np: Any = importlib.import_module("numpy")
    optimize: Any = importlib.import_module("scipy.optimize")
    kin_mod: Any = importlib.import_module("reactor.ammonia_synthesis_kinetics")
    # Shapes as MembraneReactor1D calls it: partial pressures (n, 3), temperatures (n,).
    temp = np.array([float(cfg.T_ret_in)])
    pres = float(cfg.p_ret_out)
    kinetics = kin_mod.AmmoniaSynthesisKinetics(list(cfg.species), rho_b=cfg.rho_b, rho_c=cfg.rho_c)
    nu = np.array([-3.0, -1.0, 2.0])  # H2, N2, NH3

    def rate(extent: float) -> float:
        flows = feed + nu * extent
        return float(kinetics(np.array([flows / flows.sum() * pres]), temp)[0, 2])

    extent = optimize.brentq(rate, 1e-12, float(feed[1]) * (1.0 - 1e-9), xtol=1e-16)
    flows = feed + nu * extent
    return float(flows[2] / flows.sum())


def _solve_case(
    case_id: str, overrides: dict[str, Any], dt_init_1d: float | None = None
) -> dict[str, Any]:
    """One cold ``run_case_1d`` of ``case_id`` with ``overrides`` applied to the group's config.

    ``dt_init_1d`` replaces the pipeline's ``settings.DT_INIT_1D`` (the cold solve's first
    pseudo-time step) for this call only; ``None`` keeps the pipeline's value.
    """
    np: Any = importlib.import_module("numpy")
    runner: Any = importlib.import_module("reactor.paper.runner")
    settings: Any = importlib.import_module("reactor.paper.settings")
    cases: Any = importlib.import_module("reactor.paper.cases")
    cache: Any = importlib.import_module("reactor.paper.cache")
    table = cases.load_case_table()
    row = table[table["Case_ID"] == case_id].iloc[0]
    built: dict[str, Any] = {}
    original = runner.build_config_1d
    original_dt_init = settings.DT_INIT_1D

    def build_with_overrides(*args: Any, **kwargs: Any) -> Any:
        config, design_meta = original(*args, **kwargs)
        for key, value in overrides.items():
            if not hasattr(config, key):
                raise KeyError(f"ReactorConfig has no field {key!r}")
            setattr(config, key, value)
        built["config"] = config
        return config, design_meta

    runner.build_config_1d = build_with_overrides
    if dt_init_1d is not None:
        settings.DT_INIT_1D = dt_init_1d
    t0 = time.perf_counter()
    try:
        rec = runner.run_case_1d(row, RESOLUTION, model=settings.MODEL_1D, force=True, verbose=0)
    except Exception as exc:  # recorded, not handled: the outcome is the finding
        return {
            "overrides": overrides,
            "dt_init_1d": float(dt_init_1d or original_dt_init),
            "outcome": "error",
            "exception": f"{type(exc).__name__}: {exc}",
            "wall_s": round(time.perf_counter() - t0, 3),
        }
    finally:
        runner.build_config_1d = original
        settings.DT_INIT_1D = original_dt_init
    wall = time.perf_counter() - t0
    cfg = built["config"]
    cert = rec.get("convergence_certificate", {})
    drift = cert.get("kpi_drift_rel") or {}
    result: dict[str, Any] = {
        "overrides": overrides,
        "dt_init_1d": float(dt_init_1d or original_dt_init),
        "outcome": "solved" if rec["status"] != "failed" else "failed",
        "status": rec["status"],
        "init": rec.get("init"),
        "runtime_s": round(float(rec["runtime_s"]), 3),
        "wall_s": round(wall, 3),
        "solve_converged": bool(rec["solve_converged"]),
        "solver_accepted": bool(rec["solver_accepted"]),
        "solver_acceptance_reason": rec["solver_acceptance_reason"],
        "solver_steps_attempted": int(rec["solver_steps_attempted"]),
        "steady_state_norm": float(rec["steady_state_norm"]),
        "steady_state_atol": float(cfg.steady_state_atol),
        "is_isothermal": bool(cfg.is_isothermal),
        "convergence_certificate": {
            "class": cert.get("class"),
            "certify_steps": cert.get("certify_steps"),
            "kpi_drift_ok": cert.get("kpi_drift_ok"),
            "kpi_drift_rel_max": max(drift.values()) if drift else None,
            "resume_rounds": cert.get("resume_rounds"),
        },
    }
    if rec["status"] == "failed":
        result["message"] = rec.get("message")
        return result
    flows = cache.load_flows(settings.case_cache_dir(RESOLUTION, settings.MODEL_1D, case_id))
    ret_ax = np.asarray(flows["flows_ret_ax"], dtype=float)
    perm_ax = np.asarray(flows["flows_perm_ax"], dtype=float)
    out_ret = ret_ax[-1, :]
    species = list(cfg.species)
    result.update(
        {
            "species": species,
            "retentate_in_mol_s": [float(v) for v in ret_ax[0, :]],
            "retentate_out_mol_s": [float(v) for v in out_ret],
            "y_NH3_retentate_out": float(out_ret[species.index("NH3")] / out_ret.sum()),
            "membrane_transfer_mol_s": [float(v) for v in np.asarray(flows["flows_ret_mem"])],
            "permeate_flow_change_mol_s": [float(v) for v in (perm_ax[-1, :] - perm_ax[0, :])],
            "kpis": {
                k: float(rec[k])
                for k in ("X_H2_out", "NH3_prod_out", "NH3_rec_out", "J_H2_avg", "DeltaT_max")
            },
            "element_balance_H_rel": float(rec["balance_H_rel"]),
            "element_balance_N_rel": float(rec["balance_N_rel"]),
            "element_balance_ok": bool(rec["element_balance_ok"]),
            "equilibrium_y_NH3_at_T_in_p_out": (
                _equilibrium_y_nh3(cfg, ret_ax[0, :]) if cfg.is_isothermal else None
            ),
        }
    )
    return result


def _worker(tree: Path, case_id: str, jobs: list[dict[str, Any]]) -> int:
    """Run ``jobs`` (each ``{"overrides": ..., "repeats": n}``) against ``tree``; print JSON."""
    sys.path[:0] = [str(tree / "src"), str(tree)]
    reactor_pkg: Any = importlib.import_module("reactor")
    module_file = Path(reactor_pkg.__file__).resolve()
    if tree.resolve() not in module_file.parents:
        raise RuntimeError(f"reactor imported from {module_file}, not from {tree}")
    cases: Any = importlib.import_module("reactor.paper.cases")
    settings: Any = importlib.import_module("reactor.paper.settings")
    table = cases.load_case_table()
    row = table[table["Case_ID"] == case_id].iloc[0]
    case = {k: (v.item() if hasattr(v, "item") else v) for k, v in row.to_dict().items()}
    res = settings.resolution(RESOLUTION)
    results = [
        [
            _solve_case(case_id, job["overrides"], job.get("dt_init_1d"))
            for _ in range(job["repeats"])
        ]
        for job in jobs
    ]
    print(
        json.dumps(
            {
                "case": case,
                "grid": {"num_z": res.num_z},
                "solver_1d": dict(settings.SOLVER_1D),
                "dt_init_1d": settings.DT_INIT_1D,
                "results": results,
            }
        )
    )
    return 0


def _run_worker(tree: Path, case_id: str, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Run ``jobs`` against ``tree`` in a fresh interpreter."""
    proc = subprocess.run(
        [sys.executable, __file__, "--worker", str(tree), case_id, json.dumps(jobs)],
        capture_output=True,
        text=True,
        env=_child_env(),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"1D worker failed on {tree}:\n{proc.stderr[-4000:]}")
    return dict(json.loads(proc.stdout.strip().splitlines()[-1]))


def _summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    solved = [r for r in runs if r["outcome"] == "solved"]
    out: dict[str, Any] = {"repeats": len(runs), "result": runs[0]}
    if solved:
        out["runtime_s"] = [r["runtime_s"] for r in solved]
        out["runtime_s_median"] = statistics.median(r["runtime_s"] for r in solved)
        out["wall_s"] = [r["wall_s"] for r in solved]
        out["wall_s_median"] = statistics.median(r["wall_s"] for r in solved)
        out["repeat_outlet_identical"] = all(
            r["retentate_out_mol_s"] == solved[0]["retentate_out_mol_s"] for r in solved
        )
    return out


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--worker"]:
        return _worker(Path(argv[1]), argv[2], json.loads(argv[3]))
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--group-repo", type=Path, required=True)
    parser.add_argument("--commit", default=PINNED_COMMIT)
    parser.add_argument("--case-id", default=CASE_ID)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    repo: Path = args.group_repo.resolve()
    head = _git(repo, "rev-parse", "HEAD")
    commit = _git(repo, "rev-parse", args.commit)
    if head != commit:
        raise SystemExit(f"the clone is at {head}, not at the pinned {commit}")
    status_before = _git(repo, "status", "--porcelain")
    tag_commit = _git(repo, "rev-parse", f"{TAG}^{{commit}}")
    record: dict[str, Any] = {
        "record": "t08-v19-c1-reactor",
        "version": 2,
        "assertions": ["T08.A61", "Q6"],
        "status": "measured",
        "judged": False,
        "group_repository": {
            "local_path": str(repo),
            "remotes": sorted(set(_git(repo, "remote", "-v").split("\n"))),
            "branch": _git(repo, "branch", "--show-current"),
            "on_remote_branches": sorted(
                b.strip() for b in _git(repo, "branch", "-r", "--contains", commit).split("\n")
            ),
            "commit": commit,
            "commit_date": _git(repo, "log", "-1", "--format=%cI", commit),
            "commit_subject": _git(repo, "log", "-1", "--format=%s", commit),
            "root_commits": _git(repo, "rev-list", "--max-parents=0", commit).split("\n"),
            "commit_count": int(_git(repo, "rev-list", "--count", commit)),
            "tag": TAG,
            "tag_commit": tag_commit,
            "describe": _git(repo, "describe", "--tags", commit),
            "files_changed_tag_to_commit": _git(
                repo, "diff", "--name-only", tag_commit, commit
            ).split("\n"),
            "worktree_clean_before": status_before == "",
        },
        "environment": {
            "kind": "separate venv outside this repository (python3 -m venv; pip install -e "
            "'.[test]' in the clone), never the project .venv",
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "threads": {
                k: os.environ.get(k)
                for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
            },
            "packages": {p: importlib.metadata.version(p) for p in PACKAGES},
            "installed_reactor": {
                "distribution": "ammonia-synthesis-reactor",
                "version": importlib.metadata.version("ammonia-synthesis-reactor"),
            },
            "pymrm_licence": str(importlib.metadata.metadata("pymrm").get("License", "")).split(
                "\n"
            )[0],
        },
    }
    if record["group_repository"]["root_commits"] != [ROOT_COMMIT]:
        raise SystemExit(f"unexpected root commit(s): {record['group_repository']['root_commits']}")

    record["group_test_suite"] = _run_suite(repo)
    record["group_repository"]["worktree_clean_after"] = _git(repo, "status", "--porcelain") == ""

    with tempfile.TemporaryDirectory(prefix="t08-w32r-") as tmp:
        tree = Path(tmp) / "tree"
        _export(repo, commit, tree)
        project = tomllib.loads((tree / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        licence_files = sorted(
            p.name for p in tree.iterdir() if p.name.upper().startswith(("LICEN", "COPYING"))
        )
        record["group_repository"].update(
            {
                "licence_file": licence_files,
                "licence_file_first_line": (tree / licence_files[0])
                .read_text(encoding="utf-8")
                .splitlines()[0]
                if licence_files
                else None,
                "pyproject_license": project.get("license"),
                "pyproject_version": project.get("version"),
                "pyproject_pymrm_requirement": next(
                    d for d in project["dependencies"] if d.startswith("pymrm")
                ),
            }
        )
        record["quoted_lines"] = _quote_lines(tree)

        n = args.repeats
        out = _run_worker(
            tree,
            args.case_id,
            [
                {"overrides": {}, "repeats": n},
                {"overrides": dict(ZERO_P0), "repeats": 1},
                *(
                    {
                        "overrides": {**ZERO_P0, "is_isothermal": True},
                        "repeats": 1,
                        "dt_init_1d": dt,
                    }
                    for dt, _why in ISOTHERMAL_STARTS
                ),
            ],
        )
    configured = (
        f"reactor.paper.runner.run_case_1d(row, {RESOLUTION!r}, model='1d', force=True): "
        "build_config_1d (num_z of the tier, settings.SOLVER_1D, TRACE_NH3), cold start "
        "solve(dt_init=settings.DT_INIT_1D), solver_acceptance, the KPI-drift certificate with "
        "certify-and-resume, check_element_balance; cache written to a temporary export"
    )
    record["one_1d_solve"] = {
        "model": "reactor.MembraneReactor1D (reactor.membrane_reactor_1d, paper model '1d')",
        "case_table": "data/inputs/cases_to_run.xlsx",
        "case": out["case"],
        "resolution": RESOLUTION,
        "grid": out["grid"],
        "solver_1d": out["solver_1d"],
        "dt_init_1d": out["dt_init_1d"],
        "configured_by": configured,
        "timing_fields": "runtime_s is the group's own runtime_s (the cold solve only); wall_s is "
        "the whole run_case_1d call (construction, solve, certificate, cache write)",
        "non_isothermal": _summary(out["results"][0]),
    }
    record["no_membrane"] = {
        "configuration": "P0_H2 = P0_N2 = P0_NH3 = 0 (the Arrhenius pre-factors of "
        "ReactorConfig; Perm_NH3 is a removed field): no species crosses the membrane. "
        "Non-isothermal: the permeate tube remains a heat-exchange surface; isothermal: "
        "is_isothermal = True also removes that coupling",
        "non_isothermal": _summary(out["results"][1]),
        "isothermal_by_start": [
            {"start": why, **_summary(runs)}
            for (_dt, why), runs in zip(ISOTHERMAL_STARTS, out["results"][2:], strict=True)
        ],
    }
    record["a61_reading"] = A61_READING
    record["frank_statements"] = FRANK_STATEMENTS
    record["superseded"] = SUPERSEDED
    args.out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
