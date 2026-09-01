#!/usr/bin/env python3
"""
scripts/devtools.py

Cross-platform implementation of setup/sync-devtools/detect-languages/format/
lint/license-headers/help for a repo consuming DevTools. Stdlib only (no pip
installs needed to run this script itself) and written to run on Python 3.5+.

Invoked from a consuming repo's own tiny `dev.py` bootstrap (identical in
every consumer - see README) as:
    python dev.py <command> [<lang> ...]

dev.py's only job is to download a pinned snapshot of DevTools into
.devtools/ (so this script actually exists on a fresh clone - no git
submodule involved) and then exec straight into this script with the same
argv - no extra tool to install beyond the Python you already need to run
it.
"""

import argparse
import datetime
import hashlib
import io
import os
import shutil
import subprocess
import sys
from difflib import unified_diff

KNOWN_LANGS = ("cpp", "python")
CPP_HEADER_AND_SOURCE_EXTENSIONS = (".h", ".hpp", ".hh", ".hxx", ".c", ".cc", ".cpp", ".cxx")
CPP_SOURCE_EXTENSIONS = (".c", ".cc", ".cpp", ".cxx")
STATE_FILE = ".devtools-sync.sha256"

# Conservative cap on a single command line. cmd.exe truncates at 8191
# characters, and on Windows a tool installed as a .cmd/.bat shim is executed
# through cmd.exe, so batches are sized against that limit on every platform.
MAX_COMMAND_LINE = 7000

LICENSE_MARKER = "Licensed under the Apache License, Version 2.0"

PYTHON_HEADER_LINES = (
    '# Copyright {year} {repo_name}',
    '#',
    '# Licensed under the Apache License, Version 2.0 (the "License");',
    '# you may not use this file except in compliance with the License.',
    '# You may obtain a copy of the License at',
    '#',
    '#     http://www.apache.org/licenses/LICENSE-2.0',
    '#',
    '# Unless required by applicable law or agreed to in writing, software',
    '# distributed under the License is distributed on an "AS IS" BASIS,',
    '# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.',
    '# See the License for the specific language governing permissions and',
    '# limitations under the License.',
)

CPP_HEADER_LINES = (
    '/*',
    ' * Copyright {year} {repo_name}',
    ' *',
    ' * Licensed under the Apache License, Version 2.0 (the "License");',
    ' * you may not use this file except in compliance with the License.',
    ' * You may obtain a copy of the License at',
    ' *',
    ' *     http://www.apache.org/licenses/LICENSE-2.0',
    ' *',
    ' * Unless required by applicable law or agreed to in writing, software',
    ' * distributed under the License is distributed on an "AS IS" BASIS,',
    ' * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.',
    ' * See the License for the specific language governing permissions and',
    ' * limitations under the License.',
    ' */',
)


class ToolError(Exception):
    """A required external tool is missing or a git invocation failed."""


def fail(message):
    sys.stderr.write("ERROR: {}\n".format(message))
    sys.exit(1)


def resolve(tool):
    """Locate an executable on PATH.

    Necessary on Windows: CreateProcess appends only '.exe', so a tool
    installed as 'ruff.cmd' or 'pre-commit.bat' is invisible to subprocess
    unless the full name is resolved first. shutil.which honours PATHEXT.
    """
    path = shutil.which(tool)
    if path is None:
        raise ToolError(
            "'{}' not found on PATH. Run 'python dev.py setup <lang> [<lang> ...]' first, "
            "or install it manually.".format(tool)
        )
    return path


def run(cmd, check=True):
    cmd = [resolve(cmd[0])] + list(cmd[1:])
    print(" ".join(cmd))
    result = subprocess.call(cmd)
    if check and result != 0:
        sys.exit(result)
    return result


