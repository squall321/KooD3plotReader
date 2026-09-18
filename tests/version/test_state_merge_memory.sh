#!/usr/bin/env bash
# 여러 파일의 상태를 합칠 때 사본을 만들어 피크 메모리가 2배가 되지 않는지 검사하는 시험
#
# 왜 필요한가. d3plot 은 상태를 여러 파일로 나눠 담고 리더가 파일마다 병렬로 읽은 뒤
# 하나로 합친다. 이때 **복사**하면 합치는 순간 같은 데이터가 두 벌 존재해 피크가
# 정확히 2배가 된다. 실측(2026-09-18): 상태 데이터 2.6 GB 짜리 덱에서 피크 5.5 GB,
# 이동으로 바꾼 뒤 2.8 GB. 4952상태 덱은 이 차이가 33 GB 대 68 GB 라 OOM 으로 갈린다.
#
# 사용: bash tests/version/test_state_merge_memory.sh [d3plot]
# 종료: 0 통과 / 1 실패 / 77 덱이 없어 검증 못 함(통과 아님)
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DECK="${1:-/data/koopark/deep_report_timetest/d3plot}"
BIN="${REPO}/build/examples/unified_analyzer"
WORK="${REPO}/.work/state_merge_memory"

[ -x "${BIN}" ] || { echo "  ..  ${BIN} 이 없어 건너뜀 (먼저 빌드하세요)"; exit 77; }
[ -f "${DECK}" ] || { echo "  ..  덱 ${DECK} 이 없어 건너뜀"; exit 77; }

rm -rf "${WORK}"; mkdir -p "${WORK}"
cat > "${WORK}/cfg.yaml" <<EOF
version: "2.0"
input:
  d3plot: "${DECK}"
output:
  directory: "${WORK}/out"
  json: false
  csv: true
performance:
  threads: 4
  surface_defaults: false
analysis_jobs:
  - name: "All Parts Stress"
    type: von_mises
    parts: []
    output_prefix: "stress/all"
EOF

/usr/bin/time -v "${BIN}" --config "${WORK}/cfg.yaml" > "${WORK}/run.log" 2>&1 || {
    echo "  NG  분석 실패 — ${WORK}/run.log"; exit 1; }

peak_kb="$(grep 'Maximum resident set size' "${WORK}/run.log" | awk '{print $NF}')"
states="$(grep -oE 'total states loaded' -m1 "${WORK}/run.log" > /dev/null && \
          grep -oE '[0-9]+ total states loaded' "${WORK}/run.log" | head -1 | awk '{print $1}')"
[ -n "${states:-}" ] || states="$(( $(wc -l < "$(ls "${WORK}/out/stress/"*_von_mises.csv | head -1)") - 1 ))"

# 기준은 **파일 크기**다. 상태는 파일에 float(4바이트)로 있고 메모리에는
# double(8바이트)로 올라오므로 정상 피크는 파일 크기의 약 2배다. 합치면서 사본을
# 만들면 약 4배가 된다. 3배를 한도로 두면 둘이 갈린다.
# (실측 2026-09-18, 같은 덱: 파일 1.31 GB → 수정 전 5.25 GB(4.0배) / 수정 후 2.66 GB(2.0배))
deck_bytes=0
for f in "${DECK}"*; do
    [ -f "${f}" ] || continue
    sz="$(stat -Lc %s "${f}" 2>/dev/null || echo 0)"
    deck_bytes=$((deck_bytes + sz))
done
[ "${deck_bytes}" -gt 0 ] || { echo "  ..  덱 파일 크기를 못 재 건너뜀"; exit 77; }

peak_gb="$(python3 -c "print(f'{int(${peak_kb}) / 1048576:.2f}')")"
deck_gb="$(python3 -c "print(f'{int(${deck_bytes}) / 1073741824:.2f}')")"
ratio="$(python3 -c "print(f'{int(${peak_kb}) * 1024 / int(${deck_bytes}):.2f}')")"

echo "  ..  상태 ${states}개, 덱 파일 ${deck_gb} GB, 피크 ${peak_gb} GB (${ratio}배)"

ok="$(python3 -c "print(1 if float(${ratio}) <= 3.0 else 0)")"
if [ "${ok}" = "1" ]; then
    echo "  OK  피크가 덱 파일의 ${ratio}배 (한도 3.0배) — 합치기에서 사본을 만들지 않는다"
    echo
    echo "[PASS]  실패 0 건"
    exit 0
fi
echo "  NG  피크가 덱 파일의 ${ratio}배 — 한도 3.0배를 넘었다"
echo "      상태를 합칠 때 복사하고 있을 수 있다"
echo "      (src/D3plotReader.cpp 의 병합 루프가 make_move_iterator 를 쓰는지 확인)"
echo
echo "[FAIL]  실패 1 건"
exit 1
