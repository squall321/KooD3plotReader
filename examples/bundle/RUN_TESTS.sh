#!/usr/bin/env bash
# 번들 실데이터로 후처리 3종을 실제 실행해 검증하는 스크립트 (예제 번들에 동봉)
#
# 필요: SmartTwinPostprocessor 배포본.
#   source <배포본>/env.sh   또는   export SMARTTWIN_POST_HOME=<배포본>
#
# 이전 판은 `set -e` 를 켜 두고도 각 단계를 `| tail` 로 감쌌다. 파이프의 종료
# 상태는 마지막 명령(tail)의 것이라 단계가 전부 실패해도 "전부 완료" 를 찍고
# exit 0 으로 끝났다. 여기서는 pipefail 을 켜고, 각 단계의 종료 상태와 실제
# 산출물 존재를 둘 다 확인한다.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
POST="${SMARTTWIN_POST_HOME:-${KOOD3PLOT_HOME:-/data/SmartTwinPostprocessor}}"

die() { echo "오류: $*" >&2; exit 1; }

# ── 사전 확인 — 무엇이 없는지 말하고 끝낸다 (침묵 종료 금지) ────────────
resolve() {           # resolve <이름> → 실행 가능한 경로를 stdout 으로
    local name="$1" p
    p="$POST/bin/$name"
    if [ -x "$p" ]; then echo "$p"; return 0; fi
    if p="$(command -v "$name" 2>/dev/null)"; then echo "$p"; return 0; fi
    return 1
}
MISSING=()
UA="$(resolve unified_analyzer)"   || MISSING+=("unified_analyzer")
SPH="$(resolve koo_sphere_report)" || MISSING+=("koo_sphere_report")
IMP="$(resolve koo_impact_report)" || MISSING+=("koo_impact_report")
if [ ${#MISSING[@]} -gt 0 ]; then
    die "다음 실행 파일을 찾지 못했습니다: ${MISSING[*]}
  찾아본 곳: $POST/bin/  그리고 PATH
  해결 방법:
    1) SmartTwinPostprocessor 배포본을 설치한 뒤
       source <배포본>/env.sh
    2) 또는  export SMARTTWIN_POST_HOME=<배포본 경로>
  그런 다음 이 스크립트를 다시 실행하세요."
fi

OUT="$HERE/_test_out"
rm -rf "$OUT"; mkdir -p "$OUT"

# 경로 치환은 python 으로 한다. sed 는 치환문의 & 를 매치문자열로 확장하고
# 구분자 | 가 든 경로에서 깨진다 — 'R&D' 같은 폴더에서 조용히 잘못된 경로가 됐다.
python3 - "$HERE/03_deep_report/real_data/test_config.yaml" "$OUT/deep_cfg.yaml" \
         "$HERE/01_full_angle_drop/real_data/run_truncated/d3plot" "$OUT/deep" <<'PY'
import pathlib, sys
src, dst, d3, out = sys.argv[1:5]
text = pathlib.Path(src).read_text(encoding="utf-8")
text = text.replace("__D3PLOT__", d3).replace("__OUT__", out)
pathlib.Path(dst).write_text(text, encoding="utf-8")
PY

echo "== [1/3] 딥/세트 분석 — 전각도 절단 d3plot (실제 20상태) =="
"$UA" --config "$OUT/deep_cfg.yaml" > "$OUT/step1.log" 2>&1 \
    || die "[1/3] unified_analyzer 실패 (exit $?) — 로그: $OUT/step1.log"
tail -3 "$OUT/step1.log"
SET_DIR="$OUT/deep/set_reports/example_set"
[ -f "$SET_DIR/metrics.json" ] \
    || die "[1/3] 산출물이 없습니다: $SET_DIR/metrics.json (로그: $OUT/step1.log)"
echo "   → $SET_DIR/ (metrics.json + CSV + peak PNG)"

echo "== [2/3] 전각도 스피어 레포트 — report.json(1144각도 원본) → HTML 재생성 =="
"$SPH" --from-json "$HERE/01_full_angle_drop/real_data/report.json" \
       -o "$OUT/sphere_report.html" --format html > "$OUT/step2.log" 2>&1 \
    || die "[2/3] koo_sphere_report 실패 (exit $?) — 로그: $OUT/step2.log"
tail -1 "$OUT/step2.log"
[ -s "$OUT/sphere_report.html" ] \
    || die "[2/3] 산출물이 없습니다: $OUT/sphere_report.html (로그: $OUT/step2.log)"
echo "   → $OUT/sphere_report.html (브라우저로 열어 확인)"

echo "== [3/3] 부분충격 임팩트 레포트 — impact_payload.json(25위치 사이드카) → HTML 재렌더 =="
# 주의: --from-json 입력은 impact_payload.json (HTML 옆 사이드카).
#       impact_report.json 은 요약 데이터용이라 재렌더 입력이 아니다.
cp "$HERE/02_partial_impact/real_data/impact_payload.json" "$OUT/"
# 세트 미디어(PNG/MP4)는 HTML 기준 상대경로다. 같이 옮기지 않으면 SET 탭의
# 이미지가 전부 깨진 채로 '완료' 안내가 나간다.
cp -r "$HERE/02_partial_impact/real_data/impact_report_data" "$OUT/"
"$IMP" --from-json "$OUT/impact_payload.json" \
       -o "$OUT/impact_report.html" > "$OUT/step3.log" 2>&1 \
    || die "[3/3] koo_impact_report 실패 (exit $?) — 로그: $OUT/step3.log"
tail -1 "$OUT/step3.log"
[ -s "$OUT/impact_report.html" ] \
    || die "[3/3] 산출물이 없습니다: $OUT/impact_report.html (로그: $OUT/step3.log)"
echo "   → $OUT/impact_report.html"

# 세트 미디어가 실제로 참조 가능한지 확인 — 깨진 이미지를 성공으로 안내하지 않는다
python3 - "$OUT/impact_report.html" "$OUT" <<'PY'
import pathlib, re, sys
html, out = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"), pathlib.Path(sys.argv[2])
refs = sorted(set(re.findall(r'impact_report_data/[A-Za-z0-9_./-]+', html)))
missing = [r for r in refs if not (out / r).exists()]
print(f"   세트 미디어 참조 {len(refs)}개 중 결측 {len(missing)}개")
if missing:
    print("   결측 예: " + ", ".join(missing[:3]), file=sys.stderr)
    sys.exit(1)
PY

echo "전부 완료 — 산출물: $OUT/"
