# Contributing to Claude Code Watch

Thank you for your interest in contributing to Claude Code Watch! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Pre-commit Hooks](#pre-commit-hooks)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

Please be respectful and constructive in all interactions. We're all here to make this project better.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/claude-watch.git
   cd claude-watch
   ```
3. **Add the upstream remote**:
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/claude-watch.git
   ```

## Development Setup

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git

### Installation

1. **Create a virtual environment** (recommended):
   ```bash
   python -m venv env
   source env/bin/activate  # Linux/macOS
   # or
   .\env\Scripts\activate   # Windows
   ```

2. **Install development dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

3. **Verify the installation**:
   ```bash
   make test
   ```

## Pre-commit Hooks

We use pre-commit hooks to ensure code quality before commits. These hooks run automatically on `git commit`.

### Setup Pre-commit

1. **Install pre-commit** (included in dev dependencies):
   ```bash
   pip install pre-commit
   ```

2. **Install the hooks**:
   ```bash
   pre-commit install
   ```

3. **Verify installation**:
   ```bash
   pre-commit run --all-files
   ```

### What the Hooks Check

| Hook | Purpose |
|------|---------|
| **ruff** | Linting and code style |
| **ruff-format** | Code formatting |
| **mypy** | Type checking |
| **trailing-whitespace** | Remove trailing whitespace |
| **end-of-file-fixer** | Ensure files end with newline |
| **check-yaml** | Validate YAML syntax |
| **check-json** | Validate JSON syntax |
| **check-added-large-files** | Prevent large files (>500KB) |
| **check-merge-conflict** | Detect merge conflict markers |
| **detect-private-key** | Prevent committing private keys |
| **bandit** | Security vulnerability scanning |

### Bypassing Hooks (Not Recommended)

In rare cases where you need to bypass hooks:

```bash
git commit --no-verify -m "message"
```

**Note**: CI will still run all checks, so this only delays fixing issues.

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-prompt-flag` - New features
- `fix/cache-expiry-bug` - Bug fixes
- `docs/update-readme` - Documentation
- `refactor/simplify-analytics` - Code refactoring
- `test/add-cli-tests` - Test additions

### Commit Messages

Follow conventional commit format:

```
type(scope): short description

Longer description if needed.

Fixes #123
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Examples**:
```
feat(cli): add --prompt flag for shell integration
fix(cache): handle expired cache gracefully
docs(readme): add installation instructions
test(cli): add integration tests for argument parsing
```

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_cli.py -v

# Run specific test
pytest tests/test_cli.py::TestCLIHelp::test_help_exits_zero -v

# Run fast (stop on first failure)
make test-fast
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use descriptive test names that explain what's being tested
- Use fixtures from `conftest.py` for common setup

**Example**:
```python
class TestMyFeature:
    """Tests for my new feature."""

    def test_basic_functionality(self):
        """Test that basic functionality works."""
        result = my_function()
        assert result == expected

    def test_edge_case(self):
        """Test handling of edge case."""
        result = my_function(edge_input)
        assert result is None
```

### Test Coverage

We aim for high test coverage. Check coverage with:

```bash
make test-cov
# Opens htmlcov/index.html with detailed report
```

## Code Style

### Python Style

- Follow PEP 8 guidelines
- Use type hints where practical
- Maximum line length: 100 characters
- Use descriptive variable and function names

### Formatting

Code is automatically formatted by ruff. To manually format:

```bash
make format
```

To check formatting without changing:

```bash
make format-check
```

### Linting

```bash
make lint        # Check for issues
make lint-fix    # Auto-fix what's possible
```

### Type Checking

```bash
make typecheck
```

## Pull Request Process

### Before Submitting

1. **Sync with upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks**:
   ```bash
   make lint
   make typecheck
   make test
   ```

3. **Update documentation** if needed

### Submitting

1. Push your branch to your fork
2. Create a Pull Request on GitHub
3. Fill out the PR template
4. Wait for CI checks to pass
5. Address any review feedback

### PR Requirements

- [ ] All CI checks pass (tests, lint, type-check)
- [ ] Tests added for new functionality
- [ ] Documentation updated if needed
- [ ] Commit messages follow convention
- [ ] No merge conflicts with main

### After Merge

Clean up your local branches:

```bash
git checkout main
git pull upstream main
git branch -d feature/your-branch
```

## Available Make Targets

| Target | Description |
|--------|-------------|
| `make help` | Show all available targets |
| `make install` | Install the package |
| `make install-dev` | Install with dev dependencies |
| `make test` | Run tests |
| `make test-cov` | Run tests with coverage |
| `make test-fast` | Run tests, stop on first failure |
| `make lint` | Run linter |
| `make lint-fix` | Auto-fix lint issues |
| `make format` | Format code |
| `make format-check` | Check formatting |
| `make typecheck` | Run type checker |
| `make pre-commit` | Run all pre-commit hooks |
| `make clean` | Remove build artifacts |

## Questions?

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- Be specific and include reproduction steps for bugs

Thank you for contributing!
