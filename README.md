# DevTools

Shared dev tooling for AndreiCostinescu's repos, so formatting/lint rules and
CI checks are defined once instead of copy-pasted per repo.

## What's here

- `hooks/` + `.pre-commit-hooks.yaml` — a [pre-commit](https://pre-commit.com)
  hook repo: license-header check (C/C++ and Python variants), clang-format,
  clang-tidy, DCO sign-off. Ruff itself isn't wrapped here — a Python
  consumer adds `astral-sh/ruff-pre-commit` as its own separate `repo:` entry.
- `config/` — canonical `.clang-format` / `.clang-tidy` (and, once a Python
  repo is wired up, `ruff.toml`).
- `setup.mk` — the actual `setup`/`format`/`lint`/`sync-devtools`/`help`
  implementation, parameterized by a mandatory `LANGS` list (`cpp`,
  `python`, or both). A consuming repo's own `Makefile` is just a tiny
  stub that bootstraps the submodule and forwards every target here — see
  below.
- `scripts/` — `sync-config` (copies `config/` files into a consuming repo,
  refusing to clobber local edits), `ensure-gitignore` (idempotently adds
  gitignore entries), `detect-languages` (advisory-only guess at which
  `LANGS` a repo needs, shown in `make help`/on a missing-`LANGS` error).
- `.github/actions/` — `check-clang-format` and `run-clang-tidy` composite
  actions for CI, wrapping the one command each that's identical everywhere.

## Using it in a repo

1. `git submodule add https://github.com/AndreiCostinescu/DevTools.git .devtools`
2. Point `.pre-commit-config.yaml` at this repo (`repo: https://github.com/AndreiCostinescu/DevTools`, pinned `rev:`), listing the hook ids you need (`license-header-check-cpp`/`-python`, `clang-format`, `clang-tidy`, `dco-check`).
3. Give the repo this `Makefile` (identical in every consumer — all real logic lives in `setup.mk`):
   ```makefile
   .PHONY: setup format lint sync-devtools help

   setup format lint sync-devtools help:
   	@[ -f .devtools/setup.mk ] || git submodule update --init --recursive
   	@$(MAKE) --no-print-directory -f .devtools/setup.mk $@ LANGS="$(LANGS)"
   ```
4. Run `make setup LANGS="cpp"` (or `"python"`, or `"cpp python"`) — `LANGS` is required, with no default; `make help` shows a detected suggestion.
5. In CI, reference the composite actions as
   `AndreiCostinescu/DevTools/.github/actions/<name>@<rev>`.

See PerceptionData, AndreiUtils, or RecordingLib for a working example of
all of the above wired up (all three currently pass `LANGS=cpp`).

When this repo changes, bump the pinned `rev`/submodule commit in each
consuming repo to pick it up — nothing here is pulled automatically.

## Planned

Wire up an actual Python consumer (ConceptHierarchy): extract `ruff.toml`
into `config/`, and add a `check-ruff` composite action for CI.
