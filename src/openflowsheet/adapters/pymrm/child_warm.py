"""The warm reactor child: profile `M01-S123W-v1`, the start-capable reactor of variant
`pymrm-6089593-g2-nz800-s123w-v1` (X02 design note §5.6; ADR 0070 D4, D7, D10).

Run like the base child (`<env>/venv/bin/python -I child_warm.py [--handshake]`), selected by the
variant's `runner_sha256` (D10). It is self-contained except for **one load**: the base child
`child.py` beside it, read by path, checked against `BASE_CHILD_SHA256` (v3's `runner_sha256`)
and executed as the module `ofs_pymrm_child_base`, whose `__main__` block does not run. This
file's own hash is the variant's `runner_sha256`, so the literal pins `child.py` transitively. A
base that does not hash to the literal exits 72 (`environment_mismatch`). Besides the loaded base
it imports only the standard library; no module of `openflowsheet` imports it. Every protocol
literal, the environment's checks, the model, S3, round 2, the certificate and the four
acceptance criteria are the base's, unchanged.

**Cold** (a request without `start_profile_sha256`). The base child's computation, unchanged:
`WarmReactor` overrides `outlet` only to remember the model it reads (a reference, never
written), and `_window` only to pass a cold call through to the base's. Its outlet is therefore
bitwise the base child's (gate G5a).

**Warm** (the request names `start_profile_sha256`). The backend wrote `start.json` in the attempt
directory before the launch. Its bytes must hash to the request's member, and the document must
be `tube-profile-v1` of shape `[num_z, 2, 7]` with `num_z·14` finite numbers; anything else is a
runner defect, exit 72. Then S1 does not run: S2 is built at the true inlet from the start's
`c`, `p` and `T`, exactly as the base builds it from S1's fields, with S2's `dt_init` (the base's
evidence switch included) and acceptance; S3, round 2, the certificate and the acceptance follow
unchanged. **On any refusal of the warm chain or a covered `model_exception` inside it**, the
cold chain runs in the same attempt and its outcome is the answer: `diagnostics.start` records
`used: false` and `fallback_from` (the warm refusal's stage). A cold request has
`diagnostics.start = null`.

**Export.** After every `outlet` answer that survives the non-finite screen, warm or cold, the
child writes `profile.json` (the remembered model's `cpT`, row-major, as `tube-profile-v1`; the
bytes are `json.dumps(…, sort_keys=True, separators=(",", ":"), allow_nan=False)` in ASCII)
before `result.json`, and reports its SHA-256 as `diagnostics.profile_sha256`; on any other
answer no file and `null`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import signal
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

#: The base child, loaded by path, and the SHA-256 it must have (v3's `runner_sha256`).
BASE_CHILD = Path(__file__).with_name("child.py")
BASE_CHILD_SHA256 = "0d2c345f1d414c457e047f698b9e6a3235701b91c4990ef2300d4375f753d893"
BASE_MODULE = "ofs_pymrm_child_base"
#: The exit of an environment that is not the request's (the base's literal; a test asserts it
#: equals the protocol's). Needed here before the base is loaded.
EXIT_BASE_MISMATCH = 72
#: The start's file (written by the backend), the exported profile, their format, and the
#: request member naming the start (ADR 0070 D6, D7; `adapters/experiments/backends.py`).
START_FILE = "start.json"
PROFILE_FILE = "profile.json"
PROFILE_TEMPORARY = "profile.json.tmp"
PROFILE_FORMAT = "tube-profile-v1"
START_MEMBER = "start_profile_sha256"
#: The fields per cell and side: the base's five species, then p, then T.
FIELDS = 7
SIDES = 2


class BaseMismatchError(Exception):
    """`child.py` is not the base this child pins."""


def _load_base() -> Any:
    data = BASE_CHILD.read_bytes() if BASE_CHILD.is_file() else b""
    measured = hashlib.sha256(data).hexdigest()
    if measured != BASE_CHILD_SHA256:
        raise BaseMismatchError(f"{BASE_CHILD.name} hashes to {measured}, not {BASE_CHILD_SHA256}")
    spec = importlib.util.spec_from_file_location(BASE_MODULE, BASE_CHILD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    base = _load_base()
except BaseMismatchError as error:
    if __name__ != "__main__":
        raise
    sys.stderr.write(f"environment_mismatch: {error}\n")
    sys.stderr.flush()
    os._exit(EXIT_BASE_MISMATCH)

#: The solver profile this child implements: the base's, renamed, plus the start.
PROFILE_W: dict[str, Any] = {
    **base.PROFILE,
    "id": "M01-S123W-v1",
    "start": {
        "kind": "profile",
        "format": PROFILE_FORMAT,
        "file": START_FILE,
        "replaces": ["S1"],
        "S2": "built at the true inlet from the start's c, p, T; dt_init and acceptance as S2",
        "fallback": "the S1-S3 chain of M01-S123-v2, in the same attempt, on any refusal or "
        "model_exception of the warm chain",
        "export": "profile.json after every outlet answer",
    },
}


def _configuration_w(request: dict[str, Any]) -> dict[str, Any]:
    """The base's configuration checks, against `PROFILE_W` instead of the base profile."""
    configuration = dict(request["configuration"])
    if configuration.get("profile") != PROFILE_W:
        raise base.MismatchError("the variant's profile is not the one this child implements")
    configuration["profile"] = base.PROFILE
    checked: dict[str, Any] = base._configuration({"configuration": configuration})
    return checked


