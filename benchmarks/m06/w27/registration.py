"""The W27 registration as data: paths, the registered tables, the committed JSON form.

Normative text: `docs/derivations/M06-W27-registration.md` (§0: "WO-16 implements [the tables]
**as data**, read from `registration.json`; it does not re-decide them"). Nothing here restates a
table; every map, vocabulary, seed and tolerance is read from `registration.json`. The generator
`docs/derivations/scripts/m06_w27_registration.py` is never imported (§18 WO-16a): the tests
compare this code's output with the generator's committed output instead.
"""

from __future__ import annotations

import functools
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

ROOT: Final[Path] = Path(__file__).resolve().parents[3]
#: The adaptation's records (R-194: the only tracked directory that names the benchmark).
RECORDS: Final[Path] = ROOT / "benchmarks" / "m06" / "openidaes450"
REGISTRATION_JSON: Final[Path] = RECORDS / "registration.json"
CASE_FACTS_JSON: Final[Path] = RECORDS / "case_facts.json"
ACCESS_JSON: Final[Path] = RECORDS / "access_report.json"
PROVENANCE_JSON: Final[Path] = RECORDS / "provenance.json"
DRY_JSON: Final[Path] = RECORDS / "dry_illustration.json"
#: Tier 0 item 3 (W27-R25): today's coverage against the build at hand.
COVERAGE_JSON: Final[Path] = RECORDS / "coverage.json"
DOCUMENT: Final[Path] = ROOT / "docs" / "derivations" / "M06-W27-registration.md"
GENERATOR: Final[Path] = ROOT / "docs" / "derivations" / "scripts" / "m06_w27_registration.py"
#: Tier 0 item 4: the generated report.
REPORT_MD: Final[Path] = ROOT / "docs" / "m06-w27-coverage.md"
#: The pinned archive and its extraction (git-ignored; `scripts/m06_w27_acquire.py`).
ARTIFACTS: Final[Path] = ROOT / "evidence" / "M06" / "W27" / "artifacts"
ARCHIVE_FILE: Final[Path] = ARTIFACTS / "OpenIDAES-450-demo.tar.gz"
ARCHIVE_DIR: Final[Path] = ARTIFACTS / "extracted" / "OpenIDAES-450-demo"


@functools.cache
def load() -> Mapping[str, Any]:
    """`registration.json`, parsed once per process."""
    document: Mapping[str, Any] = json.loads(REGISTRATION_JSON.read_bytes())
    return document


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def dump(document: Any) -> bytes:
    """The committed JSON form of the W27 records (the generator's `dump`): sorted keys,
    two-space indent, UTF-8, a final newline. A snapshot's SHA-256 is of this form (W27-R22)."""
    text = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def hash_rank(*parts: str) -> str:
    """W27-R28…R31: `sha256(seed ‖ 0x00 ‖ purpose ‖ 0x00 ‖ id)`, hex, compared ascending."""
    seed = str(load()["sample"]["seed_text"])
    return sha256_bytes("\x00".join((seed, *parts)).encode("utf-8"))


def classes() -> tuple[str, ...]:
    """W27-R08's precedence order, `CANDIDATE` last."""
    return tuple(str(c) for c in load()["classes"])


def provider_methods() -> dict[str, str]:
    """W27-R19's table (a test may add a test-only provider to a copy, W27-A02)."""
    return {str(k): str(v) for k, v in load()["routes"]["provider_methods"].items()}
