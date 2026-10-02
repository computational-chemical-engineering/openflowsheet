"""Comparing a recorded document against a freshly emitted one, across machines.

**Measured, 2026-09-21/22.** The same commit and the same lock file on x86-64 and aarch64
produce bit-identical structure and floats that differ in the last one to three ulps. Identical:
every `state_sha256` up the traversal, the unscaled residuals, `nnz(L) = 114`, `nnz(U) = 173`,
all three property counters, and the whole event sequence with its kinds, signatures, outcomes
and counts. Differing: `u_diag_min_abs` `0.06819573999172272` against `…125`, the recorded
linear residual, `step_inf_scaled`, and therefore the converged `merit` and its digest
(`13c05f70…` against `44c1c052…`). The non-portability enters at the SuperLU factorization, not
in the thermodynamics.

**Two pieces of existing authority decide how to compare, so this is not a new policy.**
Blueprint §8.3 promises R0 Structural — "identical structural artifacts on supported platforms"
— and says in the same section that "adaptive floating-point decisions are not included in a
cross-platform bitwise promise". ADR 0008 D2.1 is blunter still: `state_sha256`'s coverage is
fixed there and **"no test may pin a digest value"**. A byte-exact fixture comparison pins 39 of
them, so it was against an accepted ADR from the day it was written; nothing noticed, because
nothing tested that rule.

So: structure exactly, floats within a declared tolerance, digests not compared at all — only
required to be well formed. A digest that moved *without* any float moving would be a real
defect, and it is still caught, because it could only come from a float this comparison does
check or from the encoding, and `test_adr_0002_canonicalization.py` owns the encoding.

**This module was written in `tests/` and lifted here by K05**, which is what its own docstring
said would happen when the policy landed. ADR 0007 D2 is that policy: `K04-numerical-policy-v1`,
1e-9 relative with the floors below, and it is what a replay compares under (D4). The rules
here are therefore normative rather than a test convenience.

**Two policies, and a record names its own (ADR 0025; Frank's answer to its Q4).** Records made
from T08 on carry `T08-numerical-policy-v2` (`CURRENT_POLICY_ID`): v1 with ADR 0007's own rules
applied where v1 did not apply them — float-derived digests and ids compared for shape (D2), a
float floored at the threshold its quantity registers (D3, D5), a float inside text compared as a
float (D6) — and the LU pivot-path diagnostics recorded, not compared (D4). Its data are
`benchmarks/t08/numerical_policy_v2.yaml`. A record is compared under the policy it names, so
`differences` takes `policy_id` and has no default; v1's path below is frozen bit for bit with
every result registered under it, including where it is stricter than ADR 0007 as written.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any, Final

from openflowsheet.resources import packaged
from openflowsheet.run.solution_state import SCHEMA_VERSION as SOLUTION_STATE_SCHEMA


def _is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


#: ADR 0008 D2.1: covered fields that are digests of floating-point state. Never compared.
#: `checkpoint_id` is deliberately *not* here: it is a label like `attempt-0`, structural and
#: compared exactly.
#: `jacobian_identity` is deliberately *not* here. In K03's `Checkpoint` it is a digest-shaped
#: field; in K04's `RegularityEvidence` it is a structured identity record holding
#: `model_version`, `constants_sha256`, `state_sha256` and the phase signature. Descending into
#: it is the correct behaviour: the structural digests inside compare exactly, and the
#: float-derived `state_sha256` is caught by its own name.
DIGEST_FIELDS = frozenset({"state_sha256", "full_state_sha256", "target_state_sha256"})

#: And the rule behind that set, because naming them one at a time has now missed one twice.
#: **Any field whose name ends `state_sha256` is a digest of floating-point state** and is
#: never compared for value (ADR 0008 D2.1). Digests of *structure* — `constants_sha256`,
#: `model_version`, `check_policy_sha256` — do not end that way and are compared exactly,
#: which is right: R0 promises structural artifacts bit-identical across platforms.
FLOAT_DIGEST_SUFFIX = "state_sha256"


def is_float_digest(key: str) -> bool:
    return key in DIGEST_FIELDS or key.endswith(FLOAT_DIGEST_SUFFIX)


#: Digests of *structure*, which R0 does promise bit-for-bit and which are compared exactly.
STRUCTURAL_DIGEST_FIELDS = frozenset({"constants_sha256", "model_version", "content_hash"})

#: Integer quantities whose value carries no reproducible information, with the measurements
#: that say so. Each is checked for being a count and never for its value.
#:
#: Perturbing the OFF-B starting guess by **one ulp** and re-solving, thirteen times, moves
#: `property_calls` over 476..612, `requested_evaluations` over 1067..1385 and `cache_hits`
#: over 591..776 — a 13% spread — while the outcome, the two attempts, the four accepted
#: iterations, the LIQUID -> TWO_PHASE restart and all 27 events are *invariant*, and so are
#: `residual_calls` (11), `jacobian_calls` (4) and `factorizations` (8).
#:
#: The split is not arbitrary and it is not leniency. The three solver counters track the outer
#: control flow, which is bit-stable under perturbation and is compared exactly below. The three
#: property counters are sums over hundreds of *inner* iterative solves — the mixer's energy
#: closure, Rachford-Rice — each of which can take one more or one fewer step when its input
#: moves in the last bit. Asserting them across machines asserts noise; the ±3 difference
#: measured between x86-64 and aarch64 is a small sample of a quantity with that natural spread.
#:
#: **This is a classification taken on measurement and it belongs to ADR 0007 to confirm or
#: overturn.** It has a consequence beyond comparison, which the brief for that ADR carries:
#: K03 §11.2 budgets on `property_calls` and assertion A15 registers an exact count, while
#: blueprint §8.3 says "operation-count budgets support deterministic tests". A budget of 500
#: on a solve whose honest range is 476..612 decides close to arbitrarily.
UNREPRODUCIBLE_COUNTS = frozenset(
    {
        "property_calls",
        "requested_evaluations",
        "cache_hits",
        # **Fill counts, and they are not the structural quantity they look like.** `nnz(L)`
        # and `nnz(U)` count a sparsity pattern, so it is natural to file them under R0 — but
        # the pattern is the one SuperLU produced *after* partial pivoting, and pivot selection
        # compares magnitudes. Measured: nine one-ulp perturbations of the OFF-B start give six
        # distinct `nnz(L)` sequences on a single machine, including exactly the 103 against
        # 104 that aarch64 reported. Blueprint §8.3's exclusion names this case precisely —
        # "adaptive floating-point decisions are not included in a cross-platform bitwise
        # promise" — and a pivot choice is one.
        #
        # They remain *recorded* on every solve, which is what ADR 0004 D3.1 requires, and the
        # 44x44 block's fill is still asserted to be the large one in `test_k03_tear.py`.
        "nnz_L",
        "nnz_U",
    }
)

#: Kept for readers of the older name.
UNREPRODUCIBLE_COUNTERS = UNREPRODUCIBLE_COUNTS

_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")


#: **The declared numerical policy, loaded from where it is registered.** ADR 0007 D2 is
#: `K04-numerical-policy-v1` and `benchmarks/k04/reference_values.yaml` carries it; this module
#: used to carry its own copy of the table, labelled "interim", and the two drifted. The Fable
#: review of K05 measured the drift: `rcond_1` was floored at 1e-8 here against 1e-14 there,
#: six decades looser, so any two `ILL_CONDITIONED` certificates compared equal. Three entries
#: were in the registry and not here, one was here and not there, and K04's A32 classified
#: against *this* table — so the divergence was invisible to the test written to catch it.
#:
#: A policy with two copies is one copy and one rumour. This reads the registry.
def _registered_policy(
    relative: str = "benchmarks/k04/reference_values.yaml",
    policy_id: str = "K04-numerical-policy-v1",
) -> dict[str, Any]:
    import yaml  # noqa: PLC0415

    candidate = packaged(relative)
    if candidate.is_file():
        policy = yaml.safe_load(candidate.read_text(encoding="utf-8"))["numerical_policy"]
        assert policy["id"] == policy_id, policy["id"]
        return dict(policy)
    raise RuntimeError(
        f"the declared numerical policy {policy_id} is not on disk; it is registered in "
        f"{relative} and this module does not carry a copy"
    )


_POLICY = _registered_policy()

#: ADR 0007 D2's policy, frozen with every result registered under it (ADR 0025 D1.4).
V1_POLICY_ID: Final = str(_POLICY["id"])
#: ADR 0025 D1.2: what every record this build writes names, and the policy's single source.
CURRENT_POLICY_ID: Final = "T08-numerical-policy-v2"
#: The former name, kept as the alias of the current policy (ADR 0025 W2).
POLICY_ID: Final = CURRENT_POLICY_ID
RELATIVE_TOLERANCE: Final = float(_POLICY["relative"])
NEAR_THRESHOLD_MARGIN: Final = float(_POLICY["near_threshold_margin"])

#: Floors whose value is a number. An entry whose floor is prose — `check.value`'s "the
#: check's own tolerance", `u_diag_min_abs`'s ratio — is handled by `SELF_FLOORED` or compared
#: relatively, and is deliberately not parsed into a constant here.
REGISTERED_FLOOR: Final[dict[str, float]] = {
    name: float(entry["floor"])
    for name, entry in _POLICY["floors"].items()
    if "." not in name and _is_number(entry["floor"])
}

#: **There is no fallback floor, and that is ADR 0007 D2.3.** An unregistered float compares
#: relatively and nothing else: a quantity nobody has declared a threshold for has no basis on
#: which two near-zero values of it can be called the same. The invented `1e-24` that used to
#: sit here was withdrawn by D2.3 and lived on in the code until the Fable review of K05 found
#: it.
#:
#: A float that trips this is not a defect in the comparison. It is a float that needs a floor
#: in the registry, and K04's A32 is the test that says which.
NO_FLOOR: Final = 0.0

#: A `CheckResult`'s `value` is a residual of *some* kind — the field name says nothing about
#: which — but the object carries **its own registered tolerance** in the next field along. So
#: the floor for a check's value is that tolerance, which is not an invented number but the one
#: the check was judged by. Below it the quantity is not a measurement.
#:
#: Measured, and this is why the rule is needed: across x86-64 and aarch64 the same check
#: values come back as `0.0` against `4.4e-16`, `5.6e-17` against `0.0`, `2.2e-16` against
#: `-2.2e-16` — residuals at machine epsilon, where no relative tolerance means anything and
#: the sign is noise. The derivative witness moves further, 2.80e-11 against 2.93e-11, and its
#: registered tolerance of 1e-7 covers that too.
#: `sigma_min` joins it for the same reason with a different tolerance: the SVD rank tolerance
#: `n eps sigma_max` sits in the same `escalation` object, and below it a singular value is by
#: definition indistinguishable from the factorization's own backward error. Registering a
#: constant would have been wrong — the threshold is state-dependent.
SELF_FLOORED = {"value": "tolerance", "sigma_min": "tolerance"}

#: ADR 0007 D2.2, "a comparability window is a scope, not a floor" (T02 review M4). A float in
#: this map is value-compared only where the **committed** document's sibling is at least the
#: minimum — the side of the window is decided once, on the reference — and shape-checked below
#: it. The sibling is the window's selector: a scope, shape-checked and never value-compared.
COMPARABILITY_WINDOW: Final[dict[str, tuple[str, float]]] = {
    name: (str(entry["sibling"]), float(entry["minimum"]))
    for name, entry in (_POLICY.get("comparability_windows") or {}).items()
}
WINDOW_SELECTORS: Final = frozenset(sibling for sibling, _ in COMPARABILITY_WINDOW.values())


#: **Provenance**: recorded precisely *because* it varies, and therefore never compared for
#: value. Two kinds, and both are honest rather than convenient.
#:
#: Per-run: `run_id`, `started_at`, `elapsed_seconds`, `hostname`, `parent_run_id`. A run that
#: took 0.31 s and one that took 0.29 s are the same run twice.
#:
#: Per-machine: everything under an `environment` key — architecture, OS release, BLAS version,
#: thread pins, lock hash. ADR 0007 D6 requires these recorded so that a within-policy
#: difference is *attributable*; comparing them across machines asks whether two machines are
#: the same machine, to which the answer is known in advance.
#:
#: `artifacts` joins them because its values are hashes of documents containing floats, which
#: blueprint §8.3 excludes from any cross-platform bitwise promise.
#: `manifest_sha256` is here because it is *derived from* the volatile fields: it covers the
#: whole document, `elapsed_seconds` included, so two runs of the same model a second apart
#: legitimately have different ones. It is an integrity hash within one archive, never an
#: identity across two. `structural_sha256` is the one that is compared, and it is not here.
VOLATILE_FIELDS = frozenset(
    {
        "run_id",
        "started_at",
        "elapsed_seconds",
        "hostname",
        "parent_run_id",
        "artifacts",
        "manifest_sha256",
    }
)

#: **Anchored to the document root**, not matched at any depth (S5 of the Fable review of
#: K05). A bare-key rule would silently shape-compare any future artifact with a key called
#: `artifacts`, `environment`, `run_id` or `hostname` nested anywhere — the same silent-escape
#: shape the `state_sha256` suffix rule exists to avoid, running in the other direction. The
#: failure bundle, which carries `replay_identity` and `observations`, is the likely first
#: collision.
#:
#: The suffix rule for float digests stays a suffix rule: that was a deliberate choice with a
#: stated reason, and it errs toward *not* comparing a digest, which is the safe direction.

#: Keys whose entire subtree is provenance.
PROVENANCE_SUBTREES = frozenset({"environment", "recorded_environment", "current_environment"})


def _number_or_none(value: Any) -> bool:
    return value is None or (isinstance(value, int | float) and not isinstance(value, bool))


def _inside_window(key: str, committed: dict[str, Any]) -> bool:
    sibling, minimum = COMPARABILITY_WINDOW[key]
    selector = committed.get(sibling)
    return isinstance(selector, int | float) and float(selector) >= minimum


def _well_formed_provenance(expected: Any, actual: Any) -> bool:
    """Not compared is not unchecked: the *shape* is still a claim the document makes."""
    if expected is None or actual is None:
        return True
    return type(expected) is type(actual)


def _well_formed_digest(value: Any) -> bool:
    """Empty and absent are both legitimate.

    `""` is what an event carries before any state has been formed. `None` is what
    `full_state_sha256` and `jacobian_identity` carry because nothing writes them yet — that is
    the Fable review's finding S2 and A35's gap, recorded as a manifest limitation. When a
    writer appears this still checks its shape; asserting a value here would forbid the field
    ever being null, which is not this module's call to make.
    """
    if value is None or value == "":
        return True
    return isinstance(value, str) and bool(_HEX64.match(value))


def _digest_derived_id(committed: Mapping[str, Any], emitted: Mapping[str, Any]) -> bool:
    """A certificate whose id is its target hash: no plan in either document, a digest in both."""
    return all(
        document.get("plan_id") == ""
        and isinstance(document.get("target_state_sha256"), str)
        and len(document["target_state_sha256"]) == 64
        for document in (committed, emitted)
    )


def differences(
    emitted: Any,
    committed: Any,
    path: str = "",
    floor: float | None = None,
    *,
    policy_id: str,
    variable_kinds: Mapping[str, str] | None = None,
) -> list[str]:
    """Every way `emitted` departs from `committed` that the named policy does not allow.

    `policy_id` is required and has no default (ADR 0025 D1.4): a comparison registered under
    `K04-numerical-policy-v1` says so, and a record is compared under the policy it names.
    `variable_kinds` — each solution-state variable's declared quantity kind, from the compiled
    problem that was solved — is v2's alone (D5); v2 refuses to compare a solution state without
    it, and v1 refuses to be handed it, because it would ignore it.
    """
    if policy_id == V1_POLICY_ID:
        if variable_kinds is not None:
            raise TypeError(f"{V1_POLICY_ID} compares no declared kinds (ADR 0025 D5)")
        return _differences_v1(emitted, committed, path, floor)
    if policy_id == CURRENT_POLICY_ID:
        return _differences_v2(emitted, committed, path, floor, None, variable_kinds)
    raise ValueError(
        f"unknown numerical policy {policy_id!r}; this build knows {sorted(KNOWN_POLICY_IDS)}"
    )


def _differences_v1(
    emitted: Any, committed: Any, path: str = "", floor: float | None = None
) -> list[str]:
    """`K04-numerical-policy-v1`'s comparison, as at `814e151` (ADR 0025 D1.4, A12)."""
    found: list[str] = []
    where = path or "<root>"

    if isinstance(committed, dict):
        if not isinstance(emitted, dict):
            return [f"{where}: expected an object, got {type(emitted).__name__}"]
        for key in sorted(set(committed) | set(emitted)):
            if key not in committed:
                found.append(f"{where}.{key}: present in the emitted document only")
            elif key not in emitted:
                found.append(f"{where}.{key}: present in the committed document only")
            elif path == "" and (key in PROVENANCE_SUBTREES or key in VOLATILE_FIELDS):
                if not _well_formed_provenance(committed[key], emitted[key]):
                    found.append(
                        f"{where}.{key}: {type(emitted[key]).__name__} where the recorded "
                        f"document has {type(committed[key]).__name__}. Provenance is not "
                        "compared for value, but its shape is."
                    )
            elif key in UNREPRODUCIBLE_COUNTS:
                if not isinstance(emitted[key], int) or emitted[key] < 0:
                    found.append(
                        f"{where}.{key}: {emitted[key]!r} is not a count. Its value is not "
                        "compared, its kind is."
                    )
            elif is_float_digest(key):
                if not _well_formed_digest(emitted[key]):
                    found.append(
                        f"{where}.{key}: {emitted[key]!r} is not 64 lowercase hex digits or "
                        "empty. Its value is not compared (ADR 0008 D2.1), its shape is."
                    )
            elif key == "certificate_id" and _digest_derived_id(committed, emitted):
                # K04 §9's `certificate_id` is the target hash when no plan names the solve
                # (`cert-` + the first 12 hex digits of `target_state_sha256`): a digest of
                # floating-point state, so its value is not compared (ADR 0008 D2.1). What is
                # compared is that it is exactly the emitted document's own digest prefix.
                expected = f"cert-{emitted['target_state_sha256'][:12]}"
                if emitted[key] != expected:
                    found.append(
                        f"{where}.{key}: {emitted[key]!r} is not {expected!r}, the prefix of the "
                        "document's own target_state_sha256"
                    )
            elif key in WINDOW_SELECTORS:
                if not _number_or_none(emitted[key]):
                    found.append(f"{where}.{key}: {emitted[key]!r} is not a number or null")
            elif key in COMPARABILITY_WINDOW and not _inside_window(key, committed):
                if not _number_or_none(emitted[key]) or (emitted[key] is None) != (
                    committed[key] is None
                ):
                    found.append(
                        f"{where}.{key}: {emitted[key]!r} against {committed[key]!r} — outside "
                        "the comparability window the value is not compared, its shape is"
                    )
            else:
                floor = None
                source = SELF_FLOORED.get(key)
                if source is not None and isinstance(committed.get(source), int | float):
                    floor = abs(float(committed[source]))
                found += _differences_v1(
                    emitted[key], committed[key], f"{where}.{key}", floor=floor
                )
        return found

    if isinstance(committed, list):
        if not isinstance(emitted, list):
            return [f"{where}: expected a list, got {type(emitted).__name__}"]
        if len(emitted) != len(committed):
            return [f"{where}: {len(emitted)} entries against {len(committed)}"]
        for index, (left, right) in enumerate(zip(emitted, committed, strict=True)):
            found += _differences_v1(left, right, f"{where}[{index}]")
        return found

    if isinstance(committed, float) or isinstance(emitted, float):
        if emitted is None or committed is None:
            if emitted is not committed:
                found.append(f"{where}: {emitted!r} against {committed!r}")
            return found
        if floor is None:
            floor = REGISTERED_FLOOR.get(where.rsplit(".", 1)[-1], NO_FLOOR)
        if not math.isclose(
            float(emitted), float(committed), rel_tol=RELATIVE_TOLERANCE, abs_tol=floor
        ):
            found.append(
                f"{where}: {emitted!r} against {committed!r}, outside the interim "
                f"{RELATIVE_TOLERANCE:g} relative / {floor:g} absolute"
            )
        return found

    if emitted != committed:
        found.append(f"{where}: {emitted!r} against {committed!r}")
    return found


