"""pytest plugin: record every provider answer to $REC_OUT, one line per call (spec §19.7, A46).

Each line is ``tag|component|first argument|result`` with ``repr`` (round-trip exact for floats).
It records the S07 and S05 providers' ``evaluate_phase`` and ``flash``, S07's
``_solve_saturation`` and S05's ``iapws95._saturation``. Two records from the same tests before
and after a change are compared with ``cmp.py``. The identity proofs of WO-S07-NC2/NC3 were made
with these two scripts; the digests are in ``docs/S07_DECISIONS.md``. From the repository root,
in the CoolProp environment:

    export PYTHONPATH=$PWD/src:$PWD:$PWD/docs/derivations/scripts/s07_measurements
    export OPENFLOWSHEET_REQUIRE_COOLPROP=1
    REC_OUT=s07.rec python -m pytest -q -p no:cacheprovider -p recplug \\
        tests/test_s07_broad.py tests/test_s07_coolprop.py tests/test_s07_packaging.py
    REC_OUT=s05.rec python -m pytest -q -p no:cacheprovider -p recplug \\
        tests/test_s05_envelope.py tests/test_s05_iapws95.py tests/test_s05_review_adversarial.py
    sha256sum s07.rec s05.rec
"""

import os

_OUT = open(os.environ["REC_OUT"], "w")  # noqa: SIM115 - closed in pytest_unconfigure


def _wrap(cls, name, tag):
    original = getattr(cls, name)

    def wrapper(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        key = getattr(getattr(self, "_fluid", None), "component", "")
        _OUT.write(f"{tag}|{key}|{args[0]!r}|{result!r}\n")
        return result

    setattr(cls, name, wrapper)


def pytest_configure(config):
    from openflowsheet.thermo import coolprop_heos, iapws95

    for cls, tag in ((coolprop_heos.CoolPropHeosProvider, "S07"), (iapws95.Iapws95Provider, "S05")):
        _wrap(cls, "evaluate_phase", tag + ".eval")
        _wrap(cls, "flash", tag + ".flash")
    _wrap(coolprop_heos.CoolPropHeosProvider, "_solve_saturation", "S07.sat")
    original = iapws95._saturation

    def sat(t):
        result = original(t)
        _OUT.write(f"S05.sat||{t!r}|{result!r}\n")
        return result

    sat.cache_clear = original.cache_clear
    sat.cache_info = original.cache_info
    iapws95._saturation = sat


def pytest_unconfigure(config):
    _OUT.close()
