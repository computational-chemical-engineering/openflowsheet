# Brief — pre-public audit of the repository (report only)

**To:** `sonnet-implementer`. **From:** the session, 2026-10-02. **Repository:** this checkout (all branches and the full
history reachable from `origin`'s refs). Frank intends to make the GitHub repository
`computational-chemical-engineering/openflowsheet` public. Publishing exposes the **entire git history**, not only the
current tree. Your job: find what should not be public, and report. **Change nothing** — no edits, no commits, no
history rewriting, no network writes. Write only the report `docs/pre-public-audit.md` and do not commit it.

## Check (whole history: `git log --all -p`, `git rev-list --all --objects`)

1. **Secrets.** If `gitleaks` or `trufflehog` is installed, run it over the history and report the command and output
   summary. Otherwise grep the full history for: Anthropic keys/tokens (`sk-ant-`), `CLAUDE_CODE_OAUTH_TOKEN=` with a
   value, GitHub tokens (`ghp_`, `gho_`, `github_pat_`), AWS keys (`AKIA`), private keys (`-----BEGIN`), `password`,
   `.env` files, and anything that looks like the contents of `~/.config/procsim/v17-token`. **Never print a secret
   value in the report** — give commit, path and the first 4 characters only.
2. **Personal data.** E-mail addresses (list distinct addresses and where; the V17 campaign `v17-c1` transcripts held
   the operator's account address before redaction commit `15d7c2f` — confirm whether the pre-redaction blobs are still
   reachable), real names other than Frank Peters' authorship, local paths revealing usernames/home layout, IP
   addresses, hostnames.
3. **Third-party data and code** tracked anywhere in history: reference-tool outputs (`benchmarks/t06/references/`,
   IDAES/DWSIM files), anything from OpenIDAES-450, papers/PDFs, datasets (CSV/XLSX), vendored code, CasADi bytes (ADR
   0006 D5.5 forbids tracking them — confirm none were ever committed). For each: path, size, origin as far as the
   repository says (ADR 0006, `docs/v02-real-chemistry-dossier.md`, `benchmarks/**/README*`, licences), and whether its
   redistribution right is recorded.
4. **Large files.** Every blob > 1 MB in history (path, size, commit), and the repository's total packed size
   (`git count-objects -vH`).
5. **Internal material** a reader might not expect in a public repo: agent transcripts (`benchmarks/t07/v17/runs/**`),
   "Notes for Frank", session briefs (`docs/briefs/`), decision logs, scratch paths — list categories and sizes, no
   judgement on whether to keep them (that is Frank's).

## Report

`docs/pre-public-audit.md`: a short summary (blocking findings first), then one section per check with the evidence
(commands run, counts, paths, commits). End with the options for Frank: publish history as is / rewrite specific blobs
(`git filter-repo`) / squash to a single public root commit with the full history kept internally — and which findings
each option resolves. Budget: Frank is near a weekly usage limit — use scripted greps; do not read large files whole.
