#!/usr/bin/env bash
# post_analyze.sh 의 재사용(스킵) 판정과 그룹별 출력 경로가 실제로 맞는지 검증하는 시험
#
# 왜 있나 — 오케스트레이터가 "이미 있으니 스킵" 을 잘못 내면, 틀린 숫자가 담긴
# 옛 산출물이 보고서로 그대로 흘러간다. 2026-09 전수 조사에서 두 건이 확인됐다.
#   ① UA_OUTPUT_SCHEMA 가 분석기 수정(값이 달라진 수정)을 따라가지 않아,
#      옛 빌드로 낸 analysis_results/ 가 영원히 재사용됐다.
#   ② --deep-only / IMPACT flat 경로가 ${_num_groups:-1} 로 그룹 수를 1 로 가정해
#      Run_x/Output 과 Run_x/Output2 가 같은 deep_reports/Run_x 를 쓰고,
#      뒤엣것이 '스킵' 으로 사라졌다.
# 둘 다 정상 케이스(단일 그룹·최초 분석)에서는 아무 증상이 없다. 그래서 시험은
# "막으려는 그 사건을 잡는가" 로 짠다.
#
# 실제 바이너리는 쓰지 않는다 — unified_analyzer / koo_deep_report / koo_sphere_report
# 대역을 PATH 에 두고 호출 횟수와 출력 경로만 본다.
#
# 사용법: tests/scripts/test_post_analyze.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PA="$HERE/../../scripts/post_analyze.sh"
[ -x "$PA" ] || { echo "post_analyze.sh 를 찾지 못했습니다: $PA"; exit 2; }

W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT
fails=0

# ============================================================
# 대역 바이너리
# ============================================================
BIN="$W/bin"
mkdir -p "$BIN"

cat > "$BIN/unified_analyzer" << 'STUBEOF'
#!/usr/bin/env bash
# 시험용 대역 — YAML 의 output.directory 에 analysis_result.json 을 쓰고 호출을 기록한다
set -uo pipefail
if [ "${1:-}" = "--capabilities" ]; then
    if [ -z "${STUB_UA_COMMIT:-}" ]; then exit 1; fi   # 옛 빌드(플래그 없음) 흉내
    printf '{\n  "tool": "unified_analyzer",\n  "version": "%s"\n}\n' "${STUB_UA_COMMIT}"
    exit 0
fi
cfg=""
while [ $# -gt 0 ]; do
    case "$1" in
        --config) cfg="${2:-}"; shift 2 ;;
        *) shift ;;
    esac
done
[ -n "$cfg" ] || exit 1
outdir=$(sed -n 's/^  directory: "\(.*\)"$/\1/p' "$cfg")
d3=$(sed -n 's/^  d3plot: "\(.*\)"$/\1/p' "$cfg")
[ -n "$outdir" ] || exit 1
mkdir -p "$outdir"
{
    echo '{'
    echo '  "metadata": {'
    echo "    \"d3plot_path\": \"${d3}\","
    echo "    \"tool_commit\": \"${STUB_UA_COMMIT:-}\","
    echo '    "num_states": 3'
    echo '  }'
    echo '}'
} > "$outdir/analysis_result.json"
echo "ua ${d3} -> ${outdir}" >> "${STUB_LOG}"
STUBEOF

cat > "$BIN/koo_deep_report" << 'STUBEOF'
#!/usr/bin/env bash
# 시험용 대역 — --output 디렉토리에 result.json 을 쓰고 호출을 기록한다
set -uo pipefail
d3=""; out=""
while [ $# -gt 0 ]; do
    case "$1" in
        --output) out="${2:-}"; shift 2 ;;
        --config|--yield-stress) shift 2 ;;
        --*) shift ;;
        *) if [ -z "$d3" ]; then d3="$1"; fi; shift ;;
    esac
done
[ -n "$out" ] || exit 1
mkdir -p "$out"
printf '{"d3plot": "%s"}\n' "$d3" > "$out/result.json"
echo "deep ${d3} -> ${out}" >> "${STUB_LOG}"
STUBEOF

cat > "$BIN/koo_sphere_report" << 'STUBEOF'
#!/usr/bin/env bash
set -uo pipefail
echo "sphere $*" >> "${STUB_LOG}"
STUBEOF

chmod +x "$BIN/unified_analyzer" "$BIN/koo_deep_report" "$BIN/koo_sphere_report"
export PATH="$BIN:$PATH"

