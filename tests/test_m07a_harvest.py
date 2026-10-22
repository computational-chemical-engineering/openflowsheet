"""M07a.A50 (part): the alpha's harvest (V02 alpha release spec §5.2 MR-3 and MR-5, FD-α7).

The harvest covers every manifest under `evidence/`, T08's included (T08 Amendment R8 4): its 58
limitations and 2 non-pass checks are classified E/S/P/B with pointers like every other manifest's
(T08.A21's rule, `t08_support_matrix.check_a21`, run by `test_t08_w2_support_envelope.py`), and
`HARVEST_EXCLUDED` excludes no manifest at `C_α`: it names `evidence/M07a/`, M07a's own
manifest, which is written after `C_α` (R-320), and `evidence/M07/`, M07's own, which is written
after C′; both belong to the next harvest (R-485). The harvest's size is held
equal to `HARVEST_SIZE`, which M07a's manifest quotes at `C_α` (MR-5); a new manifest moves it,
and this test with it.

The envelope's id and release at `C_α` (MR-3's pin) and the matrix re-emitted after the pin are
WO-10's, at the cut.
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from collections.abc import Iterable

from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_support_matrix as matrix  # noqa: E402

T08_MANIFEST = "evidence/T08/67c66d98587f23bd7dfe8da28a8facccc92da21e/manifest.json"
#: (manifests, limitations, non-pass checks) the harvest reads (MR-5). M07a's manifest quotes
#: (23, 316, 29) at `C_α`; main's M02 follow-up, M03, M04 and M05 manifests moved it at the alpha's
#: merge into main; S01's three manifests (`ea12548…`, `implemented`, 17 and 6; `a3eaf09…` and
#: `465240a…`, `tested`, 12 and 1 each), all kept as every package keeps its superseded manifests,
#: moved it at S01's merge.
HARVEST_SIZE = (34, 413, 41)
#: The 0.2.0 release candidate C′ (M07 spec §25, R-485).
C_PRIME = "ce993651ce37c1343e771b276160bd6623e43500"


def _kinds(keys: Iterable[tuple[str, str]]) -> Counter[str]:
    """How many `limitations[i]` and `checks[i]` items `keys` holds."""
    return Counter(item.split("[")[0] for _, item in keys)


def _candidates() -> set[str]:
    """The commits named as `C_α`: the `## v0.2.0a1` heading's, once it is no longer pending,
    and the directory of every M07a manifest (`evidence/M07a/<C_α>/`)."""
    named = {path.parent.name for path in (REPO_ROOT / "evidence" / "M07a").glob("*/manifest.json")}
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = text[text.index("## v0.2.0a1") :].splitlines()[0]
    candidate = heading.split("`C_α` = `", 1)[1].split("`", 1)[0]
    if not candidate.startswith("[[PENDING: "):
        named.add(candidate)
    return named


def test_m07a_a50_nothing_is_excluded_from_the_harvest_at_c_alpha() -> None:
    """R-320, R-485: the exclusion is exactly M07a's and M07's directories, and no manifest of a
    candidate is under it — none in the working tree before the cut, none in `C_α`'s tree under
    `evidence/M07a/` after it, none in C′'s tree under `evidence/M07/`."""
    assert matrix.HARVEST_EXCLUDED == ("evidence/M07a/", "evidence/M07/")
    manifests = set(matrix._manifests())
    excluded = {path for path in manifests if path.startswith(matrix.HARVEST_EXCLUDED)}
    assert manifests - excluded == {path for path, _ in matrix.harvest_items()}
    candidates = _candidates()
    if not candidates:
        assert excluded == set()
    for candidate in sorted(candidates):
        listed = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", candidate, "--", "evidence/M07a/"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert listed == "", (candidate, listed)
    listed = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", C_PRIME, "--", "evidence/M07/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert not [path for path in listed.splitlines() if path.endswith("/manifest.json")], listed


def test_m07a_a50_t08s_manifest_is_harvested_in_full() -> None:
    items = {key for key in matrix.harvest_items() if key[0] == T08_MANIFEST}
    assert _kinds(items) == Counter({"limitations": 58, "checks": 2})
    harvest = matrix.load()["harvest"]
    classified = {(entry["manifest"], entry["item"]) for entry in harvest}
    assert items <= classified


def test_m07a_a50_the_harvest_size_is_the_quoted_one() -> None:
    items = matrix.harvest_items()
    kinds = _kinds(items)
    found = (len({path for path, _ in items}), kinds["limitations"], kinds["checks"])
    assert found == HARVEST_SIZE
    assert len(matrix.load()["harvest"]) == sum(HARVEST_SIZE[1:])
