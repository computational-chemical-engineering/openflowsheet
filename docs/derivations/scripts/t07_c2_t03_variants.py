# ruff: noqa: E501  (long claim names and quoted provenance strings; a derivation twin)
"""Independent roots for the three unjudged T03 `VERIFIED` certificates of campaign `v17-c2`.

Supplementary to `docs/reviews/T07-verdicts.md` §3.3 and §6 item 1. In `v17-c2`, T03-1, T03-2 and
T03-3 each committed a variant of the T03 fixture (SYN-001-UL-C1 with `U-PHF.duty.Q` changed from
the infeasible 250 000 W) and solved it as `job-000002`, which ended CONVERGED / VERIFIED. The
registered scorer leaves these unjudged because no root is registered for their signatures. This
script computes that root with the SYN-001 twin, by the method the twin uses for T03's registered
state (spec §5.3, `t05_reference.coupled_c1` and `t07_reference.ph_bounds`), at each revision's
own duty, and compares every coordinate of each certified state against it.

It imports only the twin (`t05_reference`, `t07_reference`, and through them `t06_reference` and
`syn001_reference`) and the standard library; it asserts at the end that neither
`process_runtime` nor `benchmarks` was imported. The run records are read as JSON bytes.

    .venv/bin/python t03_variant_roots.py --repo <checkout> --emit t03_variant_roots.json
    .venv/bin/python t03_variant_roots.py --repo <checkout> --check t03_variant_roots.json

`--emit` refuses to write when any claim below fails; `--check` re-derives everything and
requires the emitted file to be byte-identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from mpmath import mp, mpf

CAMPAIGN = "v17-c2"
#: The runs and the duty each one's session revision is expected to pin (verdict §3.3). The
#: script asserts the pin from the revision document; it does not take it from here.
RUNS = {"V17-T03-1": 50000, "V17-T03-2": 10000, "V17-T03-3": 0}
JOB = "job-000002"
REVISION = "rev-000002"
BUNDLE = f"{JOB}:bundle"
#: A certified state is judged to miss when some coordinate is more than this many allowances
#: away. Used only to show that the comparison discriminates between the three duties.
SEPARATION = 100
FINE_GRID = 1600  # 0.1 K steps on [280, 440] K for the sign-change scan


class Claims:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, detail: Any = "") -> None:
        self.rows.append((name, bool(ok), str(detail)))

    @property
    def failed(self) -> list[tuple[str, bool, str]]:
        return [r for r in self.rows if not r[1]]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------------------------------------
# The twin's C1 at an arbitrary PH-flash duty (the chain of t05_reference.coupled_c1)
# ------------------------------------------------------------------------------------------------


def c1_at(t5: Any, q: Any) -> dict[str, Any]:
    """SYN-001-UL-C1 with `U-PHF.duty.Q = q`: feed -> pump -> TP heater -> valve -> PH flash.

    The same evaluator calls, in the same order and with the same arguments, as
    `t05_reference.coupled_c1()`, whose duty is fixed at 10 000 W."""
    q = mpf(q)
    s1 = t5.stream(t5.Z_EQ, 300, t5.P_R)
    pump = t5.eval_pump(s1, mpf(180000), mpf("0.75"))
    s2 = pump["outlet"]
    heater = t5.eval_heater(s2, mpf(360))
    s3 = heater["outlet"]
    valve = t5.eval_valve(s3, None, t5.P_R)
    if valve["status"] != "ok":
        raise ValueError(valve)
    s4 = valve["outlet"]
    flash = t5.eval_ph_flash(s4, None, q, mpf(0))
    return {
        "streams": {
            "S1": s1,
            "S2": s2,
            "S3": s3,
            "S4": s4,
            "S5": flash["vapor"],
            "S6": flash["liquid"],
        },
        "work": {"U-PUMP": pump["work"]},
        "duty": {"U-HEAT": heater["duty"], "U-PHF": q},
        "flash": flash,
        "valve": valve,
        "pump": pump,
        "heater": heater,
    }


def root_coordinates(t7: Any, case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """(registered-kind coordinates, the other coordinates a SYN-001 solution state carries).

    Registered kinds (spec §4.6, GC-03, `t07_reference.coords`): every stream's n, T, P and every
    duty. The others are the lifted splits of the heater and valve outlets (S3, S4: `.V`, `.L`,
    `.vap.<c>`, `.liq.<c>`), the product totals (`S5.N`, `S6.N`) and the pump work."""
    registered = t7.coords(case["streams"], case["duty"])
    other: dict[str, Any] = {}
    zero = mpf(0)
    for sid in ("S3", "S4"):
        st = case["streams"][sid]
        other[f"{sid}.V"] = sum(st["v"], zero)
        other[f"{sid}.L"] = sum(st["l"], zero)
        for i, c in enumerate(t7.COMPONENTS):
            other[f"{sid}.vap.{c}"] = st["v"][i]
            other[f"{sid}.liq.{c}"] = st["l"][i]
    for sid in ("S5", "S6"):
        other[f"{sid}.N"] = sum(case["streams"][sid]["n"], zero)
    other["U-PUMP.W"] = case["work"]["U-PUMP"]
    return registered, other


def allowance_kind(t7: Any, var_id: str) -> tuple[str, bool]:
    """(kind, registered?). Registered kinds come from the id as GC-03 reads them; for the other
    coordinates the kind is the physical one (a flow in mol/s, the pump work in W)."""
    try:
        return t7.kind_of(var_id), True
    except ValueError:
        pass
    if var_id.endswith(".W"):
        return "heat_rate", False
    if var_id.endswith((".V", ".L", ".N")) or ".vap." in var_id or ".liq." in var_id:
        return "molar_flow", False
    raise ValueError(var_id)


def exact(value: Any) -> Fraction:
    """A binary64 JSON number, or a decimal string, as an exact rational (the scorer's `_exact`)."""
    if isinstance(value, str):
        return Fraction(Decimal(value))
    if isinstance(value, bool):
        raise TypeError(value)
    return Fraction(value)


def within(value: Any, ref20: str, allowance: str) -> bool:
    """The scorer's `within`: |v - ref| <= a, exactly, with ref at 20 significant digits."""
    return abs(exact(value) - exact(ref20)) <= exact(allowance)


# ------------------------------------------------------------------------------------------------
# Signature (spec §4.5), extracted here from the document, independently of the scorer
# ------------------------------------------------------------------------------------------------

SI_UNITS = {"1", "Pa", "K", "W", "mol/s"}


def signature(doc: dict[str, Any]) -> dict[str, Any]:
    instances: dict[str, Any] = {}
    own: dict[tuple[str, str], float] = {}
    for inst in doc["instances"]:
        params: dict[str, float] = {}
        for name, p in inst["parameters"].items():
            assert p["unit"] in SI_UNITS, p
            own[(inst["id"], name)] = float(p["value"])
            if float(p["value"]) != 0.0:
                params[name] = float(p["value"])
        instances[inst["id"]] = {"model": inst["model"]["id"], "parameters": params}
    connections = {
        c["id"]: {
            "from": [c["from"]["instance"], c["from"]["port"]],
            "to": [c["to"]["instance"], c["to"]["port"]],
            "phase": c["phase_capability"],
        }
        for c in doc["connections"]
    }
    pins: dict[str, float] = {}
    for spec in doc["specifications"]:
        if spec["role"] != "fixed":
            continue
        assert spec["unit"] in SI_UNITS, spec
        t = spec["target"]
        if t["object_type"] == "connection":
            path = t["path"]
            col = {
                "state.n": f"{t['object_id']}.n.{t['component']}",
                "state.T": f"{t['object_id']}.T",
                "state.P": f"{t['object_id']}.P",
            }[path]
        else:
            col = f"{t['object_id']}.{t['path']}"
            parts = t["path"].split(".")
            if parts[0] == "parameters" and own.get((t["object_id"], parts[1])) == float(
                spec["value"]
            ):
                continue
        assert col not in pins or pins[col] == float(spec["value"]), col
        pins[col] = float(spec["value"])
    return {
        "components": list(doc["component_set"]["components"]),
        "instances": instances,
        "connections": connections,
        "pins": pins,
    }


def signatures_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """§4.5: equal key sets and strings; numbers equal as binary64 (decimal strings allowed)."""

    def num(x: Any) -> float:
        return float(x)

    if list(a["components"]) != list(b["components"]):
        return False
    if set(a["instances"]) != set(b["instances"]):
        return False
    for k, left in a["instances"].items():
        right = b["instances"][k]
        if left["model"] != right["model"] or set(left["parameters"]) != set(right["parameters"]):
            return False
        if any(num(v) != num(right["parameters"][n]) for n, v in left["parameters"].items()):
            return False
    if a["connections"] != b["connections"]:
        return False
    if set(a["pins"]) != set(b["pins"]):
        return False
    return all(num(v) == num(b["pins"][k]) for k, v in a["pins"].items())


# ------------------------------------------------------------------------------------------------
# The computation
# ------------------------------------------------------------------------------------------------


def run(repo: Path) -> tuple[Claims, dict[str, Any]]:
    scripts = repo / "docs" / "derivations" / "scripts"
    sys.path.insert(0, str(scripts))
    import t05_reference as t5  # noqa: PLC0415
    import t07_reference as t7  # noqa: PLC0415

    mp.dps = 40
    c = Claims()
    s = t7.s
    runs_dir = repo / "benchmarks" / "t07" / "v17" / "runs"
    sums = {}
    for line in (runs_dir / f"{CAMPAIGN}.SHA256SUMS").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        sums[name] = digest

    # ---- 0. The parameterization is the twin's own C1 --------------------------------------------
    reg = t5.coupled_c1()
    mine = c1_at(t5, 10000)
    same = (
        all(
            mine["streams"][sid][key] == reg["streams"][sid][key]
            for sid in reg["streams"]
            for key in ("n", "T", "P")
        )
        and all(mine["duty"][u] == reg["duty"][u] for u in reg["duty"])
        and (mine["work"]["U-PUMP"] == reg["work"]["U-PUMP"])
    )
    c.check("P0.c1_at_10kW_equals_twin_coupled_c1_exactly", same)

    # ---- 1. The inlet to the drum, its attainable duties, and uniqueness -------------------------
    s4 = mine["streams"]["S4"]
    bounds = t7.ph_bounds(s4, None, t5.P_R)
    c.check("P1.enthalpy_strictly_increasing_161pt_GC09_grid", t7.h_increasing(s4["n"], t5.P_R))
    c.check(
        "P1.valve_outlet_two_phase",
        mine["valve"]["signature"] == "TWO_PHASE",
        mine["valve"]["signature"],
    )
    c.check(
        "P1.heater_outlet_liquid",
        mine["streams"]["S3"]["regime"] == "LIQUID",
        mine["streams"]["S3"]["regime"],
    )
    t_bub, t_dew = t5.bubble_dew(s4["n"], t5.P_R)

    roots: dict[str, Any] = {}
    for run_id, q_expected in RUNS.items():
        case = c1_at(t5, q_expected)
        fl = case["flash"]
        c.check(f"{run_id}.root_exists", fl["status"] == "ok", fl.get("code"))
        registered, other = root_coordinates(t7, case)
        roots[run_id] = {"case": case, "registered": registered, "other": other}

    # Every duty inside the attainable range, by a margin; exactly one sign change on a fine grid.
    grid = [t5.T_MIN + (t5.T_MAX - t5.T_MIN) * mpf(i) / FINE_GRID for i in range(FINE_GRID + 1)]
    h_grid = [t5.h_tp(s4["n"], t, t5.P_R) for t in grid]
    for run_id, q in RUNS.items():
        qm = mpf(q)
        c.check(
            f"{run_id}.duty_inside_attainable_range",
            bounds["Q_min_W"] < qm < bounds["Q_max_W"],
            (s(bounds["Q_min_W"]), q, s(bounds["Q_max_W"])),
        )
        h_target = bounds["H_in_W"] + qm
        f = [h - h_target for h in h_grid]
        changes = sum(1 for i in range(FINE_GRID) if (f[i] < 0) != (f[i + 1] < 0))
        increasing = all(f[i + 1] > f[i] for i in range(FINE_GRID))
        c.check(
            f"{run_id}.fine_grid_increasing_one_sign_change",
            increasing and changes == 1,
            (increasing, changes),
        )

    # ---- 2. The phase regime of each root --------------------------------------------------------
    for run_id in RUNS:
        case = roots[run_id]["case"]
        fl = case["flash"]
        split = t5.tp_split(s4["n"], fl["T"], t5.P_R)
        beta = fl["beta"]
        roots[run_id]["regime"] = {
            "signature": fl["signature"],
            "T_K": fl["T"],
            "beta": beta,
            "sum_zK_minus_1": split["szk"] - 1,
            "sum_z_over_K_minus_1": split["szik"] - 1,
            "T_minus_T_bubble_K": fl["T"] - t_bub,
            "T_dew_minus_T_K": t_dew - fl["T"],
            "route": fl["route"],
        }
        c.check(f"{run_id}.root_two_phase", fl["signature"] == "TWO_PHASE", fl["signature"])
        c.check(
            f"{run_id}.root_regime_margins_ge_1e-3",
            split["szk"] - 1 >= t5.PHASE_MARGIN and split["szik"] - 1 >= t5.PHASE_MARGIN,
            (s(split["szk"] - 1, 6), s(split["szik"] - 1, 6)),
        )
        c.check(f"{run_id}.beta_strictly_inside", 0 < beta < 1, s(beta))
        c.check(
            f"{run_id}.root_between_bubble_and_dew",
            t_bub < fl["T"] < t_dew,
            (s(t_bub), s(fl["T"]), s(t_dew)),
        )
    # At 0 W the drum is adiabatic at the inlet pressure: its products are the valve's split.
    z = roots["V17-T03-3"]["case"]
    zf, zv = z["flash"], z["streams"]["S4"]
    c.check(
        "V17-T03-3.adiabatic_root_is_inlet_split",
        abs(zf["T"] - zv["T"]) < mpf("1e-30")
        and all(abs(zf["vapor"]["n"][i] - zv["v"][i]) < mpf("1e-30") for i in range(3)),
        s(abs(zf["T"] - zv["T"]), 3),
    )

    # ---- 3. The records --------------------------------------------------------------------------
    results: dict[str, Any] = {}
    for run_id, q_expected in RUNS.items():
        rel = f"./{run_id}/store-export.json"
        raw = (runs_dir / CAMPAIGN / run_id / "store-export.json").read_bytes()
        digest = sha256_bytes(raw)
        c.check(f"{run_id}.store_export_matches_SHA256SUMS", sums.get(rel) == digest, digest)
        export = json.loads(raw)
        verified = [
            j
            for j, rr in export["run_results"].items()
            if rr.get("verification_status") == "VERIFIED"
        ]
        c.check(f"{run_id}.only_{JOB}_verified", verified == [JOB], verified)
        job = next(j for j in export["jobs"] if j["job_id"] == JOB)
        c.check(
            f"{run_id}.job_by_agent_on_{REVISION}",
            job["principal_id"] == "agent-v17"
            and job["request"]["body"]["revision_id"] == REVISION
            and job["request"]["body"]["check_tolerances"] == {},
            (job["principal_id"], job["request"]["body"]["revision_id"]),
        )
        store_rev = next(r for r in export["revisions"] if r["revision_id"] == REVISION)["document"]
        docs = export["artifact_documents"]
        bundle_rev = docs[f"{BUNDLE}/revision.json"]
        c.check(f"{run_id}.bundle_revision_equals_store_revision", bundle_rev == store_rev)
        cert = docs[f"{BUNDLE}/solution-certificate.json"]
        state_doc = docs[f"{BUNDLE}/solution-state.json"]
        c.check(
            f"{run_id}.certificate_VERIFIED_on_this_state",
            cert["verification_status"] == "VERIFIED"
            and cert["target_state_sha256"] == state_doc["state_sha256"]
            and cert["limitations"] == []
            and cert["false_success_detected"] is False,
            (cert["verification_status"], cert["target_state_sha256"][:12]),
        )

        # The revision is UL-C1 exactly, with only the duty changed, and the duty is q_expected.
        sig = signature(bundle_rev)
        q_pinned = sig["pins"]["U-PHF.duty.Q"]
        c.check(f"{run_id}.duty_pin_is_{q_expected}", q_pinned == float(q_expected), q_pinned)
        c.check(
            f"{run_id}.signature_is_UL_C1_at_its_duty",
            signatures_equal(sig, t7.sig_c1(str(q_expected))),
        )
        c.check(
            f"{run_id}.signature_differs_from_T03_fixture",
            not signatures_equal(sig, t7.sig_c1("250000")),
        )

        # Every coordinate of the certified state against the root at the same duty.
        state = state_doc["variables"]
        registered, other = roots[run_id]["registered"], roots[run_id]["other"]
        expected_ids = set(registered) | set(other)
        c.check(
            f"{run_id}.state_ids_equal_root_ids",
            set(state) == expected_ids,
            sorted(set(state) ^ expected_ids),
        )
        rows = []
        worst_reg = (mpf(0), "")
        worst_all = (mpf(0), "")
        misses = []
        for vid in sorted(expected_ids):
            ref = registered.get(vid, other.get(vid))
            kind, is_reg = allowance_kind(t7, vid)
            allowance = t7.ALLOWANCE[kind]
            value = state[vid]
            dev = abs(mpf(value) - ref)
            ratio = dev / allowance
            ok = within(value, s(ref), s(allowance))
            if not ok:
                misses.append(vid)
            if is_reg and ratio >= worst_reg[0]:
                worst_reg = (ratio, vid)
            if ratio >= worst_all[0]:
                worst_all = (ratio, vid)
            rows.append(
                {
                    "id": vid,
                    "registered_kind": is_reg,
                    "kind": kind,
                    "certified": value,
                    "root": s(ref),
                    "deviation_over_allowance": s(ratio, 3),
                    "within": ok,
                }
            )
        c.check(f"{run_id}.every_coordinate_within_allowance", not misses, misses)

        # The certified branch: both products flowing, beta and T equal to the root's.
        v_tot, l_tot = mpf(state["S5.N"]), mpf(state["S6.N"])
        beta_cert = v_tot / (v_tot + l_tot)
        c.check(f"{run_id}.certified_state_two_phase", v_tot > 0 and l_tot > 0, (v_tot, l_tot))
        results[run_id] = {
            "duty_W": q_expected,
            "store_export_sha256": digest,
            "certificate_id": cert["certificate_id"],
            "state_sha256": state_doc["state_sha256"],
            "coordinates_compared": len(rows),
            "registered_kind_coordinates": sum(1 for r in rows if r["registered_kind"]),
            "worst_registered": {
                "id": worst_reg[1],
                "deviation_over_allowance": s(worst_reg[0], 3),
            },
            "worst_all": {"id": worst_all[1], "deviation_over_allowance": s(worst_all[0], 3)},
            "beta_certified": s(beta_cert, 12),
            "beta_root": s(roots[run_id]["regime"]["beta"], 12),
            "result": "pass" if not misses else "FAIL",
            "misses": misses,
            "rows": rows,
        }

    # ---- 4. The comparison discriminates ---------------------------------------------------------
    # (a) Each certified state misses the other two duties' roots on the SOLVED coordinates, i.e.
    #     with the duty pin U-PHF.Q itself left out, so the miss is not just the changed pin.
    # (b) At its own duty, each certified state misses the two single-phase states that satisfy the
    #     same energy balance (all liquid, beta = 0; all vapour, beta = 1): a certificate on the
    #     wrong phase regime would have been caught.
    matrix = {}
    wrong_regime = {}
    states = {
        a: json.loads((runs_dir / CAMPAIGN / a / "store-export.json").read_bytes())[
            "artifact_documents"
        ][f"{BUNDLE}/solution-state.json"]["variables"]
        for a in RUNS
    }
    solved = [v for v in roots["V17-T03-1"]["registered"] if v != "U-PHF.Q"]
    for a in RUNS:
        state = states[a]
        for b in RUNS:
            ref = roots[b]["registered"]
            worst = max(abs(mpf(state[v]) - ref[v]) / t7.ALLOWANCE[t7.kind_of(v)] for v in solved)
            matrix[f"{a}|{b}"] = s(worst, 3)
            if a != b:
                c.check(
                    f"P4a.{a}_misses_root_of_{b}_by_ge_{SEPARATION}",
                    worst >= SEPARATION,
                    s(worst, 3),
                )
                # The same comparator that passed the diagonal rejects the off-diagonal.
                rejected = [
                    v
                    for v in solved
                    if not within(state[v], s(ref[v]), s(t7.ALLOWANCE[t7.kind_of(v)]))
                ]
                c.check(f"P4a.{a}_within_rejects_root_of_{b}", len(rejected) > 0, len(rejected))
        q = mpf(RUNS[a])
        target = bounds["H_in_W"] + q
        zero3 = (mpf(0),) * 3
        for phase, (vap, liq) in {"L": (zero3, s4["n"]), "V": (s4["n"], zero3)}.items():
            t_single = t5.invert_single_phase(s4["n"], t5.P_R, target, phase)
            alt = {"S5.T": t_single, "S6.T": t_single}
            for i, comp in enumerate(t7.COMPONENTS):
                alt[f"S5.n.{comp}"] = vap[i]
                alt[f"S6.n.{comp}"] = liq[i]
            worst = max(abs(mpf(state[v]) - alt[v]) / t7.ALLOWANCE[t7.kind_of(v)] for v in alt)
            wrong_regime[f"{a}|all_{'liquid' if phase == 'L' else 'vapour'}"] = s(worst, 3)
            c.check(
                f"P4b.{a}_misses_single_phase_{phase}_state_by_ge_{SEPARATION}",
                worst >= SEPARATION,
                s(worst, 3),
            )

    # ---- 5. Independence -------------------------------------------------------------------------
    leaked = sorted(m for m in sys.modules if m.split(".")[0] in ("openflowsheet", "benchmarks"))
    c.check("P5.imports_nothing_from_process_runtime_or_benchmarks", not leaked, leaked)

    document = {
        "schema": "t07-v17-c2-t03-variant-roots-v1",
        "campaign": CAMPAIGN,
        "method": (
            "t05_reference.coupled_c1's evaluator chain (eval_pump, eval_heater, eval_valve, "
            "eval_ph_flash) at U-PHF.duty.Q = the revision's pin; mpmath 40 digits; roots quoted "
            "at 20 significant digits; comparison |v - ref| <= allowance exactly, as the scorer's within()"
        ),
        "allowance": {k: s(v) for k, v in t7.ALLOWANCE.items()},
        "drum_inlet_S4": {
            "n": [s(v) for v in s4["n"]],
            "T_K": s(s4["T"]),
            "P_Pa": s(s4["P"]),
            "H_in_W": s(bounds["H_in_W"]),
            "Q_min_W": s(bounds["Q_min_W"]),
            "Q_max_W": s(bounds["Q_max_W"]),
            "T_bubble_K": s(t_bub),
            "T_dew_K": s(t_dew),
        },
        "regimes": {
            r: {k: s(v) if not isinstance(v, str) else v for k, v in roots[r]["regime"].items()}
            for r in RUNS
        },
        "certificates": results,
        "cross_matrix_worst_solved_over_allowance": matrix,
        "single_phase_alternatives_worst_over_allowance": wrong_regime,
        "claims": [{"name": n, "ok": ok} for n, ok, _ in c.rows],
    }
    return c, document


def dump(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, sort_keys=True, ensure_ascii=True) + "\n").encode()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--emit", type=Path)
    g.add_argument("--check", type=Path)
    args = ap.parse_args(argv)
    claims, document = run(args.repo.resolve())
    for name, ok, detail in claims.rows:
        print(
            f"{'PASS' if ok else 'FAIL'}  {name}  {detail if not ok or name.startswith('P1') else ''}"
        )
    for r, res in document["certificates"].items():
        print(
            f"{r}: Q={res['duty_W']} W  compared {res['coordinates_compared']} "
            f"({res['registered_kind_coordinates']} registered-kind)  worst registered "
            f"{res['worst_registered']['deviation_over_allowance']} ({res['worst_registered']['id']})  "
            f"worst all {res['worst_all']['deviation_over_allowance']} ({res['worst_all']['id']})  "
            f"beta cert {res['beta_certified']} root {res['beta_root']}  -> {res['result']}"
        )
    if claims.failed:
        print(f"REFUSED: {len(claims.failed)} of {len(claims.rows)} claims fail", file=sys.stderr)
        return 1
    data = dump(document)
    if args.emit:
        args.emit.write_bytes(data)
        print(f"wrote {args.emit} sha256 {sha256_bytes(data)}; {len(claims.rows)} claims pass")
        return 0
    old = args.check.read_bytes()
    if old != data:
        print(f"CHECK FAILED: {args.check} differs from a fresh derivation", file=sys.stderr)
        return 1
    print(
        f"check ok: {args.check} byte-identical, sha256 {sha256_bytes(data)}; "
        f"{len(claims.rows)} claims pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
