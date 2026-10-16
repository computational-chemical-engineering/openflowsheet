"""T07 W5c: the declarative `ModelSignature` per model, and binding outcomes unchanged by it.

Design note `docs/design/T07-jobs-and-bindings.md` §4.2 (`list_models`) and §15 W5c. Each model id
in `MODEL_BUILDERS` has a `ModelSignature` in `MODEL_SIGNATURES` — ports, required and zero-only
parameters, the pins its builder always reads and the one-of specification choices — and the
builders read those lists from it. The refactor is inert: every registered revision binds to the
same structure, or is refused with the same `Unbound`, as at the base commit.

`EXPECTED` was generated at `b5e9b48` (branch `wp/T07`, before `ModelSignature` existed) with

    PYTHONPATH=src:.:tests python tests/test_t07_w5c_signatures.py

which prints the table `revision_outcomes()` computes; it is pinned here verbatim. A bound
revision's entry is the SHA-256 of `_structure(binding)` — the spec's ids, equations, parameters
(binary64 hex), blocks, kinds and scales, the configuration digest, row owners, the process graph,
the revision digest and the input mapping — so any change in what a builder constructs moves it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path
from typing import Any

import pytest

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:  # the `__main__` generator runs outside pytest's rootdir setup
    sys.path.insert(0, str(TESTS))

import t05b_support as t05b  # noqa: E402
import t08_cstr_support as t08  # noqa: E402
from conftest import REPO_ROOT, load_yaml  # noqa: E402
from m02_c1_corpus import C1_CORPUS, surrogates  # noqa: E402

from openflowsheet.application.revision_binding import (  # noqa: E402
    MODEL_BUILDERS,
    MODEL_SIGNATURES,
    ModelSignature,
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.models import (  # noqa: E402
    UnitModel,
    duty_id,
    flow_id,
    pressure_id,
    temperature_id,
)
from openflowsheet.models.revision_flowsheet import InstanceView, parse_revision  # noqa: E402

Document = dict[str, Any]

#: Every registered revision directory under `benchmarks/`.
CASE_GLOB = "benchmarks/*/cases/*.yaml"

#: The revisions T05b builds in code rather than keeping as files (the T06 corpus's `T05b:*`
#: fixtures are among them).
BUILT: dict[str, Callable[[], Document]] = {
    **{f"T05b:{case}": build for case, build in t05b.SINGLE_COMPONENT_CASES.items()},
    **{f"T05b:{case}": (lambda case=case: t05b.near_pure(case)) for case in t05b.NEAR_PURE_CASES},
    "T05b:NP-GC": t05b.np_gc,
    **{f"T05b:{case}": build for case, build in t05b.DORMANT_CASES.items()},
    **{f"T05b:{case}": build for case, build in t05b.DORMANT_NON_LIFTED_CASES.items()},
    # T08 W2: the kinetic CSTR's test revisions (`t08_cstr_support`), so every builder has a bound
    # instance here; the registered PTC-R1 revision is W3's.
    "T08:PTC-R1-realization": t08.ptc_r1_revision,
    "T08:liquid-variant": t08.liquid_variant_revision,
    "T08:dormant": t08.dormant_revision,
    # M02's join (R-280 (a)): the registered C1 corpus, so every C1 builder has a bound instance.
    **{f"M02:{name}": build for name, build in C1_CORPUS.items()},
}


def _plain(value: Any) -> Any:
    """JSON-able, with every float as its binary64 hex (no rounding can hide a changed bit)."""
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, str | int | bool) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    return repr(value)


def _structure(binding: RevisionBinding) -> dict[str, Any]:
    spec = binding.spec
    graph = binding.graph
    return {
        "label": spec.label,
        "variable_ids": list(spec.variable_ids),
        "equations": [[e.equation_id, e.accumulation, e.origin] for e in spec.equations],
        "parameter_ids": list(spec.parameter_ids),
        "parameters": _plain(dict(spec.parameters)),
        "blocks": [block.block_id for block in spec.blocks],
        "block_inputs": _plain(dict(spec.block_inputs)),
        "column_scales": _plain(dict(spec.column_scales)),
        "row_scales": _plain(dict(spec.row_scales)),
        "variable_kinds": _plain(dict(spec.variable_kinds)),
        "row_kinds": _plain(dict(spec.row_kinds)),
        "configuration_sha256": binding.flowsheet.configuration_sha256,
        "units": [[unit.unit_id, unit.model_id] for unit in binding.flowsheet.units()],
        "row_units": _plain(dict(binding.row_units)),
        "graph": {
            "units": list(graph.units),
            "connections": _plain(graph.connections),
            "instance_ids": _plain(dict(graph.instance_ids)),
            "column_owners": _plain(dict(graph.column_owners)),
        },
        "revision_sha256": binding.revision_sha256,
        "input_mapping": _plain(binding.input_mapping),
    }


def outcome(document: Document) -> str:
    """`binds <sha256 of the structure>`, or the `Unbound`'s kind and detail verbatim."""
    result = bind_revision_flowsheet(document, surrogates=surrogates)
    if isinstance(result, RevisionBinding):
        text = json.dumps(_structure(result), sort_keys=True, separators=(",", ":"))
        return f"binds {hashlib.sha256(text.encode('utf-8')).hexdigest()}"
    return f"{result.kind} {result.detail}"


