#!/data/data/com.termux/files/usr/bin/bash
set -e

REPO="moradgamer802-cell/voxel-v2"
INSTALL_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/voxel"

echo "================================"
echo "   VOXEL Installer for Termux"
echo "================================"
echo ""

# Check if running on Termux
if [ ! -d "/data/data/com.termux" ]; then
    echo "Warning: This installer is designed for Termux on Android."
    echo "Continue anyway? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install dependencies
echo "[1/4] Installing dependencies..."
pkg update -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold > /dev/null 2>&1 || true
pkg install -y python python-pip git termux-api > /dev/null 2>&1 || true

# Install Python packages
echo "[2/4] Installing Python packages..."
pip install --upgrade pip --quiet 2>/dev/null || pip install --upgrade pip
pip install click rich requests textual tiktoken --quiet 2>/dev/null || pip install click rich requests textual tiktoken

# Create directories
echo "[3/4] Setting up directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$CONFIG_DIR/chats"
mkdir -p "$CONFIG_DIR/commands"

# Download VOXEL
echo "[4/4] Installing VOXEL..."
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Download the repository
if command -v git >/dev/null 2>&1; then
    git clone --depth 1 https://github.com/$REPO.git voxel > /dev/null 2>&1 || {
        echo "Git clone failed, trying direct download..."
        curl -fsSL "https://github.com/$REPO/archive/refs/heads/master.tar.gz" | tar -xz
        mv voxel-master voxel
    }
else
    curl -fsSL "https://github.com/$REPO/archive/refs/heads/master.tar.gz" | tar -xz
    mv voxel-master voxel
fi

# Install
cp voxel/voxel "$INSTALL_DIR/voxel"
chmod +x "$INSTALL_DIR/voxel"

# Install Python package
cd voxel
pip install -e . --quiet 2>/dev/null || pip install -e .

# Create initial config if not exists
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    python -m voxel.cli setup > /dev/null 2>&1 || true
fi

# Cleanup
cd /
rm -rf "$TEMP_DIR"

echo ""
echo "✓ VOXEL installed successfully!"
echo ""
echo "Default model: deepseek-v4-flash-free (free, no API key needed)"
echo "Default provider: opencode.ai/zen/v1"
echo ""
echo "Next steps:"
echo "  1. Run: source ~/.bashrc   (or open new Termux session)"
echo "  2. Run: voxel chat"
echo ""
echo "Or run directly:"
echo "  $INSTALL_DIR/voxel chat"
echo ""
