"""The two ways a variant is evaluated (M02 design note §2.1, §2.4, §3.3, §6.1; ADR 0033 D1, D4).

A backend is the `ExternalEvaluation` behind the boundary for one variant, plus what an experiment
record needs to say about it: the **environment** it evaluates in (a fingerprint, whose SHA-256 is
part of every experiment key), the result **identity** of M01 spec §8.12, and, per evaluation, an
`Execution` — the answer the boundary sees and the facts the attempt record keeps.

- `InProcessBackend`: the stand-in's closed forms, in the worker. Its fingerprint is the boundary
  module's and the evaluation module's artifact hashes and the package version.
- `OutOfProcessBackend`: one child per attempt through `external.launcher`. The first call
  performs the **handshake** (`--handshake`): the child verifies its environment and reports the
  full fingerprint, which is frozen for the backend's life (one job). Every evaluation's child
  reports the cheap part, which must equal the handshake's, else `environment_changed`.

**A handshake that cannot measure the fingerprint.** The key needs the fingerprint's SHA-256, and a
failed handshake (no environment, a mismatch, a crash) has none. The request is then keyed on the
`document_sha256` of an explicit *unmeasured* fingerprint `{measured: false, variant_sha256,
env_id, status}`, and the attempt records the handshake's failure. Such an outcome is transient
(never cached), so the stand-in key cannot shadow a measured one. (M02 build-lane decision,
reported to the design lane: the note's tables record `environment_*` attempts but its key
assumes a measured fingerprint.)
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import math
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, Final, Literal, Protocol

import openflowsheet
from openflowsheet.adapters.external.launcher import (
    ChildProgram,
    LaunchProgress,
    LaunchResult,
    Limits,
    launch,
)
from openflowsheet.adapters.variants import Variant
from openflowsheet.canonical import document_sha256, file_sha256
from openflowsheet.models.c1 import boundary as boundary_module
from openflowsheet.models.c1.boundary import ExecutionFailure, NotAccepted, TubeInlet, TubeOutlet
from openflowsheet.models.c1.reactor_standin import MODEL_ID as STANDIN_MODEL_ID
from openflowsheet.models.c1.reactor_standin import _standin_evaluation

__all__ = [
    "CHEAP_FINGERPRINT_FIELDS",
    "Backend",
    "Environment",
    "Execution",
    "InProcessBackend",
    "OutOfProcessBackend",
    "PROFILE_FILE",
    "START_FILE",
    "start_capable",
    "pinned_program",
    "unmeasured_fingerprint",
]

ExecutionKind = Literal["in_process", "out_of_process"]
#: §2.4: the part of the fingerprint every evaluation's child reports and must match.
CHEAP_FINGERPRINT_FIELDS: Final = (
    "python",
    "packages",
    "cpu_model",
    "thread_env",
    "runner_sha256",
    "export_tree_sha256",
)
#: The in-process evaluation modules a variant may name; the stand-in is the only one.
_IN_PROCESS_MODULES: Final = frozenset({"openflowsheet.models.c1.reactor_standin"})
_STAGE: Final = re.compile(r"[A-Za-z0-9_]+")
#: §2.4: where pinned environments live unless `OPENFLOWSHEET_EXTERNAL_ROOT` says otherwise.
EXTERNAL_ROOT_VARIABLE: Final = "OPENFLOWSHEET_EXTERNAL_ROOT"
#: ADR 0070 D7 (X02 design note §5.5): the start the backend hands a child, and the profile a
#: start-capable child exports after an `outlet` answer, in the attempt's working directory.
START_FILE: Final = "start.json"
PROFILE_FILE: Final = "profile.json"
#: ADR 0070 D10 (D8 as amended by the X02 review): the packaged child scripts a variant's
#: `runner_sha256` selects among; today `child.py` alone (no start-capable runner is shipped).
CHILD_SCRIPTS: Final = ("child.py",)


def start_capable(variant: Variant) -> bool:
    """ADR 0070 D4: an out-of-process variant whose evaluation profile declares a `start`."""
    if variant.kind != "out_of_process":
        return False
    profile = variant.evaluation.get("profile")
    return isinstance(profile, Mapping) and isinstance(profile.get("start"), Mapping)


@dataclass(frozen=True)
class Execution:
    """One evaluation's answer for the boundary and the attempt record's `execution` facts.
    `answer` is `None` only for the runner's own records of an evaluation that gave none (not
    executed, cancelled)."""

    kind: ExecutionKind
    status: str
    answer: TubeOutlet | NotAccepted | ExecutionFailure | None
    message: str = ""
    exit_code: int | None = None
    signal: int | None = None
    tube_outlet: Mapping[str, Any] | None = None
    stage: str | None = None
    diagnostics: Mapping[str, Any] | None = None
    fingerprint: Mapping[str, Any] | None = None
    logs: Mapping[str, Any] | None = None
    timing: Mapping[str, Any] = field(default_factory=dict)
    #: Where the logs are (a handshake's directory); the attempt's own directory when `None`.
    directory: Path | None = None


@dataclass(frozen=True)
class Environment:
    """The environment a backend evaluates in: the fingerprint and its SHA-256, or — when the
    handshake failed — the unmeasured fingerprint's SHA-256 and the failure."""

    fingerprint: Mapping[str, Any] | None
    sha256: str
    failure: Execution | None = None


