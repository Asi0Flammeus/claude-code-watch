# Claude Code Usage CLI - Project Instructions

## Project Overview
CLI tool to monitor Claude Code subscription usage limits.
- **Language**: Python 3.8+ (stdlib only, zero dependencies)
- **Platform**: Cross-platform (Linux, macOS, Windows)
- **Entry point**: `claude-usage` (executable Python script)

## Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types
| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no code change |
| `refactor` | Code change, no new feature or fix |
| `perf` | Performance improvement |
| `test` | Adding/updating tests |
| `build` | Build system, dependencies |
| `ci` | CI/CD configuration |
| `chore` | Maintenance, tooling |

### Scopes (optional)
- `api` - API communication
- `cli` - CLI arguments/parsing
- `analytics` - Analytics/history features
- `cache` - Caching system
- `config` - Configuration handling
- `display` - Output formatting
- `notify` - Notifications
- `export` - Export features

### Examples
```bash
feat(cli): add --version flag
fix(api): handle network timeout gracefully
docs: update README with installation steps
test(analytics): add unit tests for get_period_stats
ci: add GitHub Actions workflow
chore: update .gitignore
```

## Code Style

- Follow PEP 8
- Use type hints for function signatures
- Docstrings for public functions (Google style)
- Max line length: 100 characters
- Use f-strings for formatting

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=claude_usage --cov-report=term-missing

# Run specific test file
pytest tests/test_api.py -v
```

## Development Workflow

1. Create feature branch: `git checkout -b feat/feature-name`
2. Make changes with conventional commits
3. Run tests: `pytest`
4. Run linting: `ruff check .`
5. Push and create PR

## File Structure

```
claude-code-usage-cli/
├── claude-usage           # Main executable script
├── tests/                 # Test suite
│   ├── conftest.py       # Fixtures
│   ├── test_*.py         # Test files
│   └── fixtures/         # Test data
├── .github/workflows/    # CI/CD
├── docs/                 # Documentation
└── .claude/              # Claude Code config
    ├── CLAUDE.md         # This file
    └── TODO.md           # Development roadmap
```

## Key Files

- `claude-usage` - Main script (all code in single file)
- `~/.claude/.usage_config.json` - User configuration
- `~/.claude/.usage_history.json` - Usage history
- `~/.claude/.credentials.json` - Claude Code credentials

## API Reference

- **OAuth API**: `https://api.anthropic.com/api/oauth/usage`
- **Admin API**: `https://api.anthropic.com/v1/organizations/usage_report/messages`
