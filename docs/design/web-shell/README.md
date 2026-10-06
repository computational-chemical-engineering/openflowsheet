# Web-shell design (M06 input)

Design exploration made in Claude Design from `../web-shell-design-brief.md`, imported
2026-09-29 from the Claude Design project "Design project kickoff form"
(`d0fb614a-863d-4c04-9127-e0e61961efc3`, owner Frank Peters).

**Status:** accepted by Frank as the visual starting point for M06 (diagnostic web shell). It is a
design reference, not product code: nothing here is served by the application, and M06 remains
where the plan puts it (after T08) unless a plan amendment moves it.

| File | What it is |
| --- | --- |
| `Workbench.dc.html` | The workbench prototype: revision list, overview, validation/DOF, solve run with trace, certificate, streams and units, failure bundle, compare, education mode. Sample data is the brief's NET-02 / STR-03 excerpt. |
| `support.js` | Claude Design's generated `dc-runtime` (renders `<x-dc>` templates with React). Needed only to open the prototype; not a project dependency. |

The companion page `Design System.dc.html` stays in the Claude Design project; its tokens are
recorded below.

## Tokens

Families: IBM Plex Sans (prose, labels) and IBM Plex Mono (identifiers, operations, units, every
number); tabular numerals throughout. Status is always glyph + word + tone, never hue alone:
✓ ok, ◐ info, ! warn, ✕ bad, – none (dashed border). Green only for evidence that passed
(VERIFIED, PASS, MATCH); CONVERGED is info-blue because it carries no certificate; an unknown
label falls through to the failure tone.

| Token | Light | Dark |
| --- | --- | --- |
| bg | `#f6f6f3` | `#121416` |
| surface | `#ffffff` | `#1a1d20` |
| sunken | `#f0f0ec` | `#202428` |
| line | `#e2e2dc` | `#2c3035` |
| line-strong | `#cdcdc5` | `#3a3f45` |
| ink | `#16181b` | `#e8e9ea` |
| ink-2 | `#464b51` | `#a9adb2` |
| ink-3 | `#686d73` | `#9ba0a6` |
| link | `#2b5ca8` | `#8fb3ec` |
| ok | `#1c6a39` | `#86d4a0` |
| info | `#24508f` | `#93b6ea` |
| warn | `#7a5600` | `#e6c56e` |
| bad | `#a1261c` | `#f0a197` |
| gap | `#5d3f98` | `#c2aef0` |
| edu | `#0e5f5c` | `#7fd3cb` |
| select | `#e5ecf7` | `#1d2d45` |

Pill tones (fg / bg / border), light: ok `#1c6a39/#e4f1e8/#b7d9c2`, info `#24508f/#e5ecf7/#bccae4`,
warn `#7a5600/#faf0d4/#e6d29a`, bad `#a1261c/#f8e3e0/#e7b7b0`, none `#464b51/#f0f0ec/#c9c9c1`.
Dark: ok `#86d4a0/#173323/#2f5a3e`, info `#93b6ea/#18263b/#2d4466`, warn `#e6c56e/#33290f/#5a4818`,
bad `#f0a197/#3a1a17/#63302a`, none `#b3b7bc/#24282c/#454a50`.

## Data gaps the design raised (G1–G11)

The prototype tags every place where the brief's data did not give a screen what it needs. They
are triaged in `gap-triage.md`: which are artefacts of the brief's excerpt (the records hold the
data), which are records the application contract does not yet expose (T07), and which need a
design-lane answer before M06.
