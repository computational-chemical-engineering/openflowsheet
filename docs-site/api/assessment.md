# Assessment (cost and LCA)

The assessment layer computes cost and life-cycle impact as functions of a solved, verified state
(see [Cost estimation and LCA](../guide/assessment.md)). It is a Python library layer: the CLI,
HTTP and MCP interfaces do not offer it yet. A typical sequence, as in the
[cost and climate impact example](../examples/rankine-cost-and-gwp.ipynb):

```python
from openflowsheet.application.revision_binding import bind_revision_flowsheet
from openflowsheet.assessment.program import AssessmentProgram
from openflowsheet.assessment.spec import load_assessment
from openflowsheet.assessment.views import view_of
from openflowsheet.canonical import state_sha256

binding = bind_revision_flowsheet(revision)          # the solved revision document
program = AssessmentProgram.build(
    view_of(binding.flowsheet), binding.spec, load_assessment(document), state
)
report = program.report(state, state_sha256=state_sha256(state, binding.spec.variable_ids))
```

`revision` and `state` are the `revision.json` and `solution-state.json` of the run's replay
bundle. Unsupported requests come back as a typed `Refusal`; they are not raised.

## The document

::: openflowsheet.assessment.spec.load_assessment

::: openflowsheet.assessment.spec.AssessmentSpec

::: openflowsheet.assessment.spec.AssessmentDocumentError

## The flowsheet's view

::: openflowsheet.assessment.views.view_of

## The program

::: openflowsheet.assessment.program.AssessmentProgram
    options:
      members:
        - build
        - evaluate
        - linearize
        - report
        - select

::: openflowsheet.assessment.program.Refusal

::: openflowsheet.assessment.program.Limitation

::: openflowsheet.assessment.report.build_report

## Sensitivities

::: openflowsheet.studies.assessment.assessment_sensitivity

::: openflowsheet.studies.assessment.AssessmentSensitivity
    options:
      members: false

::: openflowsheet.studies.assessment.revision_sensitivity_host

::: openflowsheet.studies.assessment.trf_objective_from_assessment

## Building unit-score tables (the `lca` extra)

These functions run only where `bw2data` and `bw2calc` are installed; without them each returns
`UNSUPPORTED(LCA_ENGINE_UNAVAILABLE)`. They never run inside a solve, an optimisation or a replay.

::: openflowsheet.assessment.lca.brightway.available

::: openflowsheet.assessment.lca.brightway.build_unit_score_table

::: openflowsheet.assessment.lca.brightway.build_direct_factor_table

::: openflowsheet.assessment.lca.brightway.foreground_check
