#!/bin/bash
# ============================================================
# KooD3plot Unified Installer (Linux/macOS)
# ============================================================
# Builds C++ unified_analyzer + Python koo_deep_report into
# a single, self-contained install directory.
#
# Usage:
#   ./install.sh                     # Full build + install
#   ./install.sh --prefix=/opt/koo   # Custom install path
#   ./install.sh --update            # Rebuild only changed files
#   ./install.sh --clean             # Clean + full rebuild
#   ./install.sh --python-only       # Skip C++ build (Python only)
#   ./install.sh --cpp-only          # Skip Python packaging
#
# After install:
#   source <prefix>/activate.sh      # Set up PATH/PYTHONPATH
#   koo_deep_report <d3plot_path>    # Run single analysis
#   koo_deep_report batch <dir>      # Run batch analysis
# ============================================================

set -e

# ============================================================
# Defaults
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${SCRIPT_DIR}/dist"
BUILD_DIR="${SCRIPT_DIR}/build"
BUILD_TYPE="Release"
JOBS=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
CLEAN=false
UPDATE=false
CPP_BUILD=true
PY_BUILD=true

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $1"; }
ok()   { echo -e "${GREEN}  ✓${NC} $1"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $1"; }
err()  { echo -e "${RED}  ✗${NC} $1"; }

# ============================================================
# Parse arguments
# ============================================================
for arg in "$@"; do
    case $arg in
        --prefix=*)    PREFIX="${arg#*=}" ;;
        --build-type=*) BUILD_TYPE="${arg#*=}" ;;
        --jobs=*)      JOBS="${arg#*=}" ;;
        --clean)       CLEAN=true ;;
        --update)      UPDATE=true ;;
        --python-only) CPP_BUILD=false ;;
        --cpp-only)    PY_BUILD=false ;;
        --help|-h)
            head -22 "$0" | tail -18
            exit 0 ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

echo -e "${BLUE}"
echo "============================================================"
echo " KooD3plot Unified Installer"
echo "============================================================"
echo -e "${NC}"
echo "  Source:    ${SCRIPT_DIR}"
echo "  Install:   ${PREFIX}"
echo "  Build:     ${BUILD_TYPE} (${JOBS} jobs)"
echo "  C++ build: ${CPP_BUILD}"
echo "  Python:    ${PY_BUILD}"
echo ""

# ============================================================
# Prerequisites check
# ============================================================
log "Checking prerequisites..."

if ! command -v cmake &>/dev/null; then
    err "CMake not found (required). Install with: sudo apt install cmake"
    exit 1
fi
ok "CMake $(cmake --version | head -1 | cut -d' ' -f3)"

if command -v g++ &>/dev/null; then
    ok "g++ $(g++ -dumpversion)"
elif command -v clang++ &>/dev/null; then
    ok "clang++ $(clang++ --version | head -1)"
else
    err "No C++ compiler found"; exit 1
fi

if command -v python3 &>/dev/null; then
    ok "Python $(python3 --version | cut -d' ' -f2)"
else
    warn "Python3 not found — skipping Python packaging"
    PY_BUILD=false
fi

if command -v ffmpeg &>/dev/null; then
    ok "ffmpeg found (for MP4 encoding)"
else
    warn "ffmpeg not found — section view MP4 encoding will fail at runtime"
fi

# Check libpng for section render
if pkg-config --exists libpng 2>/dev/null || ldconfig -p 2>/dev/null | grep -q libpng; then
    ok "libpng found (section view renderer)"
    SECTION_RENDER=ON
else
    warn "libpng not found — section view renderer disabled"
    SECTION_RENDER=OFF
fi

echo ""

# ============================================================
# Clean if requested
# ============================================================
if [ "$CLEAN" = true ]; then
    log "Cleaning build directory..."
    rm -rf "${BUILD_DIR}"
    rm -rf "${PREFIX}"
    ok "Cleaned"
    echo ""
fi

# ============================================================
# C++ Build
# ============================================================
if [ "$CPP_BUILD" = true ]; then
    log "Configuring CMake..."
    mkdir -p "${BUILD_DIR}"

    cmake -B "${BUILD_DIR}" -S "${SCRIPT_DIR}" \
        -DCMAKE_BUILD_TYPE="${BUILD_TYPE}" \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DKOOD3PLOT_BUILD_TESTS=OFF \
        -DKOOD3PLOT_BUILD_EXAMPLES=ON \
        -DKOOD3PLOT_BUILD_V4_RENDER=ON \
        -DKOOD3PLOT_BUILD_SECTION_RENDER=${SECTION_RENDER} \
        -DKOOD3PLOT_BUILD_CAPI=OFF \
        -DKOOD3PLOT_ENABLE_OPENMP=ON \
        > "${BUILD_DIR}/cmake_config.log" 2>&1

    ok "CMake configured"

    log "Building C++ (${JOBS} jobs)..."
    cmake --build "${BUILD_DIR}" -j"${JOBS}" -- unified_analyzer 2>&1 | tail -5

    ok "unified_analyzer built"

    # Install unified_analyzer binary
    log "Installing C++ binaries..."
    mkdir -p "${PREFIX}/bin"
    cp "${BUILD_DIR}/examples/unified_analyzer" "${PREFIX}/bin/"
    chmod +x "${PREFIX}/bin/unified_analyzer"
    ok "unified_analyzer → ${PREFIX}/bin/"

    echo ""
