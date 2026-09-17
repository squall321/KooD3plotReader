#!/bin/bash
# ============================================================
# post_analyze.sh — SmartTwinPostprocessor 통합 후처리 오케스트레이션
# ============================================================
# test_dir 을 주면 unified_analyzer → sphere_report → deep_report batch
# 순서로 실행하여 모든 후처리 결과를 생성합니다 (실제 호출은 아래 메인 분기 참조).
# sphere 가 먼저인 이유: 집계만 해서 빠르다. deep 은 렌더를 포함해 느리므로 뒤.
#
# **주의** — 파트별 응력/주응력 CSV 는 Step 1(unified_analyzer) 에서만 나온다.
# deep_report 는 binout(matsum/rcforc) 만 읽으므로 deep 만 다시 돌려도
# 응력 계열 산출물은 갱신되지 않는다.
#
# 각 단계는 기존 결과가 최신이면 스킵합니다 (--force 로 강제 재계산).
#
# 필수 바이너리 (PATH 에서 찾음):
#   unified_analyzer, koo_deep_report, koo_sphere_report
#
# 디렉토리 구조 (koo_sphere_report USAGE.md 기준):
#   <test_dir>/
#     ├── scenario.json
#     ├── runner_config.json
#     ├── common_analysis.yaml    (unified_analyzer --recursive 용 YAML)
#     ├── output/                 (d3plot Run_* 디렉토리)
#     │   └── Run_*/
#     ├── analysis_results/       (Step 1 결과 — sphere 용)
#     │   └── Run_*/analysis_result.json + stress/strain/motion CSVs
#     └── deep_reports/           (Step 2 결과 — 개별 deep HTML)
#         └── Run_*/result.json + report.html
#
# 사용법:
#   post_analyze.sh <test_dir>
#   post_analyze.sh <test_dir> --config common_analysis.yaml
#   post_analyze.sh <test_dir> --deep-config deep_analysis.yaml
#   post_analyze.sh <test_dir> --deep-only
#   post_analyze.sh <test_dir> --sphere-only
#   post_analyze.sh <test_dir> --force
#
# 편의 옵션 (deep_report 로 전달):
#   --threads 8
#   --yield-stress 355
#   --no-render
#   --section-view
#   --section-view-mode section_3d
#   --section-view-axes x y z
#   --element-quality
#
# 고급 pass-through:
#   --deep-opts   "임의 deep_report 옵션들"    (예: --deep-opts "--parts 100 200")
#   --sphere-opts "임의 sphere_report 옵션들"
# ============================================================
set -euo pipefail

TEST_DIR=""
CONFIG_FILE=""       # unified_analyzer 용 YAML (sphere 선행)
ANALYSIS_GROUPS=()   # unified_analyzer 가 발견한 그룹 목록 (Output, Output2 등)
DEEP_CONFIG=""       # koo_deep_report --config 로 전달할 YAML
DEEP_ONLY=false
SPHERE_ONLY=false
IMPACT_ONLY=false
# 각도 산포 리포트(koo_scatter_report). 캠페인을 가로로 묶어 편차각 산포·방향도·
# 리스크맵을 낸다. 기본은 끔 — 켜면 마지막 단계로 붙는다.
SCATTER=false
SCATTER_EXTRA=()
FORCE=false
SCHEMA_CHECK=true    # false 면 산출물 존재만 보고 스킵(옛 동작)
THREADS=4
YIELD_STRESS=""

# scenario.json 의 cumulative.mode_sequence 자동 감지 → 종합 리포트 모듈 선택
#   ['DROP', ...]                   → sphere_report (전각도)
#   ['IMPACT'] 또는 ['IMPACT', ...] → impact_report (부분충격 DOE)
#   감지 실패 / 둘 다 섞임          → sphere (현행 default), --impact-only 또는 --sphere-only 로 강제
SCENARIO_MODE=""     # "DROP" | "IMPACT" | "" (감지 결과)

# deep_report 로 pass-through 할 편의 플래그 배열
# 기본: 섹션뷰 ON (모든 파트 × x/y/z × von_mises × lsprepost backend)
SECTION_VIEW=true
DEEP_EXTRA=()
SPHERE_EXTRA=()
IMPACT_EXTRA=()

