#!/bin/bash
# Claude Watch Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/Asi0Flammeus/claude-code-watch/main/install.sh | bash
#
# This script installs claude-watch using the best available method:
# 1. uv (fastest, recommended)
# 2. pipx (isolated environment)
# 3. pip (fallback)

set -e

REPO="https://github.com/Asi0Flammeus/claude-code-watch.git"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Installing claude-watch..."
echo

# Check for uv
if command -v uv &> /dev/null; then
    echo -e "${GREEN}Found uv${NC} - using uv tool install (recommended)"
    uv tool install "git+${REPO}"
    echo
    echo -e "${GREEN}✓ Installed successfully!${NC}"
    echo "  Run: ccw --help"
    exit 0
fi

# Check for pipx
if command -v pipx &> /dev/null; then
    echo -e "${GREEN}Found pipx${NC} - using pipx install"
    pipx install "git+${REPO}"
    echo
    echo -e "${GREEN}✓ Installed successfully!${NC}"
    echo "  Run: ccw --help"
    exit 0
fi

# Check for pip
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
else
    echo -e "${RED}Error: No package manager found${NC}"
    echo "Please install one of: uv, pipx, or pip"
    echo
    echo "Recommended: Install uv"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo -e "${YELLOW}Using ${PIP_CMD}${NC} - consider using uv or pipx for isolated install"
echo "  Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
echo

$PIP_CMD install "git+${REPO}"

echo
echo -e "${GREEN}✓ Installed successfully!${NC}"
echo "  Run: ccw --help"
