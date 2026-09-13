#!/usr/bin/env bash
# 배포 디렉토리를 tar.gz 로 묶고, 묶은 결과를 반드시 검증하는 패키징 도구
#
# 왜 있나 — 지금까지 배포 tar 는 손으로 묶었고, 그 절차가 리포지토리에 없었다.
# v30(2026-09-08) 에서 VERSION 이 조용히 빠졌는데 아무도 몰랐고, 호스트 VERSION 이
# 2주간 옛 커밋을 가리켰다. 여기서는 묶은 뒤 verify_package.sh 를 **강제로** 돌리고,
# 실패하면 아카이브를 지운다 — 검증에 실패한 물건이 배포 후보로 남지 않게.
#
# 구조 변환은 하지 않는다. 이미 만들어진 배포 디렉토리를 그대로 묶는다.
# (SIF → 배포 디렉토리 변환 절차는 이 스크립트의 범위가 아니다.)
#
# 사용법:
#   scripts/package_module.sh --from-dir /data/SmartTwinPostprocessor \
#                             --out /data/SmartTwinPostprocessor/SmartTwinPostprocessor_20260913_v33.tar.gz
#   # VERSION 이 배포 디렉토리에 없거나 낡았으면 SIF 에서 가져온다
#   scripts/package_module.sh --from-dir <dir> --out <tar.gz> --version-from <sif>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SRC=""
OUT=""
VERSION_FROM=""

die() { echo "오류: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
    case "$1" in
        --from-dir)     SRC="${2:-}"; shift 2 ;;
        --out)          OUT="${2:-}"; shift 2 ;;
        --version-from) VERSION_FROM="${2:-}"; shift 2 ;;
        -h|--help)      sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *)              die "알 수 없는 인자: $1" ;;
    esac
done

[ -n "$SRC" ] || die "--from-dir 가 필요합니다"
[ -n "$OUT" ] || die "--out 이 필요합니다"
[ -d "$SRC" ] || die "배포 디렉토리가 없습니다: $SRC"

SRC="$(cd "$SRC" && pwd)"
PARENT="$(dirname "$SRC")"
BASE="$(basename "$SRC")"

# ── VERSION 확보 ──────────────────────────────────────────────────────
# 배포 디렉토리의 VERSION 을 그대로 쓰되, --version-from 이 주어지면 SIF 안의
# VERSION 으로 갈아끼운다. 어느 쪽도 없으면 여기서 멈춘다 — VERSION 없는
# 아카이브를 만들지 않는 것이 이 스크립트의 존재 이유다.
VERSION_STAGE=""
if [ -n "$VERSION_FROM" ]; then
    [ -f "$VERSION_FROM" ] || die "SIF 가 없습니다: $VERSION_FROM"
    command -v apptainer >/dev/null 2>&1 || die "apptainer 를 찾지 못했습니다 (--version-from 에 필요)"
    VERSION_STAGE="$(mktemp -d)"
    trap 'rm -rf "$VERSION_STAGE"' EXIT
    if ! apptainer exec "$VERSION_FROM" cat /opt/kood3plot/VERSION > "$VERSION_STAGE/VERSION" 2>/dev/null; then
        die "SIF 안 /opt/kood3plot/VERSION 을 읽지 못했습니다: $VERSION_FROM"
    fi
    [ -s "$VERSION_STAGE/VERSION" ] || die "SIF 안 VERSION 이 비어 있습니다"
    echo "VERSION 을 SIF 에서 가져왔습니다:"
    sed -n '2,3p' "$VERSION_STAGE/VERSION" | sed 's/^/  /'
elif [ -f "$SRC/VERSION" ]; then
    echo "배포 디렉토리의 VERSION 을 씁니다:"
    sed -n '2,3p' "$SRC/VERSION" | sed 's/^/  /'
else
    die "VERSION 이 없습니다: $SRC/VERSION
  --version-from <sif> 로 SIF 안 /opt/kood3plot/VERSION 을 가져오거나,
  build_module.sh 산출물의 VERSION 을 배포 디렉토리에 두세요."
fi

# ── 묶기 ──────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$OUT")" || die "출력 폴더를 만들지 못했습니다: $(dirname "$OUT")"
TMP_TAR="$(mktemp --suffix=.tar)"
cleanup_tmp() { rm -f "$TMP_TAR"; }
trap 'cleanup_tmp; [ -n "$VERSION_STAGE" ] && rm -rf "$VERSION_STAGE"' EXIT

echo "묶는 중: $SRC → $OUT"
tar cf "$TMP_TAR" -C "$PARENT" "$BASE"

if [ -n "$VERSION_STAGE" ]; then
    # 디렉토리 안의 옛 VERSION 을 새것으로 덮는다. tar 는 뒤 항목이 이기므로
    # append 만으로 충분하다 (풀 때 나중 것이 덮어쓴다).
    tar rf "$TMP_TAR" -C "$VERSION_STAGE" --transform "s|^|${BASE}/|" VERSION
fi

gzip -9 -c "$TMP_TAR" > "$OUT" || die "gzip 에 실패했습니다"

# ── 검증 — 실패하면 아카이브를 남기지 않는다 ─────────────────────────
echo ""
if ! "$SCRIPT_DIR/verify_package.sh" "$OUT"; then
    rm -f "$OUT"
    die "검증에 실패해 아카이브를 삭제했습니다: $OUT
  위에 적힌 빠진 구성요소를 채운 뒤 다시 실행하세요."
fi

echo ""
echo "완료: $OUT  ($(du -h "$OUT" | cut -f1))"
