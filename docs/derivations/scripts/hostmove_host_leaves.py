"""Reference inventory for `docs/reviews/HOSTMOVE-ruling.md` (R-1020): the host-identity leaves of
the records that RP §7.1 re-takes, and of the other committed files the ruling classifies, read at
the commit tagged `v0.4.0` (PIN). Nothing here calls OpenFlowsheet code, and nothing reads the
running host: the inventory is a fact about committed bytes, the same on every machine.

The ruling's claims about those bytes are checked here, and the script refuses to emit when one
fails (rule 4):
- each M05 environment sidecar has the writer's nine keys in the writer's order, and the five
  in-process sidecars are equal to each other;
- in M05's REAL record, every leaf whose text holds a committed host string (the platform string,
  the CPU model, the CPU-flags digest, the pinned environment's absolute root, the host name) lies
  at a registered host-identity path, and each registered path holds one committed value;
- in the five in-process records (record, ledger, store, coupling records), no leaf holds the CPU
  model or the host name: their only host-identity leaves are the sidecar's three keys;
- in M01's IDAES record, `environment.platform` is the only member that names the host, and
  neither the CPU model nor the host name occurs in it;
- T06's registered `ref-x86-64` CPU model is the one the published starts' host blocks record.

    .venv/bin/python -I docs/derivations/scripts/hostmove_host_leaves.py          # write the JSON
    .venv/bin/python -I docs/derivations/scripts/hostmove_host_leaves.py --check  # 1 on drift
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "hostmove_host_leaves.json"
#: `git rev-list -n1 v0.4.0`: the records every host-move proof of R-1020 starts from.
PIN = "b6cdf552013330c68f2fde7291c5447daae31801"
RECORDS = "benchmarks/m05/records"
FIVE = ("tr-e2", "tr-e2-far", "tr-e2-fd", "loop-r", "loop-s")
#: `m05_wo8_runs.environment_fingerprint()`'s members, in the order it writes them.
SIDECAR_KEYS = (
    "omp_num_threads",
    "python",
    "distributions",
    "distributions_sha256",
    "conda_builds",
    "conda_builds_sha256",
    "machine",
    "cpu",
    "cpu_count",
)
#: R-1020's host-identity leaves of an M05 sidecar.
SIDECAR_HOST = ("machine", "cpu", "cpu_count")
#: R-1020's host-identity leaves of the reactor's fingerprint (`platform` is R-1008's class).
FINGERPRINT = ".frozen.reactor.fingerprint."
REACTOR_HOST = ("cpu_model", "cpu_flags_sha256", "env_allowlist.NUMBA_CACHE_DIR")
#: An attempt's cheap fingerprint (M02 §2.4, `CHEAP_FINGERPRINT_FIELDS`): its one host leaf.
ATTEMPT_CPU = re.compile(r".*\.execution\.fingerprint\.cpu_model")
#: The registered host-identity path patterns of a REAL coupling record or archived attempt.
REGISTERED = (
    re.compile(re.escape(FINGERPRINT + "platform")),
    *(re.compile(re.escape(FINGERPRINT + leaf)) for leaf in REACTOR_HOST),
    ATTEMPT_CPU,
)


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def show(path: str) -> Any:
    return json.loads(git("show", f"{PIN}:{path}"))


def leaves(node: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    """Every scalar leaf with its path (`.key`, `[i]`), as `m05_retake_diff` spells paths."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from leaves(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from leaves(value, f"{path}[{index}]")
    else:
        yield path, node


def generic(path: str) -> str:
    """A path with its list indices dropped, so that equal roles count together."""
    return re.sub(r"\[\d+\]", "[]", path)


def require(condition: bool, claim: str) -> None:
    if not condition:
        raise SystemExit(f"hostmove_host_leaves: refused, a claim fails: {claim}")


def documents(stem: str) -> Iterator[tuple[str, Any]]:
    """Every committed document of an M05 record stem, the archive's files parsed one by one."""
    base = f"{RECORDS}/trust-region-study-{stem}"
    for suffix in (".json", ".ledger.json", ".store.json", ".environment.json"):
        yield suffix, show(base + suffix)
    for name in sorted(git("ls-tree", "--name-only", PIN, base + ".coupling/").split()):
        yield "coupling " + name.rsplit("/", 1)[1], show(name)
    if stem == "real":
        archive = show(base + ".experiments.json")
        for name in sorted(archive):
            yield "experiments " + re.sub(r"[0-9a-f]{64}", "<key>", name), json.loads(archive[name])


def sidecar(stem: str) -> dict[str, Any]:
    document = show(f"{RECORDS}/trust-region-study-{stem}.environment.json")
    require(tuple(document) == SIDECAR_KEYS, f"{stem}'s sidecar has the writer's nine keys")
    return document