usage() {
    cat << 'HELPEOF'
사용법:
    post_analyze <test_dir> [options]

  전체 파이프라인: unified_analyzer → sphere_report (빠름) → deep_report (느림)
  각 단계는 기존 결과가 있으면 자동 스킵 (--force 로 강제 재계산)

[모드]
    --deep-only             deep report 만
    --sphere-only           sphere report 만 (DROP 전각도 강제)
    --impact-only           impact report 만 (IMPACT 부분충격 DOE 강제)
    --force                 기존 결과 무시하고 전체 재계산
    --no-schema-check       산출물이 낡아도 재분석하지 않음 (존재하면 스킵).
                            새 산출물(주응력 등)은 보고서에서 빈 칸으로,
                            수정 전 분석기가 낸 값은 그대로 남음

    (scenario.json 의 cumulative.mode_sequence 로 자동 감지:
       ['DROP', ...]   → sphere_report
       ['IMPACT', ...] → impact_report)

[설정]
    --config YAML           unified_analyzer 용 YAML (common_analysis.yaml)
    --deep-config YAML      koo_deep_report 용 YAML
    --threads N             병렬 스레드 수 (기본 4)
    --yield-stress MPa      항복응력

[렌더 (deep_report 전달)]
    --no-render
    --per-part-render
    --element-quality
    --render-threads N
    --ua-threads N
    --parts ID...
    --part-pattern PATTERN
    --strain-limit EPS
    --design-overrides JSON
    --material-overrides JSON

[섹션뷰 (deep_report 전달)]
    --section-view
    --section-view-backend {lsprepost|software}
    --section-view-mode {section|section_3d}
    --section-view-per-part
    --section-view-axes x y z
    --section-view-fields von_mises eps strain ...
    --section-view-target-ids ID...
    --section-view-target-patterns PAT...
    --section-view-fade DIST
    --sv-threads N

[고급]
    --deep-opts "..."       koo_deep_report 추가 옵션 pass-through
    --sphere-opts "..."     koo_sphere_report 추가 옵션 pass-through
    --scatter               각도 산포 리포트(koo_scatter_report) 추가 생성
    --scatter-opts "..."    koo_scatter_report 옵션 pass-through
                            (예: '--criterion max_principal --ground-truth ng.tsv')
    --impact-opts "..."     koo_impact_report 추가 옵션 pass-through (예: '--units ton-mm-s')
    -h|--help

예시:
    post_analyze /data/drop_test_001
    post_analyze /data/drop_test_001 --yield-stress 250 --threads 8
    post_analyze /data/drop_test_001 --deep-only --no-render
    post_analyze /data/drop_test_001 --sphere-only
    post_analyze /data/Test_Impact_A                       # 자동: IMPACT 감지
    post_analyze /data/Test_Impact_A --impact-only         # 명시
    post_analyze /data/test_001 --section-view --section-view-backend lsprepost
HELPEOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        # 오케스트레이션 제어
        --deep-only)     DEEP_ONLY=true; shift ;;
        --sphere-only)   SPHERE_ONLY=true; shift ;;
        --impact-only)   IMPACT_ONLY=true; shift ;;
        --force)         FORCE=true; shift ;;
        --no-schema-check) SCHEMA_CHECK=false; shift ;;

        # unified_analyzer / deep_report 공통 YAML 분리
        --config)        CONFIG_FILE="$2"; shift 2 ;;
        --deep-config)   DEEP_CONFIG="$2"; shift 2 ;;

        # deep_report 직접 전달 편의 옵션
        --threads)                 THREADS="$2"; shift 2 ;;
        --yield-stress)            YIELD_STRESS="$2"; shift 2 ;;
        --no-render)               DEEP_EXTRA+=(--no-render); shift ;;
        --per-part-render)         DEEP_EXTRA+=(--per-part-render); shift ;;
        --element-quality)         DEEP_EXTRA+=(--element-quality); shift ;;
        --render-threads)          DEEP_EXTRA+=(--render-threads "$2"); shift 2 ;;
        --ua-threads)              DEEP_EXTRA+=(--ua-threads "$2"); shift 2 ;;
        --parts)                   DEEP_EXTRA+=(--parts); shift
                                   while [[ $# -gt 0 && "$1" != -* ]]; do
                                       DEEP_EXTRA+=("$1"); shift
                                   done ;;
        --part-pattern)            DEEP_EXTRA+=(--part-pattern "$2"); shift 2 ;;
        --strain-limit)            DEEP_EXTRA+=(--strain-limit "$2"); shift 2 ;;
        --design-overrides)        DEEP_EXTRA+=(--design-overrides "$2"); shift 2 ;;
        --material-overrides)      DEEP_EXTRA+=(--material-overrides "$2"); shift 2 ;;

        # Section view 편의 플래그
        --section-view)            SECTION_VIEW=true; shift ;;
        --no-section-view)         SECTION_VIEW=false; shift ;;
        --section-view-backend)    DEEP_EXTRA+=(--section-view-backend "$2"); shift 2 ;;
        --section-view-mode)       DEEP_EXTRA+=(--section-view-mode "$2"); shift 2 ;;
        --section-view-per-part)   DEEP_EXTRA+=(--section-view-per-part); shift ;;
        --section-view-axes)       DEEP_EXTRA+=(--section-view-axes); shift
                                   while [[ $# -gt 0 && "$1" != -* ]]; do
                                       DEEP_EXTRA+=("$1"); shift
                                   done ;;
        --section-view-fields)     DEEP_EXTRA+=(--section-view-fields); shift
                                   while [[ $# -gt 0 && "$1" != -* ]]; do
                                       DEEP_EXTRA+=("$1"); shift
                                   done ;;
        --section-view-target-ids) DEEP_EXTRA+=(--section-view-target-ids); shift
                                   while [[ $# -gt 0 && "$1" != -* ]]; do
                                       DEEP_EXTRA+=("$1"); shift
                                   done ;;
        --section-view-target-patterns)
                                   DEEP_EXTRA+=(--section-view-target-patterns); shift
                                   while [[ $# -gt 0 && "$1" != -* ]]; do
                                       DEEP_EXTRA+=("$1"); shift
                                   done ;;
        --section-view-fade)       DEEP_EXTRA+=(--section-view-fade "$2"); shift 2 ;;
        --sv-threads)              DEEP_EXTRA+=(--sv-threads "$2"); shift 2 ;;

        # 고급 pass-through
        --deep-opts)     read -r -a _extra <<< "$2"; DEEP_EXTRA+=("${_extra[@]}"); shift 2 ;;
        --sphere-opts)   read -r -a _extra <<< "$2"; SPHERE_EXTRA+=("${_extra[@]}"); shift 2 ;;
        --scatter)       SCATTER=true; shift ;;
        --scatter-opts)  SCATTER=true; read -r -a _extra <<< "$2"
                         SCATTER_EXTRA+=("${_extra[@]}"); shift 2 ;;
        --impact-opts)   read -r -a _extra <<< "$2"; IMPACT_EXTRA+=("${_extra[@]}"); shift 2 ;;

        -h|--help)       usage ;;
        -*)              echo "ERROR: 알 수 없는 옵션: $1"; usage ;;
        *)
            if [ -z "${TEST_DIR}" ]; then
                TEST_DIR="$1"; shift
            else
                echo "ERROR: 위치 인자 여러 개: $1"; usage
            fi ;;
    esac
done

# 모드 상호 배타 체크 (test_dir 검증보다 먼저 — 옵션 오류는 인자 검증보다 우선)
_only_count=0
${DEEP_ONLY}   && _only_count=$((_only_count + 1))
${SPHERE_ONLY} && _only_count=$((_only_count + 1))
${IMPACT_ONLY} && _only_count=$((_only_count + 1))
if [ "${_only_count}" -gt 1 ]; then
    echo "ERROR: --deep-only / --sphere-only / --impact-only 중 하나만 사용 가능"
    exit 1
fi

if [ -z "${TEST_DIR}" ]; then
    echo "ERROR: test_dir 인자가 필요합니다."
    usage
