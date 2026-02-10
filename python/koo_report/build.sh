#!/bin/bash
# Build koo_report as a standalone binary using Nuitka
# Output: ../../installed/bin/koo_report
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INSTALL_DIR="$PROJECT_ROOT/installed/bin"

echo "=========================================="
echo "Building KooReport"
echo "=========================================="

# Ensure dependencies
pip install --quiet rich nuitka ordered-set 2>/dev/null || pip install --quiet --user rich nuitka ordered-set

# Build with Nuitka
echo "Compiling with Nuitka..."
cd "$SCRIPT_DIR"

python3 -m nuitka \
    --standalone \
    --onefile \
    --output-filename=koo_report \
    --output-dir="$SCRIPT_DIR/dist" \
    --assume-yes-for-download \
    --follow-imports \
    --include-package=koo_report \
    --include-package=rich \
    main.py

# Install
echo "Installing to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/dist/koo_report" "$INSTALL_DIR/koo_report"
chmod +x "$INSTALL_DIR/koo_report"

echo ""
echo "=========================================="
echo "Build complete: $INSTALL_DIR/koo_report"
echo "=========================================="
echo ""
echo "Usage:"
echo "  koo_report --test-dir /data/Tests/Test_001_Full26_1Step"
echo "  koo_report --test-dir /data/Tests/Test_001_Full26_1Step --yield-stress 250"
