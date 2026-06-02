# ChangeX — developer entry points.
#
# Thin wrappers over uv (preferred) with a pip fallback, so a fresh clone is one
# command away from a working CLI + MCP server. Run `make help` for the list.
#
# These targets assume `uv` (https://docs.astral.sh/uv/). If you do not have it,
# `make install-pip` / `make dev-pip` use plain pip + venv instead.

.DEFAULT_GOAL := help
SHELL := /bin/bash

# Use the venv's python when present so `make test` / `make demo` work whether
# you installed via uv (.venv) or pip.
VENV    := .venv
PY      := $(VENV)/bin/python
CHANGEX := $(VENV)/bin/changex

.PHONY: help install install-pip dev dev-pip test lint typecheck demo mcp build clean

help: ## Show this help.
	@echo "ChangeX make targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install the whole workspace (CLI + MCP) into .venv via uv.
	uv sync
	@echo "Installed. Try:  make demo   |   $(CHANGEX) --help"

install-pip: ## pip fallback: editable-install both packages into a venv.
	python -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e packages/core -e packages/mcp
	@echo "Installed (pip). Try:  make demo   |   $(CHANGEX) --help"

dev: ## Install with the dev toolchain (pytest/ruff/mypy) via uv.
	uv sync --extra dev

dev-pip: ## pip fallback for the dev toolchain.
	python -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e "packages/core[dev]" -e "packages/mcp[dev]"

test: ## Run the test suite.
	$(PY) -m pytest

lint: ## Lint with ruff.
	$(PY) -m ruff check packages

typecheck: ## Type-check with mypy.
	$(PY) -m mypy packages/core/src packages/mcp/src

demo: ## Run the end-to-end demo on examples/sample.docx.
	./scripts/demo.sh

mcp: ## Launch the MCP stdio server (Ctrl-C to stop).
	@echo "Starting changex-mcp on stdio (for an MCP client to connect to)..."
	$(PY) -m changex_mcp

build: ## Build wheels for the meta package + both members.
	uv build --all-packages

clean: ## Remove build artifacts and demo output.
	rm -rf dist build **/dist **/build **/*.egg-info examples/out
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
