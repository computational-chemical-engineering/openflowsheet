"""The SurrogateManifest, the ModelEvidence and their checker (M04 spec §10.1, §10.2, M04.A24).

`build_records(variant, plan_id, surrogate_id, evaluation)` turns a run plan's evaluation into the
two documents. Both are functions of the experiment records alone (keys, results, the plan), never
of a job id or a clock, so a study whose records are all cached reproduces them bitwise (M04.A32).
No non-finite number is serialized: a failed draw's score and an absent q̂ are `null`, with the
reason in the split's `failed` list or in `promotion`.

**The evidence names the manifest, not the reverse** (spec §18 A1.4, ADR 0037 Amendment 1 D6). The
manifest's SHA-256 is the surrogate's identity (an instance's `model.artifact_ref`, spec §8.2) and
does not hash its evidence; the evidence's `subject.artifact_ref` is that SHA-256, required.
Evidence about a model accumulates without changing the model's identity, and promotion rests on
the manifest alone: its checker reads no evidence.

`check_manifest(manifest)` is the checker the replacement check also runs (ADR 0037 D3): every rule
a JSON Schema cannot express. It re-derives the band, the coverage count and the verdict from the
stored scores and metrics — a hand-edited manifest cannot be promoted by editing a field — and
returns every finding, empty when the manifest is consistent.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from fractions import Fraction
from functools import cache
from typing import Any, Final

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from openflowsheet.adapters.variants import Variant
from openflowsheet.canonical import document_sha256, first_noncanonical
from openflowsheet.resources import packaged
from openflowsheet.studies.surrogate.conformal import (
    ALPHA,
    C_MIN,
    DELTA,
    METHOD_ID,
    RHO_G,
    SCORE_ID,
    TERMS,
    WIDTH_DT_K,
    WIDTH_X,
    StudyEvidence,
    clopper_pearson_lower,
    conformal_band,
    coverage_hits,
    h_min,
    k_index,
    study_verdict,
)
from openflowsheet.studies.surrogate.plan import (
    BOX,
    GRADIENT_STEP_Z,
    INPUT_MAP_ID,
    REFERENCE_DISTRIBUTION_ID,
    REGISTERED_PLANS,
    SAMPLER_ID,
    SPLITS,
)
from openflowsheet.studies.surrogate.quadratic import (
    ADMISSIBLE_DT_K,
    ADMISSIBLE_X,
    BASIS_ID,
    FIT_METHOD_ID,
    OUTPUT_MAP_ID,
)
from openflowsheet.studies.surrogate.study import MODEL_ID, Observation, SurrogateEvaluation

__all__ = [
    "ASSUMPTIONS",
    "EVIDENCE_VERSION",
    "MANIFEST_VERSION",
    "QUALIFICATIONS",
    "build_records",
    "check_manifest",
    "familywise_bound",
    "qualifications",
    "schema_errors",
]

MANIFEST_VERSION: Final = "surrogate-manifest-v1"
EVIDENCE_VERSION: Final = "model-evidence-v1"
MANIFEST_SCHEMA: Final = "surrogate-manifest.schema.json"
EVIDENCE_SCHEMA: Final = "model-evidence.schema.json"

#: Spec §6.3, ADR 0036 D6: Q0 (first, when the parent is synthetic) and Q1–Q7; Q6 is a template
#: whose three fields the manifest fills.
Q0: Final = "SYNTHETIC: certifies nothing about the reactor"
QUALIFICATIONS: Final[tuple[str, ...]] = (
    f"marginal over P_ref {REFERENCE_DISTRIBUTION_ID}; not pointwise",
    "not at optimizer-selected or adaptively chosen points",
    "no claim outside the reference box or under distribution shift",
    "relative to the parent at its design grid; excludes the parent's discretization bias DX-01 "
    "and says nothing about the physical reactor",
    "joint over (X, dT) at one query; no simultaneous claim over several queries or several "
    "surrogate units",
    "nominal 0.95 (finite-sample k/(n+1) = <value>); one-sided 95 % lower bound <L> from <m> "
    "independent test draws; declared minimum 0.90",
    "no empirical validation (no plant or literature data)",
)
_Q6: Final = 5
#: A field left unfilled: `<…>` anywhere in a qualification (M04.A24).
_UNFILLED: Final = re.compile(r"<[^<>]*>")

#: Spec §10.1's fixed list.
ASSUMPTIONS: Final[tuple[str, ...]] = (
    f"exchangeability from i.i.d. draws of P_ref {REFERENCE_DISTRIBUTION_ID}",
    "predictor, transform and score frozen before calibration",
    "failed draws scored +inf (kept in n and m)",
    "deterministic parent within one environment fingerprint",
)

#: Spec §7.4: what a promoted surrogate may claim, and what it may not.
ESTABLISHES: Final[tuple[str, ...]] = (
    "the band and its coverage statement with qualifications Q1-Q7",
    "the error metrics on the independent test set",
    "gradient agreement with the parent at the registered gradient centres",
    "exact element conservation",
    "the hard-domain and admissibility guards",
)
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "coverage at a flowsheet's solved operating point or an optimizer's candidate",
    "coverage outside the reference box",
    "anything about the physical reactor or plant data",
    "simultaneous coverage over several units or queries",
    "flowsheet sensitivities as the reactor's sensitivities",
)
_COMPARISONS: Final = (
    {
        "reference": "parent_model",
        "quantity": "surrogate approximation error",
        "split": "test",
        "pointer": "/evaluation",
    },
)
_NO_EXPERIMENTS: Final = "none: no plant or literature data (M04 scope)"
_DECIMAL: Final = 6


def _fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def qualifications(synthetic: bool, n: int, k: int, lower_bound: float | None, m: int) -> list[str]:
    """Q0 (if synthetic) and Q1–Q7, Q6 filled: k/(n+1), L (or that there is none) and m."""
    level = Fraction(k, n + 1)
    bound = "none (no finite band)" if lower_bound is None else f"{lower_bound:.{_DECIMAL}f}"
    q6 = (
        f"nominal 0.95 (finite-sample k/(n+1) = {k}/{n + 1} = {float(level):.{_DECIMAL}f}); "
        f"one-sided 95 % lower bound {bound} from {m} independent test draws; "
        "declared minimum 0.90"
    )
    filled = [q6 if i == _Q6 else text for i, text in enumerate(QUALIFICATIONS)]
    return ([Q0] if synthetic else []) + filled


# -- the records ----------------------------------------------------------------------------------


def _split_block(observations: Sequence[Observation], count: int) -> dict[str, Any]:
    keys = [o.key for o in observations]
    return {
        "count": count,
        "keys": keys,
        "keys_sha256": document_sha256(keys),
        "failed": [
            {"index": i, "status": o.envelope_status, "code": o.code}
            for i, o in enumerate(observations)
            if o.status == "failed"
        ],
        "incomplete": [
            {
                "index": i,
                "key": o.key,
                "label": o.label,
                "status": o.envelope_status,
                "code": o.code,
            }
            for i, o in enumerate(observations)
            if o.status == "incomplete"
        ],
    }


def _errors(values: Sequence[float]) -> dict[str, float] | None:
    """max, RMS and the empirical 95th percentile (nearest rank, ⌈0.95 N⌉-th smallest) of |e|."""
    if not values:
        return None
    ordered = sorted(values)
    rank = -(-len(ordered) * 95 // 100)
    return {
        "max": ordered[-1],
        "rms": math.sqrt(math.fsum(v * v for v in ordered) / len(ordered)),
        "p95": ordered[rank - 1],
    }


def _hard_domain(variant: Variant) -> dict[str, Any]:
    return dict(variant.boundary["hard_domain"])


def familywise_bound(predecessors: int, coverage_evaluated: bool) -> float:
    """Spec §5.5: δ = 0.05 per iteration whose coverage test was evaluated — every predecessor
    (the guard admits `it<i>` only after coverage failures) and this iteration if its test ran;
    exact (a multiple of 1/20 rounded once)."""
    return float(DELTA * (predecessors + (1 if coverage_evaluated else 0)))


def build_records(
    variant: Variant,
    plan_id: str,
    surrogate_id: str,
    evaluation: SurrogateEvaluation,
    *,
    predecessors: Sequence[str] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The SurrogateManifest and its ModelEvidence for a run plan (spec §10.1, §10.2);
    `predecessors` are the earlier iterations' manifest SHA-256s, in order (spec §18 A1.2)."""
    plan = evaluation.plan
    verdict = evaluation.verdict
    fit = evaluation.fit
    surrogate = fit.surrogate
    observations = evaluation.observations
    counts = plan.counts
    splits: dict[str, Any] = {
        split: _split_block(observations[split], counts[split]) for split in SPLITS
    }
    width = len(plan.gradient[0].stencil) if plan.gradient else 0
    splits["gradient"]["centres"] = [
        {
            "index": centre.index,
            "status": centre.status,
            "stencil_keys": [o.key for o in centre.stencil],
        }
        for centre in evaluation.centres
    ]
    assert all(len(c.stencil) == width for c in evaluation.centres)
    fingerprints = sorted(
        {
            o.fingerprint_sha256
            for rows in observations.values()
            for o in rows
            if o.fingerprint_sha256 is not None
        }
    )
    n = len(evaluation.calibration_scores)
    m = len(evaluation.test_scores)
    k = k_index(n)
    test_x = [e[0] for e in evaluation.test_errors]
    test_dt = [e[1] for e in evaluation.test_errors]
    within = sum(1 for s in evaluation.test_scores if s is not None and s <= 1.0)
    coverage_evaluated = verdict.hits is not None and verdict.h_min is not None
    synthetic = variant.synthetic
    lower = verdict.lower_bound
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_VERSION,
        "surrogate_id": surrogate_id,
        "model_id": MODEL_ID,
        "synthetic": synthetic,
        "iteration": plan.iteration,
        "plan_id": plan_id,
        "predecessors": list(predecessors),
        "parent": {
            "model_id": variant.model_id,
            "variant_id": variant.variant_id,
            "variant_sha256": variant.sha256,
            "fingerprint_sha256s": fingerprints,
            "boundary": dict(variant.boundary),
        },
        "input_map": {
            "id": INPUT_MAP_ID,
            "coordinates": [
                {
                    "name": b.name,
                    "unit": b.unit,
                    "lo": b.lo,
                    "hi": b.hi,
                    "centre": b.centre,
                    "half_width": b.half_width,
                }
                for b in BOX
            ],
        },
        "output_map": {
            "id": OUTPUT_MAP_ID,
            "outputs": ["X", "dT_K"],
            "admissible": {
                "X": list(ADMISSIBLE_X),
                "X_le_r_over_3": True,
                "dT_K": list(ADMISSIBLE_DT_K),
            },
        },
        "predictor": {
            "basis": BASIS_ID,
            "terms": TERMS,
            "coefficients": None
            if surrogate is None
            else {"X": list(surrogate.coefficients_x), "dT_K": list(surrogate.coefficients_dt)},
            "fit": {
                "method": FIT_METHOD_ID,
                "training_ok": fit.training_ok,
                "singular_value_ratio": fit.singular_value_ratio,
                "training_rms": None
                if fit.training_rms is None
                else {"X": fit.training_rms[0], "dT_K": fit.training_rms[1]},
            },
        },
        "score": {"id": SCORE_ID, "scales": {"X": WIDTH_X, "dT_K": WIDTH_DT_K}},
        "reference_distribution": {
            "id": REFERENCE_DISTRIBUTION_ID,
            "kind": "uniform_box",
            "sampler": SAMPLER_ID,
            "seeds": dict(plan.seeds),
        },
        "splits": splits,
        "calibration": {
            "alpha": _fraction(ALPHA),
            "n": n,
            "k": k,
            "scores": list(evaluation.calibration_scores),
            "q_hat": verdict.q_hat,
        },
        "evaluation": {
            "m": m,
            "scores": list(evaluation.test_scores),
            "hits": verdict.hits,
            "lower_bound": lower,
            "h_min": verdict.h_min,
            "c_min": float(C_MIN),
            "delta": float(DELTA),
            "errors": {"X": _errors(test_x), "dT_K": _errors(test_dt)},
            "fraction_within_width": within / m if m else None,
        },
        "gradient": {
            "step_z": GRADIENT_STEP_Z,
            "rho_g": RHO_G,
            "centres": [
                {
                    "index": centre.index,
                    "status": centre.status,
                    "errors": None
                    if centre.errors is None
                    else {"X": centre.errors[0], "dT_K": centre.errors[1]},
                }
                for centre in evaluation.centres
            ],
        },
        "domain": {
            "empirical": "box",
            "hard": _hard_domain(variant),
            "inadmissible_predictions": evaluation.inadmissible,
            "admissibility_margin": evaluation.admissibility_margin,
            "parent_extrapolated": evaluation.extrapolated,
        },
        "assumptions": list(ASSUMPTIONS),
        "qualifications": qualifications(synthetic, n, k, lower, m),
        "promotion": {
            "verdict": verdict.verdict,
            "insufficient": list(verdict.insufficient),
            "not_promotable": list(verdict.not_promotable),
            "familywise_false_pass_bound": familywise_bound(len(predecessors), coverage_evaluated),
        },
    }
    evidence: dict[str, Any] = {
        "schema_version": EVIDENCE_VERSION,
        "subject": {
            "model_id": MODEL_ID,
            "version": surrogate_id,
            "artifact_ref": document_sha256(manifest),
        },
        "parent": {
            "model_id": variant.model_id,
            "variant_id": variant.variant_id,
            "variant_sha256": variant.sha256,
            "synthetic": synthetic,
        },
        "data": [
            {"split": split, "count": counts[split], "keys_sha256": splits[split]["keys_sha256"]}
            for split in SPLITS
        ],
        "numerical": {
            "parent_accuracy": dict(variant.accuracy),
            "fit": {
                "training_ok": fit.training_ok,
                "singular_value_ratio": fit.singular_value_ratio,
            },
        },
        "comparisons": [dict(c) for c in _COMPARISONS],
        "experimental_comparisons": [],
        "experimental_comparisons_reason": _NO_EXPERIMENTS,
        "uncertainty": {
            "method": METHOD_ID,
            "claim": "joint, marginal over P_ref",
            "nominal": float(1 - ALPHA),
            "lower_bound": lower,
            "minimum": float(C_MIN),
        },
        "scope": {
            "evidence_class": "synthetic_verification" if synthetic else "model_approximation",
            "establishes": list(ESTABLISHES),
            "does_not_establish": list(DOES_NOT_ESTABLISH),
        },
    }
    return manifest, evidence


