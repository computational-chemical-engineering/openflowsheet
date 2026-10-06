# ADR 0030 — The diagnostic web shell: a no-build browser client of the HTTP binding

**Status:** **Proposed**, 2026-10-06 (design lane, `architect`, M06). Becomes Accepted with M06's tested evidence
and the design-lane review (W26).
**Normative text:** `docs/design/M06-web-shell.md` §5 (architecture), §7 (security), §8 (testing).
**Companion:** ADR 0019 Amendment 3 (the contract widening the shell needs).
**Affected requirements:** blueprint §12 (web workbench), §14.4 (W26), §15 (repository layout; one installable
package); ADR 0006 (distribution rights: nothing third-party is added); R-019 (no layer parses ids).
**Affected packages:** M06; every later UI change.

## Context

M06 adds the project's first browser-facing component to a repository with no Node tooling, a frozen
application contract (ADR 0019/0020), an Apache-2.0 licence whose NOTICE states that no third-party binaries
are distributed, and a gate (ruff, mypy strict, ~6900 pytest tests) that must stay green and run without a GUI.

## Decision

- **D1 — No build, no framework, nothing third-party.** The shell is hand-written ES modules and CSS, loaded by
  the browser as written. No npm, no `package.json`, no bundler or transpiler, no vendored library, font or image.
  Rendering goes through an in-house builder (`h` returns plain trees; `mount` creates DOM) that can create only
  text nodes and whitelisted attributes, with event handlers only on interactive elements.
- **D2 — Source and shipping.** The source of truth is `apps/web/` (blueprint §15). It ships as package data
  through the symlink `src/openflowsheet/_data/web → ../../../apps/web`, the `_data/schemas` pattern, and
  T08.A43's build check proves the wheel's bytes equal the commit's.
- **D3 — Serving.** `openflowsheet serve-http --ui` serves the unchanged HTTP binding plus a static mount at
  `/ui/` on the same origin (`application/bindings/web.py`, under the bindings' import rule). Off by default;
  loopback by default; no CORS; every `/ui` response carries a strict Content-Security-Policy (no inline script
  or style, no foreign origin) and `nosniff`, `no-referrer`, `no-cache`, same-origin opener/resource policies.
- **D4 — Browser credentials.** The existing bearer token, entered in a login form, kept in `sessionStorage`
  (opt-in `localStorage`) and sent only in the `Authorization` header. Never a cookie (no ambient authority, so
  CSRF and DNS rebinding gain nothing); never in a URL the application builds.
- **D5 — Contract only.** One `fetch` call site; URLs built from a route table generated from `OPERATIONS` and
  checked by a test. Records are read whole through the raw export with a SHA-256 check against the registered
  hash; projections are reassembled by a specified expander. The client computes only the display derivations
  listed in the design note §5.6; no operation is re-implemented in the browser and no unit is converted.
- **D6 — Testing.** Python tests of every operation the shell calls and static scans of its sources; Node's
  built-in test runner (a test-time tool; no packages) on pure view-model and view functions against fixtures
  captured from real responses; a headless-Chromium smoke test recording every request. CI installs Node by a
  SHA-pinned action; `check.sh` fails without Node unless the skip is set explicitly.
- **D7 — Typography.** System font stacks naming IBM Plex first (used when installed); no font files shipped.

## Alternatives considered

- **npm toolchain (Vite/TypeScript/React).** Rejected: committed build output cannot be reviewed against its
  source, or else the wheel/sdist build needs Node; hundreds of transitive packages would enter the supply chain
  and licence inventory; the read-mostly UI does not need reactive diffing.
- **Vendored micro-framework (Preact+htm, lit-html, Alpine).** Rejected: an opaque minified file to inventory and
  maintain for a benefit (diffing re-render) the screens do not need.
- **A separate server or port, with CORS.** Rejected: CORS widens the attack surface of a token-bearing API and
  a second process adds lifecycle; same origin needs neither.
- **Cookie session with a login endpoint.** Rejected: adds an endpoint outside `OPERATIONS` and ambient authority
  that CSRF and DNS rebinding can use.
- **A UI-side diff, audit reconstruction or rights table.** Rejected: each is a second implementation of
  contract semantics; ADR 0019 Amendment 3 provides them once, for every client.
- **Playwright or Selenium in the default gate.** Rejected for now: a large browser download in every check; the
  logic is covered by Node tests and the smoke test needs only a system browser. Kept as the fallback if the
  `--dump-dom` smoke test proves flaky (design note §12 R1).
- **Vendoring IBM Plex.** Not chosen by default: it would make NOTICE's statement false and needs an ADR 0006
  amendment (OFL-1.1 with reserved font name "Plex", files unmodified). Frank's preference (F3).

## Consequences

- Any later UI work stays within D1: adding a dependency, a build step or a framework takes a new ADR.
- The shell can only show what the contract serves; a missing datum becomes a contract ask, not a UI shortcut.
- Developers need Node ≥ 22 on `PATH` to run the full gate (or set `OPENFLOWSHEET_SKIP_WEB_TESTS=1` visibly).
- `serve-http` without `--ui` is unchanged byte for byte.

## Acceptance evidence

Gates G1–G12 of the design note (contract-only scan and request log, contract tests of the 17 operations,
identity unchanged, views on real data, security headers and XSS fixture, contrast, packaging, browser smoke,
green gate), recorded in `evidence/M06/<commit>/manifest.json`, and the design-lane review.