# -- the start and the export (tube-profile-v1) ----------------------------------------------------


def profile_bytes(fields: Any) -> bytes:
    """A model's `cpT` (shape `[num_z, 2, 7]`) as the bytes of a `tube-profile-v1` document."""
    document = {
        "format": PROFILE_FORMAT,
        "shape": [int(size) for size in fields.shape],
        "cpT": [float(value) for value in fields.reshape(-1).tolist()],
    }
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return text.encode("ascii")


def export_profile(fields: Any, directory: Path) -> str:
    """Writes `profile.json` (of a model's `cpT`) atomically in `directory`; its SHA-256."""
    data = profile_bytes(fields)
    temporary = directory / PROFILE_TEMPORARY
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.rename(temporary, directory / PROFILE_FILE)
    return hashlib.sha256(data).hexdigest()


def read_start(directory: Path, sha256: Any, num_z: int) -> list[float]:
    """The start's `cpT` (row-major, `num_z·14` floats) from `start.json` in `directory`, after
    the checks of §5.6; any failure is `MismatchError` (a runner defect, exit 72)."""
    if not isinstance(sha256, str):
        raise base.MismatchError(f"{START_MEMBER} is not a string")
    path = directory / START_FILE
    if not path.is_file():
        raise base.MismatchError(f"the request names a start but there is no {START_FILE}")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise base.MismatchError(f"{START_FILE} does not hash to the request's {START_MEMBER}")
    try:
        document = json.loads(data)
    except ValueError as error:
        raise base.MismatchError(f"{START_FILE} is not JSON: {error}") from None
    values = document.get("cpT") if isinstance(document, dict) else None
    if not isinstance(document, dict) or document.get("format") != PROFILE_FORMAT:
        raise base.MismatchError(f"{START_FILE} is not a {PROFILE_FORMAT} document")
    if document.get("shape") != [num_z, SIDES, FIELDS]:
        raise base.MismatchError(f"{START_FILE}'s shape is not [{num_z}, {SIDES}, {FIELDS}]")
    if not isinstance(values, list) or len(values) != num_z * SIDES * FIELDS:
        size = num_z * SIDES * FIELDS
        raise base.MismatchError(f"{START_FILE}'s cpT does not hold {size} values")
    if not all(
        isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
        for value in values
    ):
        raise base.MismatchError(f"{START_FILE}'s cpT holds a value that is not a finite number")
    return [float(value) for value in values]


