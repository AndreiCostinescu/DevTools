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
- [`dev.py`](dev.py) (see "Using it in a repo" below) — the one tiny script
  each consumer copies into its own repo root, identical everywhere except
  for its pinned `DEVTOOLS_REV`. Its only job is bootstrapping: download a
  pinned snapshot of this repo into `.devtools/` (no git submodule — a
  plain, gitignored download cache, refetched only when `DEVTOOLS_REV`
  changes or `.devtools/` is missing) so `scripts/devtools.py` actually
  exists on a fresh clone, then exec straight into it with the same argv.
  Python, not Make: Make isn't preinstalled on Windows, and Python is
  already a hard requirement for `scripts/devtools.py` itself, so there's
  no reason to impose a second tool just to get from a fresh clone to that
  script running.
- `.github/actions/` — `check-clang-format`, `run-clang-tidy`, and
  `check-ruff` composite actions for CI, wrapping the one command each
  that's identical everywhere.

## Using it in a repo

The steps are the same whether you're wiring this into an existing repo or
bootstrapping a brand-new one — a new repo just needs `git init` and its
initial project metadata (`pyproject.toml` for Python, `CMakeLists.txt` for
C++) in place before step 5, since `setup` relies on both for `python` and
`detect-languages` looks for both.

No git submodule is involved — `dev.py` downloads a pinned snapshot of this
repo into `.devtools/` itself, so cloning the consumer repo needs nothing
beyond a normal `git clone`.

1. Point `.pre-commit-config.yaml` at this repo (`repo: https://github.com/AndreiCostinescu/DevTools`, pinned `rev:`), listing the hook ids you need (`license-header-check-cpp`/`-python`, `clang-format`, `clang-tidy`, `dco-check`).
2. Copy this repo's [`dev.py`](dev.py) into the consumer repo root, unmodified
   except for its `DEVTOOLS_REV` — fill that in with a pinned commit SHA (or
   tag, once this repo has any) before running it; `"latest"` is also
   accepted, always tracking the current tip of `main`, but is unpinned by
   design so prefer a real SHA/tag anywhere reproducibility matters (e.g.
   CI). `dev.py` validates whatever you set against GitHub before
   attempting the download, so a bad/unfilled `DEVTOOLS_REV` fails with a
   clear message rather than a confusing 404. All real logic lives in
   `scripts/devtools.py`; `dev.py` is only the bootstrap that fetches it.
3. **Python repos only:** give `pyproject.toml` a `dev` optional-dependency
   group that includes at least `ruff` and `pre-commit`, e.g.:
   ```toml
   [project.optional-dependencies]
   dev = ["ruff", "pre-commit"]
   ```
   This is the one manual, one-time step — `devtools.py` won't edit
   `pyproject.toml` for you, since (unlike the config files it syncs below)
   its contents are project-specific. Once the `dev` extra exists, `setup`
   installs from it automatically every time — see step 4.
4. Run `python dev.py setup cpp` (or `python dev.py setup python`, or `python dev.py setup cpp python`) — at least one language is required for `setup`/`format`/`lint`/`sync-devtools`/`license-headers`. Not sure what to pass? `python dev.py detect-languages` prints a suggestion based on what's in the repo — `python dev.py help` shows the same suggestion alongside the usage summary.

   Before `setup` even starts, `dev.py` has already downloaded `.devtools/`
   (see step 2). `setup` itself does the rest: clears any conflicting
   `core.hooksPath`, runs `pip install -e ".[dev]"` (or just
   `pip install pre-commit` if you only passed `cpp`), runs `pre-commit
   install` for the `pre-commit` and `commit-msg` stages, and syncs the
   canonical config files (`.clang-format`/`.clang-tidy`/`ruff.toml` for the
   languages you passed) from `.devtools/config/` into the repo root. That
   sync is tracked via a `.devtools-sync.sha256` state file, so a later
   `sync-devtools` run detects local edits to a synced file and warns
   instead of overwriting them.
5. In CI, reference the composite actions as
   `AndreiCostinescu/DevTools/.github/actions/<action_name>@<repo_rev>`.
6. Commit the result: `dev.py`, `.pre-commit-config.yaml`, the newly-synced
   config files, and the `.gitignore` entries `setup`/`sync-devtools` add
   (`.devtools/` itself, plus the state file's temp write). `.devtools/` is
   never committed — it's rebuilt from `dev.py`'s `DEVTOOLS_REV` on demand.

When this repo changes, bump `DEVTOOLS_REV` in each consuming repo's
`dev.py` (and the pinned `rev:` in its `.pre-commit-config.yaml`, if that
hook set also changed) to pick it up — nothing here is pulled automatically.

## Repos Currently Using `DevTools`:

- [AndreiUtils](https://github.com/AndreiCostinescu/AndreiUtils) (cpp)
- [ConceptLibrary](https://github.com/AndreiCostinescu/ConceptLibrary) (python)
- [RecordingLib](https://github.com/AndreiCostinescu/RecordingLib) (cpp)
- [PerceptionData](https://github.com/AndreiCostinescu/PerceptionData) (cpp)
