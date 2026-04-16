#!/bin/bash
# ============================================================
# build_module.sh — KooD3plotReader 통합 후처리 모듈 빌드
# ============================================================
# Apptainer 이미지에 포함할 self-contained 모듈을 빌드합니다.
# 결과: <prefix>/ 디렉토리에 모든 바이너리 + Python 패키지 + 스크립트
#
# 사용법:
#   ./scripts/build_module.sh                          # 기본 (./module/)
#   ./scripts/build_module.sh --prefix /opt/kood3plot  # 커스텀 경로
#   ./scripts/build_module.sh --no-viewer              # 뷰어 제외 (headless)
#   ./scripts/build_module.sh --nuitka                 # Python→standalone exe (Python 불필요)
#   ./scripts/build_module.sh --with-lsprepost <path>  # LSPrePost 포함
#
# Apptainer def 파일에서:
#   %post
#     cd /opt/KooD3plotReader
#     ./scripts/build_module.sh --prefix /opt/kood3plot --no-viewer
#
# 결과 구조:
#   <prefix>/
#   ├── bin/
#   │   ├── unified_analyzer          # C++ 분석 엔진
#   │   ├── koo_viewer                # GUI 뷰어 (--no-viewer 시 제외)
#   │   ├── koo_deep_report           # Python CLI wrapper
#   │   ├── koo_sphere_report         # Python CLI wrapper
#   │   └── post_analyze              # 통합 오케스트레이션
#   ├── python/
#   │   ├── koo_deep_report/          # Python 패키지 소스
#   │   └── koo_sphere_report/        # Python 패키지 소스
#   ├── lsprepost/                    # LSPrePost (--with-lsprepost 시)
#   ├── activate.sh                   # source 하면 PATH/PYTHONPATH 설정
#   └── VERSION                       # 버전 정보
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
PREFIX="${PROJECT_ROOT}/module"
BUILD_DIR="${PROJECT_ROOT}/build"
BUILD_TYPE="Release"
JOBS=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
BUILD_VIEWER=true
BUILD_NUITKA=false
LSPREPOST_SRC=""

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $1"; }
ok()   { echo -e "${GREEN}  ✓${NC} $1"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $1"; }
err()  { echo -e "${RED}  ✗${NC} $1"; }

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --prefix)          PREFIX="$2"; shift 2 ;;
        --jobs)            JOBS="$2"; shift 2 ;;
        --build-type)      BUILD_TYPE="$2"; shift 2 ;;
        --no-viewer)       BUILD_VIEWER=false; shift ;;
        --nuitka)          BUILD_NUITKA=true; shift ;;
        --with-lsprepost)  LSPREPOST_SRC="$2"; shift 2 ;;
        --help|-h)
            sed -n '/^# ==/,/^# ==/p' "$0" | sed 's/^# //' | head -35
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo -e "${CYAN}"
echo "============================================================"
echo " KooD3plotReader Module Builder"
echo "============================================================"
echo -e "${NC}"
echo "  Source:     ${PROJECT_ROOT}"
echo "  Prefix:     ${PREFIX}"
echo "  Build:      ${BUILD_TYPE} (${JOBS} jobs)"
echo "  Viewer:     ${BUILD_VIEWER}"
echo "  Nuitka:     ${BUILD_NUITKA}"
echo "  LSPrePost:  ${LSPREPOST_SRC:-(not included)}"
echo ""

# ============================================================
# Prerequisites
# ============================================================
log "Checking prerequisites..."

command -v cmake  &>/dev/null && ok "cmake $(cmake --version | head -1 | cut -d' ' -f3)" \
    || { err "cmake not found"; exit 1; }
command -v g++    &>/dev/null && ok "g++ $(g++ -dumpversion)" \
    || { err "g++ not found"; exit 1; }
command -v python3 &>/dev/null && ok "python3 $(python3 --version | cut -d' ' -f2)" \
    || { err "python3 not found"; exit 1; }
