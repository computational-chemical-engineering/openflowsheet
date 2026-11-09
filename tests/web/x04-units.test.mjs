// X04 A38 (ADR 0075 D5.1, D7): the viewer's display units in the web shell — the control, its
// storage, the request member, and the two screens that show converted numbers. The display
// values below are written by the test as a server would send them; the shell only shows them.

import { test } from "node:test";
import assert from "node:assert/strict";

import { body, fixtureApi, JOB } from "./fixture-transport.mjs";
import { byAttr, byTag, tableRows, textOf } from "./tree.mjs";
import { FakeDocument } from "./fake-dom.mjs";
import { headerView } from "../../apps/web/js/frame.js";
import { mount } from "../../apps/web/js/h.js";
import * as failure from "../../apps/web/js/screens/failure.js";
import * as streams from "../../apps/web/js/screens/streams.js";
import { DASH } from "../../apps/web/js/text.js";
import {
  TEXT_UNITS,
  UNITS_KEY,
  displayRequest,
  effectiveUnits,
  readUnits,
  textUnit,
  unitChoices,
  writeUnits,
} from "../../apps/web/js/units.js";

const PROJECT = {
  project_id: "p",
  principal_id: "agent-a",
  rights: ["read"],
  server: { package_version: "0.4.0", git_commit: null },
  ambient_pressure: null,
};
const DECLARED = { ...PROJECT, ambient_pressure: { value: 101325.0, unit: "Pa" } };

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => (values.has(key) ? values.get(key) : null),
    setItem: (key, value) => values.set(key, String(value)),
    values,
  };
}

const throwing = {
  getItem() {
    throw new Error("blocked");
  },
  setItem() {
    throw new Error("blocked");
  },
};

test("A38: the choice is kept in storage, every access survives a blocked or missing storage", () => {
  const storage = memoryStorage();
  assert.equal(readUnits(storage), "si");
  writeUnits(storage, "eng");
  assert.equal(storage.values.get(UNITS_KEY), "eng");
  assert.equal(readUnits(storage), "eng");
  storage.setItem(UNITS_KEY, "kelvin please");
  assert.equal(readUnits(storage), "si"); // not a choice
  assert.equal(readUnits(throwing), "si");
  assert.doesNotThrow(() => writeUnits(throwing, "eng"));
  assert.equal(readUnits(null), "si");
  assert.doesNotThrow(() => writeUnits(undefined, "eng"));
});

test("A38: SI sends no preference; the gauge choice needs a declared ambient", () => {
  assert.deepEqual(displayRequest("si"), {});
  assert.deepEqual(displayRequest(undefined), {});
  assert.deepEqual(displayRequest("eng"), { display_units: "eng" });
  assert.equal(effectiveUnits("eng,pressure=barg", PROJECT), "si");
  assert.equal(effectiveUnits("eng,pressure=barg", DECLARED), "eng,pressure=barg");
  assert.equal(effectiveUnits("eng", PROJECT), "eng");
  assert.deepEqual(unitChoices(PROJECT).map((choice) => [choice.value, choice.enabled]), [
    ["si", true],
    ["eng", true],
    ["eng,pressure=barg", false],
  ]);
  assert.ok(unitChoices(DECLARED).every((choice) => choice.enabled));
});

test("A38: the header's units control offers SI, eng and a gauge option enabled only with an ambient", () => {
  const chosen = [];
  for (const [project, gaugeDisabled] of [
    [PROJECT, true],
    [DECLARED, false],
  ]) {
    const tree = headerView(project, { units: "eng", onUnits: (value) => chosen.push(value) });
    mount(tree, new FakeDocument().body);
    const [select] = byAttr(tree, "data-ofs-action", "units");
    const options = byTag(select, "option");
    assert.deepEqual(options.map((option) => option.p.value), ["si", "eng", "eng,pressure=barg"]);
    assert.deepEqual(options.map((option) => Boolean(option.p.selected)), [false, true, false]);
    assert.equal(Boolean(options[2].p.disabled), gaugeDisabled);
    select.p.on.change({ target: { value: "si" } });
  }
  assert.deepEqual(chosen, ["si", "si"]);
});

// A stream-table document as `get_stream_table` returns it with `display_units: "eng"`: the
// fixture's SI document with display items written in (values chosen by the test).
function displayed(document) {
  const shown = structuredClone(document);
  shown.display_units = { units: { temperature: "degC" }, ambient_pressure: null };
  for (const [index, stream] of shown.streams.entries()) {
    if (stream.T !== null) stream.display = { T: { value: 100.5 + index, unit: "degC" } };
  }
  const unit = shown.energy.units[0];
  unit.display = { Q: { value: null, unit: "kW", reason: { code: "display_out_of_range", params: { kind: "heat_rate", unit: "kW" } } } };
  return shown;
}

const SI_ARGS = { job_id: JOB.NET02, pointer: "", depth: 12, limit: 200 };

