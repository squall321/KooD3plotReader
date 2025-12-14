#!/bin/bash
# ============================================================
# KooD3plotReader - 개발 환경 자동 설정 스크립트 (Linux/macOS)
#
# 이 스크립트는:
# 1. vcpkg 설치 확인/설치
# 2. 필요한 패키지 설치
# 3. 로컬 deps/ 폴더로 복사
# 4. CMake 빌드 설정
#
# 사용법:
#   ./setup_dev_env.sh [vcpkg_path]
# ============================================================

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         KooD3plotReader Development Environment Setup        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 프로젝트 루트
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# vcpkg 경로 설정
VCPKG_ROOT="${1:-${VCPKG_ROOT:-$HOME/dev/vcpkg}}"

# triplet 자동 감지
if [[ "$OSTYPE" == "darwin"* ]]; then
    if [[ $(uname -m) == "arm64" ]]; then
        TRIPLET="arm64-osx"
    else
        TRIPLET="x64-osx"
    fi
else
    TRIPLET="x64-linux"
fi

echo "[설정]"
echo "  Project:    $PROJECT_ROOT"
echo "  vcpkg:      $VCPKG_ROOT"
echo "  Triplet:    $TRIPLET"
echo "  Platform:   $OSTYPE"
echo ""

# ============================================================
# Step 1: vcpkg 설치 확인
# ============================================================
echo -e "${BLUE}[1/5]${NC} vcpkg 확인 중..."

if [ ! -f "$VCPKG_ROOT/vcpkg" ]; then
    echo "  vcpkg가 없습니다. 설치를 시작합니다..."

    # 부모 디렉토리 생성
    mkdir -p "$(dirname "$VCPKG_ROOT")"

    echo "  vcpkg 클론 중..."
    git clone https://github.com/microsoft/vcpkg.git "$VCPKG_ROOT"

    echo "  vcpkg 부트스트랩 중..."
    cd "$VCPKG_ROOT"
    ./bootstrap-vcpkg.sh

    cd "$PROJECT_ROOT"
    echo -e "  ${GREEN}vcpkg 설치 완료!${NC}"
else
    echo -e "  ${GREEN}vcpkg 발견: $VCPKG_ROOT${NC}"
fi

# ============================================================
# Step 2: 패키지 설치
# ============================================================
echo ""
echo -e "${BLUE}[2/5]${NC} 패키지 설치 중..."

PACKAGES=("hdf5[cpp]" "yaml-cpp" "blosc" "gtest")

for pkg in "${PACKAGES[@]}"; do
    pkg_name="${pkg%%\[*}"
    echo -n "  $pkg:$TRIPLET 확인 중..."
    if "$VCPKG_ROOT/vcpkg" list | grep -qi "$pkg_name:$TRIPLET"; then
        echo -e " ${GREEN}이미 설치됨${NC}"
    else
        echo " 설치 중... (시간이 걸릴 수 있습니다)"
        "$VCPKG_ROOT/vcpkg" install "$pkg:$TRIPLET" || {
            echo -e "  ${YELLOW}[경고] $pkg 설치 실패, 계속 진행합니다.${NC}"
        }
    fi
done

# ============================================================
# Step 3: 로컬 deps 복사
# ============================================================
echo ""
echo -e "${BLUE}[3/5]${NC} 로컬 deps/ 폴더로 복사 중..."

chmod +x "$SCRIPT_DIR/copy_dependencies.sh"
"$SCRIPT_DIR/copy_dependencies.sh" "$VCPKG_ROOT" "$TRIPLET"

# ============================================================
# Step 4: 빌드 디렉토리 생성 및 CMake 설정
# ============================================================
echo ""
echo -e "${BLUE}[4/5]${NC} CMake 설정 중..."

BUILD_DIR="$PROJECT_ROOT/build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "  CMake 구성 중..."
cmake .. \
    -DKOOD3PLOT_USE_LOCAL_DEPS=ON \
    -DKOOD3PLOT_BUILD_HDF5=ON \
    -DKOOD3PLOT_BUILD_TESTS=ON \
    -DKOOD3PLOT_BUILD_EXAMPLES=ON \
    -DCMAKE_BUILD_TYPE=Release

# ============================================================
# Step 5: 빌드
# ============================================================
echo ""
echo -e "${BLUE}[5/5]${NC} 빌드 중..."

cmake --build . --config Release -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4) || {
    echo -e "${YELLOW}[경고] 빌드 실패. 수동으로 빌드해주세요.${NC}"
}

# ============================================================
# 완료
# ============================================================
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo -e "║                    ${GREEN}설정 완료!${NC}                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "다음 명령으로 테스트할 수 있습니다:"
echo ""
echo "  cd build"
echo "  ctest"
echo ""
echo "또는 직접 실행:"
echo ""
echo "  ./build/test_hdf5_writer"
echo "  ./build/test_quantization"
echo "  ./build/02_hdf5_benchmark"
echo ""
echo "프로젝트를 다른 PC로 복사해도 deps/ 폴더 덕분에 바로 빌드 가능합니다!"
echo ""

cd "$PROJECT_ROOT"
