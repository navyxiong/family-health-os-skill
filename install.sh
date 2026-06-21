#!/usr/bin/env bash
#
# Family Health OS — One-line installer for Hermes Agent
# https://github.com/navyxiong/family-health-os-skill
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/navyxiong/family-health-os-skill/main/install.sh | bash
#   curl ... | bash -s -- my-profile-name      # custom profile name
#
set -euo pipefail

# ---- Config ----------------------------------------------------------------

REPO_RAW="https://raw.githubusercontent.com/navyxiong/family-health-os-skill/main"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PROFILE_NAME="${1:-family-health-os}"
TARGET_DIR="$HERMES_HOME/profiles/$PROFILE_NAME"

# ---- Colors ----------------------------------------------------------------

if [ -t 1 ]; then
  BOLD="\033[1m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; RESET="\033[0m"
else
  BOLD=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi

info()  { echo -e "${GREEN}✓${RESET} $*"; }
warn()  { echo -e "${YELLOW}!${RESET} $*"; }
fail()  { echo -e "${RED}✗${RESET} $*" >&2; exit 1; }

# ---- Pre-flight ------------------------------------------------------------

[ -d "$HERMES_HOME" ] || fail "Hermes home not found at $HERMES_HOME. Install Hermes Agent first: https://hermes-agent.nousresearch.com/docs"

command -v python3 >/dev/null 2>&1 || fail "python3 not found. Install Python 3.10+."
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  fail "Python $PY_VERSION detected. Need Python 3.10+."
fi
info "Python $PY_VERSION"

# ---- Detect install method -------------------------------------------------

TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

if [ -d ".git" ] && [ -f "skills/productivity/family-health-os/SKILL.md" ]; then
  # Local checkout
  info "Detected local checkout, installing from current directory"
  SRC_DIR="."
elif [ -d "skills/productivity/family-health-os/SKILL.md" ]; then
  SRC_DIR="."
else
  # Download tarball
  info "Downloading skill from GitHub..."
  TARBALL_URL="$REPO_RAW/family-health-os-skill.tar.gz"
  if ! curl -fsSL "$TARBALL_URL" -o "$TMP_DIR/skill.tar.gz" 2>/dev/null; then
    warn "Pre-built tarball not found, falling back to sparse checkout"
    git clone --depth 1 --filter=blob:none --sparse \
      "https://github.com/navyxiong/family-health-os-skill.git" \
      "$TMP_DIR/repo" >/dev/null 2>&1
    (cd "$TMP_DIR/repo" && git sparse-checkout set skills) >/dev/null 2>&1
    SRC_DIR="$TMP_DIR/repo"
  else
    tar -xzf "$TMP_DIR/skill.tar.gz" -C "$TMP_DIR"
    SRC_DIR="$TMP_DIR/family-health-os-skill"
  fi
fi

# ---- Install ----------------------------------------------------------------

info "Installing to $TARGET_DIR"
mkdir -p "$TARGET_DIR/skills/productivity"
mkdir -p "$TARGET_DIR/memory/data"
mkdir -p "$TARGET_DIR/memory/schemas"

if [ -d "$SRC_DIR/skills/productivity/family-health-os" ]; then
  cp -R "$SRC_DIR/skills/productivity/family-health-os" \
        "$TARGET_DIR/skills/productivity/"
else
  fail "Source skill not found. Did you run from the repo root?"
fi

# Ensure empty data dirs survive git
touch "$TARGET_DIR/memory/data/.gitkeep"
touch "$TARGET_DIR/memory/schemas/.gitkeep"

# ---- Verify -----------------------------------------------------------------

SKILL_FILE="$TARGET_DIR/skills/productivity/family-health-os/SKILL.md"
[ -f "$SKILL_FILE" ] || fail "Install failed: SKILL.md missing at $SKILL_FILE"

# Quick smoke test
info "Running smoke test..."
(cd "$TARGET_DIR/skills/productivity/family-health-os" && \
  python3 scripts/smoke_test.py --quick 2>&1) | tail -5 || \
  warn "Smoke test failed — the skill is installed but may need attention."

# ---- Activate ---------------------------------------------------------------

if command -v hermes >/dev/null 2>&1; then
  info "Activating profile '$PROFILE_NAME'..."
  hermes profile use "$PROFILE_NAME" 2>/dev/null || \
    warn "Could not auto-activate. Run manually: hermes profile use $PROFILE_NAME"
else
  warn "hermes CLI not on PATH. After installing Hermes, run: hermes profile use $PROFILE_NAME"
fi

# ---- Done -------------------------------------------------------------------

echo
echo -e "${BOLD}${GREEN}🎉 Family Health OS installed successfully!${RESET}"
echo
echo "  Profile:    $PROFILE_NAME"
echo "  Location:   $TARGET_DIR"
echo "  Skill file: $SKILL_FILE"
echo
echo -e "${BOLD}Next step:${RESET} Tell your agent:"
echo
echo -e "  ${YELLOW}\"给奶奶建一份档案：姓名王建国，男，1948年5月30日出生\"${RESET}"
echo
echo "The agent will log it and reply:"
echo
echo -e "  ${GREEN}已录入。患者档案 | 王建国 | 1事件${RESET}"
echo
