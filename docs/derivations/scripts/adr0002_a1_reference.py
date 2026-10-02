"""Independent reference generator for ADR 0002 Amendment 1: which integers are canonical JSON.

ADR 0002 D3.3 (as amended) admits an integer `n` exactly when its decimal digits are the ECMA-262
`Number::toString` spelling of the binary64 nearest to `n`. This script decides that for the
registered integers **by exact integer arithmetic alone**: it rounds `n` to binary64 itself
(round-half-even), finds the reals that round to that binary64, and applies D3.3's digit
selection (fewest significant digits, then closest, then even) directly. It imports nothing from
`process_runtime`, and the emitted verdicts, bits and spellings use neither `float()` nor `repr`.
CPython's `float()` and `struct` appear only in `--check`'s cross-checks (claims C8, C9), as an
independent second implementation of the rounding, never as a source of an emitted value.

Emitted (`docs/derivations/scripts/adr0002_a1_reference.json`):

* `integers` -- the registered states: the integer as a decimal string, why it is registered, its
  verdict before and after the amendment, the bits of its nearest binary64, that binary64's
  canonical spelling, and the reading `units.read_number` must give.
* `samples` -- the seeds and ranges of the sampled assertions J11 and J12.
* `generator_claims` -- the self-claims `--check` re-derives; the script refuses to emit if one
  fails.

Every integer is written as a JSON *string*: this file must not depend on the rule it registers.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/adr0002_a1_reference.py --check
    python docs/derivations/scripts/adr0002_a1_reference.py \
        --emit docs/derivations/scripts/adr0002_a1_reference.json

`--emit` is byte-reproducible. `--check` also confirms that the committed JSON, if present, is
byte-identical to what `--emit` would write.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DEFAULT_JSON = Path(__file__).with_name("adr0002_a1_reference.json")

EXACT = 2**53  # every integer with |n| <= 2^53 is a binary64
EXPONENT_FORM = 10**21  # D3.3 layout (a) needs n <= 21 digits; from here on the spelling has "e+"
OVERFLOW = 2**1024 - 2**970  # the smallest magnitude that rounds to infinity (IEEE-754)

#: (id, n, why). The order is the table order of ADR 0002 Amendment 1.
REGISTERED: tuple[tuple[str, int, str], ...] = (
    ("I01", 2**53, "2^53: the old boundary; admitted under both rules (T06 A100 (b))"),
    (
        "I02",
        2**53 + 1,
        "2^53+1: J2, T06 A100 (a) and T07 G10's integer; its nearest binary64 "
        "is 2^53 (a tie, to the even mantissa); refused under both rules",
    ),
    ("I03", -(2**53 + 1), "sign symmetry of I02"),
    (
        "I04",
        2**53 + 2,
        "2^53+2: exact, and its own canonical spelling; refused before, admitted "
        "now; the value the pre-amendment test_j7 asserted refused",
    ),
    (
        "I05",
        2**54,
        "2^54: a power of two, whose rounding interval is asymmetric (the ulp below "
        "is half the ulp above); admitted now",
    ),
    (
        "I06",
        2**55,
        "2^55: exact, but its binary64 is spelled 36028797018963970; refused under "
        "both rules, so exactness is not the criterion",
    ),
    (
        "I07",
        36028797018963970,
        "the canonical spelling of I06's binary64, 2 away from it; "
        "admitted now, so the criterion is the spelling",
    ),
    (
        "I08",
        592612204108959000,
        "the measured witness: T07 W7c's V17 T08 certificate, "
        "regularity.inverse_one_norm_estimate = 5.92612204108959e17 as written; admitted now",
    ),
    ("I09", -592612204108959000, "sign symmetry of I08"),
    ("I10", 592612204108958976, "the exact value of I08's binary64; refused under both rules"),
    ("I11", 2**60, "2^60: exact; J2's float 2.0**60 is spelled I12, not this"),
    (
        "I12",
        1152921504606847000,
        "J2's registered bytes for 2.0**60, read back by json.loads; "
        "admitted now (before, ADR 0002's own J2 vector failed its round trip)",
    ),
    (
        "I13",
        2**64 - 1,
        "2^64-1: the shape of a u64 seed or hash; its nearest binary64 is 2^64; "
        "refused under both rules, which is the refusal D3.3 exists for",
    ),
    ("I14", 2**64, "2^64: exact, spelled 18446744073709552000; refused under both rules"),
    ("I15", 18446744073709552000, "the canonical spelling of 2^64; admitted now"),
    (
        "I16",
        10**20,
        "10^20: the largest power of ten spelled without an exponent (21 digits); admitted now",
    ),
    ("I17", 2**68, "2^68: exact; D3.3's own example spells its binary64 I18"),
    ("I18", 295147905179352830000, "D3.3's registered spelling of 2^68 (21 digits); admitted now"),
    (
        "I19",
        10**21 - 1,
        "10^21-1: its nearest binary64 is 10^21, spelled 1e+21; refused under both rules",
    ),
    (
        "I20",
        10**21,
        "10^21: exact, spelled 1e+21; refused under both rules (the exponent-form guard)",
    ),
    (
        "I21",
        10**400,
        "10^400: beyond binary64's range; refused with no OverflowError (T06 A100 (a))",
    ),
    ("I22", -(10**400), "sign symmetry of I21"),
)

#: Assertion J11's and J12's samples (ADR 0002 Amendment 1). The test draws them with
#: `random.Random(seed)`; this file only registers the parameters.
SAMPLES = {
    "j11": {
        "seed": 20260927,
        "count": 100000,
        "law": "random.Random(seed).randint(-2**53, 2**53), count draws",
    },
    "j12": {
        "seed": 20260927,
        "count": 100000,
        "law": (
            "rng = random.Random(seed); per draw: e = rng.randint(53, 69); "
            "m = rng.getrandbits(52) | 2**52; s = rng.choice((1, -1)); "
            "f = s * math.ldexp(m, e - 52); kept iff abs(f) < 1e21 (the integral band)"
        ),
    },
}


# ---------------------------------------------------------------------------------- the oracle


def nearest_binary64(a: int) -> tuple[int, int, int] | None:
    """`(b, q, s)` with `b = q * 2**s` the binary64 nearest the integer `a > 2**53`, rounded
    half-to-even, or `None` when `a` rounds to infinity. `2**52 <= q < 2**53`."""
    if a >= OVERFLOW:
        return None
    s = a.bit_length() - 53
    q, r = divmod(a, 1 << s)
    half = 1 << (s - 1)
    if r > half or (r == half and q & 1):
        q += 1
        if q == 1 << 53:
            q, s = 1 << 52, s + 1
    return q << s, q, s


def bits_hex(q: int, s: int, negative: bool) -> str:
    """The IEEE-754 binary64 encoding of `(-1)**negative * q * 2**s`, big-endian hex."""
    biased = s + 52 + 1023
    assert 0 < biased < 2047 and (1 << 52) <= q < (1 << 53)
    word = (int(negative) << 63) | (biased << 52) | (q - (1 << 52))
    return f"{word:016x}"


def canonical_value(b: int, q: int, s: int) -> int:
    """D3.3's `s * 10**(n - k)` for the binary64 `b > 2**53`, as an exact integer.

    The reals that round to `b` form an interval: `[b - down/2, b + up/2]`, closed exactly when
    `b`'s mantissa `q` is even (a tie rounds to the even mantissa), where `up` is the ulp above
    and `down` the ulp below (half of `up` when `b` is a power of two). Every such `b` is an
    integer with an interval at least 2 wide, so the candidates with fewest significant digits
    are the multiples of the largest power of ten the interval holds; among them D3.3 takes the
    closest to `b`, and on a tie the even `s`.
    """
    up = 1 << s
    down = up >> 1 if q == 1 << 52 else up
    closed = q % 2 == 0
    low2, high2 = 2 * b - down, 2 * b + up  # doubled, so that the half-ulps are integers
    for j in range(len(str(b)) + 1, -1, -1):
        power: int = 10**j
        step = 2 * power
        first = -((-low2) // step)
        last = high2 // step
        if not closed:
            first += first * step == low2
            last -= last * step == high2
        if first <= last:
            best = min(range(first, last + 1), key=lambda m: (abs(m * power - b), m % 2))
            return best * power
    raise AssertionError(f"no candidate for {b}")


def spelling(value: int) -> str:
    """D3.3's layout of the positive integral binary64 whose `s * 10**(n - k)` is `value`."""
    digits = str(value)
    if len(digits) <= 21:
        return digits  # layout (a)
    significant = digits.rstrip("0")
    exponent = f"e+{len(digits) - 1}"
    if len(significant) == 1:
        return significant + exponent  # layout (d)
    return significant[0] + "." + significant[1:] + exponent  # layout (e)


