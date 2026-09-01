# .devtools/setup.mk
#
# Real implementation of setup/format/lint/sync-devtools/help for a
# consuming repo. Invoked as:
#   make -f .devtools/setup.mk <target> LANGS="<space-separated languages>"
# from that repo's own (tiny, forwarding-only) Makefile - see this repo's
# README for the pattern. Runs with the CONSUMING repo as the working
# directory (`make -f` does not change directory).
#
# LANGS is mandatory and has no default: it must name at least one of
# KNOWN_LANGS below, e.g. LANGS="cpp" or LANGS="cpp python". Run
# `make help` (no LANGS needed) for a language suggestion based on what's
# actually in the repo.

SHELL := /bin/sh
.SHELLFLAGS := -ec
.ONESHELL:

KNOWN_LANGS := cpp python
STATE_FILE := .devtools-sync.sha256
BUILD_DIR ?= build

.PHONY: setup format lint sync-devtools help _check-langs _unset-hookspath

help:
	@echo "Usage: make setup LANGS=\"<lang> [<lang> ...]\"   (known: $(KNOWN_LANGS))"
	echo ""
	echo "Detected in this repo:"
	.devtools/scripts/detect-languages

_check-langs:
	@if [ -z "$(strip $(LANGS))" ]; then
	    echo "" >&2
	    echo "ERROR: LANGS is required, e.g.:" >&2
	    echo "    make setup LANGS=\"cpp python\"" >&2
	    echo "" >&2
	    echo "Known languages: $(KNOWN_LANGS)" >&2
	    echo "" >&2
	    echo "Detected in this repo:" >&2
	    .devtools/scripts/detect-languages >&2 || true
	    echo "" >&2
	    exit 1
	fi
	for lang in $(LANGS); do
	    case " $(KNOWN_LANGS) " in
	        *" $$lang "*) ;;
	        *) echo "ERROR: unknown language '$$lang' (known: $(KNOWN_LANGS))" >&2; exit 1 ;;
	    esac
	done

_unset-hookspath:
	-git config --unset-all core.hooksPath

setup: _check-langs _unset-hookspath
	git submodule update --init --recursive
	if echo " $(LANGS) " | grep -q ' python '; then
	    pip install -e ".[dev]"
	else
	    pip install pre-commit
	fi
	pre-commit install --hook-type pre-commit --hook-type commit-msg
	$(MAKE) --no-print-directory -f .devtools/setup.mk sync-devtools LANGS="$(LANGS)"

sync-devtools: _check-langs
	@.devtools/scripts/ensure-gitignore .gitignore $(STATE_FILE).tmp
	.devtools/scripts/sync-config .devtools $(STATE_FILE) $(if $(filter cpp,$(LANGS)),.clang-format .clang-tidy) $(if $(filter python,$(LANGS)),ruff.toml)

format: _check-langs
	@if echo " $(LANGS) " | grep -q ' cpp '; then
	    clang-format -i $$(git ls-files '*.h' '*.hpp' '*.hh' '*.hxx' '*.c' '*.cc' '*.cpp' '*.cxx')
	fi
	if echo " $(LANGS) " | grep -q ' python '; then
	    ruff format .
	    ruff check --fix .
	fi

lint: _check-langs
	@if echo " $(LANGS) " | grep -q ' cpp '; then
	    clang-tidy -p $(BUILD_DIR) $$(git ls-files '*.c' '*.cc' '*.cpp' '*.cxx')
	fi
	if echo " $(LANGS) " | grep -q ' python '; then
	    ruff check .
	    ruff format --check .
	fi
