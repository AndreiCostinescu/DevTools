# DevTools

Shared dev tooling for AndreiCostinescu's repos, so formatting/lint rules and
CI checks are defined once instead of copy-pasted per repo.

## What's here

- `hooks/` + `.pre-commit-hooks.yaml` — a [pre-commit](https://pre-commit.com)
  hook repo: license-header check (C/C++ and Python variants), clang-format,
  clang-tidy, DCO sign-off. Ruff itself isn't wrapped here — a Python
  consumer adds `astral-sh/ruff-pre-commit` as its own separate `repo:` entry.
- `config/` — canonical `.clang-format` / `.clang-tidy` / `ruff.toml`.
- `scripts/devtools.py` — the actual `setup`/`format`/`lint`/`sync-devtools`/
  `help` implementation, parameterized by a mandatory `--langs` list (`cpp`,
  `python`, or both). Stdlib-only Python (3.5+, no pip installs needed to
  run it), deliberately **not** a `sh`/Make-recipe script: a consuming
  repo's Makefile only runs plain commands (`git submodule update`, then
  `python .devtools/scripts/devtools.py ...`), so it works identically
  whichever shell Make executes recipes with — cmd.exe, PowerShell, or sh.
  (The pre-commit hooks in `hooks/` stay `sh` — those only ever run through
  Git's own hook mechanism, which always has a POSIX shell available even
  on Windows, so there's no reason to change them.)
- `.github/actions/` — `check-clang-format`, `run-clang-tidy`, and
  `check-ruff` composite actions for CI, wrapping the one command each
  that's identical everywhere.

## Using it in a repo

1. `git submodule add https://github.com/AndreiCostinescu/DevTools.git .devtools`
2. Point `.pre-commit-config.yaml` at this repo (`repo: https://github.com/AndreiCostinescu/DevTools`, pinned `rev:`), listing the hook ids you need (`license-header-check-cpp`/`-python`, `clang-format`, `clang-tidy`, `dco-check`).
3. Give the repo this `Makefile` (identical in every consumer — all real logic lives in `scripts/devtools.py`):
   ```makefile
   .PHONY: setup format lint sync-devtools help

   setup format lint sync-devtools help:
   	git submodule update --init --recursive
   	python .devtools/scripts/devtools.py $@ --langs $(LANGS)
   ```
4. Run `make setup LANGS="cpp"` (or `"python"`, or `"cpp python"`) — `LANGS` is required, with no default; `make help` shows a detected suggestion.
5. In CI, reference the composite actions as
   `AndreiCostinescu/DevTools/.github/actions/<name>@<rev>`.

See PerceptionData, AndreiUtils, or RecordingLib for a working example of
all of the above wired up (all three currently pass `LANGS=cpp`).

When this repo changes, bump the pinned `rev`/submodule commit in each
consuming repo to pick it up — nothing here is pulled automatically.

## Planned

Migrate ConceptHierarchy itself onto this repo: add it as the `.devtools`
submodule, replace its hand-rolled `.githooks/` + `.pre-commit-config.yaml`
+ `Makefile` with the shared ones (adding `astral-sh/ruff-pre-commit` as
its own `repo:` entry per above), and swap its `ci.yml`/`lint.yml` steps
for the `check-ruff` composite action.
