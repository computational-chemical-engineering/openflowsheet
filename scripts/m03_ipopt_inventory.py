"""[A10] inventory of the optional general-NLP path's binaries (M03 WO-6; specification §9, G-A10).

The M03 NLP path (ADR 0032) loads binary closures the default install does not: Ipopt with its
linear solver, ordering libraries, BLAS/LAPACK and Fortran runtime; cyipopt's extension; and
PyNumero's ASL library. This script records **every object a solve actually maps**, not what a
package manager says it installed: a child interpreter of the audited environment imports every
`openflowsheet` module and the NLP stack, solves NLP-1 (specification §8.1) through the gray-box
adapter `openflowsheet.studies.nlp.greybox` and cyipopt, with `casadi.nlpsol` replaced by a function
that raises, and reports `/proc/self/maps`. It does so in both import orders, because which copy of
a shared runtime wins can depend on the order. WO-6 measured the audit on a two-variable stand-in
gray box before the adapter existed (`--workload stand-in` reproduces that record); audit §9 item 1
asked WO-8 to repeat it with NLP-1, which is the default.

Each mapped ELF object is recorded with its SHA-256, size, SONAME and `DT_NEEDED` list, the package
that owns it, and its licence: read from a notice file the package ships (or, where a package ships
none, from the upstream source its own recipe names and hashes — the build script fetches it), or
recorded `unresolved`. As in `scripts/p03_binary_inventory.py`, whose helpers this reuses, a
measured fact, a declared licence and an inferred attribution are kept apart, and a licence is never
filled in from knowledge of the upstream project.

The gate items it measures (specification §9): G1 the inventory; G2 no object from the CasADi
wheel's METIS closure (derived from that wheel's own `DT_NEEDED` graph, ADR 0006 D1.5) and no
`casadi.nlpsol` call; G3 every `METIS_` exporter is METIS 5 by ADR 0006 D2.1's symbol test; G4 no
HSL object and Ipopt's own banner naming MUMPS; G5 the licence findings; G6 `pyomo` and `cyipopt`
absent from the default install's requirements. G7 and G8 are judged in `docs/m03-ipopt-audit.md`.

Usage (any Python 3.13 with the standard library; needs objdump, nm and dpkg-query)::

    python scripts/m03_ipopt_inventory.py --env .venv-nlp            # writes the inventory
    python scripts/m03_ipopt_inventory.py --env .venv-nlp --check    # regenerates and compares
    python scripts/m03_ipopt_inventory.py --env .venv-nlp --workload stand-in --check

The environment is built by `scripts/build-m03-ipopt-env.sh`. `--check` exits 0 iff the regenerated
record equals the committed one; objects of the host platform (glibc, owned by a dpkg package) are
compared by path and package only, and a changed hash there is printed as drift, not a failure: the
platform is not part of the route. Exit status of a write is 0 iff G1–G6 all pass.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FORMAT = "m03-ipopt-inventory-v1"
DEFAULT_OUT = ROOT / "benchmarks" / "m03" / "ipopt-inventory-x86_64.json"
LOCKS = {
    "conda": ROOT / "benchmarks" / "m03" / "nlp-conda-explicit.txt",
    "pip": ROOT / "benchmarks" / "m03" / "nlp-pip.lock",
    "build": ROOT / "benchmarks" / "m03" / "nlp-build-conda-explicit.txt",
}
A30_SUMMARY = ROOT / "docs" / "t08-a30" / "t08-a30-x86_64.json"
SITE = "lib/python3.13/site-packages"
PYNUMERO_ASL = "share/pyomo/lib/libpynumero_ASL.so"
#: The child's solve: spec §8.1's NLP-1 through the adapter (audit §9 item 1), or WO-6's stand-in.
WORKLOADS = ("nlp-1", "stand-in")
RECIPE_NOTICES = "share/m03-ipopt-notices"

# Specification §9 G2: what a mapped path under the CasADi package may not name.
G2_FORBIDDEN = re.compile(r"ipopt|mumps|metis|coinmumps|coinmetis", re.IGNORECASE)
# Specification §9 G4: HSL routines Ipopt can use, as Fortran or C entry points.
HSL_SYMBOL = re.compile(r"^_?(ma27|ma57|ma77|ma86|ma97)", re.IGNORECASE)
# Ipopt's own (EPL) wrapper classes for those routines, `Ipopt::Ma27TSolverInterface` and so on,
# which call function pointers its loader resolves from the `hsllib` library at run time. They are
# not HSL code; they are recorded so that the distinction is visible rather than assumed.
IPOPT_HSL_INTERFACE = re.compile(r"^_ZN5Ipopt\d+Ma(27|57|77|86|97)\w*SolverInterface")

# Notices this audit meets that `p03_binary_inventory.LICENSE_PATTERNS` does not name. Identifiers
# are informational; the category below rests on the declared licence, the presence of a notice
# and the restrictive patterns, exactly as P03 and T08.A30 judged.
EXTRA_PATTERNS: tuple[tuple[str, str], ...] = (
    ("GCC-exception-3.1", r"GCC RUNTIME LIBRARY EXCEPTION"),
    ("Apache-2.0", r"Apache License, Version 2\.0"),
    ("PSF-2.0", r"PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2"),
    ("LLVM-exception", r"LLVM Exceptions to the Apache 2\.0 License"),
    ("MIT", r"Permission is hereby granted, free of charge, to any person obtaining"),
    (
        "ISC-style",
        r"Permission to use, copy, modify, and(/or)? distribute this\s+software for any\s+purpose"
        r" with or without fee is hereby granted",
    ),
    (
        "SMLNJ-style",
        r"Permission to use, copy, modify, and distribute this software\s+and\s+its\s+documentation"
        r"\s+for any purpose and without fee is hereby granted",
    ),
    ("blessing", r"May you do good and not evil"),
    ("public-domain", r"(is|totally) (with)?in the public domain"),
)

# A child interpreter of the audited environment does what the NLP path does. argv: the project's
# `src`, the import order, the Ipopt log path, the workload (`stand-in` or `nlp-1`). It prints one
# JSON line.
_WORKLOAD = r"""
import importlib, json, pkgutil, sys
sys.path.insert(0, sys.argv[1])
order, log, workload = sys.argv[2], sys.argv[3], sys.argv[4]
# The two bindings of the `server` extra, which this environment does not install.
SERVER = ("openflowsheet.application.bindings.http", "openflowsheet.application.bindings.mcp")
skipped = []
def project():
    import openflowsheet
    for module in pkgutil.walk_packages(openflowsheet.__path__, "openflowsheet."):
        try:
            importlib.import_module(module.name)
        except ModuleNotFoundError:
            if not module.name.startswith(SERVER):
                raise
            skipped.append(module.name)
