"""DOC (S14): the site's unit catalogue is the model registry's, so it cannot drift.

`docs-site/guide/units.md` is written by `scripts/doc_unit_catalogue.py` from `list_models`,
`MODEL_BASES` and `MODEL_BUILDERS`; `--check` re-renders it and compares byte for byte.
"""

from __future__ import annotations

import sys

from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import doc_unit_catalogue as catalogue  # noqa: E402

from openflowsheet.application.revision_binding import MODEL_BASES, MODEL_BUILDERS  # noqa: E402


def test_the_committed_catalogue_is_the_generated_one() -> None:
    assert catalogue.main(["--check"]) == 0


def test_every_registered_model_and_basis_is_on_the_page() -> None:
    page = catalogue.PAGE.read_text(encoding="utf-8")
    for model_id in MODEL_BUILDERS:
        assert f"### `{model_id}`" in page, model_id
    for basis in {b for bases in MODEL_BASES.values() for b in bases}:
        assert f"| `{basis}` |" in page, basis
