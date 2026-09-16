#!/usr/bin/env bash
# 배포 아카이브(.tar.gz)가 필수 구성요소를 빠짐없이 담았는지 검사하는 도구
#
# 왜 있나 — v30(2026-09-08) 배포 tar 에서 VERSION 이 조용히 빠졌다. tar 를 풀어도
# 호스트의 옛 VERSION 이 덮이지 않아 2주 동안 `eaffe54`(8-28) 를 가리켰고, 그걸
# 믿은 후처리에서 이미 있는 기능을 "없다" 고 판단해 임시 스크립트로 다시 만들었다.
# 파일 하나가 빠져도 아무도 모르는 구조가 원인이므로, 묶은 결과를 기계가 본다.
#
# 사용법:
#   scripts/verify_package.sh <tar.gz> [<tar.gz> ...]
# 종료 상태: 전부 통과 0, 하나라도 실패 1

set -uo pipefail

# 아카이브 최상위 디렉토리(예: SmartTwinPostprocessor/) 아래 있어야 하는 것들.
# 경로는 정규식이 아니라 '최상위/이하' 접미사로 맞춘다.
REQUIRED_FILES=(
    "VERSION"
    "env.sh"
    "bin/unified_analyzer"
    "bin/koo_deep_report"
    "bin/koo_sphere_report"
    "bin/post_analyze"
)
REQUIRED_DIRS=(
    "lib/koo_deep_report"
    "lib/koo_sphere_report"
)

fail_total=0

for tarball in "$@"; do
    echo "── $(basename "$tarball")"
    if [ ! -f "$tarball" ]; then
        echo "   ✗ 파일이 없습니다: $tarball"
        fail_total=$((fail_total + 1))
        continue
    fi

    listing="$(tar tzf "$tarball" 2>/dev/null)"
    if [ -z "$listing" ]; then
        echo "   ✗ 아카이브를 읽지 못했습니다 (손상 또는 tar.gz 아님)"
        fail_total=$((fail_total + 1))
        continue
    fi

    # 최상위 디렉토리 — 여러 개면 구조가 예상과 다르다는 뜻이라 그대로 알린다
    roots="$(awk -F/ '{print $1}' <<< "$listing" | sort -u)"
    n_roots="$(wc -l <<< "$roots")"
    if [ "$n_roots" -ne 1 ]; then
        echo "   ✗ 최상위 디렉토리가 1개가 아닙니다: $(tr '\n' ' ' <<< "$roots")"
        fail_total=$((fail_total + 1))
        continue
    fi
    root="$roots"

    # 🔴 `echo "$listing" | grep -q` 로 쓰면 안 된다. grep -q 는 첫 매치에서 즉시
    #    끝나고 echo 가 SIGPIPE 로 죽는데, pipefail 이 그걸 파이프 실패로 만든다.
    #    목록 앞쪽에 있는 항목일수록 "없다" 는 거짓 실패가 난다 (실제로 겪었다).
    #    here-string 을 써서 파이프 자체를 없앤다.
    missing=()
    for f in "${REQUIRED_FILES[@]}"; do
        grep -qxF "${root}/${f}" <<< "$listing" || missing+=("$f")
    done
    for d in "${REQUIRED_DIRS[@]}"; do
        # 디렉토리는 항목 자체가 없을 수도 있으니 하위 파일 존재로 본다
        grep -q "^${root}/${d}/" <<< "$listing" || missing+=("$d/")
    done

    if [ ${#missing[@]} -gt 0 ]; then
        echo "   ✗ 빠진 구성요소 ${#missing[@]}개: ${missing[*]}"
        echo "     (아카이브 최상위: ${root}/, 총 $(wc -l <<< "$listing") 항목)"
        fail_total=$((fail_total + 1))
        continue
    fi

    # 🔴 아카이브가 지난 배포 tar 나 SIF 를 삼켰는지 본다. 배포 디렉토리를
    #    통째로 묶으면 그렇게 되고, 필수 파일은 다 있으므로 위 검사는 통과한다
    #    (550MB 여야 할 것이 22GB 로 나온 적이 있다).
    selfpack="$(grep -cE '\.(tar\.gz|tgz|sif)$' <<< "$listing" || true)"
    if [ "${selfpack:-0}" -gt 0 ]; then
        echo "   ✗ 아카이브·이미지 파일 ${selfpack}개를 담고 있습니다 "
        echo "     (배포 디렉토리를 통째로 묶어 지난 tar/SIF 까지 들어갔습니다)"
        echo "     예: $(grep -E '\.(tar\.gz|tgz|sif)$' <<< "$listing" | head -2 | tr '\n' ' ')"
        fail_total=$((fail_total + 1))
        continue
    fi

    # 🔴 래퍼가 SIF 구조(`python/`)를 가리키면 호스트(`lib/` 구조)에서 모듈을 못
    #    찾는다. 2026-09-13 배포가 그렇게 깨졌고 v33 아카이브에도 들어갔다.
    #    래퍼만 골라 한 번에 풀어 본다 (파일마다 풀면 550MB gzip 을 여러 번 읽는다).
    wtmp="$(mktemp -d)"
    tar xzf "$tarball" -C "$wtmp" --wildcards "${root}/bin/koo_*_report" 2>/dev/null || true
    badw=""
    for w in "$wtmp/${root}"/bin/koo_*_report; do
        [ -f "$w" ] || continue
        if grep -q '/python/koo_' "$w"; then
            badw="${badw} $(basename "$w")"
        fi
    done
    rm -rf "$wtmp"
    if [ -n "$badw" ]; then
        echo "   ✗ 래퍼가 python/ 경로를 가리킵니다 (호스트는 lib/ 구조):${badw}"
        echo "     scripts/deploy_from_sif.sh 로 배포한 디렉토리를 묶으세요"
        fail_total=$((fail_total + 1))
        continue
    fi

    # VERSION 내용까지 본다 — 파일만 있고 'unknown' 이면 추적이 안 된다
    ver="$(tar xzOf "$tarball" "${root}/VERSION" 2>/dev/null | sed -n 's/^Version:[[:space:]]*//p' | head -1)"
    built="$(tar xzOf "$tarball" "${root}/VERSION" 2>/dev/null | sed -n 's/^Built:[[:space:]]*//p' | head -1)"
    if [ -z "$ver" ] || [ "$ver" = "unknown" ]; then
        echo "   ✗ VERSION 의 Version 이 비었거나 unknown 입니다 (git describe 실패 상태로 빌드됨)"
        fail_total=$((fail_total + 1))
        continue
    fi

    echo "   ✓ 통과 — Version: ${ver}  Built: ${built:-?}"
done

if [ "$fail_total" -gt 0 ]; then
    echo ""
    echo "실패 ${fail_total}건 — 이 아카이브로 배포하면 안 됩니다."
    exit 1
fi
exit 0
