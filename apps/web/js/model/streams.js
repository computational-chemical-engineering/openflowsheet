// Streams and units at a run's state (M06 design note §6.6, §5.6 rule 6).
//
// A join of three records by id — the revision's connections and instances, `inspect_structure`'s
// column index, and the run's `solution-state.json` variables — with no unit conversion: each
// value is shown in the SI unit its column names. A stream row is a graph connection with its
// component flows `n`, `T` and `P`; every other column (a coordinate-less unit variable such as a
// duty, or any coordinate beyond n/T/P) is listed under its owner instance, never dropped.

const STREAM_COORDINATES = new Set(["n", "T", "P"]);

function isStreamColumn(column) {
  return (
    column.connection !== null &&
    column.connection !== undefined &&
    STREAM_COORDINATES.has(column.coordinate) &&
    (column.coordinate !== "n" || typeof column.component === "string")
  );
}

// The component order of a revision (its component set), for labelling.
export function componentsOf(revision) {
  return [...(revision?.component_set?.components ?? [])];
}

// `{components, rows, units}`:
// - `rows`: one per connection — the revision's, in its order, then any connection the column
//   index names that the revision does not contain (`inRevision: false`, under the binder's id);
//   each `{connection, inRevision, from, to, n: {component: cell}, T: cell, P: cell}`, a cell
//   `{column, value, si_unit}` or null where the index has no such column;
// - `units`: `[{instance, columns: [cell]}]` of every other column, in the revision's instance
//   order, then any owner the revision does not contain.
// `variables` is the run's `solution-state.json` `variables` (null: no state recorded, every
// value undefined).
export function streamTable(revision, columns, variables) {
  const components = componentsOf(revision);
  const values = variables ?? null;
  const cell = (column) =>
    column
      ? {
          column: column.column_id,
          value: values === null ? undefined : values[column.column_id],
          si_unit: column.si_unit,
        }
      : null;
  const byConnection = new Map();
  const byOwner = new Map();
  for (const column of columns ?? []) {
    if (isStreamColumn(column)) {
      if (!byConnection.has(column.connection)) byConnection.set(column.connection, []);
      byConnection.get(column.connection).push(column);
    } else {
      const owner = column.owner_instance ?? null;
      if (!byOwner.has(owner)) byOwner.set(owner, []);
      byOwner.get(owner).push(column);
    }
  }
  const connections = revision?.connections ?? [];
  const order = connections.map((connection) => connection.id);
  for (const id of byConnection.keys()) if (!order.includes(id)) order.push(id);
  const rows = order.map((id) => {
    const declared = connections.find((connection) => connection.id === id) ?? null;
    const found = byConnection.get(id) ?? [];
    const n = {};
    for (const component of components) {
      n[component] = cell(found.find((c) => c.coordinate === "n" && c.component === component));
    }
    for (const column of found) {
      if (column.coordinate === "n" && !(column.component in n)) n[column.component] = cell(column);
    }
    return {
      connection: id,
      inRevision: declared !== null,
      from: declared?.from ?? null,
      to: declared?.to ?? null,
      n,
      T: cell(found.find((c) => c.coordinate === "T")),
      P: cell(found.find((c) => c.coordinate === "P")),
    };
  });
  const owners = (revision?.instances ?? []).map((instance) => instance.id);
  for (const owner of byOwner.keys()) if (!owners.includes(owner)) owners.push(owner);
  const units = owners
    .filter((owner) => byOwner.has(owner))
    .map((owner) => ({ instance: owner, columns: byOwner.get(owner).map(cell) }));
  return { components, rows, units };
}

// The `list_models` entry of `modelId`, or null.
export function modelSignature(models, modelId) {
  return (models?.models ?? []).find((model) => model.model_id === modelId) ?? null;
}

// A unit panel: the instance, its model id, and the model's `ports`, `pins`, `required` and
// `zero` as `list_models` gives them; a quantity the model does not have (an empty list) is
// null, which the view reads "not applicable". `signature` null: the server lists no such model.
export function unitPanel(instance, signature) {
  const listed = (key) => {
    const value = signature?.[key];
    return Array.isArray(value) && value.length > 0 ? value : null;
  };
  return {
    instance: instance.id,
    model: instance.model?.id ?? null,
    listed: signature !== null,
    ports: listed("ports"),
    pins: listed("pins"),
    required: listed("required"),
    zero: listed("zero"),
  };
}
