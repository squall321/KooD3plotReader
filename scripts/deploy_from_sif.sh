#!/usr/bin/env bash
# SIF 안의 모듈을 호스트 배포 디렉토리로 옮기고 검증까지 하는 배포 도구
#
# 왜 있나 — 호스트 배포본을 **로컬 빌드**로 채웠다가 SIF 와 버전이 어긋난 적이
# 있다. 로컬 워킹트리는 `.bkit/`·`.claude/` 같은 도구 상태 파일 때문에 `git
# describe --dirty` 가 늘 dirty 로 나오고, 그러면 배포본 버전이
# `v2.4.0-263-gf3fd09b-dirty` 처럼 "추적 불가한 빌드" 로 찍힌다.
#
# SIF 는 GitHub 에서 clean 하게 clone 해 빌드하므로 버전이 정확하다.
# **호스트 배포본은 SIF 에서 추출한다** — 그래야 둘이 항상 같은 판이다.
#
# 사용법:
#   scripts/deploy_from_sif.sh <sif> <배포 디렉토리>
#   scripts/deploy_from_sif.sh apptainer/SmartTwinPostprocessor.sif /data/SmartTwinPostprocessor
#
# 보존되는 것(호스트 고유): env.sh, lsprepost/, bin/analyze_and_report
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
die() { echo "오류: $*" >&2; exit 1; }

SIF="${1:-}"
DEST="${2:-}"
[ -n "$SIF" ] && [ -n "$DEST" ] || die "사용법: $0 <sif> <배포 디렉토리>"
[ -f "$SIF" ]  || die "SIF 가 없습니다: $SIF"
[ -d "$DEST" ] || die "배포 디렉토리가 없습니다: $DEST"
command -v apptainer >/dev/null 2>&1 || die "apptainer 를 찾지 못했습니다"

SUDO=""
if [ ! -w "$DEST" ]; then
    sudo -n true 2>/dev/null || die "$DEST 에 쓸 수 없고 sudo 도 쓸 수 없습니다"
    SUDO="sudo -n"
fi

echo "== SIF 버전 확인 =="
VER="$(apptainer exec "$SIF" cat /opt/kood3plot/VERSION 2>/dev/null \
       | sed -n 's/^Version:[[:space:]]*//p' | head -1)"
[ -n "$VER" ] || die "SIF 안 /opt/kood3plot/VERSION 을 읽지 못했습니다"
case "$VER" in
    *dirty*) die "SIF 가 dirty 빌드입니다 ($VER) — clean 체크아웃에서 다시 빌드하세요" ;;
    unknown) die "SIF 버전이 unknown 입니다 — 추적할 수 없는 빌드는 배포하지 않습니다" ;;
esac
echo "  $VER"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "== SIF 에서 추출 =="
apptainer exec --bind "$STAGE:/mnt/out" "$SIF" \
    bash -c 'cp -a /opt/kood3plot/bin /opt/kood3plot/python /opt/kood3plot/VERSION /mnt/out/' \
    || die "추출에 실패했습니다"
[ -d "$STAGE/bin" ] && [ -d "$STAGE/python" ] && [ -f "$STAGE/VERSION" ] \
    || die "추출 결과가 불완전합니다"
echo "  bin $(ls "$STAGE/bin" | wc -l)개, python $(ls "$STAGE/python" | wc -l)개"

echo "== 백업 =="
TS="$(date +%Y%m%d_%H%M%S)"
$SUDO tar czf "${DEST}/hostdirs_backup_${TS}.tar.gz" \
    -C "$DEST" bin lib env.sh VERSION 2>/dev/null \
    || echo "  (백업 실패 — 계속합니다. 기존 파일은 아래에서 덮어써집니다)"
echo "  ${DEST}/hostdirs_backup_${TS}.tar.gz"

echo "== 배포 =="
# bin: SIF 것으로 덮되 호스트 고유 파일은 남긴다 (목록에 없는 것은 건드리지 않음)
for f in "$STAGE"/bin/*; do
    $SUDO cp -af "$f" "${DEST}/bin/" || die "bin 복사 실패: $(basename "$f")"
done
# lib: SIF 의 python/* 이 대응한다. lsprepost 등 호스트 고유 디렉토리는 남긴다
for p in "$STAGE"/python/*; do
    n="$(basename "$p")"
    $SUDO rm -rf "${DEST}/lib/${n}" || die "lib 제거 실패: $n"
    $SUDO cp -a "$p" "${DEST}/lib/" || die "lib 복사 실패: $n"
done
# VERSION — 이것이 빠져 2주간 옛 커밋을 가리킨 적이 있다
$SUDO cp -af "$STAGE/VERSION" "${DEST}/VERSION" || die "VERSION 복사 실패"
echo "  완료"

echo ""
echo "== 검증 =="
"${SCRIPT_DIR}/verify_deploy.sh" "$DEST" "$SIF"
