"""S19 design batch 1, Q1 (docs/briefs/S19-D-batch1-ruling.md): the component-order link the
SYN-form verifier relies on.

`verify.split_checks` reads SYN-form stream flows in `verify.checks.COMPONENTS` order and pairs
them with the revision view's and the fresh provider's component order. That is right only while
every basis whose verifier form is SYN has exactly those components in that order. The view's
order is the basis' (`canonical_components`) and the fresh provider refuses a basis it does not
describe (`basis_mismatch`), so the one link no other test pins is `COMPONENTS` itself, a separate
literal: Q1.A1 pins it, Q1.A2 is the negative control that keeps A1 from passing vacuously.
"""

from __future__ import annotations

import pytest

from openflowsheet.models.revision_flowsheet import selectable_bases
from openflowsheet.verify import checks, forms
from openflowsheet.verify.certificate import fresh_provider


def _syn_order_mismatches() -> tuple[list[str], int]:
    """The SYN-form bases whose basis or fresh-provider components differ from `COMPONENTS`
    (exact tuple equality), and how many SYN-form bases were examined."""
    mismatches: list[str] = []
    examined = 0
    for basis in selectable_bases():
        if forms.form_of(basis.provider_id) != forms.SYN:
            continue
        examined += 1
        if tuple(basis.components) != tuple(checks.COMPONENTS):
            mismatches.append(f"{basis.provider_id}: basis {tuple(basis.components)}")
            continue
        described = tuple(fresh_provider(basis).describe().components)
        if described != tuple(checks.COMPONENTS):
            mismatches.append(f"{basis.provider_id}: provider {described}")
    return mismatches, examined


def test_q1_a1_syn_form_bases_have_the_checks_component_order() -> None:
    mismatches, examined = _syn_order_mismatches()
    assert examined >= 1
    assert mismatches == []


def test_q1_a2_negative_control_a_non_syn_order_is_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(forms._FORMS, "wilson-ig-v2", forms.SYN)  # type: ignore[index]
    mismatches, examined = _syn_order_mismatches()
    assert examined >= 2
    assert any(entry.startswith("wilson-ig-v2:") for entry in mismatches)
