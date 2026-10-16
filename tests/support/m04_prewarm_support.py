"""M04.A40's library-level half: the smooth synthetic parent's records written by worker processes.

Not collected. The synthetic parents are reachable from no request (they are not registered), so
an `experiment` job cannot evaluate one; `run_chunk` is the body each spawned process runs instead:
its own `ExperimentRunner` on the shared experiment store, over its share of the plan's requests
(distinct keys, R-250's per-key locks). It lives in an importable module because the `spawn` start
method imports it by name in a fresh interpreter (as `t07_process_support`'s bodies do).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import m04_synthetic_parents as parents

from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider

#: The context of `tests/test_m04_study.py`'s runner, so that the keys are A19's.
MODEL_VERSION = "m04-study"


def runner(root: Path) -> ExperimentRunner:
    return ExperimentRunner(
        ExperimentStore(root, ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version=MODEL_VERSION, constants_sha256="0" * 64),
        backend_for=parents.backend_for(),
    )


def run_chunk(root: str, variant_id: str, requests: Sequence[tuple[float, ...]]) -> list[str]:
    """Run each request `(n₁, …, n₅, T, P)` at one tube through a fresh runner; the keys written
    or served, in order."""
    variant = parents.synthetic_variant(variant_id)
    own = runner(Path(root))
    keys = []
    for values in requests:
        state = StreamState(n=tuple(values[:5]), temperature=values[5], pressure=values[6])
        keys.append(own.run(variant, state, COMPONENTS, 1.0).key)
    return keys
