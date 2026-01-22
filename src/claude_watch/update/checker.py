"""Update checking and installation for claude-watch.

Provides functions for checking for updates, comparing versions,
detecting installation methods, and running upgrades.
"""

import json
import re
import subprocess
import sys
from typing import Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from claude_watch.display.colors import Colors

# GitHub repository information
GITHUB_REPO = "Asi0Flammeus/claude-code-watch"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse_version(version_str: str) -> Tuple[int, int, int, str]:
    """Parse semantic version string into comparable tuple.

    Args:
        version_str: Version string (e.g., "0.2.4", "1.0.0-beta.1").

    Returns:
        (major, minor, patch, prerelease) where prerelease is empty string
        for stable releases or the prerelease suffix (e.g., 'alpha.1', 'beta.2').
    """
    # Match semantic version with optional prerelease
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", version_str.strip())
    if not match:
        return (0, 0, 0, version_str)  # Fallback for unparseable versions

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    prerelease = match.group(4) or ""
    return (major, minor, patch, prerelease)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings.

    Args:
        v1: First version string.
        v2: Second version string.

    Returns:
        -1 if v1 < v2
         0 if v1 == v2
         1 if v1 > v2
    """
    p1 = parse_version(v1)
    p2 = parse_version(v2)

    # Compare major, minor, patch
    for i in range(3):
        if p1[i] < p2[i]:
            return -1
        if p1[i] > p2[i]:
            return 1

    # If same major.minor.patch, compare prerelease
    # No prerelease (stable) > any prerelease
    if not p1[3] and p2[3]:
        return 1  # v1 is stable, v2 is prerelease
    if p1[3] and not p2[3]:
        return -1  # v1 is prerelease, v2 is stable
    if p1[3] < p2[3]:
        return -1
    if p1[3] > p2[3]:
        return 1

    return 0


def detect_installation_method() -> Tuple[Optional[str], Optional[str]]:
    """Detect how claude-watch was installed.

    Returns:
        Tuple of (method, source_path) where:
        - method: 'uv-editable', 'uv', 'pipx', 'pip', or None
        - source_path: Local path for editable installs, None otherwise
    """
    # Check for uv tool installation
    try:
        result = subprocess.run(
            ["uv", "tool", "list", "--show-paths"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and "claude-watch" in result.stdout:
            # Check if it's an editable install by looking at the source
            # uv tool list --show-paths shows the venv path
            # We need to check if installed from local path
            for line in result.stdout.splitlines():
                if "claude-watch" in line:
                    # Check pip show in uv tool venv for editable location
                    try:
                        pip_result = subprocess.run(
                            ["pip", "show", "claude-watch"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                            env={**subprocess.os.environ, "PATH": subprocess.os.environ.get("PATH", "")},
                        )
                        if pip_result.returncode == 0:
                            for pip_line in pip_result.stdout.splitlines():
                                if pip_line.startswith("Editable project location:"):
                                    path = pip_line.split(":", 1)[1].strip()
                                    return ("uv-editable", path)
                                if pip_line.startswith("Location:") and "asi0-repos" in pip_line:
                                    # Installed from local but check for editable marker
                                    pass
                    except (subprocess.SubprocessError, FileNotFoundError, OSError):
                        pass

                    # Also check via importlib for editable installs
                    try:
                        import importlib.util
                        spec = importlib.util.find_spec("claude_watch")
                        if spec and spec.origin:
                            origin = str(spec.origin)
                            # If origin is in a repos/project directory, it's editable
                            if "/asi0-repos/" in origin or "/src/claude_watch/" in origin:
                                # Extract the project root
                                if "/src/claude_watch/" in origin:
                                    project_root = origin.split("/src/claude_watch/")[0]
                                    return ("uv-editable", project_root)
                    except (ImportError, AttributeError):
                        pass

                    return ("uv", None)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    # Check for pipx installation
    try:
        result = subprocess.run(
            ["pipx", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and "claude-watch" in result.stdout:
            return ("pipx", None)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    # Check if installed via pip (in site-packages)
    try:
        import importlib.util
        spec = importlib.util.find_spec("claude_watch")
        if spec and spec.origin:
            origin = str(spec.origin)
            if "site-packages" in origin:
                return ("pip", None)
    except (ImportError, AttributeError):
        pass

    return (None, None)


def fetch_latest_version(current_version: str = "0.0.0") -> Optional[str]:
    """Fetch the latest version from GitHub releases.

    Args:
        current_version: Current version for User-Agent header.

    Returns:
        Latest version string (without 'v' prefix), or None if fetch failed.
    """
    req = Request(
        GITHUB_RELEASES_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"claude-watch/{current_version}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            tag_name = data.get("tag_name", "")
            # Remove 'v' prefix if present (e.g., 'v0.1.0' -> '0.1.0')
            if tag_name.startswith("v"):
                tag_name = tag_name[1:]
            return tag_name if tag_name else None
    except (HTTPError, URLError, json.JSONDecodeError, KeyError):
        return None


def run_upgrade(method: str, source_path: Optional[str] = None) -> Tuple[bool, str]:
    """Run the upgrade command for the detected installation method.

    Args:
        method: Installation method ('uv-editable', 'uv', 'pipx', or 'pip')
        source_path: Local path for editable installs

    Returns:
        (success, message) tuple
    """
    github_url = f"git+https://github.com/{GITHUB_REPO}.git"

    # For editable installs, git pull then reinstall
    if method == "uv-editable" and source_path:
        # First, git pull to get latest changes
        try:
            git_result = subprocess.run(
                ["git", "pull"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=source_path,
            )
            if git_result.returncode != 0:
                # Not a git repo or pull failed, try reinstall anyway
                pass
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass

        # Reinstall editable
        cmd = ["uv", "tool", "install", "--force", "--editable", source_path]
    else:
        commands = {
            # uv/pipx remember install source, so upgrade pulls from original git URL
            "uv": ["uv", "tool", "upgrade", "claude-watch"],
            "pipx": ["pipx", "upgrade", "claude-watch"],
            # pip needs explicit URL since it doesn't track source
            "pip": [sys.executable, "-m", "pip", "install", "--upgrade", github_url],
        }
        cmd = commands.get(method)

    if not cmd:
        return False, f"Unknown installation method: {method}"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            if method == "uv-editable":
                return True, f"Successfully reinstalled from {source_path}"
            return True, f"Successfully upgraded via {method}"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            return False, f"Upgrade failed: {error_msg}"
    except subprocess.TimeoutExpired:
        return False, "Upgrade timed out after 120 seconds"
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except subprocess.SubprocessError as e:
        return False, f"Upgrade failed: {e}"


def check_for_update(current_version: str, quiet: bool = False) -> Optional[dict]:
    """Check if an update is available.

    Args:
        current_version: Current installed version.
        quiet: If True, suppress output messages.

    Returns:
        Dict with 'current', 'latest', 'update_available', 'method', 'source_path' keys,
        or None if check failed.
    """
    if not quiet:
        print("Checking for updates...")

    latest = fetch_latest_version(current_version)
    if latest is None:
        if not quiet:
            print(f"{Colors.YELLOW}Could not check for updates (GitHub unreachable or no releases){Colors.RESET}")
        return None

    update_available = compare_versions(current_version, latest) < 0
    method, source_path = detect_installation_method()

    return {
        "current": current_version,
        "latest": latest,
        "update_available": update_available,
        "method": method,
        "source_path": source_path,
    }


def run_update(current_version: str, check_only: bool = False, force: bool = False) -> int:
    """Run the update process.

    Args:
        current_version: Current installed version.
        check_only: If True, only check for updates without installing.
        force: If True, reinstall even if already on latest version (for editable installs).

    Returns:
        Exit code (0 for success, 1 for error, 2 for no update available)
    """
    result = check_for_update(current_version, quiet=False)
    if result is None:
        return 1

    current = result["current"]
    latest = result["latest"]
    update_available = result["update_available"]
    method = result["method"]
    source_path = result.get("source_path")

    print()
    print(f"  Current version: {Colors.CYAN}{current}{Colors.RESET}")
    print(f"  Latest version:  {Colors.CYAN}{latest}{Colors.RESET}")
    if method:
        method_display = method
        if method == "uv-editable" and source_path:
            method_display = f"uv-editable ({source_path})"
        print(f"  Install method:  {Colors.DIM}{method_display}{Colors.RESET}")
    print()

    # For editable installs with force, always proceed
    if force and method == "uv-editable" and source_path:
        print(f"{Colors.CYAN}Force reinstall requested{Colors.RESET}")
        print()
        print(f"Pulling latest changes and reinstalling from {Colors.CYAN}{source_path}{Colors.RESET}...")
        print()

        success, message = run_upgrade(method, source_path)

        if success:
            print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")
            print()
            print(f"Run {Colors.CYAN}claude-watch --version{Colors.RESET} to verify.")
            return 0
        else:
            print(f"{Colors.RED}✗ {message}{Colors.RESET}")
            return 1

    if not update_available:
        print(f"{Colors.GREEN}✓ You are running the latest version{Colors.RESET}")
        if method == "uv-editable" and source_path:
            print()
            print(f"{Colors.DIM}Editable install - to reload local changes:{Colors.RESET}")
            print(f"  {Colors.CYAN}ccw --update force{Colors.RESET}  (git pull + reinstall)")
        return 2

    print(f"{Colors.YELLOW}Update available: {current} → {latest}{Colors.RESET}")
    print()

    if check_only:
        if method:
            print(f"Run {Colors.CYAN}claude-watch --update{Colors.RESET} to update via {method}")
        else:
            print("Installation method not detected. Manual update may be required.")
        return 0

    # Proceed with upgrade
    if method is None:
        print(f"{Colors.YELLOW}Could not detect installation method.{Colors.RESET}")
        print()
        print("Please update manually using one of:")
        print(f"  {Colors.CYAN}uv tool upgrade claude-watch{Colors.RESET}")
        print(f"  {Colors.CYAN}pipx upgrade claude-watch{Colors.RESET}")
        print(f"  {Colors.CYAN}pip install --upgrade claude-watch{Colors.RESET}")
        return 1

    if method == "uv-editable" and source_path:
        print(f"Pulling latest changes and reinstalling from {Colors.CYAN}{source_path}{Colors.RESET}...")
    else:
        print(f"Updating via {Colors.CYAN}{method}{Colors.RESET}...")
    print()

    success, message = run_upgrade(method, source_path)

    if success:
        print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")
        print()
        print(f"Restart your shell or run {Colors.CYAN}claude-watch --version{Colors.RESET} to verify.")
        return 0
    else:
        print(f"{Colors.RED}✗ {message}{Colors.RESET}")
        return 1


__all__ = [
    "GITHUB_REPO",
    "GITHUB_RELEASES_URL",
    "parse_version",
    "compare_versions",
    "detect_installation_method",
    "fetch_latest_version",
    "run_upgrade",
    "check_for_update",
    "run_update",
]
