# Your first flowsheet

A flowsheet in OpenFlowsheet is a **revision**: one JSON document (`ProcessRevision`) that names
the components and their property basis, the unit instances, the material connections between
their ports, and the specifications that fix the degrees of freedom. This tutorial writes the
quickstart's Rankine cycle member by member and solves it from Python.

## 1. The component set selects the property basis

```python
component_set = {
    "record_source": "benchmarks/s05/components.yaml",   # IAPWS-95 water
    "components": ["H2O"],
}
```

`record_source` is a registry key, not a file you need on disk: each registered value selects one
property basis ([Property bases](../guide/property-bases.md)). Every stream of the flowsheet carries
these components.

## 2. Unit instances

Each instance names a model from the [unit catalogue](../guide/units.md), a semantic role from the
schema's vocabulary, its parameters as quantities, and a policy label:

```python
def unit(unit_id, model, role, **parameters):
    return {"id": unit_id,
            "model": {"id": model, "version": "0.0.0-declared", "artifact_ref": None},
            "semantic_role": role, "parameters": parameters,
            "policy": {"fidelity": "tutorial", "validity": "tutorial"}}

def efficiency(value):
    return {"value": value, "unit": "1", "dimension": [0, 0, 0, 0, 0, 0, 0],
            "kind": "dimensionless", "meaning": "isentropic efficiency", "role": "fixed"}

instances = [
    unit("F", "syn001.feed_source", "feed"),
    unit("P", "thermal.pump", "pump", efficiency=efficiency(0.75)),
    unit("B", "thermal.heater", "heater"),
    unit("T", "thermal.turbine", "turbine", efficiency=efficiency(0.85)),
    unit("C", "thermal.heater", "heater",
         outlet_vapor_fraction={**efficiency(0.0), "meaning": "saturated liquid out"}),
    unit("K", "syn001.product_sink", "product_sink"),
]
```

The feed source and product sink are routing models that bind on every basis but the
ammonia loop's. The condenser is a heater in *quality mode*: `outlet_vapor_fraction = 0` asks for
saturated liquid at its outlet. Each unit carries the role of its kind, the turbine `turbine`;
roles are descriptive and the binder does not read them.

## 3. Connections

A connection joins an outlet port to an inlet port and declares which phases the stream may
carry:

```python
def stream(stream_id, source, target, phase):
    return {"id": stream_id, "kind": "material",
            "from": {"instance": source[0], "port": source[1]},
            "to": {"instance": target[0], "port": target[1]},
            "state_definition": "nTP-v1", "component_mapping": "revision_component_set",
            "phase_capability": phase, "notes": stream_id}

connections = [
    stream("S1", ("F", "outlet"), ("P", "inlet"), "liquid"),
    stream("S2", ("P", "outlet"), ("B", "inlet"), "liquid"),
    stream("S3", ("B", "outlet"), ("T", "inlet"), "vapor"),
    stream("S4", ("T", "outlet"), ("C", "inlet"), "vapor_liquid"),
    stream("S5", ("C", "outlet"), ("K", "inlet"), "vapor_liquid"),
]
```

A stream's state is `nTP-v1`: the component molar flows `n`, the temperature `T` and the pressure
`P`.

## 4. Specifications

Specifications fix the feed's state and one value per unit degree of freedom. Each has a target, a
kind, a value with its unit, and the tolerance the verifier will hold it to:

```python
TOLERANCE = {"molar_flow": {"absolute": 1e-9, "relative": 1e-8, "scale": 3.0},
             "temperature": {"absolute": 1e-6}, "pressure": {"absolute": 0.01}}
SI = {"molar_flow": "mol/s", "temperature": "K", "pressure": "Pa"}

def fix(spec_id, object_type, object_id, path, value, kind, component=None):
    target = {"object_type": object_type, "object_id": object_id, "path": path}
    if component is not None:
        target["component"] = component
    return {"id": spec_id, "target": target, "kind": kind, "unit": SI[kind], "value": value,
            "tolerance": TOLERANCE[kind], "role": "fixed", "provenance": "tutorial"}

specifications = [
    fix("feed-n", "connection", "S1", "state.n", 1.0, "molar_flow", component="H2O"),
    fix("feed-T", "connection", "S1", "state.T", 318.15, "temperature"),
    fix("feed-P", "connection", "S1", "state.P", 1.0e4, "pressure"),
    fix("pump-P", "instance", "P", "outlet.P", 3.0e6, "pressure"),
    fix("boiler-T", "instance", "B", "outlet.T", 673.15, "temperature"),
    fix("turbine-P", "instance", "T", "outlet.P", 1.0e4, "pressure"),
]
```

Values may also be written in the registered non-SI spellings — `bar`, `kPa`, `MPa`, `degC`,
`kmol/h` and others — and are converted to SI at validation ([Concepts](../guide/concepts.md#units)).
`list_models` gives, for every pin of every model, the targets that can fix it.

## 5. The document, committed and solved

```python
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.types import Change, Edit

revision = {
    "schema_version": 1, "revision_id": "rankine", "parent_revision": None,
    "title": "Rankine cycle", "description": "first-flowsheet tutorial",
    "component_set": component_set, "instances": instances,
    "connections": connections, "specifications": specifications,
    "provenance": {"actor": "tutorial", "operation": "create",
                   "timestamp": "2026-10-29T00:00:00Z", "source_references": [], "notes": ""},
}

with LocalApplication.in_memory() as app:
    edits = tuple(Edit("set", (member,), value) for member, value in revision.items())
    committed = app.commit_change(Change(edits=edits), None, "create-rankine")
    report = app.validate(committed.revision_id, "simulation")
    for check in report.checks:
        if check.result != "PASS":
            print(check.id, check.result, check.message)
    run = app.solve(committed.revision_id, "default")
    print(run.outcome, run.verification_status)
```

`commit_change` takes the edits, the revision you expect to be the head (`None` for the first —
a stale expectation is a conflict, never a silent overwrite) and an idempotency key (the same key
and request replays the first answer). `validate` reports `INVALID`, `DRAFT` or
`READY_FOR_SIMULATION`, with every check and the objects it implicates; `solve` refuses anything
that is not ready.

The [Rankine example](../examples/rankine-cycle.ipynb) continues from here: it reads the state,
computes the cycle efficiency and prints the certificate's statements.
