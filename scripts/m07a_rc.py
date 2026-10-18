"""M07a WO-5: the alpha's step 8, the surface chain and G16-b (V02 alpha release spec §5.3, §8.2).

`0.2.0a1`'s RC job runs `scripts/t08_rc.py`'s subcommands unchanged for steps 1–10 except step 8
(§8.2). T08.A49's check, `t08_rc.py surface`, pins the served MCP tool list to R-133's digest
`171dd768…`; that digest moved twice since (MR-1), and `t08_rc.py`'s A49 constants are 0.1 records
that are not edited (R-192, R-234). This script's `surface` subcommand replaces step 8 (MR-6) and
writes M07a.A37's record:

1. the served digest `d(T(C_α))` is the last link's registered digest `D_m`;
2. stripping link m's additions, then link m−1's from that result, and so on down to link 1, gives
   `D_{k−1}` after each strip, ending at R-133's `D_0` (each strip is applied to the previous
   strip's output; two separate strips of the served list do not satisfy this);
3. with every link stripped, `v17-c2`'s `validate.md` and `commit_change.md` in place of the served
   two give `v17-c2`'s `6d13e13d…` (R-137), which carries A49's request/response-schema clause;
4. the MCP tools are exactly the 17 of `V17_C2_FILE_SHA256`, and each description file's SHA-256 is
   that table's value, except `validate` and `commit_change`, whose files are R-133's;

then G16-b, 40 of 40 clean against `t07_reference_t08.json` (unchanged from T08.A49; the loop is
`t08_rc.step_surface`'s, restated here because that step is not edited). §5.3's negative controls
(i)–(iv) are in `tests/test_m07a_surface_chain.py`.

**The links** (§5.3's table; a new MCP-visible change is a new link with a register entry, a strip
function, a registered digest and Frank's carry extended to name it):

- c_1, R-192 (ADR 0019 Amendment 3, A3.2): `elements` in `diff_revisions`'s `outputSchema`;
  `D_1` = `6c4375b4…` (`tests/test_t08_w2_surface_digest.py`'s `M06_A3_SERVED_SHA256`).
- c_2, R-234 (M02 note §14 B1): M02's enum values, branches, members and `$defs`, stripped by
  `tests/m02_schema_support.py`'s `without_m02` (R-234's decomposition function); `D_2` =
  `383b4e2c…`, the digest served on the tree that merged M02 into `main` (M02's manifest at
  `ba90619` records it as `checks[0].value.mcp_tool_list.served_sha256`; build decision B-WO5-1).
- c_3, R-295 (ADR 0037 D6, ADR 0019 Amendment 5): M04's `surrogate_study` job kind, stripped by
  `tests/m04_schema_support.py`'s `without_m04` (R-295's decomposition function); `D_3` =
  `455d01eb…`, registered at the alpha's merge into `main` (R-457).

The released 0.2.0a1 ran the two-link chain (its committed record at `C_α²`); a re-run of the
alpha's step 8 uses this script at the tag.

**Registered values** are restated with their sources, and `tests/test_m07a_surface_chain.py`
holds each equal to its source.

    PYTHONPATH=src:. python scripts/m07a_rc.py surface --out <path>
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t08_rc  # noqa: E402

ROOT: Final = t08_rc.ROOT
DESCRIPTIONS: Final = ROOT / "src" / "openflowsheet" / "application" / "bindings" / "descriptions"
V17_C2_TEXTS: Final = ROOT / "tests" / "fixtures" / "t08" / "v17_c2_descriptions"

Tools = list[dict[str, Any]]

#: R-133's digest, the chain's end `D_0` (`t08_rc.py`'s 0.1 constant, read, not restated).
D_0: Final = t08_rc.R133_DESCRIPTIONS_SHA256
#: `v17-c2`'s served digest (R-137), item 3's target.
V17_C2_DIGEST: Final = t08_rc.V17_C2_DESCRIPTIONS_SHA256
#: The two files N1 and N2 changed (R-133).
CHANGED: Final = ("commit_change", "validate")
#: Each description's SHA-256 as `v17-c2` served it (`tests/test_t08_w2_surface_digest.py`'s
#: `V17_C2_FILE_SHA256`, the table of `docs/reviews/T08-description-review.md`).
V17_C2_FILE_SHA256: Final = {
    "cancel_job": "e87d799cbe4c32f845772273180fc44d0571fc09a4071a41bd5ef299fab1e557",
    "commit_change": "53266974fe402613f3b147da7bc4673c5d57f55d2f3bf9f7c5dc48f5c9b0b384",
    "diff_revisions": "4a351ae2d7f67e5ff026cc5551109eeb19d7556eedbd2dd50298032858430fea",
    "get_artifact": "22cb20636e1f01efa15af3458e83978ad762e5d5279229db8d8723e6e7122883",
    "get_job": "349d0218d98e272591986daddfd1a87474d37c6a7d473f355e90ddfbf14a56b7",
    "get_job_result": "7eeab9bbee35cd31f55269dd2cd5de2ba4147d531a58ea4b5103e8c903f3520d",
    "get_project": "9ac0612f06676a8ebea3ff185df1fb942a3350efb79f63be53c1c05244aec6fb",
    "get_revision": "02442571d8c73ce99121f9248e712214fde89cca7d493c88876f6eb018cae932",
    "inspect_structure": "4e7c30320406679057dba4933e89a3e77f769538106b396961c1b677c45c9e8d",
    "list_job_events": "66b1ec26d3b22a53e17e43732d56496fd3e28db339298b0e3557987ef836c7d3",
    "list_jobs": "ffe3183f0de54bcf71b90151d8170915af647182bea734a682719fd8e04a6e03",
    "list_models": "941766bdd62094110bf39cacc25c6515efac4041e782f2cae8c5abcacd291db7",
    "list_revisions": "12c3e8f9c506c79fb7ef52e23630ac3cea548c04ed5b80b2e5f0a629a5beaec4",
    "preview_change": "a90d23555bc367af9f91e62704f7f4bc3e5a41d386f99d36a65a89cb7e70b701",
    "submit_job": "61b8509cafb9b4ab101e54622b68b36cf8e938b54df65db105b29b5c36c1771d",
    "validate": "302dc544f519046e25efe6d5a5e83840b6017bfbd36d94a3e3e54435eaae7c12",
    "wait_job": "4a5b99596c771bf6b3254fa9c294e8ad32077de45c3a2e64b93eda0dca37a01c",
}
#: The two changed files as R-133 carried them: their reviewed hashes in `REVIEW.json` as v0.1.0
#: released it (`PUBLIC_ROOT`).
R133_FILE_SHA256: Final = {
    "commit_change": "fd7ff7a808c6f0dbd3af2a45eb5b62c83c7e104a1ef433fc96a6fbbc6a05dd32",
    "validate": "1025385ae14e0fb4dde1b65f79c71e1bff19eb87559e7fa740d3b3357e754d7e",
}


def digest(tools: Tools) -> str:
    """`harness.tool_descriptions_sha256`'s rule on a tool list already dumped."""
    from openflowsheet.canonical import canonical_json  # noqa: PLC0415

    return hashlib.sha256(canonical_json(tools)).hexdigest()