fi

# ============================================================
# Python packaging
# ============================================================
if [ "$PY_BUILD" = true ]; then
    log "Installing Python package (koo_deep_report)..."

    PY_SRC="${SCRIPT_DIR}/python/koo_deep_report"
    PY_DEST="${PREFIX}/python/koo_deep_report"

    # Copy Python package
    mkdir -p "${PY_DEST}"
    cp -r "${PY_SRC}/koo_deep_report" "${PY_DEST}/"
    cp "${PY_SRC}/pyproject.toml" "${PY_DEST}/" 2>/dev/null || true

    ok "Python package copied"

    # Create wrapper script
    cat > "${PREFIX}/bin/koo_deep_report" << 'WRAPPER'
#!/bin/bash
# KooD3plot Deep Report wrapper
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
export PYTHONPATH="${INSTALL_DIR}/python/koo_deep_report:${PYTHONPATH}"
export PATH="${INSTALL_DIR}/bin:${PATH}"
exec python3 -m koo_deep_report "$@"
WRAPPER
    chmod +x "${PREFIX}/bin/koo_deep_report"

    ok "koo_deep_report CLI wrapper created"
    echo ""
fi

# ============================================================
# Create activation script
# ============================================================
log "Creating activation script..."

cat > "${PREFIX}/activate.sh" << ACTIVATE
#!/bin/bash
# Source this file to set up KooD3plot environment
# Usage: source ${PREFIX}/activate.sh

export KOOD3PLOT_HOME="${PREFIX}"
export PATH="${PREFIX}/bin:\${PATH}"
export PYTHONPATH="${PREFIX}/python/koo_deep_report:\${PYTHONPATH}"

echo "KooD3plot environment activated"
echo "  KOOD3PLOT_HOME=${PREFIX}"
echo "  unified_analyzer: \$(which unified_analyzer 2>/dev/null || echo 'not in PATH')"
echo "  koo_deep_report:  \$(which koo_deep_report 2>/dev/null || echo 'not in PATH')"
ACTIVATE
chmod +x "${PREFIX}/activate.sh"

ok "activate.sh created"

# ============================================================
# Create update script (in install dir)
# ============================================================
log "Creating update script..."

cat > "${PREFIX}/update.sh" << UPDATE
#!/bin/bash
# Quick update: pulls latest code and rebuilds
# Usage: ./update.sh
set -e
SOURCE_DIR="${SCRIPT_DIR}"
echo "Updating from: \${SOURCE_DIR}"

# Pull latest (if git repo)
if [ -d "\${SOURCE_DIR}/.git" ]; then
    echo "Pulling latest changes..."
    cd "\${SOURCE_DIR}" && git pull --ff-only 2>/dev/null || echo "(git pull skipped)"
fi

# Rebuild
echo "Rebuilding..."
cd "\${SOURCE_DIR}"
exec ./install.sh --prefix="${PREFIX}" --update
UPDATE
chmod +x "${PREFIX}/update.sh"

ok "update.sh created"
echo ""

# ============================================================
# Version info
# ============================================================
VERSION_FILE="${PREFIX}/version.txt"
echo "build_date: $(date -Iseconds)" > "${VERSION_FILE}"
echo "build_type: ${BUILD_TYPE}" >> "${VERSION_FILE}"
echo "git_commit: $(cd "${SCRIPT_DIR}" && git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" >> "${VERSION_FILE}"
echo "git_branch: $(cd "${SCRIPT_DIR}" && git branch --show-current 2>/dev/null || echo 'unknown')" >> "${VERSION_FILE}"
echo "platform: $(uname -s)-$(uname -m)" >> "${VERSION_FILE}"

# ============================================================
# Summary
# ============================================================
echo -e "${BLUE}"
echo "============================================================"
echo " Installation Complete!"
echo "============================================================"
echo -e "${NC}"
echo "  Install directory: ${PREFIX}"
echo ""

if [ -f "${PREFIX}/bin/unified_analyzer" ]; then
    UA_SIZE=$(du -sh "${PREFIX}/bin/unified_analyzer" | cut -f1)
    echo "  C++ binary:"
    echo "    ${PREFIX}/bin/unified_analyzer (${UA_SIZE})"
fi

if [ -f "${PREFIX}/bin/koo_deep_report" ]; then
    echo ""
    echo "  Python CLI:"
    echo "    ${PREFIX}/bin/koo_deep_report"
fi

echo ""
echo "  Quick start:"
echo "    source ${PREFIX}/activate.sh"
echo "    koo_deep_report <d3plot_path>"
echo "    koo_deep_report batch <directory>"
echo ""
echo "  Update:"
echo "    ${PREFIX}/update.sh"
echo "    # or: ./install.sh --prefix=${PREFIX} --update"
echo ""