# -- the checker (M04.A24) ------------------------------------------------------------------------


@cache
def _validator(name: str) -> Draft202012Validator:
    """A validator of the packaged schema `name`, its `$ref`s resolved among the packaged schemas
    by `$id` (the manifest refers to `model-variant.schema.json`'s boundary)."""
    documents = [
        json.loads(entry.read_text(encoding="utf-8"))
        for entry in packaged("schemas").iterdir()
        if entry.name.endswith(".schema.json")
    ]
    registry: Registry[Any] = Registry().with_resources(
        (document["$id"], DRAFT202012.create_resource(document)) for document in documents
    )
    schema = json.loads(packaged(f"schemas/{name}").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, registry=registry)


def schema_errors(name: str, document: Any) -> list[str]:
    """`document` against the packaged schema `name`, each error as `/<pointer>: <message>`,
    sorted by path; empty when valid."""
    found = sorted(_validator(name).iter_errors(document), key=lambda e: list(e.absolute_path))
    return ["/" + "/".join(str(p) for p in e.absolute_path) + f": {e.message}" for e in found]


def _non_finite(node: Any, pointer: str = "") -> str | None:
    if isinstance(node, float) and not math.isfinite(node):
        return pointer or "/"
    if isinstance(node, Mapping):
        for key, value in node.items():
            found = _non_finite(value, f"{pointer}/{key}")
            if found is not None:
                return found
    if isinstance(node, list | tuple):
        for i, value in enumerate(node):
            found = _non_finite(value, f"{pointer}/{i}")
            if found is not None:
                return found
    return None


