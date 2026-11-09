// The viewer's display units (ADR 0075 D5.1, X04 A38): a choice kept per viewer in browser
// storage and sent as `display_units` by the screens that show converted numbers (the streams
// screen's stream table, the failure screen). The shell never converts a number (A39): every
// converted value it shows is a `display` item the server wrote, with its SI value and unit kept
// in the element's title. SI sends no preference, so its documents are the ones without X04.

export const UNITS_KEY = "openflowsheet.display_units";

// The choices: SI, the `eng` preset, and `eng` with gauge pressure — a gauge unit is resolved
// against the project's declared ambient pressure, so that choice is offered only when
// `get_project.ambient_pressure` is not null (ADR 0075 D6.4: never assumed).
export const UNIT_CHOICES = Object.freeze([
  Object.freeze({ value: "si", label: "SI", gauge: false }),
  Object.freeze({ value: "eng", label: "eng", gauge: false }),
  Object.freeze({ value: "eng,pressure=barg", label: "eng, gauge (barg)", gauge: true }),
]);

// Whether the project declares an ambient pressure (the gauge choice's condition).
export function hasAmbient(project) {
  return project?.ambient_pressure !== null && project?.ambient_pressure !== undefined;
}

// The choices with each one's `enabled` for `project`.
export function unitChoices(project) {
  const ambient = hasAmbient(project);
  return UNIT_CHOICES.map((choice) => ({ ...choice, enabled: !choice.gauge || ambient }));
}

// The stored choice, or "si" when storage is unavailable, empty or holds anything else.
export function readUnits(storage) {
  let value = null;
  try {
    value = storage?.getItem(UNITS_KEY) ?? null;
  } catch {
    value = null;
  }
  return UNIT_CHOICES.some((choice) => choice.value === value) ? value : "si";
}

// Keeps `value` for this viewer; when storage is unavailable it applies to this page only.
export function writeUnits(storage, value) {
  try {
    storage?.setItem(UNITS_KEY, value);
  } catch {
    // Not remembered; applied for this page.
  }
}

// The choice in force for `project`: a gauge choice without a declared ambient falls back to SI
// (the server would refuse it, `ambient_pressure_undeclared`).
export function effectiveUnits(value, project) {
  const choice = UNIT_CHOICES.find((candidate) => candidate.value === value);
  if (choice === undefined || (choice.gauge && !hasAmbient(project))) return "si";
  return choice.value;
}

// The request members for `value`: none for SI, else `{display_units}`.
export function displayRequest(value) {
  return value === undefined || value === null || value === "si" ? {} : { display_units: value };
}

// ADR 0075 D7.7 (FQ4, Frank, 2026-11-09): the units human text spells otherwise — the mirror of
// `units.display.TEXT_UNITS` (a test holds the two equal). Labels and displayed values use it; a
// machine member (the display item's unit, `data-ofs-display`, the request) keeps the D2 spelling.
export const TEXT_UNITS = Object.freeze({ degC: "°C", degF: "°F" });

// `unit` as human text shows it: `degC` → `°C`, `degF` → `°F`, every other unit unchanged.
export function textUnit(unit) {
  return Object.hasOwn(TEXT_UNITS, unit) ? TEXT_UNITS[unit] : unit;
}
