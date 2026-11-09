"""A synthetic start-capable external child for the default gate (X02 design note §7 G4, §5.5;
ADR 0070 D5–D7).

Run as `python -I synthetic_warm_child.py [--handshake]` by `adapters.external.launcher`, with the
project's own interpreter. It speaks the protocol of `synthetic_child.py`, whose helpers it loads
by path (`-I` keeps this repository off `sys.path`), and adds the start: the request's
`start_profile_sha256` names `start.json` in the working directory, which the backend wrote
before the launch, and after every `outlet` answer it exports `profile.json` and reports its
SHA-256 as `diagnostics.profile_sha256`.

Its "model" is a damped fixed-point iteration x ← x + ½ (f(inlet) − x) on a 16-vector, stopped at
‖Δx‖_∞ ≤ 1e-12, from zeros (cold) or from the start's vector (warm). f is analytic: its first
five entries are the stand-in's closed-form outlet flows per tube (ξ = 0.25 F y_N2), the sixth
the outlet temperature T_in, and the other ten T_in/(i + 1). The answer's `tube_outlet` is read
from the converged x, so it lies within 1e-11 of f whatever the start.

- **Warm.** A start is checked as the real warm child checks it (§5.6): the bytes hash to the
  request's `start_profile_sha256`, the document is `tube-profile-v1` of shape [16, 1, 1] with 16
  finite values; any failure is a runner defect, exit 72.
- **Fallback.** With `OFS_TEST_WARM_REFUSE=1` in its environment (a test switch, through the
  backend's `test_environment`) the warm chain refuses and the child runs the cold chain in the
  same attempt: `diagnostics.start.used` is false and `fallback_from` names the refused stage.
- **Export.** `profile.json` is `{"format": "tube-profile-v1", "shape": [16, 1, 1], "cpT": x}`
  as sorted, compact, ASCII JSON — the real warm child's encoding — written before `result.json`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

BASE = Path(__file__).with_name("synthetic_child.py")
SIZE = 16
SHAPE = [SIZE, 1, 1]
FORMAT = "tube-profile-v1"
START_FILE = "start.json"
PROFILE_FILE = "profile.json"
TOLERANCE = 1e-12
REFUSE_VARIABLE = "OFS_TEST_WARM_REFUSE"
REFUSED_STAGE = "S2"


def _base() -> Any:
    spec = importlib.util.spec_from_file_location("ofs_synthetic_child_base", BASE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def target(tube: dict[str, Any], nu: tuple[int, ...], conversion: float) -> list[float]:
    """f(inlet), the iteration's fixed point (module docstring)."""
    feed = [tube["flow"] * value for value in tube["composition"]]
    xi = conversion * feed[1]
    temperature = float(tube["temperature"])
    flows = [feed[i] + nu[i] * xi for i in range(len(nu))]
    return [*flows, temperature, *(temperature / (i + 1) for i in range(SIZE - len(flows) - 1))]


def iterate(start: list[float], f: list[float]) -> tuple[list[float], int]:
    x = list(start)
    steps = 0
    while True:
        steps += 1
        moved = [0.5 * (fi - xi) for fi, xi in zip(f, x, strict=True)]
        x = [xi + di for xi, di in zip(x, moved, strict=True)]
        if max(abs(d) for d in moved) <= TOLERANCE:
            return x, steps


def _start(sha256: str, mismatch: int) -> list[float]:
    data = Path(START_FILE).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        os._exit(mismatch)
    document = json.loads(data)
    values = document.get("cpT")
    if not (
        document.get("format") == FORMAT
        and document.get("shape") == SHAPE
        and isinstance(values, list)
        and len(values) == SIZE
        and all(
            isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)
            for v in values
        )
    ):
        os._exit(mismatch)
    return [float(v) for v in values]


def _export(x: list[float]) -> str:
    document = {"format": FORMAT, "shape": SHAPE, "cpT": x}
    data = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "ascii"
    )
    temporary = Path(PROFILE_FILE + ".tmp")
    temporary.write_bytes(data)
    os.rename(temporary, PROFILE_FILE)
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    base = _base()
    started = time.monotonic()
    request = json.loads(sys.stdin.buffer.readline())
    threading.Thread(target=base._lifeline, daemon=True).start()
    margin = float(os.environ.get(base.DEADLINE_MARGIN_VARIABLE, base.SELF_DEADLINE_MARGIN_S))
    deadline = threading.Timer(
        float(request["deadline_s"]) + margin, base._exit, args=(base.EXIT_SELF_DEADLINE,)
    )
    deadline.daemon = True
    deadline.start()

    runner = base._sha256(Path(__file__))
    expected = request.get("expected", {})
    if expected.get("runner_sha256") != runner:
        sys.stderr.write(f"runner_sha256 {runner} is not the expected one\n")
        sys.stderr.flush()
        os._exit(base.EXIT_ENVIRONMENT_MISMATCH)
    full = base._fingerprint(expected, runner)
    cheap = {name: full[name] for name in base.CHEAP}
    timing: dict[str, float] = {"startup_s": time.monotonic() - started}
    if base.HANDSHAKE_ARGUMENT in sys.argv:
        document: dict[str, Any] = {"outcome": base.OUTCOME_HANDSHAKE, "fingerprint": full}
    else:
        solve_started = time.monotonic()
        tube = request["tube_inlet"]
        f = target(tube, base.NU, base.CONVERSION)
        sha256 = request.get("start_profile_sha256")
        start: dict[str, Any] | None = None
        if sha256 is None:
            x, steps = iterate([0.0] * SIZE, f)
        else:
            vector = _start(sha256, base.EXIT_ENVIRONMENT_MISMATCH)
            if os.environ.get(REFUSE_VARIABLE) == "1":
                x, steps = iterate([0.0] * SIZE, f)
                start = {
                    "profile_sha256": sha256,
                    "used": False,
                    "fallback_from": REFUSED_STAGE,
                    "warm_stages": {REFUSED_STAGE: "not_accepted"},
                }
            else:
                x, steps = iterate(vector, f)
                start = {
                    "profile_sha256": sha256,
                    "used": True,
                    "fallback_from": None,
                    "warm_stages": {REFUSED_STAGE: steps},
                }
        flows = x[:5]
        document = {
            "outcome": base.OUTCOME_OUTLET,
            "tube_outlet": {
                "flows": flows,
                "temperature": x[5],
                "pressure_drop": 0.0,
                "coolant_heat": None,
                "inlet_face_heat_loss": None,
            },
            "diagnostics": {
                "synthetic": True,
                "iterations": steps,
                "start": start,
                "profile_sha256": _export(x),
            },
            "fingerprint": cheap,
        }
        timing["solve_s"] = time.monotonic() - solve_started
    result = {
        "protocol": base.PROTOCOL_VERSION,
        "request_sha256": request["request_sha256"],
        **document,
        "timing": timing,
    }
    base._write(result)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(1)