def nlp():
    import cyipopt, pyomo.environ  # noqa: F401
(nlp, project)[0 if order == "nlp-first" else 1]()
(nlp, project)[1 if order == "nlp-first" else 0]()

import casadi
nlpsol_calls = []
def refuse(*args, **kwargs):
    nlpsol_calls.append(str(args[:2]))
    raise RuntimeError("casadi.nlpsol is not on the NLP path (ADR 0006 D2.4)")
casadi.nlpsol = refuse

import numpy as np, scipy.sparse as sparse, pyomo.environ as pyo, cyipopt, pyomo.version
from pyomo.contrib.pynumero.interfaces.external_grey_box import (
    ExternalGreyBoxBlock, ExternalGreyBoxModel)
from pyomo.contrib.pynumero.asl import AmplInterface

def stand_in():
    # min a + 2 b subject to a b = 1, a, b >= 0.1: the minimizer is (sqrt 2, 1/sqrt 2).
    z = casadi.SX.sym("z", 2)
    residual = casadi.Function("r", [z], [z[0] * z[1] - 1.0])
    jacobian = casadi.Function("j", [z], [casadi.jacobian(z[0] * z[1] - 1.0, z)])
    class Product(ExternalGreyBoxModel):
        def input_names(self): return ["a", "b"]
        def equality_constraint_names(self): return ["ab"]
        def output_names(self): return []
        def set_input_values(self, values): self._z = np.asarray(values, dtype=float)
        def evaluate_equality_constraints(self): return np.asarray(residual(self._z)).ravel()
        def evaluate_jacobian_equality_constraints(self):
            return sparse.coo_matrix(
                (np.asarray(jacobian(self._z)).ravel(), ([0, 0], [0, 1])), shape=(1, 2))
    m = pyo.ConcreteModel()
    m.box = ExternalGreyBoxBlock(external_model=Product())
    for name in ("a", "b"):
        m.box.inputs[name].value = 2.0
        m.box.inputs[name].setlb(0.1)
    m.objective = pyo.Objective(expr=m.box.inputs["a"] + 2.0 * m.box.inputs["b"])
    options = {"linear_solver": "mumps", "hessian_approximation": "limited-memory",
               "limited_memory_max_history": 6, "tol": 1e-10, "print_level": 0,
               "output_file": log, "file_print_level": 5}
    result = pyo.SolverFactory("cyipopt", options=options).solve(m)
    a, b = pyo.value(m.box.inputs["a"]), pyo.value(m.box.inputs["b"])
    return (str(result.solver.termination_condition),
            max(abs(a - 2 ** 0.5), abs(b - 0.5 ** 0.5)),
            options | {"output_file": "<log>"})
def nlp_1():
    # Spec §8.1's NLP-1 through the adapter (WO-8), with §8.4's options. Only Ipopt's log file is
    # added, so that its banner shows the linear solver it ran (G4); print options change no
    # numerics. The error is the decisions' scaled distance from the reference optimum.
    sys.path.insert(0, sys.argv[5])
    from m03_support import flowsheet, nlp_formulation, number, reference
    from openflowsheet.studies.nlp import closure, greybox
    typed = greybox._typed_options
    greybox._typed_options = lambda: typed() | {"output_file": log, "file_print_level": 5}
    formulation = nlp_formulation()
    report = closure.optimize(formulation, flowsheet({}))
    optimum = reference()["nlp"]["NLP-1"]["reference_optimum"]
    errors = [
        abs(start["final_decisions"][d.parameter_id] - number(optimum[d.parameter_id])) / d.scale
        for start in report.as_document()["starts"]
        for d in formulation.decisions
    ]
    return report.status, max(errors), dict(closure.IPOPT_OPTIONS) | {"output_file": "<log>"}

