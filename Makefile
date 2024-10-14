MAKEFLAGS += --no-print-directory --silent

################################################################################
# Makefile Variables
################################################################################
SHELL := $(or $(shell echo $$SHELL),/bin/sh)

POETRY_VERSION = 1.8.3

VENV_PATH ?= .venv
POETRY_HOME ?= .venv_poetry

PYTHON = $(shell command -v python3)
POETRY = $(POETRY_HOME)/bin/poetry


################################################################################
# Default
################################################################################
.DEFAULT_GOAL := default

.PHONY: default
default:
	@echo "Running default task"
	@$(MAKE) build
	@$(MAKE) install-galaxy
	@$(MAKE) format


################################################################################
# Setup & Install
################################################################################
.PHONY: build
build:
	$(POETRY) build;

.PHONY: install-galaxy
install-galaxy:
	$(POETRY) install --only-root

.PHONY: install
install:
	$(MAKE) install-poetry
	$(MAKE) clean
	$(MAKE) new-venv
	$(MAKE) install-deps
	$(MAKE) build
	$(MAKE) install-galaxy
	$(MAKE) install-hooks

.PHONY: reinstall
reinstall:
	$(MAKE) delete-venv
	$(MAKE) remove-poetry
	$(MAKE) clean
	$(MAKE) install

.PHONY: install-poetry
install-poetry:
	@if [ -f "$(POETRY)" ]; then \
		echo "Poetry already installed in virtual environment"; \
	else \
		echo "Installing poetry in virtual environment"; \
		$(PYTHON) -m venv "$(POETRY_HOME)"; \
		$(POETRY_HOME)/bin/pip install --upgrade pip; \
		$(POETRY_HOME)/bin/pip install poetry==$(POETRY_VERSION); \
	fi

.PHONY: install-deps
-include .env
install-deps:
	@echo "Installing dependencies"
	@$(POETRY) install --no-root --no-interaction --no-ansi --all-extras -v


################################################################################
# Development - Virtual Environment
################################################################################
.PHONY: new-venv
new-venv:
	@echo "Creating virtual environment"
	@$(PYTHON) -m venv "$(VENV_PATH)"

.PHONY: delete-venv
delete-venv:
	@echo "Deleting virtual environment"
	@rm -rf "$(VENV_PATH)"

.PHONY: remove-poetry
remove-poetry:
	@echo "Removing poetry from virtual environment"
	@rm -rf "$(POETRY_HOME)"


################################################################################
# Development - Utilities
################################################################################
.PHONY: clean
clean:
	@echo "Cleaning up"
	@rm -rf .pytest_cache .ruff_cache .coverage htmlcov/
	@find . -type d -name '__pycache__' -exec rm -rf {} +
	@find . -type f -name '*.py[co]' -delete
	@find . -type f -name '*~' -delete


################################################################################
# Development - Pre-commit Hooks
################################################################################
.PHONY: install-hooks
install-hooks:
	@echo "Installing pre-commit hooks"
	@$(POETRY) run pre-commit install

.PHONY: update-hooks
update-hooks:
	@echo "Updating pre-commit hooks"
	@$(POETRY) run pre-commit autoupdate


################################################################################
# Development - Dependencies
################################################################################
.PHONY: lock
lock:
	@echo "Locking dependencies"
	@$(POETRY) lock --no-update

.PHONY: lock-update
lock-update:
	@echo "Locking and updating dependencies"
	@$(POETRY) update


################################################################################
# Linting & Formatting
################################################################################
.PHONY: lint
lint:
	@echo "Running ruff check and format check"
#	@$(POETRY) run galaxy validate-all
	@$(POETRY) run ruff check . --exit-non-zero-on-fix
	@$(POETRY) run ruff format . --check

.PHONY: format
format:
	@echo "Running ruff format"
	@$(POETRY) run ruff format .
	@$(POETRY) run ruff check . --fix

.PHONY: autofix-unsafe
autofix-unsafe:
	@echo "Running ruff with autofix-unsafe"
	@$(POETRY) run galaxy validate-all --unsafe
	@$(POETRY) run ruff check . --unsafe-fixes


################################################################################
# Testing
################################################################################
.PHONY: test
test:
	$(POETRY) run pytest --ignore=galaxy/cli/cookiecutter -vvv;


################################################################################
# Development - Execution
################################################################################
.PHONY: run
run:
	$(POETRY) run galaxy run;

.PHONY: run-debug
run-debug:
	$(POETRY) run galaxy run -d;
