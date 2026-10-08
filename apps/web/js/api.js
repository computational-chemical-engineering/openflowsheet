// The shell's only network code (M06 design note §5.3, §5.4; ADR 0030 D5).
//
// Every request is a row of `ROUTES` (generated from the HTTP binding's `OPERATIONS` rows) and
// goes through `httpTransport`, whose body is the one fetch call of the shell. The bearer token
// travels in the `Authorization` header only: never in a URL, never as a cookie
// (`credentials: "omit"`). Records are read whole through the raw export with a SHA-256 check;
// projected documents (revisions, structure, bundle listings) are reassembled by `readWhole`.

import { ROUTES } from "./routes.js";

// §5.4: the views `readWhole` asks for, and its request budget per document.
export const VIEW_DEPTH = 12;
export const VIEW_LIMIT = 200;
export const READ_WHOLE_BUDGET = 500;
export const ELIDED = "$elided";
// §5.4: the operations whose answers are cached for the page session, by name and arguments.
// `get_job_result` is cached too: it answers only for an ended job, whose result is final.
const CACHED = new Set([
  "get_revision",
  "inspect_structure",
  "diff_revisions",
  "get_artifact",
  "artifact_bytes",
  "list_models",
  "validate",
  "get_job_result",
]);
const VIEW_MEMBERS = ["pointer", "depth", "cursor", "limit"];

// A non-2xx answer: `document` is the server's `ApiError` (`code`, `message`, `retryable`,
// `detail`), or one this module writes when the body is not one.
export class ApiError extends Error {
  constructor(status, document) {
    super(`${document.code}: ${document.message}`);
    this.name = "ApiError";
    this.status = status;
    this.document = document;
    this.code = document.code;
  }
}

// A failure of the shell's own reading rules (a document changed while it was read, the
// request budget ran out): shown like an error, never retried silently.
export class ReadError extends Error {
  constructor(message) {
    super(message);
    this.name = "ReadError";
  }
}

// The one network call site of the shell.
export function httpTransport(url, init) {
  return fetch(url, init);
}

function refuse(message) {
  throw new Error(`api: ${message}`);
}

function checkFinite(value, at) {
  if (typeof value === "number" && !Number.isFinite(value)) refuse(`a non-finite number at ${at}`);
  if (value !== null && typeof value === "object") {
    for (const [key, member] of Object.entries(value)) checkFinite(member, `${at}/${key}`);
  }
}

