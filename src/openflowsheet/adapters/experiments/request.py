"""An experiment's request and its identity (M02 design note §3.2, ADR 0033 D4).

An experiment is the boundary evaluation of one **process** inlet. Its identity is
`experiment_key = document_sha256(request without experiment_key)` over {model id, variant id and
SHA-256, provider identity, N_tubes, sweep ratio, components, the exact binary64 n, T, P, the
environment fingerprint's SHA-256}. Nothing is quantized: a one-ulp difference in any input is a
different experiment, and (k n, k N_tubes) is a different key although the tube sees the same
inlet (the accepted cost of process-level identity). The requesting job, the purpose, timestamps,
the timeout and the cache mode are context, never identity.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any, Final

from openflowsheet.adapters.variants import Variant
from openflowsheet.canonical import document_sha256, first_noncanonical
from openflowsheet.thermo import PropertyCapabilities, StreamState

__all__ = [
    "REQUEST_VERSION",
    "build_request",
    "capabilities_document",
    "experiment_key",
    "provider_identity_sha256",
]

REQUEST_VERSION: Final = "experiment-request-v1"


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def capabilities_document(capabilities: PropertyCapabilities) -> dict[str, Any]:
    """A provider's `describe()` as a JSON document (tuples as lists), its identity's input."""
    document: dict[str, Any] = _plain(dataclasses.asdict(capabilities))
    return document


def provider_identity_sha256(capabilities: PropertyCapabilities) -> str:
    """§3.2: `document_sha256` of the provider's `describe()` (implementation and data hashes
    included), so a changed provider is a different experiment."""
    return document_sha256(capabilities_document(capabilities))


def experiment_key(request: Mapping[str, Any]) -> str:
    """The request's own `document_sha256`, `experiment_key` left out."""
    return document_sha256(
        {key: value for key, value in request.items() if key != "experiment_key"}
    )


def build_request(
    variant: Variant,
    capabilities: PropertyCapabilities,
    n_tubes: float,
    components: Sequence[str],
    inlet: StreamState,
    environment_fingerprint_sha256: str,
) -> dict[str, Any]:
    """The request document of one experiment, its key included. The inlet is copied exactly;
    a non-finite value has no canonical form and is a `ValueError` here."""
    request: dict[str, Any] = {
        "schema_version": REQUEST_VERSION,
        "model": {
            "id": variant.model_id,
            "version": variant.variant_id,
            "artifact_ref": variant.sha256,
        },
        "boundary": {
            "provider_id": capabilities.provider_id,
            "provider_identity_sha256": provider_identity_sha256(capabilities),
            "n_tubes": n_tubes,
            "sweep_ratio": variant.sweep_ratio,
        },
        "inputs": {
            "components": list(components),
            "n": list(inlet.n),
            "T": inlet.temperature,
            "P": inlet.pressure,
        },
        "environment_fingerprint_sha256": environment_fingerprint_sha256,
    }
    pointer = first_noncanonical(request)
    if pointer is not None:
        raise ValueError(f"an experiment request must be canonical; not at {pointer!r}")
    return {**request, "experiment_key": experiment_key(request)}
