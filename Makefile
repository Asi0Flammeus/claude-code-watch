# Claude Code Watch - Development Commands
# ═══════════════════════════════════════════════════════════════════════════════

.PHONY: help install install-dev test test-cov lint format typecheck pre-commit clean

# Default target
help:
	@echo "Claude Code Watch - Development Commands"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  install      Install the package"
	@echo "  install-dev  Install with development dependencies"
	@echo "  test         Run tests"
	@echo "  test-cov     Run tests with coverage report"
	@echo "  lint         Run linter (ruff)"
	@echo "  format       Format code (ruff)"
	@echo "  typecheck    Run type checker (mypy)"
	@echo "  pre-commit   Run all pre-commit hooks"
	@echo "  clean        Remove build artifacts"
	@echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Installation
# ═══════════════════════════════════════════════════════════════════════════════

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# ═══════════════════════════════════════════════════════════════════════════════
# Testing
# ═══════════════════════════════════════════════════════════════════════════════

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html

test-fast:
	pytest tests/ -v -x --tb=short

# ═══════════════════════════════════════════════════════════════════════════════
# Linting & Formatting
# ═══════════════════════════════════════════════════════════════════════════════

lint:
	ruff check .

lint-fix:
	ruff check . --fix

format:
	ruff format .

format-check:
	ruff format . --check

typecheck:
	mypy claude_watch.py --ignore-missing-imports

pre-commit:
	pre-commit run --all-files

# ═══════════════════════════════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════════════════════════════

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ═══════════════════════════════════════════════════════════════════════════════
# Build & Release
# ═══════════════════════════════════════════════════════════════════════════════

build:
	python -m build

publish-test:
	python -m twine upload --repository testpypi dist/*

publish:
	python -m twine upload dist/*