# == T08-numerical-policy-v2 (ADR 0025) =========================================================
#
# ADR 0025 §5's table, rows tried in order and the first match wins. Every value below is read
# from `benchmarks/t08/numerical_policy_v2.yaml`, which `scripts/t08_numerical_policy.py` emits
# and checks (A1); nothing is restated here.

_V2: Final = _registered_policy("benchmarks/t08/numerical_policy_v2.yaml", CURRENT_POLICY_ID)

KNOWN_POLICY_IDS: Final = frozenset({V1_POLICY_ID, CURRENT_POLICY_ID})

V2_RELATIVE_TOLERANCE: Final = float(_V2["relative"])
#: Row 13: v1's numeric floors, without the two `u_diag` rows (D4).
V2_REGISTERED_FLOOR: Final[dict[str, float]] = {
    name: float(entry["floor"])
    for name, entry in _V2["floors"].items()
    if "." not in name and _is_number(entry["floor"])
}
#: Row 10: a `value` or `sigma_min` is floored at its sibling `tolerance`, as in v1.
V2_SELF_FLOORED: Final[dict[str, str]] = dict(_V2["self_floored"])
#: Row 9 (D3): a `near_threshold` limitation's `value` is floored at its sibling `threshold`.
LIMITATION_FLOORS: Final[dict[str, dict[str, str]]] = {
    kind: dict(rule) for kind, rule in _V2["limitation_floors"].items()
}
#: Rows 6 and 7: unchanged from v1.
V2_COMPARABILITY_WINDOW: Final[dict[str, tuple[str, float]]] = {
    name: (str(entry["sibling"]), float(entry["minimum"]))
    for name, entry in _V2["comparability_windows"].items()
}
V2_WINDOW_SELECTORS: Final = frozenset(sibling for sibling, _ in V2_COMPARABILITY_WINDOW.values())
#: Row 2: unchanged from v1.
V2_UNREPRODUCIBLE_COUNTS: Final = frozenset(_V2["unreproducible_counts"])
#: Row 3 (D4): "recorded, not reproducible" — a function of the pivot sequence, which is a
#: floating-point comparison. Checked for kind only.
POST_PIVOTING_FLOATS: Final = frozenset(_V2["post_pivoting_floats"])
#: Row 4 (D2): float digests, by name and by the suffix rule.
V2_FLOAT_DIGESTS: Final = frozenset(_V2["float_digests"]["names"])
V2_FLOAT_DIGEST_SUFFIX: Final = str(_V2["float_digests"]["suffix"])
#: D2.1: the one float digest whose nullness is compared (null on one side, null on the other).
NULL_MATCHED_DIGESTS: Final = frozenset({"level_constants_sha256"})
#: Row 11 (D5): `τ_kind` of each declared quantity kind, ADR 0001 D6's `a + r·s`.
KIND_FLOOR: Final[dict[str, float]] = {
    kind: float(entry["floor"]) for kind, entry in _V2["kind_floors"].items()
}
#: Row 12 (D5.2): the phase-branch flows are molar flows.
PHASE_BRANCH_KIND: Final = str(_V2["kind_floor_paths"]["phase_branch_flows"])
PHASE_BRANCH_FLOWS: Final = frozenset({"liquid", "vapor", "liquid_total", "vapor_total"})
#: Row 8 (D6): the keys whose string values are text with floats in it, and the token.
TEXT_KEYS: Final = frozenset(_V2["text_with_floats"]["keys"])
FLOAT_TOKEN: Final = re.compile(str(_V2["text_with_floats"]["token"]))
TOKEN_FLOOR: Final = float(_V2["text_with_floats"]["token_floor"])

