"""T06 M7/W6: the ensemble generator's law and the published starts (T6-A21…A26, A80).

Spec `docs/derivations/T06-corpus-spec.md` §6.2–§6.5 as amended (Amendments 1–3); the
generator is `benchmarks/t06/generator.py`, the published starts
`benchmarks/t06/ensemble/starts-nominal-v1.json`. A21 is on the bit patterns `u_hex` and
`delta_hex` of `ref.closed_form.draw_known_answers`, never on the decimal strings, and the draw's
`δ` is `(2.0*u − 1.0)/5.0`; the literal `0.2*w` fails three of the ten known answers, so the wrong
arithmetic cannot pass this test. A22 restates §6.2's coordinate rule without the generator; A80
recomputes every published coordinate from its recorded `u` and key.
"""

from __future__ import annotations

import hashlib
import json
import math
import pathlib
from fractions import Fraction
from functools import cache
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t06_ensemble_support import STARTS_FILE, ensemble_cases
from t08_rename_substitution import renamed_back_sha256, renamed_back_starts

from benchmarks.t06 import ensemble, generator
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.canonical import canonical_json
from openflowsheet.models.revision_flowsheet import pin_specifications
from openflowsheet.models.syn001.feed import FeedSource
from openflowsheet.run.compare import differences
from openflowsheet.thermo.syn001 import Syn001Provider

TWIN: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")
KATS: list[dict[str, Any]] = TWIN["closed_form"]["draw_known_answers"]
REGISTRY: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
PUBLISHED_BYTES = STARTS_FILE.read_bytes()
PUBLISHED: dict[str, Any] = json.loads(PUBLISHED_BYTES)
BY_CASE: dict[str, dict[str, Any]] = {entry["case"]: entry for entry in PUBLISHED["cases"]}
CASES = {case.case: case for case in ensemble_cases()}
#: §6.5, §6.6 (A4): the published starts were generated under run 1's policies and are never
#: regenerated. The revision path's policy moved to `T06-revision-v2` by
#: `globalization.eo_core` alone (A86), which the generator never reads.
GENERATED_UNDER: dict[str, str] = REGISTRY["ensemble"]["run_1"]["policies"]


# -- the draw (A21) ------------------------------------------------------------------------------


def test_there_are_ten_known_answers_and_three_refuse_the_literal() -> None:
    assert len(KATS) == 10
    assert sum(1 for kat in KATS if kat["literal_0p2_product_differs"]) == 3


@pytest.mark.parametrize("kat", KATS, ids=[kat["key"] for kat in KATS])
def test_a21_the_draw_reproduces_every_known_answer_bit_for_bit(kat: dict[str, Any]) -> None:
    key = kat["key"]
    assert generator.k53(key) == kat["k53"]
    u = generator.uniform(key)
    assert u.hex() == float.fromhex(kat["u_hex"]).hex()
    delta = generator.delta(key)
    assert delta.hex() == float.fromhex(kat["delta_hex"]).hex()
    # Independently of the generator: the nearest double to the exact rational (2k − 2⁵³)/(5·2⁵³).
    exact = Fraction(2 * kat["k53"] - 2**53, 5 * 2**53)
    assert delta == float(exact)
    # The literal product is a different law at exactly the registered keys.
    literal = 0.2 * (2.0 * u - 1.0)
    assert (literal != delta) is kat["literal_0p2_product_differs"]


def test_a21_the_key_is_the_registered_spelling() -> None:
    key = generator.draw_key("SYN-001-T06-NET03", 12, 0, "S10.T", 1)
    assert key == "T06-ens-v1|nominal|SYN-001-T06-NET03|12|00|S10.T|01"
    assert key in {kat["key"] for kat in KATS}


def test_a21_no_fixture_or_coordinate_id_contains_the_key_separator() -> None:
    """§6.3 (A3): the key's `<case id>` is the registered fixture id; the fixture ids are
    pairwise distinct and neither they nor a selected coordinate id contain `|`, so a key parses
    back into its fields and no two draws share a key."""
    fixtures = [entry["fixture"] for entry in PUBLISHED["cases"]]
    assert fixtures == [CASES[entry["case"]].fixture for entry in PUBLISHED["cases"]]
    assert len(set(fixtures)) == len(fixtures) == 22
    for entry in PUBLISHED["cases"]:
        assert "|" not in entry["fixture"], entry["case"]
        for coordinate in entry["coordinates"]:
            assert "|" not in coordinate["id"], (entry["case"], coordinate["id"])


def test_the_draw_lies_in_its_interval_and_the_start_rounds_twice() -> None:
    """`δ ∈ [−0.2, 0.2)`; `x_init + S*δ` is the product rounded, then the sum rounded."""
    for index in range(2000):
        assert -0.2 <= generator.delta(f"probe|{index}") < 0.2
    x, scale = 0.1, 3.0
    delta = generator.delta("T06-ens-v1|nominal|SYN-001-nominal|00|00|S6.n.A|00")
    product = scale * delta
    assert generator.perturbed(x, scale, delta) == x + product
    assert generator.perturbed(x, scale, delta) == float(Fraction(x) + Fraction(product))