def judge(n: int) -> dict[str, Any]:
    """The amended rule for one integer, from the definitions only."""
    a, negative = abs(n), n < 0
    sign = "-" if negative else ""
    if a <= EXACT:
        # Exact, and its own spelling: a shorter decimal would be a different integer, and every
        # integer here is a binary64 of its own, so none rounds to `n` (Amendment 1, the proof).
        if a == 0:
            return {"verdict": "admitted", "binary64": "0" * 16, "spelling": "0", "value": 0}
        s = a.bit_length() - 53
        q = a >> s if s > 0 else a << -s
        return {
            "verdict": "admitted",
            "binary64": bits_hex(q, s, negative),
            "spelling": str(n),
            "value": n,
        }
    nearest = nearest_binary64(a)
    if nearest is None:
        return {"verdict": "refused", "binary64": None, "spelling": None, "value": None}
    b, q, s = nearest
    value = canonical_value(b, q, s)
    text = sign + spelling(value)
    admitted = a < EXPONENT_FORM and value == a
    return {
        "verdict": "admitted" if admitted else "refused",
        "binary64": bits_hex(q, s, negative),
        "spelling": text,
        "value": (-b if negative else b),
    }


def table() -> list[dict[str, Any]]:
    rows = []
    for identifier, n, why in REGISTERED:
        judged = judge(n)
        rows.append(
            {
                "id": identifier,
                "n": str(n),
                "why": why,
                "verdict_before": "admitted" if abs(n) <= EXACT else "refused",
                "verdict": judged["verdict"],
                "binary64": judged["binary64"],
                "binary64_exact_integer": (
                    None if judged["value"] is None else str(judged["value"])
                ),
                "spelling_of_binary64": judged["spelling"],
                "read_number": (
                    "binary64" if judged["verdict"] == "admitted" else ("-inf" if n < 0 else "+inf")
                ),
            }
        )
    return rows


