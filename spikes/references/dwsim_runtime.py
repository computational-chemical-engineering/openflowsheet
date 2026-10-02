"""Load DWSIM 9.0.5's automation API headless into CPython (T06 reference environment).

DWSIM's Linux package targets the .NET 8 runtime (`DWSIM.UI.Desktop.runtimeconfig.json`,
framework ``Microsoft.NETCore.App`` 8.0.11). `scripts/build-reference-envs.sh` unpacks the pinned
.deb and a pinned .NET 8 runtime under `.venv-dwsim/`; this module starts that runtime through
pythonnet's CoreCLR loader with DWSIM's own runtime configuration and loads the assemblies the
automation API needs. No display is used: `Automation3` is DWSIM's GUI-less automation class.

Shared by `dwsim_smoke.py` and `dwsim_representability.py`; not imported by anything in `src/`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = REPO_ROOT / ".venv-dwsim"

ASSEMBLIES = (
    "DWSIM.Automation",
    "DWSIM.Interfaces",
    "DWSIM.GlobalSettings",
    "DWSIM.SharedClasses",
    "DWSIM.Thermodynamics",
    "DWSIM.UnitOperations",
)

_automation: Any = None


def start(env_dir: Path = DEFAULT_ENV) -> Any:
    """Start .NET, load DWSIM, and return one `DWSIM.Automation.Automation3` instance.

    DWSIM resolves data files (compound databases, property-package resources) relative to the
    working directory, so the process changes into the DWSIM directory, as its own launcher
    script `usr/local/bin/dwsim` does. Callers must therefore use absolute paths.
    """
    global _automation
    if _automation is not None:
        return _automation
    dwsim_dir = env_dir / "dwsim"
    dotnet_root = env_dir / "dotnet"
    if not (dwsim_dir / "DWSIM.Automation.dll").is_file():
        raise FileNotFoundError(f"no DWSIM under {dwsim_dir}; run scripts/build-reference-envs.sh")

    from pythonnet import load

    load(
        "coreclr",
        runtime_config=str(dwsim_dir / "DWSIM.UI.Desktop.runtimeconfig.json"),
        dotnet_root=str(dotnet_root),
    )
    import clr

    os.chdir(dwsim_dir)
    for name in ASSEMBLIES:
        clr.AddReference(str(dwsim_dir / f"{name}.dll"))
    from DWSIM.Automation import Automation3

    _automation = Automation3()
    return _automation
