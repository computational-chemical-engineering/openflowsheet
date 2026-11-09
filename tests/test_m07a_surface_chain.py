"""M07a.A37: the alpha's step 8, the surface chain of V02 alpha release spec §5.3 (MR-1, MR-6).

`scripts/m07a_rc.py` composes the chain; this module runs it on the served tool list (items 1–4)
with §5.3's negative controls (i)–(iv), and holds the script's registered values equal to their
sources. G16-b, the step's other half, runs in the RC job only (40 reference runs).

On `main` the chain has three links: c_3 (R-295, M04's `surrogate_study` job kind) was registered at
the alpha's merge (R-457). MSG adds c_4 (R-934, ADR 0058's `RunResult.failure`; MSG-G10), X02
c_5 (R-950, ADR 0070's `solve_body.warm_start`), OPT c_6 (R-960, ADR 0071's `optimize` job
operation, `validate`'s `optimization` member and the two description texts it changed; OPT D-51,
D-59, D-87), and ST c_7 (R-1000, ADR 0068's `get_stream_table` tool; ST G12). Every control
first asserts that the unmodified served list passes, so no control passes merely because the
chain already fails. The released 0.2.0a1's step 8 (two links) is
read from its committed record at `C_α²`, not re-run (`test_m07a_a37_the_released_step_8_record`).
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from collections.abc import Iterator
from typing import Any

import pytest
import yaml
from conftest import PUBLIC_ROOT, REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m07a_rc  # noqa: E402
import t08_rc  # noqa: E402

M02_MANIFEST = (
    REPO_ROOT / "evidence" / "M02" / "ba90619c62329165a21731fdff01ebc9c7203287" / "manifest.json"
)
REVIEW = "src/openflowsheet/application/bindings/descriptions/REVIEW.json"
#: `C_α²`, the candidate 0.2.0a1 was tagged from (spec Amendment 3 §19.1, R-370).
C_ALPHA_2 = "cc73219a77f6a54579c8acb151ed6fae228c8a4c"
ALPHA_SURFACE = (
    REPO_ROOT / "evidence" / "M07a" / C_ALPHA_2 / "rc" / "surface" / "rc-alpha-surface.json"
)
REGISTER = REPO_ROOT / "docs" / "decision-register.md"
L0, L1, L2, L3, L4, L5, L6, L7 = m07a_rc.LINKS


@pytest.fixture
def served() -> Iterator[list[dict[str, Any]]]:
    pytest.importorskip("mcp")
    yield m07a_rc.served_tools()


def assert_the_unmodified_list_passes(served: list[dict[str, Any]]) -> None:
    """A control's precondition: the chain holds on the list before the control modifies it."""
    assert m07a_rc.first_failure(m07a_rc.chain(copy.deepcopy(served))) is None


def test_m07a_a37_the_chain_holds_on_the_served_list(served: list[dict[str, Any]]) -> None:
    rows = m07a_rc.chain(served)
    assert [(r["item"], r["link"]) for r in rows] == [
        (1, "c_8"),
        (2, "c_8"),
        (2, "c_7"),
        (2, "c_6"),
        (2, "c_5"),
        (2, "c_4"),
        (2, "c_3"),
        (2, "c_2"),
        (2, "c_1"),
        (3, None),
    ]
    assert m07a_rc.first_failure(rows) is None, rows
    assert rows[-2]["found"] == t08_rc.R133_DESCRIPTIONS_SHA256
    texts = m07a_rc.description_texts()
    assert m07a_rc.description_problems(m07a_rc.texts_before_links(texts)) == []
    assert m07a_rc.served_texts_are_the_files(served, texts)


def test_m07a_a37_item_2_two_separate_strips_do_not_satisfy_the_chain(
    served: list[dict[str, Any]],
) -> None:
    """s_1 applied to the served list itself, not to s_2's output, does not give `D_0`; s_2 applied
    to the served list itself, not to s_3's output, does not give `D_1` (R-457, F2)."""
    assert m07a_rc.digest(m07a_rc.strip_a3_2(served)) != m07a_rc.D_0
    assert m07a_rc.digest(m07a_rc.strip_m02(served)) != L0.digest


def test_m07a_a37_control_i_a_member_added_to_another_tools_output_schema(
    served: list[dict[str, Any]],
) -> None:
    assert_the_unmodified_list_passes(served)
    (tool,) = [t for t in served if t["name"] == "get_project"]
    tool["outputSchema"]["properties"]["probe"] = {"type": "string"}
    rows = m07a_rc.chain(served)
    assert m07a_rc.first_failure(rows) == "c_8 (R-1010)"
    assert [r["pass"] for r in rows[:7]] == [False] * 7


