"""T08.A20, A22, A23 (and the harvest's A21 from W2.2): the v0.1 supported envelope.

`benchmarks/t08/support_envelope.yaml` against the code and the evidence tree, through
`scripts/t08_support_matrix.py`'s own checks (T08 release spec §5, §9). Each check is also shown to
fail on a mutated envelope, so a check that silently passes everything cannot pass here.
"""

from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from openflowsheet.application import revision_binding

ROOT = Path(__file__).resolve().parents[1]


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t08_support_matrix", ROOT / "scripts" / "t08_support_matrix.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MATRIX = _script()


@pytest.fixture(scope="module")
def envelope() -> dict[str, Any]:
    loaded: dict[str, Any] = MATRIX.load()
    return loaded


@pytest.fixture(scope="module")
def facts() -> dict[str, Any]:
    found: dict[str, Any] = MATRIX.code_facts()
    return found


def test_the_envelope_has_spec_5_1s_form(envelope: dict[str, Any]) -> None:
    assert MATRIX.check_structure(envelope) == []
    # R-280 (c): a synthetic-only model is a listed one.
    mutated = copy.deepcopy(envelope)
    (row,) = (row for row in mutated["axes"] if row["id"] == "unit_models")
    row["synthetic_members"] = ["c1.ghost"]
    assert MATRIX.check_structure(mutated) == [
        "unit_models.synthetic_members: not members ['c1.ghost']"
    ]


def test_a20_the_axes_equal_the_code(envelope: dict[str, Any], facts: dict[str, Any]) -> None:
    assert MATRIX.check_a20(envelope, facts) == []
    assert len(facts["operations"]) == 21  # spec §9's 20 and ADR 0019 Amendment 3's `list_audit`
    # Spec §9's 13 SYN-001 models, literal unchanged; M02's join adds the eight C1 models (R-280),
    # the stand-in synthetic only (R-280 (c)); W27 Amendment 3 adds M04's surrogate (R-301), which
    # has no variant, so it is not synthetic only.
    assert len([model for model in facts["models"] if model.startswith("syn001.")]) == 13
    assert len(facts["models"]) == 22
    assert facts["synthetic_models"] == ["c1.reactor_standin"]
    assert facts["providers"] == ["pr-c1-v1", "syn001"]  # M01 adds `pr-c1-v1` (ADR 0026)
    # The axis is the selectable providers (spec §5.7 Amendment S04, R-568); the module scan also
    # finds S04's library-only `pr-lib-v1` (R-569).
    assert facts["scanned_providers"] == ["pr-c1-v1", "pr-lib-v1", "syn001"]
    assert facts["unit_spellings"] == facts["adr_0016_spellings"]


@pytest.mark.parametrize(
    ("axis", "key", "change"),
    [
        ("unit_models", "members", lambda members: members[:-1]),
        ("unit_models", "synthetic_members", lambda members: []),
        ("unit_models", "synthetic_members", lambda members: [*members, "c1.reactor"]),
        ("solve_policies", "members", lambda members: [*members, "T06-revision-v1"]),
        ("components", "members", lambda members: ["A", "B"]),
        ("specifications", "unit_spellings", lambda rows: [*rows, ["pressure", "barg"]]),
        ("interfaces", "operations", lambda ops: {**ops, "solve": ["python", "cli", "mcp"]}),
        ("property_model", "providers", lambda providers: [*providers, "pr"]),
        ("platforms", "lock_sha256", lambda digest: "0" * 64),
    ],
)
def test_a20_a_changed_axis_is_caught(
    envelope: dict[str, Any], facts: dict[str, Any], axis: str, key: str, change: Any
) -> None:
    mutated = copy.deepcopy(envelope)
    (row,) = (row for row in mutated["axes"] if row["id"] == axis)
    row[key] = change(row[key])
    assert MATRIX.check_a20(mutated, facts) != []


def test_a22_every_row_names_a_typed_outcome_and_a_test_node(envelope: dict[str, Any]) -> None:
    assert MATRIX.check_a22(envelope) == []
    mutated = copy.deepcopy(envelope)
    mutated["unsupported"][0]["evidence"] = ["check:T06.A08"]
    mutated["unsupported"][1]["outcome"] = " "
    assert len(MATRIX.check_a22(mutated)) == 2


