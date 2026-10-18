"""R-460: the version `main` carries between releases, and the envelope that goes with it.

A version string that names a release identifies that release's D2.4 tree and nothing else (AM-40).
The first D2.4 change after a tag moves the version to a `.dev0` that sorts after the tagged version
and returns the envelope to its working form, R-193's `v0.2-envelope-dev` with `release: 0.2.0.dev0`
(AM-41, AM-42; V02 alpha release spec §5, MR-3). At a cut the envelope's `release` is the version,
which the gate checks again at C.
"""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

from conftest import ALPHA_TAG_COMMIT, REPO_ROOT
from packaging.version import Version

import openflowsheet

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import v0_1_gate  # noqa: E402

#: Every released version and the commit it was tagged from.
RELEASED = {"0.2.0a1": ALPHA_TAG_COMMIT}
#: R-193's working envelope.
WORKING_ENVELOPE = ("v0.2-envelope-dev", "0.2.0.dev0")


def _matrix() -> ModuleType:
    path = REPO_ROOT / "scripts" / "t08_support_matrix.py"
    spec = importlib.util.spec_from_file_location("t08_support_matrix", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MATRIX = _matrix()
VERSION = openflowsheet.__version__


def test_a_released_version_names_its_tree_only() -> None:
    """AM-40: a version that is a release's has that release's D2.4 tree. The negative control
    always runs: `HEAD`'s tree is not the alpha's, so the check can fail."""
    assert v0_1_gate.tree_differences(ALPHA_TAG_COMMIT, "HEAD") != []
    if VERSION in RELEASED:
        assert v0_1_gate.tree_differences(RELEASED[VERSION], "HEAD") == []


def test_the_envelope_matches_the_version() -> None:
    """AM-41: a canonical PEP 440 version; between releases the working envelope, at a cut the
    envelope's `release` is the version."""
    assert str(Version(VERSION)) == VERSION
    envelope = MATRIX.load()
    if Version(VERSION).is_devrelease:
        assert (envelope["envelope_id"], envelope["release"]) == WORKING_ENVELOPE
        assert MATRIX.ENVELOPE_ID == WORKING_ENVELOPE[0]
    else:
        assert envelope["release"] == VERSION


def test_the_version_sorts_after_every_release() -> None:
    """AM-42: unless it is a release's own, the version sorts after every released one (this is
    what rejects `0.2.0.dev0` after `0.2.0a1`)."""
    if VERSION not in RELEASED:
        assert Version(VERSION) > max(Version(version) for version in RELEASED)
