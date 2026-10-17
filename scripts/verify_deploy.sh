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
#   scripts/verify_deploy.sh --all-sites <디렉토리> <sif>   # 배포 지점까지 (아래)
#
# ── --all-sites: 한 릴리스가 닿아야 할 곳을 전부 본다 ──────────────────────
# 2026-10-17 에 드러났다 — 배포 지점이 넷인데 이 도구는 NFS 만 봤다. 그래서
# 호스트는 새 판, 노드가 실제로 실행하는 이미지는 2주 전 판인 상태가 "전부 일치" 로
# 통과했다. 지점은 이렇다:
#   ① 배포 디렉토리(NFS)            — 기본 검사
#   ② 설치된 SIF                     — 기본 검사
#   ③ compute-node-images            — deploy_apptainers.sh 의 원본. 노드 재설치 때 여기서 깔린다
#   ④ 노드 로컬 /opt/apptainers      — KooChainRun·smarttwin-tool 이 실제로 쓰는 것
#
# ③④ 는 **기본에서 보지 않는다.** 상류 표준 빌드의 순서가
#   ① SIF 빌드 → ② GUI·이미지 복사 → ③ deploy_from_sif.sh(→ 이 도구) → ④ tar → ⑤ Drive·메일
# 이고 노드 배포는 그 **뒤에** 따로 돌기 때문이다. 기본 검사가 노드 일치를 요구하면
# 모든 표준 빌드가 ③에서 멈추고 tar·메일도 못 나간다 (상류 요청, 2026-10-17).
# 그래서 노드 배포를 마친 뒤 `--all-sites` 로 따로 돌린다.
#
#   KOOD3PLOT_SITE_IMAGES  compute-node-images 경로 (기본 아래 값)
#   KOOD3PLOT_SITE_NODES   노드 목록, 공백 구분 (기본 "node001 node002")
#
# 종료 상태: 일치 0, 불일치·확인불가 1

set -uo pipefail

die() { echo "오류: $*" >&2; exit 2; }

ALL_SITES=false
ARGS=()
for a in "$@"; do
    case "$a" in
        --all-sites) ALL_SITES=true ;;
        *)           ARGS+=("$a") ;;
    esac
done
set -- ${ARGS[@]+"${ARGS[@]}"}
[ $# -ge 1 ] || die "검사할 배포 경로나 SIF 를 하나 이상 주세요"

SITE_IMAGES="${KOOD3PLOT_SITE_IMAGES:-/home/koopark/claude/KooSlurmInstallAutomationRefactory/apptainer/compute-node-images}"
SITE_NODES="${KOOD3PLOT_SITE_NODES:-node001 node002}"

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

# 배포 디렉토리의 CLI 래퍼가 **환경변수 없이** 실제로 뜨는지 본다.
#
# 🔴 2026-09-13 배포에서 SIF 의 래퍼(`python/` 경로)를 호스트(`lib/` 구조)에 그대로
#    덮어써, env.sh 를 source 하지 않으면 `No module named koo_sphere_report` 로
#    죽는 상태가 사흘간 남았다. env.sh 를 source 하면 PYTHONPATH 가 우연히 받쳐줘
#    드러나지 않았고, 이 검증기는 VERSION 만 봐서 못 잡았다. 실행해 봐야 안다.
check_wrappers() {             # check_wrappers <배포 디렉토리>
    local dir="$1" w n rc out bad=0 total=0
    for w in "$dir"/bin/koo_*_report; do
        [ -f "$w" ] || continue
        total=$((total + 1))
        n="$(basename "$w")"
        # 깨끗한 환경 — 사용자의 PYTHONPATH·env.sh 가 가려 주지 못하게
        out="$(env -i PATH=/usr/bin:/bin HOME="${HOME:-/tmp}" LANG=C.UTF-8 \
               timeout 120 "$w" --help 2>&1)"
        rc=$?
        if [ "$rc" -ne 0 ]; then
            [ "$bad" -eq 0 ] && echo "   래퍼 실행 확인 (환경변수 없이 --help):"
            echo "   ✗ ${n} — exit ${rc}: $(tail -1 <<< "$out" | cut -c1-100)"
            bad=$((bad + 1))
        fi
    done
    if [ "$total" -eq 0 ]; then
        echo "   (bin/koo_*_report 래퍼가 없어 실행 확인을 건너뜁니다)"
    elif [ "$bad" -eq 0 ]; then
        echo "   ✓ 래퍼 ${total}개 모두 환경변수 없이 실행됨"
    else
        echo "     래퍼가 모듈을 못 찾습니다 — 호스트는 lib/ 구조인데 python/ 경로를"
        echo "     가리키는지 확인하세요 (scripts/deploy_from_sif.sh 가 호스트 형식으로 생성합니다)"
        fails=$((fails + bad))
    fi
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
        check_wrappers "$target"

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

# ── 배포 지점 대조 (--all-sites) ─────────────────────────────────────────
# VERSION 이 아니라 **sha256** 으로 본다. 지점에 놓인 것은 SIF 파일 자체이고,
# 같은 커밋을 두 번 빌드해도 바이트는 다르다 — 실제로 배포된 그 파일인지를 물어야 한다.
check_sites() {                # check_sites <기준 SIF>
    local ref="$1" name want got
    name="$(basename "$ref")"
    want="$(sha256sum "$ref" 2>/dev/null | cut -d' ' -f1)"
    [ -n "$want" ] || { echo "   ✗ 기준 SIF 를 읽지 못했습니다: $ref"; fails=$((fails + 1)); return; }
    echo ""
    echo "배포 지점 대조 — ${name}  (${want:0:12}…)"

    # ③ 노드 재설치 원본
    if [ -f "${SITE_IMAGES}/${name}" ]; then
        got="$(sha256sum "${SITE_IMAGES}/${name}" | cut -d' ' -f1)"
        if [ "$got" = "$want" ]; then echo "   ✓ compute-node-images"
        else
            echo "   ✗ compute-node-images 가 다른 판입니다 (${got:0:12}…)"
            echo "     노드를 재설치하면 이 판이 깔립니다"
            fails=$((fails + 1))
        fi
    else
        echo "   ✗ compute-node-images 에 ${name} 이 없습니다 (${SITE_IMAGES})"
        fails=$((fails + 1))
    fi

    # ④ 노드 로컬 — 헤드 포함
    for h in head ${SITE_NODES}; do
        if [ "$h" = head ]; then got="$(sha256sum "/opt/apptainers/${name}" 2>/dev/null | cut -d' ' -f1)"
        else got="$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$h" "sha256sum '/opt/apptainers/${name}' 2>/dev/null | cut -d' ' -f1" 2>/dev/null)"
        fi
        if [ -z "$got" ]; then
            echo "   ✗ ${h}: /opt/apptainers/${name} 를 확인하지 못했습니다"
            fails=$((fails + 1))
        elif [ "$got" = "$want" ]; then
            echo "   ✓ ${h}:/opt/apptainers"
        else
            echo "   ✗ ${h}: 다른 판입니다 (${got:0:12}…) — 이 노드가 실제로 실행하는 이미지입니다"
            fails=$((fails + 1))
        fi
    done
}

if $ALL_SITES; then
    site_ref=""
    for t in "$@"; do [ -f "$t" ] && site_ref="$t"; done
    if [ -z "$site_ref" ]; then
        echo ""
        echo "✗ --all-sites 에는 기준이 될 SIF 를 인자로 주어야 합니다"
        fails=$((fails + 1))
    else
        check_sites "$site_ref"
    fi
fi

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
