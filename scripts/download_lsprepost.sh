#!/bin/bash
# ============================================================
# LSPrePost Linux 자동 다운로드 스크립트
#
# 사용법:
#   ./download_lsprepost.sh [설치 디렉토리]
#
# 예시:
#   ./download_lsprepost.sh                    (기본: ./lsprepost)
#   ./download_lsprepost.sh /usr/local/lsprepost
# ============================================================

set -e

VERSION="4.12.11"
DATE="17Dec2025"
FILENAME="LS-PrePost-2025R1_${VERSION}_CentOS7.9_x86_64.tgz"
URL="https://ftp.lstc.com/anonymous/outgoing/lsprepost/4.12/linux64/${FILENAME}"

INSTALL_DIR="${1:-$(dirname "$0")/../lsprepost}"
INSTALL_DIR=$(mkdir -p "$INSTALL_DIR" && cd "$INSTALL_DIR" && pwd)

echo ""
echo "========================================"
echo " LSPrePost ${VERSION} Linux Downloader"
echo "========================================"
echo ""
echo " URL: ${URL}"
echo " 설치 디렉토리: ${INSTALL_DIR}"
echo ""

# 이미 설치되어 있는지 확인
if [ -f "${INSTALL_DIR}/lsprepost" ] || [ -f "${INSTALL_DIR}/lspp412" ]; then
    echo "[INFO] LSPrePost가 이미 존재합니다: ${INSTALL_DIR}"
    echo "[INFO] 재설치하려면 해당 디렉토리를 삭제 후 다시 실행하세요."
    exit 0
fi

# 다운로드
ARCHIVE="${INSTALL_DIR}/${FILENAME}"
echo "[1/3] 다운로드 중... (약 400MB)"

if command -v curl &>/dev/null; then
    curl -L -o "${ARCHIVE}" "${URL}"
elif command -v wget &>/dev/null; then
    wget -O "${ARCHIVE}" "${URL}"
else
    echo "[오류] curl 또는 wget이 필요합니다."
    exit 1
fi

if [ ! -f "${ARCHIVE}" ]; then
    echo "[오류] 다운로드 실패. URL을 확인하세요:"
    echo "  ${URL}"
    exit 1
fi

# 압축 해제
echo "[2/3] 압축 해제 중..."
tar -xzf "${ARCHIVE}" -C "${INSTALL_DIR}" --strip-components=1 2>/dev/null || \
    tar -xzf "${ARCHIVE}" -C "${INSTALL_DIR}"

# 정리
echo "[3/3] 정리 중..."
rm -f "${ARCHIVE}"

echo ""
echo "========================================"
echo " 설치 완료: ${INSTALL_DIR}"
echo ""
echo " 실행 파일 확인:"
ls -la "${INSTALL_DIR}"/lsprepost "${INSTALL_DIR}"/lspp* 2>/dev/null || echo "  (직접 확인 필요)"
echo ""
echo " single_analyzer에서 자동 탐색되거나:"
echo "   single_analyzer ... --lsprepost-path ${INSTALL_DIR}/lsprepost"
echo "========================================"