fi

if [ ! -d "${TEST_DIR}" ]; then
    echo "ERROR: test_dir 없음: ${TEST_DIR}"
    exit 1
fi

# ============================================================
# scenario.json 의 cumulative.mode_sequence 자동 감지
#   ['DROP', ...]   → SCENARIO_MODE=DROP  → sphere_report
#   ['IMPACT', ...] → SCENARIO_MODE=IMPACT → impact_report
#   감지 실패        → SCENARIO_MODE=""    → 현행 default (sphere)
# 명시적 --sphere-only / --impact-only 가 자동 감지를 override.
# ============================================================
detect_scenario_mode() {
    local sc="${TEST_DIR}/scenario.json"
    if [ ! -f "${sc}" ]; then
        SCENARIO_MODE=""
        return
    fi
    SCENARIO_MODE=$(python3 - "$sc" << 'PYEOF' 2>/dev/null || echo ""
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    scs = d.get("scenarios") or []
    if not scs:
        print("")
        sys.exit(0)
    seq = scs[0].get("cumulative", {}).get("mode_sequence") or []
    if not seq:
        print("")
        sys.exit(0)
    # 첫 mode 기준 판정. 모두 IMPACT 면 IMPACT, 모두 DROP 이면 DROP.
    if all(m == "IMPACT" for m in seq):
        print("IMPACT")
    elif all(m == "DROP" for m in seq):
        print("DROP")
    else:
        # mixed — first mode
        print(seq[0])
except Exception:
    print("")
PYEOF
)
}
detect_scenario_mode

TEST_DIR="$(readlink -f "${TEST_DIR}")"
OUTPUT_DIR="${TEST_DIR}/output"
ANALYSIS_DIR="${TEST_DIR}/analysis_results"
DEEP_REPORTS_DIR="${TEST_DIR}/deep_reports"

# common_analysis.yaml 자동 탐지 (사용자가 안 줬으면 test_dir 안에서 찾음)
if [ -z "${CONFIG_FILE}" ] && [ -f "${TEST_DIR}/common_analysis.yaml" ]; then
    CONFIG_FILE="${TEST_DIR}/common_analysis.yaml"
fi

# deep_analysis.yaml 자동 탐지
if [ -z "${DEEP_CONFIG}" ] && [ -f "${TEST_DIR}/deep_analysis.yaml" ]; then
    DEEP_CONFIG="${TEST_DIR}/deep_analysis.yaml"
fi

# ============================================================
# 바이너리 존재 확인
# ============================================================
check_bin() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERROR: $1 바이너리를 PATH 에서 찾을 수 없음"
        echo "  SmartTwinPostprocessor.sif 안에서 실행하거나,"
        echo "  /data/SmartTwinPostprocessor/bin 을 PATH 에 추가하세요."
        exit 1
    fi
}
check_bin unified_analyzer
check_bin koo_deep_report
# koo_sphere_report / koo_impact_report 는 실제 사용 분기에서만 강제. 옛 SIF
# (impact 미포함) 호환성을 위해 여기서 강제하지 않고, 호출 직전에 검사.

# ============================================================
# 헤더 + 효과 모드 (자동 감지 + override)
# ============================================================
# 효과 모드: deep-only/sphere-only/impact-only 가 있으면 그것. 없으면 SCENARIO_MODE
# 가 IMPACT 면 impact, DROP 또는 빈 값이면 sphere (현행 default).
EFFECTIVE_REPORT_MODE="sphere"  # 기본
if ${IMPACT_ONLY}; then
    EFFECTIVE_REPORT_MODE="impact"
elif ${SPHERE_ONLY}; then
    EFFECTIVE_REPORT_MODE="sphere"
elif [ "${SCENARIO_MODE}" = "IMPACT" ]; then
    EFFECTIVE_REPORT_MODE="impact"
fi

mode_str="all"
${DEEP_ONLY}   && mode_str="deep-only"
${SPHERE_ONLY} && mode_str="sphere-only"
${IMPACT_ONLY} && mode_str="impact-only"

echo "============================================================"
echo " SmartTwinPostprocessor — Post Analyze"
echo "============================================================"
echo "  Test dir      : ${TEST_DIR}"
echo "  Output (sims) : ${OUTPUT_DIR}"
echo "  Analysis dir  : ${ANALYSIS_DIR}"
echo "  Deep reports  : ${DEEP_REPORTS_DIR}"
echo "  Config YAML   : ${CONFIG_FILE:-(없음)}"
echo "  Deep YAML     : ${DEEP_CONFIG:-(없음)}"
echo "  Mode          : ${mode_str}"
echo "  Force rerun   : ${FORCE}"
echo "  Threads       : ${THREADS}"
[ -n "${YIELD_STRESS}" ]          && echo "  Yield stress  : ${YIELD_STRESS} MPa"
[ "${#DEEP_EXTRA[@]}" -gt 0 ]     && echo "  Deep extras   : ${DEEP_EXTRA[*]}"
[ "${#SPHERE_EXTRA[@]}" -gt 0 ]   && echo "  Sphere extras : ${SPHERE_EXTRA[*]}"
[ "${#IMPACT_EXTRA[@]}" -gt 0 ]   && echo "  Impact extras : ${IMPACT_EXTRA[*]}"
[ -n "${SCENARIO_MODE}" ]         && echo "  Scenario mode : ${SCENARIO_MODE} → ${EFFECTIVE_REPORT_MODE}"
echo "============================================================"

# ============================================================
# Step 1: unified_analyzer --recursive
#  - sphere_report 가 analysis_results/ 를 필요로 함
#  - 산출물이 최신 스키마면 스킵 (--force 로 전체 강제, --no-schema-check 로
#    스키마 무시하고 존재 여부만 봄)
# ============================================================