def served_tools() -> Tools:
    """`T(C)`: the served MCP tool list as the digest rule dumps it."""
    from openflowsheet.application.bindings import mcp  # noqa: PLC0415

    mcp.tools.cache_clear()
    try:
        return [tool.model_dump(mode="json", exclude_none=True) for tool in mcp.tools()]
    finally:
        mcp.tools.cache_clear()


def strip_a3_2(tools: Tools) -> Tools:
    """s_1 (R-192): `tools` without `elements` in `diff_revisions`'s `outputSchema`."""
    out = copy.deepcopy(tools)
    for tool in out:
        if tool["name"] == "diff_revisions":
            schema = tool["outputSchema"]
            schema["properties"].pop("elements", None)
            schema["required"] = [name for name in schema["required"] if name != "elements"]
    return out


def strip_m02(tools: Tools) -> Tools:
    """s_2 (R-234): `tools` without M02's additions (`m02_schema_support.without_m02`)."""
    t08_rc._tests_on_path()
    from m02_schema_support import without_m02  # noqa: PLC0415

    stripped = without_m02(copy.deepcopy(tools))
    assert isinstance(stripped, list)
    return stripped


def strip_m04(tools: Tools) -> Tools:
    """s_3 (R-295): `tools` without M04's additions (`m04_schema_support.without_m04`)."""
    t08_rc._tests_on_path()
    from m04_schema_support import without_m04  # noqa: PLC0415

    stripped = without_m04(copy.deepcopy(tools))
    assert isinstance(stripped, list)
    return stripped


