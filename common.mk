.PHONY: format lint

BUILD_DIR ?= build

format:
	clang-format -i $$(git ls-files '*.h' '*.hpp' '*.hh' '*.hxx' '*.c' '*.cc' '*.cpp' '*.cxx')

lint:
	clang-tidy -p $(BUILD_DIR) $$(git ls-files '*.c' '*.cc' '*.cpp' '*.cxx')
