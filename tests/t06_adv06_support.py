"""ADV-06's noisy callback (T06 spec §4.4): the `NoisyProvider` test double and its injection.

Not collected as tests. `NoisyProvider(level)` wraps `Syn001Provider` and implements the frozen
`PropertyProvider` (`describe`, `evaluate_phase`, `flash`): every value `evaluate_phase` returns
for a molar enthalpy `h_<c>` gets `η_h · ξ`, and every `lnK_<c>` gets `η_K · ξ`; derivatives are
returned unchanged and `flash` delegates unchanged. `ξ = 2u − 1` (exact in binary64) with `u`
§6.3's draw (`benchmarks.t06.generator.uniform`) of the key

    T06-ADV-06|<level>|<phase>|<output>|<hex of the IEEE-754 big-endian n_A, n_B, n_C, T, P>

so the noise is a deterministic, rough function of the exact request — the exact property cache
stays consistent and the result does not depend on call order. `<output>` is the result's value
name (`h_A`, `lnK_B`, …) and `<phase>` the request's (`LIQUID`/`VAPOR`).

**The injection hook** (M4, `docs/t06-measurements-m45.md`): `bind_revision_flowsheet` imports
`Syn001Provider` inside the function, so replacing `openflowsheet.thermo.syn001.Syn001Provider`
for the duration of the bind call only puts the double inside the binding's `PropertyMeter`, under
every compiled property block, the traversal and the verifier's compiled residual (which
recompiles `binding.spec`); `verify/certificate.py` binds `Syn001Provider` at module import, so
the verifier's fresh flashes and fresh enthalpies stay clean. If that import ever moves to module
level the patch no longer reaches the binding: `bind_noisy` therefore asserts that the double is
the binding's provider, so such a refactor fails loudly instead of silently testing the clean one.
"""

from __future__ import annotations

import dataclasses
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from test_t06_w4_registry import CONSTRUCTED

import openflowsheet.thermo.syn001 as syn001
from benchmarks.t06.generator import uniform
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.compiled import EvaluationContext
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
)
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision

__all__ = [
    "CASE",
    "KEY_PREFIX",
    "LEVELS",
    "Adv06",
    "NoisyProvider",
    "adv06",
    "bind_noisy",
    "xi",
]

#: ADV-06's registered revision (`registry.yaml` corpus `ADV-06.revision`): T05's C1.
CASE = "benchmarks/t05/cases/SYN-001-UL-C1.yaml"
KEY_PREFIX = "T06-ADV-06"
#: §4.4's table, `level: (η_h in J/mol, η_K)`; `ref.closed_form.adv06_noise_bands` registers the
#: same amplitudes (checked by `test_the_levels_are_the_registered_bands`).
LEVELS: Mapping[str, tuple[float, float]] = {
    "H": (10.0, 1e-3),
    "M": (1e-5, 1e-11),
    "L": (1e-10, 1e-15),
}


#: The clean provider class, captured at import so the double never wraps itself.
_REAL = syn001.Syn001Provider


def xi(key: str) -> float:
    """`ξ = 2u − 1 ∈ [−1, 1)`, exact given `u` (§6.3's draw)."""
    return 2.0 * uniform(key) - 1.0


def noise_key(level: str, request: PropertyRequest, output: str) -> str:
    state = request.state
    exact = struct.pack(">5d", *state.n, state.temperature, state.pressure).hex()
    return f"{KEY_PREFIX}|{level}|{request.phase}|{output}|{exact}"


@dataclass
class NoisyProvider:
    """§4.4's test double. Counts its calls and records the largest noise it added, by kind."""

    level: str
    inner: Any = field(default_factory=lambda: _REAL())
    calls: dict[str, int] = field(default_factory=lambda: {"evaluate_phase": 0, "flash": 0})
    max_noise: dict[str, float] = field(default_factory=lambda: {"h": 0.0, "lnK": 0.0})

    def __post_init__(self) -> None:
        self.eta_h, self.eta_k = LEVELS[self.level]

    def describe(self) -> PropertyCapabilities:
        return self.inner.describe()  # type: ignore[no-any-return]

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        self.calls["evaluate_phase"] += 1
        result: PropertyResult = self.inner.evaluate_phase(request, context)
        if result.status != "ok":
            return result
        values: dict[str, float] = {}
        for name, value in result.values.items():
            kind, _, _ = name.partition("_")
            if kind not in ("h", "lnK"):
                values[name] = value
                continue
            noise = (self.eta_h if kind == "h" else self.eta_k) * xi(
                noise_key(self.level, request, name)
            )
            self.max_noise[kind] = max(self.max_noise[kind], abs(noise))
            values[name] = value + noise
        return dataclasses.replace(result, values=values)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        self.calls["flash"] += 1
        return self.inner.flash(request, context)  # type: ignore[no-any-return]


def bind_noisy(document: Mapping[str, Any], double: NoisyProvider) -> RevisionBinding:
    """Bind `document` with `double` as the provider (the M4 hook), for the bind call only, and
    assert the double is what the binding's meter wraps and that the patch is undone."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(syn001, "Syn001Provider", lambda: double)
        binding = bind_revision_flowsheet(document)
    assert syn001.Syn001Provider is _REAL
    assert isinstance(binding, RevisionBinding), binding
    # The guard against the function-local import moving: the double is actually bound.
    assert binding.flowsheet.provider._provider is double, (
        "NoisyProvider is not the binding's provider: the ADV-06 hook no longer reaches "
        "bind_revision_flowsheet (has its Syn001Provider import moved to module level?)"
    )
    return binding


@dataclass(frozen=True)
class Adv06:
    """One level's run: the double, the binding and plan, the run, the certificate when
    `CONVERGED`, and the double's call counts during the solve and during the verification."""

    level: str
    policy: str
    double: NoisyProvider
    document: dict[str, Any]
    binding: RevisionBinding
    plan: ExecutionPlan
    run: PlanResult
    certificate: SolutionCertificate | None
    solve_calls: Mapping[str, int]
    verify_calls: Mapping[str, int] | None


@cache
def adv06(level: str, policy: str) -> Adv06:
    """C1 bound with `NoisyProvider(level)`, solved on the revision path (`plan_revision` →
    `execute_plan`) under the registered `policy`, and certified (default check policy) when it
    converges. Cached: the three levels are each solved once per policy per session."""
    document: dict[str, Any] = yaml.safe_load((REPO_ROOT / CASE).read_text("utf-8"))
    double = NoisyProvider(level)
    binding = bind_noisy(document, double)
    solve_policy = CONSTRUCTED[policy]
    plan, _ = plan_revision(binding, solve_policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=solve_policy
    )
    solve_calls = dict(double.calls)
    certificate = verify_calls = None
    if run.outcome == "CONVERGED":
        certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
        verify_calls = {name: double.calls[name] - solve_calls[name] for name in double.calls}
    return Adv06(
        level, policy, double, document, binding, plan, run, certificate, solve_calls, verify_calls
    )