# -- the published starts (A22–A26, A80) ---------------------------------------------------------


def test_the_file_is_the_registered_one_with_every_start() -> None:
    """A25's hash half and A23's assembly half: 22 cases × 20 starts, none `F-GEN`."""
    assert hashlib.sha256(PUBLISHED_BYTES).hexdigest() == REGISTRY["ensemble"]["starts_sha256"]
    assert canonical_json(PUBLISHED) == PUBLISHED_BYTES
    assert PUBLISHED["rng"] == generator.RNG_ID == REGISTRY["ensemble"]["law"]["rng"]
    # §6.5 never regenerates the file: it names the generator's bytes before the rename (R-149).
    assert PUBLISHED["generator_sha256"] == renamed_back_sha256(pathlib.Path(generator.__file__))
    assert [entry["case"] for entry in PUBLISHED["cases"]] == REGISTRY["ensemble"]["cases"]
    for entry in PUBLISHED["cases"]:
        assert [start["start"] for start in entry["starts"]] == list(range(20)), entry["case"]
        assert entry["generation_failures"] == []
        assert entry["policy"] == GENERATED_UNDER[entry["path"]]
        registered = REGISTRY["ensemble"]["policies"][entry["path"]]
        assert CASES[entry["case"]].policy.policy_id == registered
        assert entry["initializer"] == generator.INITIALIZERS[entry["path"]]
    assert PUBLISHED["counts"]["starts_accepted"] == 440
    assert PUBLISHED["counts"]["generation_failures"] == 0


def test_a26_the_recorded_counts_recompute_from_the_records() -> None:
    coordinate = joint = 0
    for entry in PUBLISHED["cases"]:
        for start in entry["starts"]:
            coordinate += sum(len(draw["rejected"]) for draw in start["draws"])
            coordinate += sum(r["coordinate_rejections"] for r in start["joint_rejections"])
            joint += len(start["joint_rejections"])
            assert start["joint_attempts"] == len(start["joint_rejections"]) + 1
    assert PUBLISHED["counts"]["coordinate_rejections"] == coordinate
    assert PUBLISHED["counts"]["joint_rejections"] == joint


def _lifted(column: str) -> bool:
    """A lifted split's column (§6.2): phase flows, phase totals, products-style totals."""
    parts = column.split(".")
    return parts[1] in ("vap", "liq") or parts[-1] in ("V", "L", "N")


@pytest.mark.parametrize("case_id", sorted(BY_CASE))
def test_a22_the_selected_coordinates_are_the_rule_applied_to_the_binding(case_id: str) -> None:
    """§6.2 restated without the generator: on the revision path every declared column that is
    no lifted split's, that no fixed specification pins, and that is not a flow of a component no
    feed carries and no reaction touches, in declaration order; its scale is its kind's."""
    entry, case = BY_CASE[case_id], CASES[case_id]
    ids = [coordinate["id"] for coordinate in entry["coordinates"]]
    if case.path == "tear":
        assert ids == ["S6.n.A", "S6.n.B", "S6.n.C"]
        return
    if case.path == "legacy_eo":
        assert ids == ["S3.T"]
        return
    document = case.document()
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding)
    pinned = set(pin_specifications(document))
    units = binding.flowsheet.units()
    feeds = [unit for unit in units if isinstance(unit, FeedSource)]
    reacting = {
        component
        for unit in units
        if hasattr(unit, "stoichiometry")
        for component, nu in zip(unit.components, unit.stoichiometry, strict=True)
        if nu != 0.0
    }
    absent = {
        component
        for component in binding.flowsheet.components
        if all(dict(zip(f.components, f.flows, strict=True))[component] == 0.0 for f in feeds)
        and component not in reacting
    }
    expected = [
        column
        for column in binding.spec.variable_ids
        if not _lifted(column)
        and column not in pinned
        and not (".n." in column and column.rsplit(".", 1)[1] in absent)
    ]
    assert ids == expected
    for coordinate in entry["coordinates"]:
        kind = binding.spec.variable_kinds[coordinate["id"]]
        assert coordinate["scale"] == generator.SCALES[kind]


