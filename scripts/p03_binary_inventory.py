"""Exact binary, plugin and notice inventory of the two P03 backend candidates.

This is the [A10] audit instrument: requirement D04 asks for an "exact binary/data inventory and
distribution verdict", and [A10] asks for a "bundled plugin inventory including disabled
distributed bytes". The script produces the inventory. It does not produce the verdict, which is
ADR 0003 and ADR 0006.

Everything written here is read off the installed artifacts. Three kinds of statement are kept
apart in the output, because they carry different weight:

* ``measured`` — a size, a hash, an ELF ``DT_NEEDED`` entry, whether ``dlopen`` succeeded.
* ``declared`` — what a shipped LICENSE file or a wheel METADATA field says about itself.
* ``inferred`` — an attribution of a binary to an upstream component from its file name or its
  exported symbols. Marked as such, never silently promoted to measured.

An upstream project's licence is *not* determined here from knowledge of that project. It is
either read from a notice file the distribution actually ships, or it is recorded as unresolved.

Run against the two P02 candidate environments (see ``docs/backend-environments.md``)::

    .venv-casadi/bin/python scripts/p03_binary_inventory.py \
        --casadi-env .venv-casadi --pyomo-env .venv-pyomo \
        --out spikes/p03/results

The CasADi plugin probe needs to import CasADi, so the interpreter must be the one from
``.venv-casadi``. The Pyomo side is inventoried from the filesystem only and needs no import.

T08.A30 (the [A10] refresh, ADR 0006 D5.4; T08 release spec §4.8) inventories the *running*
interpreter's environment instead — every compiled distribution of the default install and the
``server`` extra, which must be at ``requirements.lock``'s versions — and writes the full record to
``--out`` (an evidence artifact) and the committed summary to ``--summary-dir``::

    .venv/bin/python scripts/p03_binary_inventory.py --a30 --out evidence/T08/artifacts/a30

Exit status 0 iff the record's verdict passes; both files are written either way.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------------------------
# Plugin types CasADi exposes a `load_<type>` function for. A plugin of a type absent from this
# map is inventoried as bytes but is not probed, and says so; inventing a failure for a plugin we
# have no supported way to load would be a fabricated measurement.
PROBEABLE_TYPES = (
    "archiver",
    "blas",
    "conic",
    "dple",
    "expm",
    "filesystem",
    "graphmodel",
    "integrator",
    "interpolant",
    "linsol",
    "modelicaparser",
    "nlpsol",
    "onnxbackend",
    "rootfinder",
)

# Plugin name -> the third-party solver whose library the plugin needs at run time but which the
# distribution does not contain. Used to classify a load failure as "vendor library absent" rather
# than "broken". Membership is checked against the measured absence of any matching `lib*.so`.
VENDOR_BACKED = {
    "knitro": "libknitro",
    "snopt": "libsnopt",
    "worhp": "libworhp",
    "cplex": "libcplex",
    "gurobi": "libgurobi",
    "mosek": "libmosek",
    "xpress": "libxprs",
    "ma27": "libhsl|libcoinhsl",
    "madnlp": "libmadnlp",
    "ccopt": "libccopt",
}

# Symbol-level attribution probes. A shipped notice tells you what the *build tree* contained; it
# does not tell you which shipped object the code ended up in, and for a restrictive notice that is
# exactly the question. Each probe names symbols that discriminate between two versions of the same
# upstream project, so the attribution rests on the binary rather than on the file name.
#
# METIS 4.x and METIS 5.x share `METIS_PartGraphKway` with different signatures, so that symbol
# discriminates nothing. `METIS_EstimateMemory` and `METIS_mCPartGraphKway` exist only in the 4.x
# API; `METIS_SetDefaultOptions` and `METIS_Free` were introduced in 5.x. The pair of answers
# together identifies the version, and the notice directory corroborates it.
ATTRIBUTION_PROBES: tuple[dict[str, Any], ...] = (
    {
        "component": "metis",
        "question": "Is the METIS compiled into this distribution the 4.x line or the 5.x line?",
        "positive_symbols": ["METIS_EstimateMemory", "METIS_mCPartGraphKway", "METIS_EdgeND"],
        "positive_means": "METIS 4.x",
        "negative_symbols": ["METIS_SetDefaultOptions", "METIS_Free"],
        "negative_means": "METIS 5.x",
        "any_symbol_prefix": "METIS_",
    },
)

LICENSE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("LGPL-3.0", r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 3"),
    ("LGPL-2.1", r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 2\.1"),
    ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
    ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 2"),
    ("EPL-2.0", r"Eclipse Public License - v 2\.0"),
    ("EPL-1.0", r"Eclipse Public License - v 1\.0"),
    ("CPL-1.0", r"Common Public License - v 1\.0"),
    ("Apache-2.0", r"Apache License\s+Version 2\.0"),
    ("MPL-2.0", r"Mozilla Public License Version 2\.0"),
    ("CeCILL-C", r"CeCILL-C"),
    ("BSL-1.0", r"Boost Software License"),
    ("MIT", r"\bMIT License\b"),
    ("BSD-3-Clause", r"Neither the name of .{0,120} may be used to endorse"),
    ("BSD-2-Clause", r"Redistribution and use in source and binary forms"),
    ("Zlib", r"This software is provided 'as-is', without any express or implied\s+warranty"),
)

# A notice whose text restricts redistribution rather than granting it. Matching one of these is
# reported as a finding, not as an identifier: it is the case the audit exists to catch.
RESTRICTIVE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("non-commercial / no-redistribution", r"may not be sold or redistributed"),
    (
        "non-commercial / no-redistribution",
        r"for educational and research purposes\s+by non-profit",
    ),
    ("evaluation only", r"allowed to use .{0,40} only for evaluation purposes"),
    ("prior approval required", r"further uses will require prior approval"),
)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def classify_file(path: Path) -> str:
    name = path.name
    if ".so" in name:
        return "elf-shared"
    if name.endswith(".a"):
        return "static-archive"
    if name.endswith(".la"):
        return "libtool-archive"
    if name.endswith((".h", ".hpp", ".hxx", ".inc", ".ipp")):
        return "header"
    if name.endswith((".py", ".pyi", ".pyc")):
        return "python"
    if name.endswith((".cmake", ".pc")):
        return "build-metadata"
    if path.is_file() and os.access(path, os.X_OK):
        return "elf-executable"
    return "other"


def needed_of(path: Path) -> list[str]:
    """DT_NEEDED entries of an ELF object, measured with objdump. Empty if not an ELF."""
    try:
        completed = subprocess.run(
            ["objdump", "-p", str(path)], capture_output=True, text=True, check=False
        )
    except FileNotFoundError:  # pragma: no cover - objdump missing on the host
        return []
    if completed.returncode != 0:
        return []
    return [line.split()[1] for line in completed.stdout.splitlines() if "NEEDED" in line]


def defined_symbols(path: Path) -> set[str]:
    """Dynamic symbols an ELF object defines. Empty set if the object has none or is not an ELF."""
    completed = subprocess.run(
        ["nm", "-D", "--defined-only", str(path)], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        return set()
    return {
        parts[2]
        for parts in (line.split() for line in completed.stdout.splitlines())
        if len(parts) >= 3
    }


def run_attribution_probes(package_root: Path) -> list[dict[str, Any]]:
    """Which shipped objects carry a given upstream component's code, and which version of it."""
    objects = sorted(
        path for path in package_root.rglob("*") if ".so" in path.name and path.is_file()
    )
    symbols_by_object = {path: defined_symbols(path) for path in objects}
    results: list[dict[str, Any]] = []
    for probe in ATTRIBUTION_PROBES:
        carriers: list[dict[str, Any]] = []
        for path, symbols in symbols_by_object.items():
            if not any(name.startswith(str(probe["any_symbol_prefix"])) for name in symbols):
                continue
            positive = [name for name in probe["positive_symbols"] if name in symbols]
            negative = [name for name in probe["negative_symbols"] if name in symbols]
            if positive and not negative:
                conclusion = probe["positive_means"]
            elif negative and not positive:
                conclusion = probe["negative_means"]
            else:
                conclusion = "indeterminate"
            carriers.append(
                {
                    "path": str(path.relative_to(package_root)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_of(path),
                    "positive_symbols_present": positive,
                    "negative_symbols_present": negative,
                    "conclusion": conclusion,
                }
            )
        results.append(
            {
                "component": probe["component"],
                "question": probe["question"],
                "discriminators": {
                    probe["positive_means"]: probe["positive_symbols"],
                    probe["negative_means"]: probe["negative_symbols"],
                },
                "carriers": carriers,
            }
        )
    return results


def reachability(package_root: Path, entry_point: str) -> dict[str, Any]:
    """The DT_NEEDED closure of one entry point, restricted to objects this package ships.

    CasADi loads a plugin with ``dlopen`` on first use, so a plugin is never in the link-time
    closure of the extension module. The closure is therefore what an import plus a plugin-free
    evaluation can touch, and everything outside it is shipped but dormant on that route.
    """
    shipped = {path.name: path for path in package_root.glob("*.so*") if path.is_file()}
    start = package_root / entry_point
    if not start.is_file():
        return {"entry_point": entry_point, "resolved": False}
    seen: set[str] = set()
    external: set[str] = set()
    frontier = [start]
    while frontier:
        current = frontier.pop()
        for name in needed_of(current):
            if name in seen:
                continue
            target = shipped.get(name)
            if target is None:
                external.add(name)
                continue
            seen.add(name)
            frontier.append(target)
    resolved = sorted(seen)
    return {
        "entry_point": entry_point,
        "resolved": True,
        "entry_bytes": start.stat().st_size,
        "in_package_closure": resolved,
        "external_dependencies": sorted(external),
        "closure_bytes": start.stat().st_size
        + sum(shipped[name].stat().st_size for name in resolved),
    }


def identify_notice(text: str) -> dict[str, Any]:
    identifiers = [name for name, pattern in LICENSE_PATTERNS if re.search(pattern, text, re.S)]
    restrictions = sorted(
        {label for label, pattern in RESTRICTIVE_PATTERNS if re.search(pattern, text, re.S | re.I)}
    )
    return {"declared_identifiers": identifiers, "restrictive_clauses": restrictions}


def inventory_tree(root: Path) -> list[dict[str, Any]]:
    """Every file, with its hash, and for each ELF its own DT_NEEDED list.

    The per-object `needed` list is what makes a reachability claim checkable from this record
    alone. Without it a reader has to trust a chain the inventory asserts but does not contain —
    which is exactly the load-bearing claim in the METIS finding, so it is recorded here rather
    than reconstructed from the installed tree each time someone wants to verify it.
    """
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        entry: dict[str, Any] = {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": sha256_of(path),
            "kind": classify_file(path),
        }
        if entry["kind"] in {"elf-shared", "elf-executable"}:
            entry["needed"] = needed_of(path)
        entries.append(entry)
    return entries


def symlink_map(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): os.readlink(path)
        for path in sorted(root.rglob("*"))
        if path.is_symlink()
    }


