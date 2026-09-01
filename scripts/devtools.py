#!/usr/bin/env python3
"""
scripts/devtools.py

Cross-shell implementation of setup/format/lint/sync-devtools/help for a
repo consuming DevTools. Stdlib only (no pip installs needed to run this
script itself) and written to run on Python 3.5+.

Invoked from a consuming repo's own (tiny, forwarding-only) Makefile as:
    python .devtools/scripts/devtools.py <command> --langs <lang> [<lang> ...]

Every Make recipe that calls this is a single plain command with no shell
control-flow (no if/for/pipes/quoting), so it runs identically no matter
which shell Make executes recipes with - cmd.exe, PowerShell, or sh.
"""
import argparse
import hashlib
import os
import subprocess
import sys
from difflib import unified_diff

KNOWN_LANGS = ("cpp", "python")
CPP_HEADER_AND_SOURCE_EXTENSIONS = (".h", ".hpp", ".hh", ".hxx", ".c", ".cc", ".cpp", ".cxx")
CPP_SOURCE_EXTENSIONS = (".c", ".cc", ".cpp", ".cxx")
STATE_FILE = ".devtools-sync.sha256"


def run(cmd, check=True):
    print(" ".join(cmd))
    result = subprocess.call(cmd)
    if check and result != 0:
        sys.exit(result)
    return result


def run_quiet(cmd):
    """Run a command, swallowing both output and failure - used for a step that's expected to sometimes fail."""
    devnull = subprocess.DEVNULL if hasattr(subprocess, "DEVNULL") else open(os.devnull, "wb")
    subprocess.call(cmd, stdout=devnull, stderr=devnull)


def git_tracked_files(extensions):
    result = subprocess.check_output(["git", "ls-files"], universal_newlines=True)
    return [f for f in result.splitlines() if f.lower().endswith(extensions)]


def detect_languages():
    found = []
    if os.path.isfile("CMakeLists.txt") or git_tracked_files(CPP_HEADER_AND_SOURCE_EXTENSIONS):
        found.append("cpp")
        print("  cpp    (found CMakeLists.txt and/or tracked C/C++ sources)")
    if os.path.isfile("pyproject.toml") or os.path.isfile("setup.py") or git_tracked_files((".py",)):
        found.append("python")
        print("  python (found pyproject.toml/setup.py and/or tracked .py files)")
    if not found:
        print("  (nothing detected)")
    return found


def require_langs(langs):
    if not langs:
        sys.stderr.write("\nERROR: --langs is required, e.g.:\n")
        sys.stderr.write("    make setup LANGS=\"cpp python\"\n")
        sys.stderr.write("\nKnown languages: {}\n".format(" ".join(KNOWN_LANGS)))
        sys.stderr.write("\nDetected in this repo:\n")
        detect_languages()
        sys.stderr.write("\n")
        sys.exit(1)
    for lang in langs:
        if lang not in KNOWN_LANGS:
            sys.stderr.write("ERROR: unknown language '{}' (known: {})\n".format(lang, " ".join(KNOWN_LANGS)))
            sys.exit(1)


def ensure_gitignore(gitignore_file, patterns):
    existing = set()
    if os.path.isfile(gitignore_file):
        with open(gitignore_file, "r") as f:
            existing = set(line.rstrip("\n") for line in f)
    to_add = [p for p in patterns if p not in existing]
    if to_add:
        with open(gitignore_file, "a") as f:
            for p in to_add:
                f.write(p + "\n")
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
        with open(state_file, "r") as f:
            for line in f:
                parts = line.strip().split(" ")
                if len(parts) == 2:
                    state[parts[0]] = parts[1]
    return state


def write_state(state_file, state):
    tmp = state_file + ".tmp"
    with open(tmp, "w") as f:
        for name in sorted(state):
            f.write("{} {}\n".format(name, state[name]))
    os.replace(tmp, state_file)


def sync_config(devtools_dir, state_file, files):
    state = read_state(state_file)
    for name in files:
        src = os.path.join(devtools_dir, "config", name)
        if not os.path.isfile(src):
            sys.stderr.write("ERROR: {} not found in DevTools checkout.\n".format(src))
            sys.exit(1)

        new_hash = sha256_of(src)
        old_hash = state.get(name)

        if os.path.isfile(name) and old_hash and sha256_of(name) != old_hash:
            print("")
            print("WARNING: '{}' has local changes since the last DevTools sync — leaving it alone.".format(name))
            print("  Local vs. DevTools' current version:")
            with open(name, "r") as f_local, open(src, "r") as f_upstream:
                sys.stdout.writelines(unified_diff(f_local.readlines(), f_upstream.readlines(), fromfile=name, tofile=src))
            print("  Resolve manually (or delete '{}' and re-run to accept upstream), then re-sync.".format(name))
            print("")
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
    print("Usage: make setup LANGS=\"<lang> [<lang> ...]\"   (known: {})".format(" ".join(KNOWN_LANGS)))
    print("")
    print("Detected in this repo:")
    detect_languages()


def cmd_detect_languages(_args):
    detect_languages()


def cmd_setup(args):
    require_langs(args.langs)
    run_quiet(["git", "config", "--unset-all", "core.hooksPath"])
    run(["git", "submodule", "update", "--init", "--recursive"])
    if "python" in args.langs:
        run(["pip", "install", "-e", ".[dev]"])
    else:
        run(["pip", "install", "pre-commit"])
    run(["pre-commit", "install", "--hook-type", "pre-commit", "--hook-type", "commit-msg"])
    cmd_sync_devtools(args)


def cmd_sync_devtools(args):
    require_langs(args.langs)
    ensure_gitignore(".gitignore", [STATE_FILE + ".tmp"])
    sync_config(".devtools", STATE_FILE, sync_devtools_files(args.langs))


def cmd_format(args):
    require_langs(args.langs)
    if "cpp" in args.langs:
        files = git_tracked_files(CPP_HEADER_AND_SOURCE_EXTENSIONS)
        if files:
            run(["clang-format", "-i"] + files)
    if "python" in args.langs:
        run(["ruff", "format", "."])
        run(["ruff", "check", "--fix", "."])


def cmd_lint(args):
    require_langs(args.langs)
    if "cpp" in args.langs:
        files = git_tracked_files(CPP_SOURCE_EXTENSIONS)
        if files:
            run(["clang-tidy", "-p", os.environ.get("BUILD_DIR", "build")] + files)
    if "python" in args.langs:
        run(["ruff", "check", "."])
        run(["ruff", "format", "--check", "."])


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
    ):
        p = sub.add_parser(name)
        p.add_argument("--langs", nargs="*", default=[])
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
    args.func(args)


if __name__ == "__main__":
    main()