class Backend(Protocol):
    kind: ExecutionKind

    def environment(self, directory: Path) -> Environment: ...

    def identity(self, n_tubes: float) -> Mapping[str, Any]: ...

    def evaluate(
        self,
        tube: TubeInlet,
        directory: Path,
        progress: LaunchProgress,
        check: Callable[[], None] | None,
        start: bytes | None = None,
    ) -> Execution: ...


def tube_document(value: TubeInlet | TubeOutlet) -> dict[str, Any]:
    """A tube inlet or outlet as its record carries it (tuples as lists)."""
    return {
        key: list(item) if isinstance(item, tuple) else item
        for key, item in dataclasses.asdict(value).items()
    }


def unmeasured_fingerprint(variant: Variant, status: str) -> dict[str, Any]:
    """The fingerprint document a request is keyed on when the handshake measured none."""
    environment = variant.evaluation.get("environment", {})
    return {
        "measured": False,
        "variant_sha256": variant.sha256,
        "env_id": environment.get("env_id"),
        "status": status,
    }


# -- in process -----------------------------------------------------------------------------------


class InProcessBackend:
    """The stand-in (`c1.reactor_standin`), evaluated in the worker (§3.1)."""

    kind: ExecutionKind = "in_process"

    def __init__(self, variant: Variant) -> None:
        evaluation = variant.evaluation
        if variant.kind != "in_process" or evaluation["module"] not in _IN_PROCESS_MODULES:
            raise ValueError(f"{variant.variant_id}: not an in-process variant this build runs")
        self.variant = variant
        self.conversion = float(evaluation["conversion_N2"])
        perturbation = evaluation.get("perturbation_mol_s")
        self.perturbation = None if perturbation is None else tuple(perturbation)
        self.pressure_drop = float(evaluation.get("pressure_drop_Pa", 0.0))
        self._evaluate = _standin_evaluation(self.conversion, self.perturbation, self.pressure_drop)

    def environment(self, directory: Path) -> Environment:
        module = import_module(self.variant.evaluation["module"])
        assert module.__file__ is not None and boundary_module.__file__ is not None
        fingerprint = {
            "kind": "in_process",
            "boundary_sha256": file_sha256(Path(boundary_module.__file__)),
            "module": self.variant.evaluation["module"],
            "module_sha256": file_sha256(Path(module.__file__)),
            "openflowsheet_version": openflowsheet.__version__,
        }
        return Environment(fingerprint, document_sha256(fingerprint))

    def identity(self, n_tubes: float) -> Mapping[str, Any]:
        """`ReactorStandin.identity()`'s form, with the variant's configuration."""
        configuration = {
            "model_id": STANDIN_MODEL_ID,
            "conversion_N2": self.conversion,
            "n_tubes": n_tubes,
            "perturbation_mol_s": None if self.perturbation is None else list(self.perturbation),
            "pressure_drop_Pa": self.pressure_drop,
        }
        return {
            "model_id": self.variant.model_id,
            "synthetic": True,
            "reactor_commit": None,
            "pymrm_version": None,
            "overlay_sha256": None,
            "configuration_sha256": document_sha256(configuration),
            "profile": None,
        }

    def evaluate(
        self,
        tube: TubeInlet,
        directory: Path,
        progress: LaunchProgress,
        check: Callable[[], None] | None,
        start: bytes | None = None,
    ) -> Execution:
        assert start is None, "the in-process stand-in takes no start (ADR 0070 D4)"
        outlet: TubeOutlet = self._evaluate(tube)
        return Execution(
            kind="in_process",
            status="completed",
            answer=outlet,
            tube_outlet=tube_document(outlet),
        )


