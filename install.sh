#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "================================"
echo "   VOXEL Installer for Termux"
echo "================================"
echo ""

pkg update -y
pkg install -y python python-pip git termux-api

pip install --upgrade pip
pip install click rich requests textual tiktoken

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.local/bin
cp "$SCRIPT_DIR/voxel" ~/.local/bin/voxel 2>/dev/null || true
chmod +x "$SCRIPT_DIR/voxel"

echo ""
echo "✓ VOXEL installed!"
echo ""
echo "Next steps:"
echo "  voxel setup"
echo "  voxel chat"
