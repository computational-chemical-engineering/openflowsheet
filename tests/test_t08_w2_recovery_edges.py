"""T08.A33: the recovery-edge inventory (T08 release spec §5.6, §9; V18 clause (d)).

`docs/recovery-edges.yaml` against the code. The labels the code can emit are read from
the code itself (`code_labels`: Literal annotations at run time, and an AST scan of `src/` for the
producers), never from the inventory, and must be in bijection with the inventory's labels: each
code label in exactly one row or in `not_an_edge`, each inventory label emitted by the code. The
bijection check is also shown to fail on a mutated inventory and on a code label the inventory
lacks, so a check that silently passes everything cannot pass here (spec §5.6: "adding a label
without a row fails, and deleting a row whose label is still emitted fails").
The scan reads event kinds fail-closed (T08 description review, Ruling 3): every `kind=` argument
in `orchestrator/`, `numerics/` and `verify/`, and every `.record(kind=…)` and `_initializer_event`
kind anywhere, must be a string constant or the enclosing function's own parameter (a forwarding
helper, read at its call sites); anything else is an `event:<unreadable at …>` label no row holds.

Every cited test node must be collected and pass. Every `enabled: default`, `policy-only` or
`library-only` row must cite a direct injected-failure test and non-null unchanged-physics
evidence, and a `library-only` row its `reachability_tests` (T08 review 2, Rulings 6 and 8); a row
that does not fails its own parameter of `test_a33_an_enabled_row_carries_its_evidence`, by design
(brief W2.4: the gap stays visible until the design lane rules).
"""

from __future__ import annotations

import ast
import copy
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, get_args, get_type_hints

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "recovery-edges.yaml"
SOURCE = ROOT / "src" / "openflowsheet"

#: Spec §5.6's rows, in its order.
ROW_IDS = ("E1", "E2", "E3a", "E3b", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E11", "E12", "E13")
ENABLED = ("default", "policy-only", "library-only", "absent")
EVIDENCE_KINDS = ("identity_compared", "verified_certificate", "guard")
#: Spec §5.6: the event kinds whose producers the bijection covers.
EVENT_KINDS = frozenset({"restart", "acceleration", "homotopy_step", "initializer_rejected"})
#: T08 description review, Ruling 3 (S6): the packages where every `kind=` argument is read
#: fail-closed (an event producer may forward its kind under any helper name there).
KIND_PACKAGES = ("orchestrator", "numerics", "verify")


def load() -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))
    return document


# -- the labels the code can emit ----------------------------------------------------------------


def _literal(annotation: Any) -> tuple[str, ...]:
    values = get_args(annotation)
    assert values and all(isinstance(value, str) for value in values), annotation
    return values


def _literal_labels() -> set[str]:
    from openflowsheet.models.syn001 import ph_kernel
    from openflowsheet.orchestrator import phase_contract, trace
    from openflowsheet.verify import projection

    hints = get_type_hints(trace.GlobalizationPolicy)
    sources = {
        "eo_core": hints["eo_core"],
        "eo_recovery": hints["eo_recovery"],
        "eo_recovery_unsupported": trace.EoRecoveryUnsupported,
        "opening_source": phase_contract.OpeningSource,
        "decision": phase_contract.DecisionKind,
        "ph_route": ph_kernel.Route,
        "projection_judged_at": projection.JudgedAt,
    }
    return {f"{name}:{value}" for name, literal in sources.items() for value in _literal(literal)}


