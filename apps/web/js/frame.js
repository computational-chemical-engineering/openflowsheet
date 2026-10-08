// The frame around every screen (M06 design note §5.1, §6): the header (project, principal,
// rights, server version, theme, sign out), the error panel, and the screen for a route this
// build does not have. Pure views over plain data, so they run in Node.

import { h } from "./h.js";

// The theme toggle cycles through these; "system" follows `prefers-color-scheme`.
export const THEMES = ["system", "light", "dark"];

export function nextTheme(theme) {
  const index = THEMES.indexOf(theme);
  return THEMES[(index + 1) % THEMES.length];
}

// `project`: `get_project`'s document, or null before sign-in.
export function headerView(project, { theme = "system", onTheme, onSignOut } = {}) {
  const facts =
    project === null
      ? null
      : h(
          "dl",
          { class: "facts" },
          fact("project", project.project_id),
          fact("principal", project.principal_id),
          fact("rights", [...project.rights].sort().join(", ") || "none"),
          fact(
            "server",
            `${project.server.package_version}` +
              (project.server.git_commit ? ` (${project.server.git_commit.slice(0, 12)})` : ""),
          ),
        );
  return h(
    "div",
    { class: "frame" },
    h("a", { class: "product", href: "#/" }, "OpenFlowsheet"),
    facts,
    h(
      "div",
      { class: "actions" },
      h(
        "button",
        { type: "button", "data-ofs-action": "theme", on: onTheme ? { click: onTheme } : {} },
        `theme: ${theme}`,
      ),
      project === null
        ? null
        : h(
            "button",
            {
              type: "button",
              "data-ofs-action": "sign-out",
              on: onSignOut ? { click: onSignOut } : {},
            },
            "sign out",
          ),
    ),
  );
}

function fact(term, value) {
  return h("div", null, h("dt", null, term), h("dd", null, String(value)));
}

// An error a screen's load raised: the server's `ApiError` document as it came (code, message,
// retryable, detail), or the shell's own reading error. Never a stack trace of the shell; that
// is the fatal panel's.
export function errorView(error) {
  const document = error?.document;
  if (document && typeof document.code === "string") {
    return h(
      "section",
      { class: "panel", id: "ofs-error", role: "alert", "data-ofs-error-code": document.code },
      h("h1", null, `The server refused: ${document.code}`),
      h("p", null, String(document.message ?? "")),
      h("p", { class: "muted" }, `HTTP ${error.status}; retryable: ${String(document.retryable)}`),
      h("pre", null, JSON.stringify(document.detail ?? {}, null, 2)),
    );
  }
  return h(
    "section",
    { class: "panel", id: "ofs-error", role: "alert", "data-ofs-error-code": "client" },
    h("h1", null, "The shell could not show this screen"),
    h("p", null, String(error?.message ?? error)),
  );
}

// A route no screen of this build serves: said plainly, never an empty page.
export function notFoundView(path) {
  return h(
    "section",
    { class: "panel", "data-ofs-screen": "not-found" },
    h("h1", null, "No such screen"),
    h("p", null, "This build of the shell has no screen at ", h("code", null, path), "."),
    h("p", null, h("a", { href: "#/" }, "Back to the project")),
  );
}

// The text of the fatal panel for an uncaught error or rejection.
export function fatalText(reason) {
  if (reason instanceof Error) return `${reason.name}: ${reason.message}\n${reason.stack ?? ""}`;
  return `Uncaught: ${String(reason)}`;
}
