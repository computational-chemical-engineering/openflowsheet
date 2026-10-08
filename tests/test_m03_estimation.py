"""M03 WO-5: the estimation example (spec §7) — A25-A30.

SYN-001's (r, T_f) fitted to the seeded synthetic data the reference generator stored in
`benchmarks/m03/reference_values.json` (`estimation`). FIT-I (eight measurements, with a recycle
flow and the mixer temperature) is identifiable; FIT-U (the six product flows alone) is not, because
every product stream is independent of r (derivation §5.1). The expectations are the generator's
60-digit Gauss-Newton solutions of the same weighted least-squares problems; they are independent of
`least_squares` and of the implicit sensitivities.

The data are generated from the model: these tests verify the estimation machinery, they are not
empirical validation (spec §7.2, §15) — the reports say so in fields.
"""

from __future__ import annotations

import dataclasses
import inspect
from functools import cache
from typing import Any

import pytest
from m03_support import estimation_problem, number, reference

import openflowsheet.studies.estimation as estimation_module
from openflowsheet.studies.estimation import EstimationReport, estimate
from openflowsheet.studies.sensitivity import Refusal, SensitivityResult
from openflowsheet.studies.syn001 import syn001_sensitivity

#: Spec §7.5: estimates (scaled), smooth functionals (relative), correlations and normalized
#: residuals (absolute), and FIT-U's singular-value ratio and null direction.
TAU_ESTIMATE = 1e-8
TAU_RELATIVE = 1e-6
TAU_ABSOLUTE = 1e-6
TAU_RATIO_U = 1e-12
TAU_NULL = 1e-8


@cache
def fit(fit_id: str) -> EstimationReport:
    return estimate(estimation_problem(fit_id))


def expected(fit_id: str) -> dict[str, Any]:
    fits: dict[str, Any] = reference()["estimation"]["fits"]
    return fits[fit_id]


def scale_of(parameter_id: str) -> float:
    return next(
        number(entry["scale"])
        for entry in reference()["estimation"]["theta"]
        if entry["id"] == parameter_id
    )


def relative(value: float, closed: float) -> float:
    return abs(value - closed) / abs(closed)


def test_a25_the_fit_uses_the_stored_observations_bitwise_and_generates_none() -> None:
    data = reference()["estimation"]["data"]
    stored = {entry["id"]: entry["observed"] for entry in data["measurements"] + data["validation"]}
    for fit_id in ("FIT-I", "FIT-U"):
        document = fit(fit_id).as_document()
        for item in document["measurements"] + document["validation_measurements"]:
            # The JSON holds the `repr` of each binary64 observation; the fit used exactly it.
            assert repr(item["observed"]) == stored[item["id"]]
        assert [item["id"] for item in document["measurements"]] == expected(fit_id)["measurements"]
    source = inspect.getsource(estimation_module)
    for marker in ("SplitMix", "0x9E3779B97F4A7C15", "erfinv", "random", "default_rng"):
        assert marker not in source, marker


def test_a26_fit_i_is_identifiable_and_matches_the_closed_form() -> None:
    report, closed = fit("FIT-I"), expected("FIT-I")
    assert report.status == closed["expected_status"] == "IDENTIFIABLE"
    worst_estimate = 0.0
    for parameter_id, value in closed["estimate"].items():
        item = report.estimate(parameter_id)
        assert item.determined and item.estimate is not None
        error = abs(item.estimate - number(value)) / scale_of(parameter_id)
        assert error <= TAU_ESTIMATE, (parameter_id, error)
        worst_estimate = max(worst_estimate, error)
        assert not item.at_bound
        assert item.standard_error is not None
        assert relative(item.standard_error, number(closed["standard_errors"][parameter_id])) <= (
            TAU_RELATIVE
        )
    assert report.identifiability is not None
    pairs = [
        (report.identifiability.singular_value_ratio, number(closed["singular_value_ratio"])),
        (report.chi2, number(closed["chi2"])),
        *zip(
            report.identifiability.singular_values,
            [number(value) for value in closed["singular_values_scaled"]],
            strict=True,
        ),
    ]
    assert report.covariance is not None
    for row, closed_row in zip(report.covariance, closed["covariance"], strict=True):
        pairs.extend(zip(row, [number(value) for value in closed_row], strict=True))
    worst_relative = 0.0
    for value, reference_value in pairs:
        assert value is not None
        assert relative(value, reference_value) <= TAU_RELATIVE, (value, reference_value)
        worst_relative = max(worst_relative, relative(value, reference_value))
    assert report.correlation is not None
    correlation_error = abs(report.correlation[0][1] - number(closed["correlation"]))
    assert correlation_error <= TAU_ABSOLUTE
    assert report.degrees_of_freedom == closed["degrees_of_freedom"] == 6
    assert report.identifiability.null_directions == ()
    assert report.covariance_basis == "declared_sigma"
    print(
        f"A26 worst estimate error {worst_estimate:.3e} scaled; worst relative "
        f"{worst_relative:.3e}; correlation {correlation_error:.3e}; "
        f"estimator {report.estimator_result['message']} nfev {report.estimator_result['nfev']}"
    )