def _callee(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _strings(node: ast.expr, where: str) -> Iterator[str]:
    """The string literals an argument can take: a constant, either branch of a conditional, or
    an f-string's literal head followed by `*`. Anything else yields a label no row can hold, so
    a producer the scan cannot read fails the bijection instead of vanishing from it."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.IfExp):
        yield from _strings(node.body, where)
        yield from _strings(node.orelse, where)
    elif isinstance(node, ast.JoinedStr):
        head = node.values[0] if node.values else None
        prefix = head.value if isinstance(head, ast.Constant) else ""
        yield f"{prefix}*"
    else:
        yield f"<unreadable at {where}>"


def _module(path: Path) -> str:
    return ".".join(path.relative_to(SOURCE.parent).with_suffix("").parts)


def _parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    arguments = node.args
    named = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    named += [a for a in (arguments.vararg, arguments.kwarg) if a is not None]
    return frozenset(argument.arg for argument in named)


class _Scan(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        self.module = module
        self.scope: list[str] = []
        #: The parameters of each enclosing function, innermost last.
        self.parameters: list[frozenset[str]] = []
        self.labels: set[str] = set()
        self.kind_package = any(
            module == f"openflowsheet.{package}" or module.startswith(f"openflowsheet.{package}.")
            for package in KIND_PACKAGES
        )

    def _nested(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.parameters.append(_parameters(node))
        self._nested(node)
        self.parameters.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function(node)

    def _kinds(self, node: ast.Call, callee: str) -> list[ast.expr]:
        """The kind arguments Ruling 3 reads fail-closed: every `kind=` in `KIND_PACKAGES`, and
        in every module a `.record(kind=…)` (`SolveTrace.record` is the only entry point for
        events) and `_initializer_event`'s third argument."""
        keyword = [k.value for k in node.keywords if k.arg == "kind"]
        if callee == "_initializer_event":
            return keyword + node.args[2:3]
        if self.kind_package or (callee == "record" and isinstance(node.func, ast.Attribute)):
            return keyword
        return []

    def _readable(self, kind: ast.expr) -> bool:
        """A string constant (its producer is read as one), or a parameter of the enclosing
        function (a forwarding helper, whose call sites pass the kind and are read there)."""
        if isinstance(kind, ast.Constant) and isinstance(kind.value, str):
            return True
        return (
            isinstance(kind, ast.Name)
            and bool(self.parameters)
            and (kind.id in self.parameters[-1])
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._nested(node)

    def visit_Call(self, node: ast.Call) -> None:
        where = ".".join([self.module, *self.scope])
        callee = _callee(node)
        arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
        # Event producers. `Decision("restart", …)` is the contract's verdict, read as
        # `decision:` from `DecisionKind`, not a trace event.
        if callee != "Decision":
            for argument in arguments:
                if isinstance(argument, ast.Constant) and argument.value in EVENT_KINDS:
                    self.labels.add(f"event:{argument.value}@{where}")
        # Ruling 3 (S6): a kind the scan cannot read is a label no row can hold, so a producer
        # that passes its kind through a local or a module constant fails the bijection instead
        # of vanishing from it.
        if any(not self._readable(kind) for kind in self._kinds(node, callee)):
            self.labels.add(f"event:<unreadable at {where}>")
        # F2's kernel records (T05b spec §6.5): `_KernelAnswer(regime, values, fallback)`.
        if callee == "_KernelAnswer":
            fallback = [k.value for k in node.keywords if k.arg == "fallback"] + node.args[2:3]
            for value in (v for argument in fallback for v in _strings(argument, where)):
                if value:
                    self.labels.add(f"fallback:{value}")
        # The solve route's fallback (T08 review 2, M1, Ruling 5 E11): a `Route(path, binding,
        # reason)` given a reason — a third positional argument or `reason=` that is not the
        # constant `None` — is the revision binder's refusal sending the document to `path`.
        if callee == "Route":
            reason = [k.value for k in node.keywords if k.arg == "reason"] + node.args[2:3]
            if any(not (isinstance(r, ast.Constant) and r.value is None) for r in reason):
                for value in _strings(node.args[0], where) if node.args else ():
                    self.labels.add(f"route_fallback:{value}")
        # The verifier's projection refusals (ADR 0013 D1): `_refused(state, reason, …)`.
        if callee == "_refused" and self.module == "openflowsheet.verify.projection":
            reason = [k.value for k in node.keywords if k.arg == "reason"] + node.args[1:2]
            for value in (v for argument in reason for v in _strings(argument, where)):
                self.labels.add(f"projection_refused:{value}")
        self.generic_visit(node)


def _scanned_labels() -> set[str]:
    labels: set[str] = set()
    for path in sorted(SOURCE.rglob("*.py")):
        scan = _Scan(_module(path))
        scan.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        labels |= scan.labels
    return labels


def code_labels() -> set[str]:
    from openflowsheet.application import validation
    from openflowsheet.orchestrator import warm_start

    return (
        _literal_labels()
        | _scanned_labels()
        | {f"produced_by:{validation.FALLBACK_PRODUCED_BY}"}
        | {f"initializer_source:{warm_start.WARM_START_SOURCE}"}
    )


# -- the checks -----------------------------------------------------------------------------------


def check_bijection(inventory: Mapping[str, Any], emitted: set[str]) -> list[str]:
    """Every emitted label in exactly one row or `not_an_edge`; every listed label emitted."""
    placed: Counter[str] = Counter()
    for row in inventory["rows"]:
        placed.update(row["labels"])
    placed.update(entry["label"] for entry in inventory["not_an_edge"])
    problems = [f"listed more than once: {label}" for label, n in sorted(placed.items()) if n > 1]
    problems += [
        f"emitted by the code, in no row: {label}" for label in sorted(emitted - placed.keys())
    ]
    problems += [
        f"listed, not emitted by the code: {label}" for label in sorted(placed.keys() - emitted)
    ]
    return problems


def check_form(inventory: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    rows = inventory["rows"]
    if tuple(row["id"] for row in rows) != ROW_IDS:
        problems.append(f"rows are not spec §5.6's: {[row['id'] for row in rows]}")
    for row in rows:
        where = row["id"]
        for key in ("title", "source", "trigger", "precondition", "max_count"):
            if not str(row.get(key) or "").strip():
                problems.append(f"{where}: empty {key}")
        if row.get("enabled") not in ENABLED:
            problems.append(f"{where}: enabled {row.get('enabled')!r}")
        if not isinstance(row.get("labels"), list):
            problems.append(f"{where}: labels is not a list")
        evidence = row.get("unchanged_physics")
        if evidence is None:
            if row.get("enabled") != "absent" and not str(row.get("unchanged_physics_gap") or ""):
                problems.append(f"{where}: null unchanged_physics without its reason")
        elif evidence.get("kind") not in EVIDENCE_KINDS or not evidence.get("tests"):
            problems.append(f"{where}: unchanged_physics without a kind or a test")
        # Ruling 8: a `library-only` row names the tests that fail when an offered policy or a
        # `MODEL_BUILDERS` unit reaches it.
        if row.get("enabled") == "library-only" and not row.get("reachability_tests"):
            problems.append(f"{where}: library-only without reachability_tests")
    for entry in inventory["not_an_edge"]:
        if not str(entry.get("reason") or "").strip():
            problems.append(f"not_an_edge {entry.get('label')}: no reason")
    return problems


def cited_nodes(inventory: Mapping[str, Any]) -> list[str]:
    nodes: list[str] = []
    for row in inventory["rows"]:
        nodes += row["failure_tests"]
        nodes += row.get("reachability_tests") or []
        if row["unchanged_physics"] is not None:
            nodes += row["unchanged_physics"]["tests"]
    return sorted(set(nodes))


# -- the tests ------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def inventory() -> dict[str, Any]:
    return load()


@pytest.fixture(scope="module")
def emitted() -> set[str]:
    return code_labels()


def test_the_inventory_has_spec_5_6s_form(inventory: dict[str, Any]) -> None:
    assert check_form(inventory) == []
    rows = {row["id"]: row for row in inventory["rows"]}
    # Spec §5.6's seed fixes these two.
    assert rows["E12"]["enabled"] == "policy-only"
    assert rows["E13"]["enabled"] == "absent" and rows["E13"]["labels"] == []


def test_the_scan_reads_every_label_source(emitted: set[str]) -> None:
    """Each source the inventory's header names contributes, and nothing unreadable was met."""
    prefixes = {label.split(":", 1)[0] for label in emitted}
    assert prefixes == {
        "eo_core",
        "eo_recovery",
        "eo_recovery_unsupported",
        "opening_source",
        "decision",
        "ph_route",
        "projection_judged_at",
        "projection_refused",
        "event",
        "fallback",
        "produced_by",
        "initializer_source",
        "route_fallback",
    }
    assert not [label for label in emitted if "<unreadable" in label]


def test_a33_the_bijection_holds(inventory: dict[str, Any], emitted: set[str]) -> None:
    assert check_bijection(inventory, emitted) == []


@pytest.mark.parametrize(
    "change",
    [
        lambda inv, emitted: (inv, emitted | {"fallback:new-kernel"}),  # a label without a row
        lambda inv, emitted: (
            {**inv, "rows": [r for r in inv["rows"] if r["id"] != "E6"]},
            emitted,
        ),  # a row deleted while its labels are emitted
        lambda inv, emitted: (
            {**inv, "not_an_edge": [*inv["not_an_edge"], {"label": "eo_core:ptc", "reason": "x"}]},
            emitted,
        ),  # a label in two places
        lambda inv, emitted: (inv, emitted - {"decision:restart"}),  # a listed label not emitted
    ],
    ids=["unlisted", "row-deleted", "twice", "not-emitted"],
)
def test_a33_a_broken_bijection_is_caught(
    inventory: dict[str, Any], emitted: set[str], change: Any
) -> None:
    mutated, labels = change(copy.deepcopy(inventory), set(emitted))
    assert check_bijection(mutated, labels) != []


def test_a33_the_scan_finds_a_new_producer(tmp_path: Path) -> None:
    """A new `restart` producer, `_KernelAnswer` record or reasoned `Route` in a module is a new
    label; a `Route` without a reason is none."""
    source = (
        "def f(trace, b, why):\n"
        "    trace.record(kind='restart')\n"
        "    Route('revision_eo', b)\n"
        "    Route('revision_eo', b, None)\n"
        "    Route('tear', b, reason=why)\n"
        "    return _KernelAnswer('LIQUID', {}, 'ph-new' if trace else '')\n"
    )
    scan = _Scan("openflowsheet.somewhere")
    scan.visit(ast.parse(source))
    assert scan.labels == {
        "event:restart@openflowsheet.somewhere.f",
        "fallback:ph-new",
        "route_fallback:tear",
    }


@pytest.mark.parametrize(
    ("module", "source"),
    [
        (
            "openflowsheet.orchestrator.somewhere",
            "def f(trace):\n    kind = 'restart'\n    _emit(trace, kind=kind)\n",
        ),
        (
            "openflowsheet.application.somewhere",
            "def f(trace):\n    k = 'restart'\n    trace.record(kind=k)\n",
        ),
    ],
    ids=["local-kind-to-an-orchestrator-helper", "record-in-an-application-module"],
)
def test_a33_the_scan_fails_closed_on_an_unreadable_kind(module: str, source: str) -> None:
    """T08 description review, Ruling 3 (S6): a kind passed through a local is a label no row
    holds, under the directory clause (any `kind=` in `orchestrator/`, `numerics/`, `verify/`)
    and under the `.record(kind=…)` clause (every module). A kind forwarded from the enclosing
    function's own parameter is read at its call sites instead, and is not flagged."""
    scan = _Scan(module)
    scan.visit(ast.parse(source))
    assert scan.labels == {f"event:<unreadable at {module}.f>"}
    forwarded = _Scan(module)
    forwarded.visit(ast.parse("def f(trace, kind):\n    trace.record(kind=kind)\n"))
    assert forwarded.labels == set()
    elsewhere = _Scan("openflowsheet.application.somewhere")
    elsewhere.visit(ast.parse(source.replace("trace.record(", "_emit(trace, ")))
    assert elsewhere.labels == set()


@pytest.mark.parametrize("row_id", ROW_IDS)
def test_a33_an_enabled_row_carries_its_evidence(inventory: dict[str, Any], row_id: str) -> None:
    """Spec §9, T08.A33 (as amended by T08 review 2, Ruling 6): every `default`, `policy-only` or
    `library-only` row has a direct injected-failure test and evidence of unchanged
    `model_version`, `constants_sha256` and specifications, and every `library-only` row its
    unreachability tests (which `test_a33_the_cited_nodes_exist_and_pass` runs). A row whose
    evidence is null fails here, and stays failed."""
    (row,) = [row for row in inventory["rows"] if row["id"] == row_id]
    if row["enabled"] == "absent":
        assert row["labels"] == [] and row["failure_tests"] == []
        return
    assert row["failure_tests"], f"{row_id}: no direct injected-failure test"
    assert row["unchanged_physics"] is not None, (
        f"{row_id}: no unchanged-physics evidence — {row['unchanged_physics_gap']}"
    )
    if row["enabled"] == "library-only":
        assert row.get("reachability_tests"), f"{row_id}: no reachability test"


def test_a33_the_cited_nodes_exist_and_pass(inventory: dict[str, Any]) -> None:
    """Spec §9, T08.A33: the cited tests "pass" — collected, run, not skipped."""
    nodes = cited_nodes(inventory)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", *nodes],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output[-4000:]
    assert "SKIPPED" not in output and " skipped" not in output, output[-4000:]
    # An unparametrized node runs every parameter, so at least one pass per cited node.
    assert _passed(output) >= len(nodes), output[-4000:]


def _passed(output: str) -> int:
    for line in reversed(output.splitlines()):
        words = line.replace(",", " ").split()
        if "passed" in words:
            return int(words[words.index("passed") - 1])
    return 0
