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
  `license-headers`/`help`/`detect-languages` implementation, taking the
  language(s) to act on as trailing positional args (`cpp`, `python`, or
  both — `setup`/`format`/`lint`/`sync-devtools`/`license-headers` require
  at least one). Stdlib-only Python (3.5+, no pip installs needed to run
  it). (The pre-commit hooks in `hooks/` stay `sh` — those only ever run
  through Git's own hook mechanism, which always has a POSIX shell
  available even on Windows, so there's no reason to change them.)
- `dev.py` (shown under "Using it in a repo" below) — the one tiny script
  each consumer copies into its own repo root, identical everywhere. Its
  only job is bootstrapping: run `git submodule update --init --recursive`
  so `scripts/devtools.py` actually exists on a fresh clone (before that,
  nothing under `.devtools/` is there to invoke), then exec straight into
  it with the same argv. Python, not Make: Make isn't preinstalled on
  Windows, and Python is already a hard requirement for
  `scripts/devtools.py` itself, so there's no reason to impose a second
  tool just to get from a fresh clone to that script running.
- `.github/actions/` — `check-clang-format`, `run-clang-tidy`, and
  `check-ruff` composite actions for CI, wrapping the one command each
  that's identical everywhere.

## Using it in a repo

1. `git submodule add https://github.com/AndreiCostinescu/DevTools.git .devtools`
2. Point `.pre-commit-config.yaml` at this repo (`repo: https://github.com/AndreiCostinescu/DevTools`, pinned `rev:`), listing the hook ids you need (`license-header-check-cpp`/`-python`, `clang-format`, `clang-tidy`, `dco-check`).
3. Give the repo this `dev.py` (identical in every consumer — all real logic lives in `scripts/devtools.py`):
   ```python
   #!/usr/bin/env python3
   # dev.py
   import subprocess
   import sys

   subprocess.check_call(["git", "submodule", "update", "--init", "--recursive"])
   sys.exit(subprocess.call([sys.executable, ".devtools/scripts/devtools.py"] + sys.argv[1:]))
   ```
4. Run `python dev.py setup cpp` (or `python dev.py setup python`, or `python dev.py setup cpp python`) — at least one language is required for `setup`/`format`/`lint`/`sync-devtools`/`license-headers`. Not sure what to pass? `python dev.py detect-languages` prints a suggestion based on what's in the repo — `python dev.py help` shows the same suggestion alongside the usage summary.
5. In CI, reference the composite actions as
   `AndreiCostinescu/DevTools/.github/actions/<action_name>@<repo_rev>`.

When this repo changes, bump the pinned `rev`/submodule commit in each
consuming repo to pick it up — nothing here is pulled automatically.

## Repos Currently Using `DevTools`:

- [AndreiUtils](https://github.com/AndreiCostinescu/AndreiUtils) (cpp)
- [ConceptLibrary](https://github.com/AndreiCostinescu/ConceptLibrary) (python)
- [RecordingLib](https://github.com/AndreiCostinescu/RecordingLib) (cpp)
- [PerceptionData](https://github.com/AndreiCostinescu/PerceptionData) (cpp)
