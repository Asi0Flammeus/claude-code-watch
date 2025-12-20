# Claude Watch - Development TODO

## Phase 1: Project Structure Refactoring ⏳

**Goal**: Refactor the monolithic 2.3k-line `claude_watch.py` into a modern, maintainable src-layout Python CLI structure.

### Research Summary

Based on modern Python CLI best practices from:
- [Python Packaging User Guide](https://packaging.python.org/en/latest/guides/creating-command-line-tools/)
- [Hitchhiker's Guide to Python](https://docs.python-guide.org/writing/structure/)
- [HTTPie CLI](https://github.com/httpie/cli) - Production-grade reference
- [Typer CLI Best Practices](https://www.projectrules.ai/rules/typer)

### Target Project Structure

```
claude-watch/
├── pyproject.toml              # Updated build config
├── README.md
├── Makefile
├── src/
│   └── claude_watch/
│       ├── __init__.py         # Version, public exports
│       ├── __main__.py         # python -m claude_watch entry
│       ├── cli.py              # Main CLI commands (argparse)
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py     # Configuration management
│       │   └── credentials.py  # Credential handling (keychain, file)
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── client.py       # API client (OAuth, Admin)
│       │   └── cache.py        # Response caching logic
│       │
│       ├── display/
│       │   ├── __init__.py
│       │   ├── colors.py       # ANSI color codes + support detection
│       │   ├── spinner.py      # CLI spinner animation
│       │   ├── progress.py     # Progress bars, sparklines
│       │   ├── usage.py        # Usage display formatting
│       │   └── analytics.py    # Analytics tables + charts
│       │
│       ├── history/
│       │   ├── __init__.py
│       │   └── storage.py      # Usage history persistence
│       │
│       ├── setup/
│       │   ├── __init__.py
│       │   ├── wizard.py       # Interactive setup wizard
│       │   ├── completion.py   # Shell completion setup
│       │   └── systemd.py      # Systemd timer integration
│       │
│       ├── update/
│       │   ├── __init__.py
│       │   └── checker.py      # Version check + upgrade
│       │
│       └── utils/
│           ├── __init__.py
│           ├── time.py         # Time parsing + formatting
│           └── platform.py     # Cross-platform utilities
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_cli.py
│   ├── test_api.py
│   ├── test_display.py
│   ├── test_config.py
│   └── test_history.py
│
├── completions/                # Shell completion scripts
│   ├── claude-watch.bash
│   ├── claude-watch.zsh
│   └── claude-watch.fish
│
└── docs/
    └── ...
```

### Refactoring Tasks

#### 1.1 Create src-layout skeleton
- [ ] Create `src/claude_watch/` directory structure
- [ ] Create all `__init__.py` files with proper exports
- [ ] Create `__main__.py` for `python -m claude_watch` support

#### 1.2 Extract display module (~400 lines)
- [ ] Extract `Colors` class → `display/colors.py`
- [ ] Extract `Spinner` class → `display/spinner.py`
- [ ] Extract progress bar functions → `display/progress.py`
- [ ] Extract usage display → `display/usage.py`
- [ ] Extract analytics display → `display/analytics.py`

#### 1.3 Extract config module (~200 lines)
- [ ] Extract config load/save → `config/settings.py`
- [ ] Extract credential handling → `config/credentials.py`
- [ ] Handle cross-platform paths (macOS keychain, Linux file)

#### 1.4 Extract API module (~250 lines)
- [ ] Extract API client → `api/client.py`
- [ ] Extract cache logic → `api/cache.py`
- [ ] Create mock data support for `--dry-run`

#### 1.5 Extract setup module (~400 lines)
- [ ] Extract setup wizard → `setup/wizard.py`
- [ ] Extract shell completion → `setup/completion.py`
- [ ] Extract systemd timer → `setup/systemd.py`

#### 1.6 Extract history module (~100 lines)
- [ ] Extract history storage → `history/storage.py`

#### 1.7 Extract update module (~200 lines)
- [x] Implement `--update` / `-U` CLI flag ✅ (2025-12-20)
- [x] Implement version comparison (semantic versioning) ✅
- [x] Implement installation method detection (uv/pipx/pip) ✅
- [x] Implement PyPI version check ✅
- [x] Implement upgrade execution ✅
- [x] Add `--update check` for check-only mode ✅
- [x] Add tests for update functionality ✅
- [ ] Extract version checking → `update/checker.py` (post-refactor)

#### 1.8 Extract utilities (~100 lines)
- [ ] Extract time formatting → `utils/time.py`
- [ ] Extract platform detection → `utils/platform.py`

#### 1.9 Create main CLI entry (~300 lines)
- [ ] Refactor main() → `cli.py` with clean argument parsing
- [ ] Wire up all modules
- [ ] Maintain backward compatibility with existing CLI interface

#### 1.10 Update build configuration
- [ ] Update `pyproject.toml` for src-layout
- [ ] Update entry points: `claude-watch = "claude_watch.cli:main"`
- [ ] Update `[tool.hatch.build]` paths
- [ ] Update test imports and coverage config

#### 1.11 Migration testing
- [ ] Verify all existing CLI commands work identically
- [ ] Update existing tests for new structure
- [ ] Add integration tests for module boundaries
- [ ] Test installation via pip, pipx, uv

### Design Principles

1. **Zero dependencies** - Maintain stdlib-only requirement
2. **Backward compatible** - All existing CLI flags must work
3. **Single responsibility** - Each module handles one concern
4. **Clean interfaces** - Modules communicate through clear APIs
5. **Testable** - Each module independently testable
6. **Progressive** - Can be done incrementally without breaking main

### Estimated Complexity

| Module | Lines | Priority | Complexity |
|--------|-------|----------|------------|
| display | ~400 | High | Medium |
| config | ~200 | High | Low |
| api | ~250 | High | Medium |
| setup | ~400 | Medium | High |
| update | ~200 | Low | Low |
| history | ~100 | Low | Low |
| utils | ~100 | Low | Low |
| cli | ~300 | Critical | High |

### Migration Strategy

1. **Phase A**: Create new structure alongside existing file
2. **Phase B**: Move code module-by-module with tests
3. **Phase C**: Update imports and wire modules
4. **Phase D**: Remove old `claude_watch.py`
5. **Phase E**: Update documentation and CI

---

## Phase 2: Future Enhancements (Post-Refactor)

- [ ] Add Typer for enhanced CLI (optional dependency)
- [ ] Add Rich for better terminal output (optional dependency)
- [ ] Add JSON schema validation for config files
- [ ] Add plugin architecture for custom displays
- [ ] Add export formats (CSV, JSON, HTML reports)

---

*Last updated: 2025-12-20*
