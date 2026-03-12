#!/bin/bash
# Build koo_deep_report as a standalone binary using PyInstaller
# Output: ../../installed/bin/koo_deep_report
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INSTALL_DIR="$PROJECT_ROOT/installed/bin"

echo "=========================================="
echo "Building KooDeepReport"
echo "=========================================="

# Ensure dependencies
pip install --quiet pyinstaller customtkinter 2>/dev/null || pip install --quiet --user pyinstaller customtkinter

# Build with PyInstaller
echo "Compiling with PyInstaller..."
cd "$SCRIPT_DIR"

pyinstaller \
    --noconfirm \
    --onefile \
    --name koo_deep_report \
    --distpath "$SCRIPT_DIR/dist" \
    koo_deep_report.spec

# Install
echo "Installing to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/dist/koo_deep_report" "$INSTALL_DIR/koo_deep_report"
chmod +x "$INSTALL_DIR/koo_deep_report"

echo ""
echo "=========================================="
echo "Build complete: $INSTALL_DIR/koo_deep_report"
echo "=========================================="
echo ""
echo "Usage:"
echo "  koo_deep_report <d3plot_path> --output <output_dir>"
echo "  koo_deep_report batch <root_dir> --output <output_dir> --threads 4"