def test_a27_fit_u_is_unidentifiable_along_the_split_fraction() -> None:
    report, closed = fit("FIT-U"), expected("FIT-U")
    assert report.status == closed["expected_status"] == "UNIDENTIFIABLE"
    assert report.identifiability is not None
    assert report.identifiability.rank == 1
    ratio = report.identifiability.singular_value_ratio
    assert ratio <= TAU_RATIO_U
    (direction,) = report.identifiability.null_directions
    expected_direction = [number(value) for value in closed["null_direction_scaled"]]
    null_error = max(abs(a - b) for a, b in zip(direction, expected_direction, strict=True))
    assert null_error <= TAU_NULL
    (undetermined,) = closed["not_determined"]
    split = report.estimate(undetermined)
    assert split.determined is False
    assert split.estimate is None and split.standard_error is None
    assert split.final_iterate is not None
    (parameter_id, value) = next(iter(closed["estimate"].items()))
    temperature = report.estimate(parameter_id)
    assert temperature.determined is True and temperature.estimate is not None
    error = abs(temperature.estimate - number(value)) / scale_of(parameter_id)
    assert error <= TAU_ESTIMATE
    assert temperature.standard_error is None
    assert report.covariance is None and report.correlation is None
    assert report.degrees_of_freedom == closed["degrees_of_freedom"] == 5
    print(
        f"A27 ratio {ratio:.3e}; null direction error {null_error:.3e}; T_f error {error:.3e} "
        f"scaled; r final iterate {split.final_iterate!r}; "
        f"estimator {report.estimator_result['message']} nfev {report.estimator_result['nfev']}"
    )


def test_a28_validation_predictions() -> None:
    report = fit("FIT-I")
    worst_relative = worst_absolute = 0.0
    for entry in expected("FIT-I")["validation"]:
        prediction = report.prediction(entry["id"])
        assert prediction.determined is entry["determined"] is True
        assert prediction.predicted is not None and prediction.standard_error is not None
        assert prediction.normalized_residual is not None
        for value, key in (
            (prediction.predicted, "predicted"),
            (prediction.standard_error, "prediction_standard_error"),
        ):
            error = relative(value, number(entry[key]))
            assert error <= TAU_RELATIVE, (entry["id"], key, error)
            worst_relative = max(worst_relative, error)
        error = abs(prediction.normalized_residual - number(entry["normalized_residual"]))
        assert error <= TAU_ABSOLUTE
        worst_absolute = max(worst_absolute, error)
    unidentifiable = fit("FIT-U")
    for entry in expected("FIT-U")["validation"]:
        prediction = unidentifiable.prediction(entry["id"])
        assert prediction.determined is entry["determined"]
        assert prediction.standard_error is None and prediction.normalized_residual is None
        if entry["determined"]:
            assert prediction.predicted is not None
        else:
            assert prediction.predicted is None
    projections = {
        item.validation_id: item.null_projection_relative for item in unidentifiable.validation
    }
    print(
        f"A28 FIT-I worst relative {worst_relative:.3e}, normalized residual {worst_absolute:.3e}; "
        f"FIT-U null projections {projections}"
    )


@pytest.mark.parametrize("fit_id", ["FIT-I", "FIT-U"])
def test_a29_the_report_says_what_the_data_are(fit_id: str) -> None:
    section = reference()["estimation"]
    document = fit(fit_id).as_document()
    assert document["evidence_class"] == section["evidence_class"] == "numerical_verification"
    assert document["statement"] == section["statement"]
    assert document["seed"] == section["data"]["seed"] == 20261008
    assert document["noise_model"] == {
        name: section["data"][name] for name in ("generator", "uniform", "normal", "observation")
    }
    assert document["theta_true"] == {
        name: number(value) for name, value in section["data"]["theta_true"].items()
    }
    for declared, entry in zip(document["parameters_declared"], section["theta"], strict=True):
        assert declared["bounds"] == [number(entry["lower"]), number(entry["upper"])]
        assert declared["start"] == number(entry["start"])
    sigmas = {
        entry["id"]: number(entry["sigma"])
        for entry in section["data"]["measurements"] + section["data"]["validation"]
    }
    for item in document["measurements"] + document["validation_measurements"]:
        assert item["sigma"] == sigmas[item["id"]]
    assert document["covariance_basis"] == "declared_sigma"


def test_a30_a_refused_sensitivity_ends_the_fit_and_no_difference_jacobian_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[float, float]] = []
    jacobians: list[Any] = []

    def refusing(sheet: Any, result: Any, **kwargs: Any) -> SensitivityResult:
        calls.append((sheet.split_fraction, sheet.flash_temperature))
        real = syn001_sensitivity(sheet, result, **kwargs)
        if len(calls) != 2:
            return real
        forced = Refusal("PHASE_BOUNDARY", "request", "Q4", "forced by the A30 fault injection")
        return dataclasses.replace(real, status="REFUSED", refusals=(forced,), forward=None)

    real_least_squares = estimation_module.least_squares

    def spy(*args: Any, **kwargs: Any) -> Any:
        jacobians.append(kwargs.get("jac"))
        return real_least_squares(*args, **kwargs)

    monkeypatch.setattr(estimation_module, "least_squares", spy)
    report = estimate(estimation_problem("FIT-I"), sensitivity=refusing)
    assert report.status == "FAILED"
    assert report.failure is not None
    assert report.failure.stage == "sensitivity"
    assert report.failure.codes == ("PHASE_BOUNDARY",)
    assert report.failure.iterate == calls[1]
    assert len(calls) == 2
    assert report.parameters == () and report.covariance is None
    assert jacobians and all(callable(jac) for jac in jacobians)
    assert not any(jac in ("2-point", "3-point", "cs") for jac in jacobians)
