# DOC brief: a user documentation site on GitHub Pages (build lane, one engineer)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/doc`, branch `wp/DOC` from `main` `6c382a90`. Manifest id
**S14** (alias of DOC, the R-565 precedent: the evidence schema allows only `^[PKTMSR][0-9]{2}[a-z]?$`).

## The request
Frank, 2026-10-29: "It would also be nice to have some quality documentation. Can you create Github pages, and publish
these. It should contain installation instructions, some examples, the API reference etc."
The site documents what `main` will release as **0.3.0** (S01–S11, E01: columns, water/IAPWS-95, CoolProp pure fluids,
Wilson γ–φ, `thermal.*` units, the column as a flowsheet unit, cost and LCA, studies/NLP optimisation). Repository public:
`computational-chemical-engineering/openflowsheet`; the site will be at
`https://computational-chemical-engineering.github.io/openflowsheet/`.

## Decided (orchestrator; logged as DECISION lines)
- **MkDocs + Material theme + mkdocstrings (Python handler)**. Alternative: Sphinx + autodoc. Source in `docs-site/`
  (the existing `docs/` holds internal design records and is **not** published wholesale); `mkdocs.yml` at the root; build
  output `site/` (git-ignored).
- Deployment: a new workflow `.github/workflows/site.yml` — build with `mkdocs build --strict` on every push and PR; deploy
  with `actions/configure-pages`, `actions/upload-pages-artifact`, `actions/deploy-pages` on pushes to `main` only. Pin every
  action by full commit SHA, exactly as `ci.yml` does (a test checks the workflows' pins — find it and keep it green, extend
  it to `site.yml` if it enumerates files). Docs tooling pinned with hashes in `requirements-docs.txt` (not a package
  extra; it never ships in the wheel). If the licence/binary inventory checks cover workflow or lock files, satisfy them.
- **You do not enable Pages and do not push.** The orchestrator enables Pages (`build_type=workflow`) after the merge.

## Uniformity with Frank's other repositories (Frank, 2026-10-29: "try to get some uniformity")
Follow **Peclet**'s site (`/home/frankp/Codes/suite`: `mkdocs.yml`, `.github/workflows/site.yml`, `requirements-docs.txt`,
`docs/privacy.md`, `tools/gen_python_api.py`; read them, copy what fits):
- the same theme block: Material, `primary/accent: indigo`, the light/dark toggle (`material/weather-night` /
  `material/weather-sunny`), features `navigation.sections`, `navigation.top`, `content.code.copy`, `toc.integrate`; the
  same `markdown_extensions` (admonition, tables, toc permalink, pymdownx.highlight/superfences/details); `site_url` set
  (an empty sitemap otherwise), `repo_url`, `repo_name`; footer `extra.social` icons (GitHub, PyPI);
- the same file names: workflow **`.github/workflows/site.yml`** (job names `build`/`deploy`, `concurrency: pages`,
  `mkdocs build --strict --site-dir site`, upload-pages-artifact, deploy-pages, environment `github-pages`) and
  **`requirements-docs.txt`** (here with exact pins and hashes, as this repository pins everything; the docs tooling
  never ships in the wheel); build output `site/` (git-ignored);
- the same nav shape where it applies: Home · Examples · Install & run · Python API (one page per public module) · Design
  (here: links to the ADRs and decision register on GitHub) · Releasing (`docs/RELEASING.md`) · Privacy (a short page
  like Peclet's website section: static pages, no cookies, no analytics, GitHub's logs);
- Peclet's rule: keep version numbers out of the pages (the PyPI badge and the CHANGELOG carry them).
Differences, deliberate: OpenFlowsheet is pure Python, so the API pages use **mkdocstrings** at build time instead of
Peclet's container-run generator; examples live in this site rather than in a separate gallery site (Peclet's is Quarto, `peclet-examples`).
**PyMRM** (hub report, 2026-10-29: the PyMRM book is Jupyter Book 2/MyST, `deploy.yml`; API by sphinx-autodoc2; **NumPy
docstrings**; examples/tutorials are **Jupyter notebooks executed in CI** before the build; sections Getting Started, Coding
Agents, Tutorials, Examples). Take from PyMRM:
- **NumPy docstring style** for the public API: configure mkdocstrings `docstring_style: numpy`; where you add or extend a
  public docstring, write NumPy sections (Parameters/Returns/Raises). Do not rewrite every existing prose docstring; do it
  for the objects the quickstart and examples use.
