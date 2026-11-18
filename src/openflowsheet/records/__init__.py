"""F3's component data core (ADR 0061), introduced by package F3: v2 records, their identity and
their validation (F3-WO1). The store, resolution, the data lock, the rights register and the
importers follow in later work orders.

- `model`: D1 to D5's tables (core property ids, the built-in correlation forms, record types and
  data sources) and the outcome type; the record's shape is `schemas/record-v2.schema.json`.
- `normalize`: D2 steps 1 to 5 and D6 (the anchor).
- `validate`: D2 step 6 and D7.
- `identity`: the pipeline and the SHA (D2 step 7).
"""

from __future__ import annotations

from openflowsheet.records.identity import identify, record_sha256
from openflowsheet.records.model import RECORD_FORMAT, RecordOutcome
from openflowsheet.records.normalize import normalize

__all__ = ["RECORD_FORMAT", "RecordOutcome", "identify", "normalize", "record_sha256"]
