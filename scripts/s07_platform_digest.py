"""`benchmarks/s07/platform_digest.json`: the S07 provider's A03-A13 answers, `float.hex` per fluid.

Spec §9 A31 and §12.3 item 2. The digest is a regression fixture, not validation: it records what
`coolprop-heos-v1` answers on the machine that wrote it (x86-64), so that CI can recompute the
answers on `ubuntu-24.04-arm` and compare them (Q-1: bitwise, or the pre-registered bound).

The inputs are the states of `s07_reference.json` (`phi_states`, `tp_states`, `saturation`,
`tsat`, `band`); no reference *value* is read. Per fluid, in a fixed order (tier B stops where
§16.10 stops):

- A03/A04: the 20 slots of (alpha°, alphar) at each `phi_states` entry;
- A05 (and A06 for tier A): h, s, v, Z, cp, lnphi at each `tp_states` entry, and for tier A their
  T and P derivatives;
- A08/A09: Psat and its T derivative at each `saturation` entry (tier A: every one; tier B:
  `sat_mid`), and Tsat at `tsat_mid`;
- A10/A11: both saturated phases' h, s, v, lnphi at {T_lo, T_mid, T_sigma_max}, Psat and dPsat/dT;
- A12 (H2O): u and s of the saturated liquid at 273.16 K and 450 K;
- A13: the six values at each answered phase of each `band` probe.

A refusal is recorded as the string `status:code`. The file holds the values only, in
`answers(cid)`'s order (its keys are regenerated; the test also compares their count).
`answers(cid)` returns (key, value, scale) rows; `scale` is A17's FD scale s_f (`R*T` for h, `R`
for s and cp, 1 for Z, lnphi and the jet slots, 0 for v and the saturation quantities; a
derivative takes its quantity's scale over T or P), the floor of Q-1's comparison
`|d| <= bound * max(|x|, s_f)`.

`compare()` is A31: it recomputes every answer and compares it with the digest. Outcome (a) is
bitwise equality. Otherwise (Q-1's pre-registered rule) every answer must satisfy
`|d| <= bound * max(|x|, s_f)`, with bound 1e-12 for tier A (1e-10 at the NC states) and 1e-10 for
tier B (spec §11 Q-1, §16.11); the worst ratio per quantity is reported. Above the bound the
comparison fails: nothing is loosened here.

Usage (CoolProp 8.0.0 environment, from the repository root):
    PYTHONPATH=src python scripts/s07_platform_digest.py [--check | --report]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs" / "derivations" / "scripts" / "s07_reference.json"
DIGEST = ROOT / "benchmarks" / "s07" / "platform_digest.json"
SAT_TEMPERATURES = ("T_lo", "T_mid", "T_sigma_max")
Row = tuple[str, "float | str", float]


def _modules() -> tuple[Any, Any, Any]:
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.thermo import _coolprop_heos_fluids as table
    from openflowsheet.thermo import coolprop_heos as cph

    return EvaluationContext, table, cph


def _scale(quantity: str, r: float, t: float) -> float:
    if quantity == "h":
        return r * t
    if quantity in ("s", "cp"):
        return r
    if quantity == "Z" or quantity.startswith("lnphi_"):
        return 1.0
    return 0.0


def answers(cid: str, reference: dict[str, Any] | None = None) -> list[Row]:
    """The fluid's rows (key, value or refusal string, scale), in the digest's fixed order."""
    from openflowsheet.thermo import PropertyRequest, StreamState

    evaluation_context, table, cph = _modules()
    reference = reference or json.loads(REFERENCE.read_text("utf-8"))
    fluid = reference["fluids"][cid]
    tier = next(row["tier"] for row in table.FLUIDS if row["id"] == cid)
    constants = fluid["constants"]
    r = float(constants["R"])
    provider = cph.CoolPropHeosProvider(cid)
    context = evaluation_context(model_version="s07-provider", constants_sha256="0" * 64)
    properties = ("h", "s", "v", "Z", "cp", f"lnphi_{cid}")
    rows: list[Row] = []

    def evaluate(
        t: float, p: float, phase: str, names: tuple[str, ...], derivatives: tuple[str, ...]
    ) -> Any:
        state = StreamState(n=(1.0,), temperature=t, pressure=p)
        return provider.evaluate_phase(
            PropertyRequest(state, phase, names, derivatives),  # type: ignore[arg-type]
            context,
        )

    def record(tag: str, result: Any, names: tuple[str, ...], t: float, p: float, d: bool) -> None:
        if result.status != "ok":
            rows.append((f"{tag}.status", f"{result.status}:{result.message.split(':')[0]}", 0.0))
            return
        for x in names:
            scale = _scale(x, r, t)
            rows.append((f"{tag}.{x}", float(result.values[x]), scale))
            if d:
                for wrt, divisor in (("T", t), ("P", p)):
                    value = float(result.derivatives[x][wrt])
                    rows.append((f"{tag}.d{wrt}.{x}", value, scale / divisor))

    for key in sorted(fluid["phi_states"]):
        state = fluid["phi_states"][key]
        ideal, residual = cph.helmholtz_jet(cid, state["T"], state["rho"])
        for slot, value in enumerate([*ideal, *residual]):
            rows.append((f"phi.{key}.{slot}", float(value), 1.0))
    for key in sorted(fluid["tp_states"]):
        state = fluid["tp_states"][key]
        t, p = float(state["values"][0]), float(state["values"][1])
        phase = "LIQUID" if state["phase"] == "LIQUID" else "VAPOR"
        derivatives = ("T", "P", f"n_{cid}") if tier == "A" else ()
        result = evaluate(t, p, phase, properties, derivatives)
        record(f"tp.{key}", result, properties, t, p, tier == "A")

    def saturation(t: float) -> Any:
        return evaluate(t, 1.0e5, "LIQUID", ("Psat",), ("T", "P", f"n_{cid}"))

    for key in sorted(fluid["saturation"]):
        if tier == "B" and key != "sat_mid":
            continue
        t = float(fluid["saturation"][key]["T"])
        sat = saturation(t)
        if sat.status != "ok":
            rows.append((f"sat.{key}.status", f"{sat.status}:{sat.message.split(':')[0]}", 0.0))
            continue
        rows.append((f"sat.{key}.Psat", float(sat.values["Psat"]), 0.0))
        rows.append((f"sat.{key}.dT", float(sat.derivatives["Psat"]["T"]), 0.0))
    band_t = float(fluid["band"]["T"])
    tsat = evaluate(
        band_t, float(fluid["tsat"]["tsat_mid"]["P"]), "VAPOR", ("Tsat",), ("T", "P", f"n_{cid}")
    )
    if tsat.status == "ok":
        rows.append(("tsat.Tsat", float(tsat.values["Tsat"]), 0.0))
        rows.append(("tsat.dP", float(tsat.derivatives["Tsat"]["P"]), 0.0))
    else:
        rows.append(("tsat.status", f"{tsat.status}:{tsat.message.split(':')[0]}", 0.0))

    def phases_at(t: float) -> tuple[Any, dict[str, dict[str, float]]]:
        """Psat at T and both saturated phases; below P_lo through the provider's own saturation
        state (B-18, as `tests/test_s07_coolprop.py`'s `saturated_phases`)."""
        sat = saturation(t)
        if sat.status != "ok":
            return sat, {}
        p = float(sat.values["Psat"])
        if p >= provider._fluid.p_lo:
            pair = {phase: evaluate(t, p, phase, properties, ()) for phase in ("LIQUID", "VAPOR")}
            return sat, {
                phase: {x: float(result.values[x]) for x in properties}
                for phase, result in pair.items()
                if result.status == "ok"
            }
        root = provider._saturation(t)
        values = {}
        for phase, rho in (("LIQUID", root.rho_l), ("VAPOR", root.rho_v)):
            at = provider._at(t, rho, p)
            values[phase] = {x: float(at[x][0]) for x in properties}
        return sat, values

    for key in SAT_TEMPERATURES:
        t = float(fluid["saturation"]["sat_mid"]["T"]) if key == "T_mid" else float(constants[key])
        sat, values = phases_at(t)
        if sat.status != "ok":
            rows.append((f"a10.{key}.status", f"{sat.status}:{sat.message.split(':')[0]}", 0.0))
            continue
        rows.append((f"a10.{key}.Psat", float(sat.values["Psat"]), 0.0))
        rows.append((f"a10.{key}.dT", float(sat.derivatives["Psat"]["T"]), 0.0))
        for phase in ("LIQUID", "VAPOR"):
            for x in properties:
                if phase in values:
                    rows.append((f"a10.{key}.{phase}.{x}", values[phase][x], _scale(x, r, t)))
    if cid == "H2O":
        for t in (273.16, 450.0):
            sat, values = phases_at(t)
            liquid = values["LIQUID"]
            rows.append(
                (f"a12.{t}.u", liquid["h"] - float(sat.values["Psat"]) * liquid["v"], r * t)
            )
            rows.append((f"a12.{t}.s", liquid["s"], r))
    for key in sorted(fluid["band"]["probes"]):
        probe = fluid["band"]["probes"][key]
        for phase in sorted(probe["answered"]):
            result = evaluate(band_t, float(probe["P"]), phase, properties, ())
            record(f"band.{key}.{phase}", result, properties, band_t, float(probe["P"]), False)
    return rows


BOUND_A, BOUND_NC, BOUND_B = 1e-12, 1e-10, 1e-10


def quantity(key: str) -> str:
    """The key without its state name: the quantity a worst is reported for."""
    parts = key.split(".")
    if parts[0] == "phi":
        return "phi.slot"
    if parts[0] in ("band", "sat"):
        return f"{parts[0]}.{parts[-1]}"
    return ".".join([parts[0], *parts[2:]]) if parts[0] in ("tp", "a10", "a12") else key


def compare(digest: dict[str, Any] | None = None) -> dict[str, Any]:
    """A31: recompute and compare. Returns `bitwise` (every answer equal), `failures` (answers
    above their bound, or of another kind), `worst` (per quantity: ratio, fluid, key) and the
    worst over all."""
    _, table, _ = _modules()
    digest = digest or json.loads(DIGEST.read_text("utf-8"))
    reference = json.loads(REFERENCE.read_text("utf-8"))
    failures: list[str] = []
    worst: dict[str, tuple[float, str, str]] = {}
    bitwise = True
    for row in table.FLUIDS:
        cid, tier = row["id"], row["tier"]
        stored = digest["fluids"][cid]
        rows = answers(cid, reference)
        if len(rows) != len(stored):
            failures.append(f"{cid}: {len(rows)} answers, the digest holds {len(stored)}")
            bitwise = False
            continue
        for (key, value, scale), hexed in zip(rows, stored, strict=True):
            if isinstance(value, str) or ":" in hexed:
                if value != hexed:
                    failures.append(f"{cid} {key}: {value!r} vs {hexed!r}")
                    bitwise = False
                continue
            expected = float.fromhex(hexed)
            if value == expected:
                continue
            bitwise = False
            ratio = abs(value - expected) / max(abs(expected), scale)
            bound = BOUND_B if tier == "B" else BOUND_NC if ".NC_" in key else BOUND_A
            group = quantity(key)
            if group not in worst or ratio > worst[group][0]:
                worst[group] = (ratio, cid, key)
            if not ratio <= bound:
                failures.append(
                    f"{cid} {key}: {value.hex()} vs {hexed}, ratio {ratio:.3e} > {bound:g}"
                )
    overall = max((entry[0] for entry in worst.values()), default=0.0)
    return {"bitwise": bitwise, "failures": failures, "worst": worst, "overall": overall}


def summary(result: dict[str, Any]) -> str:
    """One line: the outcome of A31 for the machine it ran on."""
    import platform

    head = f"S07 A31 ({platform.machine()}): "
    if result["bitwise"]:
        return head + "bit-identical (every answer equal to the x86-64 digest)"
    worst = max(
        result["worst"].items(), key=lambda item: item[1][0], default=("-", (0.0, "-", "-"))
    )
    status = "within the pre-registered bounds" if not result["failures"] else "FAILS"
    return (
        head
        + f"not bitwise, {status}; worst {result['overall']:.3e} "
        + f"({worst[0]}: {worst[1][1]} {worst[1][2]}); "
        + "per quantity "
        + ", ".join(f"{name} {entry[0]:.2e}" for name, entry in sorted(result["worst"].items()))
    )


def build() -> dict[str, Any]:
    _, table, cph = _modules()
    reference = json.loads(REFERENCE.read_text("utf-8"))
    return {
        "schema": "s07-platform-digest-v1",
        "note": "A31 regression fixture (x86-64): float.hex of every A03-A13 answer, in "
        "scripts/s07_platform_digest.py's answers() order; not validation",
        "coolprop_version": cph.PINNED_COOLPROP_VERSION,
        "fluids": {
            row["id"]: [
                value.hex() if isinstance(value, float) else value
                for _, value, _ in answers(row["id"], reference)
            ]
            for row in table.FLUIDS
        },
    }


def render(digest: dict[str, Any]) -> str:
    """One line per fluid: compact, stable, and diffable."""
    lines = [
        f"{json.dumps(cid)}: {json.dumps(rows, separators=(',', ':'))}"
        for cid, rows in digest["fluids"].items()
    ]
    head = {key: value for key, value in digest.items() if key != "fluids"}
    return json.dumps(head, indent=1)[:-2] + ',\n "fluids": {\n' + ",\n".join(lines) + "\n }\n}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--check", action="store_true", help="regenerate and compare with the file")
    parser.add_argument("--report", action="store_true", help="A31: compare, print one line")
    arguments = parser.parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    if arguments.report:
        result = compare()
        print(summary(result))
        for line in result["failures"][:20]:
            print(f"  {line}")
        return 1 if result["failures"] else 0
    text = render(build())
    json.loads(text)
    if arguments.check:
        same = DIGEST.read_text("utf-8") == text
        print(f"{DIGEST.relative_to(ROOT)}: {'OK (byte-identical)' if same else 'DIFFERS'}")
        return 0 if same else 1
    DIGEST.write_text(text, encoding="utf-8")
    print(f"{DIGEST.relative_to(ROOT)}: written, {len(text)} bytes, {len(text.splitlines())} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