def test_a22_every_evidence_reference_resolves(envelope: dict[str, Any]) -> None:
    references = list(MATRIX.evidence_strings(envelope))
    collected = MATRIX.collected_nodes(MATRIX.test_nodes(references))
    checks = MATRIX.manifest_checks()
    assert MATRIX.unresolved(references, collected, checks) == []
    dangling = [
        ("x", "tests/test_t08_w2_unsupported.py::test_no_such_test"),
        ("x", "check:T06.A999"),
        ("x", "doc:docs/no-such-file.md §1"),
        ("x", "somewhere"),
    ]
    assert len(MATRIX.unresolved(dangling, collected, checks)) == 4


def test_a22_the_unsupported_rows_test_nodes_pass(envelope: dict[str, Any]) -> None:
    """Spec §9, T08.A22: the node "exists and passes" — run, not skipped."""
    nodes = MATRIX.unsupported_nodes(envelope)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", *nodes],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output[-4000:]
    assert "SKIPPED" not in output and " skipped" not in output, output[-4000:]


def test_an_unbound_provider_is_rendered_apart_from_the_axes_with_its_limitation(
    envelope: dict[str, Any],
) -> None:
    """M01 review F1: `pr-c1-v1` is shipped but bound by no model, so the matrix must not list it
    beside the axes' components and domain without its caveat (L42)."""
    rendered = MATRIX.render(envelope).splitlines()
    (components,) = (line for line in rendered if line.startswith("- **Components:**"))
    assert "pr-c1-v1" not in components and "`syn001`" in components
    (shipped,) = (
        line for line in rendered if line.startswith("- **Shipped, bound on another basis:**")
    )
    assert "`pr-c1-v1`" in shipped and "no mixture VLE validation" in shipped
    assert shipped.endswith("(L42)")
    mutated = copy.deepcopy(envelope)
    (axis,) = (row for row in mutated["axes"] if row["id"] == "property_model")
    axis["other_basis_providers"] = [
        {"id": "pr-c1-v1", "limitation": "L99", "caveat": "x"},
        {"id": "pr", "limitation": "L42", "caveat": " "},
    ]
    assert len(MATRIX.check_structure(mutated)) == 3


def test_a23_the_matrix_regenerates_byte_for_byte(envelope: dict[str, Any]) -> None:
    assert MATRIX.check_a23(envelope) == []
    mutated = copy.deepcopy(envelope)
    mutated["limitations"][0]["text"] += " (edited)"
    assert MATRIX.render(mutated) != MATRIX.render(envelope)


# -- T08.A21: the harvest (W2.2) --------------------------------------------------------------


@pytest.fixture(scope="module")
def harvest_context(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "items": MATRIX.harvest_items(),
        "collected": MATRIX.collected_nodes(MATRIX.test_nodes(MATRIX.harvest_references(envelope))),
        "passing": MATRIX.manifest_checks(passing=True),
    }


def test_a21_every_item_is_classified_once_and_resolves(
    envelope: dict[str, Any], harvest_context: dict[str, Any]
) -> None:
    assert MATRIX.check_a21(envelope, **harvest_context) == []
    items = harvest_context["items"]
    # Spec §10's quoted size: 18 manifests of P00-T07, 87 + 145 limitations; plus every non-pass
    # check. Later packages' manifests (T08's since the alpha, MR-3; v0.2's M01 on) are harvested
    # too, but are not in the quote.
    v0_1 = {
        key
        for key in items
        if key[0].split("/")[1][0] in "PKT" and not key[0].startswith("evidence/T08/")
    }
    manifests = {path for path, _ in v0_1}
    limitations = [key for key in v0_1 if key[1].startswith("limitations")]
    assert (len(manifests), len(limitations)) == (18, 232)
    assert len(envelope["harvest"]) == len(items)


def _mutated(envelope: dict[str, Any], change: Any) -> dict[str, Any]:
    mutated = copy.deepcopy(envelope)
    change(mutated["harvest"])
    return mutated


def _first(kind: str) -> Any:
    def pick(harvest: list[dict[str, Any]]) -> dict[str, Any]:
        return next(entry for entry in harvest if entry["class"] == kind)

    return pick


@pytest.mark.parametrize(
    "change",
    [
        lambda h: h.pop(0),  # unmapped
        lambda h: h.append(dict(h[0])),  # classified twice
        lambda h: h.append({**h[0], "item": "limitations[999]"}),  # dangling
        lambda h: h[0].__setitem__("sha256", "0" * 64),  # changed text
        lambda h: h[0].__setitem__("class", "X"),
        lambda h: _first("P")(h).__setitem__("to", ["L18"]),
        lambda h: _first("E")(h).__setitem__("to", ["L99"]),
        lambda h: _first("E")(h).__setitem__("to", []),
        lambda h: _first("B")(h).__setitem__("to", ["B99"]),
        lambda h: _first("S")(h).__setitem__("to", ["check:K03.initializer_chain"]),
        lambda h: _first("S")(h).__setitem__("to", ["doc:docs/no-such.md"]),
    ],
    ids=[
        "unmapped",
        "twice",
        "dangling",
        "hash",
        "class",
        "P-pointer",
        "E-dangling",
        "E-empty",
        "B-dangling",
        "S-not-pass",
        "S-missing-doc",
    ],
)
def test_a21_a_bad_harvest_is_caught(
    envelope: dict[str, Any], harvest_context: dict[str, Any], change: Any
) -> None:
    assert MATRIX.check_a21(_mutated(envelope, change), **harvest_context) != []