@pytest.mark.parametrize("case_id", sorted(BY_CASE))
def test_a23_a80_every_start_is_its_draws_recomputed_bit_for_bit(case_id: str) -> None:
    """A80: each selected coordinate is `x_init + S*δ` from its recorded `u`, whose key is that of
    its accepted attempt; each earlier attempt's value lay outside the box on the recorded side;
    every accepted value lies in its box (A23); no other stream or unit column moved."""
    entry = BY_CASE[case_id]
    coordinates = {c["id"]: c for c in entry["coordinates"]}
    for start in entry["starts"]:
        joint = start["joint_attempts"] - 1
        assert [draw["coordinate"] for draw in start["draws"]] == list(coordinates)
        for draw in start["draws"]:
            coordinate = coordinates[draw["coordinate"]]
            low = -math.inf if coordinate["lower"] is None else float(coordinate["lower"])
            high = math.inf if coordinate["upper"] is None else float(coordinate["upper"])
            x_init = float(entry["x_init"][draw["coordinate"]])
            scale = float(coordinate["scale"])
            for attempt, side in enumerate(draw["rejected"]):
                key = generator.draw_key(
                    entry["fixture"], start["start"], joint, draw["coordinate"], attempt
                )
                value = x_init + scale * ((2.0 * generator.uniform(key) - 1.0) / 5.0)
                assert (value < low) if side == "below" else (value > high)
            key = generator.draw_key(
                entry["fixture"], start["start"], joint, draw["coordinate"], draw["attempt"]
            )
            u = float(draw["u"])
            assert u == generator.k53(key) * 2.0**-53
            product = scale * ((2.0 * u - 1.0) / 5.0)
            value = x_init + product
            recorded = float(start["vector"][draw["coordinate"]])
            assert value.hex() == recorded.hex() or value == 0.0 == recorded, draw
            assert low <= recorded <= high
        for column, value in start["vector"].items():
            if column in coordinates or column in entry["held_zero"] or _lifted(column):
                continue
            assert float(value) == float(entry["x_init"][column]), (case_id, column)


def _live_provider_block() -> dict[str, str]:
    """§6.5 (A3): the regeneration records the live provider's identity, never a copy of the
    published block — a moved provider identity shows as a differing byte, not as a pass."""
    described = Syn001Provider().describe()
    return {
        "provider_id": described.provider_id,
        "implementation_sha256": described.implementation_sha256,
        "data_sha256": described.data_sha256,
    }


@cache
def _regenerated() -> dict[str, Any]:
    generated = []
    for case in ensemble_cases():
        setup = ensemble.setup(case)
        starts, failures = generator.generate_case(setup)
        for start in starts:
            # A24: an absent component's every column is +0.0 — the sign is checked here, in
            # memory, because canonical JSON spells -0.0 and +0.0 alike.
            for column in setup.held_zero:
                value = start.assembled.vector[column]
                assert value == 0.0 and math.copysign(1.0, value) > 0.0, (case.case, column)
        generated.append((setup, starts, failures))
    return generator.document(
        generated,
        policies={case.case: GENERATED_UNDER[case.path] for case in ensemble_cases()},
        provider=_live_provider_block(),
        machine=generator.host(),
    )


def test_a24_absent_components_are_held_at_positive_zero() -> None:
    held = {entry["case"]: entry["held_zero"] for entry in PUBLISHED["cases"]}
    assert held["STA-02"] and all(column.endswith(".B") for column in held["STA-02"])
    assert held["NUM-03"] and all(column.endswith(".C") for column in held["NUM-03"])
    for case_id in ("THM-07", "THM-08", "THM-09"):
        assert held[case_id] and all(column.endswith((".A", ".C")) for column in held[case_id])
    for entry in PUBLISHED["cases"]:
        for start in entry["starts"]:
            assert all(start["vector"][column] == 0 for column in entry["held_zero"])
    _regenerated()


def test_the_generator_does_not_read_the_core() -> None:
    """(A4): what moved v1 to v2 is not an input of the draw or the start assembly."""
    source = pathlib.Path(generator.__file__).read_text(encoding="utf-8")
    assert "globalization" not in source and "eo_core" not in source


def test_a25_the_starts_regenerate_byte_for_byte_on_the_reference_machine_class() -> None:
    """§6.5: on the generating host the regeneration is the published file byte for byte; on any
    other host the regenerated document is reported against it under `K04-numerical-policy-v1`
    and never replaces it (a report there, not a gate). **(A3)** The regeneration carries the
    live provider's block (A3.11: after ADR 0017 the file is `3a7bd49c…`, re-emitted for the
    provider hash alone). Since the rename (R-149) the live provider and generator hashes are the
    file's with the package's name substituted, and they are compared substituted back."""
    assert (
        PUBLISHED["provider"]
        == renamed_back_starts(
            {"provider": _live_provider_block(), "generator_sha256": generator.generator_sha256()}
        )["provider"]
    )
    regenerated = renamed_back_starts(_regenerated())
    if regenerated["host"] == PUBLISHED["host"]:
        assert canonical_json(regenerated) == PUBLISHED_BYTES
    else:
        found = differences(regenerated, PUBLISHED, policy_id="K04-numerical-policy-v1")
        print(f"A25 on {regenerated['host']}: {len(found)} differences from the published starts")
        for line in found[:20]:
            print("  " + line)