test("A38: the streams screen sends display_units and shows the server's display values, SI in the title", async () => {
  const seen = [];
  const api = fixtureApi("agent-a", {
    extra(name, args) {
      if (name !== "get_stream_table" || args.display_units === undefined) return undefined;
      seen.push(args.display_units);
      const { display_units: _, ...plain } = args;
      return { status: 200, body: { ...body("agent-a", name, plain), value: displayed(body("agent-a", name, plain).value) } };
    },
  });
  const data = await streams.load(
    { jid: JOB.NET02, query: new URLSearchParams(), signal: undefined, project: PROJECT, go() {}, units: "eng" },
    api,
  );
  assert.deepEqual(seen, ["eng"]);
  const tree = streams.view(data);
  mount(tree, new FakeDocument().body);
  const si = body("agent-a", "get_stream_table", SI_ARGS).value;
  const headers = byTag(byAttr(tree, "data-ofs-stream-table", "1")[0], "th").map((th) => textOf(th));
  assert.ok(headers.includes("T (°C)"));
  assert.ok(headers.includes("P (Pa)")); // not converted: its SI unit stays
  const rows = tableRows(tree, "phase_source");
  const at = headers.indexOf("T (°C)");
  const first = si.streams.findIndex((stream) => stream.T !== null);
  const total = rows.find((row) => row[0] === si.streams[first].id && row[1] === "total");
  assert.equal(total[at], String(100.5 + first));
  // ADR 0075 D7.7 (FQ4): the heading is human text (`°C`); `data-ofs-display` is the item's unit.
  assert.ok(!headers.includes("T (degC)"));
  const cells = byAttr(tree, "data-ofs-display", "degC");
  assert.ok(cells.some((cell) => cell.p.title === `${si.streams[first].T} K`));
  // An out-of-range display is a dash with its reason; its SI value stays in the title.
  const out = byAttr(tree, "data-ofs-absent", "display_out_of_range(kind=heat_rate, unit=kW)");
  assert.equal(out.length, 1);
  assert.equal(out[0].c[0], DASH);
  assert.ok(out[0].p.title.startsWith(`${si.energy.units[0].Q} W; `));
  assert.ok(byTag(tree, "th").some((th) => textOf(th) === "Q (kW)"));
  // The as-solved state table stays SI and says so.
  assert.equal(byAttr(tree, "data-ofs-si-only", "1").length, 1);
  assert.ok(byTag(tree, "th").some((th) => textOf(th) === "T (K)"));
});

test("A38: without a preference the streams screen sends none and shows the SI table", async () => {
  const api = fixtureApi("agent-a");
  const data = await streams.load(
    { jid: JOB.NET02, query: new URLSearchParams(), signal: undefined, project: PROJECT, go() {}, units: "si" },
    api,
  );
  assert.ok(api.log.every((entry) => !("display_units" in entry.args)));
  const tree = streams.view(data);
  assert.equal(byAttr(tree, "data-ofs-display").length, 0);
  assert.ok(byTag(tree, "th").some((th) => textOf(th) === "H_flow (W)"));
});

test("A38: the failure screen sends display_units and lists the converted numbers, SI in the title", async () => {
  const seen = [];
  const api = fixtureApi("agent-a", {
    extra(name, args) {
      if (name !== "get_job_result" || args.display_units === undefined) return undefined;
      seen.push(args.display_units);
      const result = structuredClone(body("agent-a", name, { job_id: args.job_id }));
      result.display_units = { units: { pressure: "bar" }, ambient_pressure: null };
      result.run_result.failure.explanation.numbers = [
        { name: "p_spec", label: "p_spec", value: 2000000.0, unit: "Pa", kind: "pressure", display: { value: 20, unit: "bar" } },
        { name: "n", label: "n", value: 3, unit: "1", kind: null },
        { name: "t_out", label: "t_out", value: 298.15, unit: "K", kind: "temperature", display: { value: 25, unit: "degC" } },
      ];
      return { status: 200, body: result };
    },
  });
  const data = await failure.load(
    { jid: JOB["A02-352"], query: new URLSearchParams(), signal: undefined, project: PROJECT, go() {}, units: "eng" },
    api,
  );
  assert.deepEqual(seen, ["eng"]);
  const tree = failure.view(data);
  mount(tree, new FakeDocument().body);
  const [list] = byAttr(tree, "data-ofs-explanation-numbers", "2");
  assert.deepEqual(byTag(list, "li").map((li) => textOf(li)), ["p_spec: 20 bar", "t_out: 25 °C"]);
  assert.equal(byAttr(list, "data-ofs-display", "bar")[0].p.title, "2000000 Pa");
  // ADR 0075 D7.7 (FQ4): the text shows `°C`; `data-ofs-display` keeps the item's `degC`.
  assert.equal(byAttr(list, "data-ofs-display", "degC")[0].p.title, "298.15 K");
});

test("ADR 0075 D7.7 (FQ4): human text spells degC and degF with the degree sign, every other unit as is", () => {
  assert.equal(textUnit("degC"), "°C");
  assert.equal(textUnit("degF"), "°F");
  for (const unit of ["K", "bar", "barg", "kJ/(mol K)", "%", "constructor", "toString"]) assert.equal(textUnit(unit), unit);
  assert.deepEqual(TEXT_UNITS, { degC: "°C", degF: "°F" });
});
