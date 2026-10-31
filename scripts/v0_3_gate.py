"""The v0.3 gate report: the claimed gates of a registered gate set, read at the tag candidate.

V03 release specification §2 (`docs/derivations/V03-release-spec.md`); ADR 0053. One script for
the 0.3 line (`release.yml` resolves `scripts/v<major>_<minor>_gate.py`). Its registry holds one
gate set, `v0.3-gate-v1`: it covers 0.3.0, 0.3.0bN and 0.3.0rcN (N ≥ 1, canonical; Table T-V3),
claims V11–V20, W21–W26 and X31, each judged at its own candidate under ADR 0053, and does not claim
W27, which is printed `not claimed (v0.3-gate-v1)` and never read (§2.1). A version the set does not
cover is refused, and nothing else is read; 0.2.0 and its pre-releases stay `v0_2_gate.py`'s.

The line admits post-releases (R-922, V03-post1): `0.3.0.postN` (N ≥ 1, canonical) is gated as a
post-release of the released 0.3.0 by the same set and the same `C`, with the envelope at 0.3.0, a
tree check that allows only `README.md`, `pyproject.toml`'s `[project]` `version`, `urls` and
`readme`, and the version string in `src/openflowsheet/__init__.py`, and a tag `v0.3.0` on an
ancestor of the candidate (`v0_2_gate.post_release_differences`, `is_released`). The set's
`covers` pattern, and so Table T-V3, is unchanged.

It runs `scripts/v0_2_gate.py`'s engine unchanged, with this line's name (`v0.3`), its registry and
its specification texts as parameters (§2.2): the inputs, the decision items 1–12, the output
grammar, the tree record (R-151) and the journey carry of RC step 15 are that script's, with this
entry's values. The entry's strings are `benchmarks/v03/registration.json` `gate_set`'s (V03.A01).
It judges nothing: every verdict is read from where the design lane records it, and decides whether
a tag `v<version>` may be **proposed** to Frank (the tag is his, ADR 0021 D5).

    PYTHONPATH=src .venv/bin/python scripts/v0_3_gate.py --rc C [--candidate REF] [--json]
    PYTHONPATH=src .venv/bin/python scripts/v0_3_gate.py --rc C --markdown   # the notes' table
    PYTHONPATH=src .venv/bin/python scripts/v0_3_gate.py --rc C --write-tree-record  # R-151
    PYTHONPATH=src .venv/bin/python scripts/v0_3_gate.py --rc C --carry-journey K3   # step 15
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))
# V03 spec §2.2: the v0.2 engine, imported and not copied; its defaults stay v0.2's (V03.A03).
from v0_2_gate import GateSet, ReleaseLine  # noqa: E402
from v0_2_gate import build as _build  # noqa: E402
from v0_2_gate import gate_set_of as _gate_set_of  # noqa: E402
from v0_2_gate import gated_version as _gated_version  # noqa: E402
from v0_2_gate import main as _main  # noqa: E402
from v0_2_gate import markdown as _markdown  # noqa: E402
from v0_2_gate import not_covered as _not_covered  # noqa: E402
from v0_2_gate import text as _text  # noqa: E402

#: The registry (V03 spec §2.2): one entry, transcribed in `benchmarks/v03/registration.json`.
GATE_SETS: Final = (
    GateSet(
        name="v0.3-gate-v1",
        covers=re.compile(r"0\.3\.0(?:(?:b|rc)[1-9][0-9]*)?"),
        claimed=(*(f"V{n}" for n in range(11, 21)), *(f"W{n}" for n in range(21, 27)), "X31"),
        # §2.1: 0.2.0's agent campaign cannot reach the S11 build (Frank, N-1: not claimed).
        not_claimed=("W27",),
        clause=re.compile(r"\b(?:V(?:1[1-9]|20)|W2[1-6]|X31) \([a-z0-9]+\)"),
        policy_adr="docs/adr/0053-v0.3.0-release-policy.md",
        verdict_document="docs/reviews/V03-verdicts.md",
        rc_record="docs/v03-rc-record.md",
        rc_steps=tuple(range(1, 18)),
        rc_last_step=18,
        evidence_package="S13",
        packages=(
            "M01",
            "M02",
            "M03",
            "M04",
            "M05",
            "M06",
            "S01",
            "S02",
            "S03",
            "S04",
            "S05",
            "S06",
            "S07",
            "S08",
            "S08b",
            "S09",
            "S10",
            "S10c",
            "S11",
            "S12",
        ),
        envelope_id="v0.3-envelope-1",
        required_adrs=(
            "0022",
            "0026",
            "0027",
            "0030",
            "0031",
            "0032",
            "0033",
            "0034",
            "0035",
            "0036",
            "0037",
            "0038",
            "0039",
            "0041",
            "0044",
            "0045",
            "0046",
            "0047",
            "0048",
            "0049",
            "0050",
            "0051",
            "0052",
            "0053",
            "0054",
        ),
        frank_items=("Claim set", "V17 carry", "M02 N1", "M03 N1"),
        rejudge_waits=(
            ("V13", "V17 carry"),
            ("V17", "V17 carry"),
            ("W21", "M02 N1"),
            ("W24", "M03 N1"),
        ),
        links_item="V17 carry",
        specification_texts=("the V03 release specification", "§4"),
    ),
)


def release_line() -> ReleaseLine:
    """This line, read at the call so that `GATE_SETS` is the current one."""
    return ReleaseLine("v0.3", GATE_SETS, (__doc__ or "").splitlines()[0], post_releases=True)


def gate_set_of(version: str) -> GateSet | None:
    """The registered v0.3 gate set covering `version`, if one does (§2.3)."""
    return _gate_set_of(version, release_line())


def not_covered(version: str) -> str:
    return _not_covered(version, release_line())


def gated_version(version: str) -> str:
    """`0.3.0` for a post-release `0.3.0.postN` (R-922), else `version`."""
    return _gated_version(version, release_line())


def build(
    *,
    files: Mapping[str, str],
    rc: str,
    rc_version: str,
    rc_in_repository: bool,
    candidate: str,
    version: str,
    differences: Sequence[str] | None,
    is_ancestor: Callable[[str], bool],
    released: bool | None = None,
) -> dict[str, Any]:
    """`v0_2_gate.build` over this line's registry."""
    return _build(
        files=files,
        rc=rc,
        rc_version=rc_version,
        rc_in_repository=rc_in_repository,
        candidate=candidate,
        version=version,
        differences=differences,
        is_ancestor=is_ancestor,
        release=release_line(),
        released=released,
    )


def text(report: Mapping[str, Any]) -> str:
    return _text(report, release_line())


def markdown(report: Mapping[str, Any]) -> str:
    return _markdown(report, release_line())


def main(argv: Sequence[str] | None = None) -> int:
    return _main(argv, release_line())


if __name__ == "__main__":
    sys.exit(main())
