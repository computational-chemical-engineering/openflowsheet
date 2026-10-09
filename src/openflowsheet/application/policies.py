"""The application's registered solve policies (T07 design note §12.2, ruling round 1 R2.3).

Two policies, one per solve route, each the route's registered policy, and T08's offered
additions (ADR 0024):

- `T06-revision-v2`, the revision path's (`revision_eo`): ADR 0018 D6, T06 spec §6.6 (A4). It is
  `T06-revision-v1` with only `globalization.eo_core` changed, to `newton_refined`; v1 is `T05b-v2`
  with only `globalization.eo_recovery` changed, to `homotopy_or_sequential_restart` (ADR 0015);
  `T05b-v2` is the defaults with ADR 0012 D4's phase contract.
- `T04-W12`, the legacy route's (`legacy_eo`): the defaults, under the id the T06 Phase M
  registration run solved NET-05 with (`benchmarks/registry.yaml` `policies.T04-W12`).
- `T08-warm-v1` (ADR 0024 D1; T08 build-first spec §B1): `T06-revision-v2` with only
  `initializer_chain` changed, to `("compatible_warm_start", "traversal-G0-v1")` — the opt-in to
  compatible warm starts. It is offered, never a route's default, and is not a
  `benchmarks/registry.yaml` policy (that registry is T06's; nothing there names it).
- `T08-ptc-v1` (ADR 0023; T08 build-first spec §A2): `T06-revision-v2` with only
  `globalization.eo_core` changed, to `"ptc"`, with `ptc` at `PtcPolicy`'s registered constants
  (T04 §7.7). It is offered: a caller selects it by naming it in `solve_body.policy_id`, and no
  automatic path selects PTC (T04 §7.1). Like `T08-warm-v1`, it is not a
  `benchmarks/registry.yaml` policy.

The chain `T05b-v2` → `T06-revision-v1` → `T06-revision-v2` is constructed **here**, once. It moved
from `tests/t05b_support.py` and `tests/t06_support.py` (W0 flag E6), which now import it, so the
registry's `constructed_by` names this module. Moving it moved no hash: `policy_sha256` of each
object equals its registry entry, which `tests/test_t06_w4_registry.py` and
`tests/test_t07_w3a_revision_runs.py` check.

The reserved id `"default"` names no policy of its own: it resolves, at admission, to the route's
registered policy (`ROUTE_DEFAULT_POLICY`). A named registered policy is honoured on either route.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Final, Literal

from openflowsheet.orchestrator.revision import INITIALIZER_ID
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.orchestrator.warm_start import WARM_START_SOURCE

__all__ = [
    "APPLICATION_POLICIES",
    "DEFAULT_POLICY_ID",
    "INNER_ROUTE",
    "REGISTERED_POLICY_IDS",
    "ROUTE_DEFAULT_POLICY",
    "T04_W12",
    "T05B_V2",
    "T06_REVISION_V1",
    "T06_REVISION_V2",
    "T08_PTC_V1",
    "T08_WARM_V1",
    "SolvePath",
    "resolve_policy",
]

#: The solve routes (ruling round 1 R2.1; `revision_coupled`, M02 design note §4.4, ADR 0034
#: D2). The tear path is not reachable through `solve`.
SolvePath = Literal["revision_eo", "legacy_eo", "revision_coupled"]

#: ADR 0012 D4: the T05b cases' policy, the defaults with phase contract v2.
T05B_V2: Final[SolvePolicy] = SolvePolicy(
    policy_id="T05b-v2",
    residual_tolerances={},
    scales={},
    phase_contract="T05b-phase-contract-v2",
)
#: ADR 0015: run 1's revision-path policy, which stays defined (T06 spec §6.6 (A4), A95).
T06_REVISION_V1: Final[SolvePolicy] = replace(
    T05B_V2,
    policy_id="T06-revision-v1",
    globalization=replace(T05B_V2.globalization, eo_recovery="homotopy_or_sequential_restart"),
)
#: ADR 0018 D6: the revision path's registered policy.
T06_REVISION_V2: Final[SolvePolicy] = replace(
    T06_REVISION_V1,
    policy_id="T06-revision-v2",
    globalization=replace(T06_REVISION_V1.globalization, eo_core="newton_refined"),
)
#: T06 spec §6.6 ("NET-05 under its registered A02 policy"): the legacy route's registered policy.
T04_W12: Final[SolvePolicy] = SolvePolicy(policy_id="T04-W12", residual_tolerances={}, scales={})
#: ADR 0024 D1: the revision path's policy with compatible warm starts opted into.
T08_WARM_V1: Final[SolvePolicy] = replace(
    T06_REVISION_V2,
    policy_id="T08-warm-v1",
    initializer_chain=(WARM_START_SOURCE, INITIALIZER_ID),
)

#: ADR 0023 (build-first spec §A2): the revision path's policy with the PTC core selected; the
#: `ptc` constants are `PtcPolicy`'s defaults, T04 §7.7's registered ones.
T08_PTC_V1: Final[SolvePolicy] = replace(
    T06_REVISION_V2,
    policy_id="T08-ptc-v1",
    globalization=replace(T06_REVISION_V2.globalization, eo_core="ptc"),
)

#: §12.2 as amended by R2.3: the policies a solve through the contract may name.
APPLICATION_POLICIES: Final[Mapping[str, SolvePolicy]] = {
    "T06-revision-v2": T06_REVISION_V2,
    "T04-W12": T04_W12,
    "T08-ptc-v1": T08_PTC_V1,
    "T08-warm-v1": T08_WARM_V1,
}
#: Every name `benchmarks/registry.yaml` registers a solve policy under — its `policies` keys and
#: their `policy_id` values, which differ for `T04-HOM-01-edge-off` (policy id `T04-HOM-01`) — a
#: committed copy — nothing under `benchmarks/` is read at run time — that
#: `tests/test_t07_b3_policies.py` holds equal to both. A registered name the contract does not
#: offer is refused `unsupported`, an unknown one `not_found` (V17 spec F3, adopted in
#: `docs/T07_DECISIONS.md`; `v17-c1` B3; T07 review 2, S2).
REGISTERED_POLICY_IDS: Final[frozenset[str]] = frozenset(
    {
        "SYN-001-K03",
        "T02-eo",
        "T04-HOM-01",
        "T04-HOM-01-edge-off",
        "T04-W12",
        "T05-W13",
        "T05b-v2",
        "T06-revision-v1",
        "T06-revision-v2",
    }
)
#: The reserved id that resolves to the route's registered policy; `solve_body.policy_id`'s
#: default (R2.3).
DEFAULT_POLICY_ID: Final[str] = "default"
#: R2.3: each route's registered policy.
ROUTE_DEFAULT_POLICY: Final[Mapping[SolvePath, str]] = {
    "revision_eo": "T06-revision-v2",
    "legacy_eo": "T04-W12",
}


#: M02 design note §4.4: a route whose inner solves are another route's, and so whose default
#: policy is that route's (`revision_coupled`'s inner plan is `plan_revision`'s, as `revision_eo`).
INNER_ROUTE: Final[Mapping[SolvePath, SolvePath]] = {"revision_coupled": "revision_eo"}


def resolve_policy(policy_id: str, solve_path: SolvePath) -> SolvePolicy | None:
    """The policy a requested id names on `solve_path`: `"default"` is the route's registered
    policy (on `revision_coupled`, its inner route's), a registered id is itself on every route,
    and anything else is `None` (admission's `not_found`, §5.3 step 4)."""
    if policy_id == DEFAULT_POLICY_ID:
        return APPLICATION_POLICIES[ROUTE_DEFAULT_POLICY[INNER_ROUTE.get(solve_path, solve_path)]]
    return APPLICATION_POLICIES.get(policy_id)
