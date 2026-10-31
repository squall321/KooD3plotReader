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

# s1_extract 대역 — 경로에 FAIL_S1 이 들면 실패를 흉내 낸다
cat > "$BIN/s1_extract" << 'STUBEOF'
#!/usr/bin/env bash
d3="$1"; shift
out=""
while [ $# -gt 0 ]; do
    case "$1" in --output) out="$2"; shift 2 ;; *) shift ;; esac
done
echo "s1 ${d3} -> ${out}" >> "${STUB_LOG}"
case "${d3}" in *FAIL_S1*) echo "ERROR: 대역 실패"; exit 1 ;; esac
printf 'fake-s1\n' > "${out}"
printf '{"schema": "kood3plot.s1", "file": "s1.h5"}\n' > "$(dirname "${out}")/s1.json"
STUBEOF
# koo_ontology 대역 — 인자를 그대로 기록하고, 경로에 FAIL_ONTO 가 들면 실패를 흉내 낸다
cat > "$BIN/koo_ontology" << 'STUBEOF'
#!/usr/bin/env bash
echo "onto $*" >> "${STUB_LOG}"
case "$*" in *FAIL_ONTO*) echo "Error: 대역 실패" >&2; exit 1 ;; esac
STUBEOF
chmod +x "$BIN/unified_analyzer" "$BIN/koo_deep_report" "$BIN/koo_sphere_report" "$BIN/s1_extract" "$BIN/koo_ontology"
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

PA_RC=0                         # 직전 run_pa 의 종료 코드

