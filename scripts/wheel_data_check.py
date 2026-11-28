"""The wheel's data at a release candidate: RC item `WHEEL-DATA` of the standing release procedure.

RP (`docs/derivations/release-procedure.md`) §3.6 moves V03.A17's ship-set and E01-data
inspection and V03.A19's fresh-venv probe out of the per-release script `scripts/v03_rc.py`
(step 17e) into this one, so that the item's script is a standing owner (§3.3). The checks and
their ids are 17e's; `scripts/v03_rc.py` itself is legacy and unchanged.

At `--commit C` (the checkout must be at C):

- `wheel.built`: `scripts/t08_dist.py --commit C` exits 0 and its record passes, so the wheel is
  T08.A43's, built from `git archive` of C. Step 3 judges T08.A43 itself on CI; here the build is
  only the input to the checks below.
- `a17.ship_set`: the wheel holds each ship-set file of `benchmarks/v03/registration.json` once,
  at `openflowsheet/_data/<path>`, with the repository's SHA-256; `a17.e01_data`: E01's seven data
  files of `docs/e01-data-licences.json` once each, with the recorded SHA-256;
  `a17.no_repository_only_file`: no member ends in a registered repository-only path.
- `a19.fresh_venv`: a fresh venv, `requirements.lock`, then the wheel with `--no-deps`, and the
  two probes, each exit 0; `a19.site_packages`, `a19.a` … `a19.d`: V03.A19 (a)–(d) from the probe
  run in that venv with `-I` from an empty directory; (c) equals the checkout's answers bitwise
  (every float as `float.hex`); `a19.probe_outputs`: both probe documents exist.

With `--f1-f3`, RC item `WHEEL-F1-F3` (line 0.5's design note `docs/briefs/REL050-line-0.5.md`
D-5): the installed package *uses* F1's and F3's package data, which neither a v1 solve nor a
replay reads, so a runtime file read from a repository path, or left undeclared, would otherwise
ship broken and pass every other step.

- `wheel.built` (WF-1): as above.
- `f1f3.probes` (WF-2): the probe runs in a fresh venv (`requirements.lock`, then the wheel
  `--no-deps`) with `-I` from an empty directory, importing from `site-packages`, and once in the
  checkout at C, importing from its `src/`; both exit 0 and find no entry point in group
  `openflowsheet.extensions` (WF-3 compares built-in registries only).
- `f1.registry_sha256` (WF-3): `list_capabilities()` through the Python binding of a fresh
  in-memory project returns a `CapabilityPage` in both, and the two `registry_sha256` are equal
  64-hex strings.
- `f3.legacy_records` (WF-4, as restated by the design-lane review REL050-R, Ruling 1): on each
  side, `search_records(limit=200)` through `next_cursor` to the end, in at most ceil(N/200) + 1
  pages, gives only items whose `store` is `legacy`, and their sorted `(id, record_sha256)` list
  equals the sorted `(id, sha256)` list of the index records over that side's files. Both lists
  are read here from `src/openflowsheet/records/legacy_index.json` in `git archive` of C, not
  through the code under test. The checkout's files are every entry of `files` (N records); the
  installed side's are those whose `path` P is package data at C, `openflowsheet/_data/P` being a
  key of `scripts/t08_dist.py`'s `expected_package_files` (N_pkg records). N >= 1 and N_pkg >= 1.
  The sides differ by ADR 0061 D8: a legacy file that is not package data is not available in a
  wheel and contributes no records. The probe itself stops after `PROBE_MAX_PAGES` pages and
  records `pagination did not end`, so a cursor that never ends fails the check instead of
  hanging it.

With `--f2`, RC item `WHEEL-F2` (line 0.6's design note `docs/briefs/REL060-line-0.6.md` D-5):
the installed package *uses* F2's data on the v2 route (its schemas, the legacy index the
lowering reads), which neither a v1 solve nor a replay reaches. No floating point is compared.

- `wheel.built` (WV-1): as above.
- `f2.inputs`: the script writes, in the checkout at C, for each R of `F2_STATES` the v1 document
  (`scripts/corpus_identity.py` `revision_document`) and its raised v2 document, and N, the raised
  `g8/SYN-001-T06-NET02` with `materials.thermal_coordinate` `h_mass`; each raised document has
  `schema_version` 2 and N differs from its source only at `/materials/thermal_coordinate`. The
  SHA-256 of each document's canonical bytes is recorded. Both probes read these as data.
- `f2.probes` (WV-2): as WF-2, both probes with `F2_THREADS` = 1 (each probe records them).
- `f2.v2_runs_as_v1` (WV-3): on each side, each document committed in a fresh in-memory project
  gives `committed` and `READY_FOR_SIMULATION`, its `default` solve `CONVERGED`, and the run
  manifest's `artifact_r0_sha256` and `artifacts` of v2 equal v1's (ADR 0062 D8).
- `f2.r0_registered` (WV-4): on each side, each R's v2 `artifact_r0_sha256` equals F0's
  registered M3 of `benchmarks/f0/corpus.json` at C, read by `git show`, not through the code
  under test.
- `f2.refusal` (WV-5): on each side, `check_admission(revision=N)` raises `revision_unsupported`
  with `detail.unbound` exactly `F2_REFUSAL`, and the base's v2 document is admitted.

    python scripts/wheel_data_check.py --commit C [--out DIR] [--f1-f3 | --f2]
    <venv>/bin/python -I scripts/wheel_data_check.py probe --out J [--in-checkout] [--f1-f3]
    <venv>/bin/python -I scripts/wheel_data_check.py probe --f2 --inputs I --out J [--in-checkout]

The work directory is `--out`, or a temporary directory removed afterwards. The checks are
printed one per line, then the document of findings as one JSON line, then
`wheel data check: PASS|FAIL` (with `--f1-f3`, `wheel data check (F1, F3): PASS|FAIL`; with
`--f2`, `wheel data check (F2): PASS|FAIL`); with `--out`, the document is also
`<out>/wheel-data-check.json` (`<out>/wheel-f1f3-check.json`, `<out>/wheel-f2-check.json`).
Exit 0 iff every check passes, 1 otherwise, 2 when the checkout is not at C.

The probe imports only the standard library and the installed `openflowsheet`, so this module
imports nothing else at its top level.
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REGISTRATION = Path("benchmarks/v03/registration.json")
E01_DATA = Path("docs/e01-data-licences.json")
#: V03.A17: E01's data files in the wheel.
E01_FILE_COUNT = 7
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
#: WHEEL-F1-F3: the entry-point group WF-2 requires empty in both probes, the committed index
#: whose records WF-4 lists, the form of a registry digest, WF-4's page size, and the probe's
#: own bound on pages (REL050-R F-3), which holds well above WF-4's ceil(N/200) + 1.
EXTENSIONS_GROUP = "openflowsheet.extensions"
LEGACY_INDEX = Path("src/openflowsheet/records/legacy_index.json")
HEX64 = re.compile("[0-9a-f]{64}")
PAGE_LIMIT = 200
PROBE_MAX_PAGES = 100
#: WHEEL-F2: the states R (`<set>`, `<name>`) of WV-3 and WV-4, the base N is raised from, the
#: pointer at which N differs from it, WV-5's refusal (ADR 0062 D12, F2 decision WO6b-5), the
#: thread variables both probes run with (WV-2), and F0's registry, whose M3 is WV-4's expectation.
F2_STATES = (("g8", "SYN-001-T06-NET02"), ("s11-gp", "GP-C1"))
F2_BASE = "g8/SYN-001-T06-NET02"
THERMAL_COORDINATE = "/materials/thermal_coordinate"
F2_REFUSAL = "unsupported(construct_unavailable(thermal_coordinate:h_mass, F6))"
F2_THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
F0_REGISTRY = Path("benchmarks/f0/corpus.json")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# -- V03.A17 over the wheel's members ------------------------------------------------------------


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


# -- V03.A19 -------------------------------------------------------------------------------------


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
            raise SystemExit("probe --in-checkout: openflowsheet is not imported from a checkout")
        found["c"] = answers(WilsonIdealGasProvider(records))
        return found
    from openflowsheet.application.binding_common import Unbound  # noqa: PLC0415
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


# -- WHEEL-F1-F3 ---------------------------------------------------------------------------------


def _raised(error: BaseException) -> dict[str, str]:
    return {"type": type(error).__name__, "message": str(error)}


def probe_f1f3(checkout: bool) -> dict[str, Any]:
    """WF-2 to WF-4's probe through the Python binding of a fresh in-memory project: the entry
    points of `EXTENSIONS_GROUP`, the capability page's `registry_sha256`, and every record
    `search_records` lists. A call that raises is recorded by its type and message, so that the
    check it feeds fails by name; so is a cursor that has not ended after `PROBE_MAX_PAGES`."""
    import importlib.metadata  # noqa: PLC0415

    import openflowsheet  # noqa: PLC0415

    found: dict[str, Any] = {
        "module_file": openflowsheet.__file__,
        "version": openflowsheet.__version__,
        "entry_points": sorted(
            f"{point.name} = {point.value}"
            for point in importlib.metadata.entry_points(group=EXTENSIONS_GROUP)
        ),
    }
    if checkout and not Path(openflowsheet.__file__).resolve().is_relative_to(ROOT / "src"):
        raise SystemExit(f"probe --in-checkout --f1-f3: openflowsheet is not imported from {ROOT}")
    from openflowsheet.application.local import LocalApplication  # noqa: PLC0415

    try:
        application = LocalApplication.in_memory()
    except Exception as error:  # noqa: BLE001 - WF-3 and WF-4 record what was raised
        found["capabilities"] = found["records"] = {"error": _raised(error)}
        return found
    with application:
        try:
            page = application.list_capabilities()
            found["capabilities"] = {
                "page": type(page).__name__,
                "registry_sha256": page.registry_sha256,
            }
        except Exception as error:  # noqa: BLE001
            found["capabilities"] = {"error": _raised(error)}
        try:
            items: list[dict[str, Any]] = []
            pages = 0
            cursor = None
            while pages < PROBE_MAX_PAGES:
                records = application.search_records(limit=PAGE_LIMIT, cursor=cursor)
                pages += 1
                items += [
                    {key: item[key] for key in ("id", "record_sha256", "store")}
                    for item in records.items
                ]
                cursor = records.next_cursor
                if cursor is None:
                    break
            if cursor is None:
                found["records"] = {"pages": pages, "items": items}
            else:
                unended = {"type": "Pagination", "message": "pagination did not end"}
                found["records"] = {"pages": pages, "error": unended}
        except Exception as error:  # noqa: BLE001
            found["records"] = {"error": _raised(error)}
    return found


def legacy_index_pairs(
    index: Mapping[str, Any], paths: Collection[str] | None = None
) -> list[tuple[str, str]]:
    """WF-4's expected list: the sorted `(id, sha256)` pairs of the index's records over its
    `files`, or over those whose `path` is in `paths`."""
    return sorted(
        (record["id"], record["sha256"])
        for entry in index["files"]
        if paths is None or entry["path"] in paths
        for record in entry["records"]
    )


def package_data_legacy_paths(
    index: Mapping[str, Any], package_files: Collection[str]
) -> list[str]:
    """WF-4's installed side: the index's file paths P that are package data, that is whose
    `openflowsheet/_data/P` is in `package_files` (`t08_dist.expected_package_files`' keys)."""
    return sorted(
        entry["path"]
        for entry in index["files"]
        if f"openflowsheet/_data/{entry['path']}" in package_files
    )


def legacy_expectations(tree: Path, commit: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """The committed index of the source tree `tree` and its package-data legacy paths, the
    latter by T08.A43's own reading of `pyproject.toml`; with `commit`, `tree` is first filled
    with `git archive` of it. Host side only: the probe imports nothing outside the standard
    library and `openflowsheet`."""
    import t08_dist  # noqa: PLC0415

    if commit is not None:
        t08_dist.export_commit(commit, tree)
    index = json.loads((tree / LEGACY_INDEX).read_text(encoding="utf-8"))
    package_files = t08_dist.expected_package_files(tree, t08_dist.pyproject(tree))
    return index, package_data_legacy_paths(index, package_files)


def page_bound(count: int) -> int:
    """WF-4's bound on pages for N records: ceil(N/200) + 1."""
    return -(-count // PAGE_LIMIT) + 1


def _listed(document: Mapping[str, Any]) -> list[tuple[str, str]] | None:
    """The sorted `(id, record_sha256)` pairs of a probe, or None unless every item is legacy."""
    items = document.get("records", {}).get("items")
    if not isinstance(items, list) or any(item.get("store") != "legacy" for item in items):
        return None
    return sorted((item.get("id"), item.get("record_sha256")) for item in items)


def _paged(document: Mapping[str, Any], bound: int) -> bool:
    pages = document.get("records", {}).get("pages")
    return isinstance(pages, int) and 1 <= pages <= bound


def f1f3_findings(
    installed: Mapping[str, Any],
    checkout: Mapping[str, Any],
    index_pairs: Sequence[tuple[str, str]],
    package_pairs: Sequence[tuple[str, str]],
) -> dict[str, bool]:
    """WF-2's probe clauses, WF-3 and WF-4 from the two probe documents and the index's lists:
    `index_pairs` over every file (the checkout's, N), `package_pairs` over the package-data
    files (the installed side's, N_pkg)."""
    sides = (installed, checkout)
    bound = page_bound(len(index_pairs))
    digests = [side.get("capabilities", {}).get("registry_sha256") for side in sides]
    listed = [_listed(side) for side in sides]
    return {
        "site_packages": "site-packages" in str(installed.get("module_file", "")),
        "no_extensions": all(side.get("entry_points") == [] for side in sides),
        "registry_sha256": all(
            side.get("capabilities", {}).get("page") == "CapabilityPage" for side in sides
        )
        and all(isinstance(digest, str) and HEX64.fullmatch(digest) for digest in digests)
        and digests[0] == digests[1],
        "legacy_records": len(index_pairs) >= 1
        and len(package_pairs) >= 1
        and all(_paged(side, bound) for side in sides)
        and listed[0] == sorted(package_pairs)
        and listed[1] == sorted(index_pairs),
    }


# -- WHEEL-F2 ------------------------------------------------------------------------------------


def canonical(document: Any) -> bytes:
    """A JSON document's canonical bytes: sorted keys, separators `,` `:`, UTF-8."""
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def differences(a: Any, b: Any, pointer: str = "") -> list[str]:
    """The JSON pointers at which `a` and `b` differ: a member present in one only, a list of
    another length, or unequal values (the deepest pointer of each)."""
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        found: list[str] = []
        for key in sorted(set(a) | set(b)):
            step = f"{pointer}/{str(key).replace('~', '~0').replace('/', '~1')}"
            found += differences(a[key], b[key], step) if key in a and key in b else [step]
        return found
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [
            p
            for i, (x, y) in enumerate(zip(a, b, strict=True))
            for p in differences(x, y, f"{pointer}/{i}")
        ]
    return [] if type(a) is type(b) and a == b else [pointer]


def f2_inputs(coordinate: str = "h_mass") -> dict[str, Any]:
    """The probes' inputs, built in the checkout: for each R of `F2_STATES` its v1 document and
    the raised v2 document; and N, the base's v2 document with `materials.thermal_coordinate`
    `coordinate` (`h_mass` for the item; a test's control builds it with `T`). Host side only."""
    import copy  # noqa: PLC0415

    import corpus_identity  # noqa: PLC0415

    from openflowsheet.models.revision_flowsheet import legacy_providers  # noqa: PLC0415
    from openflowsheet.revision_v2.raise_v1 import raise_v1  # noqa: PLC0415

    revisions: dict[str, dict[str, Any]] = {}
    for run_set, name in F2_STATES:
        v1 = corpus_identity.revision_document(run_set, name)
        revisions[f"{run_set}/{name}"] = {"v1": v1, "v2": raise_v1(v1, legacy_providers())}
    refused = copy.deepcopy(revisions[F2_BASE]["v2"])
    refused["materials"]["thermal_coordinate"] = coordinate
    return {"revisions": revisions, "refused": refused}


def inputs_findings(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """`f2.inputs`: the five documents' canonical SHA-256 (`<R>:v1`, `<R>:v2`, `N`), the pointers
    at which N differs from the base's v2 document, and whether every raised document has
    `schema_version` 2 and N differs only at `THERMAL_COORDINATE`, there `h_mass`."""
    revisions = inputs["revisions"]
    refused = inputs["refused"]
    digests = {
        f"{key}:{version}": sha256(canonical(revisions[key][version]))
        for key in sorted(revisions)
        for version in ("v1", "v2")
    }
    digests["N"] = sha256(canonical(refused))
    differ = differences(revisions[F2_BASE]["v2"], refused)
    raised = [revisions[key]["v2"] for key in revisions] + [refused]
    ok = (
        sorted(revisions) == sorted(f"{s}/{n}" for s, n in F2_STATES)
        and all(document.get("schema_version") == 2 for document in raised)
        and differ == [THERMAL_COORDINATE]
        and refused["materials"]["thermal_coordinate"] == "h_mass"
    )
    return {"documents": digests, "differences": differ, "ok": ok}


def registered_r0(registry_text: str) -> dict[str, Any]:
    """WV-4's expectation: each R's `artifact_r0_sha256` of F0's M3 in `registry_text` (the
    registry's bytes at C), or None where it holds none."""
    measures = json.loads(registry_text).get("measures", {}).get("M3", {})
    return {
        f"{s}/{n}": measures.get(f"{s}/{n}", {}).get("artifact_r0_sha256") for s, n in F2_STATES
    }


def _committed_run(document: Mapping[str, Any]) -> dict[str, Any]:
    """WV-3 for one document in a fresh in-memory project: commit its members other than
    `revision_id` and `parent_revision` as one `Change`, solve with `default`, read the run
    manifest. What raises is recorded by its type and message."""
    from openflowsheet.application.local import LocalApplication  # noqa: PLC0415
    from openflowsheet.application.transaction_types import Change, Edit  # noqa: PLC0415

    body = {k: v for k, v in document.items() if k not in ("revision_id", "parent_revision")}
    found: dict[str, Any] = {}
    try:
        with LocalApplication.in_memory() as application:
            change = Change(edits=tuple(Edit("set", (key,), value) for key, value in body.items()))
            committed = application.commit_change(change, None, "wheel-f2")
            found["status"] = exact(committed.status)
            validation = committed.validation
            found["validation"] = exact(validation.status) if validation is not None else None
            if committed.revision_id is None:
                found["detail"] = str(committed)[:2000]
                return found
            result = application.solve(committed.revision_id, "default")
            found["outcome"] = exact(result.outcome)
            manifests = [output for output in result.outputs if output.kind == "run_manifest"]
            found["run_manifests"] = len(manifests)
            if len(manifests) == 1:
                manifest = json.loads(application.artifact_bytes(manifests[0].artifact_id))
                found["artifact_r0_sha256"] = manifest.get("artifact_r0_sha256")
                found["artifacts"] = manifest.get("artifacts")
    except Exception as error:  # noqa: BLE001 - WV-3 records what was raised
        found["error"] = _raised(error)
    return found


def _admission(document: Mapping[str, Any]) -> dict[str, Any]:
    """WV-5 for one document: `{"raised": {code, unbound}}` for an `ApplicationError`,
    `{"admitted": <report.admitted>}` when a report is returned, `{"error": …}` for anything
    else."""
    from openflowsheet.application.errors import ApplicationError  # noqa: PLC0415
    from openflowsheet.application.local import LocalApplication  # noqa: PLC0415

    try:
        with LocalApplication.in_memory() as application:
            report = application.check_admission(revision=document)
    except ApplicationError as error:
        detail = error.error.detail
        unbound = detail.get("unbound") if isinstance(detail, Mapping) else None
        return {"raised": {"code": error.error.code, "unbound": unbound}}
    except Exception as error:  # noqa: BLE001
        return {"error": _raised(error)}
    return {"admitted": bool(report.admitted)}


def probe_f2(checkout: bool, inputs_path: Path) -> dict[str, Any]:
    """WV-2 to WV-5's probe: the entry points of `EXTENSIONS_GROUP`, the thread variables, each
    input document's committed run (WV-3) and the admission of N and of the base's v2 (WV-5)."""
    import importlib.metadata  # noqa: PLC0415

    import openflowsheet  # noqa: PLC0415

    found: dict[str, Any] = {
        "module_file": openflowsheet.__file__,
        "version": openflowsheet.__version__,
        "entry_points": sorted(
            f"{point.name} = {point.value}"
            for point in importlib.metadata.entry_points(group=EXTENSIONS_GROUP)
        ),
        "threads": {name: os.environ.get(name) for name in F2_THREADS},
    }
    if checkout and not Path(openflowsheet.__file__).resolve().is_relative_to(ROOT / "src"):
        raise SystemExit(f"probe --in-checkout --f2: openflowsheet is not imported from {ROOT}")
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
    found["runs"] = {
        key: {version: _committed_run(pair[version]) for version in ("v1", "v2")}
        for key, pair in sorted(inputs["revisions"].items())
    }
    found["refusal"] = {
        "N": _admission(inputs["refused"]),
        "v2": _admission(inputs["revisions"][F2_BASE]["v2"]),
    }
    return found


def _ran(run: Mapping[str, Any]) -> bool:
    """One document's WV-3 clauses: committed, ready, converged, a manifest with a 64-hex r0 and
    a name-to-64-hex `artifacts` index that holds `solution-state.json`."""
    artifacts = run.get("artifacts")
    return (
        run.get("status") == "committed"
        and run.get("validation") == "READY_FOR_SIMULATION"
        and run.get("outcome") == "CONVERGED"
        and run.get("run_manifests") == 1
        and isinstance(run.get("artifact_r0_sha256"), str)
        and HEX64.fullmatch(run["artifact_r0_sha256"]) is not None
        and isinstance(artifacts, dict)
        and "solution-state.json" in artifacts
        and all(isinstance(v, str) and HEX64.fullmatch(v) for v in artifacts.values())
    )


def f2_findings(
    installed: Mapping[str, Any], checkout: Mapping[str, Any], registered: Mapping[str, Any]
) -> dict[str, bool]:
    """WV-2's probe clauses and WV-3 to WV-5 from the two probe documents and F0's registered
    M3 (`registered_r0`)."""
    sides = (installed, checkout)
    keys = sorted(f"{s}/{n}" for s, n in F2_STATES)

    def runs(side: Mapping[str, Any]) -> dict[str, Any]:
        found = side.get("runs")
        return found if isinstance(found, dict) and sorted(found) == keys else {}

    def twin(side: Mapping[str, Any], key: str) -> bool:
        pair = runs(side).get(key, {})
        v1, v2 = pair.get("v1", {}), pair.get("v2", {})
        return (
            _ran(v1)
            and _ran(v2)
            and v2["artifact_r0_sha256"] == v1["artifact_r0_sha256"]
            and v2["artifacts"] == v1["artifacts"]
        )

    def r0(side: Mapping[str, Any], key: str) -> Any:
        return runs(side).get(key, {}).get("v2", {}).get("artifact_r0_sha256")

    refused = {"raised": {"code": "revision_unsupported", "unbound": F2_REFUSAL}}
    return {
        "site_packages": "site-packages" in str(installed.get("module_file", "")),
        "no_extensions": all(side.get("entry_points") == [] for side in sides),
        "threads": all(side.get("threads") == dict.fromkeys(F2_THREADS, "1") for side in sides),
        "v2_runs_as_v1": all(bool(runs(side)) and twin(side, k) for side in sides for k in keys),
        "r0_registered": all(
            isinstance(registered.get(k), str) and HEX64.fullmatch(registered[k]) for k in keys
        )
        and all(r0(side, k) == registered[k] for side in sides for k in keys),
        "refusal": all(
            side.get("refusal", {}).get("N") == refused
            and side.get("refusal", {}).get("v2") == {"admitted": True}
            for side in sides
        ),
    }


# -- the item --------------------------------------------------------------------------------------


def _check(checks: list[dict[str, Any]], check_id: str, passed: bool, **value: Any) -> None:
    checks.append({"id": check_id, "result": "pass" if passed else "fail", **value})


def _run(argv: Sequence[str], log: Path, cwd: Path = ROOT, **env: str) -> int:
    """Run `argv` without the caller's PYTHONPATH (plus `env`), its output to `log`."""
    environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"} | env
    with log.open("w", encoding="utf-8") as stream:
        done = subprocess.run(
            list(argv), cwd=cwd, env=environment, stdout=stream, stderr=subprocess.STDOUT
        )
    return done.returncode


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _built(commit: str, work: Path, logs: Path, checks: list[dict[str, Any]]) -> Path:
    """`wheel.built`: `scripts/t08_dist.py` at `commit` into `<work>/dist`, which is returned."""
    dist = work / "dist"
    script = ROOT / "scripts" / "t08_dist.py"
    built = _run(
        [sys.executable, str(script), "--out", str(dist), "--commit", commit], logs / "dist.log"
    )
    record_path = dist / "t08-a43-dist.json"
    record = _json(record_path)
    _check(
        checks,
        "wheel.built",
        built == 0 and record.get("passed") is True,
        exit_code=built,
        record_sha256=sha256(record_path.read_bytes()) if record_path.exists() else None,
    )
    return dist


def _fresh_venv(work: Path, wheel: Path | None, logs: Path, exits: dict[str, int | None]) -> Path:
    """A fresh venv in `<work>/wheelvenv`: `requirements.lock`, then `wheel` with `--no-deps`;
    the exit codes go to `exits` (`venv`, `lock`, `wheel`), and its python is returned."""
    venv = work / "wheelvenv"
    exits["venv"] = _run([sys.executable, "-m", "venv", str(venv)], logs / "venv.log")
    python = venv / "bin" / "python"
    if exits["venv"] == 0:
        pip = [str(python), "-m", "pip", "install"]
        exits["lock"] = _run([*pip, "-r", str(ROOT / "requirements.lock")], logs / "lock.log")
        if exits["lock"] == 0 and wheel is not None:
            exits["wheel"] = _run([*pip, "--no-deps", str(wheel)], logs / "wheel.log")
    return python


def run_checks(commit: str, work: Path) -> list[dict[str, Any]]:
    """Build the wheel at `commit` into `work`, install it into a fresh venv, probe, judge."""
    logs = work / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    dist = _built(commit, work, logs, checks)
    registration = json.loads((ROOT / REGISTRATION).read_text(encoding="utf-8"))["ship_set"]
    ships = {path: sha256((ROOT / path).read_bytes()) for path in registration["ships"]}
    e01 = json.loads((ROOT / E01_DATA).read_text(encoding="utf-8"))["files"]
    wheel, members = wheel_members(dist)
    findings = wheel_findings(
        members, ships, {row["path"]: row["sha256"] for row in e01}, registration["repository_only"]
    )
    _check(
        checks,
        "a17.ship_set",
        bool(members) and all(row["ok"] for row in findings["ship_set"].values()),
        wheel=wheel.name if wheel else None,
        members=len(members),
        rows=findings["ship_set"],
    )
    _check(
        checks,
        "a17.e01_data",
        len(findings["e01_data"]) == E01_FILE_COUNT
        and all(row["ok"] for row in findings["e01_data"].values()),
        rows=findings["e01_data"],
    )
    _check(
        checks,
        "a17.no_repository_only_file",
        bool(members) and not findings["repository_only_present"],
        present=findings["repository_only_present"],
    )
    installed_path = work / "a19-installed.json"
    checkout_path = work / "a19-checkout.json"
    probe_cwd = work / "probe-cwd"
    probe_cwd.mkdir(exist_ok=True)
    me = str(Path(__file__).resolve())
    exits: dict[str, int | None] = dict.fromkeys(("venv", "lock", "wheel", "probe", "checkout"))
    python = _fresh_venv(work, wheel, logs, exits)
    if exits["wheel"] == 0:
        exits["probe"] = _run(
            [str(python), "-I", me, "probe", "--out", str(installed_path)],
            logs / "probe.log",
            cwd=probe_cwd,
        )
    exits["checkout"] = _run(
        [sys.executable, me, "probe", "--in-checkout", "--out", str(checkout_path)],
        logs / "checkout.log",
        PYTHONPATH=str(ROOT / "src"),
    )
    _check(checks, "a19.fresh_venv", all(code == 0 for code in exits.values()), exits=exits)
    installed = _json(installed_path)
    checkout = _json(checkout_path)
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
        _check(checks, f"a19.{name}", ok, **said)
    _check(
        checks,
        "a19.probe_outputs",
        installed_path.exists() and checkout_path.exists(),
        installed_sha256=sha256(installed_path.read_bytes()) if installed_path.exists() else None,
        checkout_sha256=sha256(checkout_path.read_bytes()) if checkout_path.exists() else None,
        module_file=installed.get("module_file"),
        version=installed.get("version"),
    )
    return checks


def run_f1f3_checks(commit: str, work: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """WHEEL-F1-F3: build the wheel at `commit` into `work`, install it into a fresh venv, run
    the F1/F3 probe there and in the checkout, judge; the checks and the findings."""
    logs = work / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    wheel, _ = wheel_members(_built(commit, work, logs, checks))
    installed_path = work / "f1f3-installed.json"
    checkout_path = work / "f1f3-checkout.json"
    probe_cwd = work / "probe-cwd"
    probe_cwd.mkdir(exist_ok=True)
    me = str(Path(__file__).resolve())
    exits: dict[str, int | None] = dict.fromkeys(("venv", "lock", "wheel", "probe", "checkout"))
    python = _fresh_venv(work, wheel, logs, exits)
    if exits["wheel"] == 0:
        exits["probe"] = _run(
            [str(python), "-I", me, "probe", "--f1-f3", "--out", str(installed_path)],
            logs / "f1f3-probe.log",
            cwd=probe_cwd,
        )
    exits["checkout"] = _run(
        [sys.executable, me, "probe", "--f1-f3", "--in-checkout", "--out", str(checkout_path)],
        logs / "f1f3-checkout.log",
        PYTHONPATH=str(ROOT / "src"),
    )
    installed = _json(installed_path)
    checkout = _json(checkout_path)
    index, package_paths = legacy_expectations(work / "export", commit)
    expected = {
        "installed": legacy_index_pairs(index, package_paths),
        "checkout": legacy_index_pairs(index),
    }
    found = f1f3_findings(installed, checkout, expected["checkout"], expected["installed"])
    sides = {"installed": installed, "checkout": checkout}
    _check(
        checks,
        "f1f3.probes",
        all(code == 0 for code in exits.values())
        and found["site_packages"]
        and found["no_extensions"],
        exits=exits,
        module_file={side: doc.get("module_file") for side, doc in sides.items()},
        entry_points={side: doc.get("entry_points") for side, doc in sides.items()},
        probe_sha256={
            side: sha256(path.read_bytes()) if path.exists() else None
            for side, path in (("installed", installed_path), ("checkout", checkout_path))
        },
    )
    digests = {
        side: doc.get("capabilities", {}).get("registry_sha256") for side, doc in sides.items()
    }
    _check(
        checks,
        "f1.registry_sha256",
        found["registry_sha256"],
        **{side: doc.get("capabilities") for side, doc in sides.items()},
    )
    listed = {side: _listed(doc) for side, doc in sides.items()}
    records = {
        side: {
            "pages": doc.get("records", {}).get("pages"),
            "items": len(doc.get("records", {}).get("items") or []),
            "error": doc.get("records", {}).get("error"),
            "all_legacy": listed[side] is not None,
            "sha256": sha256(json.dumps(listed[side]).encode())
            if listed[side] is not None
            else None,
            "expected": len(expected[side]),
            "equals_index": listed[side] == expected[side],
        }
        for side, doc in sides.items()
    }
    count = len(expected["checkout"])
    legacy = {"n": count, "n_pkg": len(expected["installed"]), "package_data_paths": package_paths}
    _check(
        checks,
        "f3.legacy_records",
        found["legacy_records"],
        **legacy,
        page_bound=page_bound(count),
        **records,
    )
    findings = {
        "registry_sha256": digests,
        "legacy_records": legacy,
        "wheel_sha256": sha256(wheel.read_bytes()) if wheel is not None else None,
    }
    return checks, findings


def run_f2_checks(commit: str, work: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """WHEEL-F2: build the wheel at `commit` into `work`, write the inputs in the checkout,
    install the wheel into a fresh venv, run the F2 probe there and in the checkout, judge; the
    checks and the findings."""
    logs = work / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    wheel, _ = wheel_members(_built(commit, work, logs, checks))
    inputs_path = work / "f2-inputs.json"
    try:
        inputs = f2_inputs()
    except Exception as error:  # noqa: BLE001 - f2.inputs fails by name; the probes find no file
        _check(checks, "f2.inputs", False, error=_raised(error))
        documents: dict[str, str] = {}
    else:
        inputs_path.write_bytes(canonical(inputs))
        said = inputs_findings(inputs)
        documents = said["documents"]
        _check(checks, "f2.inputs", said["ok"], **said)
    installed_path = work / "f2-installed.json"
    checkout_path = work / "f2-checkout.json"
    probe_cwd = work / "probe-cwd"
    probe_cwd.mkdir(exist_ok=True)
    me = str(Path(__file__).resolve())
    threads = dict.fromkeys(F2_THREADS, "1")
    flags = ["probe", "--f2", "--inputs", str(inputs_path)]
    exits: dict[str, int | None] = dict.fromkeys(("venv", "lock", "wheel", "probe", "checkout"))
    python = _fresh_venv(work, wheel, logs, exits)
    if exits["wheel"] == 0:
        exits["probe"] = _run(
            [str(python), "-I", me, *flags, "--out", str(installed_path)],
            logs / "f2-probe.log",
            cwd=probe_cwd,
            **threads,
        )
    exits["checkout"] = _run(
        [sys.executable, me, *flags, "--in-checkout", "--out", str(checkout_path)],
        logs / "f2-checkout.log",
        cwd=ROOT,
        PYTHONPATH=str(ROOT / "src"),
        **threads,
    )
    sides = {"installed": _json(installed_path), "checkout": _json(checkout_path)}
    shown = subprocess.run(
        ["git", "show", f"{commit}:{F0_REGISTRY.as_posix()}", "--"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    registered = registered_r0(shown.stdout if shown.returncode == 0 else "{}")
    found = f2_findings(sides["installed"], sides["checkout"], registered)
    _check(
        checks,
        "f2.probes",
        all(code == 0 for code in exits.values())
        and found["site_packages"]
        and found["no_extensions"]
        and found["threads"],
        exits=exits,
        module_file={side: doc.get("module_file") for side, doc in sides.items()},
        entry_points={side: doc.get("entry_points") for side, doc in sides.items()},
        threads={side: doc.get("threads") for side, doc in sides.items()},
        probe_sha256={
            side: sha256(path.read_bytes()) if path.exists() else None
            for side, path in (("installed", installed_path), ("checkout", checkout_path))
        },
    )
    runs = {side: doc.get("runs") or {} for side, doc in sides.items()}

    def each(field: str) -> dict[str, Any]:
        return {
            side: {
                key: {version: run.get(field) for version, run in pair.items()}
                for key, pair in found_runs.items()
            }
            for side, found_runs in runs.items()
        }

    r0 = each("artifact_r0_sha256")
    artifacts_sha256 = {
        side: {
            key: {
                version: sha256(canonical(run["artifacts"])) if "artifacts" in run else None
                for version, run in pair.items()
            }
            for key, pair in found_runs.items()
        }
        for side, found_runs in runs.items()
    }
    _check(
        checks,
        "f2.v2_runs_as_v1",
        found["v2_runs_as_v1"],
        r0=r0,
        artifacts_sha256=artifacts_sha256,
        status=each("status"),
        validation=each("validation"),
        outcome=each("outcome"),
        error=each("error"),
    )
    _check(checks, "f2.r0_registered", found["r0_registered"], registered=registered, r0=r0)
    refusal = {side: doc.get("refusal") for side, doc in sides.items()}
    _check(checks, "f2.refusal", found["refusal"], expected=F2_REFUSAL, **refusal)
    findings = {
        "documents": documents,
        "r0": r0,
        "registered": registered,
        "artifacts_sha256": artifacts_sha256,
        "refusal": {
            side: ((said or {}).get("N") or {}).get("raised", {}).get("unbound")
            for side, said in refusal.items()
        },
        "wheel_sha256": sha256(wheel.read_bytes()) if wheel is not None else None,
    }
    return checks, findings


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("mode", nargs="?", choices=("probe",), help="probe: A19's probe only")
    parser.add_argument("--commit", help="C; the checkout must be at it")
    parser.add_argument("--out", type=Path, help="the work directory (default: a temporary one)")
    parser.add_argument(
        "--in-checkout", action="store_true", help="probe: the checkout's (c) answers only"
    )
    item = parser.add_mutually_exclusive_group()
    item.add_argument(
        "--f1-f3", action="store_true", help="RC item WHEEL-F1-F3 (or its probe) instead"
    )
    item.add_argument("--f2", action="store_true", help="RC item WHEEL-F2 (or its probe) instead")
    parser.add_argument("--inputs", type=Path, help="probe --f2: the inputs the item wrote")
    arguments = parser.parse_args(argv)
    if arguments.mode == "probe":
        if arguments.out is None:
            parser.error("probe needs --out")
        if arguments.f2:
            if arguments.inputs is None:
                parser.error("probe --f2 needs --inputs")
            found = probe_f2(arguments.in_checkout, arguments.inputs)
        elif arguments.f1_f3:
            found = probe_f1f3(arguments.in_checkout)
        else:
            found = probe(arguments.in_checkout)
        arguments.out.write_text(json.dumps(found, indent=1, sort_keys=True) + "\n", "utf-8")
        return 0
    if arguments.commit is None:
        parser.error("--commit is required")
    head = _head()
    if head != arguments.commit:
        print(f"refused: {ROOT} is at {head}, not at {arguments.commit}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="wheel-data-") as scratch:
        work = arguments.out or Path(scratch)
        work.mkdir(parents=True, exist_ok=True)
        if arguments.f2:
            checks, findings = run_f2_checks(head, work)
            document = {
                "format": "wheel-f2-check-v1",
                "commit": head,
                "findings": findings,
                "checks": checks,
            }
            name, title = "wheel-f2-check.json", "wheel data check (F2)"
        elif arguments.f1_f3:
            checks, findings = run_f1f3_checks(head, work)
            document = {
                "format": "wheel-f1f3-check-v1",
                "commit": head,
                "findings": findings,
                "checks": checks,
            }
            name, title = "wheel-f1f3-check.json", "wheel data check (F1, F3)"
        else:
            checks = run_checks(head, work)
            document = {"format": "wheel-data-check-v1", "commit": head, "checks": checks}
            name, title = "wheel-data-check.json", "wheel data check"
        if arguments.out is not None:
            text = json.dumps(document, indent=1, sort_keys=True) + "\n"
            (work / name).write_text(text, encoding="utf-8")
    for entry in checks:
        print(f"{entry['result'].upper():4} {entry['id']}")
    print(json.dumps(document, sort_keys=True, separators=(",", ":")))
    passed = all(entry["result"] == "pass" for entry in checks)
    print(f"{title}: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
