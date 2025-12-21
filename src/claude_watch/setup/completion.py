"""Shell completion installation for claude-watch.

Provides functions for installing and configuring shell tab completion
for bash, zsh, and fish shells.
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

from claude_watch.display.colors import Colors


def detect_shell() -> str:
    """Detect the user's default shell.

    Returns:
        Shell name: 'bash', 'zsh', or 'fish'.
    """
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return "zsh"
    elif "fish" in shell:
        return "fish"
    elif "bash" in shell:
        return "bash"
    # Fallback: check if running in a known shell
    if os.environ.get("ZSH_VERSION"):
        return "zsh"
    if os.environ.get("FISH_VERSION"):
        return "fish"
    if os.environ.get("BASH_VERSION"):
        return "bash"
    return "bash"  # Default to bash


def get_completion_source_path() -> Optional[Path]:
    """Find the completions directory from the package installation.

    Returns:
        Path to completions directory, or None if not found.
    """
    # Try to find completions relative to this module
    module_dir = Path(__file__).parent
    completions_dir = module_dir / "completions"
    if completions_dir.exists():
        return completions_dir

    # Try sibling directory (for development)
    completions_dir = module_dir.parent / "completions"
    if completions_dir.exists():
        return completions_dir

    # Try from package root (src layout)
    completions_dir = module_dir.parent.parent / "completions"
    if completions_dir.exists():
        return completions_dir

    # Try site-packages location
    for path in sys.path:
        completions_dir = Path(path) / "claude_watch" / "completions"
        if completions_dir.exists():
            return completions_dir

    # Try project root (for development when running directly)
    # Go up from src/claude_watch/setup to project root
    project_root = module_dir.parent.parent.parent
    completions_dir = project_root / "completions"
    if completions_dir.exists():
        return completions_dir

    return None


# Shell configuration templates
SHELL_CONFIGS: dict[str, dict] = {
    "bash": {
        "completion_file": "claude-watch.bash",
        "rc_files": [Path.home() / ".bashrc", Path.home() / ".bash_profile"],
        "completion_dir": Path.home() / ".local" / "share" / "bash-completion" / "completions",
        "source_line": lambda path: f'\n# Claude Watch completion\n[ -f "{path}" ] && source "{path}"\n',
    },
    "zsh": {
        "completion_file": "claude-watch.zsh",
        "rc_files": [Path.home() / ".zshrc"],
        "completion_dir": Path.home() / ".zsh" / "completions",
        "source_line": lambda path: f'\n# Claude Watch completion\n[ -f "{path}" ] && source "{path}"\n',
    },
    "fish": {
        "completion_file": "claude-watch.fish",
        "rc_files": [],  # Fish auto-loads from completions dir
        "completion_dir": Path.home() / ".config" / "fish" / "completions",
        "source_line": None,  # Fish doesn't need sourcing
    },
}


def setup_shell_completion(shell: Optional[str] = None) -> bool:
    """Set up shell completion for the user's shell.

    Args:
        shell: Shell name to configure. If None, auto-detects.

    Returns:
        True if setup succeeded, False otherwise.
    """
    if shell is None:
        shell = detect_shell()

    completions_source = get_completion_source_path()

    if not completions_source:
        print(f"{Colors.YELLOW}Could not find completion scripts.{Colors.RESET}")
        print(f"{Colors.DIM}You can manually install from the project's completions/ directory.{Colors.RESET}")
        return False

    config = SHELL_CONFIGS.get(shell)
    if not config:
        print(f"{Colors.YELLOW}Unknown shell: {shell}{Colors.RESET}")
        return False

    source_file = completions_source / config["completion_file"]
    if not source_file.exists():
        print(f"{Colors.YELLOW}Completion file not found: {source_file}{Colors.RESET}")
        return False

    # Strategy: copy to completion directory
    dest_dir = config["completion_dir"]
    dest_file = dest_dir / config["completion_file"]

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, dest_file)
        print(f"{Colors.GREEN}✓ Copied completion to {dest_file}{Colors.RESET}")

        # For bash/zsh, add source line to rc file if not using XDG completion
        if shell in ("bash", "zsh") and config["source_line"]:
            # Check if bash-completion is available (auto-loads from dir)
            bash_completion_dir = Path("/usr/share/bash-completion/completions")
            if shell == "bash" and bash_completion_dir.exists():
                # User might have bash-completion installed, which auto-loads
                alt_dest = bash_completion_dir / "claude-watch"
                if os.access(str(bash_completion_dir), os.W_OK):
                    shutil.copy2(source_file, alt_dest)
                    print(f"{Colors.DIM}Also copied to system completions: {alt_dest}{Colors.RESET}")
                    return True

            # Add source line to rc file
            for rc_file in config["rc_files"]:
                if rc_file.exists():
                    content = rc_file.read_text()
                    if "claude-watch" not in content.lower() and "Claude Watch" not in content:
                        source_line = config["source_line"](dest_file)
                        with open(rc_file, "a") as f:
                            f.write(source_line)
                        print(f"{Colors.GREEN}✓ Added source line to {rc_file}{Colors.RESET}")
                    else:
                        print(f"{Colors.DIM}Completion already configured in {rc_file}{Colors.RESET}")
                    break

        print(f"{Colors.DIM}Restart your shell or run: source {dest_file}{Colors.RESET}")
        return True

    except PermissionError:
        print(f"{Colors.YELLOW}Permission denied writing to {dest_dir}{Colors.RESET}")
        print(f"{Colors.DIM}You can manually copy {source_file} to your completions directory.{Colors.RESET}")
        return False
    except Exception as e:
        print(f"{Colors.RED}Error setting up completion: {e}{Colors.RESET}")
        return False


__all__ = [
    "detect_shell",
    "get_completion_source_path",
    "setup_shell_completion",
    "SHELL_CONFIGS",
]