def _scores(values: Any) -> tuple[float | None, ...]:
    return tuple(None if v is None else float(v) for v in values)


def check_manifest(manifest: Mapping[str, Any]) -> list[str]:
    """Every inconsistency of `manifest` that its schema cannot express (M04.A24); empty when
    none. The schema is checked first; a manifest that fails it is not read further."""
    invalid = schema_errors(MANIFEST_SCHEMA, manifest)
    if invalid:
        return [f"schema: {error}" for error in invalid]
    found: list[str] = []
    pointer = _non_finite(manifest)
    if pointer is not None:
        return [f"non-finite number at {pointer}"]
    pointer = first_noncanonical(manifest)
    if pointer is not None:
        return [f"not canonical at {pointer}"]

    plan_id = manifest["plan_id"]
    registered = REGISTERED_PLANS.get(plan_id)
    if registered is None:
        return [f"plan {plan_id!r} is not registered"]
    iteration, counts, synthetic_only = registered
    if manifest["iteration"] != iteration:
        found.append(f"iteration {manifest['iteration']} is not plan {plan_id!r}'s {iteration}")
    if len(manifest["predecessors"]) != iteration - 1:
        found.append(
            f"{len(manifest['predecessors'])} predecessors; iteration {iteration} has "
            f"{iteration - 1}"
        )
    if synthetic_only and not manifest["synthetic"]:
        found.append(f"plan {plan_id!r} is registered for synthetic parents only")

    # Splits: the plan's counts, keys hashed as recorded, pairwise disjoint and without repeats.
    splits = manifest["splits"]
    seen: dict[str, str] = {}
    for split in SPLITS:
        block = splits[split]
        keys = block["keys"]
        expected: int = counts[split]
        size = expected * 2 * len(BOX) if split == "gradient" else expected
        if block["count"] != expected or len(keys) != size:
            found.append(
                f"{split}: count {block['count']} with {len(keys)} keys; the plan has {expected}"
            )
        if block["keys_sha256"] != document_sha256(keys):
            found.append(f"{split}: keys_sha256 is not the keys' SHA-256")
        for key in keys:
            if key in seen:
                found.append(f"{split}: key {key} is also in {seen[key]} (overlapping splits)")
            seen[key] = split
        for entry in (*block["failed"], *block["incomplete"]):
            if not 0 <= entry["index"] < len(keys):
                found.append(f"{split}: index {entry['index']} is outside the split")
            elif "key" in entry and entry["key"] != keys[entry["index"]]:
                found.append(
                    f"{split}: incomplete key {entry['key']} is not keys[{entry['index']}]"
                )
    centres = splits["gradient"]["centres"]
    stencil_keys = [key for centre in centres for key in centre["stencil_keys"]]
    if stencil_keys != splits["gradient"]["keys"]:
        found.append("gradient: the centres' stencil keys are not the split's keys in order")

    # The band, the coverage count and the bound, re-derived from the stored scores.
    calibration = manifest["calibration"]
    evaluation = manifest["evaluation"]
    cal_scores = _scores(calibration["scores"])
    test_scores = _scores(evaluation["scores"])
    n, m = len(cal_scores), len(test_scores)
    if calibration["n"] != n or n != counts["calibration"]:
        found.append(f"n = {calibration['n']} ({n} scores); the plan's is {counts['calibration']}")
    if evaluation["m"] != m or m != counts["test"]:
        found.append(f"m = {evaluation['m']} ({m} scores); the plan's is {counts['test']}")
    if calibration["k"] != k_index(n):
        found.append(f"k = {calibration['k']}, not k({n}) = {k_index(n)}")
    if evaluation["h_min"] != h_min(m):
        found.append(f"h_min = {evaluation['h_min']}, not h_min({m}) = {h_min(m)}")
    band = conformal_band(cal_scores)
    q_hat = calibration["q_hat"]
    if (q_hat is None) != (band.q_hat is None) or (
        q_hat is not None and float(q_hat) != band.q_hat
    ):
        found.append(f"q_hat {q_hat!r} is not the k-th smallest stored score ({band.q_hat!r})")
    hits = None if band.q_hat is None else coverage_hits(test_scores, band.q_hat)
    if evaluation["hits"] != hits:
        found.append(f"hits {evaluation['hits']!r} is not #{{score <= q_hat}} = {hits!r}")
    lower = None if hits is None else clopper_pearson_lower(hits, m)
    stored = evaluation["lower_bound"]
    if (stored is None) != (lower is None) or (
        lower is not None and stored is not None and abs(float(stored) - lower) > 1e-12
    ):
        found.append(f"lower_bound {stored!r} is not L(H, m) = {lower!r}")

    # The verdict, re-derived from the stored metrics (spec §7.3).
    fit = manifest["predictor"]["fit"]
    gradient = manifest["gradient"]["centres"]
    errors: tuple[float, ...] | None = None
    if gradient and all(c["status"] == "ok" and c["errors"] is not None for c in gradient):
        errors = tuple(float(c["errors"][o]) for c in gradient for o in ("X", "dT_K"))
    complete = not any(splits[split]["incomplete"] for split in SPLITS)
    derived = study_verdict(
        StudyEvidence(
            budget_ok=True,
            plan_complete=complete,
            training_ok=int(fit["training_ok"]),
            singular_value_ratio=None
            if fit["singular_value_ratio"] is None
            else float(fit["singular_value_ratio"]),
            calibration_scores=cal_scores,
            test_scores=test_scores,
            gradient_errors=errors,
            inadmissible=int(manifest["domain"]["inadmissible_predictions"]),
            extrapolated=int(manifest["domain"]["parent_extrapolated"]),
        )
    )
    promotion = manifest["promotion"]
    recorded = (
        promotion["verdict"],
        tuple(promotion["insufficient"]),
        tuple(promotion["not_promotable"]),
    )
    if recorded != (derived.verdict, derived.insufficient, derived.not_promotable):
        found.append(
            f"verdict {recorded} is inconsistent with the stored metrics "
            f"({derived.verdict}, {derived.insufficient}, {derived.not_promotable})"
        )
    bound = familywise_bound(
        len(manifest["predecessors"]), derived.hits is not None and derived.h_min is not None
    )
    if promotion["familywise_false_pass_bound"] != bound:
        found.append(
            f"familywise_false_pass_bound {promotion['familywise_false_pass_bound']!r} is not "
            f"0.05 x the iterations whose coverage test was evaluated ({bound!r})"
        )
    if (manifest["predictor"]["coefficients"] is None) != (
        "training_unidentifiable" in derived.insufficient
    ):
        found.append("coefficients are present iff the fit is identifiable")
    if (manifest["predictor"]["coefficients"] is None) != (
        manifest["domain"]["admissibility_margin"] is None
    ):
        found.append("admissibility_margin is present iff there is a predictor")

    # The qualifications: Q0 first iff synthetic, then Q1–Q7, Q6 filled.
    stated = list(manifest["qualifications"])
    for text in stated:
        if _UNFILLED.search(text):
            found.append(f"qualification with an unfilled field: {text!r}")
    expected_q = ([Q0] if manifest["synthetic"] else []) + list(QUALIFICATIONS)
    if len(stated) != len(expected_q):
        found.append(f"{len(stated)} qualifications; {len(expected_q)} are required")
    else:
        q6_index = _Q6 + (1 if manifest["synthetic"] else 0)
        for i, (text, required) in enumerate(zip(stated, expected_q, strict=True)):
            if i == q6_index:
                if not text.startswith("nominal 0.95 (finite-sample k/(n+1) = "):
                    found.append(f"Q6 is missing: {text!r}")
            elif text != required:
                found.append(f"qualification {required!r} is missing")
    return found
