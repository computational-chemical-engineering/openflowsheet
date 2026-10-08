// The browser's credential (M06 design note §7, ADR 0030 D4): the project's bearer token,
// typed into a form or handed over once in the boot fragment, kept under `openflowsheet.token`
// in `sessionStorage` — and in `localStorage` only when "remember on this browser" is ticked —
// and sent only in the `Authorization` header (api.js). Never a cookie, never logged, never in a
// URL the shell builds. Storage can be missing or refuse (private windows, blocked site data),
// so every access is wrapped; a refused write leaves the token held in memory for the page.

import { h } from "./h.js";

export const TOKEN_KEY = "openflowsheet.token";

function read(storage) {
  try {
    return storage?.getItem(TOKEN_KEY) ?? null;
  } catch {
    return null;
  }
}

function write(storage, value) {
  try {
    if (value === null) storage?.removeItem(TOKEN_KEY);
    else storage?.setItem(TOKEN_KEY, value);
  } catch {
    // Storage refused: the in-memory copy still serves this page.
  }
}

// `{get, set, clear, remembered}` over the two storages (injected, so Node tests pass fakes).
export function createTokenStore({ session, local } = {}) {
  let memory = null;
  return {
    get() {
      return memory ?? read(session) ?? read(local);
    },
    set(token, remember = false) {
      memory = token;
      write(session, token);
      write(local, remember ? token : null);
    },
    clear() {
      memory = null;
      write(session, null);
      write(local, null);
    },
    remembered() {
      return read(local) !== null;
    },
  };
}

// §6: a `token` in the boot fragment's query is stored for the session and then removed from
// the address (`replaceState`), so it stays in no history entry. Returns whether one was taken.
export function takeBootToken(location, history, store, withoutToken) {
  const hash = String(location.hash ?? "");
  const mark = hash.indexOf("?");
  if (mark < 0) return false;
  const token = new URLSearchParams(hash.slice(mark + 1)).get("token");
  if (token === null) return false;
  if (token !== "") store.set(token, false);
  history.replaceState(null, "", `${location.pathname}${location.search}${withoutToken(hash)}`);
  return token !== "";
}

// The sign-in screen: a password field, the opt-in "remember", and the server's message when a
// token was refused. `onSubmit(token, remember)` is called with the field's values.
export function loginView({ message = null, onSubmit }) {
  const submit = (event) => {
    event.preventDefault();
    const form = event.target;
    const token = String(form.elements.token.value ?? "").trim();
    const remember = Boolean(form.elements.remember.checked);
    if (token) onSubmit(token, remember);
  };
  return h(
    "section",
    { class: "panel login", "data-ofs-screen": "login" },
    h("h1", null, "Sign in to OpenFlowsheet"),
    h(
      "p",
      { class: "muted" },
      "Paste a bearer token granted for this project (",
      h("code", null, "openflowsheet project grant"),
      "). It is sent only in the Authorization header of this page's requests.",
    ),
    message === null ? null : h("p", { class: "notice", role: "alert" }, message),
    h(
      "form",
      { on: { submit } },
      h("label", { for: "ofs-token" }, "Token"),
      h("input", { id: "ofs-token", name: "token", type: "password", autocomplete: "off" }),
      h(
        "label",
        { class: "remember" },
        h("input", { name: "remember", type: "checkbox" }),
        "remember on this browser",
      ),
      h("button", { type: "submit" }, "Sign in"),
    ),
  );
}