# ---------------------------------------------------------------------------------- the claims


def claims(rows: list[dict[str, Any]]) -> dict[str, str]:
    """Every claim the amendment makes about these numbers, re-derived. Raises on the first
    failure; returns a one-line summary per claim for the emitted file."""
    ns = [int(row["n"]) for row in rows]
    by_id = {row["id"]: row for row in rows}
    out: dict[str, str] = {}

    assert len(set(ns)) == len(ns) and len(by_id) == len(rows), "C1"
    out["C1"] = f"{len(rows)} registered integers, pairwise distinct"

    beyond = [row for row in rows if abs(int(row["n"])) > EXACT]
    admitted_beyond = [row["id"] for row in beyond if row["verdict"] == "admitted"]
    refused_beyond = [row["id"] for row in beyond if row["verdict"] == "refused"]
    at_or_below = [row["id"] for row in rows if abs(int(row["n"])) <= EXACT]
    assert len(admitted_beyond) >= 3 and len(refused_beyond) >= 3 and at_or_below, "C2"
    out["C2"] = (
        f"beyond 2^53: {len(admitted_beyond)} admitted {admitted_beyond}, "
        f"{len(refused_beyond)} refused {refused_beyond}; at or below: {at_or_below}"
    )

    pairs = (("I06", "I07"), ("I10", "I08"), ("I11", "I12"), ("I14", "I15"), ("I17", "I18"))
    for exact_id, spelled_id in pairs:
        exact, spelled = by_id[exact_id], by_id[spelled_id]
        assert exact["binary64"] == spelled["binary64"], f"C3 {exact_id}"
        assert exact["binary64_exact_integer"] == exact["n"], f"C3 {exact_id} exact"
        assert spelled["binary64_exact_integer"] != spelled["n"], f"C3 {spelled_id} inexact"
        assert (exact["verdict"], spelled["verdict"]) == ("refused", "admitted"), f"C3 {exact_id}"
    out["C3"] = (
        f"{len(pairs)} binary64 values registered twice: the exact integer refused, the "
        "canonical spelling (inexact) admitted"
    )

    for row in rows:
        n = int(row["n"])
        if abs(n) < EXPONENT_FORM:
            assert (row["verdict"] == "admitted") == (row["spelling_of_binary64"] == row["n"]), (
                f"C4 {row['id']}"
            )
    out["C4"] = "below 10^21: admitted exactly when the binary64's spelling is the integer's digits"

    assert not [r for r in rows if (r["verdict_before"], r["verdict"]) == ("admitted", "refused")]
    changed = [r["id"] for r in rows if r["verdict_before"] != r["verdict"]]
    assert changed == admitted_beyond, "C5"
    out["C5"] = f"no state goes admitted -> refused; the states that change are {changed}"

    anchors = {  # ADR 0002's own registered spellings, recomputed by the oracle
        2**68: "295147905179352830000",  # D3.3
        2**60: "1152921504606847000",  # J2
        10**20: "100000000000000000000",  # J1
        10**21: "1e+21",  # J1
    }
    for n, text in anchors.items():
        assert judge(n)["spelling"] == text, f"C6 {n}"
    out["C6"] = "the oracle reproduces ADR 0002's registered spellings of 2^60, 2^68, 1e20, 1e21"

    window = range(EXACT, EXACT + 4097)
    assert all((judge(n)["verdict"] == "admitted") == (n % 2 == 0) for n in window), "C7a"
    starts = (2**55, 2**60, 592612204108959000 - 2048, 10**20 - 2048, 2**68 - 2048)
    for start in starts:
        integers = range(start, start + 4096)
        admitted = {n for n in integers if judge(n)["verdict"] == "admitted"}
        spellings: set[int] = set()
        for n in integers:
            nearest = nearest_binary64(n)
            assert nearest is not None
            spellings.add(canonical_value(*nearest))
        assert admitted == spellings & set(integers), f"C7b {start}"
        assert len({judge(n)["binary64"] for n in admitted}) == len(admitted), f"C7b {start}"
    out["C7"] = (
        "[2^53, 2^53+4096]: admitted exactly the even integers; in 4096-wide windows at 2^55, "
        "2^60, the witness, 1e20 and 2^68, the admitted integers are exactly the canonical "
        "spellings in the window, one per binary64"
    )

    for row in rows:
        n = int(row["n"])
        if row["binary64"] is not None:
            cpython = f"{struct.unpack('>Q', struct.pack('>d', float(n)))[0]:016x}"
            assert cpython == row["binary64"], f"C8 {row['id']}"
    out["C8"] = "the oracle's rounding equals CPython's float(n) on every registered integer"

    witness = f"{struct.unpack('>Q', struct.pack('>d', 5.92612204108959e17))[0]:016x}"
    assert by_id["I08"]["binary64"] == witness and by_id["I08"]["verdict"] == "admitted", "C9"
    out["C9"] = f"I08 is the binary64 of the decimal 5.92612204108959e17 ({witness})"

    for row in rows:
        if row["verdict"] == "refused":
            expected = "-inf" if int(row["n"]) < 0 else "+inf"
            assert row["read_number"] == expected, f"C10 {row['id']}"
    out["C10"] = "every refused integer reads as the infinity of its sign (T06 A100 (a))"
    return out


