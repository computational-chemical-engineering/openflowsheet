"""The application's one error vocabulary (ADR 0076 I-9, S17 D3).

`ApiError` is the one error shape (T07 design note §5.8) and `ApiErrorCode` its codes, each with
its HTTP status. `ApplicationError` (§4.2) carries an `ApiError` out of a contract call;
`api_error` builds one, ready to raise, and records its caller's module for MSG's audit.
`SolveFailedError` is `RunResult.raise_for_outcome`'s (MSG §3.4). Validation's own refusals
(`task_unsupported`, `nlp_solver_unavailable`, `optimization_request_missing`) are built here.
It imports no application module at run time, so every application module can import it.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Literal, Self

# ADR 0076 I-14: importing the registry installs the catalogue's before-freeze hook.
import openflowsheet.registry  # noqa: F401
from openflowsheet.messages import audit
from openflowsheet.schema_check import validate_document

if TYPE_CHECKING:
    from openflowsheet.application.job_records import RunResult


ApiErrorCode = Literal[
    "invalid_request",
    "document_not_canonical",
    "unauthenticated",
    "forbidden",
    "not_found",
    "idempotency_key_reused",
    "not_ready",
    "revision_not_ready",
    "revision_unsupported",
    "verification_weakening_refused",
    "budget_exceeds_ceiling",
    "limit_exceeded",
    "unsupported",
    "internal_error",
    # ADR 0035 D3 (M02 design note §6.2): a promotion whose replacement check failed.
    "model_replacement_incompatible",
]


#: §5.8's HTTP status of each code.
API_ERROR_HTTP_STATUS: Final[Mapping[str, int]] = {
    "invalid_request": 422,
    "document_not_canonical": 422,
    "unauthenticated": 401,
    "forbidden": 403,
    "not_found": 404,
    "idempotency_key_reused": 409,
    "not_ready": 409,
    "revision_not_ready": 422,
    "revision_unsupported": 422,
    "verification_weakening_refused": 422,
    "budget_exceeds_ceiling": 422,
    "limit_exceeded": 429,
    "unsupported": 501,
    "internal_error": 500,
    "model_replacement_incompatible": 422,
}


@dataclass(frozen=True)
class ApiError:
    """§5.8: the one error shape. Domain outcomes are results, never an `ApiError`."""

    code: ApiErrorCode
    message: str
    retryable: bool
    detail: Mapping[str, Any] = field(default_factory=dict)

    @property
    def http_status(self) -> int:
        return API_ERROR_HTTP_STATUS[self.code]

    @property
    def explanation(self) -> dict[str, Any]:
        """MSG §3.3: the explanation document a transport attaches as `detail.explanation` —
        the one this error carries when it was projected, else rendered now (surface null).
        A property, never a field: it is not in `as_document()` and is stored nowhere (I2)."""
        carried = self.detail.get("explanation")
        if isinstance(carried, Mapping):
            return dict(carried)
        return self.render_explanation()

    def render_explanation(self, surface: Literal["python", "cli"] | None = None) -> dict[str, Any]:
        """The explanation rendered from the machine document (any carried one ignored)."""
        from openflowsheet.messages.render import RenderContext, render_error

        detail = {name: value for name, value in self.detail.items() if name != "explanation"}
        return render_error(
            {"code": self.code, "message": self.message, "detail": detail},
            context=RenderContext(surface=surface),
        )

    def as_document(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "detail": dict(self.detail),
            "retryable": self.retryable,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        validate_document("api-error.schema.json", document)
        return cls._build(document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            code=document["code"],
            message=document["message"],
            retryable=document["retryable"],
            detail=dict(document["detail"]),
        )


class ApplicationError(Exception):
    """§4.2: a non-domain outcome of a contract call. `error` is the typed `ApiError`."""

    def __init__(self, error: ApiError) -> None:
        super().__init__(f"{error.code}: {error.message}")
        self.error = error

    @property
    def code(self) -> ApiErrorCode:
        return self.error.code

    @property
    def explanation(self) -> dict[str, Any]:
        """MSG §3.3: the error's explanation as Python shows it (surface `python`)."""
        return self.error.render_explanation("python")

    def __str__(self) -> str:
        """MSG §4.5: the layered text; its last line is `args[0]`, `"<code>: <message>"`, the
        pre-MSG string, so an unanchored match on that string still matches. Never convert
        this error to a document through `str()` (§4.7): use `error.as_document()`."""
        from openflowsheet.messages.text import format_text

        return format_text(self.explanation, str(self.args[0]))


def api_error(
    code: ApiErrorCode, message: str, /, *, retryable: bool = False, **detail: Any
) -> ApplicationError:
    """An `ApplicationError` of `code`, ready to raise. `code` and `message` are positional, so
    a `detail` member may be named `code` (`explain`'s `not_found`, ADR 0058 D7)."""
    if audit.auditor is not None:  # MSG-G3: the codes this machine text carries have entries
        _observe(code, message, detail, sys._getframe(1).f_globals.get("__name__", ""))
    return ApplicationError(
        ApiError(code=code, message=message, retryable=retryable, detail=detail)
    )


def _observe(code: str, message: str, detail: dict[str, Any], caller: str) -> None:
    auditor = audit.auditor
    assert auditor is not None
    auditor.code(code, caller)
    auditor.observe(message, caller)
    reason = detail.get("reason")
    if isinstance(reason, str):
        auditor.observe(reason, caller)


class SolveFailedError(Exception):
    """MSG §3.4: `RunResult.raise_for_outcome` on a run that did not end converged. Not an
    `ApplicationError`: a domain outcome is not an `ApiError`. `result` is the run result; the
    text is the failure's layered text (or, for a job that ended without a failure bundle, its
    status's)."""

    def __init__(self, result: RunResult) -> None:
        failure = result.failure
        machine = (
            f"{failure.outcome}: {failure.message or failure.outcome}"
            if failure is not None
            else f"{result.job_status}: job {result.job_id}"
        )
        super().__init__(machine)
        self.result = result

    def __str__(self) -> str:
        failure = self.result.failure
        if failure is not None:
            return str(failure)
        from openflowsheet.messages.render import RenderContext, render_code
        from openflowsheet.messages.text import format_text

        explanation = render_code(
            self.result.job_status,
            context=RenderContext(surface="python", job_id=self.result.job_id),
        )
        return format_text(explanation, str(self.args[0]))


def task_unsupported(task: str) -> ApplicationError:
    """U05's refusal of a task v0.1 does not validate for, ready to raise (T08 review 2, Ruling 1).
    `LocalApplication.validate` raises it audited, before reading the revision."""
    return api_error("unsupported", f"task_unsupported({task})", pointer="/task")


def nlp_solver_unavailable() -> ApplicationError:
    """OPT design §4.11 (ADR 0071 D8, D10): `validate(task="optimization")` where no audited NLP
    solver is available — ADR 0019's `unsupported`, `nlp_solver_unavailable`, pointer `/task`,
    raised before the revision is read (U05's place). The message is the same on every platform
    (D-16); the probe's detail, which names the platform, is the report reason's."""
    return api_error("unsupported", "nlp_solver_unavailable", pointer="/task")


def optimization_request_missing() -> ApplicationError:
    """OPT design §4.11: `task="optimization"` without an `optimization` request."""
    return api_error(
        "invalid_request",
        "task optimization needs an optimization request",
        pointer="/optimization",
    )