# -- out of process --------------------------------------------------------------------------------


def external_root() -> Path:
    """§2.4: `$OPENFLOWSHEET_EXTERNAL_ROOT`, else `$XDG_CACHE_HOME/openflowsheet/external`."""
    configured = os.environ.get(EXTERNAL_ROOT_VARIABLE)
    if configured:
        return Path(configured)
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "openflowsheet" / "external"


@functools.cache
def _packaged_child_sha256(name: str) -> str | None:
    """The SHA-256 of a packaged child script, `None` when the package does not hold it."""
    child = Path(str(files("openflowsheet.adapters") / "pymrm" / name))
    return hashlib.sha256(child.read_bytes()).hexdigest() if child.is_file() else None


def pinned_program(variant: Variant) -> ChildProgram:
    """The pinned environment's interpreter and the packaged child for a variant (§2.4). The
    application never builds an environment; an absent one is `environment_unavailable`.

    ADR 0070 D10: the child is the packaged script whose bytes hash to the variant's
    `runner_sha256` (among `CHILD_SCRIPTS`); when none does, `child.py`, so that a
    mismatch surfaces as before (the handshake's `environment_mismatch`)."""
    root = external_root() / str(variant.evaluation["environment"]["env_id"])
    pinned = variant.evaluation.get("runner_sha256")
    name = next(
        (script for script in CHILD_SCRIPTS if _packaged_child_sha256(script) == pinned),
        CHILD_SCRIPTS[0],
    )
    child = files("openflowsheet.adapters") / "pymrm" / name
    return ChildProgram(root / "venv" / "bin" / "python", Path(str(child)), root)


def _finite(value: Any) -> bool:
    return isinstance(value, float | int) and not isinstance(value, bool) and math.isfinite(value)


def _parse_outlet(document: Any, components: int) -> TubeOutlet | None:
    """A child's `tube_outlet`, or `None` when it is not one (a protocol error)."""
    if not isinstance(document, dict):
        return None
    flows = document.get("flows")
    if not (isinstance(flows, list) and len(flows) == components and all(map(_finite, flows))):
        return None
    if not (_finite(document.get("temperature")) and _finite(document.get("pressure_drop"))):
        return None
    optional = (document.get("coolant_heat"), document.get("inlet_face_heat_loss"))
    if not all(value is None or _finite(value) for value in optional):
        return None
    return TubeOutlet(
        flows=tuple(float(value) for value in flows),
        temperature=float(document["temperature"]),
        pressure_drop=float(document["pressure_drop"]),
        coolant_heat=None if optional[0] is None else float(optional[0]),
        inlet_face_heat_loss=None if optional[1] is None else float(optional[1]),
    )