command -v ffmpeg &>/dev/null && ok "ffmpeg found" \
    || warn "ffmpeg not found — section view MP4 re-encode will fail"

# Check libpng for section render
SECTION_RENDER=OFF
if pkg-config --exists libpng 2>/dev/null || ldconfig -p 2>/dev/null | grep -q libpng; then
    ok "libpng found"
    SECTION_RENDER=ON
else
    warn "libpng not found — software section renderer disabled"
fi

# Check Xvfb for LSPrePost batch
if command -v Xvfb &>/dev/null; then
    ok "Xvfb found (LSPrePost batch rendering)"
else
    warn "Xvfb not found — LSPrePost rendering unavailable"
fi

echo ""

# ============================================================
# C++ Build
# ============================================================
log "Configuring CMake..."

CMAKE_OPTS=(
    -DCMAKE_BUILD_TYPE="${BUILD_TYPE}"
    -DCMAKE_INSTALL_PREFIX="${PREFIX}"
    -DKOOD3PLOT_BUILD_V4_RENDER=ON
    -DKOOD3PLOT_BUILD_SECTION_RENDER=${SECTION_RENDER}
    -DKOOD3PLOT_ENABLE_OPENMP=ON
    -DKOOD3PLOT_BUILD_TESTS=OFF
    -DKOOD3PLOT_BUILD_CAPI=OFF
    -DKOOD3PLOT_BUILD_HDF5=OFF
)

if [ "$BUILD_VIEWER" = true ]; then
    CMAKE_OPTS+=(-DKOOD3PLOT_BUILD_VIEWER=ON)
else
    CMAKE_OPTS+=(-DKOOD3PLOT_BUILD_VIEWER=OFF)
fi

mkdir -p "${BUILD_DIR}"
cmake -B "${BUILD_DIR}" -S "${PROJECT_ROOT}" "${CMAKE_OPTS[@]}" \
    > "${BUILD_DIR}/cmake_config.log" 2>&1
ok "CMake configured"

log "Building C++ (${JOBS} jobs)..."

# Always build unified_analyzer
cmake --build "${BUILD_DIR}" -j"${JOBS}" --target unified_analyzer 2>&1 | tail -3
ok "unified_analyzer built"

if [ "$BUILD_VIEWER" = true ]; then
    cmake --build "${BUILD_DIR}" -j"${JOBS}" --target koo_viewer 2>&1 | tail -3
    ok "koo_viewer built"
fi

echo ""

# ============================================================
# Install to prefix
# ============================================================
log "Installing to ${PREFIX}..."

mkdir -p "${PREFIX}/bin"
mkdir -p "${PREFIX}/python"

# C++ binaries
cp "${BUILD_DIR}/examples/unified_analyzer" "${PREFIX}/bin/"
chmod +x "${PREFIX}/bin/unified_analyzer"
ok "unified_analyzer → bin/"

if [ "$BUILD_VIEWER" = true ] && [ -f "${BUILD_DIR}/viewer/koo_viewer" ]; then
    cp "${BUILD_DIR}/viewer/koo_viewer" "${PREFIX}/bin/"
    chmod +x "${PREFIX}/bin/koo_viewer"
    ok "koo_viewer → bin/"
fi

# Python packages
cp -r "${PROJECT_ROOT}/python/koo_deep_report" "${PREFIX}/python/"
cp -r "${PROJECT_ROOT}/python/koo_sphere_report" "${PREFIX}/python/"
ok "Python packages → python/"

# CLI wrapper: koo_deep_report
cat > "${PREFIX}/bin/koo_deep_report" << 'WRAPPER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
export PYTHONPATH="${MODULE_DIR}/python/koo_deep_report:${MODULE_DIR}/python/koo_sphere_report:${PYTHONPATH:-}"
export PATH="${MODULE_DIR}/bin:${PATH}"
exec python3 -m koo_deep_report "$@"
WRAPPER
chmod +x "${PREFIX}/bin/koo_deep_report"
ok "koo_deep_report wrapper → bin/"