def run_quiet(cmd):
    """Run a command, swallowing output, failure, and a missing executable.

    Used for steps that are expected to sometimes be no-ops.
    """
    try:
        cmd = [resolve(cmd[0])] + list(cmd[1:])
    except ToolError:
        return
    subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_batched(prefix, files, separator=None):
    """Invoke 'prefix' over 'files', splitting into several calls if needed.

    'separator' (typically '--') is appended once per batch, immediately
    before the file names, so that a file named '-i' cannot be reinterpreted
    as an option.
    """
    base = list(prefix) + ([separator] if separator else [])
    base_len = sum(len(a) + 1 for a in base)

    batch = []
    batch_len = base_len
    for name in files:
        cost = len(name) + 1
        if batch and batch_len + cost > MAX_COMMAND_LINE:
            run(base + batch)
            batch = []
            batch_len = base_len
        batch.append(name)
        batch_len += cost
    if batch:
        run(base + batch)


def git_output(args):
    try:
        return subprocess.check_output([resolve("git")] + list(args))
    except subprocess.CalledProcessError as exc:
        raise ToolError("git {} failed with exit status {}".format(" ".join(args), exc.returncode))
    except OSError as exc:
        raise ToolError("could not execute git: {}".format(exc))


def git_tracked_files(extensions):
    """Return tracked files with one of 'extensions'.

    '-z' is required: with the default core.quotePath, git C-quotes non-ASCII
    names, and a name containing a newline would otherwise be split in two.
    """
    raw = git_output(["ls-files", "-z"])
    names = [chunk.decode("utf-8", "surrogateescape") for chunk in raw.split(b"\0") if chunk]
    return [n for n in names if n.lower().endswith(extensions)]


def positional(files):
    """Prefix each path with './' so it cannot be read as an option.

    Used for clang-tidy, whose '--' separator introduces compiler arguments
    rather than terminating option parsing.
    """
    return ["./" + f if not f.startswith("./") else f for f in files]


def repo_name():
    try:
        top = git_output(["rev-parse", "--show-toplevel"]).decode("utf-8", "surrogateescape").strip()
        name = os.path.basename(top)
    except ToolError:
        name = "Unknown"
    return name + " Authors"


def build_header(lines, year, name):
    return "\n".join(lines).format(year=year, repo_name=name) + "\n\n"


def add_license_header(path, header_text):
    with open(path, "rb") as f:
        content = f.read()
    head = b"\n".join(content.split(b"\n")[:20])
    if LICENSE_MARKER.encode("utf-8") in head:
        return False

    header_bytes = header_text.encode("utf-8")
    if content[:2] == b"#!":
        newline_pos = content.find(b"\n")
        insert_at = newline_pos + 1 if newline_pos != -1 else len(content)
    else:
        insert_at = 0

    with open(path, "wb") as f:
        f.write(content[:insert_at])
        f.write(header_bytes)
        f.write(content[insert_at:])
    return True


def detect_languages():
    found = []
    try:
        cpp_sources = git_tracked_files(CPP_HEADER_AND_SOURCE_EXTENSIONS)
        py_sources = git_tracked_files((".py",))
    except ToolError as exc:
        print("  (not a git working tree, or git unavailable: {})".format(exc))
        cpp_sources = py_sources = []

    if os.path.isfile("CMakeLists.txt") or cpp_sources:
        found.append("cpp")
        print("  cpp    (found CMakeLists.txt and/or tracked C/C++ sources)")
    if os.path.isfile("pyproject.toml") or os.path.isfile("setup.py") or py_sources:
        found.append("python")
        print("  python (found pyproject.toml/setup.py and/or tracked .py files)")
    if not found:
        print("  (nothing detected)")
    return found


def require_langs(langs):
    if not langs:
        sys.stderr.write("\nERROR: at least one language is required, e.g.:\n")
        sys.stderr.write("    python dev.py setup cpp python\n")
        sys.stderr.write("\nKnown languages: {}\n".format(" ".join(KNOWN_LANGS)))
        sys.stderr.write("\nDetected in this repo:\n")
        detect_languages()
        sys.stderr.write("\n")
        sys.exit(1)
    for lang in langs:
        if lang not in KNOWN_LANGS:
            fail("unknown language '{}' (known: {})".format(lang, " ".join(KNOWN_LANGS)))


