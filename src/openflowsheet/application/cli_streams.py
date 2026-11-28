"""The `streams` command's parts that need nothing of the command line's own (ST §6.3; ADR 0075
D7.6, D9): a bundle directory's refusal and display preference as the `ApiError`s
`get_stream_table` gives, a job's page request, and the written table. Moved verbatim from
`application.cli` (X06 decision X06-CI1-6); `cli.command_streams` calls them.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openflowsheet.application.errors import ApiError
    from openflowsheet.units.display import DisplayUnits


def stream_table_refusal(code: str, message: str, detail: Mapping[str, Any]) -> ApiError:
    """A `StreamTableError` of a bundle directory as the `ApiError` it maps to (§6.1's codes); the
    detail members a directory cannot give (`null`, D1-14) are left out."""
    from openflowsheet.application.errors import api_error

    given = {key: value for key, value in detail.items() if value is not None}
    if code == "not_found":
        return api_error("not_found", message, **given).error
    if code == "unsupported":
        return api_error("unsupported", message, **given).error
    return api_error("internal_error", message, **given).error


def bundle_display_units(text: str) -> DisplayUnits | ApiError:
    """`--display-units` of a bundle directory: the preference resolved without an ambient
    pressure (a directory has no project; X04 decision D-8), or its refusal as the `ApiError`
    `get_stream_table` raises for it (ADR 0075 D9). The request schema's bound on the member
    (1 to 1024 characters) comes first and refuses as `dispatch` does (X04 review S4)."""
    from openflowsheet.application.documents import validate_inline
    from openflowsheet.application.errors import api_error
    from openflowsheet.application.operations import OPERATIONS
    from openflowsheet.schema_check import DocumentSchemaError
    from openflowsheet.units.display import DisplayUnitsError, parse_display_units

    operation = OPERATIONS["get_stream_table"]
    member = {
        "type": "object",
        "properties": {"display_units": operation.request_schema["properties"]["display_units"]},
    }
    try:
        validate_inline(operation.name, member, {"display_units": text})
    except DocumentSchemaError as error:
        return api_error("invalid_request", error.message, pointer=error.pointer).error
    try:
        return parse_display_units(text, None)
    except DisplayUnitsError as error:
        pointer = error.pointer
        detail: dict[str, Any] = (
            {"pointer": pointer} if pointer is not None else {"reason": error.message}
        )
        return api_error(error.api_error, error.message, **detail).error


def stream_table_request(
    arguments: argparse.Namespace, pointer: str, depth: int, cursor: str | None, limit: int
) -> dict[str, Any]:
    """`streams`' `get_stream_table` request for one page of `--job`'s table: the job, pointer,
    depth and limit, then the cursor when there is one and `--display-units` when given."""
    request: dict[str, Any] = {
        "job_id": arguments.job,
        "pointer": pointer,
        "depth": depth,
        "limit": limit,
    }
    if cursor is not None:
        request["cursor"] = cursor
    if arguments.display_units is not None:
        request["display_units"] = arguments.display_units
    return request


def write_stream_table(document: dict[str, Any], arguments: argparse.Namespace) -> None:
    """`streams`' output: the table rendered in `--format` (text, JSON or CSV), written to stdout,
    or to the file `--output` names."""
    from openflowsheet.application import stream_table_format

    render = {
        "text": stream_table_format.to_text,
        "json": stream_table_format.to_json,
        "csv": stream_table_format.to_csv,
    }[arguments.format]
    text = render(document)
    if arguments.output is None:
        sys.stdout.write(text)
    else:
        with open(arguments.output, "w", encoding="utf-8", newline="") as out:
            out.write(text)
