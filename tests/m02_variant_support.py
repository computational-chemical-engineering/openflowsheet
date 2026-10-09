"""Test-only variants a test registers for the binder (M02 WO-10, WO-11). Not collected.

`register_variants(monkeypatch)` patches `adapters.variants.registry` and `registered_variant` for
the test only, and returns `add(variant) -> variant`: each added variant then resolves by its id
and SHA-256 exactly as a registered one does (the binder's `model_variant_mismatch` pass, the
replacement check's `resolvable` facet). Package data is never touched.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from openflowsheet.adapters import variants


def register_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[variants.Variant], variants.Variant]:
    extra: dict[str, variants.Variant] = {}
    registry, registered = variants.registry, variants.registered_variant
    monkeypatch.setattr(
        variants,
        "registry",
        lambda: {**registry(), **{key: value.sha256 for key, value in extra.items()}},
    )
    monkeypatch.setattr(
        variants,
        "registered_variant",
        lambda variant_id: extra[variant_id] if variant_id in extra else registered(variant_id),
    )

    def add(variant: variants.Variant) -> variants.Variant:
        extra[variant.variant_id] = variant
        return variant

    return add