def one_member_too_many(strip: Any) -> Any:
    """`strip`, followed by deleting `get_project.outputSchema.properties.head`."""

    def too_many(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        stripped = strip(tools)
        (tool,) = [t for t in stripped if t["name"] == "get_project"]
        del tool["outputSchema"]["properties"]["head"]
        return stripped

    return too_many


def test_m07a_a37_control_ii_s_m_strips_one_member_too_many(
    served: list[dict[str, Any]],
) -> None:
    assert_the_unmodified_list_passes(served)
    too_many = one_member_too_many(m07a_rc.strip_m04)
    links = (L0, L1, m07a_rc.Link("c_3", "R-295", too_many, L2.digest), L3, L4, L5, L6, L7)
    rows = m07a_rc.chain(served, links)
    assert all(row["pass"] for row in rows[:6])
    assert m07a_rc.first_failure(rows) == "c_3 (R-295)"


def test_m07a_a37_control_ii_prime_an_inner_link_strips_one_member_too_many(
    served: list[dict[str, Any]],
) -> None:
    assert_the_unmodified_list_passes(served)
    too_many = one_member_too_many(m07a_rc.strip_m02)
    links = (L0, m07a_rc.Link("c_2", "R-234", too_many, L1.digest), L2, L3, L4, L5, L6, L7)
    rows = m07a_rc.chain(served, links)
    assert all(row["pass"] for row in rows[:7])
    assert m07a_rc.first_failure(rows) == "c_2 (R-234)"


def test_m07a_a37_control_iii_one_byte_of_another_description_changed() -> None:
    texts = m07a_rc.description_texts()
    texts["list_jobs"] = texts["list_jobs"].replace(".", ",", 1)
    problems = m07a_rc.description_problems(m07a_rc.texts_before_links(texts))
    assert len(problems) == 1
    assert problems[0].startswith("list_jobs.md: ")


def test_m07a_a37_control_iv_elements_left_in_place(served: list[dict[str, Any]]) -> None:
    assert_the_unmodified_list_passes(served)
    links = (
        m07a_rc.Link("c_1", "R-192", lambda tools: tools, L0.digest),
        *(L1, L2, L3, L4, L5, L6, L7),
    )
    rows = m07a_rc.chain(served, links)
    assert [r["pass"] for r in rows[:8]] == [True] * 8
    assert m07a_rc.first_failure(rows) == "c_1 (R-192)"


def test_m07a_a37_registered_values_equal_their_sources() -> None:
    import test_t08_w2_surface_digest as surface

    assert m07a_rc.LINKS[0].digest == surface.M06_A3_SERVED_SHA256
    assert m07a_rc.V17_C2_FILE_SHA256 == surface.V17_C2_FILE_SHA256
    assert m07a_rc.CHANGED == surface.CHANGED
    assert m07a_rc.D_0 == surface.T08_DESCRIPTIONS_SHA256
    manifest = json.loads(M02_MANIFEST.read_text(encoding="utf-8"))
    measured = manifest["checks"][0]["value"]["mcp_tool_list"]
    assert m07a_rc.LINKS[1].digest == measured["served_sha256"]
    assert measured["without_m02_sha256"] == m07a_rc.LINKS[0].digest
    released = json.loads(
        subprocess.run(
            ["git", "show", f"{PUBLIC_ROOT}:{REVIEW}"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        ).stdout
    )
    for name, sha256 in m07a_rc.R133_FILE_SHA256.items():
        assert released["operations"][name]["sha256"] == sha256


def test_m07a_a37_link_c_3_is_r_295s_strip_and_r_457s_digest(
    served: list[dict[str, Any]],
) -> None:
    from m04_schema_support import without_m04

    assert m07a_rc.strip_m04(served) == without_m04(copy.deepcopy(served))
    register = REGISTER.read_text(encoding="utf-8")
    start = register.index("\n## R-457 ")
    entry = register[start : register.index("\n## R-", start + 1)]
    assert L2.digest in entry


def test_m07a_a37_the_released_step_8_record() -> None:
    """0.2.0a1's step 8 at `C_α²`, read rather than re-run: two links, passed (R-457, AM-18)."""
    record = json.loads(ALPHA_SURFACE.read_text(encoding="utf-8"))
    assert record["passed"] is True
    assert record["first_failure"] is None
    assert [row["link"] for row in record["chain"]] == ["c_2", "c_2", "c_1", None]
    assert record["chain"][0]["found"] == L1.digest
    assert record["chain"][-1]["expected"] == m07a_rc.V17_C2_DIGEST


def test_m07a_a37_ci_dispatch_input_rc_alpha_selects_the_alphas_step_8() -> None:
    """The `rc_alpha` input runs steps 1–10 with the alpha's step 8; `rc` runs T08's, as before."""
    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert inputs["rc_alpha"]["type"] == "boolean"
    assert inputs["rc_alpha"]["default"] is False
    jobs = workflow["jobs"]
    for job in ("dist", "bundle-set", "rc-steps", "rc-ensemble"):
        assert "inputs.rc_alpha" in jobs[job]["if"], job
    assert jobs["clean-install"]["needs"] == "dist"
    assert jobs["bundle-replay"]["needs"] == "bundle-set"
    steps = {step.get("name"): step for step in jobs["rc-steps"]["steps"]}
    t08 = [s for s in steps.values() if "t08_rc.py surface" in s.get("run", "")]
    alpha = [s for s in steps.values() if "m07a_rc.py surface" in s.get("run", "")]
    assert len(t08) == len(alpha) == 1
    assert t08[0]["if"] == "always() && inputs.rc"
    assert alpha[0]["if"] == "always() && inputs.rc_alpha"


def test_msg_g10_link_c_4_is_msgs_strip_and_digest(served: list[dict[str, Any]]) -> None:
    """c_4 (R-934): `without_msg` is the strip, and `D_4` the served digest the surface-digest
    test registers (MSG-G10), and R-976's register entry carries it (review Q5, M6; R-457's form).
    Frank's carry naming c_4 is a release-time item."""
    import test_t08_w2_surface_digest as surface
    from msg_schema_support import without_msg

    assert m07a_rc.strip_msg(served) == without_msg(copy.deepcopy(served))
    assert L3.digest == surface.MSG_SERVED_SHA256
    assert L4.digest == surface.X02_SERVED_SHA256
    assert L2.digest == surface.M04_SERVED_SHA256
    register = REGISTER.read_text(encoding="utf-8")
    start = register.index("\n## R-976 ")
    end = register.find("\n## R-", start + 1)
    entry = register[start : end if end != -1 else None]
    assert L3.digest in entry and L2.digest in entry


def test_msg_the_added_description_is_pinned_at_its_recorded_hash() -> None:
    """§5.3 item 4 with c_4 (ADR 0058 D7): `explain.md` is pinned at `REVIEW.json`'s hash, and one
    byte of it changed is caught as MSG's."""
    record = json.loads((REPO_ROOT / REVIEW).read_text(encoding="utf-8"))
    for name, sha256 in m07a_rc.MSG_FILE_SHA256.items():
        assert record["operations"][name]["sha256"] == sha256
    texts = m07a_rc.description_texts()
    texts["explain"] = texts["explain"].replace(".", ",", 1)
    (problem,) = m07a_rc.description_problems(m07a_rc.texts_before_links(texts))
    assert problem.startswith("explain.md: ") and " is not MSG's " in problem


def test_msg_g10_control_c_4_left_in_place(served: list[dict[str, Any]]) -> None:
    """A c_4 whose strip takes nothing out fails at c_3: `failure` reaches M04's digest."""
    assert_the_unmodified_list_passes(served)
    links = (
        *(L0, L1, L2),
        m07a_rc.Link("c_4", "R-934", lambda tools: tools, L3.digest),
        *(L4, L5, L6, L7),
    )
    rows = m07a_rc.chain(served, links)
    assert all(row["pass"] for row in rows[:5])
    assert m07a_rc.first_failure(rows) == "c_4 (R-934)"


def test_x02_link_c_5_is_x02s_strip_and_digest(served: list[dict[str, Any]]) -> None:
    """c_5 (R-950, ADR 0070): `without_x02` is the strip, `D_5` the served digest the surface-digest
    test registers, and R-950's register entry carries it with `D_4` (R-457's form)."""
    import test_t08_w2_surface_digest as surface
    from x02_schema_support import without_x02

    assert m07a_rc.strip_x02(served) == without_x02(copy.deepcopy(served))
    assert L4.digest == surface.X02_SERVED_SHA256
    assert L3.digest == surface.MSG_SERVED_SHA256
    register = REGISTER.read_text(encoding="utf-8")
    start = register.index("\n## R-950 ")
    end = register.find("\n## R-", start + 1)
    entry = register[start : end if end != -1 else None]
    assert L4.digest in entry and L3.digest in entry


def test_x02_control_c_5_left_in_place(served: list[dict[str, Any]]) -> None:
    """A c_5 whose strip takes nothing out fails at c_5: `warm_start` reaches MSG's digest."""
    assert_the_unmodified_list_passes(served)
    links = (
        *(L0, L1, L2, L3),
        m07a_rc.Link("c_5", "R-950", lambda tools: tools, L4.digest),
        *(L5, L6, L7),
    )
    rows = m07a_rc.chain(served, links)
    assert all(row["pass"] for row in rows[:4])
    assert m07a_rc.first_failure(rows) == "c_5 (R-950)"


def test_opt_link_c_6_is_opts_strip_and_digest(served: list[dict[str, Any]]) -> None:
    """c_6 (R-960, ADR 0071; OPT design §4.13, G15): `without_opt` is the strip, `D_6` the served
    digest the surface-digest test registers, and R-960's register entry carries it with `D_5`
    (R-457's form)."""
    import test_t08_w2_surface_digest as surface
    from opt_schema_support import without_opt

    assert m07a_rc.strip_opt(served) == without_opt(copy.deepcopy(served))
    assert L5.digest == surface.OPT_SERVED_SHA256
    assert L4.digest == surface.X02_SERVED_SHA256
    register = REGISTER.read_text(encoding="utf-8")
    start = register.index("\n## R-960 ")
    end = register.find("\n## R-", start + 1)
    entry = register[start : end if end != -1 else None]
    assert L5.digest in entry and L4.digest in entry


def test_opt_control_c_6_left_in_place(served: list[dict[str, Any]]) -> None:
    """A c_6 whose strip takes nothing out fails at c_6: OPT's additions reach X02's digest."""
    assert_the_unmodified_list_passes(served)
    links = (
        *(L0, L1, L2, L3, L4),
        m07a_rc.Link("c_6", "R-960", lambda tools: tools, L5.digest),
        *(L6, L7),
    )
    rows = m07a_rc.chain(served, links)
    assert all(row["pass"] for row in rows[:3])
    assert m07a_rc.first_failure(rows) == "c_6 (R-960)"


def test_opt_control_c_6_restores_the_texts_only_with_the_strip(
    served: list[dict[str, Any]],
) -> None:
    """A c_6 that strips the schema members but leaves OPT's two description texts fails at c_6;
    item 4 on the served texts with only X04's two undone names exactly those two files."""
    from opt_schema_support import OPT_DESCRIPTIONS, _without
    from x04_schema_support import X04_DESCRIPTIONS, pre_x04_text

    assert_the_unmodified_list_passes(served)
    links = (L0, L1, L2, L3, L4, m07a_rc.Link("c_6", "R-960", _without, L5.digest), L6, L7)
    rows = m07a_rc.chain(served, links)
    assert all(row["pass"] for row in rows[:3])
    assert m07a_rc.first_failure(rows) == "c_6 (R-960)"
    texts = m07a_rc.description_texts() | {name: pre_x04_text(name) for name in X04_DESCRIPTIONS}
    problems = m07a_rc.description_problems(texts)
    assert sorted(p.split(".md:")[0] for p in problems) == sorted(OPT_DESCRIPTIONS)


def test_st_g12_link_c_7_is_sts_strip_and_digest(served: list[dict[str, Any]]) -> None:
    """c_7 (R-1000, ADR 0068): `without_st` is the strip, `D_7` the served digest the surface-digest
    test registers (ST G12), `D_6` is what the strip leaves, and R-1000's register entry carries
    both (R-457's form)."""
    import test_t08_w2_surface_digest as surface
    from st_schema_support import without_st

    assert m07a_rc.strip_st(served) == without_st(copy.deepcopy(served))
    assert L6.digest == surface.ST_SERVED_SHA256
    before_x04 = m07a_rc.strip_x04(served)  # X04's c_8 postdates ST
    assert m07a_rc.digest(m07a_rc.strip_st(before_x04)) == L5.digest == surface.OPT_SERVED_SHA256
    register = REGISTER.read_text(encoding="utf-8")
    start = register.index("\n## R-1000 ")
    end = register.find("\n## R-", start + 1)
    entry = register[start : end if end != -1 else None]
    assert L6.digest in entry and L5.digest in entry


def test_st_the_added_description_is_pinned_at_its_recorded_hash() -> None:
    """§5.3 item 4 with c_7 (R-1000, ADR 0068): `get_stream_table.md` is pinned at the hash
    `REVIEW.json` recorded at ST's merge, which is its pre-X04 copy's (X04's c_8 changed the file),
    and one byte of that copy changed is caught as ST's."""
    from x04_schema_support import pre_x04_text

    for name, sha256 in m07a_rc.ST_FILE_SHA256.items():
        assert hashlib.sha256(pre_x04_text(name).encode("utf-8")).hexdigest() == sha256
    texts = m07a_rc.texts_before_links(m07a_rc.description_texts())
    texts["get_stream_table"] = texts["get_stream_table"].replace(".", ",", 1)
    (problem,) = m07a_rc.description_problems(texts)
    assert problem.startswith("get_stream_table.md: ") and " is not ST's " in problem


def test_st_g12_control_c_7_left_in_place(served: list[dict[str, Any]]) -> None:
    """A c_7 whose strip takes nothing out fails at c_7: the tool reaches OPT's digest."""
    assert_the_unmodified_list_passes(served)
    links = (
        *(L0, L1, L2, L3, L4, L5),
        m07a_rc.Link("c_7", "R-1000", lambda tools: tools, L6.digest),
        L7,
    )
    rows = m07a_rc.chain(served, links)
    assert rows[0]["pass"] and rows[1]["pass"]
    assert m07a_rc.first_failure(rows) == "c_7 (R-1000)"


def test_x04_link_c_8_is_x04s_strip_and_digest(served: list[dict[str, Any]]) -> None:
    """c_8 (R-1010, ADR 0075, ADR 0019 Amendment 17): `without_x04` is the strip, `D_8` the served
    digest the surface-digest test registers, `D_7` is what the strip leaves, and R-1010's
    register entry carries both (R-457's form)."""
    import test_t08_w2_surface_digest as surface
    from x04_schema_support import without_x04

    assert m07a_rc.strip_x04(served) == without_x04(copy.deepcopy(served))
    assert L7.digest == surface.X04_SERVED_SHA256
    assert m07a_rc.digest(m07a_rc.strip_x04(served)) == L6.digest == surface.ST_SERVED_SHA256
    register = REGISTER.read_text(encoding="utf-8")
    start = register.index("\n## R-1010 ")
    end = register.find("\n## R-", start + 1)
    entry = register[start : end if end != -1 else None]
    assert L7.digest in entry and L6.digest in entry


def test_x04_the_changed_descriptions_are_pinned_at_their_recorded_hash() -> None:
    """§5.3 item 4 with c_8 (R-1010): X04's two texts are the files `REVIEW.json` records, and
    `texts_before_links` undoes exactly those two, to the hashes the earlier links pinned."""
    from x04_schema_support import X04_DESCRIPTIONS

    record = json.loads((REPO_ROOT / REVIEW).read_text(encoding="utf-8"))
    texts = m07a_rc.description_texts()
    for name in X04_DESCRIPTIONS:
        found = hashlib.sha256(texts[name].encode("utf-8")).hexdigest()
        assert record["operations"][name]["sha256"] == found
    before = m07a_rc.texts_before_links(texts)
    undone = sorted(name for name in texts if before[name] != texts[name])
    from opt_schema_support import OPT_DESCRIPTIONS

    assert undone == sorted({*X04_DESCRIPTIONS, *OPT_DESCRIPTIONS})
    assert m07a_rc.description_problems(before) == []


def test_x04_control_c_8_left_in_place(served: list[dict[str, Any]]) -> None:
    """A c_8 whose strip takes nothing out fails at c_8: X04's additions reach ST's digest."""
    assert_the_unmodified_list_passes(served)
    links = (*m07a_rc.LINKS[:7], m07a_rc.Link("c_8", "R-1010", lambda tools: tools, L7.digest))
    rows = m07a_rc.chain(served, links)
    assert rows[0]["pass"]
    assert m07a_rc.first_failure(rows) == "c_8 (R-1010)"


def test_x04_control_c_8_restores_the_texts_only_with_the_strip(
    served: list[dict[str, Any]],
) -> None:
    """A c_8 that strips the schema members but leaves X04's two description texts fails at c_8;
    item 4 on the served texts with only OPT's two undone names exactly X04's two files."""
    from opt_schema_support import OPT_DESCRIPTIONS, pre_opt_text
    from x04_schema_support import X04_DESCRIPTIONS, _without

    assert_the_unmodified_list_passes(served)
    links = (*m07a_rc.LINKS[:7], m07a_rc.Link("c_8", "R-1010", _without, L7.digest))
    rows = m07a_rc.chain(served, links)
    assert rows[0]["pass"]
    assert m07a_rc.first_failure(rows) == "c_8 (R-1010)"
    texts = m07a_rc.description_texts() | {name: pre_opt_text(name) for name in OPT_DESCRIPTIONS}
    problems = m07a_rc.description_problems(texts)
    assert sorted(p.split(".md:")[0] for p in problems) == sorted(X04_DESCRIPTIONS)