def inventory_notices(licenses_root: Path) -> list[dict[str, Any]]:
    notices: list[dict[str, Any]] = []
    if not licenses_root.is_dir():
        return notices
    for path in sorted(licenses_root.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        record = {
            "path": str(path.relative_to(licenses_root)),
            "component": path.relative_to(licenses_root).parts[0],
            "bytes": path.stat().st_size,
            "sha256": sha256_of(path),
        }
        record.update(identify_notice(text))
        notices.append(record)
    return notices


def probe_plugins(package_root: Path) -> list[dict[str, Any]]:
    """Which shipped plugins actually load, and which are bytes that cannot.

    The distinction is [A10]'s "disabled distributed bytes". A plugin is *disabled* when its object
    is present and counted in the download but no invocation of it can succeed in this environment.
    """
    import casadi  # noqa: PLC0415 - deliberately local; only this probe needs the backend

    present_libraries = {path.name for path in package_root.glob("*.so*")}
    plugins: list[dict[str, Any]] = []
    pattern = re.compile(r"^libcasadi_([a-z0-9]+)_([a-z0-9_]+)\.so$")
    for path in sorted(package_root.glob("libcasadi_*.so")):
        match = pattern.match(path.name)
        if match is None:
            continue
        plugin_type, plugin_name = match.group(1), match.group(2)
        record: dict[str, Any] = {
            "type": plugin_type,
            "name": plugin_name,
            "file": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_of(path),
            "needed": needed_of(path),
        }
        loader = getattr(casadi, f"load_{plugin_type}", None)
        if plugin_type not in PROBEABLE_TYPES or loader is None:
            record["load"] = "not-probed"
            record["load_detail"] = (
                f"casadi exposes no load_{plugin_type}() in {casadi.__version__}"
            )
        else:
            try:
                loader(plugin_name)
            except Exception as error:  # noqa: BLE001 - the failure text is the evidence
                record["load"] = "failed"
                record["load_detail"] = " ".join(str(error).split())[:300]
            else:
                record["load"] = "ok"
                record["load_detail"] = ""
        vendor = VENDOR_BACKED.get(plugin_name)
        if vendor is not None:
            shipped = sorted(
                name for name in present_libraries if re.match(f"({vendor})", name) is not None
            )
            record["vendor_library_expected"] = vendor
            record["vendor_library_shipped"] = shipped
        plugins.append(record)
    return plugins


def summarize(entries: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for entry in entries:
        bucket = totals.setdefault(entry["kind"], {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += int(entry["bytes"])
    return dict(sorted(totals.items()))


def casadi_inventory(env: Path) -> dict[str, Any]:
    package_roots = sorted(env.glob("lib/python*/site-packages/casadi"))
    if not package_roots:
        raise SystemExit(f"no casadi package under {env}")
    package_root = package_roots[0]
    files = inventory_tree(package_root)
    plugins = probe_plugins(package_root)
    disabled = [entry for entry in plugins if entry["load"] == "failed"]
    return {
        "root": str(package_root),
        "files": files,
        "symlinks": symlink_map(package_root),
        "totals": summarize(files),
        "total_bytes": sum(int(entry["bytes"]) for entry in files),
        "dist_info": dist_info_record(package_root.parent, "casadi-*.dist-info"),
        "notices": inventory_notices(package_root / "include" / "licenses"),
        "plugins": plugins,
        "disabled_distributed_bytes": {
            "definition": (
                "Plugin objects present in the download for which no invocation can succeed in "
                "this environment, because the third-party library they bind to is not distributed "
                "with them. They are downloaded, installed and redistributed; they cannot be run."
            ),
            "plugin_objects": len(disabled),
            "plugin_bytes": sum(int(entry["bytes"]) for entry in disabled),
            "plugin_names": sorted(f"{entry['type']}:{entry['name']}" for entry in disabled),
            "vendor_adaptor_stubs": [
                {
                    "path": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_of(path),
                }
                for path in sorted(package_root.glob("*_adaptor.so"))
            ],
        },
        "reachability": reachability(package_root, "_casadi.so"),
        "attribution_probes": run_attribution_probes(package_root),
    }


def dist_info_record(site_packages: Path, pattern: str) -> dict[str, Any]:
    """What the wheel's own metadata directory declares, and which notice files it carries.

    Kept separate from the package tree because the two can disagree: a distribution may ship a
    licence expression in METADATA and no notice beside it, or notices in the package tree that the
    metadata directory does not mention. Both happen among these two candidates.
    """
    matches = sorted(site_packages.glob(pattern))
    if not matches:
        return {"present": False}
    root = matches[0]
    metadata_text = (root / "METADATA").read_text(encoding="utf-8", errors="replace")
    declared = {
        key: next(
            (
                line.split(":", 1)[1].strip()
                for line in metadata_text.splitlines()
                if line.startswith(f"{key}:")
            ),
            None,
        )
        for key in ("Name", "Version", "License", "License-Expression")
    }
    notices = [
        {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": sha256_of(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and re.search(r"(LICENSE|COPYING|NOTICE)", path.name, re.I)
    ]
    return {
        "present": True,
        "path": str(root.relative_to(site_packages)),
        "entries": sorted(item.name for item in root.iterdir()),
        "declared": declared,
        "notice_files": notices,
    }


def pyomo_inventory(env: Path, pyomo_lib: Path) -> dict[str, Any]:
    package_roots = sorted(env.glob("lib/python*/site-packages/pyomo"))
    if not package_roots:
        raise SystemExit(f"no pyomo package under {env}")
    package_root = package_roots[0]
    files = inventory_tree(package_root)
    built: list[dict[str, Any]] = []
    if pyomo_lib.is_dir():
        for path in sorted(pyomo_lib.iterdir()):
            if not path.is_file():
                continue
            built.append(
                {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_of(path),
                    "kind": classify_file(path),
                    "needed": needed_of(path),
                }
            )
    built_notices = sorted(
        str(path)
        for path in pyomo_lib.parent.rglob("*")
        if path.is_file() and re.search(r"(LICENSE|COPYING|NOTICE)", path.name, re.I)
    )
    return {
        "root": str(package_root),
        "totals": summarize(files),
        "total_bytes": sum(int(entry["bytes"]) for entry in files),
        "dist_info": dist_info_record(package_root.parent, "pyomo-*.dist-info"),
        "shipped_binaries": [
            entry for entry in files if entry["kind"] in {"elf-shared", "static-archive"}
        ],
        "package_tree_notice_files": [
            entry
            for entry in files
            if re.search(r"(LICENSE|COPYING|NOTICE)", Path(entry["path"]).name, re.I)
        ],
        "locally_built_extensions": built,
        "locally_built_notice_files": built_notices,
        "locally_built_note": (
            "PyNumero's ASL interface is not distributed in the wheel. It is compiled on the host "
            "by `pyomo build-extensions` into ~/.pyomo/lib, so these bytes are a build product of "
            "the installing machine, not bytes this project would redistribute. The build leaves "
            "no notice file for the AMPL Solver Library itself; establishing the ASL terms needs "
            "the upstream source distribution and is recorded as unresolved, not guessed."
        ),
    }


# ============================================================================================
# T08.A30 — the [A10] refresh (ADR 0006 D5.4) over every compiled distribution of the default
# install and the `server` extra, at the lock's versions, on the architecture this runs on.
# ============================================================================================
#
# The P03 inventory above audited one wheel. ADR 0006 D5.4 makes the refresh due on any second
# platform's wheel, and T08 spec §4.8 widens it to every compiled distribution the project makes
# its users install. The rules are P03's: everything is read off the installed artifacts, a term
# is read from a shipped notice or recorded as unresolved, and an attribution by name is marked
# `inferred`. What is new is the *required closure*: the objects an import of the installed Python
# extension modules links, which is where a restrictive, non-LGPL GPL-family or unresolved object
# fails the gate (spec §4.8 verdict rule) rather than merely being listed.

A30_FORMAT = "t08-a30-inventory-v1"
ROOT = Path(__file__).resolve().parent.parent
ELF_MAGIC = b"\x7fELF"
AR_MAGIC = b"!<arch>\n"

# ADR 0006 D4's eight objects, by file name, as audited on the x86-64 wheel: unresolved, outside the
# `_casadi.so` closure, mode-B notice items. Dispositioned is not cleared — they stay listed — but
# they are not *new* findings. An object of the same component under another name (the aarch64
# wheel's own hash-suffixed copies) is not covered by this list and is reported as new.
ADR0006_D4 = frozenset(
    {
        "libgfortran-8f1e9814.so.5.0.0",
        "libquadmath-828275a7.so.0.0.0",
        "libgomp-870cb1d0.so.1.0.0",
        "libmvec-2-583a17db.28.so",
        "libspral.a",
        "libmatlab_ipc.so",
        "libcplex_adaptor.so",
        "libgurobi_adaptor.so",
    }
)
# ADR 0006 Amendment 2 (design lane, 2026-10-01; R-142): D4 on the aarch64 wheel adds its two
# unresolved toolchain-runtime objects, by file name, with their x86-64 counterparts' defaults.
ADR0006_A2 = frozenset({"libgfortran-8de1544a.so.5.0.0", "libgomp-7eb2fb8b.so.1.0.0"})
# ADR 0006 Amendment 1 (Frank, 2026-10-01): the GCC runtime library numpy and scipy vendor is under
# GPL-3.0 with the GCC Runtime Library Exception, read as outside blueprint §15's GPL line.
ADR0006_A1_GCC_RUNTIME_DISTRIBUTIONS = frozenset({"numpy", "scipy"})
ADR0006_A1_GCC_RUNTIME_LICENCE = "GPL-3.0-with-GCC-exception"

# ADR 0006 D2's disposition of the restrictive METIS 4.x notice: the carrier and everything that
# reaches it stay off every project path (D1.5) and out of every mode-B artifact (R2).
ADR0006_D2_METIS_CARRIERS = frozenset(
    {"libcoinmetis.so", "libcoinmetis.so.2", "libcoinmetis.so.2.0.0"}
)

# CasADi's object-to-notice mapping is a name rule (P03 audit §2.7, `inferred`): an object is
# attributed to every notice whose path names a component the object's name names. Two static
# archives carry no component in their names; their defined symbols are SCS's (`scs_*`, read with
# `nm`), and `superscs-external` is the only SCS notice shipped.
# `libsipopt` is Ipopt's sensitivity extension, whose notice is Ipopt's; `coin` prefixes a Coin-OR
# `ThirdParty` build (`libcoinmetis`, `libcoinmumps`) and is dropped before matching.
CASADI_NAME_ALIASES = {"indirect": "superscs", "linsys": "superscs", "sipopt": "ipopt"}

_GPL = re.compile(r"\bA?GPL\b|GPL-\d|GNU (Affero )?General Public", re.IGNORECASE)
_LGPL = re.compile(r"\bLGPL|GNU (Lesser|Library) General Public", re.IGNORECASE)


def _object_kind(path: Path) -> str | None:
    """`elf` or `static-archive` from the file's magic bytes; None for anything else."""
    try:
        with path.open("rb") as handle:
            head = handle.read(8)
    except OSError:
        return None
    if head.startswith(ELF_MAGIC):
        return "elf"
    if head == AR_MAGIC:
        return "static-archive"
    return None


def _soname_of(path: Path) -> str | None:
    completed = subprocess.run(
        ["objdump", "-p", str(path)], capture_output=True, text=True, check=False
    )
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "SONAME":
            return parts[1]
    return None


def licence_category(licence: str | None, restrictive: bool = False) -> str:
    """The spec §4.8 category of one declared licence string.

    `restrictive` (a no-redistribution or use-restricting notice), `gpl-family` (GPL or AGPL, with
    or without an exception — the LGPL excluded, which ADR 0006 Q1 allows), `lgpl`, `unresolved`
    (nothing read), or `identified` (any other licence read off a shipped notice or the metadata).
    """
    if restrictive:
        return "restrictive"
    if not licence:
        return "unresolved"
    if _LGPL.search(licence):
        return "lgpl"
    if _GPL.search(licence):
        return "gpl-family"
    return "identified"


_CATEGORY_ORDER = ("identified", "lgpl", "gpl-family", "unresolved", "restrictive")


def _lock_pins(lock: Path) -> dict[str, str]:
    from packaging.utils import canonicalize_name  # noqa: PLC0415 - the A30 mode only

    pins: dict[str, str] = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "==" in line:
            name, version = line.split("==", 1)
            pins[canonicalize_name(name)] = version.strip()
    return pins


def _a30_roots(pyproject: Path) -> list[Any]:
    """The default install's requirements plus the `server` extra's, from `pyproject.toml`."""
    import tomllib  # noqa: PLC0415

    from packaging.requirements import Requirement  # noqa: PLC0415

    with pyproject.open("rb") as handle:
        project = tomllib.load(handle)["project"]
    texts = [*project["dependencies"], *project["optional-dependencies"]["server"]]
    return [Requirement(text) for text in texts]


def _t07_licence_module() -> Any:
    """The closure walk and the compiled-wheel test of `scripts/t07_licence_inventory.py` (G19).

    Reused rather than copied so that A30 and G19 cannot disagree about which distributions the
    `server` extra brings or which of them are compiled.
    """
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location(
        "t07_licence_inventory", Path(__file__).resolve().parent / "t07_licence_inventory.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _declared_licence(distribution: Any) -> str | None:
    meta = distribution.metadata
    expression = meta.get("License-Expression")
    if expression:
        return str(expression)
    licence = meta.get("License")
    classifiers = [
        value.removeprefix("License :: ")
        for value in meta.get_all("Classifier") or []
        if value.startswith("License ::")
    ]
    parts = [licence.strip().splitlines()[0]] if licence and licence.strip() else []
    parts += classifiers
    return "; ".join(parts) or None


def _bundled_stanzas(dist_info: Path) -> list[dict[str, Any]]:
    """The `Name:` / `Files:` / `License:` blocks a wheel builder appends to the dist-info licence.

    numpy and scipy declare their vendored libraries this way (`numpy.libs/libgfortran*.so` …), so
    a vendored object is attributed by the wheel's own words, not by its name.
    """
    stanzas: list[dict[str, Any]] = []
    for notice in sorted(dist_info.rglob("*")):
        if not notice.is_file() or not re.search(r"(LICEN[CS]E|COPYING|NOTICE)", notice.name, re.I):
            continue
        current: dict[str, Any] = {}
        for line in notice.read_text(encoding="utf-8", errors="replace").splitlines() + [""]:
            match = re.match(r"^(Name|Files|License):\s*(.*)$", line)
            if match:
                current[match.group(1).lower()] = match.group(2).strip()
                continue
            if not line.strip() and {"files", "license"} <= current.keys():
                current["notice"] = str(notice.relative_to(dist_info.parent))
                stanzas.append(current)
            if not line.strip():
                current = {}
    return stanzas


def _casadi_notice_components(licenses_root: Path) -> list[dict[str, Any]]:
    """Every notice under `casadi/include/licenses`, with the name keys the name rule matches on."""
    components = []
    for record in inventory_notices(licenses_root):
        keys = set()
        for part in Path(record["path"]).parts[:-1]:
            key = re.sub(r"(-external|-build|-src|_runtime|-[\d.]+)+$", "", part.lower())
            key = key.removeprefix("lib") if len(key) > 3 else key
            if len(key) >= 3 or key == "z":  # `libz-external` is zlib's
                keys.add(key)
        restrictive = bool(record["restrictive_clauses"])
        identifiers = record["declared_identifiers"]
        # An LGPL text carries the GPL text it modifies; the pair declares the LGPL.
        if any(name.startswith("LGPL") for name in identifiers):
            identifiers = [name for name in identifiers if not name.startswith("GPL")]
        components.append(
            {
                "notice": f"casadi/include/licenses/{record['path']}",
                "keys": sorted(keys),
                "licence": " AND ".join(identifiers) or None,
                "restrictive": restrictive,
            }
        )
    return components


def _casadi_name_tokens(name: str) -> set[str]:
    stem = re.sub(r"(\.so.*|\.a)$", "", name.lower())
    tokens = set()
    for token in re.split(r"[_\-.]", stem):
        token = token.removeprefix("lib")
        if token:
            tokens.add(CASADI_NAME_ALIASES.get(token, token))
            if token.startswith("coin") and len(token) > 4:
                tokens.add(token.removeprefix("coin"))
    return tokens


def _attribute_casadi(name: str, components: list[dict[str, Any]]) -> dict[str, Any]:
    """P03 §2.7's name rule: a notice is attributed when one of its keys starts an object token."""
    tokens = _casadi_name_tokens(name)
    matched = [
        component
        for component in components
        if any(
            token == key or (len(key) >= 3 and token.startswith(key))
            for token in tokens
            for key in component["keys"]
        )
    ]
    if not matched:
        return {"source": "none", "licence": None, "notices": [], "category": "unresolved"}
    categories = [
        licence_category(component["licence"] or "identified", component["restrictive"])
        for component in matched
    ]
    worst = max(categories, key=_CATEGORY_ORDER.index)
    return {
        "source": "casadi-notice-by-name (inferred)",
        "licence": "; ".join(sorted({c["licence"] or "unidentified" for c in matched})),
        "notices": sorted(component["notice"] for component in matched),
        "category": worst,
    }


def _distribution_objects(distribution: Any, site_packages: Path) -> list[dict[str, Any]]:
    """Every compiled object a distribution installed (its RECORD), with hash and `DT_NEEDED`."""
    import fnmatch  # noqa: PLC0415

    name = distribution.metadata["Name"]
    metadata_file = next(
        (entry for entry in distribution.files or [] if str(entry).endswith(".dist-info/METADATA")),
        None,
    )
    stanzas = (
        []
        if metadata_file is None
        else _bundled_stanzas(Path(str(distribution.locate_file(metadata_file))).parent)
    )
    declared = _declared_licence(distribution)
    components: list[dict[str, Any]] = []
    if name.lower() == "casadi":
        components = _casadi_notice_components(site_packages / "casadi" / "include" / "licenses")
    objects = []
    for entry in sorted(distribution.files or [], key=str):
        path = Path(str(distribution.locate_file(entry))).resolve()
        if not path.is_file() or path.is_symlink():
            continue
        kind = _object_kind(path)
        if kind is None:
            continue
        try:
            relative = str(path.relative_to(site_packages.resolve()))
        except ValueError:
            relative = str(entry)
        row: dict[str, Any] = {
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": sha256_of(path),
            "kind": kind,
        }
        if kind == "elf":
            row["needed"] = needed_of(path)
            row["soname"] = _soname_of(path)
            row["python_extension"] = any(
                symbol.startswith("PyInit_") for symbol in defined_symbols(path)
            )
        # `Files: scipy.libs/libgfortran*.so` names the versioned `…so.5.0.0` too.
        stanza = next(
            (item for item in stanzas if fnmatch.fnmatch(relative, item["files"] + "*")), None
        )
        vendored = Path(relative).parts[0].endswith(".libs")
        if stanza is not None:
            row["attribution"] = {
                "source": "dist-info-bundled-stanza (declared)",
                "licence": stanza["license"],
                "component": stanza.get("name"),
                "notices": [stanza["notice"]],
                "category": licence_category(stanza["license"]),
            }
        elif components:
            row["attribution"] = _attribute_casadi(path.name, components)
        elif vendored:
            row["attribution"] = {
                "source": "none",
                "licence": None,
                "notices": [],
                "category": "unresolved",
            }
        else:
            row["attribution"] = {
                "source": "distribution-metadata (declared)",
                "licence": declared,
                "notices": [],
                "category": licence_category(declared),
            }
        objects.append(row)
    return objects


def _files_digest(distribution: Any) -> str:
    """SHA-256 over `path\\tsha256` of every installed file but bytecode and install records.

    The per-file hashes A44 compares a clean install against, condensed to one value per
    distribution so the committed summary can carry it.
    """
    lines = []
    for entry in sorted(distribution.files or [], key=str):
        text = str(entry)
        if text.endswith(".pyc") or text.rsplit("/", 1)[-1] in {
            "RECORD",
            "INSTALLER",
            "REQUESTED",
            "direct_url.json",
        }:
            continue
        path = Path(str(distribution.locate_file(entry)))
        if path.is_file():
            lines.append(f"{text}\t{sha256_of(path)}\n")
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def _closure_of(
    starts: list[str], by_name: dict[str, list[str]], needed: dict[str, list[str]]
) -> set[str]:
    """`DT_NEEDED` closure over the inventoried objects, by file name or SONAME."""
    seen: set[str] = set()
    frontier = list(starts)
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        for dependency in needed.get(current, []):
            frontier.extend(by_name.get(dependency, []))
    return seen


# The measured half of "unreachable from every project path": a child interpreter does what the
# project does — imports every `openflowsheet` module and both bindings, solves SYN-001-nominal
# through the CLI — and reports every object mapped from `site-packages`.
_WORKLOAD = r"""
import importlib, json, pkgutil, sys, tempfile
import openflowsheet
for module in pkgutil.walk_packages(openflowsheet.__path__, "openflowsheet."):
    importlib.import_module(module.name)
from openflowsheet.application import cli
with tempfile.TemporaryDirectory() as scratch:
    status = cli.main(["solve", "SYN-001-nominal", "--out", scratch + "/bundle"])
mapped = set()
with open("/proc/self/maps", encoding="utf-8") as handle:
    for line in handle:
        fields = line.rstrip("\n").split(None, 5)  # the path may contain spaces
        if len(fields) == 6 and "site-packages/" in fields[5]:
            mapped.add(fields[5].split("site-packages/", 1)[1])
print(json.dumps({"solve_exit": status, "mapped": sorted(mapped)}))
"""


def measured_project_load() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-c", _WORKLOAD], capture_output=True, text=True, check=False, cwd=ROOT
    )
    if completed.returncode != 0:
        raise SystemExit(f"the project workload failed:\n{completed.stderr[-2000:]}")
    return json.loads(completed.stdout.strip().splitlines()[-1])


def a30_inventory(pyproject: Path, lock: Path) -> dict[str, Any]:
    """The T08.A30 record for the running interpreter's environment."""
    import sysconfig  # noqa: PLC0415

    t07 = _t07_licence_module()
    site_packages = Path(sysconfig.get_paths()["purelib"])
    roots = _a30_roots(pyproject)
    found = t07.closure(roots)
    pins = _lock_pins(lock)
    distributions = []
    objects: list[dict[str, Any]] = []
    off_lock = []
    for name, distribution in sorted(found.items()):
        if pins.get(name) != distribution.version:
            off_lock.append(f"{name} {distribution.version} (lock: {pins.get(name)})")
        compiled = bool(t07._compiled(distribution))
        rows = _distribution_objects(distribution, site_packages) if compiled else []
        for row in rows:
            row["distribution"] = name
        objects.extend(rows)
        distributions.append(
            {
                "name": name,
                "version": distribution.version,
                "compiled": compiled,
                "declared_licence": _declared_licence(distribution),
                "objects": len(rows),
                "object_bytes": sum(int(row["bytes"]) for row in rows),
                "files_digest": _files_digest(distribution),
            }
        )
    if off_lock:
        raise SystemExit("not at the lock's versions: " + "; ".join(off_lock))

    # A wheel's objects find each other through their own RPATH (`$ORIGIN`, `../<name>.libs`); a
    # name no object of the same distribution carries is the system's (libgfortran's `libz.so.1`
    # is not CasADi's `libz.so.1`). So names resolve within a distribution, never across.
    by_name: dict[str, list[str]] = {}
    needed: dict[str, list[str]] = {}
    for row in objects:
        for alias in {Path(row["path"]).name, row.get("soname")} - {None}:
            by_name.setdefault(f"{row['distribution']}/{alias}", []).append(row["path"])
        needed[row["path"]] = [f"{row['distribution']}/{name}" for name in row.get("needed", [])]

    entries = sorted(row["path"] for row in objects if row.get("python_extension"))
    required = _closure_of(entries, by_name, needed)

    # METIS: every object defining a METIS_ symbol, by version, then everything that reaches one.
    carriers = []
    for row in objects:
        if row["kind"] != "elf":
            continue
        symbols = defined_symbols(site_packages / row["path"])
        if not any(symbol.startswith("METIS_") for symbol in symbols):
            continue
        probe = ATTRIBUTION_PROBES[0]
        positive = [name for name in probe["positive_symbols"] if name in symbols]
        negative = [name for name in probe["negative_symbols"] if name in symbols]
        conclusion = (
            "METIS 4.x"
            if positive and not negative
            else "METIS 5.x"
            if negative and not positive
            else "indeterminate"
        )
        carriers.append({"path": row["path"], "sha256": row["sha256"], "conclusion": conclusion})
    restricted = {item["path"] for item in carriers if item["conclusion"] != "METIS 5.x"}
    metis_closure = {
        row["path"] for row in objects if _closure_of([row["path"]], by_name, needed) & restricted
    }
    plugin = re.compile(r"libcasadi_([a-z0-9]+)_([a-z0-9_]+)\.so$")
    metis_plugins = sorted(
        f"{match.group(1)}:{match.group(2)}"
        for path in metis_closure
        if (match := plugin.search(path)) is not None
    )
    measured = measured_project_load()
    loaded = set(measured["mapped"])

    for row in objects:
        row["in_required_closure"] = row["path"] in required
        row["in_metis_closure"] = row["path"] in metis_closure

    findings = []
    for row in objects:
        category = row["attribution"]["category"]
        if category not in {"restrictive", "gpl-family", "unresolved"}:
            continue
        name = Path(row["path"]).name
        if row["distribution"] == "casadi" and name in ADR0006_D4:
            disposition = "ADR 0006 D4"
        elif row["distribution"] == "casadi" and name in ADR0006_A2:
            disposition = "ADR 0006 Amendment 2"
        elif row["distribution"] == "casadi" and name in ADR0006_D2_METIS_CARRIERS:
            disposition = "ADR 0006 D2"
        elif (
            row["distribution"] in ADR0006_A1_GCC_RUNTIME_DISTRIBUTIONS
            and row["attribution"]["licence"] == ADR0006_A1_GCC_RUNTIME_LICENCE
        ):
            disposition = "ADR 0006 Amendment 1"
        else:
            disposition = None
        findings.append(
            {
                "path": row["path"],
                "distribution": row["distribution"],
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "category": category,
                "licence": row["attribution"]["licence"],
                "notices": row["attribution"]["notices"],
                "in_required_closure": row["in_required_closure"],
                "loaded_by_project": row["path"] in loaded,
                "dispositioned_by": disposition,
            }
        )
    undispositioned_required = sorted(
        item["path"]
        for item in findings
        if item["dispositioned_by"] is None
        and (item["in_required_closure"] or item["loaded_by_project"])
    )
    metis_reached = sorted((required | loaded) & metis_closure)
    return {
        "format": A30_FORMAT,
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "lock_sha256": sha256_of(lock),
        "requirements": [str(requirement) for requirement in roots],
        "distributions": distributions,
        "objects": objects,
        "required_closure": {
            "definition": (
                "The DT_NEEDED closure, over the inventoried objects by file name or SONAME, of "
                "every installed Python extension module (an ELF defining a PyInit_ symbol) of "
                "every distribution in the default install and the server extra."
            ),
            "entry_points": entries,
            "objects": sorted(required),
        },
        "measured_project_load": {
            "workload": "import every openflowsheet module and both bindings; "
            "openflowsheet solve SYN-001-nominal",
            "solve_exit": measured["solve_exit"],
            "mapped": sorted(loaded),
        },
        "metis": {
            "carriers": carriers,
            "closure": sorted(metis_closure),
            "closure_plugins": metis_plugins,
            "reached_from_project_paths": metis_reached,
        },
        "findings": findings,
        "verdict": {
            "undispositioned_in_required_closure": undispositioned_required,
            "metis_reached_from_project_paths": metis_reached,
            "pass": not undispositioned_required and not metis_reached,
        },
    }


def a30_summary(record: dict[str, Any], record_sha256: str) -> dict[str, Any]:
    """The committed digest of one architecture's record (the record itself is an artifact)."""
    required_rows = [row for row in record["objects"] if row["in_required_closure"]]
    by_distribution: dict[str, dict[str, int]] = {}
    for row in record["objects"]:
        bucket = by_distribution.setdefault(row["distribution"], {})
        category = row["attribution"]["category"]
        bucket[category] = bucket.get(category, 0) + 1
    distributions = []
    for entry in record["distributions"]:
        rows = sorted(
            f"{row['path']}\t{row['sha256']}\n"
            for row in record["objects"]
            if row["distribution"] == entry["name"]
        )
        # One value per distribution over its objects' (path, sha256): what a test compares with
        # an earlier audit (P03's CasADi record) without the record itself being committed.
        objects_digest = hashlib.sha256("".join(rows).encode()).hexdigest()
        distributions.append({**entry, "objects_digest": objects_digest})
    return {
        "format": f"{A30_FORMAT}-summary",
        "record_sha256": record_sha256,
        "host": record["host"],
        "lock_sha256": record["lock_sha256"],
        "distributions": distributions,
        "categories_by_distribution": dict(sorted(by_distribution.items())),
        "objects": len(record["objects"]),
        "distinct_objects": len({row["sha256"] for row in record["objects"]}),
        "required_closure": [
            {
                "path": row["path"],
                "distribution": row["distribution"],
                "sha256": row["sha256"],
                "needed": row.get("needed", []),
                "licence": row["attribution"]["licence"],
                "category": row["attribution"]["category"],
            }
            for row in required_rows
        ],
        "measured_project_load": record["measured_project_load"],
        "metis": record["metis"],
        "findings": record["findings"],
        "verdict": record["verdict"],
    }


def a30_main(arguments: argparse.Namespace) -> int:
    record = a30_inventory(arguments.pyproject, arguments.lock)
    machine = record["host"]["machine"]
    arguments.out.mkdir(parents=True, exist_ok=True)
    target = arguments.out / f"a30-inventory-{machine}.json"
    target.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    summary = a30_summary(record, sha256_of(target))
    summary_target = arguments.summary_dir / f"t08-a30-{machine}.json"
    summary_target.parent.mkdir(parents=True, exist_ok=True)
    summary_target.write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    compiled = [row["name"] for row in record["distributions"] if row["compiled"]]
    print(f"wrote {target} ({target.stat().st_size} bytes) and {summary_target}")
    print(
        f"{machine}: {len(record['objects'])} objects in {len(compiled)} compiled distributions "
        f"({', '.join(compiled)}); required closure {len(record['required_closure']['objects'])}"
    )
    for item in record["findings"]:
        if item["dispositioned_by"] is None:
            where = (
                "REQUIRED" if item["in_required_closure"] or item["loaded_by_project"] else "listed"
            )
            print(f"  new finding [{where}] {item['path']}: {item['category']} ({item['licence']})")
    verdict = record["verdict"]
    print("A30 " + ("PASS" if verdict["pass"] else "FAIL") + f": {verdict}")
    return 0 if verdict["pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--casadi-env", type=Path, default=Path(".venv-casadi"))
    parser.add_argument("--pyomo-env", type=Path, default=Path(".venv-pyomo"))
    parser.add_argument("--pyomo-lib", type=Path, default=Path.home() / ".pyomo" / "lib")
    parser.add_argument("--out", type=Path, default=Path("spikes/p03/results"))
    # T08.A30: inventory the running interpreter's environment instead of the P03 candidates.
    parser.add_argument("--a30", action="store_true", help="T08.A30 mode (see the A30 section)")
    parser.add_argument("--pyproject", type=Path, default=ROOT / "pyproject.toml")
    parser.add_argument("--lock", type=Path, default=ROOT / "requirements.lock")
    parser.add_argument("--summary-dir", type=Path, default=ROOT / "docs" / "t08-a30")
    arguments = parser.parse_args()
    if arguments.a30:
        return a30_main(arguments)

    host = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }
    arguments.out.mkdir(parents=True, exist_ok=True)

    casadi_record = {"host": host, "candidate": "casadi", **casadi_inventory(arguments.casadi_env)}
    pyomo_record = {
        "host": host,
        "candidate": "pyomo",
        **pyomo_inventory(arguments.pyomo_env, arguments.pyomo_lib),
    }
    for name, record in (("casadi", casadi_record), ("pyomo", pyomo_record)):
        target = arguments.out / f"{name}-inventory.json"
        target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