- **Examples as Jupyter notebooks** in `examples/*.ipynb` (outputs not committed), rendered with `mkdocs-jupyter`
  (`execute: true`, so CI executes them at build), **and** executed by a pytest test (nbclient) that asserts their key
  numbers against the values stated in the page. Notebooks needing an absent optional extra print a stated skip.
- **Section names**: Home · Getting Started (install, quickstart) · Tutorials · Examples · Coding Agents (CLI/MCP/HTTP for
  agents, and how to ask a coding agent to work with OpenFlowsheet) · User guide · Python API · Design · Releasing ·
  Privacy.

## Content (truthful; the project's scientific conduct applies to documentation)
1. **Home**: what OpenFlowsheet is (an agent-native, open, equation-oriented process simulator with evidence: certificates,
   verification vs empirical validation distinguished), status (0.2.0 released; 0.3.0 contents), links.
2. **Installation**: `pip install openflowsheet` (Python ≥ 3.13), each optional extra (`coolprop`, `lca`, `nlp`, `server`,
   …: read `pyproject.toml`) and what it enables and its licence note; from source; verifying the install.
3. **Quickstart**: one flowsheet solved from Python and the same from the CLI (`openflowsheet …`), reading the result and its
   certificate.
4. **User guide**: concepts (flowsheet, streams, property bases and how to select one, units, solve, the verifier and
   certificates, refusals as typed results); property bases (SYN-001, water IAPWS-95, CoolProp, Wilson; what each supports
   and refuses); unit catalogue — **generated** from the model registry (`MODEL_BUILDERS`/`MODEL_SIGNATURES`/`MODEL_BASES`) by
   a script under `scripts/` with a `--check` mode tested in the suite, so it cannot drift; distillation column; studies,
   sensitivities and optimisation (the `nlp` extra); cost estimation and LCA (accuracy class, uncertainty, data rights, the
   `lca` extra); interfaces for agents (CLI, Python, HTTP, MCP).
5. **Examples**: 4–6 runnable notebooks in `examples/` using only the public application contract (`examples/README.md` rule),
   e.g. a water Rankine cycle, a CoolProp refrigeration loop, a Wilson distillation column, a cost/LCA assessment, a small
   optimisation (skip gracefully with a stated message when an optional extra is absent). Each is rendered in the site with
   its output, and **each is executed by a test** that checks its key numbers against values stated in the page (so the
   docs fail loudly when the code changes). An example is a demonstration, never gate evidence.
6. **API reference**: mkdocstrings pages for the public Python surface (find it: `openflowsheet/__init__.py`, the
   application layer, `docs/interfaces-frozen.md`); do not document private modules; fix docstrings only where a public
   object lacks one, without changing behaviour.
7. **Limitations / support matrix** (from `docs/support-matrix.md` and the envelope; what is not supported, stated plainly),
   **changelog** (include `CHANGELOG.md`), **licence and attributions** (`LICENSE`, `NOTICE`: IAPWS, IDAES BSD, data
   sources), **design records**: links to ADRs and the decision register on GitHub, not rendered.

## Verification
`mkdocs build --strict` clean (no warnings, no broken links); the example tests and the catalogue `--check` pass; the tests
you touch pass; `scripts/s11_identity.py` → `S11-IDENTITY PASS` at the end (docstring-only edits must not move anything).
Not the full gate (the orchestrator runs it once). Then write `evidence/S14/<commit>/manifest.json` with `status: tested`
in the pattern of a recent build-lane manifest (e.g. `scripts/s11_evidence_manifest.py`'s output; never angle-bracket values).

## Rules
- Pytest with a private temp dir: `TMPDIR=/home/frankp/.cache/doc-tmp PYTEST_ADDOPTS="--basetemp=/home/frankp/.cache/doc-tmp/pt"`,
  `PYTHONPATH=$PWD/src:$PWD`, `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python`; install docs tooling into a separate venv
  under `/home/frankp/.cache/doc-venv`. Never `/tmp` directly.
- DECISION lines for open choices in `docs/DOC_DECISIONS.md`, each an isolated commit. Stage named paths; commit messages
  name DOC. Do not push. Do not start subagents. Do not send names, e-mail addresses or other personal identifiers to any
  external service (pip/PyPI downloads are fine). Do not put any e-mail address on the site.
- Context cap ~150k: commit, write a ≤40-line handoff at the end of `docs/DOC_DECISIONS.md`, end.
- Report in at most 20 lines: pages built, examples and their tests, build result, what is left.
