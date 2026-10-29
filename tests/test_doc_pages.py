"""DOC (S14): the site's generated pages are the code's, so they cannot drift.

`docs-site/guide/units.md` (from `list_models`, `MODEL_BASES` and `MODEL_BUILDERS`) and
`docs-site/api/operations.md` (from `OPERATIONS`) are written by `scripts/doc_pages.py`; `--check`
re-renders both and compares byte for byte.
"""

from __future__ import annotations

import sys

from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import doc_pages as catalogue  # noqa: E402

from openflowsheet.application.operations import OPERATIONS  # noqa: E402
from openflowsheet.application.revision_binding import MODEL_BASES, MODEL_BUILDERS  # noqa: E402


def test_the_committed_pages_are_the_generated_ones() -> None:
    assert catalogue.main(["--check"]) == 0


def test_every_registered_model_and_basis_is_on_the_page() -> None:
    page = catalogue.PAGE.read_text(encoding="utf-8")
    for model_id in MODEL_BUILDERS:
        assert f"### `{model_id}`" in page, model_id
    for basis in {b for bases in MODEL_BASES.values() for b in bases}:
        assert f"| `{basis}` |" in page, basis


def test_every_operation_is_in_the_table() -> None:
    page = catalogue.OPERATIONS_PAGE.read_text(encoding="utf-8")
    for name in OPERATIONS:
        assert f"| `{name}` |" in page, name
