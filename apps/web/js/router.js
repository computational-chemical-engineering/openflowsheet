// Hash routes (M06 design note §6): `#/rev/{rid}/validation?k=v`. Pure functions — parsing a
// hash, matching it against route patterns, building links — so they run in Node.

// `{path, params}` of a location hash: the route path, and the `?k=v` text after it as
// `URLSearchParams`. An empty hash is the route `/`.
export function parseHash(hash) {
  let text = String(hash ?? "");
  if (text.startsWith("#")) text = text.slice(1);
  const mark = text.indexOf("?");
  const path = (mark < 0 ? text : text.slice(0, mark)) || "/";
  const params = new URLSearchParams(mark < 0 ? "" : text.slice(mark + 1));
  return { path: path.startsWith("/") ? path : `/${path}`, params };
}

function segments(path) {
  return path.split("/").filter((part, index) => index > 0 || part !== "");
}

// The first route of `routes` (`[{name, pattern}]`, pattern like `/job/{jid}/file/{name}`)
// whose pattern matches `path`: `{name, values}`, each value percent-decoded; or null.
export function matchRoute(routes, path) {
  const parts = segments(path === "/" ? "" : path);
  for (const route of routes) {
    const pattern = segments(route.pattern === "/" ? "" : route.pattern);
    if (pattern.length !== parts.length) continue;
    const values = {};
    let matched = true;
    for (let index = 0; index < pattern.length && matched; index += 1) {
      const want = pattern[index];
      const part = parts[index];
      const parameter = /^\{([a-z_]+)\}$/.exec(want);
      if (parameter) {
        if (part === "") matched = false;
        else {
          try {
            values[parameter[1]] = decodeURIComponent(part);
          } catch {
            matched = false;
          }
        }
      } else if (want !== part) {
        matched = false;
      }
    }
    if (matched) return { name: route.name, values };
  }
  return null;
}

// The hash link to `pattern` with `values` filled in, each percent-encoded (an id's `/` is
// `%2F`), and `query` (an object; null/undefined members dropped) after a `?`.
export function link(pattern, values = {}, query = {}) {
  const path = pattern.replace(/\{([a-z_]+)\}/g, (_, name) => {
    const value = values[name];
    if (value === null || value === undefined) throw new Error(`link: ${pattern} needs ${name}`);
    return encodeURIComponent(String(value));
  });
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined) search.append(key, String(value));
  }
  const text = search.toString();
  return `#${path}${text ? `?${text}` : ""}`;
}

// `hash` with the reserved boot key `token` removed (§6: it is stored, then stripped).
export function withoutToken(hash) {
  const { path, params } = parseHash(hash);
  params.delete("token");
  const text = params.toString();
  return `#${path}${text ? `?${text}` : ""}`;
}