// The URL and `fetch` options of operation `name` with request members `args` (§5.3).
export function buildRequest(name, args, token, signal) {
  const route = ROUTES[name];
  if (route === undefined) refuse(`${name} is not an HTTP operation`);
  for (const key of Object.keys(args)) {
    if (!route.members.includes(key)) refuse(`${name} has no request member ${key}`);
  }
  const path = route.path.replace(/\{([a-z_]+)\}/g, (_, parameter) => {
    const value = args[parameter];
    if (value === null || value === undefined) refuse(`${name} needs ${parameter}`);
    return encodeURIComponent(String(value));
  });
  const rest = {};
  for (const key of route.members) {
    const value = args[key];
    if (!route.path_params.includes(key) && value !== null && value !== undefined) {
      rest[key] = value;
    }
  }
  const headers = { Authorization: `Bearer ${token}` };
  const init = {
    method: route.verb,
    headers,
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
    signal,
  };
  let url = path;
  if (route.verb === "GET") {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(rest)) {
      if (typeof value === "object") refuse(`${name}: ${key} cannot travel in a query`);
      checkFinite(value, `/${key}`);
      query.append(key, String(value));
    }
    const text = query.toString();
    if (text) url = `${path}?${text}`;
  } else {
    checkFinite(rest, "");
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(rest);
  }
  return { url, init };
}

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const keys = Object.keys(value).filter((k) => value[k] !== undefined).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${canonical(value[k])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

// RFC 6901 §3.
export function escapeToken(token) {
  return String(token).replace(/~/g, "~0").replace(/\//g, "~1");
}

function isPlainObject(node) {
  return node !== null && typeof node === "object" && !Array.isArray(node);
}

// Whether `node` is the projection's elision marker for the node at pointer `at`:
// `{"$elided": {"pointer": at, "members"|"items": n}}`, `$elided` its only key.
export function isMarker(node, at, kind) {
  if (!isPlainObject(node)) return false;
  const keys = Object.keys(node);
  if (keys.length !== 1 || keys[0] !== ELIDED) return false;
  const inner = node[ELIDED];
  if (!isPlainObject(inner)) return false;
  const names = Object.keys(inner).sort();
  const count = names.length === 2 && names[1] === "pointer" ? names[0] : null;
  if (count !== "items" && count !== "members") return false;
  if (kind !== undefined && count !== kind) return false;
  return inner.pointer === at && Number.isInteger(inner[count]) && inner[count] >= 0;
}

function hex(buffer) {
  return Array.from(new Uint8Array(buffer), (b) => b.toString(16).padStart(2, "0")).join("");
}

// The SHA-256 of `bytes`, or null where `crypto.subtle` is missing (an insecure context).
export async function sha256Hex(bytes) {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return null;
  return hex(await subtle.digest("SHA-256", bytes));
}

async function errorDocument(response) {
  let document = null;
  try {
    document = await response.json();
  } catch {
    document = null;
  }
  if (isPlainObject(document) && typeof document.code === "string") return document;
  return {
    code: "internal_error",
    message: `HTTP ${response.status} without an error document`,
    retryable: false,
    detail: {},
  };
}

// The API of one page session. `tokenStore` is `{get(): string|null, clear(): void}`.
export function createApi(transport = httpTransport, tokenStore) {
  const cache = new Map();

  async function request(name, args, signal) {
    const token = tokenStore.get();
    if (!token) {
      throw new ApiError(401, {
        code: "unauthenticated",
        message: "no token: sign in",
        retryable: false,
        detail: {},
      });
    }
    const { url, init } = buildRequest(name, args, token, signal);
    const response = await transport(url, init);
    if (response.status < 200 || response.status > 299) {
      const document = await errorDocument(response);
      if (response.status === 401) tokenStore.clear();
      throw new ApiError(response.status, document);
    }
    return response;
  }

  async function cached(name, args, load) {
    if (!CACHED.has(name)) return load();
    const key = `${name} ${canonical(args)}`;
    if (cache.has(key)) return cache.get(key);
    const value = await load();
    cache.set(key, value);
    return value;
  }

  // Operation `name` with request members `args`: its response document. A domain result
  // (an INVALID report, a failed job) is a document, not an error.
  async function call(name, args = {}, { signal } = {}) {
    if (name === "artifact_bytes") refuse("the raw export is read with raw()");
    return cached(name, args, async () => (await request(name, args, signal)).json());
  }

  // `artifact_bytes`: the exact bytes of a record, and whether their SHA-256 is the one the
  // bundle listing registered — "match", "mismatch", or "unchecked" (no `crypto.subtle`).
  async function raw(artifactId, expectedSha256, { signal } = {}) {
    const args = { artifact_id: artifactId };
    const bytes = await cached("artifact_bytes", args, async () => {
      const response = await request("artifact_bytes", args, signal);
      return new Uint8Array(await response.arrayBuffer());
    });
    const found = await sha256Hex(bytes);
    let digest = "unchecked";
    if (found !== null && typeof expectedSha256 === "string") {
      digest = found === expectedSha256 ? "match" : "mismatch";
    }
    return { bytes, sha256: found, digest };
  }

  // `raw` parsed as UTF-8 JSON.
  async function rawJson(artifactId, expectedSha256, options = {}) {
    const read = await raw(artifactId, expectedSha256, options);
    const text = new TextDecoder("utf-8", { fatal: true }).decode(read.bytes);
    return { document: JSON.parse(text), digest: read.digest, sha256: read.sha256 };
  }

  // §5.4: the whole document a projecting operation views, reassembled from its views.
  async function readWhole(name, args, { signal } = {}) {
    for (const member of VIEW_MEMBERS) {
      if (member in args) refuse(`readWhole sets ${member} itself`);
    }
    return cached(name, { ...args, readWhole: true }, () => expandAll(name, args, signal));
  }

  async function expandAll(name, args, signal) {
    let requests = 0;
    let sha = null;

    async function view(pointer, cursor) {
      requests += 1;
      if (requests > READ_WHOLE_BUDGET) {
        throw new ReadError(
          `${name}: more than ${READ_WHOLE_BUDGET} requests to read one document; stopped`,
        );
      }
      const document = await (
        await request(
          name,
          { ...args, pointer, depth: VIEW_DEPTH, limit: VIEW_LIMIT, cursor: cursor ?? null },
          signal,
        )
      ).json();
      if (sha === null) sha = document.sha256;
      else if (document.sha256 !== sha) {
        throw new ReadError(`${name}: the document changed while it was read (${pointer})`);
      }
      return document;
    }

    // The value at `pointer`; an array target is paged to its end.
    async function page(pointer) {
      const first = await view(pointer, null);
      if (!Array.isArray(first.value)) return first.value;
      const items = [...first.value];
      let cursor = first.next_cursor;
      while (cursor !== null && cursor !== undefined) {
        const next = await view(pointer, cursor);
        if (!Array.isArray(next.value)) throw new ReadError(`${name}: a page is not an array`);
        items.push(...next.value);
        cursor = next.next_cursor;
      }
      return items;
    }

    // `target`: `node` is a whole array target page, never cut at 20 items.
    async function expand(node, at, target = false) {
      if (isMarker(node, at)) {
        const value = await page(at);
        // A view always shows its target, so a view of `at` that is a marker of `at` is literal
        // content shaped like one (the design's deepEqual guard, without its second request when
        // the literal's count differs from the marker's): kept as it is, never read again.
        if (isMarker(value, at)) return value;
        return expand(value, at, Array.isArray(value));
      }
      if (Array.isArray(node)) {
        const last = node[node.length - 1];
        if (!target && node.length > 0 && isMarker(last, at, "items")) {
          return expand(await page(at), at, true); // a nested array cut at 20: read it whole
        }
        const out = [];
        for (let index = 0; index < node.length; index += 1) {
          out.push(await expand(node[index], `${at}/${index}`));
        }
        return out;
      }
      if (isPlainObject(node)) {
        const out = {};
        for (const [key, value] of Object.entries(node)) {
          out[key] = await expand(value, `${at}/${escapeToken(key)}`);
        }
        return out;
      }
      return node;
    }

    const root = await page("");
    return expand(root, "", Array.isArray(root));
  }

  // §5.4 live jobs: `wait_job` until the job has ended, `onWait` called with each answer; one
  // outstanding call at a time, ended early by `signal`. Returns the ended job.
  async function followJob(jobId, { afterSequence = -1, timeoutS = 20, signal, onWait } = {}) {
    let after = afterSequence;
    for (;;) {
      const waited = await call(
        "wait_job",
        { job_id: jobId, after_sequence: after, timeout_s: timeoutS },
        { signal },
      );
      if (onWait) onWait(waited);
      if (waited.events.length > 0) after = waited.events[waited.events.length - 1].sequence;
      if (waited.ended) return waited.job;
    }
  }

  return { call, raw, rawJson, readWhole, followJob, cacheSize: () => cache.size };
}
