"""The worker ↔ child protocol of the isolation profile `external-subprocess-v1` (M02 design note
§2.3, ADR 0033 D2).

One attempt is one child. The worker writes one JSON line to the child's stdin and keeps stdin
open for the whole attempt: it is the child's lifeline. The child answers with one file,
`result.json`, written atomically in its private working directory, and an exit code. Every
constant here is mirrored as a literal in each child script (`adapters/pymrm/child.py`,
`tests/support/synthetic_child.py`), which import nothing of this package; a test asserts the
literals are equal.
"""

from __future__ import annotations

from typing import Final

#: The protocol's version, carried in every request line and every `result.json`.
PROTOCOL_VERSION: Final = 1
#: The isolation profile this protocol implements (blueprint §11.3): **not a sandbox**.
ISOLATION_PROFILE: Final = "external-subprocess-v1"

#: The child's exit codes (§2.3 step 4). Any other code, or a signal, is `crashed`.
EXIT_OK: Final = 0
#: The child's stdin reached end of file: the worker is gone (layer L3).
EXIT_LIFELINE_LOST: Final = 70
#: The child's own deadline, `deadline_s` + `SELF_DEADLINE_MARGIN_S`, passed (layer L3's backstop).
EXIT_SELF_DEADLINE: Final = 71
#: The child's environment is not the one the request expects (one line of reason on stderr).
EXIT_ENVIRONMENT_MISMATCH: Final = 72

#: The child's one output file, its temporary name, and the two log files, in the attempt directory.
RESULT_FILE: Final = "result.json"
RESULT_TEMPORARY: Final = "result.json.tmp"
STDOUT_FILE: Final = "child.stdout"
STDERR_FILE: Final = "child.stderr"

#: The argument that makes the child verify its environment and report its fingerprint (§2.4).
HANDSHAKE_ARGUMENT: Final = "--handshake"
#: `result.json` `outcome` values: an evaluation's two answers and the handshake's.
OUTCOME_OUTLET: Final = "outlet"
OUTCOME_NOT_ACCEPTED: Final = "not_accepted"
OUTCOME_HANDSHAKE: Final = "handshake"

#: The child exits `EXIT_SELF_DEADLINE` this long after `deadline_s` (production margin).
SELF_DEADLINE_MARGIN_S: Final = 30.0
#: A test-hook environment variable that overrides the margin (G3 (f)). It reaches a child only
#: through the launcher's Python-only `test_environment` argument; no API, CLI or variant sets it.
DEADLINE_MARGIN_VARIABLE: Final = "OFS_TEST_DEADLINE_MARGIN_S"

#: Layer L1 (§2.3 steps 5-6): the adapter polls the child this often, and waits this long between
#: SIGTERM and SIGKILL unless the variant says otherwise.
POLL_S: Final = 0.2
KILL_GRACE_S: Final = 2.0
