# Versioning Convention

Claude-Watch follows a TODO-progress-based semantic versioning scheme.

## Version Format: `MAJOR.MINOR.PATCH`

| Part | Format | Trigger | Responsibility |
|------|--------|---------|----------------|
| **Major** | `X.0.0` | Breaking changes, major milestones | Manual (user decision) |
| **Minor** | `0.X.0` | Phase completed in TODO.md | Auto-increment on phase completion |
| **Patch** | `0.0.X` | Task within a phase completed | Auto-increment on task completion |

## Examples

```
0.1.0  → Phase 1 complete
0.1.1  → Task 1.1 complete
0.1.2  → Task 1.2 complete
0.1.3  → Task 1.3 complete
0.2.0  → Phase 2 complete
1.0.0  → User decides (e.g., stable release)
```

## Release Workflow

### After completing a task (patch bump):

```bash
# 1. Update __version__ in src/claude_watch/_version.py
#    e.g., "0.1.0" → "0.1.1"

# 2. Commit
git add src/claude_watch/_version.py
git commit -m "chore(version): bump to 0.1.1"

# 3. Tag and push
git tag v0.1.1
git push origin main --tags
```

### After completing a phase (minor bump):

```bash
# 1. Update __version__ in src/claude_watch/_version.py
#    e.g., "0.1.5" → "0.2.0"

# 2. Commit
git add src/claude_watch/_version.py
git commit -m "chore(version): bump to 0.2.0 (Phase 2 complete)"

# 3. Tag and push
git tag v0.2.0
git push origin main --tags
```

## Automated Release

When a tag matching `v*` is pushed, the GitHub Actions workflow automatically:

1. Runs tests
2. Builds the package
3. Creates a GitHub Release with auto-generated notes
4. (Optional) Publishes to PyPI if configured

## Update Check

Users can check for updates via:

```bash
claude-watch --update check   # Check only
claude-watch --update         # Check and install
```

The update system fetches the latest release from GitHub (no PyPI dependency).