def _document(name: str) -> Document:
    if name in BUILT:
        return BUILT[name]()
    loaded: Document = load_yaml(REPO_ROOT / name)
    return loaded


def revision_names() -> list[str]:
    """Every registered revision file, then every T05b built revision."""
    files = [
        str(path.relative_to(REPO_ROOT).as_posix()) for path in sorted(REPO_ROOT.glob(CASE_GLOB))
    ]
    return [*files, *BUILT]


def revision_outcomes() -> dict[str, str]:
    return {name: outcome(_document(name)) for name in revision_names()}


#: Generated at `b5e9b48`; see the module docstring. Re-generated for the rename to `openflowsheet`
#: (R-149), which moved the 55 `binds` digests through the SYN-001 provider's self-hash only:
#: `tests/test_t08_rename_substitution.py` gives the pre-rename table back.
EXPECTED: dict[str, str] = {
    "benchmarks/syn001/cases/SYN-001-A02-340-two-phase-guess.yaml": (
        "unsupported specification_role_unsupported(GUESS-heater-outlet-T)"
    ),
    "benchmarks/syn001/cases/SYN-001-A02-352-vapor-guess-410.yaml": (
        "unsupported specification_role_unsupported(GUESS-heater-outlet-T)"
    ),
    "benchmarks/syn001/cases/SYN-001-A02-355-dew-guess-377.yaml": (
        "unsupported specification_role_unsupported(GUESS-heater-outlet-T)"
    ),
    "benchmarks/syn001/cases/SYN-001-A02-355-dew-guess.yaml": (
        "unsupported specification_role_unsupported(GUESS-heater-outlet-T)"
    ),
    "benchmarks/syn001/cases/SYN-001-A02-355-liquid-guess.yaml": (
        "unsupported specification_role_unsupported(GUESS-heater-outlet-T)"
    ),
    "benchmarks/syn001/cases/SYN-001-A02-355.yaml": (
        "unsupported specification_role_unsupported(GUESS-heater-outlet-T)"
    ),
    "benchmarks/syn001/cases/SYN-001-A02-360-liquid-guess.yaml": (
        "unsupported specification_role_unsupported(GUESS-heater-outlet-T)"
    ),
    "benchmarks/syn001/cases/SYN-001-A02-360-no-guess.yaml": (
        "unsupported specification_role_unsupported(GUESS-heater-outlet-T)"
    ),
    "benchmarks/syn001/cases/SYN-001-A02-360-vapor-guess.yaml": (
        "unsupported specification_role_unsupported(GUESS-heater-outlet-T)"
    ),
    "benchmarks/syn001/cases/SYN-001-A02-360.yaml": (
        "unsupported specification_role_unsupported(GUESS-heater-outlet-T)"
    ),
    "benchmarks/syn001/cases/SYN-001-A02-365.yaml": (
        "unsupported specification_role_unsupported(GUESS-heater-outlet-T)"
    ),
    "benchmarks/syn001/cases/SYN-001-all-liquid-310K.yaml": (
        "binds f88ebfd2bdc04a4f2fd81ac0d71776fe7888b5c6a55e985ab26822570aa17216"
    ),
    "benchmarks/syn001/cases/SYN-001-all-vapor-420K.yaml": (
        "binds f86ae415989f14040b0ddd47e667e5fe2acb81f8968d52b5f41cf19e83a43f55"
    ),
    "benchmarks/syn001/cases/SYN-001-conflicting-heater-spec.yaml": (
        "unsupported specification_unconsumed(SPEC-heater-duty)"
    ),
    "benchmarks/syn001/cases/SYN-001-high-recycle.yaml": (
        "binds 61909113866631330fcb610d3e5f95cd5becc7588bfb2dcaba70231290504e75"
    ),
    "benchmarks/syn001/cases/SYN-001-nominal.yaml": (
        "binds 85d6b702d79d6e6df2948b7092f856b683eb80c064dd35f749c773a325b5f9e3"
    ),
    "benchmarks/syn001/cases/SYN-001-once-through.yaml": (
        "binds c3095a4e8acef76fe3b8e924903696a73e6ac3176b03aea499c8080cf67331de"
    ),
    "benchmarks/t05/cases/SYN-001-UL-C1.yaml": (
        "binds 9c1004b0faf03826813e4f4a8991497693d2af35a5a731cd4a1628a09eed6e58"
    ),
    "benchmarks/t05/cases/SYN-001-UL-C2.yaml": (
        "binds 9891a6fcda49877381603bc60acb58b452d91ca792ddae4c24b587cc104eacbc"
    ),
    "benchmarks/t05/cases/SYN-001-UL-C3.yaml": (
        "binds 5574e4eea2cbf7525382c15c11fc336b590e06cc5ec1496ceb790f17cd4194dc"
    ),
    "benchmarks/t05/cases/SYN-001-UL-C3X.yaml": (
        "binds 0ccf4d4b5a53f1223c8bd61996ab93c858e12776a67dd39aaa82a60b3a94a7c0"
    ),
    "benchmarks/t06/cases/SYN-001-T06-NET02.yaml": (
        "binds f98601ebdcb59d9ed24fbb4cd5611cf542ad3ee7b6ec09f37520df59dc111466"
    ),
    "benchmarks/t06/cases/SYN-001-T06-NET03.yaml": (
        "binds 45dda3c9bec68953af7c9882b745df794246bbc3c5238a89fd9800d501671565"
    ),
    "benchmarks/t06/cases/SYN-001-T06-NET06.yaml": (
        "binds 3ee1919fbb194c31cec702e0a4c1af2116e1b3a979969d69c7ef31866ab09669"
    ),
    "benchmarks/t06/cases/SYN-001-T06-NET09.yaml": (
        "binds 5a0d4e63512390106eca55235d454cf0a563e6ce0163484f89c720ab22f9ba77"
    ),
    "benchmarks/t06/cases/SYN-001-T06-NET10.yaml": (
        "binds efbed4f2126b29b18895a155b746f09336dbd9ccb9c95c342821b5483c4cabb6"
    ),
    "benchmarks/t06/cases/SYN-001-T06-NET11.yaml": (
        "binds d9150265e6681d230f0950e70cbecc301a25a6f7d2c8f42fa78073da3acaf529"
    ),
    "benchmarks/t06/cases/SYN-001-T06-PC2.yaml": (
        "binds b72066aa6b4e2f27ad7bdfe5b0637ca671247482f98cc38f3f73a0673618454a"
    ),
    "benchmarks/t06/cases/SYN-001-T06-REF01.yaml": (
        "binds 62455d0fdf01e5b24bcf26f2a9f9a7d45450d11946fa827a4fd28ccc9030a409"
    ),
    "benchmarks/t06/cases/SYN-001-T06-REF02.yaml": (
        "binds 478710e3fcb388a062e722f71aea02cc66197f24412d4afe5a42346ef98ec1a6"
    ),
    "benchmarks/t06/cases/SYN-001-T06-REF03.yaml": (
        "binds 20ce3130b5b6f4945c663ee4906f948484ba2453e40998397c2bc3153ecc9341"
    ),
    "benchmarks/t06/cases/SYN-001-T06-REF04.yaml": (
        "binds 3dc1c4d825f2c79bd10f90ef0bed736f364ee9a4604c0352eb4e7ff979172791"
    ),
    "benchmarks/t06/cases/SYN-001-T06-REF05.yaml": (
        "binds 01bb763a2886fec5dfed139641ce4b181548ccb3315275411f052402040b8539"
    ),
    "benchmarks/t06/cases/SYN-001-T06-REF06.yaml": (
        "binds a2144607930cb8d61cac5a8ca0e770443832024ab26d5bdf7cd2c991320585bc"
    ),
    "benchmarks/t06/cases/SYN-001-T06-REF07.yaml": (
        "binds 5a0cfe87e753bffcd2a4d9230aa29baacbad016ef3f1a84d02794207aed03ff2"
    ),
    "benchmarks/t06/cases/SYN-001-T06-STA02.yaml": (
        "binds 96e4196667e3c4796ac1c9b81dce014459a5902dda97bc499c6bdb27c8971f40"
    ),
    "benchmarks/t06/cases/SYN-001-T06-STA03-degC.yaml": (
        "binds 4b51a847eb3c53288a6d3425cfa8666b63672494dce316ce665ab4a371acf057"
    ),
    "benchmarks/t06/cases/SYN-001-T06-STA03-kgs.yaml": (
        "binds 3801b22ad9793d2952a22f2dbfda7ada767ccfff19ae899a60df4f9457a20160"
    ),
    "benchmarks/t06/cases/SYN-001-T06-STA04.yaml": (
        "binds fc8abe1f2096ad4f77e7f6bccfd631d03a095e151d2e8016eda1bb1043d4701c"
    ),
    "benchmarks/t06/cases/SYN-001-T06-STR02.yaml": ("incomplete specification_missing(S3.T)"),
    "benchmarks/t06/cases/SYN-001-T06-STR06.yaml": (
        "unsupported specification_unsupported(SPEC-feed-n-B)"
    ),
    "benchmarks/t06/cases/SYN-001-T06-THM01.yaml": (
        "binds a8038283e1272da5161db23c11711c68041236f24b54fcc323dcc753e74935a5"
    ),
    "benchmarks/t06/cases/SYN-001-T06-THM02.yaml": (
        "binds 836e549270e0fe2df714b9d23b951e14cd1aa16a35d59a0a75d156e0c797dea5"
    ),
    "benchmarks/t06/cases/SYN-001-T06-THM10.yaml": (
        "binds b2a90c18e77767c76584d386a681c6ddf06a54f2cd09170014a642a5da31ce0c"
    ),
    "T05b:SC-1": ("binds 2f4559a59fde74b0a8f1ba076e39f76ef8a9b646824a5855f4e05fc9fdd8ac72"),
    "T05b:SC-2": ("binds c1a66bf3788ff03e5cd155b34776fca4f80e69d9db09224f7aebe4a320df3661"),
    "T05b:SC-3": ("binds 8f37afed6d8976e866e52124876e00506f09ff9008b7adec78264422a5474ef7"),
    "T05b:SC-4": ("binds 74459269302c04487fdf0b83df38a4b1c1051cc2911c08222dd5c1f62f246abd"),
    "T05b:NP-1": ("binds 8eb9b491ae2d9d7523dcb4ff6cea9b513a3875efa31c33b0d6663fda2028e9ef"),
    "T05b:NP-2": ("binds 5d442a4e1ea26498652b533e7a8d779aa6432667a82a4d56d2f84374c92ad31a"),
    "T05b:NP-3": ("binds ab6ff932ad8c626ab37767487ea231b8e811ccf8f87ea1c4bafe9205caa29889"),
    "T05b:NP-G": ("binds e532b20d018ddb7fdac43c6d0b939c0842e69f2fc1468e430fa4a1878e32fc61"),
    "T05b:NP-GC": ("binds c3c4e7b94f14ccd6935d997c5abf666299d39fab45f384bb408621c795003d56"),
    "T05b:DZ-1": ("binds dc632a64d3bca7955d915a0ff6b5249e47875b1753601a9f5dab2354a4d9b79e"),
    "T05b:DZ-2": ("binds cfe639fcb34482ad9c9a7dab1a0f38cba8b2c62e28ab3fb85a08fbf2311bcda1"),
    "T05b:DZ-3": ("binds fb6a65a4bfb6940c62a1d2c7c55dc84c8c6e9a93a0d3ea0f70a537b4c6e1e7c2"),
    "T05b:DZ-4": ("binds 5b477bbfd5ca889681a2b574c7486b73122dae26b47407a0eedbe50acb1496e2"),
    "T05b:DZ-5": ("binds eed82b54a4b910d8d4ed759d8e621bbdb71fabf7f0841ed6ed60cd029b09bae3"),
    "T05b:DZ-2C": ("binds ebf5270cbdf8e989f87d24a0a593742aadcba3f713882ab3cbbb8fba3b4ae66d"),
    "T05b:DZ-6": ("binds 639f4226ec0fff25c9a2ab539848920b8473d1b0628f2179e029e198f06f56ad"),
    "T05b:DZ-7": ("binds 2618d3ecda61f2fb2aca4e8e8d9c7e225ebddc23948a00c153624312b08e8919"),
    "T05b:DZ-8": ("binds e625bdd31cdf94e5ab4c55c48d0a01d52243633cf6a35dc4503cb26a79c64293"),
    "T05b:DZ-9": ("binds eaf446755a46795f0191670534df236b380d0ce6471e7abce3d04f338901be08"),
    "T05b:DZ-10": ("binds cd712aff96687b382932cf579d110266acee805e60bb0070b34037a9e26ec7e9"),
    "T05b:DZ-12": ("binds 5573cb9244eecdaaeb5ee6342754ac393c8d162a6593af3080b2548d790094ff"),
    "T05b:DZ-11": ("binds f2b24fedea1e74e699e053000baae49f91004971105c4a0ced31416a8099e631"),
    # Added at T08 W2 (the model did not exist at `b5e9b48`): regression values of the kinetic
    # CSTR's test revisions, generated by `outcome` at the commit that adds the model. The feed of
    # the first two moved to Amendment 1's `C` trace (§Am1.1); with the old feed `(0.5, 0.5, 0.0)`
    # they give the W2 values `20947b6d…` and `cd004f73…` again (before R-149).
    "T08:PTC-R1-realization": (
        "binds 571cb928c82146da30cbd4dbb4b3bc7e577a93e42a9eb8cd48c54081ed163733"
    ),
    "T08:liquid-variant": (
        "binds 45a818fc10fe380e4f9566ea5d99d9c9da787626a237c84ddb676f5771a4c918"
    ),
    "T08:dormant": ("binds e3e4c930948d53b37cedb4ae1256de489d247ab0f08668504c9dd2918a7d93f8"),
    # M02's join (R-280 (a)): the C1 corpus's rows, generated at the join; the rows above are
    # unchanged by it.
    "M02:C1-LOOP-M02-v1": (
        "binds fd646a2ddede5d18dde2ae445bf6b9e2e807c3fba3721cada6d7699e46ccac1e"
    ),
    "M02:C1-FLASH-F1-M02-v1": (
        "binds 048236ad9eff05e455314474db6fb80df015249ba56e525489c4919a8649271f"
    ),
    "M02:C1-HEATER-M02-v1": (
        "binds 480a8ed1bb998f323c96faa98b3759296724ad3423593c6ce15bfa18764f6bdb"
    ),
    "M02:C1-MIXER-M02-v1": (
        "binds 8d122ddb37ae3b8b3fc448a831bc024ce178df8a51cfa27fa64a6e04db0c9b86"
    ),
    "M02:C1-REACTOR-M02-v1": (
        "binds 68f5821bd967758a371284eda807ee90bcc2b9429c1bf601b6ca48c4f8ae6e66"
    ),
    # W27 Amendment 3 §22.4 (R-302): M04's surrogate revision, bound through the corpus's fixture
    # resolver; generated at its registration. The rows above are unchanged by it.
    "M02:C1-SURROGATE-M04-v1": (
        "binds 291932ea44010ce04fd47b8ddb916da1aa962428d4705b06da6de9f3ef7469b0"
    ),
}