# CLI wrapper: koo_sphere_report
cat > "${PREFIX}/bin/koo_sphere_report" << 'WRAPPER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
export PYTHONPATH="${MODULE_DIR}/python/koo_deep_report:${MODULE_DIR}/python/koo_sphere_report:${PYTHONPATH:-}"
export PATH="${MODULE_DIR}/bin:${PATH}"
exec python3 -m koo_sphere_report "$@"
WRAPPER
chmod +x "${PREFIX}/bin/koo_sphere_report"
ok "koo_sphere_report wrapper → bin/"

# post_analyze orchestration script
cp "${PROJECT_ROOT}/scripts/post_analyze.sh" "${PREFIX}/bin/post_analyze"
chmod +x "${PREFIX}/bin/post_analyze"
ok "post_analyze → bin/"

# ============================================================
# Nuitka standalone builds (optional)
# ============================================================
if [ "$BUILD_NUITKA" = true ]; then
    log "Building standalone executables with Nuitka..."

    if ! python3 -m nuitka --version &>/dev/null; then
        warn "Nuitka not found — installing..."
        pip install nuitka ordered-set 2>/dev/null || pip install --user nuitka ordered-set 2>/dev/null || {
            err "Failed to install Nuitka"; BUILD_NUITKA=false;
        }
    fi

    if [ "$BUILD_NUITKA" = true ]; then
        NUITKA_COMMON=(
            --standalone
            --onefile
            --assume-yes-for-downloads
            --remove-output
            --no-pyi-file
        )

        NUITKA_TMP=$(mktemp -d)

        # koo_deep_report
        log "  Building koo_deep_report (Nuitka)..."
        DEEP_SRC="${PROJECT_ROOT}/python/koo_deep_report"
        cat > "${NUITKA_TMP}/entry_deep.py" << 'ENTRY'
from koo_deep_report.__main__ import main
main()
ENTRY
        cd "${DEEP_SRC}"
        python3 -m nuitka "${NUITKA_COMMON[@]}" \
            --include-package=koo_deep_report \
            --output-filename=koo_deep_report \
            --output-dir="${PREFIX}/bin" \
            "${NUITKA_TMP}/entry_deep.py" \
            2>&1 | tail -3 \
            && ok "koo_deep_report (Nuitka onefile) → bin/" \
            || warn "koo_deep_report Nuitka build failed (shell wrapper still available)"

        # koo_sphere_report
        log "  Building koo_sphere_report (Nuitka)..."
        SPHERE_SRC="${PROJECT_ROOT}/python/koo_sphere_report"
        cat > "${NUITKA_TMP}/entry_sphere.py" << 'ENTRY'
from koo_sphere_report.__main__ import main
main()
ENTRY
        cd "${SPHERE_SRC}"
        python3 -m nuitka "${NUITKA_COMMON[@]}" \
            --include-package=koo_sphere_report \
            --output-filename=koo_sphere_report \
            --output-dir="${PREFIX}/bin" \
            "${NUITKA_TMP}/entry_sphere.py" \
            2>&1 | tail -3 \
            && ok "koo_sphere_report (Nuitka onefile) → bin/" \
            || warn "koo_sphere_report Nuitka build failed (shell wrapper still available)"

        rm -rf "${NUITKA_TMP}"
        cd "${PROJECT_ROOT}"

        echo ""
    fi
fi

# LSPrePost (optional)
if [ -n "${LSPREPOST_SRC}" ] && [ -d "${LSPREPOST_SRC}" ]; then
    log "Copying LSPrePost..."
    cp -r "${LSPREPOST_SRC}" "${PREFIX}/lsprepost"
    ok "LSPrePost → lsprepost/"
