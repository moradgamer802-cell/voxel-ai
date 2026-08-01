#!/data/data/com.termux/files/usr/bin/bash
# VOXEL AI - one-line installer for Termux
# Usage: curl -fsSL https://raw.githubusercontent.com/moradgamer802-cell/voxel-ai/main/install.sh | bash
set -e

REPO="moradgamer802-cell/voxel-ai"
BRANCH="main"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH"
BOT_DIR="$HOME/voxel-ai"

echo "=== VOXEL AI installer ==="
echo "[1/3] Checking Python..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python install kortesi (first time dorkar, 2-3 minute lagte pare)..."
    pkg update -y >/dev/null 2>&1 || true
    pkg install -y python
fi
echo "Python OK: $(python3 --version)"

echo "[2/3] Downloading VOXEL AI..."
mkdir -p "$BOT_DIR"
if ! curl -fsSL "$RAW/bangbot.py" -o "$BOT_DIR/bangbot.py"; then
    echo "Download fail! Internet check koro ar abar try koro."
    exit 1
fi
chmod +x "$BOT_DIR/bangbot.py"
echo "Downloaded: $BOT_DIR/bangbot.py"

echo "[3/3] Adding 'voxel' command..."
RC_FILE="$HOME/.bashrc"
ALIAS_LINE="alias voxel='python3 $BOT_DIR/bangbot.py'"
if grep -q "alias voxel=" "$RC_FILE" 2>/dev/null; then
    sed -i "s|^alias voxel=.*|$ALIAS_LINE|" "$RC_FILE"
else
    echo "$ALIAS_LINE" >> "$RC_FILE"
fi

echo
echo "======================================"
echo "  INSTALL DONE!"
echo "======================================"
echo "  Run:     voxel"
echo "  (new terminal hole: source ~/.bashrc)"
echo "  Help:    /help"
echo "  Update:  same installer abar chalao"
echo "======================================"
