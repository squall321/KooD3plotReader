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
# 보존되는 것(호스트 고유): env.sh(PYTHONPATH 줄만 갱신), lsprepost/, bin/analyze_and_report
# 생성되는 것: bin/koo_*_report 래퍼 — 호스트 lib/ 구조에 맞춘 형식
#
# SIF 파일 자체도 배포 디렉토리에 설치한다(<배포 디렉토리>/<SIF 파일명>). 첫 판은
# 호스트 bin/lib 만 갈고 SIF 는 그대로 둔 채, 검증도 **원본** SIF 와만 대조했다 —
# 배포 디렉토리의 SIF 가 옛 판으로 남아도 통과하는 구멍이었다.
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
# SIF 설치 — 같은 파일이면 건너뛴다. 임시 이름으로 복사한 뒤 mv 로 교체해,
# 복사 도중 실패해도 기존 SIF 가 깨진 채 남지 않게 한다.
SIF_NAME="$(basename "$SIF")"
DEST_SIF="${DEST}/${SIF_NAME}"
if [ "$(readlink -f "$SIF")" != "$(readlink -f "$DEST_SIF" 2>/dev/null || true)" ]; then
    if [ -f "$DEST_SIF" ]; then
        OLD_VER="$(apptainer exec "$DEST_SIF" cat /opt/kood3plot/VERSION 2>/dev/null \
                   | sed -n 's/^Version:[[:space:]]*//p' | head -1)"
        $SUDO mv -f "$DEST_SIF" "${DEST}/${SIF_NAME%.sif}_backup_${TS}.sif" \
            || die "기존 SIF 백업 실패"
        echo "  기존 SIF(${OLD_VER:-?}) → ${SIF_NAME%.sif}_backup_${TS}.sif"
    fi
    $SUDO cp -f "$SIF" "${DEST_SIF}.tmp.$$" || die "SIF 복사 실패"
    $SUDO mv -f "${DEST_SIF}.tmp.$$" "$DEST_SIF" || die "SIF 교체 실패"
    echo "  SIF 설치: $DEST_SIF"
fi

# ── 파이썬 패키지 목록 (lib/ 에 들어갈 것) ──
# 순서는 기존 호스트 배포본(v32)과 같게 두고, 새 패키지는 뒤에 붙인다.
PKGS=()
for known in koo_deep_report koo_sphere_report koo_impact_report koo_federate_report koo_custom_report; do
    [ -d "$STAGE/python/$known" ] && PKGS+=("$known")
done
for d in "$STAGE"/python/koo_*; do
    n="$(basename "$d")"
    case " ${PKGS[*]} " in *" $n "*) ;; *) PKGS+=("$n") ;; esac
done
PKGPATH=""
for n in "${PKGS[@]}"; do
    PKGPATH="${PKGPATH}\${SMARTTWIN_POST_HOME}/lib/${n}:"
done

# bin: 실행 파일(ELF·post_analyze·심볼릭 링크)만 SIF 에서 복사한다.
# 🔴 `koo_*_report` 래퍼는 **복사하면 안 된다.** SIF 안 래퍼는 SIF 의 `python/`
#    구조를 가리키는데 호스트는 `lib/` 구조다. 2026-09-13 배포에서 그대로 덮어써
#    env.sh 없이는 전부 `No module named …` 로 죽는 상태가 사흘 남았다.
#    호스트 래퍼는 아래에서 v32 원본과 같은 형식으로 생성한다.
for f in "$STAGE"/bin/*; do
    n="$(basename "$f")"
    case "$n" in koo_*_report) continue ;; esac
    $SUDO cp -af "$f" "${DEST}/bin/" || die "bin 복사 실패: $n"
done

# 호스트 래퍼 생성 — v32 호스트 배포본의 래퍼와 같은 형식 (모듈명만 다르다)
HOSTBIN="$STAGE/hostbin"
mkdir -p "$HOSTBIN"
for n in "${PKGS[@]}"; do
    {
        printf '%s\n' '#!/bin/bash'
        printf '%s\n' 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"'
        printf '%s\n' 'export SMARTTWIN_POST_HOME="$(cd "${SCRIPT_DIR}/.." && pwd)"'
        printf 'export PYTHONPATH="%s${PYTHONPATH:-}"\n' "$PKGPATH"
        printf '%s\n' 'export PATH="${SMARTTWIN_POST_HOME}/bin:${PATH}"'
        printf '%s\n' 'export LSPREPOST_PATH="${SMARTTWIN_POST_HOME}/lib/lsprepost"'
        printf '%s\n' 'export KOOD3PLOT_HOME="${SMARTTWIN_POST_HOME}"'
        printf 'exec python3 -m %s "$@"\n' "$n"
    } > "$HOSTBIN/$n"
    chmod 755 "$HOSTBIN/$n"
    $SUDO cp -f "$HOSTBIN/$n" "${DEST}/bin/$n" || die "래퍼 설치 실패: $n"
done
echo "  래퍼 ${#PKGS[@]}개 생성 (lib/ 형식): ${PKGS[*]}"
# lib: SIF 의 python/* 이 대응한다. lsprepost 등 호스트 고유 디렉토리는 남긴다
for p in "$STAGE"/python/*; do
    n="$(basename "$p")"
    $SUDO rm -rf "${DEST}/lib/${n}" || die "lib 제거 실패: $n"
    $SUDO cp -a "$p" "${DEST}/lib/" || die "lib 복사 실패: $n"
done
# env.sh — 호스트 고유 설정은 보존하되 PYTHONPATH 줄만 패키지 목록에 맞춘다.
# 새 패키지(koo_scatter_report 등)를 넣고 env.sh 를 안 고치면, source 해도 import 가 안 된다.
if [ -f "${DEST}/env.sh" ]; then
    ENVPATH=""
    for n in "${PKGS[@]}"; do ENVPATH="${ENVPATH}\${SMARTTWIN_POST_HOME}/lib/${n}:"; done
    awk -v line="export PYTHONPATH=${ENVPATH}\$PYTHONPATH" '
        /^export PYTHONPATH=/ { print line; done=1; next }
        { print }
        END { if (!done) print line }' "${DEST}/env.sh" > "$STAGE/env.sh" \
        || die "env.sh 갱신본 작성 실패"
    $SUDO cp -f "$STAGE/env.sh" "${DEST}/env.sh" || die "env.sh 설치 실패"
    echo "  env.sh PYTHONPATH 갱신 (나머지 줄 보존)"
fi

# VERSION — 이것이 빠져 2주간 옛 커밋을 가리킨 적이 있다
$SUDO cp -af "$STAGE/VERSION" "${DEST}/VERSION" || die "VERSION 복사 실패"
echo "  완료"

echo ""
echo "== 검증 =="
# 🔴 원본 SIF 가 아니라 **배포 디렉토리에 설치된** SIF 와 대조한다.
"${SCRIPT_DIR}/verify_deploy.sh" "$DEST" "$DEST_SIF"