# ============================================================
# 헬퍼
# ============================================================
mk_tree() {                     # mk_tree <test_dir> <output 하위 d3plot 경로...>
    local t="$1"; shift
    mkdir -p "$t/output"
    local p
    for p in "$@"; do
        mkdir -p "$(dirname "$t/output/$p")"
        printf 'fake-d3plot\n' > "$t/output/$p"
    done
}

mk_config() {                   # mk_config <test_dir>
    printf 'version: "2.0"\nperformance:\n  threads: 1\n' > "$1/common_analysis.yaml"
}

run_pa() {                      # run_pa <test_dir> <옵션...> — 호출 기록을 새로 시작한다
    local t="$1"; shift
    export STUB_LOG="$W/calls.log"
    : > "$STUB_LOG"
    "$PA" "$t" "$@" > "$W/last_run.log" 2>&1
    return 0
}

n_calls() {                     # n_calls <접두어: ua|deep|sphere>
    grep -c "^$1 " "$W/calls.log" 2>/dev/null || true
}

chk() {                         # chk <이름> <기대> <실제>
    if [ "$3" = "$2" ]; then
        echo "  OK  $1"
    else
        echo "  NG  $1 — '$3', 기대 '$2'"
        fails=$((fails + 1))
    fi
}

chk_file() {                    # chk_file <이름> <있어야 하는 파일>
    if [ -f "$2" ]; then
        echo "  OK  $1"
    else
        echo "  NG  $1 — 없음: $2"
        fails=$((fails + 1))
    fi
}

chk_no_file() {                 # chk_no_file <이름> <없어야 하는 파일>
    if [ ! -e "$2" ]; then
        echo "  OK  $1"
    else
        echo "  NG  $1 — 있으면 안 되는데 있음: $2"
        fails=$((fails + 1))
    fi
}

export STUB_UA_COMMIT="aaaa111"

# ============================================================
# ① --deep-only + 다중 그룹 — 그룹별 폴더로 갈려야 한다
# ============================================================
echo "[1] --deep-only 다중 그룹 (Output / Output2)"
T1="$W/t1"
mk_tree "$T1" Run_a/Output/d3plot Run_a/Output2/d3plot \
              Run_b/Output/d3plot Run_b/Output2/d3plot
run_pa "$T1" --deep-only --no-render
chk "deep 호출 4회 (그룹 4개 모두)" 4 "$(n_calls deep)"
chk_file "Output/Run_a"  "$T1/deep_reports/Output/Run_a/result.json"
chk_file "Output/Run_b"  "$T1/deep_reports/Output/Run_b/result.json"
chk_file "Output2/Run_a" "$T1/deep_reports/Output2/Run_a/result.json"
chk_file "Output2/Run_b" "$T1/deep_reports/Output2/Run_b/result.json"
chk_no_file "그룹 없는 deep_reports/Run_a 는 만들지 않는다" "$T1/deep_reports/Run_a"

echo "[1b] 같은 조건 재실행 — 전부 스킵"
run_pa "$T1" --deep-only --no-render
chk "deep 호출 0회" 0 "$(n_calls deep)"

# ============================================================
# ② --deep-only + 단일 그룹 — 기존 경로 유지 (회귀 방지)
# ============================================================
echo "[2] --deep-only 단일 그룹"
T2="$W/t2"
mk_tree "$T2" Run_a/Output/d3plot Run_b/Output/d3plot
run_pa "$T2" --deep-only --no-render
chk "deep 호출 2회" 2 "$(n_calls deep)"
chk_file "deep_reports/Run_a" "$T2/deep_reports/Run_a/result.json"
chk_no_file "단일 그룹은 하위 폴더를 만들지 않는다" "$T2/deep_reports/Output"

# ============================================================
# ③ deep 산출물이 낡으면(이 스크립트가 낸 표식이 없으면) 다시 만든다
# ============================================================
echo "[3] 옛 deep 산출물 재사용 금지"
T3="$W/t3"
mk_tree "$T3" Run_x/d3plot
mkdir -p "$T3/deep_reports/Run_x"
printf '{"old": true}\n' > "$T3/deep_reports/Run_x/result.json"
run_pa "$T3" --deep-only --no-render
chk "옛 result.json 은 다시 만든다" 1 "$(n_calls deep)"
run_pa "$T3" --deep-only --no-render
chk "방금 만든 것은 스킵" 0 "$(n_calls deep)"

