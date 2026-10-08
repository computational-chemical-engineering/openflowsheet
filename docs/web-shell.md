# The diagnostic web shell

A browser view of one OpenFlowsheet project, for a person diagnosing what the simulator did: revisions,
validation and degrees of freedom, runs and their traces, certificates and failure bundles, streams,
comparisons, and the project's audit history. It is a client of the HTTP binding and nothing else: every
value on a screen is a server answer, read through the same application contract an agent uses. It edits
nothing. Its only two actions are **Solve** (`submit_job`) and **Cancel** (`cancel_job`).

Normative design: `docs/design/M06-web-shell.md` (§5 architecture, §6 screens, §7 security, §8 testing) and
ADR 0030 (proposed). This page describes the shell as built. The places where the build departs from the
design note are listed in [As built](#as-built-departures-from-the-design-note).

## Starting it

```bash
openflowsheet project init ./plant --project-id plant          # once
openflowsheet project grant --project ./plant --principal frank --rights read,execute
#   prints the token once: prt_…
openflowsheet serve-http --project ./plant --ui
#   openflowsheet: web shell at http://127.0.0.1:8765/ui/
```

Open the printed address and paste the token into the sign-in form. The shell checks the token with
`get_project` and then shows the project. To hand the token over in the address instead, open
`http://127.0.0.1:8765/ui/#/?token=prt_…`. The shell reads the token from the fragment once, stores it, and
removes it from the address. A fragment is never sent to the server.

**`--ui`.**
- Off by default. Without it, `serve-http` serves the API exactly as before; nothing of the shell is
  imported.
- With it, the same server and origin also serve the shell's static files at `/ui/`, and `/` redirects to
  `/ui/`.
- The files are public to local processes, but they contain no project data. Every data request needs the
  bearer token.
- Host and port follow `serve-http`'s rules: loopback `127.0.0.1:8765` by default, and a non-loopback
  `--host` needs `--allow-remote`.
- If the packaged files are missing, the server refuses to start (exit 1).

**Rights.**

| Right | What it unlocks |
| --- | --- |
| `read` | Every screen |
| `execute` | Solve and Cancel. Without it, both buttons are shown greyed with "needs the execute right". |
| `policy` | Another principal's rows, or all principals' rows, in the agent history. Without it, those choices are greyed. If the server is asked anyway, its refusal (`forbidden`) is shown. |

**The token in the browser.**
- The token is kept in `sessionStorage` under `openflowsheet.token`. It is also kept in `localStorage`, but
  only if "remember on this browser" is ticked.
- **Sign out** clears both.
- It travels only in the `Authorization` header of the shell's own requests. It is never a cookie, never in
  a URL the shell builds, and never logged.
- A 401 (an unknown, expired or revoked token) clears the stored token and returns to the sign-in screen
  with the server's message.

**Browsers.** The shell is tested in headless Chromium only. It uses plain ES modules, CSS custom properties
and `crypto.subtle`, but no other browser is tested.

## Screens

Routes are hash routes under `/ui/`. Every screen's header shows:
- the project;
- the signed-in principal and its rights;
- the server version;
- a theme toggle (system, light, dark);
- a number toggle: short (`toPrecision(6)`) or full (shortest round-trip, Python's `repr`). Every number
  also carries its full value as a tooltip.

Statuses are pills that carry a glyph *and* a word: ✓ ok, ◐ info, ! warn, – none, ✕ bad. Any label the
shell does not know is shown as ✕ bad.

The tables below list each screen's reads (§6 of the design note, plus the extra reads listed under
[As built](#as-built-departures-from-the-design-note)) and **what the screen does not claim**.

| Route | Screen | Reads |
| --- | --- | --- |
| `#/login` | Sign in | `get_project` |
| `#/` | Project: head, revisions, recent jobs | `get_project`, `list_revisions`, `list_jobs` |
| `#/rev/{rid}` | Revision overview, flowsheet drawing, Solve | `get_revision`, `validate`, `list_revisions`, `list_jobs`, `get_job_result`, `list_models` |
| `#/rev/{rid}/validation` | Validation and degrees of freedom | `validate`, `inspect_structure` |
| `#/rev/{rid}/row/{row}` | Equation view (structure) | `inspect_structure` |
| `#/job/{jid}` | Run: summary, attempts, trace, plan, bundle files; live while running; Cancel | `get_job`, `list_job_events`, `wait_job`, `get_job_result`, `get_artifact`, `artifact_bytes` |
| `#/job/{jid}/certificate` | Certificate | `get_job_result`, `get_artifact`, `artifact_bytes`, `inspect_structure` |
| `#/job/{jid}/failure` | Failure bundle | `get_job_result`, `get_artifact`, `artifact_bytes` |
| `#/job/{jid}/streams` | Streams and units | `get_job_result`, `get_artifact`, `artifact_bytes`, `inspect_structure`, `list_models` |
| `#/job/{jid}/row/{row}` | Equation view at a run's state | `get_job_result`, `get_artifact`, `artifact_bytes`, `inspect_structure` |
| `#/job/{jid}/file/{name}` | One bundle member as a JSON tree, with download | `get_job_result`, `get_artifact`, `artifact_bytes` |
| `#/compare/rev/{a}/{b}` | Revision comparison | `diff_revisions`, `get_revision` ×2 |
| `#/compare/run/{j1}/{j2}` | Scenario view (run comparison) | per run: `get_job_result`, `get_artifact`, `artifact_bytes` |
| `#/history` | Agent history (`?principal=all` or another principal needs `policy`) | `list_audit`, then per linked row: `get_revision`, `diff_revisions`, `validate`, `get_job`, `get_job_result` |

Together these are 17 operations, and the shell calls no other (`tests/test_m06_static_scan.py`, and in a
browser `tests/test_m06_browser_smoke.py`).

### What each screen does not claim

- **Project.**
  - It lists what the project recorded: revisions, jobs, and their status counts as the server reports
    them.
  - It does not say whether any revision solves or any run is right.
- **Revision overview.**
  - Values are shown *as written* in the revision, in its units, with no conversion.
  - The validation pill is the server's `validate` (task `simulation`), asked now.
  - The flowsheet is a drawing laid out in the browser from the connections (§6.1: layers by longest path,
    recycles as arcs below). It has no geometry, and it is not a process diagram anyone drew.
  - Solve submits; it does not promise convergence.
- **Validation and degrees of freedom.**
  - Checks, structural counts, matching and degree-of-freedom rows are the server's.
  - The browser computes no matching, degrees of freedom or redundancy.
  - For an unroutable revision, the structural report shown is the validation's own analysis, and the
    screen says so.
- **Equation view.**
  - It shows structure only: the row, its residual kind and unit, the columns it touches, and the column it
    is matched to. It shows no symbolic equation text.
  - At a run's state it shows recorded values.
  - Links between rows and columns are offered only when the run's recorded structural report equals the
    structure of its revision today. Otherwise a guard says why they are not.
- **Run and trace.**
  - Job events, solve events and counters are shown as recorded.
  - Per-attempt counters are differences of the recorded counters (§5.6 rule 1). "Outside attempts" is the
    remainder.
  - There is no per-event timing. Elapsed time is the run manifest's.
  - While the job runs, the screen follows `wait_job` and reloads itself when the job ends. The live view is
    a view of the server's events, not a progress estimate.
- **Certificate.**
  - The verifier's certificate is shown as recorded.
  - The scaled residual (value ÷ reference) is display arithmetic.
  - The near-threshold flag is read from each check, never computed in the browser.
  - The shell does not re-verify anything. A certificate is local to the certified state (support matrix
    L19).
- **Failure bundle.**
  - Observations, the typed outcome, and the recorded replay identity are shown as recorded.
  - An inferred cause is labelled as the bundle labels it ("hypothesis"); it is not a diagnosis.
  - `blocked_by` is not provided (design note §4.4).
- **Streams and units.**
  - SI values from the solution state, with no conversion.
  - The vapour fraction of a phase split is display arithmetic. Components are labelled in the revision's
    component-set order.
  - A run without a solution state says so and shows its best checkpoint.
- **Bundle file.**
  - The member's bytes as stored, read through the raw export and checked against the SHA-256 the bundle
    listing registers: "match", or "mismatch" with a warning banner. Over plain HTTP from another machine
    the check is "unchecked" (an insecure context has no `crypto.subtle`).
  - Download saves exactly those bytes.
  - The tree opens the top level only.
- **Revision comparison.**
  - The members and elements that changed are the server's `diff_revisions`. The before and after values
    are read from the two revisions.
  - The browser diffs no documents.
- **Scenario view.**
  - Differences between two runs are displayed, not judged. No registered comparison, tolerance or
    agreement is applied (design note Q4).
  - It is a run comparison, not a scenario object (F4).
- **Agent history.**
  - It shows what the project recorded (every effect and every refusal), not what an agent said or claimed.
  - The validation shown beside a commit is recomputed now by the current server. It is not the report the
    agent received at commit time (R7).
  - It judges no agent.

## Security model

The local, single-user model of design note §7:
- **Exposure.** `--ui` is off by default and the server binds loopback by default. There are no CORS
  headers.
- **Credentials.** There is no ambient credential, so cross-site requests and DNS rebinding gain nothing.
- **Response headers.** Every `/ui` response carries a strict Content-Security-Policy (`default-src 'none';
  script-src 'self'; style-src 'self'; …; frame-ancestors 'none'`), `nosniff`, `no-referrer`, `no-cache`,
  and same-origin opener and resource policies.
- **Untrusted text.** Revision titles, descriptions, messages and case text reach the page only as text
  nodes, after the projection's forbidden code points (bidirectional overrides and the like) are replaced
  by U+FFFD.
- **Not provided.** There is no TLS, no multi-user hosting, and no security assessment beyond this model.
  `--allow-remote` keeps its warning.

## As built: departures from the design note

Recorded for the design-lane review (WO-13). None widens what the shell may call or show. Each is within
the 17 operations, the static scan and the CSP.

1. **Reads beyond §6's table.** All are calls to operations already among the 17:
   - The frame asks `get_project` once per page session (the header and rights).
   - `#/rev/{rid}` also reads `list_revisions`, for the revision's summary (content SHA-256, principal,
     created), which `get_revision` does not carry. It also reads `get_job_result` for each ended job of
     the revision, for the outcome and verification pills of its runs.
   - `#/job/{jid}` also reads `solution-certificate.json` (the recovery path from `branch_provenance`).
   - Every run screen reads `get_job_result` and the bundle listing (`get_artifact`) to find a member and
     the SHA-256 that §5.3's digest check compares with.
   - `#/job/{jid}/certificate` also reads `revision.json`, `structural-report.json` and `inspect_structure`,
     for the row links and the §6.5 guard.
   - `#/job/{jid}/streams` also reads `failure-bundle.json` when the run has no solution state (its best
     checkpoint).
2. **Three bundle kinds have no published record schema**: `check_policy`, `solve_path` and
   `structural_report`. The fixture validity test and the HTTP contract test hold them to being JSON objects
   only, and fail on any further kind without a schema.
3. **JSON trees open only the top level.** Deeper levels are collapsed `<details>` and open on click; their
   text is in the page either way.
4. **Certificate check labels.** The certificate's lower-case check results are mapped as follows:
   - `pass` → ok (✓), as `PASS`;
   - `fail` → bad (✕), as `FAIL`;
   - `unsupported` and `not_applicable` → none (–), the tone of `NOT_RUN`: no check was evaluated.

   This is a build-session decision pending the design-lane review. §5.5 lists only the upper-case labels,
   and would show every unlisted label as bad.
5. **A wrong method on `/ui` answers 422 `invalid_request`, not 405.** This is the binding's one error
   shape, the `ApiError` document the API gives for a method it does not route. It carries the shell's
   headers (`tests/test_m06_wo4_serving.py`).
6. **`js/frame.js`.** This module is not in §5.1's layout. It holds the frame's pure views: the header, the
   error panel, the not-found screen, and the text of the fatal marker. They are kept out of `main.js` so
   they run under Node.
7. **The `autocomplete` attribute.** It was added to `h.js`'s attribute whitelist so that the token field
   can carry §7's `autocomplete=off`. The §5.1 whitelist does not name it.
8. **The browser test drives Chromium over the DevTools protocol, not `--dump-dom`.**
   - It uses the same binary and flags (`--headless=new --disable-gpu`, a temporary profile, plus
     `--remote-debugging-pipe`), opens each route cold in a fresh browser context, waits for
     `data-ofs-ready="1"`, and reads the serialized DOM exactly as `--dump-dom` prints it.
   - Measured on the reference host, `--dump-dom --virtual-time-budget=20000` took about 24 s a route
     (8.5 min for §6's routes). The protocol run of the whole module takes about 11 s and was 10 of 10
     green.
   - The protocol also lets the test click (Solve, Cancel, download), hold a real job, and see console
     errors, uncaught exceptions and dialogs.
   - It needs only the standard library. No Playwright or Selenium dependency is added (ADR 0030's
     rejected alternative stays rejected).

## Tests

| Gate | Test |
| --- | --- |
| G1, static | `tests/test_m06_static_scan.py` |
| G1, dynamic | `tests/test_m06_browser_smoke.py`, which runs with a request recorder |
| G2 | `tests/test_m06_http_contract.py`: all 17 operations over HTTP on the W26 fixture project |
| G8 | `tests/test_m06_wo4_serving.py` checks the headers; the browser test checks hostile text in the DOM |
| G11 | `tests/test_m06_browser_smoke.py`: every route renders |
| Screen logic | Node: `node --test "tests/web/*.test.mjs"` |

The browser test looks for a browser in this order: `OPENFLOWSHEET_BROWSER`, then `chromium`,
`chromium-browser` and `google-chrome` on `PATH`. If none is found, it is skipped with that reason, unless
`OPENFLOWSHEET_REQUIRE_BROWSER=1` is set (CI's x86-64 leg), in which case it fails.
