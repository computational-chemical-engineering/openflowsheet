"""M03 A42: the closed-form reference generator re-derives every claim (spec §11, §13).

``docs/derivations/scripts/m03_reference.py --check`` recomputes the 257 instantiated claims of the
specification at 60 digits and requires the committed ``benchmarks/m03/reference_values.json`` to
equal its output byte for byte. It runs in about 25 s, so it runs on every gate: the M03 tests judge
the implementation against that file, and the file is only an expectation while the generator that
produced it still stands behind it.
"""

from __future__ import annotations

import re
import subprocess
import sys

from m03_support import (
    GENERATOR_PATH,
    REFERENCE_PATH,
    REFERENCE_SHA256,
    REPO_ROOT,
    constant,
    reference,
)

#: Spec §13 and A42: the generator's own count of instantiated claims.
REGISTERED_CLAIMS = 257

_PASSED = re.compile(r"^(\d+) claims passed$", re.MULTILINE)
_IDENTICAL = re.compile(
    r"^benchmarks/m03/reference_values\.json is byte-identical to the generator's output$",
    re.MULTILINE,
)


def test_a42_the_generator_check_passes_and_the_json_is_its_output() -> None:
    completed = subprocess.run(
        [sys.executable, str(GENERATOR_PATH), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    passed = _PASSED.search(completed.stdout)
    assert passed is not None, output
    assert int(passed.group(1)) == REGISTERED_CLAIMS, output
    assert _IDENTICAL.search(completed.stdout) is not None, output


def test_the_loader_returns_the_file_the_specification_cites() -> None:
    """The loader pins the bytes to the spec header's SHA-256, and the claims count agrees."""
    loaded = reference()
    assert REFERENCE_PATH.is_file()
    assert loaded["schema"] == "m03-reference-v1"
    assert loaded["specification"] == "docs/derivations/M03-studies-spec.md"
    assert len(loaded["generator_claims"]) == REGISTERED_CLAIMS
    assert len(REFERENCE_SHA256) == 64
    # Spec §3.4, §3.5, §4.7: the registered thresholds the tests use, read through one door.
    assert constant("tau_regime") == 1e-4
    assert constant("tau_root") == 1e-10
    assert constant("tau_alias") == 1e-8
    assert constant("tau_abs_scaled") == 1e-11
    assert constant("tau_rel") == 1e-10
    assert constant("tau_fd_scaled") == 1e-9
