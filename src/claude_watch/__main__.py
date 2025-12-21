"""Enable running claude-watch as a module: python -m claude_watch."""

import sys
from pathlib import Path

# During transition: support running from src layout before full migration
# After migration, this will import directly from claude_watch.cli
_project_root = Path(__file__).parent.parent.parent
_legacy_module = _project_root / "claude_watch.py"

if _legacy_module.exists():
    # Transition period: import from legacy single-file module
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from claude_watch import main
else:
    # Post-migration: import from package
    from claude_watch.cli import main

if __name__ == "__main__":
    main()
