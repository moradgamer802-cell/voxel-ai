#!/bin/bash
# VOXEL AI - Termux Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/moradgamer802-cell/voxel-ai/main/install.sh | bash

REPO="moradgamer802-cell/voxel-ai"
BRANCH="main"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH"
BOT_DIR="$HOME/voxel-ai"
RC_FILE="$HOME/.bashrc"

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
CYN='\033[0;36m'
RST='\033[0m'

echo ""
echo -e "${CYN}◆  VOXEL AI Installer${RST}"
echo -e "${CYN}────────────────────────────────────${RST}"

# ── Step 1: Python ────────────────────────────────────────────────
echo -e "\n${YLW}[1/3] Python check...${RST}"
if command -v python3 >/dev/null 2>&1; then
    echo -e "${GRN}✓ Python found: $(python3 --version 2>&1)${RST}"
else
    echo "  Python nai — install kortesi..."
    if command -v pkg >/dev/null 2>&1; then
        pkg update -y 2>/dev/null || true
        if ! pkg install -y python; then
            echo -e "${RED}✗ Python install fail! Manually try: pkg install python${RST}"
            exit 1
        fi
    else
        echo -e "${RED}✗ Termux 'pkg' command pawa jacche na.${RST}"
        echo "  Termux e acho? F-Droid theke Termux install koro: https://f-droid.org"
        exit 1
    fi
fi

# ── Step 2: Download ──────────────────────────────────────────────
echo -e "\n${YLW}[2/3] Downloading VOXEL AI...${RST}"
mkdir -p "$BOT_DIR"

DOWNLOAD_OK=0
if command -v curl >/dev/null 2>&1; then
    if curl -fsSL "$RAW/voxel.py" -o "$BOT_DIR/voxel.py" 2>/dev/null; then
        DOWNLOAD_OK=1
    fi
fi

if [ "$DOWNLOAD_OK" -eq 0 ] && command -v wget >/dev/null 2>&1; then
    echo "  curl kaj koreni, wget try kortesi..."
    if wget -q "$RAW/voxel.py" -O "$BOT_DIR/voxel.py" 2>/dev/null; then
        DOWNLOAD_OK=1
    fi
fi

if [ "$DOWNLOAD_OK" -eq 0 ]; then
    echo -e "${RED}✗ Download fail!${RST}"
    echo "  Check koro:"
    echo "   1. Internet connection ache?"
    echo "   2. curl installed? (pkg install curl)"
    echo "   3. GitHub accessible?"
    exit 1
fi

# file size check — kono corrupted/empty file na
FSIZE=$(wc -c < "$BOT_DIR/voxel.py" 2>/dev/null || echo 0)
if [ "$FSIZE" -lt 40000 ]; then
    echo -e "${RED}✗ Download incomplete (file too small: ${FSIZE} bytes). Abar try koro.${RST}"
    rm -f "$BOT_DIR/voxel.py"
    exit 1
fi

chmod +x "$BOT_DIR/voxel.py"
echo -e "${GRN}✓ Downloaded: $BOT_DIR/voxel.py (${FSIZE} bytes)${RST}"

# legacy shim so old aliases pointing at bangbot.py keep working
if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$RAW/bangbot.py" -o "$BOT_DIR/bangbot.py" 2>/dev/null || true
elif command -v wget >/dev/null 2>&1; then
    wget -q "$RAW/bangbot.py" -O "$BOT_DIR/bangbot.py" 2>/dev/null || true
fi

# ── Step 3: Shell alias ───────────────────────────────────────────
echo -e "\n${YLW}[3/3] Setting up 'voxel' command...${RST}"
ALIAS_LINE="alias voxel='python3 $BOT_DIR/voxel.py'"

# .bashrc create koro jodi na thake
touch "$RC_FILE"

if grep -q "alias voxel=" "$RC_FILE" 2>/dev/null; then
    # update existing alias
    sed -i "s|^alias voxel=.*|$ALIAS_LINE|" "$RC_FILE"
    echo -e "${GRN}✓ 'voxel' alias updated in $RC_FILE${RST}"
else
    echo "" >> "$RC_FILE"
    echo "# VOXEL AI" >> "$RC_FILE"
    echo "$ALIAS_LINE" >> "$RC_FILE"
    echo -e "${GRN}✓ 'voxel' alias added to $RC_FILE${RST}"
fi

# current session e o kaj korbe jeno
eval "$ALIAS_LINE" 2>/dev/null || true

# ── Done ─────────────────────────────────────────────────────────
echo ""
echo -e "${CYN}────────────────────────────────────${RST}"
echo -e "${GRN}◆  INSTALL DONE!${RST}"
echo -e "${CYN}────────────────────────────────────${RST}"
echo ""
echo -e "  Start:   ${GRN}voxel${RST}"
echo -e "  (notu terminal hole: ${YLW}source ~/.bashrc${RST})"
echo -e "  Help:    /help"
echo -e "  Update:  same installer abar chalao"
echo ""
