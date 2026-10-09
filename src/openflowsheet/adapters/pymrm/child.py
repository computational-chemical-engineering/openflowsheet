"""The reactor child: one attempt of the pinned 1D ammonia reactor (M02 design note §2.2-§2.4;
ADR 0033 D1, D2; M01 spec §8.3-§8.12).

Run by `adapters.external.launcher` as `<env>/venv/bin/python -I child.py [--handshake]`, in a
fresh process per attempt, inside the environment that `adapters.pymrm.env build` made from pins.
It ships in the wheel, but **no module of `openflowsheet` imports it**, and it imports nothing
outside the standard library, numpy, scipy, pymrm and the pinned `reactor` package (a default-gate
AST test asserts both). The protocol's constants are literals here, mirrored from
`adapters/external/protocol.py`; a test asserts they are equal.

**Protocol.** One JSON request line on stdin; stdin stays open as the lifeline (its end of file
exits 70); the child's own deadline (`deadline_s` + 30 s) exits 71; an environment that is not
the request's exits 72 with one line of reason on stderr; the answer is one `result.json`, written
atomically in the working directory (the attempt directory), then exit 0. **Every exit is
`os._exit`**: a normal interpreter exit while the lifeline thread is blocked in stdin's buffered
read dies with SIGABRT, which would read as a crash of the model.

**The environment.** Its root is the parent of `NUMBA_CACHE_DIR` (the launcher sets it): the
export of the pinned commit (`export/`, with its tree hash in `export/EXPORT_TREE_SHA256`), the
merged species database, the lock, the venv and `env-manifest.json`. Every attempt checks the
runner's own hash, the commit and the lock against the request; the handshake (`--handshake`)
also recomputes the export tree hash and the database hash and checks every installed version
against the lock, then reports the full environment fingerprint. An evaluation reports the cheap
part (§2.4), which the worker compares with the handshake's.

**The evaluation** is M01's (spec §8.3-§8.7), derived from `benchmarks/m01/reactor_probe.py`:
the pinned `MembraneReactor1D` with the F-R1 subclass (the five-species backflow inflow), the
geometry of the configured case, every permeance pre-factor zero, the tube's inlet (F_ret_in,
y_ret_in, T_in, p_ret_out = P_in) and coolant (pure N2 at sweep_ratio x F_ret_in, T_in, 1 bar);
the start strategy S1 (cold at the trace inlet), S2 (warm at the true inlet from S1's fields),
S3 (the polish of profile `M01-S123-v2`: `M01-S123-v1`'s, plus one conditional round when A45's
element defect exceeds 10⁻⁷ after it, design note §14.5 D1); then the evaluation's four
acceptance criteria. The first one that fails is the answer `not_accepted` at its registered stage
(`S1`, `S2`, `S3`, `certificate`, `backflow`, `nonpositive_flow`); otherwise the raw outlet —
the retentate's axial face flows at z = L, the last cell's temperature, the Ergun pressure drop,
the coolant's heat uptake and the inlet-face heat loss — with the diagnostics. The pressure
convention and the element defect are the boundary's to judge (Amendment 1). The computation is a
pure function of the request: every limit is a count, never a clock.

**An exception inside the model** (R-251; design note §14.1 B9) is the registered stage
`model_exception`, not a crash: purity makes it recur on every attempt. The window runs from
building the first reactor object through the outlet's extraction (S1, S2, S3, the certificate,
`outlet`); `model_exception` decides what it covers — any `Exception` but `MemoryError`, `OSError`
and their subclasses — and what the diagnostics record (the qualified type name, the message's
first line, the formatted traceback's SHA-256; the traceback itself goes to stderr). Everything
else — an exception outside the window, `MemoryError`, `OSError`, a signal — stays a crash.

**A non-finite value** (design note §14.5 D2) is the registered stage `nonfinite`, not a crash:
before the result is written, `nonfinite_screen` scans it whole (`nonfinite_paths`). An `outlet`
with any non-finite value becomes `not_accepted` at `nonfinite`, without its `tube_outlet`; a
`not_accepted` keeps its stage (the first refusal wins). Either way every non-finite value is
written as null and its JSON pointer listed in `diagnostics.nonfinite_paths`. The child writes no
NaN of its own: a value the group's code does not return is null. `_write` keeps
`allow_nan=False`, so a non-finite value that escaped the scan is still a crash.

**Evidence-only switches.** `OFS_EVIDENCE_S2_DT_INIT` (S2's `dt_init`, M01.A42) and
`OFS_EVIDENCE_BACKFLOW_ALT` (the backflow inflow `[0, 0, 0, 1, 0]`, M01.A44) are read from the
environment, which the launcher builds from an allowlist: only its Python-only `test_environment`
argument can add them, so no variant, request or API reaches them. They enter the handshake's
fingerprint (`env_allowlist`), so a result made with one is keyed apart.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import platform
import signal
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = 1
EXIT_LIFELINE_LOST = 70
EXIT_SELF_DEADLINE = 71
EXIT_ENVIRONMENT_MISMATCH = 72
RESULT_FILE = "result.json"
RESULT_TEMPORARY = "result.json.tmp"
HANDSHAKE_ARGUMENT = "--handshake"
OUTCOME_OUTLET = "outlet"
OUTCOME_NOT_ACCEPTED = "not_accepted"
OUTCOME_HANDSHAKE = "handshake"
#: R-251: the stage of an exception the model raised inside its window (`model_exception`).
STAGE_MODEL_EXCEPTION = "model_exception"
#: §14.5 D2: the stage of an evaluation whose result holds a non-finite value.
STAGE_NONFINITE = "nonfinite"
MODEL_EXCEPTION_MESSAGE_LIMIT = 512
SELF_DEADLINE_MARGIN_S = 30.0
DEADLINE_MARGIN_VARIABLE = "OFS_TEST_DEADLINE_MARGIN_S"

#: The environment's layout (`adapters.pymrm.env`), relative to its root.
EXPORT_DIR = "export"
EXPORT_TREE_FILE = "EXPORT_TREE_SHA256"
DATABASE_FILE = "merged-database.json"
LOCK_FILE = "reactor-env.lock"
MANIFEST_FILE = "env-manifest.json"

THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMBA_NUM_THREADS",
)
#: The evidence-only switches (module docstring).
S2_DT_INIT_VARIABLE = "OFS_EVIDENCE_S2_DT_INIT"
BACKFLOW_ALT_VARIABLE = "OFS_EVIDENCE_BACKFLOW_ALT"
BACKFLOW_ALT = [0.0, 0.0, 0.0, 1.0, 0.0]

SPECIES = ["H2", "N2", "NH3", "Ar", "CH4"]
#: M01 spec §8.5: every permeance pre-factor zero (the packed bed of Q6).
PERMEANCE_PREFACTOR = 0.0
#: `calculate_flows`' space velocity, used for its design metrics (the catalyst mass the KPI
#: certificate reads) only: the inlet flow is the tube's, never this.
DESIGN_GHSV_H = 1000.0
DESIGN_H2_N2 = 3.0
#: The solver profile this child implements (M01 spec §8.7); the variant's `profile` must equal it.
PROFILE: dict[str, Any] = {
    "id": "M01-S123-v2",
    "S1": {
        "inlet": "y_NH3 := trace_NH3, renormalized",
        "trace_NH3": 1e-9,
        "solver": "group SOLVER_1D",
        "dt_init": 1e-6,
        "acceptance": "group solver_acceptance, STEADY_STATE_ACCEPT_FACTOR",
    },
    "S2": {
        "inlet": "true",
        "start": "S1 fields (c, p, T)",
        "solver": "group SOLVER_1D",
        "dt_init": 1e-6,
        "acceptance": "group solver_acceptance, STEADY_STATE_ACCEPT_FACTOR",
    },
    "S3": {
        "rtol": 1e-12,
        "atol_factor": 0.1,
        "dt_init": 1.0,
        "max_steps": 400,
        "target": "1e-6*(num_z/100)^2",
        "round2": {
            "when": "the certificate after S3 passed and A45's element defect read after it is "
            "not <= defect_threshold",
            "defect": "max over the elements present in the requested inlet of "
            "|element_defect_rel| (outlet's formula); NaN if any of them is NaN",
            "defect_threshold": 1e-7,
            "target": "S3's target / 10",
            "rtol": 1e-12,
            "atol_factor": 0.1,
            "dt_init": 1.0,
            "max_steps": 400,
            "accepted": "S3 is accepted iff round 2 converged; the certificate is then repeated "
            "on its status and decides",
        },
    },
    "acceptance": [
        "S3 converged at its target",
        "the group's KPI-drift certificate after S3",
        "u_ret > 0 on every face",
        "every axial flow of a species present in the requested inlet > 0",
    ],
}
#: The configuration members this child implements, and their types.
CONFIGURATION: dict[str, type] = {
    "geometry_case": str,
    "num_z": int,
    "sweep_ratio": float,
    "permeance_prefactors": float,
    "coolant": str,
    "backflow": list,
}
ELEMENTS: dict[str, list[int]] = {
    "H": [2, 0, 3, 0, 4],
    "N": [0, 2, 1, 0, 0],
    "C": [0, 0, 0, 0, 1],
    "Ar": [0, 0, 0, 1, 0],
}


class MismatchError(Exception):
    """The environment is not the one the request expects (exit 72)."""


# -- process plumbing ------------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _exit(code: int) -> None:
    os._exit(code)


def _lifeline() -> None:
    sys.stdin.buffer.read()  # blocks until the worker closes stdin, or dies
    _exit(EXIT_LIFELINE_LOST)


def _write(document: dict[str, Any], directory: Path) -> None:
    temporary = directory / RESULT_TEMPORARY
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, allow_nan=False))
        handle.flush()
        os.fsync(handle.fileno())
    os.rename(temporary, directory / RESULT_FILE)


def model_exception(error: Exception) -> tuple[dict[str, str], str] | None:
    """R-251 (design note §14.1 B9): an exception raised inside the model's window, as the
    diagnostics of the stage `model_exception` and its formatted traceback; `None` when it is not
    covered and stays a crash (`MemoryError`, `OSError` and their subclasses).

    A pure function of the exception and its traceback. The synthetic child
    (`tests/support/synthetic_child.py`) calls this same function, so both classify alike."""
    if isinstance(error, MemoryError | OSError):
        return None
    kind = type(error)
    lines = str(error).splitlines()
    text = "".join(traceback.format_exception(kind, error, error.__traceback__))
    record = {
        "type": f"{kind.__module__}.{kind.__qualname__}",
        "message": (lines[0] if lines else "")[:MODEL_EXCEPTION_MESSAGE_LIMIT],
        "traceback_sha256": hashlib.sha256(text.encode("utf-8", "backslashreplace")).hexdigest(),
    }
    return record, text


def nonfinite_paths(document: Any) -> list[str]:
    """§14.5 D2: the RFC 6901 pointers of every non-finite float in `document`, in document
    order (a mapping's own iteration order). A pure function; the synthetic child
    (`tests/support/synthetic_child.py`) calls this same function."""
    found: list[str] = []

    def visit(value: Any, pointer: str) -> None:
        if isinstance(value, float):
            if not math.isfinite(value):
                found.append(pointer)
        elif isinstance(value, dict):
            for key, item in value.items():
                visit(item, f"{pointer}/{str(key).replace('~', '~0').replace('/', '~1')}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{pointer}/{index}")

    visit(document, "")
    return found


def _set_null(document: Any, pointer: str) -> None:
    *parents, last = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]
    node = document
    for part in parents:
        node = node[int(part)] if isinstance(node, list) else node[part]
    if isinstance(node, list):
        node[int(last)] = None
    else:
        node[last] = None


def nonfinite_screen(document: dict[str, Any]) -> dict[str, Any]:
    """§14.5 D2: an evaluation's result with no non-finite value, as written. When it holds
    one, every such value becomes null and its pointer is listed in
    `diagnostics.nonfinite_paths`; an `outlet` becomes `not_accepted` at `nonfinite`, without its
    `tube_outlet`; a `not_accepted` keeps its stage. A result with none is returned unchanged
    (the same object). The synthetic child calls this same function."""
    paths = nonfinite_paths(document)
    if not paths:
        return document
    for pointer in paths:
        _set_null(document, pointer)
    if document.get("outcome") == OUTCOME_OUTLET:
        document["outcome"] = OUTCOME_NOT_ACCEPTED
        document["stage"] = STAGE_NONFINITE
        document.pop("tube_outlet", None)
    diagnostics = document.get("diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = document["diagnostics"] = {}
    diagnostics["nonfinite_paths"] = paths
    return document


# -- the environment -------------------------------------------------------------------------------


def tree_sha256(root: Path) -> str:
    """The export's tree hash: SHA-256 of the canonical JSON list of `[relative path, file
    SHA-256]` sorted by path (`EXPORT_TREE_SHA256` itself excluded). `env.tree_sha256` computes
    the same with ADR 0002's canonical JSON; a default-gate test asserts they agree."""
    entries = sorted(
        [path.relative_to(root).as_posix(), _sha256(path)]
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() != EXPORT_TREE_FILE
    )
    text = json.dumps(entries, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def locked_versions(lock: Path) -> dict[str, str]:
    """`name -> version` for every `name==version` requirement of a hash-pinned lock."""
    found: dict[str, str] = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "--")):
            continue
        requirement = line.split()[0]
        name, separator, version = requirement.partition("==")
        if separator:
            found[_normalized(name)] = version
    return found


def _normalized(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def _installed(names: list[str]) -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for name in names:
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            found[name] = None
    return found


def _cpu() -> tuple[str, str]:
    """The CPU model and the SHA-256 of its feature flags (`/proc/cpuinfo`; elsewhere what
    `platform` says)."""
    model, flags = "", ""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            key, _, value = line.partition(":")
            if key.strip() == "model name" and not model:
                model = value.strip()
            elif key.strip() in ("flags", "Features") and not flags:
                flags = value.strip()
    except OSError:
        pass
    model = model or platform.processor() or platform.machine() or "unknown"
    return model, hashlib.sha256(flags.encode("utf-8")).hexdigest()


class Environment:
    """The environment root and what an attempt verifies of it."""

    def __init__(self, expected: dict[str, Any], runner: str) -> None:
        cache = os.environ.get("NUMBA_CACHE_DIR")
        if not cache:
            raise MismatchError("NUMBA_CACHE_DIR is not set; the launcher sets it")
        self.root = Path(cache).parent
        self.export = self.root / EXPORT_DIR
        self.runner = runner
        manifest_path = self.root / MANIFEST_FILE
        if not manifest_path.is_file():
            raise MismatchError(f"no {MANIFEST_FILE} at {self.root}")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if expected.get("runner_sha256") != runner:
            raise MismatchError(f"runner_sha256 {runner} is not the expected one")
        for name in ("commit", "lock_sha256"):
            if self.manifest.get(name) != expected.get(name):
                raise MismatchError(
                    f"{name} {self.manifest.get(name)!r} is not {expected.get(name)!r}"
                )
        lock = self.root / LOCK_FILE
        if _sha256(lock) != expected.get("lock_sha256"):
            raise MismatchError(f"{LOCK_FILE} does not hash to the expected lock_sha256")
        self.locked = locked_versions(lock)
        marker = self.export / EXPORT_TREE_FILE
        self.export_tree = marker.read_text(encoding="utf-8").strip()
        if self.export_tree != self.manifest.get("export_tree_sha256"):
            raise MismatchError(f"{EXPORT_TREE_FILE} is not the manifest's export_tree_sha256")
        self.database = self.root / DATABASE_FILE
        self.packages = _installed(sorted(self.locked))

    def verify_fully(self) -> None:
        """The handshake's checks: the export tree, the database and every installed version."""
        measured = tree_sha256(self.export)
        if measured != self.export_tree:
            raise MismatchError(f"the export's tree hash is {measured}, not {self.export_tree}")
        if _sha256(self.database) != self.manifest.get("merged_database_sha256"):
            raise MismatchError(f"{DATABASE_FILE} is not the manifest's merged_database_sha256")
        wrong = {
            name: (self.packages[name], version)
            for name, version in self.locked.items()
            if self.packages[name] != version
        }
        if wrong:
            raise MismatchError(f"installed versions differ from the lock: {sorted(wrong.items())}")

    def import_reactor(self) -> None:
        """Put the export's `src` first on the path and check `reactor` is the export's."""
        source = self.export / "src"
        sys.path.insert(0, str(source))
        reactor = importlib.import_module("reactor")
        location = Path(str(reactor.__file__)).resolve()
        if source.resolve() not in location.parents:
            raise MismatchError(f"reactor imported from {location}, not from the export")

    def fingerprint(self, attempt: Path) -> dict[str, Any]:
        """§2.4's fingerprint (the handshake reports it whole; an evaluation, its cheap part)."""
        cpu_model, cpu_flags = _cpu()
        return {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_model": cpu_model,
            "cpu_flags_sha256": cpu_flags,
            "packages": dict(self.packages),
            "thread_env": {name: os.environ.get(name) for name in THREAD_VARIABLES},
            "env_allowlist": {
                name: value.replace(str(attempt), "${ATTEMPT_DIR}")
                for name, value in sorted(os.environ.items())
            },
            "export_tree_sha256": self.export_tree,
            "merged_database_sha256": self.manifest.get("merged_database_sha256"),
            "lock_sha256": self.manifest.get("lock_sha256"),
            "runner_sha256": self.runner,
        }


CHEAP = ("python", "packages", "cpu_model", "thread_env", "runner_sha256", "export_tree_sha256")


# -- the reactor (M01 spec §8.3-§8.7; reactor_probe.py) -------------------------------------------


def _configuration(request: dict[str, Any]) -> dict[str, Any]:
    configuration = dict(request["configuration"])
    profile = configuration.pop("profile", None)
    if profile != PROFILE:
        raise MismatchError("the variant's profile is not the one this child implements")
    if set(configuration) != set(CONFIGURATION):
        raise MismatchError(f"configuration members {sorted(configuration)} are not this child's")
    for name, kind in CONFIGURATION.items():
        value = configuration[name]
        if kind is float and isinstance(value, int) and not isinstance(value, bool):
            value = configuration[name] = float(value)
        if not isinstance(value, kind) or isinstance(value, bool):
            raise MismatchError(f"configuration.{name} is not a {kind.__name__}")
    if configuration["permeance_prefactors"] != PERMEANCE_PREFACTOR:
        raise MismatchError("this child runs every permeance pre-factor at zero")
    if len(configuration["backflow"]) != len(SPECIES):
        raise MismatchError("configuration.backflow needs one entry per species")
    return configuration


def dippr107_h(row: dict[str, float], temperature: float) -> float:
    """The antiderivative of the group's DIPPR-107 c_p (J/kmol/K)."""
    c1, c2, c3, c4, c5 = (row[f"c_p_C{k}"] for k in range(1, 6))
    return (
        c1 * temperature
        + c2 * c3 / math.tanh(c3 / temperature)
        - c4 * c5 * math.tanh(c5 / temperature)
    )


def h_group(database: dict[str, Any], species: str, temperature: float) -> float:
    """The group's molar enthalpy of `species` at `temperature`, J/mol."""
    row = database["species_properties"]["data"][species]
    reference = dippr107_h(row, 298.15)
    return float(row["dH_f"] + (dippr107_h(row, temperature) - reference) / 1000.0)


def steady_state_target(num_z: int) -> float:
    return 1e-6 * (num_z / 100.0) ** 2


def element_defects(
    np: Any, n_in: list[float], n_out: list[float], composition: list[float]
) -> dict[str, float]:
    """M01.A45's relative element defects of the retentate between its inlet and outlet faces,
    over the elements present in the requested inlet `composition` (§14.6 E2): element e is
    present iff E_e · y_req > 0, tested exactly; an absent element has no key (its 0/0 carries
    no information). The defect itself is taken on the faces passed in, as under v2."""
    return {
        element: float((np.dot(weights, n_out) - np.dot(weights, n_in)) / np.dot(weights, n_in))
        for element, weights in ELEMENTS.items()
        if np.dot(weights, composition) > 0
    }


def max_defect(np: Any, defects: dict[str, float]) -> float:
    """§14.6 E2's δ: the largest |defect| over `defects` (the present elements), NaN if any of
    them is NaN, whatever their order (`max` alone keeps a NaN only in the first position). The
    NaN returned is the defect's own: the child makes none."""
    values = [abs(value) for value in defects.values()]
    for value in values:
        if np.isnan(value):
            return value
    return max(values)


def axial_flows(np: Any, retentate: Any, composition: list[float]) -> dict[str, Any]:
    """§14.6 E2's positivity diagnostics of the retentate's axial flows (faces × species).
    Species i is present iff its requested inlet mole fraction `composition[i]` is > 0, tested
    exactly (never on the model's inlet face, whose absent entries carry roundoff of either
    sign). `min_axial_flow_mol_s` is the minimum over present species and every face; the
    absent species (only Ar or CH4 inside the domain) are listed in component order, with the
    largest |flow| they carry on any face (`null` when none is absent)."""
    flows = np.asarray(retentate)
    present = np.array([value > 0.0 for value in composition])
    absent = [species for species, kept in zip(SPECIES, present, strict=True) if not kept]
    return {
        "min_axial_flow_mol_s": float(np.min(flows[:, present])),
        "absent_species": absent,
        "absent_species_max_abs_flow_mol_s": (
            float(np.max(np.abs(flows[:, ~present]))) if absent else None
        ),
    }


def flows_positive(diagnostics: dict[str, Any]) -> bool:
    """The acceptance's positivity clause: every axial flow of a present species is > 0 (a NaN
    is not)."""
    return bool(diagnostics["min_axial_flow_mol_s"] > 0.0)


def certificate_diagnostics(certificate: dict[str, Any], wall_s: float) -> dict[str, Any]:
    """The KPI-drift certificate as the result records it (`diagnostics.certificate`)."""
    drift = certificate.get("kpi_drift_rel") or {}
    residual = certificate.get("achieved_residual")
    return {
        "kpi_drift_ok": certificate.get("kpi_drift_ok"),
        "kpi_drift_rel_max": max(drift.values()) if drift else None,
        "residual": None if residual is None else float(residual),
        "wall_s": wall_s,
    }


def certificate_passed(certificate: dict[str, Any]) -> bool:
    return certificate.get("kpi_drift_ok") is True


def after_s3(
    status3: Any,
    certify: Any,
    read_defect: Any,
    polish: Any,
    stage: dict[str, Any],
    diagnostics: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    """§14.6 E1: profile `M01-S123-v2`'s sequence after an accepted S3, over three injected
    callables — `certify(status)` (the group's certificate, which marches the state),
    `read_defect()` (δ from the model's current flows; a read) and `polish()` (round 2 on the same
    object: `(status, record)`). Returns the stage this sequence refuses at (`S3`, `certificate`)
    or None, and the deciding certificate (None when round 2 did not converge).

    certificate₁ on S3's status; δ₁ read after it and recorded as `defect_round1` whatever its
    verdict; a failed certificate₁ decides (no round 2); δ₁ ≤ the threshold leaves v2's path plus
    the read; otherwise (a NaN included) round 2, S3's acceptance becomes its convergence, and a
    converged round is certified again (certificate₂ decides). `diagnostics.certificate` holds
    the deciding certificate; `stage.round2.certificate_round1` holds certificate₁ when round 2
    ran."""
    policy: Any = PROFILE["S3"]["round2"]
    started = time.perf_counter()
    certificate = certify(status3)
    summary = certificate_diagnostics(certificate, time.perf_counter() - started)
    delta = read_defect()
    stage["defect_round1"] = delta
    stage["round2"] = None
    if not certificate_passed(certificate):
        diagnostics["certificate"] = summary
        return "certificate", certificate
    if delta <= policy["defect_threshold"]:
        diagnostics["certificate"] = summary
        return None, certificate
    status, record = polish()
    record["certificate_round1"] = summary
    stage["round2"] = record
    stage["accepted"] = bool(record["converged"])
    if not stage["accepted"]:
        return "S3", None
    started = time.perf_counter()
    certificate = certify(status)
    diagnostics["certificate"] = certificate_diagnostics(certificate, time.perf_counter() - started)
    return (None if certificate_passed(certificate) else "certificate"), certificate


class Reactor:
    """The pinned model for one configuration (geometry, grid, backflow) and one database."""

    def __init__(self, configuration: dict[str, Any], database_path: Path) -> None:
        self.configuration = configuration
        self.database_path = database_path
        self.database = json.loads(database_path.read_text(encoding="utf-8"))
        self.np: Any = importlib.import_module("numpy")
        self.reactor: Any = importlib.import_module("reactor")
        self.case_setup: Any = importlib.import_module("reactor.paper.case_setup")
        self.cases: Any = importlib.import_module("reactor.paper.cases")
        self.settings: Any = importlib.import_module("reactor.paper.settings")
        self.kpis: Any = importlib.import_module("reactor.paper.kpis")
        self.runner: Any = importlib.import_module("reactor.paper.runner")
        stages = (PROFILE["S1"]["dt_init"], PROFILE["S2"]["dt_init"])
        if stages != (self.settings.DT_INIT_1D, self.settings.DT_INIT_1D):
            raise MismatchError("the group's DT_INIT_1D is not the profile's S1/S2 dt_init")
        table = self.cases.load_case_table()
        rows = table[table["Case_ID"] == configuration["geometry_case"]]
        if len(rows) != 1:
            raise MismatchError(f"geometry case {configuration['geometry_case']!r} is not one row")
        self.row = rows.iloc[0]

    def config(self, tube: dict[str, Any], composition: list[float]) -> tuple[Any, dict[str, Any]]:
        """`reactor_probe.build`, with the tube's inlet and coolant in place of the GHSV's."""
        reactor, row = self.reactor, self.row
        r_min, r_max = reactor.DEFAULTS["r_min"], float(row["r_max_m"])
        l_membrane, l_seal = float(row["L_m"]), reactor.DEFAULTS["Lsealing"]
        flows = self.case_setup.calculate_flows(
            GHSV=DESIGN_GHSV_H,
            eps=reactor.DEFAULTS["eps"],
            Dcat=float(row["Dcat"]),
            rho_c=reactor.DEFAULTS["rho_c"],
            L_membrane=l_membrane,
            Lsealing=l_seal,
            r_max=r_max,
            r_min=r_min,
            Nm=int(row["N_mem"]),
            sweep_ratio=float(row["Sweep_Ratio"]),
            H2_N2_ratio=DESIGN_H2_N2,
        )
        t_in = float(tube["temperature"])
        coolant = [float(value) for value in tube["coolant_composition"]]
        config = reactor.ReactorConfig.from_defaults(
            L=l_membrane + l_seal,
            Lsealing=l_seal,
            r_min=r_min,
            r_max=r_max,
            p_ret_out=float(tube["outlet_pressure"]),
            p_perm_out=float(tube["coolant_outlet_pressure"]),
            T_ret_in=t_in,
            T_perm_in=float(tube["coolant_temperature"]),
            T_ret_init=t_in,
            T_perm_init=float(tube["coolant_temperature"]),
            F_ret_in=float(tube["flow"]),
            F_perm_in=float(tube["coolant_flow"]),
            y_ret_in=list(composition),
            y_ret_init=list(composition),
            y_perm_in=coolant,
            y_perm_init=coolant,
            Nm=int(row["N_mem"]),
            Dcat=float(row["Dcat"]),
            is_counter_current=bool(row["Is_Counter_Current"]),
            factor_react=1.0,
            factor_p=1.0,
            factor_T=1e-1,
            num_z=int(self.configuration["num_z"]),
            is_isothermal=False,
            species=list(SPECIES),
            database=str(self.database_path),
            **self.settings.SOLVER_1D,
        )
        for species in SPECIES:
            setattr(config, f"P0_{species}", PERMEANCE_PREFACTOR)
            if not hasattr(config, f"EA_{species}"):
                setattr(config, f"EA_{species}", 0.0)
        meta = {"W_cat": flows[4], "A_membrane_m2": 1.0}
        return config, meta

    def model_class(self, backflow: list[float]) -> Any:
        """F-R1 (M01 spec §8.5): the pinned 1D class with its backflow inflow set for five
        species, after `_init_derived()`. The pinned code is not patched."""
        np = self.np
        base = self.runner._one_d_class(self.settings.MODEL_1D)

        def _init_derived(model: Any) -> None:
            base._init_derived(model)
            inflow = np.asarray(backflow, dtype=float).reshape((1, 1, model.num_c))
            model.inflow_conc_ret_backflow = model.p_ret_out / (model.Rg * model.T_ret_in) * inflow

        return type("FiveSpecies1D", (base,), {"_init_derived": _init_derived})

    def _accepted(self, status: Any, config: Any) -> bool:
        verdict = self.kpis.solver_acceptance(
            status, config.steady_state_atol, self.settings.STEADY_STATE_ACCEPT_FACTOR
        )
        return bool(verdict["accepted"])

    def evaluate(
        self, tube: dict[str, Any], s2_dt_init: float | None, backflow: list[float]
    ) -> dict[str, Any]:
        """S1-S3 and the evaluation's acceptance: `{outcome, stage | tube_outlet, diagnostics}`.
        An exception the window (`_window`) raises is the stage `model_exception` when
        `model_exception` covers it, and propagates (a crash) when it does not (R-251)."""
        num_z = int(self.configuration["num_z"])
        y_in = [float(value) for value in tube["composition"]]
        trace = float(PROFILE["S1"]["trace_NH3"])
        raw = y_in[:2] + [trace] + y_in[3:]
        total = sum(raw)
        y_trace = [value / total for value in raw]
        diagnostics: dict[str, Any] = {"stages": {}, "num_z": num_z}

        def refused(stage: str) -> dict[str, Any]:
            return {"outcome": OUTCOME_NOT_ACCEPTED, "stage": stage, "diagnostics": diagnostics}

        try:
            reached = self._window(tube, y_in, y_trace, s2_dt_init, backflow, diagnostics)
        except Exception as error:
            covered = model_exception(error)
            if covered is None:
                raise
            record, text = covered
            sys.stderr.write(text)
            sys.stderr.flush()
            diagnostics["model_exception"] = record
            return refused(STAGE_MODEL_EXCEPTION)
        if isinstance(reached, str):
            return refused(reached)
        certificate, outlet = reached
        diagnostics.update(outlet["diagnostics"])
        if not certificate_passed(certificate):
            return refused("certificate")
        if not diagnostics["u_ret_min"] > 0.0:
            return refused("backflow")
        if not flows_positive(diagnostics):
            return refused("nonpositive_flow")
        return {
            "outcome": OUTCOME_OUTLET,
            "tube_outlet": outlet["tube_outlet"],
            "diagnostics": diagnostics,
        }

    def _window(
        self,
        tube: dict[str, Any],
        y_in: list[float],
        y_trace: list[float],
        s2_dt_init: float | None,
        backflow: list[float],
        diagnostics: dict[str, Any],
    ) -> str | tuple[dict[str, Any], dict[str, Any]]:
        """R-251's window: from the first reactor object through the outlet's extraction. The
        stage S1, S2 or S3 refused at, or the certificate and the outlet; the stages' and the
        certificate's diagnostics go into `diagnostics` as they are reached."""
        num_z = int(self.configuration["num_z"])
        stages: dict[str, Any] = diagnostics["stages"]
        model = self.model_class(backflow)
        started = time.perf_counter()
        config1, meta = self.config(tube, y_trace)
        first = model(config=config1)
        status1 = first.solve(dt_init=self.settings.DT_INIT_1D, return_status=True, verbose=0)
        stages["S1"] = self._stage(status1, self._accepted(status1, config1), started)
        if not stages["S1"]["accepted"]:
            return "S1"
        started = time.perf_counter()
        config2, meta = self.config(tube, y_in)
        count = len(SPECIES)
        second = model(
            config=config2,
            c=first.cpT[..., :count].copy(),
            p=first.cpT[..., -2].copy(),
            T=first.cpT[..., -1].copy(),
        )
        dt2 = self.settings.DT_INIT_1D if s2_dt_init is None else s2_dt_init
        status2 = second.solve(dt_init=dt2, return_status=True, verbose=0)
        stages["S2"] = self._stage(status2, self._accepted(status2, config2), started)
        stages["S2"]["dt_init"] = dt2
        if not stages["S2"]["accepted"]:
            return "S2"
        started = time.perf_counter()
        polish: Any = PROFILE["S3"]
        target = steady_state_target(num_z)
        second.rtol, second.atol = polish["rtol"], polish["atol_factor"] * target
        status3 = second.solve(
            num_timesteps=polish["max_steps"],
            dt_init=polish["dt_init"],
            steady_state_atol=target,
            return_status=True,
            verbose=0,
        )
        stages["S3"] = self._stage(status3, bool(status3.converged), started)
        stages["S3"]["steady_state_target"] = target
        if not stages["S3"]["accepted"]:
            return "S3"
        refused, certificate = after_s3(
            status3,
            lambda status: self.runner.certify_convergence_1d(second, status, meta),
            lambda: self._defect(second, y_in),
            lambda: self._round2(second, target),
            stages["S3"],
            diagnostics,
        )
        if refused == "S3" or certificate is None:
            return "S3"
        outlet = self.outlet(
            second, float(tube["temperature"]), float(tube["coolant_temperature"]), y_in
        )
        return certificate, outlet

    def _defect(self, model: Any, composition: list[float]) -> float:
        """§14.6 E2's δ of the model's current state (a read: no state changes)."""
        retentate = model.compute_flows()[0]
        n_in = [float(value) for value in retentate[0, :]]
        n_out = [float(value) for value in retentate[-1, :]]
        return max_defect(self.np, element_defects(self.np, n_in, n_out, composition))

    def _round2(self, model: Any, target: float) -> tuple[Any, dict[str, Any]]:
        """§14.5 D1's round 2 (settings unchanged by §14.6 E1): one more polish round on the same
        object at a tenth of S3's target. Its status and its record."""
        policy: Any = PROFILE["S3"]["round2"]
        started = time.perf_counter()
        target2 = target / 10.0
        model.rtol, model.atol = policy["rtol"], policy["atol_factor"] * target2
        status = model.solve(
            num_timesteps=policy["max_steps"],
            dt_init=policy["dt_init"],
            steady_state_atol=target2,
            return_status=True,
            verbose=0,
        )
        return status, {
            "steps": int(status.num_steps_attempted),
            "converged": bool(status.converged),
            "steady_state_target": target2,
            "wall_s": time.perf_counter() - started,
        }

    @staticmethod
    def _stage(status: Any, accepted: bool, started: float) -> dict[str, Any]:
        best = getattr(status, "best_steady_state_norm", None)
        return {
            "accepted": accepted,
            "converged": bool(status.converged),
            "steady_state_norm": float(status.steady_state_norm),
            "best_steady_state_norm": None if best is None else float(best),
            "steps": int(status.num_steps_attempted),
            "wall_s": time.perf_counter() - started,
        }

    def outlet(
        self, model: Any, t_in: float, t_coolant_in: float, composition: list[float]
    ) -> dict[str, Any]:
        """`reactor_probe.outlet`: the raw outlet and its diagnostics; `composition` is the
        requested inlet's, which decides the present species and elements (§14.6 E2)."""
        np, database = self.np, self.database
        retentate, _, permeate, _ = model.compute_flows()
        n_in = [float(value) for value in retentate[0, :]]
        n_out = [float(value) for value in retentate[-1, :]]
        defects = element_defects(np, n_in, n_out, composition)
        t_out = float(model.cpT[-1, 1, -1])
        t_coolant_out = float(model.cpT[-1, 0, -1])
        coolant_flow = float(np.sum(permeate[0, :]))
        coolant_heat = coolant_flow * (
            h_group(database, "N2", t_coolant_out) - h_group(database, "N2", t_coolant_in)
        )
        retentate_change = sum(
            n_out[i] * h_group(database, s, t_out) - n_in[i] * h_group(database, s, t_in)
            for i, s in enumerate(SPECIES)
        )
        p_first = float(model.cpT[0, 1, -2])
        pressure_drop = p_first - float(model.p_ret_out)
        return {
            "tube_outlet": {
                "flows": n_out,
                "temperature": t_out,
                "pressure_drop": pressure_drop,
                "coolant_heat": coolant_heat,
                "inlet_face_heat_loss": -(retentate_change + coolant_heat),
            },
            "diagnostics": {
                "inlet_face_n_mol_s": n_in,
                "T_max_K": float(np.max(model.cpT[:, 1, -1])),
                "p_first_cell_Pa": p_first,
                "dP_over_P": pressure_drop / float(model.p_ret_out),
                "coolant_out_T_K": t_coolant_out,
                "coolant_flow_mol_s": coolant_flow,
                "coolant_heat_uptake_W": coolant_heat,
                "inlet_face_heat_loss_W": -(retentate_change + coolant_heat),
                "element_defect_rel": defects,
                "u_ret_min": float(np.min(model.u_ret_ax)),
                **axial_flows(np, retentate, composition),
            },
        }


# -- main ------------------------------------------------------------------------------------------


def _evidence_switches() -> tuple[float | None, bool]:
    value = os.environ.get(S2_DT_INIT_VARIABLE)
    s2 = None if value is None else float(value)
    if s2 is not None and not (math.isfinite(s2) and s2 > 0.0):
        raise MismatchError(f"{S2_DT_INIT_VARIABLE} = {value!r} is not a positive finite number")
    return s2, os.environ.get(BACKFLOW_ALT_VARIABLE) == "1"


def main() -> None:
    started = time.monotonic()
    attempt = Path.cwd()
    request = json.loads(sys.stdin.buffer.readline())
    threading.Thread(target=_lifeline, daemon=True).start()
    margin = float(os.environ.get(DEADLINE_MARGIN_VARIABLE, SELF_DEADLINE_MARGIN_S))
    deadline = threading.Timer(
        float(request["deadline_s"]) + margin, _exit, args=(EXIT_SELF_DEADLINE,)
    )
    deadline.daemon = True
    deadline.start()
    handshake = HANDSHAKE_ARGUMENT in sys.argv
    try:
        if request.get("protocol") != PROTOCOL_VERSION:
            raise MismatchError(f"protocol {request.get('protocol')!r} is not {PROTOCOL_VERSION}")
        environment = Environment(request.get("expected", {}), _sha256(Path(__file__)))
        configuration = _configuration(request)
        s2_dt_init, backflow_alt = _evidence_switches()
        if handshake:
            environment.verify_fully()
        environment.import_reactor()
        reactor = Reactor(configuration, environment.database)
    except MismatchError as error:
        sys.stderr.write(f"environment_mismatch: {error}\n")
        sys.stderr.flush()
        _exit(EXIT_ENVIRONMENT_MISMATCH)
        raise  # unreachable: `_exit` does not return
    full = environment.fingerprint(attempt)
    solve_started = time.monotonic()
    timing: dict[str, float] = {"startup_s": solve_started - started}
    if handshake:
        document: dict[str, Any] = {"outcome": OUTCOME_HANDSHAKE, "fingerprint": full}
    else:
        backflow = BACKFLOW_ALT if backflow_alt else list(configuration["backflow"])
        document = reactor.evaluate(request["tube_inlet"], s2_dt_init, backflow)
        document["fingerprint"] = {name: full[name] for name in CHEAP}
        document["diagnostics"]["evidence"] = {
            "s2_dt_init": s2_dt_init,
            "backflow_alt": backflow_alt,
        }
    timing["solve_s"] = time.monotonic() - solve_started
    result = {
        "protocol": PROTOCOL_VERSION,
        "request_sha256": request["request_sha256"],
        **document,
        "timing": timing,
    }
    _write(result if handshake else nonfinite_screen(result), attempt)
    _exit(0)


if __name__ == "__main__":
    # Every exit is `os._exit` (module docstring). SIGINT keeps its default action, so an
    # interrupt from the terminal ends the child by the signal (`crashed`) instead of raising
    # `KeyboardInterrupt` into a normal interpreter exit; nothing here raises `SystemExit`. Every
    # other failure is an exception: a crash of the child's own code, exit 1, its traceback on
    # stderr.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(1)
    os._exit(0)  # unreachable: `main` leaves through `os._exit`
