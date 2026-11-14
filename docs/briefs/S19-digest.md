# S19 design digest (generated at main d90b498f, 2026-11-14)

Trial scan with scope `src/openflowsheet/*` (the repo config's scope is application/ only): 282 files, debt 6370.9, repo health 7.3, brain functions 44, file smells 59.

## Debt per package

| package | debt | NLOC |
| --- | --- | --- |
| models | 1343.1 | 22150 |
| studies | 1257.8 | 15607 |
| orchestrator | 974.6 | 8355 |
| assessment | 677.0 | 6803 |
| numerics | 423.0 | 1972 |
| verify | 378.2 | 6634 |
| application | 301.8 | 18589 |
| thermo | 293.8 | 9453 |
| run | 257.6 | 1456 |
| graph | 164.6 | 1555 |
| messages | 129.0 | 1590 |
| units | 55.0 | 713 |
| adapters | 53.9 | 2583 |
| top | 23.0 | 673 |
| registry | 22.5 | 1240 |
| compile | 16.0 | 763 |
| ir | 0.0 | 0 |

## Files with debt >= 40 (path, NLOC, debt, health, smells)

| file | NLOC | debt | health | smells |
| --- | --- | --- | --- | --- |
| src/openflowsheet/orchestrator/region.py | 2137 | 415.6 | 1.0 | huge_file,duplication |
| src/openflowsheet/models/syn001/column.py | 1670 | 352.9 | 1.0 | large_file,duplication |
| src/openflowsheet/studies/trust_region/projection.py | 1343 | 272.9 | 1.0 | large_file |
| src/openflowsheet/run/compare.py | 478 | 156.9 | 3.3 |  |
| src/openflowsheet/models/revision_flowsheet.py | 748 | 153.6 | 4.9 |  |
| src/openflowsheet/numerics/newton.py | 700 | 146.4 | 7.3 |  |
| src/openflowsheet/numerics/anderson.py | 398 | 143.5 | 7.5 |  |
| src/openflowsheet/assessment/cost/sets.py | 521 | 128.4 | 4.7 |  |
| src/openflowsheet/numerics/ptc.py | 612 | 126.1 | 7.0 |  |
| src/openflowsheet/assessment/cost/contributor.py | 1028 | 123.4 | 2.8 | large_file |
| src/openflowsheet/verify/table.py | 1483 | 120.1 | 1.6 | large_file |
| src/openflowsheet/models/syn001/cascade.py | 1023 | 118.9 | 2.1 | large_file,duplication |
| src/openflowsheet/orchestrator/splits.py | 613 | 115.9 | 6.3 |  |
| src/openflowsheet/orchestrator/execution.py | 684 | 106.3 | 5.2 |  |
| src/openflowsheet/models/syn001/column_solve.py | 1254 | 101.1 | 3.4 | large_file,duplication |
| src/openflowsheet/studies/nlp/verification.py | 797 | 97.9 | 4.4 |  |
| src/openflowsheet/models/syn001/column_unit.py | 654 | 95.1 | 4.9 |  |
| src/openflowsheet/studies/surrogate/manifest.py | 625 | 94.9 | 5.2 |  |
| src/openflowsheet/studies/trust_region/study.py | 826 | 94.4 | 4.3 |  |
| src/openflowsheet/orchestrator/coupling.py | 337 | 92.9 | 7.5 |  |
| src/openflowsheet/assessment/sizing/families.py | 887 | 87.1 | 5.4 |  |
| src/openflowsheet/verify/checks.py | 884 | 84.7 | 6.1 |  |
| src/openflowsheet/studies/nlp/replay.py | 428 | 81.7 | 5.4 |  |
| src/openflowsheet/studies/nlp/revision.py | 694 | 79.6 | 6.8 |  |
| src/openflowsheet/run/identity.py | 166 | 76.4 | 7.7 |  |
| src/openflowsheet/models/syn001/column_blocks.py | 409 | 74.6 | 4.7 |  |
| src/openflowsheet/assessment/lca/inventory.py | 259 | 71.7 | 7.5 |  |
| src/openflowsheet/assessment/cost/forms.py | 557 | 70.6 | 7.2 |  |
| src/openflowsheet/verify/certificate.py | 1088 | 67.2 | 4.9 | large_file |
| src/openflowsheet/studies/nlp/request.py | 501 | 67.0 | 6.5 |  |
| src/openflowsheet/models/syn001/ph_kernel.py | 829 | 63.5 | 5.8 |  |
| src/openflowsheet/studies/trust_region/trf.py | 413 | 62.2 | 6.8 |  |
| src/openflowsheet/thermo/wilson_ig.py | 764 | 60.5 | 6.9 |  |
| src/openflowsheet/orchestrator/executor.py | 1057 | 60.4 | 5.0 | large_file,duplication |
| src/openflowsheet/graph/tear.py | 305 | 58.3 | 6.2 |  |
| src/openflowsheet/messages/render.py | 717 | 58.0 | 6.0 |  |
| src/openflowsheet/thermo/pr_c1.py | 730 | 55.7 | 4.6 | duplication |
| src/openflowsheet/messages/lint.py | 192 | 55.0 | 6.5 |  |
| src/openflowsheet/assessment/report.py | 253 | 54.3 | 7.2 |  |
| src/openflowsheet/thermo/coolprop_heos.py | 905 | 53.7 | 6.4 | duplication |
| src/openflowsheet/studies/nlp/revision_host.py | 670 | 51.5 | 8.0 |  |
| src/openflowsheet/units/__init__.py | 432 | 50.0 | 7.4 |  |
| src/openflowsheet/orchestrator/revision.py | 282 | 49.0 | 7.0 |  |
| src/openflowsheet/assessment/cost/derived.py | 158 | 47.1 | 7.7 |  |
| src/openflowsheet/studies/surrogate/study.py | 372 | 44.8 | 7.7 |  |
| src/openflowsheet/application/revision_run.py | 1111 | 44.6 | 6.6 | large_file |
| src/openflowsheet/application/binding.py | 920 | 43.6 | 7.0 |  |
| src/openflowsheet/models/syn001/cascade_solve.py | 623 | 43.0 | 5.1 | duplication |
| src/openflowsheet/models/__init__.py | 406 | 42.6 | 8.5 |  |
| src/openflowsheet/models/syn001/gamma_phi.py | 314 | 42.0 | 7.5 |  |

## Import cycles (module level, TYPE_CHECKING imports ignored, all nesting levels)

282 modules, 1721 import edges, 10 strongly connected components. Each edge: importer -> imported (file:line of the first import).

### Cycle 1: 17 modules, 51 edges

- models.syn001.admission -> models.syn001.tp_state (src/openflowsheet/models/syn001/admission.py:15)
- models.syn001.cascade -> models.syn001.equilibrium_form (src/openflowsheet/models/syn001/cascade.py:75)
- models.syn001.cascade -> models.syn001.gamma_phi (src/openflowsheet/models/syn001/cascade.py:76)
- models.syn001.cascade -> models.syn001.saturation_band (src/openflowsheet/models/syn001/cascade.py:77)
- models.syn001.cascade -> models.syn001.tp_state (src/openflowsheet/models/syn001/cascade.py:78)
- models.syn001.cascade -> orchestrator.region (src/openflowsheet/models/syn001/cascade.py:84)
- models.syn001.conversion_reactor -> models.syn001.admission (src/openflowsheet/models/syn001/conversion_reactor.py:88)
- models.syn001.conversion_reactor -> models.syn001.ph_kernel (src/openflowsheet/models/syn001/conversion_reactor.py:89)
- models.syn001.conversion_reactor -> models.syn001.tp_state (src/openflowsheet/models/syn001/conversion_reactor.py:96)
- models.syn001.equilibrium_form -> models.syn001.cascade (src/openflowsheet/models/syn001/equilibrium_form.py:130)
- models.syn001.flash -> models.syn001.equilibrium_form (src/openflowsheet/models/syn001/flash.py:73)
- models.syn001.flash -> models.syn001.tp_state (src/openflowsheet/models/syn001/flash.py:74)
- models.syn001.flowsheet -> models.syn001.flash (src/openflowsheet/models/syn001/flowsheet.py:41)
- models.syn001.flowsheet -> models.syn001.heater (src/openflowsheet/models/syn001/flowsheet.py:42)
- models.syn001.flowsheet -> models.syn001.mixer (src/openflowsheet/models/syn001/flowsheet.py:43)
- models.syn001.gamma_phi -> models.syn001.saturation_band (src/openflowsheet/models/syn001/gamma_phi.py:30)
- models.syn001.heater -> models.syn001.tp_state (src/openflowsheet/models/syn001/heater.py:81)
- models.syn001.kinetic_cstr -> models.syn001.conversion_reactor (src/openflowsheet/models/syn001/kinetic_cstr.py:82)
- models.syn001.kinetic_cstr -> models.syn001.ph_kernel (src/openflowsheet/models/syn001/kinetic_cstr.py:89)
- models.syn001.kinetic_cstr -> models.syn001.tp_state (src/openflowsheet/models/syn001/kinetic_cstr.py:90)
- models.syn001.mixer -> models.syn001.equilibrium_form (src/openflowsheet/models/syn001/mixer.py:105)
- models.syn001.mixer -> models.syn001.gamma_phi (src/openflowsheet/models/syn001/mixer.py:90)
- models.syn001.mixer -> models.syn001.tp_state (src/openflowsheet/models/syn001/mixer.py:106)
- models.syn001.ph_kernel -> models.syn001.equilibrium_form (src/openflowsheet/models/syn001/ph_kernel.py:67)
- models.syn001.ph_kernel -> models.syn001.gamma_phi (src/openflowsheet/models/syn001/ph_kernel.py:59)
- models.syn001.ph_kernel -> models.syn001.saturation_band (src/openflowsheet/models/syn001/ph_kernel.py:68)
- models.syn001.ph_kernel -> models.syn001.tp_state (src/openflowsheet/models/syn001/ph_kernel.py:73)
- models.syn001.saturation_band -> models.syn001.equilibrium_form (src/openflowsheet/models/syn001/saturation_band.py:37)
- models.syn001.saturation_band -> models.syn001.gamma_phi (src/openflowsheet/models/syn001/saturation_band.py:261)
- models.syn001.tp_state -> models.syn001.equilibrium_form (src/openflowsheet/models/syn001/tp_state.py:42)
- models.syn001.tp_state -> models.syn001.gamma_phi (src/openflowsheet/models/syn001/tp_state.py:40)
- models.syn001.tp_state -> models.syn001.saturation_band (src/openflowsheet/models/syn001/tp_state.py:44)
- orchestrator.mass -> models.syn001.flash (src/openflowsheet/orchestrator/mass.py:390)
- orchestrator.mass -> models.syn001.flowsheet (src/openflowsheet/orchestrator/mass.py:421)
- orchestrator.mass -> models.syn001.heater (src/openflowsheet/orchestrator/mass.py:390)
- orchestrator.mass -> models.syn001.kinetic_cstr (src/openflowsheet/orchestrator/mass.py:390)
- orchestrator.mass -> models.syn001.tp_state (src/openflowsheet/orchestrator/mass.py:331)
- orchestrator.region -> models.syn001.equilibrium_form (src/openflowsheet/orchestrator/region.py:87)
- orchestrator.region -> models.syn001.flash (src/openflowsheet/orchestrator/region.py:344)
- orchestrator.region -> models.syn001.flowsheet (src/openflowsheet/orchestrator/region.py:345)
- orchestrator.region -> models.syn001.gamma_phi (src/openflowsheet/orchestrator/region.py:81)
- orchestrator.region -> models.syn001.ph_kernel (src/openflowsheet/orchestrator/region.py:88)
- orchestrator.region -> models.syn001.saturation_band (src/openflowsheet/orchestrator/region.py:89)
- orchestrator.region -> models.syn001.tp_state (src/openflowsheet/orchestrator/region.py:90)
- orchestrator.region -> orchestrator.mass (src/openflowsheet/orchestrator/region.py:111)
- orchestrator.region -> verify.checks (src/openflowsheet/orchestrator/region.py:786)
- verify.checks -> models.syn001.flash (src/openflowsheet/verify/checks.py:31)
- verify.checks -> models.syn001.flowsheet (src/openflowsheet/verify/checks.py:32)
- verify.checks -> models.syn001.tp_state (src/openflowsheet/verify/checks.py:38)
- verify.checks -> verify.saturation (src/openflowsheet/verify/checks.py:715)
- verify.saturation -> verify.checks (src/openflowsheet/verify/saturation.py:33)

### Cycle 2: 4 modules, 6 edges

- messages.audit -> messages.catalogue (src/openflowsheet/messages/audit.py:29)
- messages.catalogue -> messages.audit (src/openflowsheet/messages/catalogue.py:274)
- messages.catalogue -> registry (src/openflowsheet/messages/catalogue.py:345)
- registry -> messages.catalogue (src/openflowsheet/registry/__init__.py:784)
- registry -> registry.discovery (src/openflowsheet/registry/__init__.py:53)
- registry.discovery -> messages.catalogue (src/openflowsheet/registry/discovery.py:299)

### Cycle 3: 3 modules, 4 edges

- verify.gamma_phi_units -> verify.table (src/openflowsheet/verify/gamma_phi_units.py:65)
- verify.table -> verify.gamma_phi_units (src/openflowsheet/verify/table.py:1728)
- verify.table -> verify.thermal (src/openflowsheet/verify/table.py:1681)
- verify.thermal -> verify.table (src/openflowsheet/verify/thermal.py:43)

### Cycle 4: 3 modules, 4 edges

- assessment.program -> assessment.report (src/openflowsheet/assessment/program.py:823)
- assessment.program -> studies.nlp.verification (src/openflowsheet/assessment/program.py:451)
- assessment.report -> assessment.program (src/openflowsheet/assessment/report.py:29)
- studies.nlp.verification -> assessment.program (src/openflowsheet/studies/nlp/verification.py:45)

### Cycle 5: 3 modules, 4 edges

- application.revision_routes -> application.revision_run (src/openflowsheet/application/revision_routes.py:20)
- application.revision_run -> application.validation (src/openflowsheet/application/revision_run.py:381)
- application.validation -> application.revision_routes (src/openflowsheet/application/validation.py:294)
- application.validation -> application.revision_run (src/openflowsheet/application/validation.py:529)

### Cycle 6: 2 modules, 2 edges

- units -> units.display (src/openflowsheet/units/__init__.py:616)
- units.display -> units (src/openflowsheet/units/display.py:30)

### Cycle 7: 2 modules, 2 edges

- models.syn001.column_blocks -> models.syn001.column_solve (src/openflowsheet/models/syn001/column_blocks.py:33)
- models.syn001.column_solve -> models.syn001.column_blocks (src/openflowsheet/models/syn001/column_solve.py:1512)

### Cycle 8: 2 modules, 2 edges

- application.contract -> application.types (src/openflowsheet/application/contract.py:20)
- application.types -> application.contract (src/openflowsheet/application/types.py:1392)

### Cycle 9: 2 modules, 2 edges

- studies.surrogate.manifest -> studies.surrogate.study (src/openflowsheet/studies/surrogate/manifest.py:76)
- studies.surrogate.study -> studies.surrogate.manifest (src/openflowsheet/studies/surrogate/study.py:423)

### Cycle 10: 2 modules, 2 edges

- assessment.sizing -> assessment.sizing.families (src/openflowsheet/assessment/sizing/__init__.py:606)
- assessment.sizing.families -> assessment.sizing (src/openflowsheet/assessment/sizing/families.py:30)

## Package-level import edges (count of module edges)

- adapters -> _files: 1
- adapters -> canonical: 7
- adapters -> compiled: 1
- adapters -> models: 5
- adapters -> orchestrator: 2
- adapters -> resources: 1
- adapters -> thermo: 2
- application -> _files: 1
- application -> adapters: 20
- application -> canonical: 21
- application -> compile: 4
- application -> compiled: 10
- application -> graph: 11
- application -> messages: 21
- application -> models: 88
- application -> orchestrator: 35
- application -> registry: 6
- application -> resources: 5
- application -> run: 23
- application -> studies: 30
- application -> thermo: 20
- application -> units: 10
- application -> verify: 14
- assessment -> application: 1
- assessment -> canonical: 4
- assessment -> compile: 18
- assessment -> compiled: 2
- assessment -> models: 15
- assessment -> studies: 1
- assessment -> thermo: 7
- compile -> canonical: 1
- compile -> compiled: 2
- graph -> compile: 3
- messages -> canonical: 1
- messages -> registry: 1
- messages -> resources: 1
- messages -> units: 1
- models -> canonical: 28
- models -> compile: 38
- models -> compiled: 48
- models -> messages: 1
- models -> orchestrator: 14
- models -> thermo: 66
- models -> units: 1
- numerics -> canonical: 3
- numerics -> compile: 1
- numerics -> orchestrator: 3
- orchestrator -> canonical: 8
- orchestrator -> compile: 11
- orchestrator -> compiled: 8
- orchestrator -> graph: 8
- orchestrator -> messages: 2
- orchestrator -> models: 33
- orchestrator -> numerics: 15
- orchestrator -> run: 1
- orchestrator -> thermo: 8
- orchestrator -> verify: 1
- registry -> canonical: 3
- registry -> messages: 3
- registry -> resources: 2
- run -> application: 2
- run -> canonical: 4
- run -> graph: 2
- run -> models: 1
- run -> orchestrator: 2
- run -> resources: 3
- run -> verify: 2
- serialize -> canonical: 1
- serialize -> compiled: 1
- studies -> adapters: 9
- studies -> assessment: 8
- studies -> canonical: 11
- studies -> compile: 29
- studies -> compiled: 6
- studies -> models: 34
- studies -> numerics: 9
- studies -> orchestrator: 22
- studies -> resources: 2
- studies -> run: 6
- studies -> thermo: 10
- studies -> verify: 12
- thermo -> canonical: 2
- thermo -> compiled: 9
- thermo -> resources: 3
- units -> canonical: 1
- verify -> canonical: 1
- verify -> compile: 6
- verify -> compiled: 8
- verify -> messages: 2
- verify -> models: 41
- verify -> numerics: 4
- verify -> orchestrator: 4
- verify -> resources: 1
- verify -> run: 1
- verify -> thermo: 20
- verify -> units: 1
