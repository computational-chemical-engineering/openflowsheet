"""M07a.A50 (part): the alpha's harvest (V02 alpha release spec §5.2 MR-3 and MR-5, FD-α7).

The harvest covers every manifest under `evidence/`, T08's included (T08 Amendment R8 4): its 58
limitations and 2 non-pass checks are classified E/S/P/B with pointers like every other manifest's
(T08.A21's rule, `t08_support_matrix.check_a21`, run by `test_t08_w2_support_envelope.py`), and
`HARVEST_EXCLUDED` is empty. The harvest's size is held equal to `HARVEST_SIZE`, which M07a's
manifest quotes at `C_α` (MR-5); a new manifest moves it, and this test with it.

The envelope's id and release at `C_α` (MR-3's pin) and the matrix re-emitted after the pin are
WO-10's, at the cut.
"""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Iterable

from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_support_matrix as matrix  # noqa: E402

T08_MANIFEST = "evidence/T08/67c66d98587f23bd7dfe8da28a8facccc92da21e/manifest.json"
#: (manifests, limitations, non-pass checks) the harvest reads (MR-5).
HARVEST_SIZE = (23, 316, 29)


def _kinds(keys: Iterable[tuple[str, str]]) -> Counter[str]:
    """How many `limitations[i]` and `checks[i]` items `keys` holds."""
    return Counter(item.split("[")[0] for _, item in keys)


def test_m07a_a50_nothing_is_excluded_from_the_harvest() -> None:
    assert matrix.HARVEST_EXCLUDED == ()
    assert set(matrix._manifests()) == {path for path, _ in matrix.harvest_items()}


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
