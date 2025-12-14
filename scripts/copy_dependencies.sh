#!/bin/bash
# ============================================================
# KooD3plotReader - vcpkg 의존성 로컬 복사 스크립트 (Linux/macOS)
#
# 사용법:
#   ./copy_dependencies.sh [vcpkg_root] [triplet]
#
# 예시:
#   ./copy_dependencies.sh ~/dev/vcpkg x64-linux
#   ./copy_dependencies.sh                         # 기본값 사용
# ============================================================

set -e

echo ""
echo "========================================"
echo " KooD3plotReader Dependency Copier"
echo "========================================"
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 기본값 설정
VCPKG_ROOT="${1:-${VCPKG_ROOT:-$HOME/dev/vcpkg}}"

# triplet 자동 감지
if [ -z "$2" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if [[ $(uname -m) == "arm64" ]]; then
            TRIPLET="arm64-osx"
        else
            TRIPLET="x64-osx"
        fi
    else
        # Linux
        TRIPLET="x64-linux"
    fi
else
    TRIPLET="$2"
fi

# 프로젝트 루트
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPS_DIR="$PROJECT_ROOT/deps/$TRIPLET"

echo "[설정]"
echo "  VCPKG_ROOT:   $VCPKG_ROOT"
echo "  TRIPLET:      $TRIPLET"
echo "  PROJECT_ROOT: $PROJECT_ROOT"
echo "  DEPS_DIR:     $DEPS_DIR"
echo ""

# vcpkg 확인
if [ ! -f "$VCPKG_ROOT/vcpkg" ]; then
    echo -e "${RED}[오류] vcpkg를 찾을 수 없습니다: $VCPKG_ROOT${NC}"
    echo "vcpkg를 먼저 설치해주세요:"
    echo "  git clone https://github.com/microsoft/vcpkg.git"
    echo "  cd vcpkg"
    echo "  ./bootstrap-vcpkg.sh"
    exit 1
fi

# deps 디렉토리 생성
echo "[1/4] 디렉토리 생성 중..."
if [ -d "$DEPS_DIR" ]; then
    echo "  기존 deps 디렉토리 삭제 중..."
    rm -rf "$DEPS_DIR"
fi
mkdir -p "$DEPS_DIR"/{include,lib,bin,share}

# vcpkg 패키지 설치
echo ""
echo "[2/4] vcpkg 패키지 설치 확인 중..."

PACKAGES=("hdf5[cpp]" "yaml-cpp" "blosc" "gtest")

for pkg in "${PACKAGES[@]}"; do
    echo -n "  $pkg 확인 중..."
    if "$VCPKG_ROOT/vcpkg" list | grep -qi "${pkg%%\[*}:$TRIPLET"; then
        echo -e " ${GREEN}이미 설치됨${NC}"
    else
        echo " 설치 중..."
        "$VCPKG_ROOT/vcpkg" install "$pkg:$TRIPLET"
    fi
done

# 설치된 패키지 경로
INSTALLED_DIR="$VCPKG_ROOT/installed/$TRIPLET"

# 파일 복사
echo ""
echo "[3/4] 파일 복사 중..."

# include 복사
echo "  include 파일 복사 중..."
cp -r "$INSTALLED_DIR/include/"* "$DEPS_DIR/include/" 2>/dev/null || true

# lib 복사
echo "  lib 파일 복사 중..."
cp -r "$INSTALLED_DIR/lib/"* "$DEPS_DIR/lib/" 2>/dev/null || true

# bin 복사 (실행 파일 등)
echo "  bin 파일 복사 중..."
if [ -d "$INSTALLED_DIR/bin" ]; then
    cp -r "$INSTALLED_DIR/bin/"* "$DEPS_DIR/bin/" 2>/dev/null || true
fi

# debug 복사 (선택적)
if [ -d "$INSTALLED_DIR/debug" ]; then
    echo "  debug 파일 복사 중..."
    mkdir -p "$DEPS_DIR/debug/lib"
    cp -r "$INSTALLED_DIR/debug/lib/"* "$DEPS_DIR/debug/lib/" 2>/dev/null || true
    if [ -d "$INSTALLED_DIR/debug/bin" ]; then
        mkdir -p "$DEPS_DIR/debug/bin"
        cp -r "$INSTALLED_DIR/debug/bin/"* "$DEPS_DIR/debug/bin/" 2>/dev/null || true
    fi
fi

# share 복사 (CMake 설정 등)
echo "  share 파일 복사 중..."
cp -r "$INSTALLED_DIR/share/"* "$DEPS_DIR/share/" 2>/dev/null || true

# 버전 정보 저장
echo ""
echo "[4/4] 버전 정보 저장 중..."

cat > "$DEPS_DIR/VERSION.txt" << EOF
# KooD3plotReader Local Dependencies
# Generated: $(date)
# Triplet: $TRIPLET
# Platform: $OSTYPE

## Installed Packages:
$("$VCPKG_ROOT/vcpkg" list | grep "$TRIPLET")
EOF

# 사용법 파일 생성
cat > "$DEPS_DIR/README.md" << 'EOF'
# Local Dependencies

This directory contains pre-built dependencies for KooD3plotReader.

## Usage

```bash
# CMake will automatically find these dependencies
cmake .. -DKOOD3PLOT_USE_LOCAL_DEPS=ON
```

## Regenerate

```bash
./scripts/copy_dependencies.sh [vcpkg_root] [triplet]
```

## Contents

- `include/` - Header files
- `lib/` - Static/shared libraries
- `bin/` - Executables and DLLs
- `share/` - CMake config files
- `debug/` - Debug builds (optional)
EOF

echo ""
echo -e "${GREEN}========================================"
echo " 완료!"
echo "========================================${NC}"
echo ""
echo "로컬 의존성이 다음 위치에 복사되었습니다:"
echo "  $DEPS_DIR"
echo ""
echo "사용 방법:"
echo "  cmake .. -DKOOD3PLOT_USE_LOCAL_DEPS=ON"
echo ""
echo "또는 프로젝트를 다른 PC로 복사하면 자동으로 deps/ 폴더가 사용됩니다."
echo ""
