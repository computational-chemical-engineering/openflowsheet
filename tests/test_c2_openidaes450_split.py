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


def _blob(oid: str) -> bytes:
    out = subprocess.run(
        ["git", "cat-file", "blob", oid], cwd=ROOT, capture_output=True, check=False
    )
    assert out.returncode == 0, f"git blob {oid} is not readable here; this needs the history"
    return out.stdout


RECORD_BEFORE_BLOB = "17632cea3ac9e3ebe23076bade2fc6bf9c29948c"  # split.json before Amendment 2


@pytest.fixture(scope="module")
def record_before():
    raw = _blob(RECORD_BEFORE_BLOB)
    assert hashlib.sha256(raw).hexdigest() == (
        "ee940a7ee2c6a2128f12fdc25c4e9906ff66607a5ce4e0bb975c00a935adf6cd"
    )
    return json.loads(raw)


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


def test_a12_f1_facts_committed_and_item_8_still_refuses(record, record_before):
    facts = json.loads(FACTS.read_bytes())
    assert record["f1"]["status"] == "facts_committed"
    assert not any("topology_units" in c for c in facts["cases"])
    facts["cases"][0]["topology_units"] = []
    raw = gen.read_inputs()
    raw["case_facts"] = json.dumps(facts).encode()
    del raw[gen.F1_KEY]  # item 8 must refuse before item 13 sees the absent facts file
    with pytest.raises(gen.SplitRefusedError) as exc:
        gen.build(raw, pins={})
    assert exc.value.rule == "SPLIT-R13"
    assert set(record) == set(record_before)
    assert {k: v for k, v in record.items() if k != "f1"} == {
        k: v for k, v in record_before.items() if k != "f1"
    }
    assert record["f1"] != record_before["f1"]


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
    raw[gen.F1_KEY] = (ROOT / gen.F1_FACTS[0]).read_bytes()  # Amendment 2's item 13 reads it
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


# Amendment 2 (2026-10-23, R-581/R-582): case_facts-v2.json, its writer and its admission.
FACTS_V2 = ROOT / "benchmarks/m06/openidaes450/case_facts-v2.json"
WRITER = ROOT / "docs/derivations/scripts/c2_openidaes450_facts_v2.py"
FACTS_V2_SHA256 = "4f5c5a65fe1b310e04b7e311464e4d87ba90ed4bfa7a90c240cde397cd0114ef"
WS1_BLOB = "7b0686e195ae6685fa1b0738a3dbbd674d21cc02"  # case_facts-v2.json at 7b5c07f
WS1_SHA256 = "57d43acbee1c0952e43c0a5410783fd0dba8c1a4b4e38a74e31f8b57cbb33494"
TAIL_SHA256 = "fb0e0fe31c6cd42d294e916ff87fd0038af03406d7ff6474dcd3930a5645724d"
FIRST_DEVELOPMENT = "blind_synthesized_anaerobic_digester_unit"
ARCHIVE_PRESENT = (
    ROOT / "evidence/M06/W27/artifacts/extracted/OpenIDAES-450-demo" / "cases"
).is_dir()


def _head(raw: bytes) -> dict:
    """The first line of a facts file (everything but the cases), closed and parsed."""
    return json.loads(raw.split(b"\n", 1)[0] + b"]}")


def _all_ids() -> set[str]:
    return {c["case_id"] for c in json.loads(FACTS.read_bytes())["cases"]}


def _refusal(raw_v2: bytes | None) -> gen.SplitRefusedError:
    raw = gen.read_inputs()
    raw.pop(gen.F1_KEY, None)
    if raw_v2 is not None:
        raw[gen.F1_KEY] = raw_v2
    with pytest.raises(gen.SplitRefusedError) as exc:
        gen.build(raw)
    return exc.value