class OutOfProcessBackend:
    """A variant evaluated by a fresh child per attempt (ADR 0033 D1)."""

    kind: ExecutionKind = "out_of_process"

    def __init__(
        self,
        variant: Variant,
        program: ChildProgram | None = None,
        *,
        expected: Mapping[str, Any] | None = None,
        test_environment: Mapping[str, str] | None = None,
    ) -> None:
        if variant.kind != "out_of_process":
            raise ValueError(f"{variant.variant_id}: not an out-of-process variant")
        self.variant = variant
        self.program = program if program is not None else pinned_program(variant)
        evaluation = variant.evaluation
        self.expected = (
            dict(expected)
            if expected is not None
            else {
                "commit": evaluation["reactor"]["commit"],
                "lock_sha256": evaluation["environment"]["lock_sha256"],
                "runner_sha256": evaluation["runner_sha256"],
            }
        )
        self.configuration = {**evaluation["configuration"], "profile": evaluation["profile"]}
        execution = variant.execution
        self.limits = Limits(
            timeout_s=float(execution["timeout_s"]), kill_grace_s=float(execution["kill_grace_s"])
        )
        self.test_environment = test_environment
        self._environment: Environment | None = None

    def _request(self, tube: TubeInlet | None, start_sha256: str | None = None) -> dict[str, Any]:
        request: dict[str, Any] = {
            "deadline_s": self.limits.timeout_s,
            "expected": self.expected,
            "configuration": self.configuration,
        }
        if tube is not None:
            request["tube_inlet"] = tube_document(tube)
        if start_sha256 is not None:
            # ADR 0070 D7: the child reads `start.json` and checks it against this hash.
            request["start_profile_sha256"] = start_sha256
        return request

    def _failure(
        self, result: LaunchResult, status: str | None = None, directory: Path | None = None
    ) -> Execution:
        status = status or result.status
        return Execution(
            directory=directory,
            kind="out_of_process",
            status=status,
            answer=ExecutionFailure(status, result.message),
            message=result.message,
            exit_code=result.exit_code,
            signal=result.signal,
            logs=result.logs,
            timing={"wall_s": result.wall_s, **result.timing},
        )

    def environment(self, directory: Path) -> Environment:
        """The handshake, once (§2.4, §6.1 item 3); its record's logs stay in `directory`."""
        if self._environment is not None:
            return self._environment
        result = launch(
            self.program,
            self._request(None),
            directory,
            self.limits,
            handshake=True,
            test_environment=self.test_environment,
        )
        if result.status == "environment_unavailable":
            result = dataclasses.replace(
                result,
                message=f"{result.message}; build it with `python -m "
                f"openflowsheet.adapters.pymrm.env build --variant {self.variant.variant_id}`",
            )
        failure: Execution | None = None
        if result.status != "completed":
            failure = self._failure(result, directory=directory)
        else:
            assert result.document is not None
            fingerprint = result.document["fingerprint"]
            if fingerprint.get("runner_sha256") != self.variant.evaluation["runner_sha256"]:
                failure = self._failure(
                    dataclasses.replace(
                        result,
                        message="environment_mismatch: the child's runner_sha256 "
                        f"{fingerprint.get('runner_sha256')!r} is not the variant's",
                    ),
                    "environment_mismatch",
                    directory,
                )
            else:
                self._environment = Environment(fingerprint, document_sha256(fingerprint))
                return self._environment
        assert failure is not None
        # Not frozen here, so the runner can retry the handshake within its own budget; the
        # runner keeps the final outcome, failure included, for the job's life (R-236).
        return Environment(
            None, document_sha256(unmeasured_fingerprint(self.variant, failure.status)), failure
        )

    def _exported(self, directory: Path, diagnostics: Any) -> str | None:
        """ADR 0070 D6/D7 (X02 design note §5.5): a start-capable child's `outlet` exports
        `profile.json` and reports its hash as `diagnostics.profile_sha256`. A missing file or a
        hash that differs is a protocol error (its message); `None` when the export holds, or
        when the variant is not start-capable."""
        if not start_capable(self.variant):
            return None
        reported = diagnostics.get("profile_sha256") if isinstance(diagnostics, Mapping) else None
        path = directory / PROFILE_FILE
        if not path.is_file():
            return "protocol_error: a start-capable outlet exported no profile.json"
        if (
            not isinstance(reported, str)
            or hashlib.sha256(path.read_bytes()).hexdigest() != reported
        ):
            return "protocol_error: profile.json does not hash to diagnostics.profile_sha256"
        return None

    def identity(self, n_tubes: float) -> Mapping[str, Any]:
        """§8.12's identity of an out-of-process result: the pin, the measured pymrm version,
        the overlay, the configuration's hash and the profile."""
        evaluation = self.variant.evaluation
        fingerprint = self._environment.fingerprint if self._environment is not None else None
        packages = (fingerprint or {}).get("packages") or {}
        return {
            "model_id": self.variant.model_id,
            "synthetic": self.variant.synthetic,
            "reactor_commit": evaluation["reactor"]["commit"],
            "pymrm_version": packages.get("pymrm"),
            "overlay_sha256": evaluation["overlay_sha256"],
            "configuration_sha256": document_sha256(evaluation["configuration"]),
            "profile": evaluation["profile"]["id"],
        }

    def evaluate(
        self,
        tube: TubeInlet,
        directory: Path,
        progress: LaunchProgress,
        check: Callable[[], None] | None,
        start: bytes | None = None,
    ) -> Execution:
        """One launch at `tube`. `start` (ADR 0070 D7, X02 design note §5.5) is a start profile's
        bytes: written as `start.json` in the attempt directory before the launch, its hash in
        the child's request. Without it the child's request is unchanged."""
        assert self._environment is not None and self._environment.fingerprint is not None
        start_sha256 = None
        if start is not None:
            start_sha256 = hashlib.sha256(start).hexdigest()
            directory.mkdir(parents=True, exist_ok=True)
            (directory / START_FILE).write_bytes(start)
        result = launch(
            self.program,
            self._request(tube, start_sha256),
            directory,
            self.limits,
            progress=progress,
            check=check,
            test_environment=self.test_environment,
        )
        if result.status != "completed":
            return self._failure(result)
        document = result.document
        assert document is not None
        reported = document["fingerprint"]
        frozen = self._environment.fingerprint
        changed = [name for name in CHEAP_FINGERPRINT_FIELDS if reported.get(name) != frozen[name]]
        common = {
            "kind": "out_of_process",
            "exit_code": result.exit_code,
            "signal": result.signal,
            "diagnostics": document.get("diagnostics"),
            "fingerprint": reported,
            "logs": result.logs,
            "timing": {"wall_s": result.wall_s, **result.timing},
        }
        if changed:
            message = f"environment_changed: the child reports another {', '.join(changed)}"
            return Execution(
                status="environment_changed",
                answer=ExecutionFailure("environment_changed", message),
                message=message,
                **common,
            )
        if document["outcome"] == "not_accepted":
            stage = document.get("stage")
            if isinstance(stage, str) and _STAGE.fullmatch(stage):
                return Execution(
                    status="completed", answer=NotAccepted(stage), stage=stage, **common
                )
            message = f"protocol_error: stage {stage!r} is not [A-Za-z0-9_]+"
        else:
            outlet = _parse_outlet(document.get("tube_outlet"), len(tube.composition))
            exported = self._exported(directory, document.get("diagnostics"))
            if outlet is not None and exported is not None:
                return Execution(
                    status="protocol_error",
                    answer=ExecutionFailure("protocol_error", exported),
                    message=exported,
                    **common,
                )
            if outlet is not None:
                return Execution(
                    status="completed",
                    answer=outlet,
                    tube_outlet=document["tube_outlet"],
                    **common,
                )
            message = "protocol_error: tube_outlet is not five finite flows, T and dP"
        return Execution(
            status="protocol_error",
            answer=ExecutionFailure("protocol_error", message),
            message=message,
            **common,
        )
