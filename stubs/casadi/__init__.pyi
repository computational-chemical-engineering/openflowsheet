"""Local typing stub for CasADi 3.8.0, shadowing the malformed one the wheel ships.

**Why this file exists.** `casadi-3.8.0` ships `casadi.pyi` with a `py.typed` marker, and that stub
is not valid Python: `Sparsity.dfs` is declared as

    def dfs(self, j: int, top: int, INOUT: ..., INOUT: ..., pinv: ..., INOUT: ...) -> ...

with three parameters named `INOUT`, in four places. mypy rejects it with "Duplicate argument
'INOUT' in function definition" and then stops — `errors prevented further checking` — so the
upstream defect takes the whole type-check run down with it, including every module that has
nothing to do with CasADi. It is a SWIG stub-generation defect in the dependency; nothing in this
repository can make that file parse.

**What this does.** `__getattr__` returning `Any` is the standard way to say "this dependency has
no usable type information". It is a truthful statement here rather than a convenience: upstream's
information is unusable. It is *not* a relaxation of this project's own checks — `mypy --strict`
still applies in full to every line of `openflowsheet`, including the signatures, returns and
attribute types of the one module permitted to import CasADi
(`openflowsheet/compile/casadi_backend.py`, ADR 0003 D5.7). What is lost is static checking of
the arguments passed *into* CasADi calls in that single file, and those are covered instead by the
K01 conformance fixtures, which run the real backend and compare against independent expectations.

**When to delete it.** When a CasADi release ships a stub mypy can parse. The check is one command:

    .venv/bin/python -c "import ast,casadi,pathlib; \
        ast.parse(pathlib.Path(casadi.__file__).with_suffix('.pyi').read_text())"

`tests/test_k01_backend_dependency.py::test_the_local_casadi_stub_is_still_needed` runs exactly
that and fails if it starts succeeding, so this shim cannot outlive the defect unnoticed.
"""

from typing import Any

def __getattr__(name: str) -> Any: ...