def test_a20_facts_v2_is_pinned_and_is_ws1s_content(record):
    data = FACTS_V2.read_bytes()
    assert hashlib.sha256(data).hexdigest() == FACTS_V2_SHA256
    assert record["f1"]["facts"] == {
        "path": "benchmarks/m06/openidaes450/case_facts-v2.json",
        "schema": "openidaes450-case-facts-v2",
        "sha256": FACTS_V2_SHA256,
        "writer": "docs/derivations/scripts/c2_openidaes450_facts_v2.py",
    }
    old = _blob(WS1_BLOB)
    assert hashlib.sha256(old).hexdigest() == WS1_SHA256
    tail = data.split(b"\n", 1)[1]
    assert tail == old.split(b"\n", 1)[1]
    assert hashlib.sha256(tail).hexdigest() == TAIL_SHA256
    before, after = _head(old), _head(data)
    assert before["source"].pop("generator") == "docs/derivations/scripts/m06_w27_registration.py"
    assert (
        after["source"].pop("generator") == "docs/derivations/scripts/c2_openidaes450_facts_v2.py"
    )
    assert before == after
    flipped = bytearray(data)
    flipped[len(data) // 2] ^= 0x01
    assert _refusal(bytes(flipped)).rule == "SPLIT-R13/A2"
    assert _refusal(None).rule == "SPLIT-R13/A2"


def _a21_edit(n: int, doc: dict) -> None:
    i = next(k for k, c in enumerate(doc["cases"]) if c["case_id"] == FIRST_DEVELOPMENT)
    units = doc["cases"][i]["topology_units"]
    if n == 1:
        units[0]["kind"] = "A21Kind"
    elif n == 2:
        del doc["cases"][i]
    elif n == 3:
        units[0], units[1] = units[1], units[0]
    elif n == 4:
        units.append(dict(units[-1]))
    elif n == 5:
        doc["source"]["case_facts_v1_sha256"] = "0" * 64
    elif n == 6:
        doc["cases"][i]["x"] = 1
    else:
        units[0]["id"] = 7


@pytest.mark.parametrize(
    ("edit", "label"),
    [
        (1, "kind_sets"),
        (2, "case_ids"),
        (3, "unit_order"),
        (4, "unit_ids"),
        (5, "binding"),
        (6, "case_keys"),
        (7, "unit_form"),
    ],
)
def test_a21_each_identity_is_reached(record, edit, label):
    facts = json.loads(FACTS.read_bytes())
    doc = json.loads(FACTS_V2.read_bytes())
    assert record["development"]["case_ids"][0] == FIRST_DEVELOPMENT
    case = next(c for c in doc["cases"] if c["case_id"] == FIRST_DEVELOPMENT)
    assert len(case["topology_units"]) == 4
    assert "A21Kind" not in {u["kind"] for c in doc["cases"] for u in c["topology_units"]}
    gen.f1_identities(facts, doc)  # the committed pair passes
    _a21_edit(edit, doc)
    with pytest.raises(gen.SplitRefusedError) as exc:
        gen.f1_identities(facts, doc)
    assert exc.value.rule == "SPLIT-R13/A2"
    assert exc.value.label == label
    assert str(exc.value).startswith(f"SPLIT-R13/A2 {label}: ")
    assert not ({t.decode() for t in TOKEN.findall(str(exc.value).encode())} & _all_ids())


def test_a22_f1_unit_level_states(record):
    by_v1 = {c["case_id"]: c for c in json.loads(FACTS.read_bytes())["cases"]}
    doc = json.loads(FACTS_V2.read_bytes())
    by_v2 = {c["case_id"]: c for c in doc["cases"]}
    registered = {
        "blind_synthesized_hda_flash": {},
        "official_idaes_skeleton_pervaporation": {"topology:SkeletonUnitModel": ["pervap"]},
    }
    assert record["f1"]["unit_level_states"] == registered
    for case_id, groups in registered.items():
        kinds = sorted(k.removeprefix("topology:") for k in groups)
        assert kinds == record["f1"]["kind_level_states"][case_id]

    def groups_of(case_id):
        """§6 from the registration text, sharing no code with the generator."""
        v1 = by_v1[case_id]
        assert v1["unit_source"] == "units.json"
        covered = {u.get("topology_kind") for u in v1["units"]}
        covered |= {u["key"].removeprefix("idaes:") for u in v1["units"]}
        units = by_v2[case_id]["topology_units"]
        added = {u["kind"] for u in units} - {"Feed", "Product"} - covered
        return {f"topology:{k}": [u["id"] for u in units if u["kind"] == k] for k in added}

    assert {c: groups_of(c) for c in registered} == registered
    assert len(by_v2["official_idaes_skeleton_pervaporation"]["topology_units"]) == 6
    facts = json.loads(FACTS.read_bytes())
    for u in by_v2["official_idaes_skeleton_pervaporation"]["topology_units"]:
        if u["id"] == "pervap":
            u["id"] = "pervap2"
    gen.f1_identities(facts, doc)
    with pytest.raises(gen.SplitRefusedError) as exc:
        gen.f1_unit_level_states(facts, doc)
    assert exc.value.rule == "SPLIT-R13"


TWELVE = (
    "benchmarks/m06/openidaes450/access_report.json",
    "benchmarks/m06/openidaes450/case_facts.json",
    "benchmarks/m06/openidaes450/coverage.json",
    "benchmarks/m06/openidaes450/dry_illustration.json",
    "benchmarks/m06/openidaes450/registration.json",
    "benchmarks/m06/openidaes450/runs/w27-m07-83f825d/coverage.json",
    *(
        f"evidence/M07/{c}/rc/step17/{name}"
        for c in (
            "c899c85ab43fb114cd85c69baf12e692b75a8eab",
            "ce993651ce37c1343e771b276160bd6623e43500",
        )
        for name in ("at-c.json.gz", "at-cw.json.gz", "coverage-at-C.json.gz")
    ),
)


def test_a23_one_exact_path_admits_the_facts_file(record, drawn):
    entries = gen.ALL_CASE_FILES
    assert len(TWELVE) == 12
    assert set(entries) == set(TWELVE) | {"benchmarks/m06/openidaes450/case_facts-v2.json"}
    assert len(entries) == len(set(entries)) == 13
    tracked = set(_tracked())
    for entry in entries:
        assert not any(ch in entry for ch in "*?[") and not entry.endswith("/")
        assert entry in tracked and (ROOT / entry).is_file() and not (ROOT / entry).is_symlink()
    held = {c.encode() for c in drawn[2]}
    found = set(TOKEN.findall(FACTS_V2.read_bytes())) & held
    assert len(found) == record["held_out"]["count"] == 224


def test_a24_w27_preflight_pins_hold():
    from benchmarks.m06.w27 import preflight

    pins = preflight.REGISTERED_SHA256
    assert len(pins) == 3
    for path, sha in pins.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha, str(path)


def _writer(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", str(WRITER), *args], cwd=ROOT, capture_output=True, text=True
    )


@pytest.mark.skipif(not ARCHIVE_PRESENT, reason="pinned archive absent")
def test_a25a_writer_reproduces_the_committed_file_from_the_archive():
    out = _writer("--check")
    assert out.returncode == 0, out.stdout + out.stderr
    assert f"sha256 {FACTS_V2_SHA256}" in out.stdout


def test_a25b_writer_without_archive_is_not_checked(tmp_path):
    before = hashlib.sha256(FACTS_V2.read_bytes()).hexdigest()
    out = _writer("--check", "--archive", str(tmp_path))
    assert out.returncode == 2
    assert out.stdout.startswith("NOT CHECKED:")
    assert hashlib.sha256(FACTS_V2.read_bytes()).hexdigest() == before == FACTS_V2_SHA256


def test_a25c_writer_regression_on_a_synthetic_archive(tmp_path):
    """A regression of the writer's canonical form and self-claims, not a validation."""
    doc = json.loads(FACTS_V2.read_bytes())

    def build_archive(root: Path, docs: dict) -> None:
        for case in docs["cases"]:
            d = root / "cases" / case["case_id"]
            d.mkdir(parents=True)
            (d / "topology.json").write_text(json.dumps({"units": case["topology_units"]}))

    good = tmp_path / "good"
    build_archive(good, doc)
    out = _writer("--check", "--archive", str(good))
    assert out.returncode == 0, out.stdout + out.stderr
    next(c for c in doc["cases"] if c["case_id"] == FIRST_DEVELOPMENT)["topology_units"][0][
        "kind"
    ] = "A25Kind"
    bad = tmp_path / "bad"
    build_archive(bad, doc)
    out = _writer("--check", "--archive", str(bad))
    assert out.returncode == 2
    text = (out.stdout + out.stderr).encode()
    assert not ({t.decode() for t in TOKEN.findall(text)} & _all_ids())
