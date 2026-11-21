"""X07a (WO16): every `git show <rev>:<path>` in `scripts/` and `src/` ends its arguments with `--`.

Without it git also `lstat()`s `<rev>:<path>` as a work-tree file and dies (`fatal: failed to
stat`) on any error but ENOENT/ENOTDIR, such as Windows' ENAMETOOLONG once the working directory
and the argument pass 260 characters (WO15). The scan reads each call, or argument list, that has
the string `"show"` followed by a string, f-string or concatenation that contains `:`, and asks for
a `"--"` among the same arguments.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Files frozen by an earlier registration, left as they are: `v0_1_gate.py` is pinned byte for byte
#: (`v0_1_gate_files_sha256`, test_m07a_v0_2_gate A13), `m07_journey.py` is in the journey carry set
#: (`carry.journey_files`, byte-equal to the anchor). Their calls stay without `--`.
FROZEN = ("scripts/m07_journey.py", "scripts/v0_1_gate.py")


def _has_colon(node: ast.expr) -> bool:
    """Whether `node` is a string, f-string or `+` of them with a `:` in a literal part."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) and ":" in node.value
    if isinstance(node, ast.JoinedStr):
        return any(_has_colon(part) for part in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _has_colon(node.left) or _has_colon(node.right)
    return False


def _is_string(node: ast.expr, text: str) -> bool:
    return isinstance(node, ast.Constant) and node.value == text


def unseparated_shows(tree: ast.AST) -> list[int]:
    """Lines of the `show <rev>:<path>` argument lists in `tree` that lack a `--`."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            arguments = node.args
        elif isinstance(node, ast.List):
            arguments = node.elts
        else:
            continue
        shows = [i for i, argument in enumerate(arguments) if _is_string(argument, "show")]
        if not shows:
            continue
        if any(_has_colon(argument) for argument in arguments[shows[0] + 1 :]) and not any(
            _is_string(argument, "--") for argument in arguments
        ):
            lines.append(node.lineno)
    return lines


def test_git_show_of_a_rev_path_ends_with_a_separator() -> None:
    missing = []
    for directory in ("scripts", "src"):
        for path in sorted((REPO_ROOT / directory).rglob("*.py")):
            if path.relative_to(REPO_ROOT).as_posix() in FROZEN:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            missing += [
                f"{path.relative_to(REPO_ROOT).as_posix()}:{line}"
                for line in unseparated_shows(tree)
            ]
    assert not missing, "git show <rev>:<path> without a final `--`: " + ", ".join(missing)
