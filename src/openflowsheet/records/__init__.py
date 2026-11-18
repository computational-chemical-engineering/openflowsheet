"""F3's component data core (ADR 0061), introduced by package F3: v2 records, their identity and
their validation (F3-WO1); the store and resolution (F3-WO2); the legacy import and the loader
views (F3-WO3); the data lock and the rights register (F3-WO4). The user-file importer and the
operations follow in F3-WO5.

- `model`: D1 to D5's tables (core property ids, the built-in correlation forms, record types and
  data sources) and the outcome type; the record's shape is `schemas/record-v2.schema.json`.
- `normalize`: D2 steps 1 to 5 and D6 (the anchor); its function `normalize` is not re-exported,
  so the submodule keeps its name on the package.
- `validate`: D2 step 6 and D7.
- `identity`: the pipeline and the SHA (D2 step 7).
- `store`: the content-addressed object store and `records.sqlite3` (D8).
- `stack`: the store stack, project store over legacy store (D8).
- `resolve`: lookup keys, identity classes and resolution (D9).
- `importers.legacy`: the legacy importer, its profiles and the committed legacy index (D12).
- `legacy_views`: the legacy loaders' dataclasses rebuilt from imported records (D12).
- `lock`: the data lock, its builder and `data_lock_sha256` (D10); the lock's shape is
  `schemas/data-lock.schema.json`.
- `rights`: the rights register, its seed rows and the effective assessment (D11).
"""

from __future__ import annotations

from openflowsheet.records.identity import identify, record_sha256
from openflowsheet.records.model import RECORD_FORMAT, RecordOutcome

__all__ = ["RECORD_FORMAT", "RecordOutcome", "identify", "record_sha256"]
