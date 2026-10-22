"""C2: SPLIT-A01…A17 of `docs/derivations/C2-OpenIDAES-450-split-registration.md` §9.

Pure file checks over committed files. The draw is re-implemented here from the registration's
text (SPLIT-R02…R07) and compared with the generator's record; no assertion takes its expectation
from the generator alone. No test prints a held-out case id (SPLIT-R10): a failure names
`sha256(id)[:12]`.
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs/derivations/scripts/c2_openidaes450_split.py"
RECORD = ROOT / "benchmarks/m06/openidaes450/split.json"
COVERAGE = ROOT / "benchmarks/m06/openidaes450/coverage.json"
FACTS = ROOT / "benchmarks/m06/openidaes450/case_facts.json"
SAMPLE = ROOT / "benchmarks/m06/openidaes450/runs/w27-m07-83f825d/sample.json"
SEED = "OpenIDAES-450-split-v1/f39746770dd7f3f1ad96f75dbac8d29b4deef4f7"
TOKEN = re.compile(rb"[A-Za-z0-9_]+")


def _load_generator():
    spec = importlib.util.spec_from_file_location("c2_openidaes450_split", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gen = _load_generator()


def _tag(ident: str) -> str:
    return hashlib.sha256(ident.encode()).hexdigest()[:12]


def _rank(purpose: str, ident: str) -> str:
    return hashlib.sha256(f"{SEED}\x00{purpose}\x00{ident}".encode()).hexdigest()


def _independent_draw(*, purpose="case", alternate=True, force=True):
    """SPLIT-R02…R06 written from the registration text, sharing no code with the generator."""
    rows = json.loads(COVERAGE.read_bytes())["rows"]
    sample = json.loads(SAMPLE.read_bytes())
    named = set(gen.NAMED_EXPOSED)
    exposed = set(sample["cases"]) | set(sample["canaries"]) | named
    frame = [r for r in rows if r["class"] != "ARTIFACT_INCOMPLETE"]
    groups: dict[tuple[str, str], list[str]] = {}
    for r in frame:
        groups.setdefault((r["family"], r["class"]), []).append(r["case_id"])
    odd = [k for k in groups if len(groups[k]) % 2 == 1]
    odd.sort(key=lambda k: _rank("stratum", k[0] + "|" + k[1]))
    held: set[str] = set()
    for k, ids in groups.items():
        t = len(ids) // 2
        if alternate and k in odd and odd.index(k) % 2 == 0:
            t += 1
        candidates = [c for c in ids if not (force and c in exposed)]
        candidates.sort(key=lambda c: _rank(purpose, c))
        held.update(candidates[: min(t, len(candidates))])
    return {r["case_id"] for r in frame}, exposed, held


def _commit(ids) -> str:
    return hashlib.sha256("".join(f"{i}\n" for i in sorted(ids)).encode()).hexdigest()


@pytest.fixture(scope="module")
def record():
    return json.loads(RECORD.read_bytes())


@pytest.fixture(scope="module")
def drawn():
    return _independent_draw()


def test_a01_check_is_byte_identical():
    rec, _ = gen.build(gen.read_inputs())
    assert gen.render(rec) == RECORD.read_bytes()


def test_a02_a_changed_input_is_refused():
    raw = gen.read_inputs()
    raw["coverage"] = raw["coverage"][:-2] + b" \n"
    with pytest.raises(gen.SplitRefusedError) as exc:
        gen.build(raw)
    assert exc.value.rule == "SPLIT-R01/R12"


def test_a03_partition_and_sizes(record, drawn):
    frame, _, held = drawn
    rows = json.loads(COVERAGE.read_bytes())["rows"]
    every = {r["case_id"] for r in rows}
    dev = set(record["development"]["case_ids"])
    excluded = set(record["frame"]["excluded"])
    assert len(every) == 450 and excluded == {"watertap_metab"}
    assert not (dev & held) and not (dev & excluded) and not (held & excluded)
    assert dev | held | excluded == every and dev | held == frame
    t = record["totals"]
    assert (len(dev), len(held), len(excluded)) == (225, 224, 1)
    assert (t["development"], t["held_out"], t["excluded"], t["frame"]) == (225, 224, 1, 449)


def test_a04_exposed_cases_are_development(record):
    sample = json.loads(SAMPLE.read_bytes())
    dev = set(record["development"]["case_ids"])
    sources = {e["case_id"]: e["source"] for e in record["exposed"]["cases"]}
    assert len(sample["cases"]) == 45 and len(sample["canaries"]) == 3
    assert len(gen.NAMED_EXPOSED) == 17
    assert set(sources) == set(sample["cases"]) | set(sample["canaries"]) | set(gen.NAMED_EXPOSED)
    assert len(sources) == record["exposed"]["count"] == 65
    assert set(sources) <= dev
    assert Counter(s.split(":")[0] for s in sources.values()) == Counter(
        {"w27_sample": 45, "w27_canary": 3, "named": 17}
    )


def test_a05_independent_draw_reproduces_the_record(record, drawn):
    frame, _, held = drawn
    assert sorted(frame - held) == record["development"]["case_ids"]
    assert _commit(held) == record["held_out"]["commitment"]
    assert len(held) == record["held_out"]["count"]


def test_a06_stratum_identities_and_balance(record):
    strata = record["strata"]
    odd = sorted(s["odd_rank"] for s in strata if s["n"] % 2)
    assert odd == list(range(len(odd)))
    assert all(s["odd_rank"] is None for s in strata if not s["n"] % 2)
    for s in strata:
        up = s["odd_rank"] is not None and s["odd_rank"] % 2 == 0
        assert s["target"] == s["n"] // 2 + up
        assert s["held_out"] == min(s["target"], s["n"] - s["exposed"])
        assert s["development"] == s["n"] - s["held_out"]
        assert s["shortfall"] == s["target"] - s["held_out"]
        if s["shortfall"] == 0:
            assert abs(s["n"] - 2 * s["held_out"]) <= 1
    total_target = sum(s["target"] for s in strata)
    assert abs(2 * total_target - record["totals"]["frame"]) <= 1
    short = [(s["family"], s["class"], s["n"], s["exposed"], s["shortfall"]) for s in strata]
    assert [s for s in short if s[4]] == [("pareto", "COMPONENT_UNAVAILABLE", 1, 1, 1)]
    assert record["totals"]["shortfall"] == 1 and total_target == 225


def test_a07_held_out_ids_match_the_commitment(record, drawn):
    ids = gen.held_out_ids()
    assert set(ids) == drawn[2]
    assert _commit(ids) == record["held_out"]["commitment"]


def test_a08_seed_and_rank_bytes(record):
    assert record["seed_text"] == SEED == gen.SEED_TEXT
    expected = hashlib.sha256(SEED.encode() + b"\x00case\x00x").hexdigest()
    assert gen.rank("case", "x") == expected != gen.rank("order", "x")


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    return [p for p in out.stdout.decode().split("\0") if p]


def test_a09_no_held_out_id_outside_the_allowlist(drawn):
    held = {c.encode() for c in drawn[2]}
    entries = json.loads(RECORD.read_bytes())["contaminated"]
    tolerated = {(e["sha256"], where) for e in entries for where in e["where"]}
    allow = set(gen.ALL_CASE_FILES)
    assert all((ROOT / p).is_file() for p in allow)
    hits: list[str] = []
    scanned = 0
    for path in _tracked():
        if path in allow or gen.HELDOUT_SEGMENT in Path(path).parts[:-1]:
            continue
        full = ROOT / path
        if not full.is_file():
            continue
        data = full.read_bytes()
        if path.endswith(".gz"):
            data = gzip.decompress(data)
        scanned += 1
        for token in set(TOKEN.findall(data)) & held:
            if (hashlib.sha256(token).hexdigest(), path) not in tolerated:
                hits.append(f"{path}: held-out case {_tag(token.decode())}")
    assert scanned > 1000
    assert not hits, "\n".join(sorted(hits))


def test_a10_the_record_names_no_held_out_case_and_no_gap_field(drawn):
    held = drawn[2]
    text = RECORD.read_bytes()
    assert not (set(t.decode() for t in TOKEN.findall(text)) & held)
    keys: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            keys.update(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(json.loads(text))
    assert not keys & {"reasons", "units", "components", "packages"}


def test_a11_strata_are_the_committed_w27_r02_classes(record):
    rows = json.loads(COVERAGE.read_bytes())["rows"]
    counts = Counter((r["family"], r["class"]) for r in rows if r["class"] != "ARTIFACT_INCOMPLETE")
    assert record["strata_basis"] == "W27-R02"
    assert {(s["family"], s["class"]): s["n"] for s in record["strata"]} == dict(counts)
    assert len(record["strata"]) == 17


def test_a12_f1_awaits_facts_and_refuses_once_they_exist(record):
    facts = json.loads(FACTS.read_bytes())
    assert record["f1"]["status"] == "awaiting_facts"
    assert not any("topology_units" in c for c in facts["cases"])
    facts["cases"][0]["topology_units"] = []
    raw = gen.read_inputs()
    raw["case_facts"] = json.dumps(facts).encode()
    with pytest.raises(gen.SplitRefusedError) as exc:
        gen.build(raw, pins={})
    assert exc.value.rule == "SPLIT-R13"


def test_a13_f1_kind_level_states():
    by_id = {c["case_id"]: c for c in json.loads(FACTS.read_bytes())["cases"]}

    def added(case_id):
        case = by_id[case_id]
        assert case["unit_source"] == "units.json"
        covered = {u.get("topology_kind") for u in case["units"]}
        covered |= {u["key"].removeprefix("idaes:") for u in case["units"]}
        return set(case["topology_kinds"]) - {"Feed", "Product"} - covered

    assert added("blind_synthesized_hda_flash") == set()
    assert added("official_idaes_skeleton_pervaporation") == {"SkeletonUnitModel"}
    row = next(
        r
        for r in json.loads(COVERAGE.read_bytes())["rows"]
        if r["case_id"] == "blind_synthesized_hda_flash"
    )
    units = [q["subject"] for q in row["reasons"] if q["kind"] == "UNIT_UNAVAILABLE"]
    assert row["class"] == "UNIT_UNAVAILABLE" and units == ["PressureChanger"]


def test_a14_rule_mutants_change_the_held_out_set(record):
    registered = record["held_out"]["commitment"]
    for mutant in (
        _independent_draw(purpose="order"),
        _independent_draw(alternate=False),
        _independent_draw(force=False),
    ):
        assert _commit(mutant[2]) != registered


@pytest.mark.parametrize(
    ("change", "rule"),
    [
        ("named_not_a_case", "SPLIT-R14.3"),
        ("named_outside_frame", "SPLIT-R14.3"),
        ("sample_excluded", "SPLIT-R14.4"),
        ("case_sets_differ", "SPLIT-R14.2"),
    ],
)
def test_a15_inconsistent_inputs_are_refused(change, rule):
    raw = gen.read_inputs()
    named = dict(gen.NAMED_EXPOSED)
    if change == "named_not_a_case":
        named["no_such_case"] = "x"
    elif change == "named_outside_frame":
        named["watertap_metab"] = "x"
    elif change == "sample_excluded":
        sample = json.loads(raw["sample"])
        sample["excluded"] = []
        raw["sample"] = json.dumps(sample).encode()
    else:
        facts = json.loads(raw["case_facts"])
        facts["cases"] = facts["cases"][1:]
        raw["case_facts"] = json.dumps(facts).encode()
    with pytest.raises(gen.SplitRefusedError) as exc:
        gen.build(raw, pins={}, named_exposed=named)
    assert exc.value.rule == rule


def test_a16_contamination_is_recorded_and_held_out(record, drawn):
    entries = record["contaminated"]
    held = {hashlib.sha256(c.encode()).hexdigest() for c in drawn[2]}
    assert [e["sha256"][:12] for e in entries] == ["c87ac13adc32"]
    assert all(e["sha256"] in held and e["where"] and e["date"] and e["cause"] for e in entries)
    t = record["totals"]
    assert (t["contaminated"], t["held_out_headline"]) == (1, t["held_out"] - 1) == (1, 223)
    assert len(gen.CONTAMINATED) == 1


def test_a17_generator_output_names_no_held_out_case(drawn):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        assert gen.main(["--check"]) == 0
    text = (out.getvalue() + err.getvalue()).encode()
    assert "byte-identical" in out.getvalue()
    assert not (set(t.decode() for t in TOKEN.findall(text)) & drawn[2])


# Amendment 1 (2026-10-22, R-555): a re-taken coverage.json is read at its pinned content.
EXPOSED_EXAMPLE = "blind_synthesized_hda_flash"  # exposed (SPLIT-R04 c); prose names only these


@pytest.fixture(scope="module")
def pinned_coverage():
    raw = gen.git_blob(ROOT, gen.PINNED_BLOBS["coverage"])
    assert raw is not None, "Amendment 1 needs the repository's history (a full clone)"
    return raw


def _triples(raw: bytes):
    return sorted((r["case_id"], r["family"], r["class"]) for r in json.loads(raw)["rows"])


def _working(pinned: bytes, edit) -> dict[str, bytes]:
    cov = json.loads(pinned)
    edit(cov)
    raw = {name: (ROOT / path).read_bytes() for name, (path, _) in gen.INPUTS.items()}
    raw["coverage"] = json.dumps(cov, indent=2).encode()
    return raw


def _retake(cov):
    cov["snapshot"]["git_commit"] = "0" * 40
    cov["snapshot_sha256"] = "f" * 64


def _no_fetch(root, oid):
    raise AssertionError("an unmoved input must not be read from history")


def test_a18_a_retaken_coverage_is_read_at_its_pinned_content(record, pinned_coverage):
    pin = gen.INPUTS["coverage"][1]
    assert (
        hashlib.sha256(pinned_coverage).hexdigest() == pin == record["inputs"]["coverage"]["sha256"]
    )
    # the working copy's read fields equal the pinned ones (whatever else a re-take moved)
    assert len(_triples(pinned_coverage)) == 450
    assert _triples(COVERAGE.read_bytes()) == _triples(pinned_coverage)

    # a version re-take: only the snapshot fields move; the draw reads the pinned bytes
    working = _working(pinned_coverage, _retake)
    assert hashlib.sha256(working["coverage"]).hexdigest() != pin
    raw = gen.pinned_inputs(working)
    assert raw["coverage"] == pinned_coverage
    rec, _ = gen.build(raw)
    assert gen.render(rec) == RECORD.read_bytes()
    assert (
        rec["coverage_snapshot"]["git_commit"]
        == json.loads(pinned_coverage)["snapshot"]["git_commit"]
    )
    # an unmoved working copy is used as is: no history is needed
    unmoved = dict(working, coverage=pinned_coverage)
    assert gen.pinned_inputs(unmoved, fetch=_no_fetch) == unmoved


def _set(case_id, field, value):
    def edit(cov):
        next(r for r in cov["rows"] if r["case_id"] == case_id)[field] = value

    return edit


def _drop(case_id):
    def edit(cov):
        cov["rows"] = [r for r in cov["rows"] if r["case_id"] != case_id]

    return edit


def _add(cov):
    cov["rows"].append(
        {"case_id": "a19_added_case", "family": "idaes", "class": "UNIT_UNAVAILABLE"}
    )


@pytest.mark.parametrize(
    ("edit", "counts"),
    [
        (_set(EXPOSED_EXAMPLE, "class", "COMPONENT_UNAVAILABLE"), "removed 0, added 0, changed 1"),
        (_set(EXPOSED_EXAMPLE, "family", "watertap"), "removed 0, added 0, changed 1"),
        (_drop(EXPOSED_EXAMPLE), "removed 1, added 0, changed 0"),
        (_add, "removed 0, added 1, changed 0"),
    ],
    ids=["class", "family", "removed", "added"],
)
def test_a19_read_field_drift_is_refused(pinned_coverage, edit, counts):
    working = _working(pinned_coverage, edit)
    with pytest.raises(gen.SplitRefusedError) as exc:
        gen.pinned_inputs(working)
    assert exc.value.rule == "SPLIT-R12/A1"
    assert f"({counts}, duplicate rows 0)" in str(exc.value)
    ids = {r[0] for r in _triples(pinned_coverage)} | {"a19_added_case"}
    assert not ({t.decode() for t in TOKEN.findall(str(exc.value).encode())} & ids)


def test_a19_missing_history_is_an_explicit_refusal(pinned_coverage, tmp_path):
    working = _working(pinned_coverage, _retake)
    assert gen.git_blob(ROOT, "0" * 40) is None
    assert gen.git_blob(tmp_path, gen.PINNED_BLOBS["coverage"]) is None
    with pytest.raises(gen.SplitRefusedError) as exc:
        gen.pinned_inputs(working, root=tmp_path)
    assert exc.value.rule == "SPLIT-R01/A1"
    with pytest.raises(gen.SplitRefusedError) as exc:
        gen.pinned_inputs(working, fetch=lambda root, oid: pinned_coverage[:-2] + b" \n")
    assert exc.value.rule == "SPLIT-R01/R12"
