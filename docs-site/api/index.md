# Python API

The public Python surface is the application contract: one class that opens a project, the request
and result types it takes and returns, the validation report, the error it raises, the operations
table every transport shares, and the replay report. Everything else in the package is internal and
may change without notice.

```python
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.types import Change, Edit
```

| Page | Contents |
| --- | --- |
| [LocalApplication](local.md) | open a project; the `Application`, job-control and inspection operations |
| [Requests and results](types.md) | `Change`, `Edit`, `RunResult`, `TransactionResult`, jobs, project and registry views |
| [Validation](validation.md) | `ValidationReport`, `Check` |
| [Errors and pages](contract.md) | `ApplicationError`, `ApiError`, `Page`, `Projection` |
| [Operations table](operations.md) | `OPERATIONS` and `dispatch`, the one path from a request document to a response |
| [Replay](replay.md) | `ReplayReport`, `ReplayPolicy` |

Every result type has `as_document()`, which returns exactly the JSON document the CLI prints and
HTTP and MCP send. The documents' JSON Schemas are in the repository's `schemas/` directory.
