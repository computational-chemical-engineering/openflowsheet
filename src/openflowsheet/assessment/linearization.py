"""The assessment program's typed refusal, its linearization record and M03's feasibility tolerance.

A leaf of `assessment.program` (E01 §4.12, §4.2.1): the report and the NLP verifier read these
three without importing the program, which imports the report. `assessment.program` re-exports
`Refusal` and `Linearization`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from openflowsheet.compile.casadi_backend import TwinMatrix


@dataclass(frozen=True)
class Refusal:
    """A typed refusal (or an `unsupported` result): never an exception to the caller (§4.12)."""

    code: str
    target: str = ""
    detail: str = ""
    kind: Literal["refusal", "unsupported"] = "refusal"

    def as_document(self) -> dict[str, Any]:
        return {"kind": self.kind, "code": self.code, "target": self.target, "detail": self.detail}


@dataclass(frozen=True)
class Linearization:
    values: Mapping[str, float]
    d_dx: TwinMatrix
    d_dp: TwinMatrix


def _feasibility_tolerance() -> float:
    """M03's V3 feasibility tolerance on scaled inequalities (§4.2.1), imported, never redefined.
    Imported here, not at module load, because `studies.nlp` will import this package."""
    from openflowsheet.studies.nlp.tolerances import TAU_FEAS  # noqa: PLC0415

    return float(TAU_FEAS)