if workload == "nlp-1":
    termination, max_error, options = nlp_1()
else:
    termination, max_error, options = stand_in()
banner = [line.strip() for line in open(log, encoding="utf-8") if "This is Ipopt version" in line]
mapped = set()
with open("/proc/self/maps", encoding="utf-8") as handle:
    for line in handle:
        fields = line.rstrip("\n").split(None, 5)  # the path may contain spaces
        if len(fields) == 6 and fields[5].startswith("/") and not fields[5].endswith(" (deleted)"):
            mapped.add(fields[5])
print(json.dumps({
    # The stand-in record predates this field, and stays byte-identical without it.
    **({} if workload == "stand-in" else {"workload": workload}),
    "termination": termination,
    "max_error": max_error,
    "ipopt_banner": banner,
    "options": options,
    "pynumero_asl": AmplInterface.libname,
    "nlpsol_calls": nlpsol_calls,
    "skipped_modules": skipped,
    "versions": {"cyipopt": cyipopt.__version__, "pyomo": pyomo.version.version,
                 "casadi": casadi.__version__, "numpy": np.__version__},
    "mapped": sorted(mapped),
}))
"""

# Where Pyomo would look for libpynumero_ASL in this environment if PYOMO_CONFIG_DIR were not set.
_DEFAULT_LOOKUP = r"""
from pyomo.common.fileutils import find_library
print(find_library("pynumero_ASL") or "")
"""


def _p03() -> Any:
    spec = importlib.util.spec_from_file_location(
        "p03_binary_inventory", Path(__file__).resolve().parent / "p03_binary_inventory.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P03 = _p03()


def _child_environment(env: Path, *, pyomo_config: bool) -> dict[str, str]:
    environment = {
        "HOME": os.environ.get("HOME", "/nonexistent"),
        "PATH": f"{env}/bin:/usr/bin:/bin",
        "PYTHONNOUSERSITE": "1",
        "LC_ALL": "C.UTF-8",
        # MUMPS/OpenBLAS under LLVM OpenMP are bitwise reproducible run to run only single-
        # threaded (WO-8's measurement); the recorded `max_error` is compared bit for bit.
        "OMP_NUM_THREADS": "1",
    }
    if pyomo_config:
        environment["PYOMO_CONFIG_DIR"] = str(env / "share" / "pyomo")
    return environment


def run_workload(env: Path, order: str, workload: str) -> dict[str, Any]:
    """One NLP-path solve in a fresh interpreter of `env`, from an empty working directory."""
    with tempfile.TemporaryDirectory() as scratch:
        completed = subprocess.run(
            [str(env / "bin" / "python"), "-I", "-c", _WORKLOAD, str(ROOT / "src"), order,
             f"{scratch}/ipopt.log", workload, str(ROOT / "tests")],
            capture_output=True, text=True, check=False, cwd=scratch,
            env=_child_environment(env, pyomo_config=True),
        )  # fmt: skip
    if completed.returncode != 0:
        raise SystemExit(f"the NLP workload ({order}) failed:\n{completed.stderr[-3000:]}")
    return dict(json.loads(completed.stdout.strip().splitlines()[-1]))


def default_lookup(env: Path) -> str:
    """The libpynumero_ASL Pyomo finds when the route's PYOMO_CONFIG_DIR is not set."""
    with tempfile.TemporaryDirectory() as scratch:
        completed = subprocess.run(
            [str(env / "bin" / "python"), "-I", "-c", _DEFAULT_LOOKUP],
            capture_output=True, text=True, check=False, cwd=scratch,
            env=_child_environment(env, pyomo_config=False),
        )  # fmt: skip
    found = completed.stdout.strip()
    home = os.environ.get("HOME")
    if home and found.startswith(home + "/"):
        found = "~" + found[len(home) :]
    return found.replace(str(env), "$ENV") or "(none)"


# ---- ownership ---------------------------------------------------------------------------------


def conda_packages(env: Path) -> list[dict[str, Any]]:
    packages = []
    for meta in sorted((env / "conda-meta").glob("*.json")):
        record = json.loads(meta.read_text(encoding="utf-8"))
        packages.append(record)
    return packages


def _relative_pkgs(path: Path, extracted: Path) -> str:
    return f"$PKGS/{extracted.name}/{path.relative_to(extracted)}"


_NOTICE_NAME = re.compile(r"(LICEN[CS]E|COPYING|NOTICE|COPYRIGHT|EXCEPTION)", re.IGNORECASE)