def ensure_gitignore(gitignore_file, patterns):
    existing = set()
    needs_leading_newline = False
    if os.path.isfile(gitignore_file):
        with io.open(gitignore_file, "r", encoding="utf-8") as f:
            content = f.read()
        existing = set(content.splitlines())
        needs_leading_newline = bool(content) and not content.endswith("\n")

    to_add = [p for p in patterns if p not in existing]
    if not to_add:
        return
    with io.open(gitignore_file, "a", encoding="utf-8", newline="\n") as f:
        if needs_leading_newline:
            f.write(u"\n")
        for p in to_add:
            f.write(p + u"\n")
            print("Added '{}' to {}".format(p, gitignore_file))


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_state(state_file):
    state = {}
    if os.path.isfile(state_file):
        with io.open(state_file, "r", encoding="utf-8") as f:
            for line in f:
                # rsplit, not split: a tracked name may contain spaces.
                parts = line.rstrip("\r\n").rsplit(" ", 1)
                if len(parts) == 2 and parts[0]:
                    state[parts[0]] = parts[1]
    return state


def write_state(state_file, state):
    tmp = state_file + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for name in sorted(state):
            f.write(u"{} {}\n".format(name, state[name]))
    os.replace(tmp, state_file)


def report_conflict(name, src, reason):
    print("")
    print("WARNING: '{}' {} — leaving it alone.".format(name, reason))
    print("  Local vs. DevTools' current version:")
    with io.open(name, "r", encoding="utf-8", errors="replace") as f_local, \
            io.open(src, "r", encoding="utf-8", errors="replace") as f_upstream:
        sys.stdout.writelines(
            unified_diff(f_local.readlines(), f_upstream.readlines(), fromfile=name, tofile=src)
        )
    print("  Resolve manually (or delete '{}' and re-run to accept upstream), then re-sync.".format(name))
    print("")


def sync_config(devtools_dir, state_file, files):
    state = read_state(state_file)
    for name in files:
        src = os.path.join(devtools_dir, "config", name)
        if not os.path.isfile(src):
            fail("{} not found in DevTools checkout.".format(src))

        new_hash = sha256_of(src)
        old_hash = state.get(name)

        if os.path.isfile(name):
            if old_hash is None:
                # Pre-existing file this script has never written. Treat as a
                # conflict rather than silently clobbering hand-written config.
                if sha256_of(name) != new_hash:
                    report_conflict(name, src, "already exists and was not written by DevTools")
                    continue
            elif sha256_of(name) != old_hash:
                report_conflict(name, src, "has local changes since the last DevTools sync")
                continue

        with open(src, "rb") as f_src:
            content = f_src.read()
        with open(name, "wb") as f_dst:
            f_dst.write(content)
        state[name] = new_hash
        print("Synced '{}' from DevTools.".format(name))
    write_state(state_file, state)


def sync_devtools_files(langs):
    files = []
    if "cpp" in langs:
        files += [".clang-format", ".clang-tidy"]
    if "python" in langs:
        files += ["ruff.toml"]
    return files


def cmd_help(_args):
    print("Usage: python dev.py <command> <lang> [<lang> ...]   (known languages: {})".format(" ".join(KNOWN_LANGS)))
    print("")
    print("Commands: help, detect-languages, setup, format, lint, sync-devtools, license-headers")
    print("")
    print("Detected in this repo:")
    detect_languages()


def cmd_detect_languages(_args):
    detect_languages()