run_pa() {                      # run_pa <test_dir> <옵션...> — 호출 기록을 새로 시작한다
    local t="$1"; shift
    export STUB_LOG="$W/calls.log"
    : > "$STUB_LOG"
    "$PA" "$t" "$@" > "$W/last_run.log" 2>&1
    PA_RC=$?
    # 이번 실행이 Step 1 요약("완료: N / 스킵: M / 실패: K / 전체: T")까지 갔는가.
    # 이 양성 증거가 없으면 뒤따르는 '호출 0회' 단정들은 "올바르게 스킵했다" 와
    # "아무것도 못 하고 죽었다" 를 구분하지 못한다 — 대역 호출 횟수와 파일 존재만
    # 보기 때문이다. 실제로 post_analyze.sh 를 `exit 1` 한 줄로 바꿔도 스킵 계열
    # 단정 9건이 그대로 OK 로 찍혔다.
    #
    # 종료 코드 자체는 단정에 쓰지 않는다 — post_analyze.sh 의 마지막 문장이
    # `[ -f "${TEST_DIR}/report.html" ] && echo …` 라, 대역 sphere 가 report.html 을
    # 만들지 않는 이 시험 환경에서는 정상 완료해도 1 이 나온다. 사유 표시용으로만
    # PA_RC 에 남긴다.
    if ! grep -q '완료: ' "$W/last_run.log"; then
        echo "  NG  실행이 Step 1 요약까지 가지 못했다 (종료 $PA_RC) — post_analyze.sh $*"
        fails=$((fails + 1))
    fi
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

# ============================================================
# ⑩ 커밋 문자열이 같아도 실행 파일이 달라졌으면 다시 분석한다
#    --capabilities 의 "version" 은 CMake **설정 시점**의 git describe 라서
#    `cmake --build build --target unified_analyzer` 로만 다시 빌드하면 값이
#    옛 설정 시점에 얼어붙는다(실측: 5커밋 전 값을 답했다). 커밋만 보면
#    '값만 달라진 수정' 이 통째로 스킵된다.
# ============================================================
echo "[10] 같은 커밋 · 다른 실행 파일"
T10="$W/t10"
mk_tree "$T10" Run_x/d3plot
mk_config "$T10"
run_pa "$T10" --sphere-only
chk "최초 분석 1회" 1 "$(n_calls ua)"
run_pa "$T10" --sphere-only
chk "같은 실행 파일이면 스킵" 0 "$(n_calls ua)"
# 커밋 문자열(STUB_UA_COMMIT)은 그대로 둔 채 실행 파일 내용만 바꾼다 = 증분 빌드
printf '# 값만 달라진 분석기 수정 흉내 — 커밋 문자열은 그대로다\n' >> "$BIN/unified_analyzer"
run_pa "$T10" --sphere-only
chk "실행 파일이 바뀌면 재분석" 1 "$(n_calls ua)"
if grep -q "분석기 실행 파일" "$W/last_run.log"; then
    echo "  OK  재분석 사유로 실행 파일 변경을 남긴다"
else
    echo "  NG  실행 파일 변경 사유가 화면에 없다"
    fails=$((fails + 1))
fi

# ============================================================
# [11] S1 단계 — 켜야만 돌고, 런마다 d3plot 옆에 만들고, 있으면 건너뛰고(--force 면
#      다시), 한 런이 실패해도 끝까지 간다(DynaForge 계약 C-3).
# ============================================================
echo "[11] S1 단계"
T11="$W/t11"
mk_tree "$T11" Run_a/Output/d3plot Run_b/Output/d3plot Run_FAIL_S1/Output/d3plot
mk_config "$T11"
run_pa "$T11" --sphere-only
chk "--s1 없으면 s1_extract 를 부르지 않는다" 0 "$(n_calls s1)"
run_pa "$T11" --sphere-only --s1-opts "--floor-part 23 --units mm,t,s,MPa"
chk "--s1-opts 만으로 켜진다 — 런 셋 모두 부른다" 3 "$(n_calls s1)"
chk_file "Run_a 의 s1.h5 는 d3plot 옆" "$T11/output/Run_a/Output/s1.h5"
chk_file "런마다 s1.log" "$T11/output/Run_b/Output/s1.log"
chk_no_file "실패한 런에는 s1.h5 가 없다" "$T11/output/Run_FAIL_S1/Output/s1.h5"
if grep -q "완료: 2 / 스킵: 0 / 실패: 1" "$W/last_run.log"; then
    echo "  OK  실패 1건을 세고 끝까지 간다"
else
    echo "  NG  S1 요약이 '완료: 2 / 스킵: 0 / 실패: 1' 이 아니다"
    fails=$((fails + 1))
fi
chk_file "캠페인 색인 output/s1_index.json" "$T11/output/s1_index.json"
chk "색인에 성공한 런 둘" 2 "$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["runs"]))' "$T11/output/s1_index.json")"
run_pa "$T11" --sphere-only --s1
chk "다시 돌리면 있는 것은 건너뛰고 실패한 것만 다시" 1 "$(n_calls s1)"
chk "건너뛴 런도 색인에 남는다" 2 "$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["runs"]))' "$T11/output/s1_index.json")"
run_pa "$T11" --sphere-only --s1 --force
chk "--force 면 전부 다시" 3 "$(n_calls s1)"

# ============================================================
# [12] 온톨로지 꾸러미 단계 — 리포트 JSON 마다 부르고, 리포트에 준 항복값을 그대로
#      넘기고, S1 뒤에 돌고, 실패해도 끝까지 간다. deep 만이면 부르지 않는다.
# ============================================================
echo "[12] 온톨로지 꾸러미"
T12="$W/t12"
mk_tree "$T12" Run_a/Output/d3plot Run_b/Output/d3plot
mk_config "$T12"
run_pa "$T12" --sphere-only
chk "리포트 JSON 이 없으면 부르지 않는다" 0 "$(n_calls onto)"
printf '{}\n' > "$T12/report.json"
printf '{}\n' > "$T12/report_Output2.json"
printf '{}\n' > "$T12/report.ontology.json"
run_pa "$T12" --sphere-only --s1 --yield-stress 300 --sphere-opts "--yield-map /m/yield.json"
chk "그룹 리포트까지 둘, 꾸러미 파일은 다시 먹지 않는다" 2 "$(n_calls onto)"
chk "리포트와 같은 항복값·캠페인 폴더를 넘긴다" 1 \
    "$(grep -c "^onto sphere $T12/report.json --test-dir $T12 --yield-stress 300 --yield-map /m/yield.json\$" "$W/calls.log")"
chk "S1 다음에 돈다" "s1" "$(grep -v '^ua \|^sphere \|^deep ' "$W/calls.log" | head -1 | cut -d' ' -f1)"
printf '{}\n' > "$T12/impact_report.json"
run_pa "$T12" --sphere-only
chk "impact_report.json 도 impact 로" 1 "$(grep -c "^onto impact $T12/impact_report.json\$" "$W/calls.log")"
run_pa "$T12" --deep-only --no-render
chk "--deep-only 면 부르지 않는다(deep 은 스스로 쓴다)" 0 "$(n_calls onto)"
T12F="$W/t12_FAIL_ONTO"
mk_tree "$T12F" Run_a/Output/d3plot
mk_config "$T12F"
printf '{}\n' > "$T12F/report.json"
run_pa "$T12F" --sphere-only
if grep -q "WARN: 꾸러미 실패 — report.json" "$W/last_run.log" && grep -q "결과 위치" "$W/last_run.log"; then
    echo "  OK  꾸러미가 실패해도 경고만 하고 끝까지 간다"
else
    echo "  NG  꾸러미 실패가 파이프라인을 멈췄거나 경고가 없다"
    fails=$((fails + 1))
fi
mv "$BIN/koo_ontology" "$W/koo_ontology.off"
run_pa "$T12" --sphere-only
mv "$W/koo_ontology.off" "$BIN/koo_ontology"
if grep -q "koo_ontology 가 PATH 에 없음" "$W/last_run.log"; then
    echo "  OK  옛 SIF(koo_ontology 없음)면 건너뛴다고 말한다"
else
    echo "  NG  koo_ontology 없을 때 사유가 없다"
    fails=$((fails + 1))
fi

echo ""
if [ "$fails" -gt 0 ]; then
    echo "[FAIL] 실패 ${fails} 건"
    exit 1
fi
echo "[PASS] 실패 0 건"