# -- the reactor -----------------------------------------------------------------------------------


class WarmReactor(base.Reactor):  # type: ignore[misc,name-defined]
    """The base reactor, plus the warm chain (S2 from a start, then the base's S3 onward)."""

    def __init__(self, configuration: dict[str, Any], database_path: Path) -> None:
        super().__init__(configuration, database_path)
        #: The model the last `outlet` read (a reference; never written).
        self.remembered: Any = None
        #: The start's `cpT` while the warm chain runs; `None` otherwise (the cold path).
        self._start: Any = None

    def outlet(self, model: Any, *args: Any) -> dict[str, Any]:
        self.remembered = model
        result: dict[str, Any] = super().outlet(model, *args)
        return result

    def _window(
        self,
        tube: dict[str, Any],
        y_in: list[float],
        y_trace: list[float],
        s2_dt_init: float | None,
        backflow: list[float],
        diagnostics: dict[str, Any],
    ) -> Any:
        if self._start is None:
            return super()._window(tube, y_in, y_trace, s2_dt_init, backflow, diagnostics)
        return self._warm_window(tube, y_in, s2_dt_init, backflow, diagnostics)

    def evaluate_w(
        self,
        tube: dict[str, Any],
        s2_dt_init: float | None,
        backflow: list[float],
        start: tuple[str, list[float]] | None,
    ) -> dict[str, Any]:
        """The evaluation: the base's without a start; the warm chain, then the cold chain on
        any refusal of it, with one. `diagnostics.start` records which answered."""
        self.remembered = None
        if start is None:
            document: dict[str, Any] = self.evaluate(tube, s2_dt_init, backflow)
            document["diagnostics"]["start"] = None
            return document
        sha256, values = start
        num_z = int(self.configuration["num_z"])
        self._start = self.np.asarray(values, dtype=float).reshape((num_z, SIDES, FIELDS))
        try:
            warm: dict[str, Any] = self.evaluate(tube, s2_dt_init, backflow)
        finally:
            self._start = None
        warm_diagnostics = warm["diagnostics"]
        stage = warm.get("stage")
        if warm["outcome"] == base.OUTCOME_OUTLET and base.nonfinite_paths(warm):
            stage = base.STAGE_NONFINITE
        if warm["outcome"] == base.OUTCOME_OUTLET and stage is None:
            warm_diagnostics["start"] = {
                "profile_sha256": sha256,
                "used": True,
                "fallback_from": None,
                "warm_stages": dict(warm_diagnostics["stages"]),
            }
            return warm
        warm_stages = dict(warm_diagnostics["stages"])
        if "model_exception" in warm_diagnostics:
            warm_stages[base.STAGE_MODEL_EXCEPTION] = warm_diagnostics["model_exception"]
        self.remembered = None
        cold: dict[str, Any] = self.evaluate(tube, s2_dt_init, backflow)
        cold["diagnostics"]["start"] = {
            "profile_sha256": sha256,
            "used": False,
            "fallback_from": stage,
            "warm_stages": warm_stages,
        }
        return cold

    def _warm_window(
        self,
        tube: dict[str, Any],
        y_in: list[float],
        s2_dt_init: float | None,
        backflow: list[float],
        diagnostics: dict[str, Any],
    ) -> str | tuple[dict[str, Any], dict[str, Any]]:
        """The base `_window` from S2 on, with S2 built from the start's fields in place of
        S1's (`child.py` `Reactor._window`; the lines after S2 are the base's)."""
        num_z = int(self.configuration["num_z"])
        stages: dict[str, Any] = diagnostics["stages"]
        model = self.model_class(backflow)
        started = time.perf_counter()
        config2, meta = self.config(tube, y_in)
        count = len(base.SPECIES)
        start = self._start
        second = model(
            config=config2,
            c=start[..., :count].copy(),
            p=start[..., -2].copy(),
            T=start[..., -1].copy(),
        )
        dt2 = self.settings.DT_INIT_1D if s2_dt_init is None else s2_dt_init
        status2 = second.solve(dt_init=dt2, return_status=True, verbose=0)
        stages["S2"] = self._stage(status2, self._accepted(status2, config2), started)
        stages["S2"]["dt_init"] = dt2
        if not stages["S2"]["accepted"]:
            return "S2"
        started = time.perf_counter()
        polish: Any = base.PROFILE["S3"]
        target = base.steady_state_target(num_z)
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
        refused, certificate = base.after_s3(
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


# -- main ------------------------------------------------------------------------------------------


def main_w() -> None:
    """The base `main`, with this file's runner hash, `_configuration_w`, and the start."""
    started = time.monotonic()
    attempt = Path.cwd()
    request = json.loads(sys.stdin.buffer.readline())
    threading.Thread(target=base._lifeline, daemon=True).start()
    margin = float(os.environ.get(base.DEADLINE_MARGIN_VARIABLE, base.SELF_DEADLINE_MARGIN_S))
    deadline = threading.Timer(
        float(request["deadline_s"]) + margin, base._exit, args=(base.EXIT_SELF_DEADLINE,)
    )
    deadline.daemon = True
    deadline.start()
    handshake = base.HANDSHAKE_ARGUMENT in sys.argv
    try:
        if request.get("protocol") != base.PROTOCOL_VERSION:
            raise base.MismatchError(
                f"protocol {request.get('protocol')!r} is not {base.PROTOCOL_VERSION}"
            )
        environment = base.Environment(request.get("expected", {}), base._sha256(Path(__file__)))
        configuration = _configuration_w(request)
        s2_dt_init, backflow_alt = base._evidence_switches()
        start: tuple[str, list[float]] | None = None
        if not handshake and request.get(START_MEMBER) is not None:
            sha256 = request[START_MEMBER]
            start = (sha256, read_start(attempt, sha256, int(configuration["num_z"])))
        if handshake:
            environment.verify_fully()
        environment.import_reactor()
        reactor = WarmReactor(configuration, environment.database)
    except base.MismatchError as error:
        sys.stderr.write(f"environment_mismatch: {error}\n")
        sys.stderr.flush()
        base._exit(base.EXIT_ENVIRONMENT_MISMATCH)
        raise  # unreachable: `_exit` does not return
    full = environment.fingerprint(attempt)
    solve_started = time.monotonic()
    timing: dict[str, float] = {"startup_s": solve_started - started}
    if handshake:
        document: dict[str, Any] = {"outcome": base.OUTCOME_HANDSHAKE, "fingerprint": full}
    else:
        backflow = base.BACKFLOW_ALT if backflow_alt else list(configuration["backflow"])
        document = reactor.evaluate_w(request["tube_inlet"], s2_dt_init, backflow, start)
        document["fingerprint"] = {name: full[name] for name in base.CHEAP}
        document["diagnostics"]["evidence"] = {
            "s2_dt_init": s2_dt_init,
            "backflow_alt": backflow_alt,
        }
    timing["solve_s"] = time.monotonic() - solve_started
    result = {
        "protocol": base.PROTOCOL_VERSION,
        "request_sha256": request["request_sha256"],
        **document,
        "timing": timing,
    }
    if not handshake:
        result = base.nonfinite_screen(result)
        exported = None
        if result["outcome"] == base.OUTCOME_OUTLET:  # written before result.json
            assert reactor.remembered is not None, "an outlet answer reads a model"
            exported = export_profile(reactor.remembered.cpT, attempt)
        result["diagnostics"]["profile_sha256"] = exported
    base._write(result, attempt)
    base._exit(0)


if __name__ == "__main__":
    # As the base child's guard: every exit is `os._exit`; SIGINT keeps its default action.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        main_w()
    except Exception:
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(1)
    os._exit(0)  # unreachable: `main_w` leaves through `os._exit`
