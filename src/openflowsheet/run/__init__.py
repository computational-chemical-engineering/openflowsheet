"""Runs, their immutable manifests and replay, introduced by package K05 (plan §4.2 row K05).

A *run* is one execution of a solve and its verification: the plan, the trace, the certificate
or the failure bundle, and the environment they happened in. The `RunManifest` pins that
environment so that a later difference is **attributable** rather than mysterious, and the
replay bundle is the archive a third party can re-run or, failing that, inspect.

**The thing K05 must not do is quietly succeed.** Blueprint §8.3 names three reports — exact
replay, compatible reproduction, inspected archived results — and ADR 0007 D4 makes the choice
between them a decision taken *before* anything runs, from the recorded environment against the
current one. A changed dependency therefore never produces a silent pass: it moves the mode to
`inspected_archived_results` and the verdict to `NOT_RUN`, which is gate G05's first clause.

**And timing is never structural** (plan §4.2 K05, blueprint D20). A run records how long it
took, because that is useful; nothing that takes a hash ever sees it.
"""