# -- the signatures ------------------------------------------------------------------------------


@cache
def _bound() -> tuple[tuple[Document, RevisionBinding], ...]:
    """Every registered revision that binds, with its binding."""
    out = []
    for name in revision_names():
        document = _document(name)
        binding = bind_revision_flowsheet(document, surrogates=surrogates)
        if isinstance(binding, RevisionBinding):
            out.append((document, binding))
    return tuple(out)


@cache
def _units_by_model() -> dict[str, list[UnitModel]]:
    out: dict[str, list[UnitModel]] = {}
    for _, binding in _bound():
        for unit in binding.flowsheet.units():
            out.setdefault(unit.model_id, []).append(unit)
    return out


def test_every_builder_has_a_signature_in_the_same_order() -> None:
    assert list(MODEL_SIGNATURES) == list(MODEL_BUILDERS)
    assert all(signature.model_id == key for key, signature in MODEL_SIGNATURES.items())


def test_the_registered_revisions_construct_every_model() -> None:
    assert set(_units_by_model()) == set(MODEL_BUILDERS)


@pytest.mark.parametrize("model_id", list(MODEL_SIGNATURES))
def test_the_signature_ports_are_the_constructed_units_ports(model_id: str) -> None:
    units = _units_by_model()[model_id]
    assert units
    for unit in units:
        assert unit.ports() == MODEL_SIGNATURES[model_id].ports, unit.unit_id


