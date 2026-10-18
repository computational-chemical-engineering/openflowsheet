# `examples/`

Executable tutorials and the inspectable end-to-end demonstrations of the runtime
(blueprint §15, §16). An example here must run against the public application contract only,
with no private path that bypasses validation.

Nothing lives here yet. The first example is introduced by **K06**: the complete local
Python/CLI flash-recycle demonstration required by gate **G06** — an end-to-end solve that is
inspectable without unrelated code, with its trace, balance checks, final Jacobian evidence, a
deliberately failing companion case, and replay from a pinned bundle.

Later contributions: the bounded agent-workflow tasks of **T07**, the real reactor refinement
journey of **M07**, and the diagnostic web-shell walkthroughs of **M06**.

An example is a demonstration, never gate evidence by itself: release claims come from the
registered benchmark cases and the evidence manifests (plan §5.1, §6).

**The reference journey (M07).** `scripts/m07_journey.py run` writes the journey's record and
`render` its report, `journey.md` (M07 spec §6.2, ADR 0041): one decision taken through four
rungs of fidelity, with its limits stated. The report is a demonstration of a workflow on a
registered test configuration, never gate evidence by itself; nothing in it is validated against
plant data.