def real() -> dict[str, Any]:
    """REAL's host leaves: where each committed host string occurs, counted per registered role."""
    s0 = show(f"{RECORDS}/trust-region-study-real.coupling/S0.json")["frozen"]["reactor"]
    fingerprint = s0["fingerprint"]
    environment = sidecar("real")
    strings = {
        "platform": fingerprint["platform"],
        "cpu_model": fingerprint["cpu_model"],
        "cpu_flags_sha256": fingerprint["cpu_flags_sha256"],
        "environment_root": fingerprint["env_allowlist"]["NUMBA_CACHE_DIR"].rsplit("/", 2)[0],
        "host_name": environment["machine"],
    }
    roles: Counter[str] = Counter()
    values: dict[str, set[str]] = {}
    for where, document in documents("real"):
        if where == ".environment.json":
            continue
        for path, value in leaves(document):
            text = value if isinstance(value, str) else ""
            hit = [name for name, needle in strings.items() if needle and needle in text]
            registered = any(pattern.fullmatch(path) for pattern in REGISTERED)
            require(not hit or registered, f"REAL {where}{path} holds {hit} off the registry")
            if registered:
                role = generic(path) if where.startswith("coupling") else "archive " + path
                role = re.sub(r"^.*(\.frozen|\.iterations)", r"\1", role)
                roles[role] += 1
                values.setdefault(role, set()).add(str(value))
    # Not vacuous: each of the six registered roles is found, and none is empty.
    require(len(roles) == 6 and all(roles.values()), "REAL holds all six registered roles")
    for role, seen in values.items():
        require(len(seen) == 1, f"REAL's {role} has one committed value")
    moving = sum(count for role, count in roles.items() if not role.endswith(".platform"))
    return {
        "committed_host_strings": strings,
        "sidecar_host": {key: environment[key] for key in SIDECAR_HOST},
        "leaves": {
            role: {"count": roles[role], "value": next(iter(values[role]))} for role in roles
        },
        "platform_leaves": sum(n for role, n in roles.items() if role.endswith(".platform")),
        "host_leaves_if_every_host_value_moves": moving + len(SIDECAR_HOST),
    }


def five() -> dict[str, Any]:
    sidecars = {stem: sidecar(stem) for stem in FIVE}
    first = sidecars[FIVE[0]]
    require(all(item == first for item in sidecars.values()), "the five sidecars are equal")
    needles = (first["machine"], first["cpu"])
    for stem in FIVE:
        for where, document in documents(stem):
            if where == ".environment.json":
                continue
            for path, value in leaves(document):
                text = value if isinstance(value, str) else ""
                require(not any(n in text for n in needles), f"{stem} {where}{path} names the host")
    return {
        "stems": [f"trust-region-study-{stem}" for stem in FIVE],
        "sidecar_host": {key: first[key] for key in SIDECAR_HOST},
        "host_leaves_if_every_host_value_moves": len(SIDECAR_HOST),
    }


def idaes(cpu: str, host: str) -> dict[str, Any]:
    record = show("benchmarks/m01/idaes-conformance.json")
    text = json.dumps(record)
    require(cpu not in text and host not in text, "the IDAES record names no CPU and no host")
    platform = record["environment"]["platform"]
    found = [path for path, value in leaves(record) if value == platform]
    require(found == [".environment.platform"], "environment.platform is its one host leaf")
    return {"environment_members": sorted(record["environment"]), "platform": platform}


def inventory() -> dict[str, Any]:
    record = show("benchmarks/m03/ipopt-inventory-x86_64.json")
    return {
        "pynumero_asl_lookup_without_pyomo_config_dir": record[
            "pynumero_asl_lookup_without_pyomo_config_dir"
        ],
        "host": record["host"],
    }


def t06() -> dict[str, Any]:
    import yaml  # noqa: PLC0415  (the test environment's; the registry is YAML)

    registry = yaml.safe_load(git("show", f"{PIN}:benchmarks/registry.yaml"))
    reference = registry["ensemble"]["machine_classes"]["ref-x86-64"]
    hosts = {
        name: show(f"benchmarks/t06/ensemble/{name}")["host"]
        for name in ("starts-nominal-v1.json", "starts-nominal-holdout1.json")
    }
    for name, host in hosts.items():
        require(host["cpu_model"] == reference["cpu_model"], f"{name} records the reference CPU")
    return {"ref-x86-64": reference, "published_starts_hosts": hosts}


def build() -> dict[str, Any]:
    reactor = real()
    strings = reactor["committed_host_strings"]
    return {
        "generator": "docs/derivations/scripts/hostmove_host_leaves.py",
        "ruling": "docs/reviews/HOSTMOVE-ruling.md",
        "pinned_commit": PIN,
        "m05_real": reactor,
        "m05_in_process": five(),
        "m01_idaes": idaes(strings["cpu_model"], strings["host_name"]),
        "m03_inventory": inventory(),
        "t06": t06(),
    }


def encode(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


def main(argv: list[str]) -> int:
    data = encode(build())
    if "--check" in argv:
        same = OUT.exists() and OUT.read_bytes() == data
        print(f"hostmove_host_leaves: {'PASS' if same else 'FAIL'}")
        return 0 if same else 1
    OUT.write_bytes(data)
    print(f"hostmove_host_leaves: wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