elif [ -d "${PROJECT_ROOT}/installed/lsprepost" ]; then
    log "Copying bundled LSPrePost..."
    cp -r "${PROJECT_ROOT}/installed/lsprepost" "${PREFIX}/lsprepost"
    ok "LSPrePost (bundled) → lsprepost/"
fi

echo ""

# ============================================================
# Activation script
# ============================================================
log "Creating activation script..."

cat > "${PREFIX}/activate.sh" << ACTIVATE
#!/bin/bash
# Source this file to set up KooD3plotReader module environment
# Usage: source ${PREFIX}/activate.sh

export KOOD3PLOT_HOME="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
export PATH="\${KOOD3PLOT_HOME}/bin:\${PATH}"
export PYTHONPATH="\${KOOD3PLOT_HOME}/python/koo_deep_report:\${KOOD3PLOT_HOME}/python/koo_sphere_report:\${PYTHONPATH:-}"

# LSPrePost path (if bundled)
if [ -d "\${KOOD3PLOT_HOME}/lsprepost" ]; then
    export LSPREPOST_PATH="\${KOOD3PLOT_HOME}/lsprepost"
fi

echo "KooD3plotReader module activated"
echo "  KOOD3PLOT_HOME=\${KOOD3PLOT_HOME}"
echo "  unified_analyzer: \$(which unified_analyzer 2>/dev/null || echo 'not found')"
echo "  koo_deep_report:  \$(which koo_deep_report 2>/dev/null || echo 'not found')"
echo "  koo_sphere_report:\$(which koo_sphere_report 2>/dev/null || echo 'not found')"
echo "  post_analyze:     \$(which post_analyze 2>/dev/null || echo 'not found')"
ACTIVATE
chmod +x "${PREFIX}/activate.sh"
ok "activate.sh created"

# ============================================================
# Version file
# ============================================================
VERSION=$(git -C "${PROJECT_ROOT}" describe --tags --always 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
cat > "${PREFIX}/VERSION" << EOF
KooD3plotReader Post-Processing Module
Version:    ${VERSION}
Built:      ${BUILD_DATE}
Build Type: ${BUILD_TYPE}
Viewer:     ${BUILD_VIEWER}
LSPrePost:  $([ -d "${PREFIX}/lsprepost" ] && echo "bundled" || echo "not included")
Platform:   $(uname -s)-$(uname -m)

Components:
  unified_analyzer    C++ d3plot analysis engine
  koo_deep_report     Python single-sim report (wraps unified_analyzer)
  koo_sphere_report   Python all-angle sphere report
  post_analyze        Bash orchestrator (unified→deep→sphere pipeline)
  $([ "$BUILD_VIEWER" = true ] && echo "koo_viewer          C++ interactive GUI viewer")
EOF
ok "VERSION file created"

echo ""

# ============================================================
# Summary
# ============================================================
TOTAL_SIZE=$(du -sh "${PREFIX}" | cut -f1)

echo -e "${CYAN}============================================================"
echo " Module Build Complete"
echo -e "============================================================${NC}"
echo ""
echo "  Location: ${PREFIX}"
echo "  Size:     ${TOTAL_SIZE}"
echo "  Version:  ${VERSION}"
echo ""
echo "  Contents:"
ls -1 "${PREFIX}/bin/" | sed 's/^/    /'
echo ""
echo "  Usage:"
echo "    source ${PREFIX}/activate.sh"
echo "    post_analyze <test_dir> --section-view --section-view-backend lsprepost"
echo ""
echo "  Apptainer integration:"
echo "    Copy this module to /opt/kood3plot in your .def file"
echo "    Add to %environment:"
echo "      export PATH=/opt/kood3plot/bin:\$PATH"
echo "      export PYTHONPATH=/opt/kood3plot/python/koo_deep_report:/opt/kood3plot/python/koo_sphere_report:\$PYTHONPATH"
echo ""
