"""ST WO-5: `openflowsheet streams` (design note `docs/design/ST-stream-table.md` §6.3; ADR 0068).

Goldens for TH-C1 in the three forms (`tests/fixtures/st/cli/`, self-generated regression fixtures,
not validation: the numbers are G1–G3's in `tests/test_st_core.py`), project and directory modes
giving one document, the JSON form equal to the operation's document, the paged assembly at
`limit=1`, `--output`, and the exit codes.
"""

from __future__ import annotations

import csv
import io
import json
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet import __version__
from openflowsheet.application import cli, stream_table, stream_table_format
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.types import Change
from openflowsheet.canonical import canonical_json
from openflowsheet.run.bundle import ARTIFACT_DIR

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import corpus_identity as f0  # noqa: E402

GOLDEN = REPO_ROOT / "tests" / "fixtures" / "st" / "cli"
RANKINE = REPO_ROOT / "examples" / "rankine-cycle.changeset.json"
TH_C2 = REPO_ROOT / "benchmarks" / "s11" / "thermal" / "TH-C2.json"
FORMATS = {"text": "TH-C1.txt", "json": "TH-C1.json", "csv": "TH-C1.csv"}


@cache
def th_c1(root: Path) -> Path:
    """TH-C1 solved as RC step 4 writes it (F0's corpus run `s11-th/TH-C1`)."""
    directory = root / "TH-C1"
    with f0.pinned_threads():
        f0.solve("s11-th", "TH-C1", directory)
    return directory


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return th_c1(tmp_path_factory.mktemp("st-cli"))


@dataclass(frozen=True)
class Solved:
    project: Path
    job_id: str

    @property
    def bundle(self) -> Path:
        return self.project / "jobs" / self.job_id / "bundle"


@pytest.fixture(scope="module")
def solved(tmp_path_factory: pytest.TempPathFactory) -> Solved:
    """The README Rankine cycle (the FB-06 recipe) solved in a project."""
    project = tmp_path_factory.mktemp("st-cli-project") / "project"
    with LocalApplication.create(project, project_id="st-cli") as app:
        change, parent, key = Change.from_change_set(
            json.loads(RANKINE.read_text(encoding="utf-8"))
        )
        committed = app.commit_change(change, parent, key)
        assert committed.revision_id is not None
        result = app.solve(committed.revision_id, "default")
        assert result.outcome == "CONVERGED"
    return Solved(project, result.job_id)


