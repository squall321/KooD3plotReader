#!/usr/bin/env bash
# 커밋이 바뀐 뒤 재설정 없이 빌드해도 각인된 버전이 따라오는지 검사하는 시험
#
# 왜 필요한가. 버전을 CMake **설정** 시점에 한 번만 읽으면, 그 뒤 커밋을 쌓고
# `make` 만 한 바이너리는 옛 커밋을 자기 버전이라고 답한다. 산출물의 tool_commit
# 과 `--skip-existing` 의 '분석기가 바뀌었나' 판정이 모두 그 값을 믿는다
# (실측 2026-09-17: 로컬 빌드가 9/16 커밋 f3fd09b 를 찍었다).
#
# 사용: bash tests/version/test_version_stamp.sh
# 종료: 0 통과 / 1 실패
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="${REPO}/.work/version_stamp"
fails=0

ok()  { echo "  OK  $1"; }
ng()  { echo "  NG  $1"; fails=$((fails + 1)); }

rm -rf "${WORK}"
mkdir -p "${WORK}"

# 저장소를 건드리지 않도록 복제본에서 검사한다 (커밋을 새로 쌓아야 한다).
git clone --quiet --no-hardlinks "${REPO}" "${WORK}/repo" 2>/dev/null || {
    echo "  NG  저장소 복제 실패"; exit 1; }
cd "${WORK}/repo" || exit 1
git config user.email "test@example.com"
git config user.name "version stamp test"

# 복제본은 **커밋된** 상태만 가져온다. 지금 고치는 중인 내용을 검사하려면
# 작업 트리의 미커밋 변경을 옮겨야 한다 — 안 그러면 '고치기 전 코드' 를 시험한다.
# 수정된 파일(diff)과 **새 파일(미추적)** 을 모두 옮긴다. 새 파일을 빼먹으면
# 새로 추가한 스크립트가 없는 채로 빌드가 깨진다 (실제로 한 번 겪었다).
_wip=0
if ! git -C "${REPO}" diff --quiet HEAD -- . ':(exclude).work'; then
    git -C "${REPO}" diff HEAD -- . ':(exclude).work' > "${WORK}/wip.patch"
    git apply "${WORK}/wip.patch" 2>/dev/null || {
        echo "  NG  작업 트리 변경을 복제본에 적용하지 못했다"; exit 1; }
    _wip=1
fi
# -z 로 널 구분해 읽는다 — 한글 파일명이 따옴표로 감싸져 경로가 깨지지 않게.
while IFS= read -r -d '' f; do
    [ -z "${f}" ] && continue
    case "${f}" in .work/*) continue ;; esac
    mkdir -p "$(dirname "${f}")"
    cp "${REPO}/${f}" "${f}" || continue
    _wip=1
done < <(git -C "${REPO}" ls-files --others --exclude-standard -z)
if [ "${_wip}" = 1 ]; then
    git add -A > /dev/null 2>&1
    git commit --quiet -m "test: 작업 트리 미커밋 변경 반영"
    echo "  ..  작업 트리의 미커밋 변경·새 파일을 복제본에 반영했다"
fi

build_dir="${WORK}/repo/build_vs"
cmake -S . -B "${build_dir}" -DCMAKE_BUILD_TYPE=Release \
      -DKOOD3PLOT_BUILD_V4_RENDER=OFF -DKOOD3PLOT_BUILD_TESTS=OFF > "${WORK}/cmake.log" 2>&1 || {
    echo "  NG  cmake 설정 실패 — ${WORK}/cmake.log"; exit 1; }
cmake --build "${build_dir}" -j4 --target unified_analyzer > "${WORK}/build1.log" 2>&1 || {
    echo "  NG  첫 빌드 실패 — ${WORK}/build1.log"; exit 1; }

version_of() {
    "${build_dir}/examples/unified_analyzer" --capabilities 2>/dev/null \
        | python3 -c 'import json,sys; print(json.load(sys.stdin).get("version", ""))'
}

v1="$(version_of)"
head1="$(git rev-parse --short HEAD)"
case "${v1}" in
    *"${head1}"*) ok "첫 빌드가 현재 커밋(${head1})을 각인한다" ;;
    *)            ng "첫 빌드 각인 '${v1}' 에 현재 커밋 ${head1} 이 없다" ;;
esac

# 커밋을 하나 쌓고 **재설정 없이** 다시 빌드한다 (실제 개발 흐름).
echo "// version stamp test $(date +%s%N)" >> src/Version.cpp
git add src/Version.cpp
git commit --quiet -m "test: 버전 각인 검사용 커밋"
head2="$(git rev-parse --short HEAD)"

cmake --build "${build_dir}" -j4 --target unified_analyzer > "${WORK}/build2.log" 2>&1 || {
    echo "  NG  두 번째 빌드 실패 — ${WORK}/build2.log"; exit 1; }
v2="$(version_of)"

case "${v2}" in
    *"${head2}"*) ok "커밋 후 재빌드가 새 커밋(${head2})을 각인한다" ;;
    *)            ng "커밋 후 재빌드 각인이 '${v2}' — 새 커밋 ${head2} 을 못 따라갔다" ;;
esac

# 아무것도 바뀌지 않았으면 다시 빌드해도 각인이 그대로여야 한다 (헛 재링크 방지).
cmake --build "${build_dir}" -j4 --target unified_analyzer > "${WORK}/build3.log" 2>&1
v3="$(version_of)"
[ "${v2}" = "${v3}" ] && ok "변경이 없으면 각인도 그대로 (${v3})" \
                      || ng "변경이 없는데 각인이 바뀌었다 (${v2} → ${v3})"

echo
if [ "${fails}" -eq 0 ]; then
    echo "[PASS]  실패 0 건"
    exit 0
fi
echo "[FAIL]  실패 ${fails} 건"
exit 1
