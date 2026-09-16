#!/usr/bin/env bash
# verify_package.sh 가 "막으려는 사건" 을 실제로 잡는지 검증하는 시험
#
# 왜 있나 — 이번 작업에서 검증 도구가 자기 목적을 못 지킨 사례가 세 번 나왔다.
#   ① echo|grep -q + pipefail 의 SIGPIPE 로 정상 아카이브를 거짓 실패시킴
#   ② 배포 검증이 대상 간 대조를 안 해 호스트 vs SIF 불일치를 놓침
#   ③ "빠진 것" 만 보고 "들어가면 안 되는 것" 을 안 봐 22GB 아카이브를 통과시킴
# 검증기에도 시험이 필요하다.
#
# 사용법: tests/deploy/test_verify_package.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VP="$HERE/../../scripts/verify_package.sh"
[ -x "$VP" ] || { echo "verify_package.sh 를 찾지 못했습니다: $VP"; exit 2; }

W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT
fails=0

mk_good() {                     # mk_good <디렉토리>
    local d="$1/SmartTwinPostprocessor"
    mkdir -p "$d/bin" "$d/lib/koo_deep_report" "$d/lib/koo_sphere_report"
    printf 'KooD3plotReader Post-Processing Module\nVersion:    abc1234\nBuilt:      2026-09-13T00:00:00Z\n' > "$d/VERSION"
    echo x > "$d/env.sh"
    for b in unified_analyzer koo_deep_report koo_sphere_report post_analyze; do echo x > "$d/bin/$b"; done
    echo x > "$d/lib/koo_deep_report/__init__.py"
    echo x > "$d/lib/koo_sphere_report/__init__.py"
}

check() {                       # check <이름> <기대 exit> <tar 경로>
    local name="$1" want="$2" tarball="$3"
    "$VP" "$tarball" > /dev/null 2>&1
    local got=$?
    if [ "$got" -eq "$want" ]; then
        echo "  OK  $name (exit $got)"
    else
        echo "  NG  $name — exit $got, 기대 $want"
        fails=$((fails + 1))
    fi
}

# ① 정상 아카이브는 통과해야 한다 (SIGPIPE 거짓 실패 회귀 방지)
mk_good "$W/a"
(cd "$W/a" && tar czf "$W/good.tar.gz" SmartTwinPostprocessor)
check "정상 아카이브는 통과" 0 "$W/good.tar.gz"

# ② VERSION 이 빠지면 실패 (v30~v32 에서 실제로 일어난 사건)
mk_good "$W/b"; rm "$W/b/SmartTwinPostprocessor/VERSION"
(cd "$W/b" && tar czf "$W/nover.tar.gz" SmartTwinPostprocessor)
check "VERSION 누락을 잡는다" 1 "$W/nover.tar.gz"

# ③ 지난 tar/SIF 를 삼키면 실패 (22GB 사건)
mk_good "$W/c"
echo dummy > "$W/c/SmartTwinPostprocessor/SmartTwinPostprocessor_20260828_v29.tar.gz"
(cd "$W/c" && tar czf "$W/selfpack.tar.gz" SmartTwinPostprocessor)
check "자기 자신을 삼킨 아카이브를 잡는다" 1 "$W/selfpack.tar.gz"
mk_good "$W/c2"
echo dummy > "$W/c2/SmartTwinPostprocessor/SmartTwinPostprocessor.sif"
(cd "$W/c2" && tar czf "$W/sifpack.tar.gz" SmartTwinPostprocessor)
check "SIF 를 삼킨 아카이브를 잡는다" 1 "$W/sifpack.tar.gz"

# ④ 바이너리가 빠지면 실패 — 목록 앞쪽 항목이라 SIGPIPE 결함이 있으면 이게 오작동했다
mk_good "$W/d"; rm "$W/d/SmartTwinPostprocessor/bin/unified_analyzer"
(cd "$W/d" && tar czf "$W/nobin.tar.gz" SmartTwinPostprocessor)
check "bin 누락을 잡는다" 1 "$W/nobin.tar.gz"

# ⑤ Version 이 unknown 이면 실패 (추적 불가 빌드)
mk_good "$W/e"
sed -i 's/^Version:.*/Version:    unknown/' "$W/e/SmartTwinPostprocessor/VERSION"
(cd "$W/e" && tar czf "$W/unknown.tar.gz" SmartTwinPostprocessor)
check "unknown 버전을 잡는다" 1 "$W/unknown.tar.gz"

# ⑥ 최상위가 여러 개면 실패
mk_good "$W/f"; mkdir -p "$W/f/Other"; echo x > "$W/f/Other/f"
(cd "$W/f" && tar czf "$W/two.tar.gz" SmartTwinPostprocessor Other)
check "최상위 2개를 잡는다" 1 "$W/two.tar.gz"

# ⑥b 래퍼가 SIF 구조(python/)를 가리키면 실패 (2026-09-13 배포 회귀)
mk_good "$W/g"
printf '#!/bin/bash\nexport PYTHONPATH="${MODULE_DIR}/python/koo_deep_report"\nexec python3 -m koo_deep_report "$@"\n' \
    > "$W/g/SmartTwinPostprocessor/bin/koo_deep_report"
(cd "$W/g" && tar czf "$W/pywrap.tar.gz" SmartTwinPostprocessor)
check "python/ 경로 래퍼를 잡는다" 1 "$W/pywrap.tar.gz"
mk_good "$W/h"
printf '#!/bin/bash\nexport PYTHONPATH="${SMARTTWIN_POST_HOME}/lib/koo_deep_report"\nexec python3 -m koo_deep_report "$@"\n' \
    > "$W/h/SmartTwinPostprocessor/bin/koo_deep_report"
(cd "$W/h" && tar czf "$W/libwrap.tar.gz" SmartTwinPostprocessor)
check "lib/ 경로 래퍼는 통과" 0 "$W/libwrap.tar.gz"

# ⑦ 손상 아카이브 / 없는 파일
head -c 200 "$W/good.tar.gz" > "$W/broken.tar.gz"
check "손상 아카이브를 잡는다" 1 "$W/broken.tar.gz"
check "없는 파일을 잡는다" 1 "$W/nope.tar.gz"

echo ""
if [ "$fails" -gt 0 ]; then
    echo "[FAIL] 실패 ${fails} 건"
    exit 1
fi
echo "[PASS] 실패 0 건"