@dataclass(frozen=True)
class Link:
    """One registered surface change c_k: its register entry, its strip function s_k, and the
    served digest D_k after it."""

    name: str
    register: str
    strip: Callable[[Tools], Tools]
    digest: str


LINKS: Final = (
    Link(
        "c_1",
        "R-192",
        strip_a3_2,
        "6c4375b478d71c12b1211c17fafe7e58e9dfc0a05e11def2106799a6917631c9",
    ),
    Link(
        "c_2",
        "R-234",
        strip_m02,
        "383b4e2c004810663a3e3f80c591730bc95894e35736619eacac0f51e51b5403",
    ),
    Link(
        "c_3",
        "R-295",
        strip_m04,
        "455d01eb2f420032b27358798e6b331a0120aa1857f02ce3cb7851647849e125",
    ),
)


def with_v17_c2_texts(tools: Tools) -> Tools:
    """`tools` with `v17-c2`'s two texts in place of the served `validate` and `commit_change`
    (a tool's served description is its file, byte for byte)."""
    from openflowsheet.application.operations import OPERATIONS  # noqa: PLC0415

    kept = {
        OPERATIONS[name].mcp_tool: (V17_C2_TEXTS / f"{name}.md").read_text("utf-8")
        for name in CHANGED
    }
    out = copy.deepcopy(tools)
    for tool in out:
        if tool["name"] in kept:
            tool["description"] = kept[tool["name"]]
    return out


def chain(tools: Tools, links: Sequence[Link] = LINKS) -> list[dict[str, Any]]:
    """§5.3 items 1–3 on `tools`: one row per item and link, in the order they are judged —
    the served digest (item 1, link m), each strip from link m down to link 1 (item 2), and
    `v17-c2`'s texts on the fully stripped list (item 3)."""
    last = links[-1]
    found = digest(tools)
    rows = [
        {
            "item": 1,
            "link": last.name,
            "register": last.register,
            "expected": last.digest,
            "found": found,
            "pass": found == last.digest,
        }
    ]
    current = tools
    for k in range(len(links), 0, -1):
        link = links[k - 1]
        current = link.strip(current)
        expected = links[k - 2].digest if k > 1 else D_0
        found = digest(current)
        rows.append(
            {
                "item": 2,
                "link": link.name,
                "register": link.register,
                "expected": expected,
                "found": found,
                "pass": found == expected,
            }
        )
    found = digest(with_v17_c2_texts(current))
    rows.append(
        {
            "item": 3,
            "link": None,
            "register": "R-137",
            "expected": V17_C2_DIGEST,
            "found": found,
            "pass": found == V17_C2_DIGEST,
        }
    )
    return rows


def first_failure(rows: Sequence[Mapping[str, Any]]) -> str | None:
    """The link (with its register entry) at which the chain first fails, or None."""
    for row in rows:
        if not row["pass"]:
            return f"{row['link']} ({row['register']})" if row["link"] else row["register"]
    return None


def description_texts() -> dict[str, str]:
    """Each MCP operation's served description file, by operation name."""
    from openflowsheet.application.operations import OPERATIONS  # noqa: PLC0415

    return {
        name: (DESCRIPTIONS / f"{name}.md").read_text("utf-8")
        for name, operation in OPERATIONS.items()
        if "mcp" in operation.transports
    }


