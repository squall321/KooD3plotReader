#!/usr/bin/env bash
# 배포된 후처리 모듈의 VERSION 과 실행 파일이 실제로 같은 판인지 대조하는 도구
#
# 왜 있나 — 2026-09-11 에 배포한 바이너리는 최신이었는데 VERSION 파일만 8-28 판이
# 남아 2주간 옛 커밋을 가리켰다. 그걸 믿은 후처리가 이미 있는 기능을 "없다" 고
# 판단해 임시 스크립트로 다시 만들었다 (docs/postproc_gap_2026-09/plan.md §0).
# VERSION 은 종이, 실행 파일은 실물이다. 둘이 어긋나면 여기서 걸린다.
#
# 사용법:
#   scripts/verify_deploy.sh /data/SmartTwinPostprocessor
#   scripts/verify_deploy.sh /data/SmartTwinPostprocessor/SmartTwinPostprocessor.sif
#   scripts/verify_deploy.sh <디렉토리> <sif>     # 둘 다 검사하고 서로도 대조
#
# 종료 상태: 일치 0, 불일치·확인불가 1

set -uo pipefail

die() { echo "오류: $*" >&2; exit 2; }
[ $# -ge 1 ] || die "검사할 배포 경로나 SIF 를 하나 이상 주세요"

fails=0
# 🔴 set -u 에서 빈 배열 참조(${#ARR[@]})가 unbound 로 죽는 bash 가 있다.
#    개수는 카운터로 따로 센다.
n_seen=0
declare -a SEEN_LABEL SEEN_VER

# VERSION 파일에서 Version: 값을 뽑는다
read_version_file() {          # read_version_file <VERSION 파일 경로>
    sed -n 's/^Version:[[:space:]]*//p' "$1" 2>/dev/null | head -1
}

# 실행 파일에게 직접 묻는다. --capabilities 가 없는 옛 빌드면 빈 문자열.
ask_binary() {                 # ask_binary <unified_analyzer 실행 방법...>
    local out
    out="$("$@" --capabilities 2>/dev/null)" || return 1
    # python 없이도 돌아야 하므로 sed 로 뽑는다
    sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' <<< "$out" | head -1
}

check_pair() {                 # check_pair <라벨> <VERSION 값> <바이너리 값>
    local label="$1" vfile="$2" vbin="$3"
    echo "── ${label}"
    echo "   VERSION 파일 : ${vfile:-(없음)}"
    echo "   실행 파일    : ${vbin:-(--capabilities 미지원 — 2026-09-13 이전 빌드)}"

    # 바이너리가 답하지 못해도 VERSION 은 기록해 둔다 — 대상 간 대조(호스트 vs SIF)는
    # 여전히 가능해야 한다. 이번 사건이 바로 그 형태였다.
    if [ -n "$vfile" ]; then
        SEEN_LABEL+=("$label"); SEEN_VER+=("$vfile"); n_seen=$((n_seen + 1))
    fi

    if [ -z "$vbin" ]; then
        echo "   ✗ 실행 파일이 스스로 답하지 못합니다. 이 배포본은 버전을 대조할 수 없습니다."
        echo "     --capabilities 를 담은 빌드로 다시 배포하세요."
        fails=$((fails + 1))
        return
    fi
    if [ -z "$vfile" ]; then
        echo "   ✗ VERSION 파일이 없거나 Version 줄이 없습니다 (배포 tar 에서 빠졌을 수 있습니다)."
        fails=$((fails + 1))
        return
    fi
    if [ "$vfile" != "$vbin" ]; then
        echo "   ✗ 불일치 — VERSION 은 '${vfile}', 실행 파일은 '${vbin}' 입니다."
        echo "     VERSION 을 믿고 기능 유무를 판단하면 틀립니다. 재배포하세요."
        fails=$((fails + 1))
        return
    fi
    echo "   ✓ 일치 (${vbin})"
}

for target in "$@"; do
    if [ -d "$target" ]; then
        vfile="$(read_version_file "$target/VERSION")"
        vbin=""
        if [ -x "$target/bin/unified_analyzer" ]; then
            vbin="$(ask_binary "$target/bin/unified_analyzer")"
        else
            echo "── ${target}"
            echo "   ✗ bin/unified_analyzer 가 없거나 실행할 수 없습니다"
            fails=$((fails + 1))
            continue
        fi
        check_pair "$target" "$vfile" "$vbin"

    elif [ -f "$target" ]; then
        command -v apptainer >/dev/null 2>&1 || die "apptainer 를 찾지 못했습니다 (SIF 검사에 필요)"
        vfile="$(apptainer exec "$target" cat /opt/kood3plot/VERSION 2>/dev/null \
                 | sed -n 's/^Version:[[:space:]]*//p' | head -1)"
        vbin="$(ask_binary apptainer exec "$target" /opt/kood3plot/bin/unified_analyzer)"
        check_pair "$target (SIF 내부)" "$vfile" "$vbin"

    else
        echo "── ${target}"
        echo "   ✗ 경로가 없습니다"
        fails=$((fails + 1))
    fi
done

# 여러 대상을 줬으면 서로도 같은 판인지 본다 — 호스트와 SIF 가 어긋나는 것이
# 이번 사건의 형태였다
if [ "$n_seen" -gt 1 ]; then
    echo ""
    echo "대상 간 대조 (VERSION 파일 기준):"
    first="${SEEN_VER[0]}"
    same=true
    for v in "${SEEN_VER[@]}"; do [ "$v" = "$first" ] || same=false; done
    if $same; then
        echo "   ✓ 모두 같은 판입니다 (${first})"
    else
        echo "   ✗ 대상마다 판이 다릅니다 — 어느 쪽을 믿어야 할지 알 수 없습니다:"
        for i in "${!SEEN_VER[@]}"; do echo "      ${SEEN_VER[$i]}  ← ${SEEN_LABEL[$i]}"; done
        fails=$((fails + 1))
    fi
fi

echo ""
if [ "$fails" -gt 0 ]; then
    echo "실패 ${fails}건 — 이 배포본의 버전 표시를 신뢰하면 안 됩니다."
    exit 1
fi
echo "전부 일치."
exit 0
