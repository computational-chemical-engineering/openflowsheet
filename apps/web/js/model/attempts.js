// Attempts of a solve, from its recorded events (M06 design note §5.6 rule 1, §6.3).
//
// Display arithmetic over recorded counters, nothing else: an attempt's counters are its
// `attempt_closed` event's `counters` minus the matching `attempt_opened` event's, matched by
// `(step_index ?? null, attempt)`. An `attempt_closed` event with a non-null `homotopy_level` is
// a homotopy corrector closing its own run inside the attempt, not an attempt
// (`verify/failure.py`, ADR 0010 D7.2). Counters no attempt accounts for are the final event's
// counters minus the sum of the attempts' deltas: "outside attempts".

function matchKey(event) {
  return `${JSON.stringify(event.step_index ?? null)} ${JSON.stringify(event.attempt)}`;
}

// `b - a` per counter name of `b`; null when either side lacks a counter object.
export function counterDelta(b, a) {
  if (!b || !a) return null;
  const out = {};
  for (const [name, value] of Object.entries(b)) out[name] = value - (a[name] ?? 0);
  return out;
}

function corrector(event) {
  return event.homotopy_level !== undefined && event.homotopy_level !== null;
}

// `{attempts, totals, outside}` of a solve's events (the `solve-events.json` array):
// `attempts` in closing order, each `{step_index, attempt, signature, outcome, iterations,
// deltas, opened}` (`opened` false and `deltas` null when no opening event matched); an attempt
// opened and never closed is listed last with outcome null. `totals` is the final event's
// counters; `outside` is `totals` minus every attempt's deltas.
export function attemptsOf(events) {
  const opened = new Map();
  const closed = new Set();
  const attempts = [];
  for (const event of events) {
    if (event.kind === "attempt_opened" && !corrector(event)) {
      opened.set(matchKey(event), event);
    } else if (event.kind === "attempt_closed" && !corrector(event)) {
      const key = matchKey(event);
      const start = opened.get(key);
      closed.add(key);
      attempts.push({
        step_index: event.step_index ?? null,
        attempt: event.attempt,
        signature: event.signature ?? start?.signature ?? null,
        outcome: event.outcome ?? null,
        iterations: event.iteration ?? null,
        deltas: counterDelta(event.counters, start?.counters),
        opened: start !== undefined,
      });
    }
  }
  for (const [key, start] of opened) {
    if (closed.has(key)) continue;
    attempts.push({
      step_index: start.step_index ?? null,
      attempt: start.attempt,
      signature: start.signature ?? null,
      outcome: null,
      iterations: null,
      deltas: null,
      opened: true,
    });
  }
  const last = events.length > 0 ? events[events.length - 1] : null;
  const totals = last?.counters ?? null;
  let outside = null;
  if (totals) {
    outside = { ...totals };
    for (const { deltas } of attempts) {
      if (!deltas) continue;
      for (const [name, value] of Object.entries(deltas)) {
        if (name in outside) outside[name] -= value;
      }
    }
  }
  return { attempts, totals, outside };
}

// `[[instance, phase], ...]` as text: "U-HEAT VAPOR · U-PHF TWO_PHASE"; null → null.
export function signatureText(signature) {
  if (!Array.isArray(signature)) return null;
  return signature.map((pair) => (Array.isArray(pair) ? pair.join(" ") : String(pair))).join(" · ");
}