def description_problems(texts: Mapping[str, str]) -> list[str]:
    """§5.3 item 4 on `texts` (operation name -> description file): one line per failure."""
    problems: list[str] = []
    if sorted(texts) != sorted(V17_C2_FILE_SHA256):
        problems.append(f"tools {sorted(texts)} are not v17-c2's 17")
    for name in sorted(set(texts) & set(V17_C2_FILE_SHA256)):
        expected = R133_FILE_SHA256[name] if name in CHANGED else V17_C2_FILE_SHA256[name]
        found = hashlib.sha256(texts[name].encode("utf-8")).hexdigest()
        if found != expected:
            source = "R-133's" if name in CHANGED else "v17-c2's"
            problems.append(f"{name}.md: {found} is not {source} {expected}")
    return problems


def served_texts_are_the_files(tools: Tools, texts: Mapping[str, str]) -> bool:
    """Each served tool's description is its operation's file, byte for byte."""
    from openflowsheet.application.operations import OPERATIONS  # noqa: PLC0415

    by_tool = {OPERATIONS[name].mcp_tool: text for name, text in texts.items()}
    return {tool["name"]: tool["description"] for tool in tools} == by_tool


def g16b(out: Path, checks: list[dict[str, Any]], expected_class: str) -> list[dict[str, Any]]:
    """G16-b over the reference tasks and four transports (`t08_rc.step_surface`'s loop)."""
    t08_rc._tests_on_path()
    from benchmarks.t07.v17 import reference  # noqa: PLC0415

    runs: list[dict[str, Any]] = []
    for task in reference.TASKS:
        for transport in reference.TRANSPORTS:
            record = reference.run(task, transport, out / "g16b" / task / transport)
            numbers = reference.verdict(record)
            run = json.loads((record.directory / "run.json").read_bytes())
            conditions = record.scores["completion"]["conditions"]
            runs.append(
                {
                    "task": task,
                    "transport": transport,
                    "clean": bool(reference.clean(numbers))
                    and all(conditions.values())
                    and record.scores["infrastructure_failure"] is None,
                    "attributable": run["provenance"].get("machine_class") == expected_class
                    and run["provenance"].get("tree_clean") is not None,
                }
            )
    clean = sum(run["clean"] for run in runs)
    t08_rc.check(
        checks,
        "a37.g16b_clean",
        clean == len(runs) == 40,
        clean=clean,
        runs=len(runs),
        not_clean=[(r["task"], r["transport"]) for r in runs if not r["clean"]],
    )
    t08_rc.check(checks, "a16.g16b_records_attributable", all(r["attributable"] for r in runs))
    return runs


def step_surface(arguments: argparse.Namespace) -> int:
    os.environ.update({name: "1" for name in t08_rc.THREAD_VARIABLES})
    out: Path = arguments.out
    tools = served_tools()
    rows = chain(tools)
    texts = description_texts()
    problems = description_problems(texts)
    checks: list[dict[str, Any]] = []
    for row in rows:
        suffix = f"{row['link']}_{row['register']}" if row["link"] else row["register"]
        t08_rc.check(
            checks,
            f"a37.item{row['item']}.{suffix}".replace("-", "").lower(),
            row["pass"],
            expected=row["expected"],
            found=row["found"],
        )
    t08_rc.check(
        checks,
        "a37.item4.tools_and_files",
        not problems and served_texts_are_the_files(tools, texts),
        problems=problems,
    )
    expected_class = t08_rc.machine_class()
    runs = g16b(out, checks, expected_class)
    return t08_rc.finish(
        out / "rc-alpha-surface.json",
        "surface-alpha",
        checks,
        chain=rows,
        first_failure=first_failure(rows),
        runs=runs,
        provenance={**t08_rc.provenance(), "machine_class": expected_class},
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="step", required=True)
    commands.add_parser("surface").add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    arguments.out = arguments.out.resolve()
    return step_surface(arguments)


if __name__ == "__main__":
    sys.exit(main())
