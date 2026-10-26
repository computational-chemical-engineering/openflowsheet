"""S09 WO-S09-1: the BioSTEAM environment's committed files (spec §2.1, §12; A04's file part).

The test never builds or imports BioSTEAM. It reads the lock, the build script and
`docs/reference-environments.md` §9. The half of A04 that compares each record's fingerprint
with §9's waits for the records of WO-S09-2.
"""

from __future__ import annotations

import re

from conftest import REPO_ROOT

REFERENCES = REPO_ROOT / "spikes" / "references"
LOCK = REFERENCES / "biosteam-requirements.lock"
IN_FILE = REFERENCES / "biosteam-requirements.in"
DOC = REPO_ROOT / "docs" / "reference-environments.md"

# S09 spec §2.1.
VERSIONS = {
    "biosteam": "2.54.0",
    "thermosteam": "0.54.2",
    "thermo": "0.6.1",
    "chemicals": "1.5.2",
    "flexsolve": "0.5.10",
    "numba": "0.68.0",
    "numpy": "2.5.4",
    "scipy": "1.18.1",
    "coolprop": "8.0.0",
}


def _lock_entries() -> dict[str, list[str]]:
    """Map each pinned distribution (as `name==version`) to its hash list."""
    entries: dict[str, list[str]] = {}
    current = None
    for line in LOCK.read_text().splitlines():
        if re.match(r"^[A-Za-z]", line):
            current = line.split()[0]
            entries[current] = []
        m = re.search(r"--hash=sha256:([0-9a-f]{64})", line)
        if m and current:
            entries[current].append(m.group(1))
    return entries


def _section9() -> str:
    text = DOC.read_text()
    return text[text.index("## 9. The S09 third column reference") :]


def test_lock_pins_every_distribution_by_hash() -> None:
    entries = _lock_entries()
    assert len(entries) > 40
    for pin, hashes in entries.items():
        assert re.fullmatch(r"[A-Za-z0-9_.-]+==[^=\s]+", pin), pin
        assert hashes, f"{pin} has no hash"


def test_lock_holds_the_versions_of_spec_2_1() -> None:
    pins = {p.split("==")[0].lower(): p.split("==")[1] for p in _lock_entries()}
    for name, version in VERSIONS.items():
        assert pins.get(name) == version, name
    for tool in ("setuptools", "wheel", "cython"):  # the --no-build-isolation route
        assert tool in pins


def test_in_file_names_the_tool() -> None:
    lines = [ln for ln in IN_FILE.read_text().splitlines() if ln and not ln.startswith("#")]
    assert lines[0] == "biosteam==2.54.0"
    assert "biosteam-requirements.in" in LOCK.read_text().split("\n\n")[0]


def test_build_script_uses_the_lock_with_hashes() -> None:
    script = (REPO_ROOT / "scripts" / "build-reference-envs.sh").read_text()
    assert "spikes/references/biosteam-requirements.lock" in script
    assert ".venv-biosteam" in script
    assert "--require-hashes" in script
    assert "--no-build-isolation" in script


def test_section9_records_two_identical_fingerprints_and_the_statements() -> None:
    sec = _section9()
    fingerprints = re.findall(r"\[\.venv-biosteam\] pip freeze sha256: ([0-9a-f]{64})", sec)
    assert len(fingerprints) == 1  # one value, recorded for the two consecutive builds
    assert "identical" in sec and "two consecutive builds" in sec
    assert "University of Illinois/NCSA Open Source License" in sec
    assert "aarch64" in sec and "installability" in sec


def test_venv_is_git_ignored() -> None:
    patterns = (REPO_ROOT / ".gitignore").read_text().splitlines()
    assert ".venv-*/" in patterns