def _read_notice(path: Path, label: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    identified = P03.identify_notice(text)
    identifiers = identified["declared_identifiers"] + [
        name for name, pattern in EXTRA_PATTERNS if re.search(pattern, text, re.S)
    ]
    return {
        "path": label,
        "sha256": P03.sha256_of(path),
        "identifiers": sorted(set(identifiers)),
        "restrictive_clauses": identified["restrictive_clauses"],
    }


def conda_notices(env: Path, record: dict[str, Any]) -> list[dict[str, Any]]:
    """Notices a conda package ships (`info/licenses`, and licence files among its own files), and
    those read from an upstream source its recipe names and hashes (fetched by the build script)."""
    notices = []
    extracted = Path(record.get("extracted_package_dir") or "")
    licenses = extracted / "info" / "licenses"
    if licenses.is_dir():
        for path in sorted(p for p in licenses.rglob("*") if p.is_file()):
            notices.append(_read_notice(path, _relative_pkgs(path, extracted)))
    for name in record.get("files", []):
        if name.startswith("share/licenses/") or (
            _NOTICE_NAME.search(Path(name).name) and not name.startswith(("include/", "lib/"))
        ):
            path = env / name
            if path.is_file():
                notices.append(_read_notice(path, f"$ENV/{name}"))
    return notices


# Objects whose own notice the package does not ship correctly, so that the package-level notices
# would attribute the wrong text (or none) to them. Each is read instead from the upstream source
# the package's recipe names and hashes, fetched by the build script into RECIPE_NOTICES/<key>.
OBJECT_NOTICES: tuple[tuple[str, str, str], ...] = (
    ("libsqlite3", r"^libsqlite3\.so", "libsqlite ships no notice"),
    (
        "libuuid",
        r"^libuuid\.so",
        "libuuid ships util-linux's top-level COPYING (GPL-2.0, util-linux's default for code "
        "without its own licence); libuuid carries its own",
    ),
    (
        "libpord",
        r"^libpord_seq\.so",
        "MUMPS's LICENSE excludes PORD and points at PORD/README, which mumps-seq does not ship",
    ),
)


def object_notices(env: Path, name: str) -> tuple[list[dict[str, Any]], str] | None:
    for key, pattern, reason in OBJECT_NOTICES:
        if re.match(pattern, name):
            directory = env / RECIPE_NOTICES / key
            if not directory.is_dir():
                return [], reason
            source = (directory / "SOURCE").read_text(encoding="utf-8").strip()
            rows = []
            files = (p for p in directory.iterdir() if p.is_file() and p.name != "SOURCE")
            for path in sorted(files):
                row = _read_notice(path, f"$ENV/{path.relative_to(env)}")
                row["source"] = source
                rows.append(row)
            return rows, reason
    return None


def judge(declared: str | None, notices: list[dict[str, Any]]) -> str:
    """The licence category of a conda-owned or built object (spec §9 G5's classes).

    `restrictive` if any notice restricts; `unresolved` if no notice was read (a declared licence
    alone is not a notice: blueprint §15, "unknown rights are not assumed redistributable");
    otherwise by the declared expression — `gpl-with-gcc-runtime-exception` (the GCC runtime,
    R-135), `lgpl` (ADR 0006 Q1), `gpl-family`, or `identified` — except that a notice reading as
    the GPL (without an LGPL text or the GCC exception) under a non-GPL declaration is
    `unresolved`.
    """
    if any(notice["restrictive_clauses"] for notice in notices):
        return "restrictive"
    if not notices:
        return "unresolved"
    read = sorted({name for notice in notices for name in notice["identifiers"]})
    text = declared or " ".join(read)
    if re.search(r"GCC-exception", text) or (
        "GCC-exception-3.1" in read and re.search(r"\bGPL", text)
    ):
        return "gpl-with-gcc-runtime-exception"
    category: str = P03.licence_category(text)
    # A shipped GPL text the declaration does not account for is a conflict, not a reading.
    gpl_read = [n for n in read if n.startswith("GPL")] and not any(
        n.startswith("LGPL") or n == "GCC-exception-3.1" for n in read
    )
    if gpl_read and category not in {"gpl-family", "lgpl"}:
        return "unresolved"
    return category


def _spdx_tokens(expression: str | None) -> set[str]:
    if not expression:
        return set()
    tokens = re.split(r"\s+(?:AND|OR|WITH)\s+|[()]", expression)
    return {token.strip() for token in tokens if token.strip()}


# Licence families whose texts state their version in a header the patterns read, so that a
# declared version the notice does not carry is a measured conflict. The BSD texts do not qualify:
# P03's 2-clause pattern matches every BSD text.
_VERSIONED_FAMILIES = ("EPL", "CPL", "GPL", "LGPL", "Apache", "MPL")


def declared_vs_read(declared: str | None, notices: list[dict[str, Any]]) -> list[str]:
    """Declared SPDX identifiers that a read notice identifies as a different version of the same
    licence family (for example a package declaring EPL-1.0 that ships the EPL-2.0 text)."""
    read = {name for notice in notices for name in notice["identifiers"]}
    conflicts = []
    for token in sorted(_spdx_tokens(declared)):
        version = re.sub(r"(-only|-or-later|\+)$", "", token)
        family = re.sub(r"-\d.*$", "", version)
        if family not in _VERSIONED_FAMILIES:
            continue
        same_family = {name for name in read if re.sub(r"-\d.*$", "", name) == family}
        if same_family and version not in read:
            conflicts.append(f"declared {token}, notice reads {', '.join(sorted(same_family))}")
    return conflicts


def substitute_prefix(data: bytes, placeholder: bytes, prefix: bytes) -> bytes:
    """conda's binary relocation: in each NUL-terminated string containing the placeholder, the
    placeholder becomes the prefix and the string is NUL-padded back to its original length."""
    out = bytearray()
    position = 0
    while (start := data.find(placeholder, position)) != -1:
        begin = data.rfind(b"\0", 0, start) + 1
        end = data.find(b"\0", start)
        end = len(data) if end == -1 else end
        string = data[begin:end].replace(placeholder, prefix)
        out += data[position:begin] + string + b"\0" * (end - begin - len(string))
        position = end
    return bytes(out + data[position:])


def package_identity(
    env: Path, record: dict[str, Any], real: Path, installed: str
) -> dict[str, Any]:
    """The object's identity in its conda package, independent of where the environment lives.

    A file the package marks for binary prefix relocation (`file_mode: binary`) differs from the
    package's bytes only by the install prefix; its `sha256` is then the package file's, and the
    installed bytes are checked to be exactly that file relocated to this prefix. Any other file
    must be byte-identical to the package's record.
    """
    extracted = Path(record["extracted_package_dir"])
    relative = str(real.relative_to(env))
    paths = json.loads((extracted / "info" / "paths.json").read_text(encoding="utf-8"))
    entry = next(item for item in paths["paths"] if item["_path"] == relative)
    if entry.get("file_mode") == "binary" and entry.get("prefix_placeholder"):
        relocated = substitute_prefix(
            (extracted / relative).read_bytes(),
            entry["prefix_placeholder"].encode(),
            str(env).encode(),
        )
        return {
            "sha256": entry["sha256"],
            "prefix_relocated": True,
            "installed_equals_package_relocated": hashlib.sha256(relocated).hexdigest()
            == installed,
        }
    return {"installed_equals_package": entry["sha256"] == installed}


def platform_owner(path: str) -> dict[str, Any]:
    """The dpkg package owning a host object (the C library), with its copyright notice."""
    candidates = [path]
    if path.startswith("/usr/lib/"):
        candidates.append(path.removeprefix("/usr"))
    for candidate in candidates:
        completed = subprocess.run(
            ["dpkg-query", "-S", candidate], capture_output=True, text=True, check=False
        )
        if completed.returncode == 0 and completed.stdout.strip():
            package = completed.stdout.split(":", 1)[0].strip()
            version = subprocess.run(
                ["dpkg-query", "-W", "-f", "${Version}", package],
                capture_output=True, text=True, check=False,
            ).stdout.strip()  # fmt: skip
            copyright_file = Path("/usr/share/doc") / package / "copyright"
            notices = (
                [_read_notice(copyright_file, str(copyright_file))]
                if copyright_file.is_file()
                else []
            )
            return {"package": package, "version": version, "notices": notices}
    return {"package": None, "version": None, "notices": []}


# ---- ELF facts ---------------------------------------------------------------------------------


def undefined_symbols(path: Path) -> set[str]:
    completed = subprocess.run(
        ["nm", "-D", "--undefined-only", str(path)], capture_output=True, text=True, check=False
    )
    return {line.split()[-1] for line in completed.stdout.splitlines() if line.split()}


def elf_facts(path: Path) -> dict[str, Any]:
    defined = P03.defined_symbols(path)
    undefined = undefined_symbols(path)
    metis_defined = sorted(name for name in defined if name.startswith("METIS_"))
    return {
        "bytes": path.stat().st_size,
        "sha256": P03.sha256_of(path),
        "soname": P03._soname_of(path),
        "needed": P03.needed_of(path),
        "metis_exports": len(metis_defined),
        "metis_imports": sorted(name for name in undefined if name.startswith("METIS_")),
        "hsl_exports": sorted(name for name in defined if HSL_SYMBOL.match(name)),
        "hsl_imports": sorted(name for name in undefined if HSL_SYMBOL.match(name)),
        "ipopt_hsl_interface": any(IPOPT_HSL_INTERFACE.search(name) for name in defined),
        "_defined": defined,
    }


def is_elf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return bool(handle.read(4) == P03.ELF_MAGIC)
    except OSError:
        return False


# ---- the CasADi wheel's METIS closure (ADR 0006 D1.5), derived, not listed --------------------


def casadi_metis_closure(site: Path) -> list[str]:
    """Every ELF in the CasADi package that reaches a METIS 4 carrier through `DT_NEEDED`."""
    root = site / "casadi"
    objects = [p for p in sorted(root.rglob("*")) if p.is_file() and not p.is_symlink()]
    objects = [p for p in objects if is_elf(p)]
    by_name: dict[str, list[str]] = {}
    needed: dict[str, list[str]] = {}
    carriers = set()
    for path in objects:
        key = str(path.relative_to(site))
        for alias in {path.name, P03._soname_of(path)} - {None}:
            by_name.setdefault(str(alias), []).append(key)
        needed[key] = P03.needed_of(path)
        symbols = P03.defined_symbols(path)
        if "METIS_EstimateMemory" in symbols or "METIS_mCPartGraphKway" in symbols:
            carriers.add(key)
    for symlink in (p for p in root.rglob("*") if p.is_symlink()):
        target = str(symlink.resolve().relative_to(site.resolve()))
        by_name.setdefault(symlink.name, []).append(target)
    return sorted(key for key in needed if P03._closure_of([key], by_name, needed) & carriers)


# ---- the record ------------------------------------------------------------------------------


def _normalise(path: str, env: Path) -> str:
    return "$ENV/" + path[len(str(env)) + 1 :] if path.startswith(str(env) + "/") else path


def build_record(env: Path, workload: str) -> dict[str, Any]:
    env = env.resolve()
    site = env / SITE
    runs = {order: run_workload(env, order, workload) for order in ("project-first", "nlp-first")}
    mapped_sets = {order: set(run.pop("mapped")) for order, run in runs.items()}
    mapped = sorted(set().union(*mapped_sets.values()))
    elf_paths = [path for path in mapped if is_elf(Path(path))]

    packages = conda_packages(env)
    # A package that installs the file itself owns it; one that only installs a symlink to it
    # (`_openmp_mutex`'s libgomp.so.1 → llvm-openmp's libomp.so) does not.
    conda_owner: dict[str, dict[str, Any]] = {}
    for symlinks in (False, True):
        for record in packages:
            for name in record.get("files", []):
                if (env / name).is_symlink() == symlinks:
                    conda_owner.setdefault(os.path.realpath(env / name), record)
    pip_owner: dict[str, Any] = {}
    distributions = {
        dist.metadata["Name"].lower(): dist
        for dist in importlib.metadata.distributions(path=[str(site)])
    }
    for distribution in distributions.values():
        if (distribution.read_text("INSTALLER") or "").strip() == "conda":
            continue
        for entry in distribution.files or []:
            pip_owner.setdefault(
                os.path.realpath(str(distribution.locate_file(entry))), distribution
            )
    pip_rows: dict[str, dict[str, Any]] = {}

    built = json.loads((env / (PYNUMERO_ASL.removesuffix(".so") + ".build.json")).read_text())
    pyomo = distributions["pyomo"]
    metadata_file = next(e for e in pyomo.files or [] if str(e).endswith(".dist-info/METADATA"))
    pyomo_dist_info = Path(str(pyomo.locate_file(metadata_file))).parent
    pyomo_notices = [
        _read_notice(path, f"$ENV/{path.relative_to(env)}")
        for path in sorted(pyomo_dist_info.rglob("*"))
        if path.is_file() and _NOTICE_NAME.search(path.name)
    ]

    notices_cache: dict[str, list[dict[str, Any]]] = {}
    objects = []
    for path in elf_paths:
        real = os.path.realpath(path)
        facts = elf_facts(Path(real))
        defined = facts.pop("_defined")
        row: dict[str, Any] = {"path": _normalise(path, env), **facts}
        row["python_extension"] = any(name.startswith("PyInit_") for name in defined)
        row["loaded_in"] = sorted(order for order, paths in mapped_sets.items() if path in paths)
        if real == str(env / PYNUMERO_ASL):
            row["origin"] = "built: libpynumero_ASL (scripts/build-m03-ipopt-env.sh)"
            row["licence"] = {
                "declared": P03._declared_licence(pyomo),
                "source": "the Pyomo sources it is compiled from (pyomo dist-info notice)",
                "notices": pyomo_notices,
                "category": judge(P03._declared_licence(pyomo), pyomo_notices),
            }
            row["build_record_sha256"] = built["sha256"]
        elif real in conda_owner:
            record = conda_owner[real]
            if record["name"] not in notices_cache:
                notices_cache[record["name"]] = conda_notices(env, record)
            notices = notices_cache[record["name"]]
            row["origin"] = f"conda-forge: {record['name']}-{record['version']}-{record['build']}"
            row["licence"] = {
                "declared": record.get("license"),
                "source": "conda package notices (package-level: applied to each of its objects)",
                "notices": notices,
            }
            override = object_notices(env, Path(real).name)
            if override is not None:
                row["licence"]["package_notices"] = [notice["path"] for notice in notices]
                notices, reason = override
                row["licence"]["notices"] = notices
                row["licence"]["source"] = f"upstream source pinned by the recipe ({reason})"
            row["licence"]["category"] = judge(record.get("license"), notices)
            row["licence"]["declared_vs_read"] = declared_vs_read(record.get("license"), notices)
            row.update(package_identity(env, record, Path(real), row["sha256"]))
        elif real in pip_owner:
            distribution = pip_owner[real]
            name = distribution.metadata["Name"]
            if name not in pip_rows:
                pip_rows[name] = {
                    item["path"]: item for item in P03._distribution_objects(distribution, site)
                }
            relative = str(Path(real).relative_to(site.resolve()))
            attribution = pip_rows[name][relative]["attribution"]
            category = attribution["category"]
            disposition = None
            if (
                category == "gpl-family"
                and name.lower() in P03.ADR0006_A1_GCC_RUNTIME_DISTRIBUTIONS
                and attribution["licence"] == P03.ADR0006_A1_GCC_RUNTIME_LICENCE
            ):
                disposition = "ADR 0006 Amendment 1"
            row["origin"] = f"pypi: {name}-{distribution.version}"
            row["licence"] = {
                "declared": attribution["licence"],
                "source": attribution["source"],
                "notices": attribution["notices"],
                "category": category,
                "dispositioned_by": disposition,
            }
        elif not real.startswith(str(env) + "/"):
            owner = platform_owner(path)
            row["origin"] = f"platform: {owner['package']} {owner['version']}"
            row["licence"] = {
                "declared": None,
                "source": "dpkg copyright notice",
                "notices": owner["notices"],
                "category": "platform",
            }
        else:
            row["origin"] = "unknown"
            row["licence"] = {"declared": None, "notices": [], "category": "unresolved"}
        objects.append(row)

    by_path = {row["path"]: row for row in objects}
    # G2: the CasADi wheel's METIS closure, from its own DT_NEEDED graph, against what was mapped.
    closure = casadi_metis_closure(site)
    casadi_mapped = sorted(p for p in by_path if p.startswith(f"$ENV/{SITE}/casadi/"))
    g2: dict[str, Any] = {
        "casadi_objects_mapped": casadi_mapped,
        "forbidden_name_matches": [p for p in casadi_mapped if G2_FORBIDDEN.search(Path(p).name)],
        "casadi_metis_closure_size": len(closure),
        "casadi_metis_closure_mapped": sorted(
            set(closure) & {p.removeprefix(f"$ENV/{SITE}/") for p in casadi_mapped}
        ),
        "nlpsol_calls": {order: run["nlpsol_calls"] for order, run in runs.items()},
    }
    g2["pass"] = not (
        g2["forbidden_name_matches"]
        or g2["casadi_metis_closure_mapped"]
        or any(g2["nlpsol_calls"].values())
    )
    # G3: ADR 0006 D2.1's binary test on every mapped METIS_ exporter.
    probe = P03.ATTRIBUTION_PROBES[0]
    carriers = []
    for row in objects:
        if not row["metis_exports"]:
            continue
        defined = P03.defined_symbols(Path(os.path.realpath(row["path"].replace("$ENV", str(env)))))
        five = [name for name in probe["negative_symbols"] if name in defined]
        four = [name for name in probe["positive_symbols"] if name in defined]
        carriers.append(
            {
                "path": row["path"],
                "origin": row["origin"],
                "sha256": row["sha256"],
                "metis5_symbols_present": five,
                "metis4_symbols_present": four,
                "conclusion": "METIS 5.x" if five and not four else "not METIS 5",
                "needed_by": sorted(
                    other["path"]
                    for other in objects
                    if row["soname"] in other["needed"] or Path(row["path"]).name in other["needed"]
                ),
            }
        )
    importers = sorted(row["path"] for row in objects if row["metis_imports"])
    g3: dict[str, Any] = {
        "carriers": carriers,
        "objects_importing_metis_symbols": importers,
        "pass": all(item["conclusion"] == "METIS 5.x" for item in carriers),
    }
    # G4: no HSL object; Ipopt's own banner names the linear solver.
    banners = sorted({line for run in runs.values() for line in run["ipopt_banner"]})
    g4: dict[str, Any] = {
        "hsl_symbol_exporters": sorted(row["path"] for row in objects if row["hsl_exports"]),
        "hsl_symbol_importers": sorted(row["path"] for row in objects if row["hsl_imports"]),
        "ipopt_hsl_interface_objects": sorted(
            row["path"] for row in objects if row["ipopt_hsl_interface"]
        ),
        "hsl_named_objects": sorted(p for p in by_path if "hsl" in Path(p).name.lower()),
        "ipopt_banner": banners,
        "linear_solver_option": runs["project-first"]["options"]["linear_solver"],
    }
    g4["pass"] = (
        not g4["hsl_symbol_exporters"]
        and not g4["hsl_symbol_importers"]
        and not g4["hsl_named_objects"]
        and len(banners) == 1
        and "running with linear solver MUMPS" in banners[0]
    )
    # G5: licence findings over every non-platform object.
    findings = [
        {
            "path": row["path"],
            "origin": row["origin"],
            "category": row["licence"]["category"],
            "declared": row["licence"]["declared"],
            "dispositioned_by": row["licence"].get("dispositioned_by"),
        }
        for row in objects
        if row["licence"]["category"] in {"restrictive", "gpl-family", "unresolved"}
    ]
    mismatches = [
        {"path": row["path"], "origin": row["origin"], "conflict": conflict}
        for row in objects
        for conflict in row["licence"].get("declared_vs_read", [])
    ]
    g5: dict[str, Any] = {
        "findings": findings,
        "undispositioned": sorted(f["path"] for f in findings if not f["dispositioned_by"]),
        "declared_vs_read": mismatches,
    }
    g5["pass"] = not g5["undispositioned"]
    # G6: the default install's requirements name neither package.
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    requirement_sets = {"dependencies": project["dependencies"]} | {
        f"optional-dependencies.{key}": value
        for key, value in project.get("optional-dependencies", {}).items()
    }
    named = {
        where: sorted(text for text in texts if re.match(r"(?i)\s*(pyomo|cyipopt)\b", text))
        for where, texts in requirement_sets.items()
    }
    g6: dict[str, Any] = {
        "requirements_naming_pyomo_or_cyipopt": {k: v for k, v in named.items() if v},
        "nlp_extra_declared": "optional-dependencies.nlp" in requirement_sets,
    }
    g6["pass"] = all(
        where == "optional-dependencies.nlp" for where in g6["requirements_naming_pyomo_or_cyipopt"]
    )
    g1: dict[str, Any] = {
        "objects": len(objects),
        "distinct_sha256": len({row["sha256"] for row in objects}),
        "bytes": sum(row["bytes"] for row in objects),
        "unknown_origin": sorted(row["path"] for row in objects if row["origin"] == "unknown"),
        "conda_objects_not_matching_their_package": sorted(
            row["path"]
            for row in objects
            if row["origin"].startswith("conda-forge: ")
            and not (
                row.get("installed_equals_package") or row.get("installed_equals_package_relocated")
            )
        ),
        "import_orders_map_the_same_objects": len({frozenset(v) for v in mapped_sets.values()})
        == 1,
    }
    g1["pass"] = (
        not g1["unknown_origin"]
        and not g1["conda_objects_not_matching_their_package"]
        and g1["import_orders_map_the_same_objects"]
    )

    a30 = json.loads(A30_SUMMARY.read_text(encoding="utf-8"))
    a30_digests = {item["name"]: item["objects_digest"] for item in a30["distributions"]}
    pip_distributions = []
    for key, distribution in sorted(distributions.items()):
        installer = (distribution.read_text("INSTALLER") or "").strip()
        canonical = re.sub(r"[-_.]+", "-", key)
        compiled = sorted(
            f"{row['path']}\t{row['sha256']}\n"
            for row in P03._distribution_objects(distribution, site)
        )
        digest = hashlib.sha256("".join(compiled).encode()).hexdigest()
        pip_distributions.append(
            {
                "name": distribution.metadata["Name"],
                "version": distribution.version,
                "installer": installer,
                "compiled_objects": len(compiled),
                # T08.A30's per-distribution digest over its compiled objects' (path, sha256): equal
                # means the same binaries the default install's [A10] refresh audited.
                "objects_digest": digest,
                "same_objects_as_t08_a30": (
                    None if canonical not in a30_digests else digest == a30_digests[canonical]
                ),
            }
        )
    loaded_by_package: dict[str, int] = {}
    for row in objects:
        if row["origin"].startswith("conda-forge: "):
            loaded_by_package[row["origin"].removeprefix("conda-forge: ")] = (
                loaded_by_package.get(row["origin"].removeprefix("conda-forge: "), 0) + 1
            )
    conda_rows = []
    for record in packages:
        key = f"{record['name']}-{record['version']}-{record['build']}"
        conda_rows.append(
            {
                "name": record["name"],
                "version": record["version"],
                "build": record["build"],
                "sha256": record.get("sha256"),
                "md5": record.get("md5"),
                "declared_licence": record.get("license"),
                "loaded_objects": loaded_by_package.get(key, 0),
            }
        )

    for run in runs.values():
        run["pynumero_asl"] = _normalise(run["pynumero_asl"], env)
    return {
        "format": FORMAT,
        "host": {
            "machine": platform.machine(),
            "libc": " ".join(platform.libc_ver()),
        },
        "locks": {name: P03.sha256_of(path) for name, path in sorted(LOCKS.items())},
        "pynumero_asl_build": built,
        "workload": runs,
        "pynumero_asl_lookup_without_pyomo_config_dir": default_lookup(env),
        "conda_packages": conda_rows,
        "pip_distributions": pip_distributions,
        "objects": objects,
        "gates": {"G1": g1, "G2": g2, "G3": g3, "G4": g4, "G5": g5, "G6": g6},
        "pass_g1_to_g6": all(gate["pass"] for gate in (g1, g2, g3, g4, g5, g6)),
    }


def _comparable(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """The record with platform objects reduced to path and package, and those objects' drift."""
    record = json.loads(json.dumps(record))
    platform_rows = {}
    for row in record["objects"]:
        if row["origin"].startswith("platform: "):
            platform_rows[row["path"]] = {
                "sha256": row.pop("sha256"),
                "bytes": row.pop("bytes"),
                "origin": row["origin"],
            }
            row["origin"] = row["origin"].rsplit(" ", 1)[0]
            for notice in row["licence"]["notices"]:
                notice.pop("sha256", None)
    record["host"].pop("libc", None)
    return record, platform_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--env", type=Path, default=ROOT / ".venv-nlp")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--workload",
        choices=WORKLOADS,
        default="nlp-1",
        help="what the child solves: spec §8.1's NLP-1 through the WO-8 adapter (the default), or "
        "WO-6's two-variable stand-in, which the audit was first measured on",
    )
    arguments = parser.parse_args()
    if not (arguments.env / "bin" / "python").exists():
        print(f"no environment at {arguments.env}; build it with scripts/build-m03-ipopt-env.sh")
        return 2
    record = build_record(arguments.env, arguments.workload)
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    gates = " ".join(
        f"{name} {'PASS' if gate['pass'] else 'FAIL'}" for name, gate in record["gates"].items()
    )
    if arguments.check:
        committed = json.loads(arguments.out.read_text(encoding="utf-8"))
        new, new_platform = _comparable(record)
        old, old_platform = _comparable(committed)
        for path in sorted(set(new_platform) | set(old_platform)):
            if new_platform.get(path) != old_platform.get(path):
                print(f"platform drift (not compared): {path}")
        if new != old:
            changed = sorted(key for key in set(new) | set(old) if new.get(key) != old.get(key))
            print(f"--check FAILED: {arguments.out} differs in {', '.join(changed)}")
            return 1
        print(f"--check passed: {arguments.out} reproduced ({gates})")
        return 0
    arguments.out.write_text(text, encoding="utf-8")
    print(f"wrote {arguments.out} ({len(text)} bytes): {len(record['objects'])} objects; {gates}")
    return 0 if record["pass_g1_to_g6"] else 1


if __name__ == "__main__":
    sys.exit(main())