# unified_analyzer 산출물 스키마 버전.
# **분석기 산출물이 늘거나 값이 달라지면 이 값을 올린다.**
# 예전에는 analysis_result.json 존재만 보고 스킵했는데, 그러면 분석기가
# 산출물을 늘려도(σ1 주응력 CSV 등) 기존 run 이 영원히 옛 산출물로 남는다.
# 마커가 없거나 값이 다르면 그 run 만 다시 분석한다.
#   v2: max/min principal stress CSV (SinglePassAnalyzer — von Mises 와 항상 동반)
#   v3: 시계열 20점 잘림 제거 + 수치 표기 교정(유효숫자 10, 비유한값 null),
#       표면 응력·요소 면 위상 수정 — 산출물 목록이 아니라 **값**이 달라졌다.
#       v3 부터 마커는 `키=값` 줄 형식이라, 옛 마커("2" 한 줄)는 형식이 달라
#       자동으로 낡은 것으로 판정된다.
UA_OUTPUT_SCHEMA=3
UA_SCHEMA_MARKER=".ua_schema"

# deep_report 산출물 재사용 판정용 마커 (이 스크립트가 쓴다).
# koo_deep_report 가 batch 모드에서 스스로 쓰는 .ua_schema 와 이름을 겹치지 않게 둔다.
# 한계 — koo_deep_report(파이썬) 자체 판이 바뀐 것은 여기서 알 수 없다.
# 알 수 있는 것(스키마·분석기 커밋·d3plot 갱신)만 본다.
DEEP_OUTPUT_SCHEMA=1
DEEP_SCHEMA_MARKER=".post_analyze_deep"