def test_m04_and_m05_harvest_rows_map_to_l49_not_the_alphas_l43(envelope: dict[str, Any]) -> None:
    """The alpha's released L43 keeps its id; M04's envelope row is L49, and the M04/M05 manifests
    that cite it as "L43" are mapped there by their harvest rows (R-459, AM-30)."""
    rows = [
        entry
        for entry in envelope["harvest"]
        if entry["manifest"].startswith(("evidence/M04/", "evidence/M05/"))
    ]
    assert [entry["item"] for entry in rows if "L43" in (entry.get("to") or [])] == []
    assert any("L49" in (entry.get("to") or []) for entry in rows)
    (l43,) = (row for row in envelope["limitations"] if row["id"] == "L43")
    assert " ".join(l43["text"].split()).startswith("The Anderson recycle")


# -- D1-A03: the library-only tripwire (D1, R-561) --------------------------------------------

#: The syn001 models that are library-only: package whose harvest items name them under U04.
#: The package that binds either model writes its L-rows and reclassifies its U04 items.
LIBRARY_ONLY = {"syn001.cascade": "S01", "syn001.column": "S02"}


def library_only_problems(builders: Any, harvest: list[dict[str, Any]]) -> list[str]:
    """Why `LIBRARY_ONLY` no longer holds: (a) a library-only id in `builders`; (b) an item of
    its package's manifests with U04 in `to` whose note lacks the id in back-ticks and
    `library-only`; (c) a package with no U04 item (no vacuous pass)."""
    problems: list[str] = []
    for model_id, package in LIBRARY_ONLY.items():
        suffix = "bound: add its L-rows and reclassify its U04 items (D1, R-561)"
        if model_id in builders:
            problems.append(f"{model_id} is in MODEL_BUILDERS; {suffix}")
        items = [
            entry
            for entry in harvest
            if entry["manifest"].startswith(f"evidence/{package}/")
            and "U04" in (entry.get("to") or [])
        ]
        if not items:
            problems.append(f"{model_id}: {package} has no U04 item in the harvest; {suffix}")
        for entry in items:
            note = entry.get("note") or ""
            if f"`{model_id}`" not in note or "library-only" not in note:
                problems.append(
                    f"{model_id}: {entry['manifest']} {entry['item']} is U04 without "
                    f"`{model_id}` and library-only in its note; {suffix}"
                )
    return problems


def test_d1_the_library_only_models_are_unbound_with_their_u04_items(
    envelope: dict[str, Any],
) -> None:
    assert library_only_problems(revision_binding.MODEL_BUILDERS, envelope["harvest"]) == []


def test_d1_binding_a_library_only_model_trips_the_wire(envelope: dict[str, Any]) -> None:
    bound = {**revision_binding.MODEL_BUILDERS, "syn001.cascade": object()}
    problems = library_only_problems(bound, envelope["harvest"])
    assert len(problems) == 1
    assert "syn001.cascade" in problems[0]
    assert "bound: add its L-rows and reclassify its U04 items (D1, R-561)" in problems[0]


def test_d1_a_u04_item_that_loses_its_model_id_trips_the_wire(envelope: dict[str, Any]) -> None:
    mutated = copy.deepcopy(envelope["harvest"])
    entry = next(
        item
        for item in mutated
        if item["manifest"].startswith("evidence/S01/") and "U04" in (item.get("to") or [])
    )
    entry["note"] = entry["note"].replace("`syn001.cascade`", "the cascade")
    problems = library_only_problems(revision_binding.MODEL_BUILDERS, mutated)
    assert len(problems) == 1
    assert "syn001.cascade" in problems[0]
    # no vacuous pass: a harvest with the package's U04 items removed is also a problem
    stripped = [i for i in envelope["harvest"] if "U04" not in (i.get("to") or [])]
    assert len(library_only_problems(revision_binding.MODEL_BUILDERS, stripped)) == 2
