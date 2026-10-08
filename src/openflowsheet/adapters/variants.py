"""Variants: the frozen identities of external model configurations (M02 design note §3.1, §6.1;
ADR 0033 D3, ADR 0034 D5, ADR 0035 D1).

A variant is one document of `model-variant.schema.json`: what the model evaluates and how (in the
worker, or in a pinned child per attempt), the boundary contract it is evaluated under, its accuracy
contract, its execution limits and its coupling block. Its identity is its `document_sha256`
(ADR 0002), which a revision pins as `instances[i].model.artifact_ref`; its `variant_id` is
`instances[i].model.version`.

**Append-only package data.** The registered documents are `variants/<variant_id>.json` beside this
module, and `variants/registry.json` maps each `variant_id` to its SHA-256. Loading a registered
variant recomputes the hash and refuses a document that does not match, so an edited document is
refused rather than silently re-pinned. A changed child, overlay, profile, grid, lock or limit is a
**new** variant id; the old one stays loadable so that old revisions keep binding.

A variant built from a document that is not registered (`variant_from_document`) is how tests make
variants a registry must never carry — a synthetic out-of-process child, a perturbed stand-in —
with their own identities; nothing reachable from a request resolves one.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any, Final, Literal

from jsonschema import Draft202012Validator

from openflowsheet.canonical import document_sha256, first_noncanonical, load_document
from openflowsheet.models.c1.boundary import HardDomain
from openflowsheet.resources import packaged

__all__ = [
    "REGISTRY_FILE",
    "Variant",
    "VariantError",
    "hard_domain",
    "registered_variant",
    "registry",
    "resolve",
    "variant_from_document",
]

#: The registered documents' directory, and the registry's file name inside it.
VARIANTS: Final[Traversable] = files("openflowsheet.adapters") / "variants"
REGISTRY_FILE: Final = "registry.json"
SCHEMA_FILE: Final = "model-variant.schema.json"

EvaluationKind = Literal["in_process", "out_of_process"]


class VariantError(ValueError):
    """A variant document that is not a valid, registered, unedited variant."""


@dataclass(frozen=True)
class Variant:
    """One variant: its document (never mutated) and the document's SHA-256."""

    document: Mapping[str, Any]
    sha256: str

    @property
    def variant_id(self) -> str:
        return str(self.document["variant_id"])

    @property
    def model_id(self) -> str:
        return str(self.document["model_id"])

    @property
    def synthetic(self) -> bool:
        return bool(self.document["synthetic"])

    @property
    def kind(self) -> EvaluationKind:
        kind: EvaluationKind = self.document["evaluation"]["kind"]
        return kind

    @property
    def evaluation(self) -> Mapping[str, Any]:
        return self.section("evaluation")

    @property
    def boundary(self) -> Mapping[str, Any]:
        return self.section("boundary")

    @property
    def accuracy(self) -> Mapping[str, Any]:
        return self.section("accuracy")

    @property
    def execution(self) -> Mapping[str, Any]:
        return self.section("execution")

    @property
    def coupling(self) -> Mapping[str, Any]:
        return self.section("coupling")

    @property
    def sweep_ratio(self) -> float:
        """The coolant's sweep ratio: the out-of-process configuration's, else the boundary's
        default 1.0 (the stand-in, spec §8.3)."""
        if self.kind == "out_of_process":
            return float(self.evaluation["configuration"]["sweep_ratio"])
        return 1.0

    def section(self, name: str) -> Mapping[str, Any]:
        value: Mapping[str, Any] = self.document[name]
        return value


@cache
def _validator() -> Draft202012Validator:
    schema = json.loads(packaged(f"schemas/{SCHEMA_FILE}").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def variant_from_document(document: Mapping[str, Any]) -> Variant:
    """A variant from a document: canonical (ADR 0002) and valid against the schema, else
    `VariantError`. Registration is not checked here (`registered_variant` does)."""
    pointer = first_noncanonical(document)
    if pointer is not None:
        raise VariantError(f"variant document not canonical at {pointer!r}")
    errors = sorted(_validator().iter_errors(document), key=lambda error: list(error.path))
    if errors:
        where = "/".join(str(part) for part in errors[0].absolute_path)
        raise VariantError(f"variant document invalid at /{where}: {errors[0].message}")
    return Variant(document=document, sha256=document_sha256(document))


@cache
def registry() -> Mapping[str, str]:
    """`variants/registry.json`: every registered `variant_id` and its SHA-256."""
    document = load_document(
        (VARIANTS / REGISTRY_FILE).read_text(encoding="utf-8"), source=REGISTRY_FILE
    )
    if not isinstance(document, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in document.items()
    ):
        raise VariantError(f"{REGISTRY_FILE} must map variant ids to SHA-256 strings")
    return dict(document)


@cache
def registered_variant(variant_id: str) -> Variant:
    """The registered variant `variant_id`, its hash checked against the registry."""
    pinned = registry().get(variant_id)
    if pinned is None:
        raise VariantError(f"unknown variant {variant_id!r}")
    name = f"{variant_id}.json"
    document = load_document((VARIANTS / name).read_text(encoding="utf-8"), source=name)
    if not isinstance(document, dict):
        raise VariantError(f"{name} is not an object")
    variant = variant_from_document(document)
    if variant.variant_id != variant_id:
        raise VariantError(f"{name} declares variant_id {variant.variant_id!r}")
    if variant.sha256 != pinned:
        raise VariantError(
            f"{name} hashes to {variant.sha256}, the registry pins {pinned}: a registered variant "
            "is never edited (append-only, M02 design note §3.1)"
        )
    return variant


def resolve(model_id: str, version: str | None, artifact_ref: str | None) -> Variant | None:
    """The registered variant a revision's model reference pins (§6.1), or `None` when the id is
    unknown, the hash differs, or the variant is another model's."""
    if version is None or artifact_ref is None or version not in registry():
        return None
    variant = registered_variant(version)
    if variant.sha256 != artifact_ref or variant.model_id != model_id:
        return None
    return variant


def hard_domain(variant: Variant) -> HardDomain:
    """The boundary's hard domain as the variant declares it (ADR 0034 D10)."""
    block = variant.boundary["hard_domain"]
    flow = block["tube_flow_mol_s"]
    return HardDomain(
        temperature_k=(float(block["T_K"][0]), float(block["T_K"][1])),
        pressure_pa=(float(block["P_Pa"][0]), float(block["P_Pa"][1])),
        h2_n2=(float(block["H2_N2"][0]), float(block["H2_N2"][1])),
        inert_fraction=float(block["inert_max"]),
        tube_flow=None if flow is None else (float(flow[0]), float(flow[1])),
    )