# ============================================================
# ④ Step 1 — 옛 마커("2" 한 줄)는 낡은 것이다
# ============================================================
echo "[4] Step 1 옛 스키마 마커 재분석"
T4="$W/t4"
mk_tree "$T4" Run_x/d3plot
mk_config "$T4"
mkdir -p "$T4/analysis_results/Run_x"
printf '{"metadata": {"num_states": 3}}\n' > "$T4/analysis_results/Run_x/analysis_result.json"
printf '2\n' > "$T4/analysis_results/Run_x/.ua_schema"
run_pa "$T4" --sphere-only
chk "옛 스키마 산출물은 다시 분석" 1 "$(n_calls ua)"

echo "[4b] 같은 분석기·같은 d3plot 이면 스킵"
run_pa "$T4" --sphere-only
chk "재분석 안 함" 0 "$(n_calls ua)"

# ============================================================
# ⑤ 분석기 커밋이 바뀌면 다시 분석한다
# ============================================================
echo "[5] 분석기 커밋 변경"
STUB_UA_COMMIT="bbbb222" run_pa "$T4" --sphere-only
chk "커밋이 바뀌면 재분석" 1 "$(n_calls ua)"

# ============================================================
# ⑥ d3plot 을 다시 돌리면(산출물보다 새로우면) 다시 분석한다
# ============================================================
echo "[6] d3plot 재시뮬레이션"
run_pa "$T4" --sphere-only          # 먼저 최신 상태로 맞춘다
touch -d "2030-01-01 00:00:00" "$T4/output/Run_x/d3plot"
run_pa "$T4" --sphere-only
chk "새 d3plot 은 재분석" 1 "$(n_calls ua)"

# ============================================================
# ⑦ --no-schema-check 는 예전대로 '있으면 스킵'
# ============================================================
echo "[7] --no-schema-check"
T7="$W/t7"
mk_tree "$T7" Run_x/d3plot
mk_config "$T7"
mkdir -p "$T7/analysis_results/Run_x"
printf '{"metadata": {"num_states": 3}}\n' > "$T7/analysis_results/Run_x/analysis_result.json"
run_pa "$T7" --sphere-only --no-schema-check
chk "존재하면 스킵" 0 "$(n_calls ua)"

# ============================================================
# ⑧ 기본 파이프라인(unified → sphere → deep) + 다중 그룹
# ============================================================
echo "[8] 기본 파이프라인 다중 그룹"
T8="$W/t8"
mk_tree "$T8" Run_a/Output/d3plot Run_a/Output2/d3plot
mk_config "$T8"
run_pa "$T8" --no-render
chk "ua 호출 2회" 2 "$(n_calls ua)"
chk "deep 호출 2회" 2 "$(n_calls deep)"
chk_file "analysis_results/Output/Run_a"  "$T8/analysis_results/Output/Run_a/analysis_result.json"
chk_file "analysis_results/Output2/Run_a" "$T8/analysis_results/Output2/Run_a/analysis_result.json"
chk_file "deep_reports/Output/Run_a"      "$T8/deep_reports/Output/Run_a/result.json"
chk_file "deep_reports/Output2/Run_a"     "$T8/deep_reports/Output2/Run_a/result.json"
run_pa "$T8" --no-render
chk "재실행은 ua 0회" 0 "$(n_calls ua)"
chk "재실행은 deep 0회" 0 "$(n_calls deep)"

# ============================================================
# ⑨ 분석기 커밋을 알 수 없어도 무한 재분석에 빠지지 않는다
#    (--capabilities 가 없는 옛 빌드)
# ============================================================
echo "[9] 커밋을 알 수 없는 분석기"
T9="$W/t9"
mk_tree "$T9" Run_x/d3plot
mk_config "$T9"
STUB_UA_COMMIT="" run_pa "$T9" --sphere-only
chk "최초 분석 1회" 1 "$(n_calls ua)"
STUB_UA_COMMIT="" run_pa "$T9" --sphere-only
chk "재실행은 스킵 (무한 재분석 없음)" 0 "$(n_calls ua)"
if grep -q "분석기 커밋: 알 수 없음" "$W/last_run.log"; then
    echo "  OK  커밋을 모른다는 사실을 화면에 남긴다"
else
    echo "  NG  커밋 미상 사유가 화면에 없다"
    fails=$((fails + 1))
fi

echo ""
if [ "$fails" -gt 0 ]; then
    echo "[FAIL] 실패 ${fails} 건"
    exit 1
fi
echo "[PASS] 실패 0 건"
