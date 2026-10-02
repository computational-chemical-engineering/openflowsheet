"""Backend-free helpers shared by the two P02 harnesses.

Specification: `docs/derivations/P02-composition-spec.md` §10.1. Nothing here imports a backend,
`process_runtime`, or the judge's `benchmarks.p02.expected` — the harnesses implement the block
formulas themselves so that the judge's expectation stays independent of what it judges.
"""

from spikes.p02.common.counters import BlockCounters, CounterSet
from spikes.p02.common.export import (
    canonical_csc,
    constants_sha256,
    state_sha256,
    write_json,
)
from spikes.p02.common.results import (
    RESULTS_ROOT,
    STATUS_ERROR,
    STATUS_INVALID_TRIAL_STATE,
    STATUS_OK,
    STATUS_UNSUPPORTED,
    ResultWriter,
    jacobian_payload,
    metadata_payload,
    residual_payload,
)
from spikes.p02.common.states import (
    EVALUATION_ORDER,
    I_FORM_VARIABLES,
    StateInput,
    load_directions,
    load_states,
)
from spikes.p02.common.timing import (
    environment_record,
    measure_memory,
    repeat_microseconds,
    timed,
)

__all__ = [
    "EVALUATION_ORDER",
    "I_FORM_VARIABLES",
    "RESULTS_ROOT",
    "STATUS_ERROR",
    "STATUS_INVALID_TRIAL_STATE",
    "STATUS_OK",
    "STATUS_UNSUPPORTED",
    "BlockCounters",
    "CounterSet",
    "ResultWriter",
    "StateInput",
    "canonical_csc",
    "constants_sha256",
    "environment_record",
    "jacobian_payload",
    "load_directions",
    "load_states",
    "measure_memory",
    "metadata_payload",
    "repeat_microseconds",
    "residual_payload",
    "state_sha256",
    "timed",
    "write_json",
]
