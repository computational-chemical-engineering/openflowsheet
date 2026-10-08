// Boot and navigation of the diagnostic web shell (M06 design note §5, §6, §8 A6).
//
// On every navigation `<html data-ofs-ready>` is "0" until the screen's `load` has resolved and
// its view is mounted, then "1" (the browser smoke test waits for it). An error a load raises is
// shown in the error panel; an uncaught error or rejection anywhere renders `<pre id="ofs-fatal">`
// and sets `data-ofs-error="1"`. Every screen is `{name, pattern, load(params, api), view(data)}`;
// `params` holds the route's values, `query` (URLSearchParams), `signal` (aborted when the
// user navigates away), `project` (the frame's `get_project` document: rights, policies) and
// `go(hash)` (navigate; the current hash is loaded again).

import { createApi } from "./api.js";
import { createTokenStore, loginView, takeBootToken } from "./auth.js";
import { errorView, fatalText, headerView, nextTheme, notFoundView } from "./frame.js";
import { h, mount, replace } from "./h.js";
import { link, matchRoute, parseHash, withoutToken } from "./router.js";
import * as certificate from "./screens/certificate.js";
import { setNumberMode } from "./screens/common.js";
import * as failure from "./screens/failure.js";
import * as projectScreen from "./screens/project.js";
import * as revision from "./screens/revision.js";
import * as streams from "./screens/streams.js";
import * as validation from "./screens/validation.js";

// The screens of this build, matched in order.
const SCREENS = [projectScreen, revision, validation, certificate, failure, streams];

const THEME_KEY = "openflowsheet.theme";
const root = document.documentElement;
const header = document.getElementById("ofs-header");
const main = document.getElementById("ofs-main");

function fatal(reason) {
  if (document.getElementById("ofs-fatal") === null) {
    mount(h("pre", { id: "ofs-fatal", role: "alert" }, fatalText(reason)), document.body);
  }
  root.setAttribute("data-ofs-error", "1");
}
window.addEventListener("error", (event) => fatal(event.error ?? event.message));
window.addEventListener("unhandledrejection", (event) => fatal(event.reason));

function storage(name) {
  try {
    return window[name] ?? null;
  } catch {
    return null;
  }
}

const local = storage("localStorage");
const store = createTokenStore({ session: storage("sessionStorage"), local });
let api = createApi(undefined, store);
let project = null;
let loginMessage = null;
let controller = null;

let numbers = "short";
let theme = "system";
try {
  theme = local?.getItem(THEME_KEY) ?? "system";
} catch {
  theme = "system";
}

function applyTheme() {
  if (theme === "light" || theme === "dark") root.setAttribute("data-theme", theme);
  else {
    theme = "system";
    root.removeAttribute("data-theme");
  }
}

function renderHeader() {
  replace(
    headerView(project, {
      theme,
      onTheme: () => {
        theme = nextTheme(theme);
        try {
          local?.setItem(THEME_KEY, theme);
        } catch {
          // Not remembered; applied for this page.
        }
        applyTheme();
        renderHeader();
      },
      numbers,
      onNumbers: () => {
        numbers = numbers === "short" ? "full" : "short";
        setNumberMode(numbers);
        renderHeader();
        navigate();
      },
      onSignOut: () => {
        store.clear();
        api = createApi(undefined, store); // nothing read with the old token is kept
        project = null;
        loginMessage = null;
        renderHeader();
        location.hash = link("/login");
      },
    }),
    header,
  );
}

function toLogin(message) {
  project = null;
  loginMessage = message;
  renderHeader();
  const { path, params } = parseHash(location.hash);
  const next = path === "/login" ? params.get("next") : withoutToken(location.hash);
  location.hash = link("/login", {}, { next });
}

function showLogin(params) {
  replace(
    loginView({
      message: loginMessage,
      onSubmit: async (token, remember) => {
        store.set(token, remember);
        api = createApi(undefined, store);
        try {
          project = await api.call("get_project");
        } catch (error) {
          if (error?.status === 401) {
            loginMessage = error.document.message;
            showLogin(params);
            return;
          }
          replace(errorView(error), main);
          return;
        }
        loginMessage = null;
        renderHeader();
        const next = params.get("next");
        location.hash = next && next.startsWith("#/") && !next.startsWith("#/login") ? next : "#/";
      },
    }),
    main,
  );
  root.setAttribute("data-ofs-ready", "1");
}

// Navigate to `hash`; the current hash is rendered again (a reload of the screen's data).
function go(hash) {
  if (location.hash === hash) navigate();
  else location.hash = hash;
}

async function navigate() {
  controller?.abort();
  controller = new AbortController();
  const { signal } = controller;
  root.setAttribute("data-ofs-ready", "0");
  const { path, params } = parseHash(location.hash);
  if (path === "/login") {
    showLogin(params);
    return;
  }
  if (!store.get()) {
    toLogin(null);
    return;
  }
  try {
    if (project === null) {
      project = await api.call("get_project", {}, { signal });
      renderHeader();
    }
    const match = matchRoute(SCREENS, path);
    let tree;
    if (match === null) tree = notFoundView(path);
    else {
      const screen = SCREENS.find((candidate) => candidate.name === match.name);
      const data = await screen.load(
        { ...match.values, query: params, signal, project, go },
        api,
      );
      if (signal.aborted) return;
      tree = screen.view(data);
    }
    replace(tree, main);
  } catch (error) {
    if (signal.aborted) return;
    if (error?.status === 401) {
      toLogin(error.document.message);
      return;
    }
    replace(errorView(error), main);
  }
  root.setAttribute("data-ofs-ready", "1");
}

applyTheme();
takeBootToken(location, history, store, withoutToken);
renderHeader();
window.addEventListener("hashchange", navigate);
navigate();
