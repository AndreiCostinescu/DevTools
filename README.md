# DevTools

Shared dev tooling for AndreiCostinescu's repos, so formatting/lint rules and
CI checks are defined once instead of copy-pasted per repo.

## What's here

- `hooks/` + `.pre-commit-hooks.yaml` — a [pre-commit](https://pre-commit.com)
  hook repo: license-header check, clang-format, clang-tidy, DCO sign-off.
- `config/` — canonical `.clang-format` / `.clang-tidy`.
- `common.mk` — shared `format`/`lint` Make targets.
- `scripts/` — `sync-config` (copies `config/` files into a consuming repo,
  refusing to clobber local edits) and `ensure-gitignore` (idempotently adds
  gitignore entries). Both used by consuming repos' `make setup`.
- `.github/actions/` — `check-clang-format` and `run-clang-tidy` composite
  actions for CI, wrapping the one command each that's identical everywhere.

## Using it in a repo

1. `git submodule add https://github.com/AndreiCostinescu/DevTools.git .devtools`
2. Point `.pre-commit-config.yaml` at this repo (`repo: https://github.com/AndreiCostinescu/DevTools`, pinned `rev:`).
3. Add a `setup` target to the repo's `Makefile` that runs
   `git submodule update --init --recursive`, installs pre-commit, and calls
   `.devtools/scripts/sync-config` / `ensure-gitignore`; `-include .devtools/common.mk`
   for `format`/`lint`.
4. In CI, reference the composite actions as
   `AndreiCostinescu/DevTools/.github/actions/<name>@<rev>`.

See PerceptionData, AndreiUtils, or RecordingLib for a working example of
all of the above wired up.

When this repo changes, bump the pinned `rev`/submodule commit in each
consuming repo to pick it up — nothing here is pulled automatically.

## Planned

Python tooling (ruff, etc.) alongside the existing C/C++ setup.