def _templates(
    signature: ModelSignature, view: InstanceView, components: tuple[str, ...]
) -> set[str]:
    """The required names, expanded as the signature's docstring states (written out here)."""
    names: set[str] = set()
    for template in signature.required:
        if "{component}" in template:
            names |= {template.replace("{component}", c) for c in components}
        elif template.endswith("{key}"):
            prefix = template[: -len("{key}")]
            names |= {name for name in view.parameters if name.startswith(prefix)}
        else:
            names.add(template)
    return names


def _pin_columns(
    view: InstanceView, quantity: str, port: str | None, components: tuple[str, ...]
) -> set[str]:
    if port is None:
        assert quantity == "duty"
        return {duty_id(view.unit_id)}
    (stream,) = view.ports[port]
    if quantity == "flow":
        return {flow_id(stream, c) for c in components}
    return {temperature_id(stream) if quantity == "temperature" else pressure_id(stream)}


def test_the_signature_describes_every_bound_instance_exactly() -> None:
    """What `list_models` reports is what binding reads: on every bound instance, the declared
    parameters are the required ones plus zero-only ones present, and the pinned columns are the
    always-read pins plus exactly one option of each choice."""
    checked = 0
    for document, _ in _bound():
        view = parse_revision(document)
        for instance in view.instances:
            signature = MODEL_SIGNATURES[instance.model_id]
            required = _templates(signature, instance, view.components)
            assert required <= set(instance.parameters), instance.unit_id
            assert set(instance.parameters) - required <= set(signature.zero), instance.unit_id
            expected: set[str] = set()
            for pin in signature.pins:
                expected |= _pin_columns(instance, pin.quantity, pin.port, view.components)
            for choice in signature.choices:
                pinned = [
                    option
                    for option in choice.options
                    if _pin_columns(instance, option.quantity, option.port, view.components)
                    <= set(instance.pins)
                ]
                assert len(pinned) == 1, (instance.unit_id, choice.name)
                expected |= _pin_columns(
                    instance, pinned[0].quantity, pinned[0].port, view.components
                )
            assert set(instance.pins) == expected, instance.unit_id
            checked += 1
    assert checked > 0


# -- binding outcomes unchanged ---------------------------------------------------------------


def test_the_pinned_table_covers_every_registered_revision() -> None:
    assert revision_names() == list(EXPECTED)


@pytest.mark.parametrize("name", list(EXPECTED))
def test_binding_outcome_is_unchanged(name: str) -> None:
    assert outcome(_document(name)) == EXPECTED[name]


if __name__ == "__main__":
    print("EXPECTED: dict[str, str] = {")
    for name, value in revision_outcomes().items():
        print(f"    {json.dumps(name)}: (\n        {json.dumps(value)}\n    ),")
    print("}")
