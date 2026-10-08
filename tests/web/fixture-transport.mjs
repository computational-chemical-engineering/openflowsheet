// M06 WO-7: the W26 fixture project as a transport for `createApi` (design note §8 Layer B).
//
// `tests/web/fixtures/w26/` holds the server's answers to every request the screens make on the
// fixture project (scripts/m06_web_fixtures.py, through `operations.dispatch`). This transport
// reads back the operation and the request members from the URL and body `api.js` built —
// matching the path against `ROUTES` as the HTTP binding matches its rows, decoding path
// parameters, reading query numbers as the binding does — and answers the record under the
// same key the generator wrote. A request the fixtures do not hold fails the test that made it,
// naming the request, so a screen cannot ask the server something the fixtures never answered.

import { readFileSync } from "node:fs";

import { createApi } from "../../apps/web/js/api.js";
import { ROUTES } from "../../apps/web/js/routes.js";

const DIRECTORY = new URL("./fixtures/w26/", import.meta.url);

export const FIXTURE = JSON.parse(readFileSync(new URL("exchanges.json", DIRECTORY), "utf-8"));

// The bytes of a raw record, as the generator wrote them.
export function rawBytes(name) {
  return new Uint8Array(readFileSync(new URL(name, DIRECTORY)));
}

// `name {members}`: the generator's `key` (canonical JSON, keys sorted, null members dropped).
export function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const keys = Object.keys(value)
      .filter((k) => value[k] !== undefined && value[k] !== null)
      .sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${canonical(value[k])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function fixtureKey(name, args) {
  return `${name} ${canonical(args)}`;
}

const JSON_NUMBER = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/;

// `{name, args}` of a request `api.js` built.
export function decodeRequest(url, init) {
  const mark = url.indexOf("?");
  const path = mark < 0 ? url : url.slice(0, mark);
  const query = new URLSearchParams(mark < 0 ? "" : url.slice(mark + 1));
  for (const [name, route] of Object.entries(ROUTES)) {
    if (route.verb !== init.method) continue;
    const names = [];
    const pattern = route.path.replace(/\{([a-z_]+)\}/g, (_, parameter) => {
      names.push(parameter);
      return "([^/]+)";
    });
    const found = new RegExp(`^${pattern}$`).exec(path);
    if (found === null) continue;
    const args = init.body === undefined ? {} : JSON.parse(init.body);
    names.forEach((parameter, index) => {
      args[parameter] = decodeURIComponent(found[index + 1]);
    });
    const numeric = FIXTURE.numeric_query_members[name] ?? [];
    for (const [member, text] of query) {
      args[member] = numeric.includes(member) && JSON_NUMBER.test(text) ? JSON.parse(text) : text;
    }
    return { name, args };
  }
  throw new Error(`fixture transport: no route for ${init.method} ${url}`);
}

function response(status, bytes) {
  return {
    status,
    headers: { get: () => null },
    json: async () => JSON.parse(new TextDecoder().decode(bytes)),
    arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.length),
  };
}

// The record answering `name` with `args` as `principal`, or undefined.
export function recordOf(principal, name, args) {
  const key = fixtureKey(name, args);
  return FIXTURE.principals[principal]?.[key] ?? FIXTURE.shared[key];
}

// A transport answering as `principal` from the fixtures; `log` collects `{name, args}`.
// `extra(name, args)` may answer first (a test's stand-in for an action), returning
// `{status, body}` or undefined.
export function fixtureTransport(principal = "agent-a", { log = [], extra } = {}) {
  const transport = async (url, init) => {
    const { name, args } = decodeRequest(url, init);
    log.push({ name, args });
    const record = extra?.(name, args) ?? recordOf(principal, name, args);
    if (record === undefined) {
      throw new Error(`fixture transport: no record for ${fixtureKey(name, args)} as ${principal}`);
    }
    if (record.raw !== undefined) return response(record.status, rawBytes(record.raw));
    return response(record.status, new TextEncoder().encode(JSON.stringify(record.body)));
  };
  transport.log = log;
  return transport;
}

// An API of one page session over the fixtures, as `principal`.
export function fixtureApi(principal = "agent-a", options = {}) {
  const transport = fixtureTransport(principal, options);
  let token = "fixture-token";
  const api = createApi(transport, { get: () => token, clear: () => (token = null) });
  api.log = transport.log;
  return api;
}

// The document a GET record holds (a test reading the fixtures directly).
export function body(principal, name, args) {
  const record = recordOf(principal, name, args);
  if (record === undefined) throw new Error(`no record for ${fixtureKey(name, args)}`);
  return record.body;
}

// A raw record parsed.
export function rawJson(artifactId) {
  const record = FIXTURE.shared[fixtureKey("artifact_bytes", { artifact_id: artifactId })];
  if (record === undefined) throw new Error(`no raw record for ${artifactId}`);
  return JSON.parse(new TextDecoder().decode(rawBytes(record.raw)));
}

export const REV = FIXTURE.revisions;
export const JOB = FIXTURE.jobs;