def streams(*argv: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = cli.main(["streams", *argv])
    out, err = capsys.readouterr()
    return code, out, err


def _golden(form: str) -> str:
    """The golden of `form` as the CLI prints it. The CSV file is kept with LF line ends
    (`.gitattributes`: `*.csv text eol=lf`), and the CLI writes RFC 4180's CRLF. The JSON golden
    takes this package's version in `evaluator.package_version`, the one member that moves with a
    release rather than with the run."""
    text = (GOLDEN / FORMATS[form]).read_text(encoding="utf-8")
    if form == "csv":
        return text.replace("\n", "\r\n")
    if form == "json":
        document = json.loads(text)
        document["evaluator"]["package_version"] = __version__
        return canonical_json(document).decode("utf-8") + "\n"
    return text


# ==================================================================================== goldens


@pytest.mark.parametrize("form", sorted(FORMATS))
def test_th_c1_golden(form: str, bundle: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = streams(str(bundle), "--format", form, capsys=capsys)
    assert (code, err) == (0, "")
    golden = _golden(form)
    assert out == golden


def test_the_json_form_is_the_documents_canonical_json(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = streams(str(bundle), "--format", "json", capsys=capsys)
    assert code == 0
    assert out == canonical_json(stream_table.from_bundle(bundle)).decode("utf-8") + "\n"


def test_the_csv_form_has_one_row_per_total_and_phase(
    bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = streams(str(bundle), "--format", "csv", capsys=capsys)
    assert code == 0 and out.endswith("\r\n")
    document = stream_table.from_bundle(bundle)
    rows = list(csv.DictReader(io.StringIO(out, newline="")))
    header = out.split("\r\n", 1)[0].split(",")
    assert header == [*stream_table_format.CSV_COLUMNS, "n_H2O_mol_s", "x_H2O"]
    expected = sum(1 + len(s["substreams"][0]["phases"]) for s in document["streams"])
    assert len(rows) == expected
    for stream in document["streams"]:
        mine = [row for row in rows if row["stream"] == stream["id"]]
        total, phases = mine[0], mine[1:]
        assert total["phase_family"] == total["phase_fraction_molar"] == ""
        substream = stream["substreams"][0]
        assert total["H_flow_W"] == repr(substream["H_flow"])
        for row, phase in zip(phases, substream["phases"], strict=True):
            assert row["phase_family"] == phase["id"]["family"]
            assert row["vapor_fraction_molar"] == row["vapor_fraction_mass"] == ""
            assert (row["T_K"], row["P_Pa"]) == (total["T_K"], total["P_Pa"])
            assert row["H_flow_W"] == repr(phase["H_flow"])


def test_the_text_form_marks_absent_values_with_footnotes() -> None:
    """A dormant stream's `T` is `-` with a footnote naming `zero_flow`; a status other than
    `VERIFIED` puts the warning first."""
    document = json.loads((GOLDEN / "TH-C1.json").read_text(encoding="utf-8"))
    stream = document["streams"][0]
    stream["T"] = None
    stream["absent"] = {"T": {"code": "zero_flow", "params": {"stream": stream["id"]}}}
    document["verification_status"] = "UNVERIFIED"
    text = stream_table_format.to_text(document)
    lines = text.splitlines()
    assert lines[0] == "WARNING: verification_status is UNVERIFIED"
    (row,) = [line for line in lines if line.startswith("T [K]")]
    assert row.split()[2] == "-*1"
    assert lines[-1] == f"*1 zero_flow(stream={stream['id']})"


# ====================================================================== the two modes and paging


def test_project_and_directory_modes_give_one_document(
    solved: Solved, capsys: pytest.CaptureFixture[str]
) -> None:
    project = ["--project", str(solved.project), "--job", solved.job_id]
    code, by_job, err = streams(*project, "--format", "json", capsys=capsys)
    assert (code, err) == (0, "")
    code, by_directory, _ = streams(str(solved.bundle), "--format", "json", capsys=capsys)
    assert code == 0
    document, directory = json.loads(by_job), json.loads(by_directory)
    assert document["source"]["job_id"] == solved.job_id
    assert document["source"]["bundle_id"] == f"{solved.job_id}:bundle"
    assert directory["source"]["job_id"] is directory["source"]["bundle_id"] is None
    directory["source"] = document["source"]
    assert directory == document
    # The forms of the parsed JSON (integral floats read back as ints) are the CLI's own.
    with LocalApplication.open(solved.project) as app:
        operation = app.get_stream_table(solved.job_id)
    assert not operation.truncated
    assert by_job == canonical_json(operation.value).decode("utf-8") + "\n"
    forms = {"text": stream_table_format.to_text, "csv": stream_table_format.to_csv}
    for form, render in forms.items():
        code, by_job_form, _ = streams(*project, "--format", form, capsys=capsys)
        assert code == 0
        assert by_job_form == render(document)


def test_the_paged_assembly_at_limit_1_is_the_whole_document(solved: Solved) -> None:
    """Depth 1 elides every member of the root, and `limit=1` pages each array one item at a
    time: the assembly reads many views and rebuilds the operation's document exactly."""
    with LocalApplication.open(solved.project) as app:
        whole = app.get_stream_table(solved.job_id).value
        views: list[str] = []

        def fetch(pointer: str, depth: int, cursor: str | None, limit: int) -> Any:
            views.append(pointer)
            request: dict[str, Any] = {
                "job_id": solved.job_id,
                "pointer": pointer,
                "depth": depth,
                "limit": limit,
            }
            if cursor is not None:
                request["cursor"] = cursor
            return dispatch(app, "get_stream_table", request)

        assembled = stream_table_format.assemble(fetch, depth=1, limit=1)
    assert assembled == whole
    assert views.count("/streams") == len(whole["streams"])


def test_a_view_of_another_document_is_refused(solved: Solved) -> None:
    """Every view must carry the first one's `sha256`."""
    with LocalApplication.open(solved.project) as app:
        calls = 0

        def fetch(pointer: str, depth: int, cursor: str | None, limit: int) -> Any:
            nonlocal calls
            calls += 1
            request = {"job_id": solved.job_id, "pointer": pointer, "depth": depth}
            view = dict(dispatch(app, "get_stream_table", request))
            if calls > 1:
                view["sha256"] = "0" * 64
            return view

        from openflowsheet.application.contract import ApplicationError

        with pytest.raises(ApplicationError) as refused:
            stream_table_format.assemble(fetch, depth=1)
    assert refused.value.code == "internal_error"


def test_output_writes_the_file_and_prints_nothing(
    bundle: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "table.csv"
    code, out, err = streams(str(bundle), "--format", "csv", "--output", str(target), capsys=capsys)
    assert (code, out, err) == (0, "", "")
    assert target.read_bytes() == _golden("csv").encode("utf-8")


# ==================================================================================== exit codes


def _exit(code: str) -> int:
    return cli.API_EXIT_CODES[code]


@pytest.mark.parametrize(
    ("label", "argv", "expected"),
    [
        ("both modes", lambda b, s: [str(b), "--project", str(s.project), "--job", "j"], 2),
        ("no mode", lambda b, s: [], 2),
        ("project without job", lambda b, s: ["--project", str(s.project)], 2),
        ("no project", lambda b, s: ["--project", str(b / "nowhere"), "--job", "j"], 1),
        ("unknown job", lambda b, s: ["--project", str(s.project), "--job", "job-999999"], 6),
        ("no bundle", lambda b, s: [str(b / "nowhere")], 6),
    ],
)
def test_exit_codes(
    label: str,
    argv: Callable[[Path, Solved], list[str]],
    expected: int,
    bundle: Path,
    solved: Solved,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out, err = streams(*argv(bundle, solved), capsys=capsys)
    assert code == expected, (label, err)
    assert out == ""  # text form: a refusal's document goes to stdout only with --format json
    assert err


def test_a_refusal_with_json_prints_the_error_document(
    tmp_path: Path, bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bundle directory without a solution state: `not_found` (exit 6) naming the member; with
    `--format json` the projected `ApiError` is on stdout."""
    directory = tmp_path / "bundle"
    shutil.copytree(bundle, directory)
    (directory / ARTIFACT_DIR / "solution-state.json").unlink()
    code, out, err = streams(str(directory), "--format", "json", capsys=capsys)
    assert code == _exit("not_found") == 6
    document = json.loads(out)
    assert document["code"] == "not_found"
    assert document["detail"]["member"] == "solution-state.json"
    assert "solution-state.json" in err


@pytest.mark.skipif(
    __import__("importlib.util").util.find_spec("CoolProp") is not None,
    reason="the coolprop extra is installed; TH-C2 is served",
)
def test_an_unavailable_basis_exits_unsupported(
    tmp_path: Path, bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "bundle"
    shutil.copytree(bundle, directory)
    revision = directory / ARTIFACT_DIR / "revision.json"
    revision.write_text(TH_C2.read_text(encoding="utf-8"), encoding="utf-8")
    code, _, err = streams(str(directory), capsys=capsys)
    assert code == _exit("unsupported")
    assert "basis_unavailable(coolprop-heos-v1)" in err