def document() -> dict[str, Any]:
    rows = table()
    return {
        "schema": "adr0002-a1-reference-v1",
        "generator": "docs/derivations/scripts/adr0002_a1_reference.py",
        "specification": "docs/adr/0002-canonicalization-and-schemas.md, Amendment 1",
        "note": (
            "Integers are decimal strings. Verdicts, bits and spellings come from exact integer "
            "arithmetic on ECMA-262 Number::toString's definition; none from process_runtime."
        ),
        "integers": rows,
        "samples": SAMPLES,
        "generator_claims": claims(rows),
    }


def emitted() -> bytes:
    return (json.dumps(document(), indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="re-derive every claim")
    parser.add_argument("--emit", metavar="PATH", help="write the reference JSON")
    arguments = parser.parse_args(argv)
    if not arguments.check and not arguments.emit:
        parser.error("choose --check and/or --emit PATH")
    data = emitted()  # raises, and emits nothing, if a claim fails
    if arguments.check:
        for name, summary in json.loads(data)["generator_claims"].items():
            print(f"PASS {name}: {summary}")
        if DEFAULT_JSON.is_file():
            if DEFAULT_JSON.read_bytes() != data:
                print(f"FAIL {DEFAULT_JSON.name} differs from what --emit writes")
                return 1
            print(f"{DEFAULT_JSON.name} is byte-identical to --emit")
    if arguments.emit:
        Path(arguments.emit).write_bytes(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