_LIMITATION_ENTRY = re.compile(r"\.limitations\[\d+\]\Z")
_PHASE_BRANCH_ENTRY = re.compile(r"\A<root>\.phase_branch\.[^.\[]+\Z")


def _is_float_digest_v2(key: str) -> bool:
    return key in V2_FLOAT_DIGESTS or key.endswith(V2_FLOAT_DIGEST_SUFFIX)


def _real(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _outside(emitted: Any, committed: Any, where: str, floor: float, source: str) -> list[str]:
    """D2.1 on one pair of numbers, with D1.5's label."""
    if math.isclose(float(emitted), float(committed), rel_tol=V2_RELATIVE_TOLERANCE, abs_tol=floor):
        return []
    return [
        f"{where}: {emitted!r} against {committed!r}, outside {CURRENT_POLICY_ID} "
        f"({V2_RELATIVE_TOLERANCE:g} relative / {floor!r} absolute, {source})"
    ]


def _post_pivoting(where: str, key: str, emitted: Mapping[str, Any], committed: Any) -> list[str]:
    """Row 3, D4.1: the kind of a pivot-path diagnostic, never its value."""
    value = emitted[key]
    label = f"{where}.{key}"
    if (value is None) != (committed is None):
        return [
            f"{label}: {value!r} against {committed!r}; null on one side requires null on the "
            "other (ADR 0025 D4)"
        ]
    if value is None:
        return []
    if not _real(value) or not math.isfinite(value) or value < 0:
        return [
            f"{label}: {value!r} is not a finite number >= 0. A pivot-path diagnostic is "
            "recorded, not reproducible: its value is not compared, its kind is (ADR 0025 D4)"
        ]
    if key == "u_diagonal_ratio" and value > 1:
        return [f"{label}: {value!r} is a ratio of |U| diagonals greater than 1 (ADR 0025 D4)"]
    largest = emitted.get("u_diag_max_abs")
    if key == "u_diag_min_abs" and _real(largest) and value > largest:
        return [f"{label}: {value!r} exceeds u_diag_max_abs {largest!r} (ADR 0025 D4)"]
    return []


def _certificate_id(where: str, emitted: Mapping[str, Any], committed: Mapping[str, Any]) -> str:
    """Row 5, D2.2: classed by how the committed id was built. Empty when consistent."""
    target = committed.get("target_state_sha256")
    built_from_digest = (
        isinstance(target, str)
        and bool(_HEX64.match(target))
        and committed["certificate_id"] == f"cert-{target[:12]}"
    )
    if not built_from_digest:
        mine, theirs = emitted["certificate_id"], committed["certificate_id"]
        return f"{where}.certificate_id: {mine!r} against {theirs!r}" if mine != theirs else ""
    own = emitted.get("target_state_sha256")
    expected = f"cert-{own[:12]}" if isinstance(own, str) else None
    if emitted["certificate_id"] != expected:
        return (
            f"{where}.certificate_id: {emitted['certificate_id']!r} is not {expected!r}, the "
            "digest form of the emitted document's own target_state_sha256 (ADR 0025 D2.2)"
        )
    return ""


def _text(where: str, emitted: str, committed: str) -> list[str]:
    """Row 8, D6.3: the template exactly, then each float token relatively, in order."""
    if FLOAT_TOKEN.sub("<f>", emitted) != FLOAT_TOKEN.sub("<f>", committed):
        return [
            f"{where}: {emitted!r} against {committed!r}; the text around its floats differs "
            "(ADR 0025 D6)"
        ]
    found: list[str] = []
    pairs = zip(FLOAT_TOKEN.findall(emitted), FLOAT_TOKEN.findall(committed), strict=True)
    for index, (left, right) in enumerate(pairs):
        found += _outside(
            float(left),
            float(right),
            f"{where} (float {index} of its text)",
            TOKEN_FLOOR,
            "a float in text has no kind, ADR 0025 D6",
        )
    return found


def _variables(
    where: str, emitted: Any, committed: Mapping[str, Any], kinds: Mapping[str, str]
) -> list[str]:
    """Row 11, D5.1: each variable floored at `τ_kind` of its declared kind, else relative."""
    if not isinstance(emitted, dict):
        return [f"{where}: expected an object, got {type(emitted).__name__}"]
    found: list[str] = []
    for name in sorted(set(committed) | set(emitted)):
        if name not in committed:
            found.append(f"{where}.{name}: present in the emitted document only")
        elif name not in emitted:
            found.append(f"{where}.{name}: present in the committed document only")
        else:
            kind = kinds.get(name)
            floor = KIND_FLOOR.get(kind) if kind is not None else None
            source = (
                f"tau_kind of {kind}, ADR 0025 D5"
                if floor is not None
                else (
                    f"{kind} registers no tau_kind, relative only, ADR 0025 D5"
                    if kind is not None
                    else "no declared kind, relative only, ADR 0025 D5"
                )
            )
            found += _differences_v2(
                emitted[name],
                committed[name],
                f"{where}.{name}",
                floor if floor is not None else NO_FLOOR,
                source,
                None,
            )
    return found


def _differences_v2(
    emitted: Any,
    committed: Any,
    path: str,
    floor: float | None,
    source: str | None,
    kinds: Mapping[str, str] | None,
) -> list[str]:
    """`T08-numerical-policy-v2`: ADR 0025 §5's rows, in order."""
    found: list[str] = []
    where = path or "<root>"

    if isinstance(committed, dict):
        if not isinstance(emitted, dict):
            return [f"{where}: expected an object, got {type(emitted).__name__}"]
        solution_state = path == "" and committed.get("schema_version") == SOLUTION_STATE_SCHEMA
        for key in sorted(set(committed) | set(emitted)):
            if key not in committed:
                found.append(f"{where}.{key}: present in the emitted document only")
                continue
            if key not in emitted:
                found.append(f"{where}.{key}: present in the committed document only")
                continue
            mine, theirs = emitted[key], committed[key]
            # Row 1: root-anchored provenance.
            if path == "" and (key in PROVENANCE_SUBTREES or key in VOLATILE_FIELDS):
                if not _well_formed_provenance(theirs, mine):
                    found.append(
                        f"{where}.{key}: {type(mine).__name__} where the recorded document has "
                        f"{type(theirs).__name__}. Provenance is not compared for value, but "
                        "its shape is."
                    )
            # Row 2: counts.
            elif key in V2_UNREPRODUCIBLE_COUNTS:
                if not isinstance(mine, int) or mine < 0:
                    found.append(
                        f"{where}.{key}: {mine!r} is not a count. Its value is not compared, "
                        "its kind is."
                    )
            # Row 3: post-pivoting diagnostics.
            elif key in POST_PIVOTING_FLOATS:
                found += _post_pivoting(where, key, emitted, theirs)
            # Row 4: float digests.
            elif _is_float_digest_v2(key):
                if not _well_formed_digest(mine):
                    found.append(
                        f"{where}.{key}: {mine!r} is not 64 lowercase hex digits or empty. Its "
                        "value is not compared (ADR 0008 D2.1, ADR 0025 D2), its shape is."
                    )
                elif key in NULL_MATCHED_DIGESTS and (mine is None) != (theirs is None):
                    found.append(
                        f"{where}.{key}: {mine!r} against {theirs!r}; null on one side requires "
                        "null on the other (ADR 0025 D2.1)"
                    )
            # Row 5: the certificate id, by how it was built.
            elif key == "certificate_id":
                difference = _certificate_id(where, emitted, committed)
                if difference:
                    found.append(difference)
            # Row 6: a comparability window's selector.
            elif key in V2_WINDOW_SELECTORS:
                if not _number_or_none(mine):
                    found.append(f"{where}.{key}: {mine!r} is not a number or null")
            # Row 7: outside its window, a windowed float is compared for shape.
            elif key in V2_COMPARABILITY_WINDOW and not _inside_v2_window(key, committed):
                if not _number_or_none(mine) or (mine is None) != (theirs is None):
                    found.append(
                        f"{where}.{key}: {mine!r} against {theirs!r} — outside the "
                        "comparability window the value is not compared, its shape is"
                    )
            # Row 8: text with floats in it.
            elif key in TEXT_KEYS and isinstance(mine, str) and isinstance(theirs, str):
                found += _text(f"{where}.{key}", mine, theirs)
            # Row 11: a solution state's variables, by declared kind.
            elif solution_state and key == "variables" and isinstance(theirs, dict):
                if kinds is None:
                    found.append(
                        f"{where}.variables: declared kinds not supplied; {CURRENT_POLICY_ID} "
                        "does not compare a solution state without them (ADR 0025 D5)"
                    )
                else:
                    found += _variables(f"{where}.variables", mine, theirs, kinds)
            # Row 12: phase-branch flows.
            elif key in PHASE_BRANCH_FLOWS and _PHASE_BRANCH_ENTRY.match(where):
                found += _phase_branch_flow(f"{where}.{key}", mine, theirs)
            else:
                child_floor, child_source = _sibling_floor(where, key, committed)
                found += _differences_v2(
                    mine, theirs, f"{where}.{key}", child_floor, child_source, None
                )
        return found

    if isinstance(committed, list):
        if not isinstance(emitted, list):
            return [f"{where}: expected a list, got {type(emitted).__name__}"]
        if len(emitted) != len(committed):
            return [f"{where}: {len(emitted)} entries against {len(committed)}"]
        for index, (left, right) in enumerate(zip(emitted, committed, strict=True)):
            found += _differences_v2(left, right, f"{where}[{index}]", None, None, None)
        return found

    # Rows 9–14: a float, under the floor its row gives, else its registered one, else none.
    if isinstance(committed, float) or isinstance(emitted, float):
        if emitted is None or committed is None:
            if emitted is not committed:
                found.append(f"{where}: {emitted!r} against {committed!r}")
            return found
        if not (_real(emitted) and _real(committed)):
            return [f"{where}: {emitted!r} against {committed!r}"]
        if floor is None:
            key = where.rsplit(".", 1)[-1]
            if key in V2_REGISTERED_FLOOR:
                floor, source = V2_REGISTERED_FLOOR[key], f"the floor of {key}, ADR 0007 D2.2"
            else:
                floor, source = NO_FLOOR, "no registered floor, ADR 0007 D2.3"
        return _outside(emitted, committed, where, floor, source or "")

    # Row 15: every other leaf, exactly.
    if emitted != committed:
        found.append(f"{where}: {emitted!r} against {committed!r}")
    return found


def _inside_v2_window(key: str, committed: dict[str, Any]) -> bool:
    sibling, minimum = V2_COMPARABILITY_WINDOW[key]
    selector = committed.get(sibling)
    return isinstance(selector, int | float) and float(selector) >= minimum


def _sibling_floor(
    where: str, key: str, committed: Mapping[str, Any]
) -> tuple[float | None, str | None]:
    """Rows 9 and 10: a floor read from the committed object's own sibling, or none."""
    kind = committed.get("kind")
    in_limitation = isinstance(kind, str) and _LIMITATION_ENTRY.search(where) is not None
    sibling = LIMITATION_FLOORS.get(str(kind), {}).get(key) if in_limitation else None
    if sibling is not None and _real(committed.get(sibling)):
        return abs(float(committed[sibling])), f"its sibling {sibling}, ADR 0025 D3"
    sibling = V2_SELF_FLOORED.get(key)
    if sibling is not None and isinstance(committed.get(sibling), int | float):
        return abs(float(committed[sibling])), f"its sibling {sibling}, ADR 0007 D2.2"
    return None, None


def _phase_branch_flow(where: str, emitted: Any, committed: Any) -> list[str]:
    """Row 12, D5.2: a phase split's flows, floored at the molar-flow `τ_kind`."""
    floor = KIND_FLOOR[PHASE_BRANCH_KIND]
    source = f"tau_kind of {PHASE_BRANCH_KIND}, ADR 0025 D5.2"
    if isinstance(committed, list):
        if not isinstance(emitted, list):
            return [f"{where}: expected a list, got {type(emitted).__name__}"]
        if len(emitted) != len(committed):
            return [f"{where}: {len(emitted)} entries against {len(committed)}"]
        found: list[str] = []
        for index, (left, right) in enumerate(zip(emitted, committed, strict=True)):
            found += _differences_v2(left, right, f"{where}[{index}]", floor, source, None)
        return found
    return _differences_v2(emitted, committed, where, floor, source, None)


def pinned_digests(document: Any, path: str = "") -> list[str]:
    """Where a document carries a digest of floating-point state. ADR 0008 D2.1's scope."""
    found: list[str] = []
    if isinstance(document, dict):
        for key, value in document.items():
            if is_float_digest(key) and value:
                found.append(f"{path}.{key}")
            found += pinned_digests(value, f"{path}.{key}")
    elif isinstance(document, list):
        for index, entry in enumerate(document):
            found += pinned_digests(entry, f"{path}[{index}]")
    return found