# 이 자리의 unified_analyzer 가 어느 커밋으로 빌드됐나.
# 스키마 번호만으로는 "값이 달라진 수정"(변위 19배 과대, 표면 응력 0 등)을 못 거른다
# — 그런 수정은 산출물 목록을 바꾸지 않아 번호를 올릴 계기가 없었다. 커밋이 다르면
# 값도 다를 수 있다고 보고 다시 분석한다.
# 못 얻으면 빈 값으로 두고 사유를 알린다(없는 값을 지어내지 않는다).
UA_TOOL_COMMIT=""
UA_TOOL_COMMIT_REASON=""
detect_ua_commit() {
    local caps
    if ! caps=$(unified_analyzer --capabilities 2>/dev/null); then
        UA_TOOL_COMMIT_REASON="unified_analyzer --capabilities 실패 (옛 빌드?)"
        return 0
    fi
    UA_TOOL_COMMIT=$(printf '%s' "${caps}" | \
        sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    if [ -z "${UA_TOOL_COMMIT}" ] || [ "${UA_TOOL_COMMIT}" = "unknown" ]; then
        UA_TOOL_COMMIT=""
        UA_TOOL_COMMIT_REASON="--capabilities 에 빌드 커밋이 없음"
    fi
}
detect_ua_commit

_ua_commit_reported=false
report_ua_commit() {
    if ${_ua_commit_reported}; then return 0; fi
    _ua_commit_reported=true
    if [ -n "${UA_TOOL_COMMIT}" ]; then
        echo "  분석기 커밋: ${UA_TOOL_COMMIT} — 이 커밋으로 낸 산출물만 재사용합니다"
    else
        echo "  분석기 커밋: 알 수 없음 — ${UA_TOOL_COMMIT_REASON}"
        echo "    커밋 대조 없이 스키마·d3plot 시각만으로 재사용을 판정합니다."
    fi
}

# 마커 파일에서 키 하나 읽기 (파일·키가 없으면 빈 값)
_marker_field() {                # _marker_field <마커 파일> <키>
    if [ ! -f "$1" ]; then return 0; fi
    sed -n "s/^$2=//p" "$1" 2>/dev/null
}

# 이 산출물이 지금 분석기가 내는 것과 같은가.
# 아니면 사유를 _stale_reason 에 남긴다 — 왜 다시 도는지 사람이 봐야 한다.
_stale_reason=""
outputs_are_current() {          # <결과dir> <마커파일> <스키마> <산출물파일> <d3plot>
    local rd="$1" marker="$2" want_schema="$3" sentinel="$4" d3="$5"
    _stale_reason=""
    if [ ! -f "${rd}/${sentinel}" ]; then
        _stale_reason="산출물 없음"
        return 1
    fi
    ${SCHEMA_CHECK} || return 0          # --no-schema-check: 존재하면 최신 취급
    local got_schema got_commit
    got_schema=$(_marker_field "${rd}/${marker}" schema)
    if [ "${got_schema}" != "${want_schema}" ]; then
        _stale_reason="산출물 스키마 ${got_schema:-없음} ≠ ${want_schema}"
        return 1
    fi
    got_commit=$(_marker_field "${rd}/${marker}" analyzer)
    if [ "${got_commit}" != "${UA_TOOL_COMMIT}" ]; then
        _stale_reason="분석기 커밋 ${got_commit:-없음} → ${UA_TOOL_COMMIT:-알 수 없음}"
        return 1
    fi
    if [ -n "${d3}" ] && [ -f "${d3}" ] && [ "${d3}" -nt "${rd}/${sentinel}" ]; then
        _stale_reason="d3plot 이 산출물보다 새로움 (재시뮬레이션)"
        return 1
    fi
    return 0
}

# 분석 성공 후 표식 기록. analyzer 값이 비면 "그때도 커밋을 알 수 없었다" 는 뜻이다
# (모르는 것을 아는 척하지 않는다). 다음 실행에서 커밋을 알게 되면 값이 달라져 다시 돈다.
write_marker() {                 # <결과dir> <마커파일> <스키마>
    {
        echo "schema=$3"
        echo "analyzer=${UA_TOOL_COMMIT}"
    } > "$1/$2"
}

# 이 result_dir 이 최신 산출물을 갖고 있는가?
ua_result_is_current() {         # <결과dir> <d3plot>
    outputs_are_current "$1" "${UA_SCHEMA_MARKER}" "${UA_OUTPUT_SCHEMA}" \
        "analysis_result.json" "${2:-}"
}

run_step_unified() {
    echo ""
    echo "=== [Step 1] unified_analyzer (Run 별 개별 분석) ==="
    report_ua_commit

    if ${FORCE}; then
        echo "  FORCE 모드 — 기존 analysis_results/ 삭제"
        rm -rf "${ANALYSIS_DIR}"
    fi

    if [ ! -d "${OUTPUT_DIR}" ]; then
        echo "  ERROR: ${OUTPUT_DIR} 없음 (시뮬레이션 output 디렉토리)"
        return 1
    fi

    if [ -z "${CONFIG_FILE}" ]; then
        echo "  ERROR: common_analysis.yaml 없음. --config 로 지정하거나"
        echo "         ${TEST_DIR}/common_analysis.yaml 에 위치시켜주세요."
        return 1
    fi

    if [ ! -f "${CONFIG_FILE}" ]; then
        echo "  ERROR: config 파일 없음: ${CONFIG_FILE}"
        return 1
    fi

    # d3plot 탐색 → (run_name, sub_path, d3plot_path) 트리플로 수집
    # output/Run_xxx/Output/d3plot  → run_name=Run_xxx, sub_path=Output
    # output/Run_xxx/d3plot         → run_name=Run_xxx, sub_path=_default
    D3PLOT_ENTRIES=()    # "run_name|sub_path|d3plot_path"
    GROUP_LIST=""        # 줄바꿈 구분 그룹 목록 (중복 포함)

    while IFS= read -r d3plot_path; do
        rel="${d3plot_path#${OUTPUT_DIR}/}"    # Run_xxx/Output/d3plot
        run_name="${rel%%/*}"                  # Run_xxx

        if [ -z "${run_name}" ] || [ "${run_name}" = "${rel}" ]; then
            continue
        fi

        # sub_path: Run 폴더와 d3plot 사이의 경로
        after_run="${rel#${run_name}/}"         # Output/d3plot
        sub_path="${after_run%/d3plot}"          # Output

        # d3plot 이 Run 바로 밑에 있으면 sub_path == "d3plot" 이 됨
        if [ "${sub_path}" = "d3plot" ] || [ "${sub_path}" = "${after_run}" ]; then
            sub_path="_default"
        fi

        D3PLOT_ENTRIES+=("${run_name}|${sub_path}|${d3plot_path}")
        GROUP_LIST="${GROUP_LIST}${sub_path}"$'\n'

    done < <(find "${OUTPUT_DIR}" -name "d3plot" -type f 2>/dev/null | sort)

    _total=${#D3PLOT_ENTRIES[@]}
    if [ "${_total}" = 0 ]; then
        echo "  ERROR: d3plot 파일을 찾을 수 없음: ${OUTPUT_DIR}"
        return 1
    fi

    # 유니크 그룹 목록 + 카운트
    UNIQUE_GROUPS=$(echo "${GROUP_LIST}" | sed '/^$/d' | sort -u)
    _num_groups=$(echo "${UNIQUE_GROUPS}" | wc -l)
    echo "  d3plot ${_total}개 탐지, ${_num_groups}개 그룹:"
    echo "${UNIQUE_GROUPS}" | while read -r g; do
        cnt=$(echo "${GROUP_LIST}" | grep -cx "${g}")
        echo "    - ${g}: ${cnt}개 Run"
    done

    # 그룹별로 analysis_results 구성
    _done=0
    _skip=0
    _fail=0
    _stale=0
    _idx=0

    for entry in "${D3PLOT_ENTRIES[@]}"; do
        _idx=$(( _idx + 1 ))
        IFS='|' read -r run_name sub_path d3plot_path <<< "${entry}"

        # 결과 디렉토리 결정
        if [ "${_num_groups}" = 1 ] && [ "${sub_path}" != "_default" ]; then
            # 그룹 1개면 analysis_results/Run_xxx/ (하위 안 나눔)
            result_dir="${ANALYSIS_DIR}/${run_name}"
        elif [ "${sub_path}" = "_default" ]; then
            result_dir="${ANALYSIS_DIR}/${run_name}"
        else
            # 그룹 여러 개면 analysis_results/{sub_path}/Run_xxx/
            result_dir="${ANALYSIS_DIR}/${sub_path}/${run_name}"
        fi

        # skip 판정 — '있으면 스킵' 이 아니라 '최신이면 스킵'
        if ! ${FORCE} && ua_result_is_current "${result_dir}" "${d3plot_path}"; then
            _skip=$(( _skip + 1 ))
            continue
        fi
        # 산출물은 있는데 낡아서 다시 도는 경우를 따로 세고, 사유를 그 줄에 적는다
        _reason=""
        if ! ${FORCE} && [ -f "${result_dir}/analysis_result.json" ]; then
            _stale=$(( _stale + 1 ))
            _reason=" [재분석: ${_stale_reason}]"
        fi

        mkdir -p "${result_dir}"

        # config YAML 에 input/output 섹션 추가 (템플릿에 없을 수 있으므로 항상 prepend)
        tmp_yaml=$(mktemp /tmp/ua_config_XXXXXX.yaml)
        {
            echo 'version: "2.0"'
            echo "input:"
            echo "  d3plot: \"${d3plot_path}\""
            echo "output:"
            echo "  directory: \"${result_dir}\""
            echo "  json: true"
            echo "  csv: true"
            echo ""
            # 원본 config 에서 version/input/output 제외하고 나머지 (performance, analysis_jobs 등) 추가
            grep -v '^\s*version:\|^\s*d3plot:\|^\s*directory:\|^\s*json:\|^\s*csv:\|^input:\|^output:' "${CONFIG_FILE}" | \
                grep -v '^\s*#.*d3plot\|^\s*#.*directory'
        } > "${tmp_yaml}"

        printf "  [%d/%d] %s/%s → analysis_results/%s/%s%s ... " "${_idx}" "${_total}" "${run_name}" "${sub_path}" "${sub_path}" "${run_name}" "${_reason}"

        if unified_analyzer --config "${tmp_yaml}" 2>&1 | tail -5; then
            echo "OK"
            write_marker "${result_dir}" "${UA_SCHEMA_MARKER}" "${UA_OUTPUT_SCHEMA}"
            _done=$(( _done + 1 ))
        else
            echo "FAIL"
            _fail=$(( _fail + 1 ))
        fi

        rm -f "${tmp_yaml}"
    done

    echo ""
    echo "  완료: ${_done} / 스킵: ${_skip} / 실패: ${_fail} / 전체: ${_total}"
    if [ "${_stale}" -gt 0 ]; then
        echo "  ※ 이 중 ${_stale}개는 기존 산출물이 낡아 다시 분석했습니다 (사유는 위 각 줄의 [재분석: …])."
        echo "     분석기가 산출물을 늘렸거나(주응력 CSV 등) 값이 달라지는 수정을 했다는 뜻입니다."
        echo "     재분석을 원치 않으면 --no-schema-check 를 주십시오(그 항목은 옛 값 그대로 보고됩니다)."
    fi

    # 그룹 목록을 전역으로 저장 (sphere_report 에서 사용)
    ANALYSIS_GROUPS=()
    while read -r g; do
        [ -n "${g}" ] && ANALYSIS_GROUPS+=("${g}")
    done <<< "${UNIQUE_GROUPS}"
}

# ============================================================
# Step 3: koo_scatter_report  (각도 산포 — 캠페인을 가로로 묶는다)
#  - 편차각 산포·방향도·히트맵·회수율·리스크맵을 한 장으로
#  - 그림은 외부 라이브러리 없이 SVG (망이 막혀도 열린다)
# ============================================================
run_step_scatter() {
    echo ""
    echo "=== [Step 3] koo_scatter_report (각도 산포) ==="

    if [ ! -d "${ANALYSIS_DIR}" ] || \
       [ "$(find "${ANALYSIS_DIR}" -name "analysis_result.json" 2>/dev/null | head -1)" = "" ]; then
        echo "  analysis_results/ 가 없어 건너뜁니다 (Step 1 을 먼저 실행하세요)"
        return 0
    fi

    # 모듈이 없으면 조용히 넘어가지 않고 사유를 말한다
    if ! python3 -c "import koo_scatter_report" >/dev/null 2>&1; then
        echo "  koo_scatter_report 를 찾지 못했습니다 — 건너뜁니다"
        echo "    (배포본이면 env.sh 를 source 했는지, 저장소면 PYTHONPATH 를 확인하세요)"
        return 0
    fi

    local out="${TEST_DIR}/scatter_report.html"
    if python3 -m koo_scatter_report "${TEST_DIR}" -o "${out}" \
            "${SCATTER_EXTRA[@]}"; then
        echo "  → ${out}"
    else
        # 산포 리포트 실패가 전체 파이프라인을 죽이지 않게 한다.
        # 앞 단계 산출물(deep/sphere)은 이미 나와 있다.
        echo "  koo_scatter_report 실패 — 앞 단계 산출물은 그대로 남아 있습니다"
    fi
}

# ============================================================
# Step 2: koo_sphere_report --test-dir  (빠름 — aggregation 만)
#  - 전각도 DOE 종합 리포트 (analysis_results/ 필수)
# ============================================================
run_step_sphere() {
    echo ""
    echo "=== [Step 2] koo_sphere_report (종합 리포트) ==="

    if [ ! -d "${ANALYSIS_DIR}" ] || \
       [ "$(find "${ANALYSIS_DIR}" -name "analysis_result.json" 2>/dev/null | head -1)" = "" ]; then
        echo "  ERROR: analysis_results/ 없음 또는 비어있음"
        echo "         Step 1 을 먼저 실행하거나 --config 를 지정하세요"
        return 1
    fi

    # 그룹이 여러 개면 (Output, Output2 등) 그룹별로 sphere report 생성
    # 그룹이 1개 또는 _default 면 기존 방식 (단일 report.html)
    if [ "${#ANALYSIS_GROUPS[@]}" -gt 1 ]; then
        echo "  ${#ANALYSIS_GROUPS[@]}개 그룹 감지 → 그룹별 sphere report 생성"
        echo ""

        # analysis_results/ 를 먼저 백업, 그룹별로 심볼릭 링크 교체
        orig_ar="${TEST_DIR}/analysis_results"
        ar_bak="${TEST_DIR}/.analysis_results_original"

        # 원본 백업 (1회)
        if [ -d "${orig_ar}" ] && [ ! -L "${orig_ar}" ]; then
            mv "${orig_ar}" "${ar_bak}"
        elif [ -L "${orig_ar}" ]; then
            rm -f "${orig_ar}"
        fi

        for group in "${ANALYSIS_GROUPS[@]}"; do
            # 백업된 원본 안의 그룹 폴더 참조
            group_dir="${ar_bak}/${group}"
            if [ ! -d "${group_dir}" ]; then
                echo "  [${group}] .analysis_results_original/${group}/ 없음 — SKIP"
                continue
            fi

            # 그룹 폴더를 analysis_results 로 심볼릭 링크
            ln -sfn "${group_dir}" "${orig_ar}"

            output_html="${TEST_DIR}/report_${group}.html"
            output_json="${TEST_DIR}/report_${group}.json"

            echo "  [${group}] sphere report → $(basename "${output_html}")"

            cmd=(koo_sphere_report --test-dir "${TEST_DIR}"
                       --format html json
                       --output "${output_html}"
                       --json "${output_json}")
            [ -n "${YIELD_STRESS}" ] && cmd+=(--yield-stress "${YIELD_STRESS}")
            [ "${#SPHERE_EXTRA[@]}" -gt 0 ] && cmd+=("${SPHERE_EXTRA[@]}")

            "${cmd[@]}" || echo "  [${group}] WARN: sphere report 실패"

            # 심볼릭 링크 제거
            rm -f "${orig_ar}"
        done

        # 원본 복구
        if [ -d "${ar_bak}" ]; then
            mv "${ar_bak}" "${orig_ar}"
        fi
    else
        # 단일 그룹 또는 _default — 기존 방식
        local cmd=(koo_sphere_report --test-dir "${TEST_DIR}" --format html json)
        [ -n "${YIELD_STRESS}" ] && cmd+=(--yield-stress "${YIELD_STRESS}")
        [ "${#SPHERE_EXTRA[@]}" -gt 0 ] && cmd+=("${SPHERE_EXTRA[@]}")

        echo "  $ ${cmd[*]}"
        "${cmd[@]}"
    fi
}

# ============================================================
# Step 3: koo_deep_report batch --skip-existing  (느림 — 렌더 포함)
#  - 각 sim 별 deep 분석 + 개별 HTML 생성
#  - --deep-config 있으면 deep_report --config 로 전달
#  - DEEP_EXTRA 배열로 임의 옵션 pass-through
# ============================================================
run_step_deep() {
    echo ""
    echo "=== [Step 3] koo_deep_report (Run 별 개별 분석 + 렌더) ==="
    report_ua_commit

    if ${FORCE}; then
        echo "  FORCE 모드 — 기존 deep_reports/ 삭제"
        rm -rf "${DEEP_REPORTS_DIR}"
    fi

    if [ ! -d "${OUTPUT_DIR}" ]; then
        echo "  ERROR: ${OUTPUT_DIR} 없음 (시뮬레이션 output 디렉토리)"
        return 1
    fi

    mkdir -p "${DEEP_REPORTS_DIR}"

    # 그룹 수를 여기서 직접 센다.
    # 예전에는 run_step_unified 가 정한 전역 ${_num_groups:-1} 을 봤는데,
    # --deep-only 와 IMPACT flat 경로는 그 함수를 거치지 않아 늘 1 로 떨어졌다.
    # 그러면 Run_x/Output 과 Run_x/Output2 가 같은 deep_reports/Run_x 를 써서
    # 뒤엣것이 '스킵' 으로 사라지고, 그 그룹의 deep 리포트는 끝내 생기지 않았다.
    _deep_group_list=""
    while IFS= read -r d3plot_path; do
        rel="${d3plot_path#${OUTPUT_DIR}/}"
        run_name="${rel%%/*}"
        if [ -z "${run_name}" ] || [ "${run_name}" = "${rel}" ]; then
            continue
        fi
        after_run="${rel#${run_name}/}"
        sub_path="${after_run%/d3plot}"
        if [ "${sub_path}" = "d3plot" ] || [ "${sub_path}" = "${after_run}" ]; then
            sub_path="_default"
        fi
        _deep_group_list="${_deep_group_list}${sub_path}"$'\n'
    done < <(find "${OUTPUT_DIR}" -name "d3plot" -type f 2>/dev/null | sort)
    _deep_num_groups=$(echo "${_deep_group_list}" | sed '/^$/d' | sort -u | wc -l)

    # Step 1 과 동일 방식: Run 폴더별로 d3plot 찾아서 개별 호출
    # deep_report batch 는 중첩 구조(Run_xxx/Output/d3plot)에서 이름이 꼬이므로 사용 안 함
    _deep_total=0
    _deep_done=0
    _deep_skip=0
    _deep_fail=0
    _deep_stale=0

    while IFS= read -r d3plot_path; do
        _deep_total=$(( _deep_total + 1 ))

        rel="${d3plot_path#${OUTPUT_DIR}/}"
        run_name="${rel%%/*}"

        if [ -z "${run_name}" ] || [ "${run_name}" = "${rel}" ]; then
            continue
        fi

        # sub_path 결정 (그룹이 여러 개면 하위 분류)
        after_run="${rel#${run_name}/}"
        sub_path="${after_run%/d3plot}"
        if [ "${sub_path}" = "d3plot" ] || [ "${sub_path}" = "${after_run}" ]; then
            sub_path="_default"
        fi

        # 출력 경로: 그룹 1개면 deep_reports/Run_xxx, 여러개면 deep_reports/{sub_path}/Run_xxx
        if [ "${_deep_num_groups}" = 1 ] && [ "${sub_path}" != "_default" ]; then
            deep_out="${DEEP_REPORTS_DIR}/${run_name}"
        elif [ "${sub_path}" = "_default" ]; then
            deep_out="${DEEP_REPORTS_DIR}/${run_name}"
        else
            deep_out="${DEEP_REPORTS_DIR}/${sub_path}/${run_name}"
        fi

        # skip 판정 — '있으면 스킵' 이 아니라 '지금 분석기로 낸 것이면 스킵'.
        # result.json 존재만 보면 옛 빌드(변위 19배 과대·표면 응력 0 등)로 낸
        # 리포트가 영원히 재사용된다.
        if ! ${FORCE} && outputs_are_current "${deep_out}" "${DEEP_SCHEMA_MARKER}" \
                "${DEEP_OUTPUT_SCHEMA}" "result.json" "${d3plot_path}"; then
            _deep_skip=$(( _deep_skip + 1 ))
            continue
        fi
        _reason=""
        if ! ${FORCE} && [ -f "${deep_out}/result.json" ]; then
            _deep_stale=$(( _deep_stale + 1 ))
            _reason=" [재생성: ${_stale_reason}]"
        fi

        printf "  [%d] %s/%s%s ... " "${_deep_total}" "${run_name}" "${sub_path}" "${_reason}"

        cmd=(koo_deep_report "${d3plot_path}" --output "${deep_out}")
        [ -n "${DEEP_CONFIG}" ]  && cmd+=(--config "${DEEP_CONFIG}")
        [ -n "${YIELD_STRESS}" ] && cmd+=(--yield-stress "${YIELD_STRESS}")

        # 섹션뷰 기본값 주입 (SECTION_VIEW=true 이고 사용자가 --section-view 를 DEEP_EXTRA 에 안 넣었을 때)
        if ${SECTION_VIEW}; then
            # DEEP_EXTRA 에 이미 --section-view 있으면 중복 방지
            _has_sv=false
            for _e in "${DEEP_EXTRA[@]}"; do
                [ "${_e}" = "--section-view" ] && { _has_sv=true; break; }
            done
            if ! ${_has_sv}; then
                cmd+=(--section-view --section-view-per-part
                      --section-view-axes x y z
                      --section-view-fields von_mises)
                # lsprepost 있으면 사용, 없으면 software fallback
                if command -v lsprepost >/dev/null 2>&1 || \
                   [ -x "${LSPREPOST_PATH:-}/lsprepost" ] 2>/dev/null; then
                    cmd+=(--section-view-backend lsprepost)
                else
                    cmd+=(--section-view-backend software)
                fi
            fi
        fi

        [ "${#DEEP_EXTRA[@]}" -gt 0 ] && cmd+=("${DEEP_EXTRA[@]}")

        if "${cmd[@]}" > /dev/null 2>&1; then
            echo "OK"
            write_marker "${deep_out}" "${DEEP_SCHEMA_MARKER}" "${DEEP_OUTPUT_SCHEMA}"
            _deep_done=$(( _deep_done + 1 ))
        else
            echo "FAIL"
            _deep_fail=$(( _deep_fail + 1 ))
        fi

    done < <(find "${OUTPUT_DIR}" -name "d3plot" -type f 2>/dev/null | sort)

    echo ""
    echo "  완료: ${_deep_done} / 스킵: ${_deep_skip} / 실패: ${_deep_fail} / 전체: ${_deep_total}"
    if [ "${_deep_stale}" -gt 0 ]; then
        echo "  ※ 이 중 ${_deep_stale}개는 기존 리포트가 낡아 다시 만들었습니다 (사유는 위 각 줄의 [재생성: …])."
    fi
}

# ============================================================
# Step 2-impact: koo_impact_report --test-dir   (부분충격 DOE 종합)
#  - scenarios[*].cumulative.mode_sequence == ['IMPACT'] 일 때
#  - sphere 와 동일하게 analysis_results/ 가 필수 (unified_analyzer 결과)
# ============================================================
run_step_impact() {
    echo ""
    echo "=== [Step 2] koo_impact_report (부분충격 DOE 종합) ==="

    # Soft-skip: 옛 SIF (2.3.x) 호환성. koo_impact_report 가 없으면 deep_report 진행.
    if ! command -v koo_impact_report >/dev/null 2>&1; then
        echo "  WARN: koo_impact_report 가 PATH 에 없음 (옛 SIF?) — SKIP"
        return 0
    fi

    # Layout 게이트: F*/Run_*/analysis_result.json (face-tree)
    #                또는 output/Run_*/Output/d3plot (flat DOE) 중 하나 필요
    _face_layout=$(find "${TEST_DIR}" -maxdepth 3 -path '*/F*/Run_*/analysis_result.json' 2>/dev/null | head -1)
    _flat_layout=$(find "${OUTPUT_DIR}" -maxdepth 3 -name 'd3plot' -type f 2>/dev/null | head -1)
    if [ -z "${_face_layout}" ] && [ -z "${_flat_layout}" ]; then
        echo "  ERROR: F*/Run_*/analysis_result.json 도, output/Run_*/d3plot 도 없음"
        echo "         IMPACT 분석을 위한 데이터가 없습니다"
        return 1
    fi

    local cmd=(koo_impact_report --test-dir "${TEST_DIR}"
                   --format html json terminal
                   --output "${TEST_DIR}/impact_report.html"
                   --json   "${TEST_DIR}/impact_report.json")
    [ -n "${YIELD_STRESS}" ] && cmd+=(--yield-stress "${YIELD_STRESS}")
    [ "${#IMPACT_EXTRA[@]}" -gt 0 ] && cmd+=("${IMPACT_EXTRA[@]}")

    echo "  $ ${cmd[*]}"
    "${cmd[@]}"
}

# ============================================================
# 실행 분기 (auto-detect + override)
#   --deep-only        : deep_report 만
#   --sphere-only      : unified → sphere
#   --impact-only      : unified → impact
#   default + SCENARIO_MODE==IMPACT : unified → impact → deep
#   default            : unified → sphere → deep
# ============================================================
# Helper: IMPACT 모드일 때, common_analysis.yaml 이 없고 output/Run_*/d3plot 만 있으면
# run_step_unified 를 건너뛴다. koo_impact_report.load_partial_impact_doe_report 가
# 내부에서 unified_analyzer 를 Run 별로 직접 실행한다.
should_skip_unified_for_impact() {
    [ -z "${CONFIG_FILE}" ] || return 1
    local _d3
    _d3=$(find "${OUTPUT_DIR}" -maxdepth 3 -name 'd3plot' -type f 2>/dev/null | head -1)
    [ -n "${_d3}" ]
}

if ${DEEP_ONLY}; then
    run_step_deep
    ${SCATTER} && run_step_scatter
elif ${SPHERE_ONLY}; then
    run_step_unified
    run_step_sphere
    ${SCATTER} && run_step_scatter
elif ${IMPACT_ONLY}; then
    if should_skip_unified_for_impact; then
        echo ""
        echo "  ※ IMPACT 모드 + common_analysis.yaml 없음 + flat output/Run_* 감지"
        echo "    → run_step_unified SKIP. koo_impact_report 가 내부에서 unified_analyzer 실행"
    else
        run_step_unified
    fi
    run_step_impact
    ${SCATTER} && run_step_scatter
else
    if [ "${EFFECTIVE_REPORT_MODE}" = "impact" ]; then
        echo ""
        echo "  ※ scenario.json mode_sequence=['IMPACT'] 감지 → koo_impact_report 사용"
        if should_skip_unified_for_impact; then
            echo "    common_analysis.yaml 없음 + flat layout → run_step_unified SKIP"
        else
            run_step_unified
        fi
        run_step_impact
    else
        run_step_unified
        run_step_sphere
    fi
    run_step_deep
    ${SCATTER} && run_step_scatter
fi

echo ""
echo "============================================================"
echo " 완료"
echo "============================================================"
echo "  결과 위치:"
if ! ${SPHERE_ONLY} && ! ${IMPACT_ONLY}; then
    [ -d "${DEEP_REPORTS_DIR}" ] && echo "    ${DEEP_REPORTS_DIR}/ (개별 deep HTML)"
fi
if ! ${DEEP_ONLY}; then
    if [ "${EFFECTIVE_REPORT_MODE}" = "impact" ] || ${IMPACT_ONLY}; then
        [ -f "${TEST_DIR}/impact_report.html" ] && echo "    ${TEST_DIR}/impact_report.html (impact 종합)"
    else
        [ -f "${TEST_DIR}/report.html" ] && echo "    ${TEST_DIR}/report.html (sphere 종합)"
    fi
fi
