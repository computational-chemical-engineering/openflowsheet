"""Print F0's frozen modules, one repository path per line: the gate's `frozen_cmd` (S17).

The paths are the keys of measure M9 in F0's registry (`benchmarks/f0/corpus.json`): every file
feeding an `implementation_sha256` or `artifact_hash`. A refactor step that changes one of their
bytes fails `codehealth gate`'s frozen rule (docs/code-health.md). The gate runs this command in
the base tree, so the list is the registered one, not the change's. Standard library only: it runs
under any Python 3, without the project installed.

S19 W5 (ruling R3, work order WO-1): with `S19_W5_BATCH` set to a batch file (the gate queue's
`--mode w5`, `scripts/w5_gate.py`), the batch's `admitted` paths are left out: a W5 step may
change them, and the W5 tiers judge what that moves.

    python3 scripts/codehealth_frozen.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
CORPUS: Final = ROOT / "benchmarks" / "f0" / "corpus.json"
BATCH_VARIABLE: Final = "S19_W5_BATCH"


def frozen_paths() -> list[str]:
    """The keys of M9's registered values, sorted."""
    registry = json.loads(CORPUS.read_text(encoding="utf-8"))
    return sorted(registry["measures"]["M9"])


def admitted() -> set[str]:
    """The W5 batch's admitted paths when `S19_W5_BATCH` names a batch file, else none."""
    name = os.environ.get(BATCH_VARIABLE)
    if not name:
        return set()
    batch = json.loads(Path(name).read_text(encoding="utf-8"))
    return set(batch["admitted"])


def main() -> int:
    paths = frozen_paths()
    if not paths:
        raise SystemExit(f"{CORPUS}: measure M9 registers no paths")
    exempt = admitted()
    print("\n".join(path for path in paths if path not in exempt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
