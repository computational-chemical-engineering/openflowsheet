// The flowsheet drawing of a revision (M06 design note §6.1 "Layout", §5.6 rule 5).
//
// Nodes are the revision's instances; edges its connections `from.instance → to.instance`.
// (1) Back edges: a depth-first search from the sources (instances with no incoming edge) in
// instance order, following outgoing edges in connection order; an edge to an instance on the
// search stack is a back edge (a recycle). Instances the sources do not reach (a cycle with no
// source) are searched from afterwards, in instance order, by the same rule. (2) Layer: the
// longest path from a source over forward edges. (3) Within a layer: instance order, then one
// barycentre pass left to right on the positions of each node's forward predecessors, ties by
// instance order. (4) x = 160·layer, y = 90·index; boxes 120×44; forward edges as elbows, back
// edges routed below the drawing and labelled by connection id. A connection naming an instance
// the revision does not have is not drawn and is returned in `dangling`.

export const LAYER_X = 160;
export const ROW_Y = 90;
export const BOX_W = 120;
export const BOX_H = 44;
export const MARGIN = 16;
const BACK_GAP = 28;
const BACK_STEP = 22;

export function layout(revision) {
  const instances = revision?.instances ?? [];
  const ids = instances.map((instance) => instance.id);
  const order = new Map(ids.map((id, index) => [id, index]));
  const edges = [];
  const dangling = [];
  for (const connection of revision?.connections ?? []) {
    const from = connection?.from?.instance;
    const to = connection?.to?.instance;
    if (order.has(from) && order.has(to)) edges.push({ id: connection.id, from, to, back: false });
    else dangling.push(connection.id);
  }
  const outgoing = new Map(ids.map((id) => [id, []]));
  const incoming = new Map(ids.map((id) => [id, 0]));
  for (const edge of edges) {
    outgoing.get(edge.from).push(edge);
    incoming.set(edge.to, incoming.get(edge.to) + 1);
  }

  // (1) Back edges.
  const state = new Map(ids.map((id) => [id, "new"]));
  const visit = (id) => {
    state.set(id, "open");
    for (const edge of outgoing.get(id)) {
      if (state.get(edge.to) === "open") edge.back = true;
      else if (state.get(edge.to) === "new") visit(edge.to);
    }
    state.set(id, "done");
  };
  for (const id of ids) if (incoming.get(id) === 0 && state.get(id) === "new") visit(id);
  for (const id of ids) if (state.get(id) === "new") visit(id);

  // (2) Layers: longest path over forward edges (a DAG once back edges are set aside).
  const predecessors = new Map(ids.map((id) => [id, []]));
  for (const edge of edges) if (!edge.back) predecessors.get(edge.to).push(edge.from);
  const layer = new Map();
  const layerOf = (id) => {
    if (!layer.has(id)) {
      const preds = predecessors.get(id);
      layer.set(id, preds.length === 0 ? 0 : 1 + Math.max(...preds.map(layerOf)));
    }
    return layer.get(id);
  };
  for (const id of ids) layerOf(id);

  // (3) Order within a layer.
  const depth = ids.length === 0 ? 0 : Math.max(...ids.map((id) => layer.get(id)));
  const layers = Array.from({ length: depth + 1 }, () => []);
  for (const id of ids) layers[layer.get(id)].push(id);
  const position = new Map();
  layers[0]?.forEach((id, index) => position.set(id, index));
  for (let at = 1; at < layers.length; at += 1) {
    const barycentre = new Map(
      layers[at].map((id) => {
        const preds = predecessors.get(id);
        const sum = preds.reduce((total, p) => total + position.get(p), 0);
        return [id, preds.length === 0 ? 0 : sum / preds.length];
      }),
    );
    layers[at].sort((a, b) => barycentre.get(a) - barycentre.get(b) || order.get(a) - order.get(b));
    layers[at].forEach((id, index) => position.set(id, index));
  }

  // (4) Geometry.
  const nodes = instances.map((instance) => {
    const at = layer.get(instance.id);
    const index = position.get(instance.id);
    return {
      id: instance.id,
      model: instance.model?.id ?? null,
      layer: at,
      index,
      x: MARGIN + LAYER_X * at,
      y: MARGIN + ROW_Y * index,
      w: BOX_W,
      h: BOX_H,
    };
  });
  const node = new Map(nodes.map((entry) => [entry.id, entry]));
  const rows = Math.max(1, ...layers.map((members) => members.length));
  const bottom = MARGIN + ROW_Y * (rows - 1) + BOX_H;
  let backs = 0;
  const drawn = edges.map((edge) => {
    const a = node.get(edge.from);
    const b = node.get(edge.to);
    if (!edge.back) {
      const x1 = a.x + BOX_W;
      const y1 = a.y + BOX_H / 2;
      const x2 = b.x;
      const y2 = b.y + BOX_H / 2;
      const mid = (x1 + x2) / 2;
      return { ...edge, d: `M ${x1} ${y1} H ${mid} V ${y2} H ${x2}`, label: null };
    }
    const below = bottom + BACK_GAP + BACK_STEP * backs;
    backs += 1;
    const x1 = a.x + BOX_W / 2;
    const x2 = b.x + BOX_W / 2;
    return {
      ...edge,
      d: `M ${x1} ${a.y + BOX_H} V ${below} H ${x2} V ${b.y + BOX_H}`,
      label: { text: edge.id, x: (x1 + x2) / 2, y: below - 6 },
    };
  });
  const width = MARGIN * 2 + LAYER_X * depth + BOX_W;
  const height = (backs > 0 ? bottom + BACK_GAP + BACK_STEP * (backs - 1) : bottom) + MARGIN;
  return { nodes, edges: drawn, dangling, width, height };
}
