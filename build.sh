#!/bin/bash
# ============================================================
# KooD3plot Build Script
# ============================================================
# Usage:
#   ./build.sh              # Release build + install
#   ./build.sh debug        # Debug build + install
#   ./build.sh clean        # Clean build directory
#   ./build.sh rebuild      # Clean + Release build + install
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
INSTALL_DIR="${SCRIPT_DIR}/installed"
BUILD_TYPE="Release"
NUM_JOBS=$(nproc 2>/dev/null || echo 4)

# Parse arguments
case "$1" in
    debug)
        BUILD_TYPE="Debug"
        ;;
    clean)
        echo "Cleaning build directory..."
        rm -rf "${BUILD_DIR}"
        echo "Done."
        exit 0
        ;;
    rebuild)
        echo "Cleaning build directory..."
        rm -rf "${BUILD_DIR}"
        ;;
esac

echo "============================================================"
echo "KooD3plot Build Script"
echo "============================================================"
echo "Build type: ${BUILD_TYPE}"
echo "Build dir:  ${BUILD_DIR}"
echo "Install dir: ${INSTALL_DIR}"
echo "Jobs: ${NUM_JOBS}"
echo "============================================================"

# Configure
echo ""
echo "[1/3] Configuring CMake..."
cmake -B "${BUILD_DIR}" \
    -DCMAKE_BUILD_TYPE="${BUILD_TYPE}" \
    -DKOOD3PLOT_BUILD_CAPI=OFF \
    "${SCRIPT_DIR}"

# Build
echo ""
echo "[2/3] Building..."
cmake --build "${BUILD_DIR}" -j"${NUM_JOBS}"

# Install
echo ""
echo "[3/3] Installing to ${INSTALL_DIR}..."
cmake --install "${BUILD_DIR}" --prefix "${INSTALL_DIR}"

echo ""
echo "============================================================"
echo "Build complete!"
echo "============================================================"
echo ""
echo "Installed binaries:"
ls -la "${INSTALL_DIR}/bin/" 2>/dev/null | grep -E "^-" | awk '{print "  " $NF}'
echo ""
echo "Usage:"
echo "  ${INSTALL_DIR}/bin/unified_analyzer --config <config.yaml>"
echo "  ${INSTALL_DIR}/bin/kood3plot_cli --mode query -q von_mises <d3plot>"
echo ""