def cmd_setup(args):
    require_langs(args.langs)

    # `git config --get-all` exits 1 when the key isn't set at all - the
    # normal case for most repos - so check the exit code directly instead
    # of routing this through git_output (which would raise ToolError).
    hooks_path_set = subprocess.call(
        [resolve("git"), "config", "--get-all", "core.hooksPath"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0
    if hooks_path_set:
        print("Note: clearing an existing core.hooksPath so pre-commit's hooks take effect.")
        run_quiet(["git", "config", "--unset-all", "core.hooksPath"])

    # sys.executable, not bare 'pip': guarantees installation into the
    # interpreter running this script rather than whichever pip is first on PATH.
    pip = [sys.executable, "-m", "pip", "install"]
    if "python" in args.langs:
        cmd = pip + ["-e", ".[dev]"]
    else:
        cmd = pip + ["pre-commit"]
    print(" ".join(cmd))
    result = subprocess.call(cmd)
    if result != 0:
        sys.exit(result)

    run(["pre-commit", "install", "--hook-type", "pre-commit", "--hook-type", "commit-msg"])
    cmd_sync_devtools(args)


def cmd_sync_devtools(args):
    require_langs(args.langs)
    ensure_gitignore(".gitignore", [".devtools/", STATE_FILE + ".tmp"])
    sync_config(".devtools", STATE_FILE, sync_devtools_files(args.langs))


def cmd_format(args):
    require_langs(args.langs)
    if "cpp" in args.langs:
        files = git_tracked_files(CPP_HEADER_AND_SOURCE_EXTENSIONS)
        if files:
            run_batched(["clang-format", "-i"], files, separator="--")
    if "python" in args.langs:
        run(["ruff", "format", "."])
        run(["ruff", "check", "--fix", "."])


def cmd_lint(args):
    require_langs(args.langs)
    if "cpp" in args.langs:
        files = git_tracked_files(CPP_SOURCE_EXTENSIONS)
        if files:
            build_dir = os.environ.get("BUILD_DIR", "build")
            run_batched(["clang-tidy", "-p", build_dir], positional(files))
    if "python" in args.langs:
        run(["ruff", "check", "."])
        run(["ruff", "format", "--check", "."])


def cmd_license_headers(args):
    require_langs(args.langs)
    year = datetime.date.today().year
    name = repo_name()
    changed = []

    if "python" in args.langs:
        header = build_header(PYTHON_HEADER_LINES, year, name)
        for f in git_tracked_files((".py",)):
            if add_license_header(f, header):
                changed.append(f)

    if "cpp" in args.langs:
        header = build_header(CPP_HEADER_LINES, year, name)
        for f in git_tracked_files(CPP_HEADER_AND_SOURCE_EXTENSIONS):
            if add_license_header(f, header):
                changed.append(f)

    if changed:
        print("Added the Apache 2.0 license header to:")
        for f in changed:
            print("  - " + f)
    else:
        print("Every tracked source file already has the license header.")


def cmd_ensure_gitignore(args):
    ensure_gitignore(args.gitignore_file, args.patterns)


def cmd_sync_config(args):
    sync_config(args.devtools_dir, args.state_file, args.files)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="devtools.py")
    sub = parser.add_subparsers(dest="command")

    for name, func in (
            ("help", cmd_help),
            ("detect-languages", cmd_detect_languages),
            ("setup", cmd_setup),
            ("format", cmd_format),
            ("lint", cmd_lint),
            ("sync-devtools", cmd_sync_devtools),
            ("license-headers", cmd_license_headers),
    ):
        p = sub.add_parser(name)
        p.add_argument("langs", nargs="*")
        p.set_defaults(func=func)

    p_gitignore = sub.add_parser("ensure-gitignore")
    p_gitignore.add_argument("gitignore_file")
    p_gitignore.add_argument("patterns", nargs="+")
    p_gitignore.set_defaults(func=cmd_ensure_gitignore)

    p_sync = sub.add_parser("sync-config")
    p_sync.add_argument("devtools_dir")
    p_sync.add_argument("state_file")
    p_sync.add_argument("files", nargs="+")
    p_sync.set_defaults(func=cmd_sync_config)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        sys.exit(1)
    try:
        args.func(args)
    except ToolError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()
