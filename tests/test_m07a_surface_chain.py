"""M07a.A37: the alpha's step 8, the surface chain of V02 alpha release spec §5.3 (MR-1, MR-6).

`scripts/m07a_rc.py` composes the chain; this module runs it on the served tool list (items 1–4)
with §5.3's negative controls (i)–(iv), and holds the script's registered values equal to their
sources. G16-b, the step's other half, runs in the RC job only (40 reference runs).

On `main` the chain has three links: c_3 (R-295, M04's `surrogate_study` job kind) was registered at
the alpha's merge (R-457). Every control first asserts that the unmodified served list passes, so no
control passes merely because the chain already fails. The released 0.2.0a1's step 8 (two links) is
read from its committed record at `C_α²`, not re-run (`test_m07a_a37_the_released_step_8_record`).
"""

from __future__ import annotations

import copy
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
L0, L1, L2 = m07a_rc.LINKS


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
        (1, "c_3"),
        (2, "c_3"),
        (2, "c_2"),
        (2, "c_1"),
        (3, None),
    ]
    assert m07a_rc.first_failure(rows) is None, rows
    assert rows[-2]["found"] == t08_rc.R133_DESCRIPTIONS_SHA256
    texts = m07a_rc.description_texts()
    assert m07a_rc.description_problems(texts) == []
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
    assert m07a_rc.first_failure(rows) == "c_3 (R-295)"
    assert [r["pass"] for r in rows[:2]] == [False, False]


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
    links = (L0, L1, m07a_rc.Link("c_3", "R-295", too_many, L2.digest))
    rows = m07a_rc.chain(served, links)
    assert rows[0]["pass"]
    assert m07a_rc.first_failure(rows) == "c_3 (R-295)"


def test_m07a_a37_control_ii_prime_an_inner_link_strips_one_member_too_many(
    served: list[dict[str, Any]],
) -> None:
    assert_the_unmodified_list_passes(served)
    too_many = one_member_too_many(m07a_rc.strip_m02)
    links = (L0, m07a_rc.Link("c_2", "R-234", too_many, L1.digest), L2)
    rows = m07a_rc.chain(served, links)
    assert rows[0]["pass"] and rows[1]["pass"]
    assert m07a_rc.first_failure(rows) == "c_2 (R-234)"


def test_m07a_a37_control_iii_one_byte_of_another_description_changed() -> None:
    texts = m07a_rc.description_texts()
    texts["list_jobs"] = texts["list_jobs"].replace(".", ",", 1)
    problems = m07a_rc.description_problems(texts)
    assert len(problems) == 1
    assert problems[0].startswith("list_jobs.md: ")


def test_m07a_a37_control_iv_elements_left_in_place(served: list[dict[str, Any]]) -> None:
    assert_the_unmodified_list_passes(served)
    links = (m07a_rc.Link("c_1", "R-192", lambda tools: tools, L0.digest), L1, L2)
    rows = m07a_rc.chain(served, links)
    assert [r["pass"] for r in rows[:3]] == [True, True, True]
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
