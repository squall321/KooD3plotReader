#!/bin/bash
# ============================================================
# post_analyze.sh — SmartTwinPostProcessor 통합 후처리 오케스트레이션
# ============================================================
# test_dir 을 주면 unified_analyzer → deep_report batch → sphere_report
# 순서로 실행하여 모든 후처리 결과를 생성합니다.
#
# 각 단계는 기존 결과가 있으면 스킵합니다 (--force 로 강제 재계산).
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
DEEP_CONFIG=""       # koo_deep_report --config 로 전달할 YAML
DEEP_ONLY=false
SPHERE_ONLY=false
FORCE=false
THREADS=4
YIELD_STRESS=""

# deep_report 로 pass-through 할 편의 플래그 배열
DEEP_EXTRA=()
SPHERE_EXTRA=()

usage() {
    sed -n '/^# ==/,/^# ==/p' "$0" | sed 's/^# //' | head -55
    exit 1
}

while [[ $# -gt 0 ]]; do
    case $1 in
        # 오케스트레이션 제어
        --deep-only)     DEEP_ONLY=true; shift ;;
        --sphere-only)   SPHERE_ONLY=true; shift ;;
        --force)         FORCE=true; shift ;;

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
        --section-view)            DEEP_EXTRA+=(--section-view); shift ;;
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

if [ -z "${TEST_DIR}" ]; then
    echo "ERROR: test_dir 인자가 필요합니다."
    usage
fi

if [ ! -d "${TEST_DIR}" ]; then
    echo "ERROR: test_dir 없음: ${TEST_DIR}"
    exit 1
fi

if ${DEEP_ONLY} && ${SPHERE_ONLY}; then
    echo "ERROR: --deep-only 와 --sphere-only 는 동시 사용 불가"
    exit 1
fi

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
        echo "  SmartTwinPostProcessor.sif 안에서 실행하거나,"
        echo "  /data/SmartTwinPostprocessor/bin 을 PATH 에 추가하세요."
        exit 1
    fi
}
check_bin unified_analyzer
check_bin koo_deep_report
check_bin koo_sphere_report

# ============================================================
# 헤더
# ============================================================
mode_str="all"
${DEEP_ONLY}   && mode_str="deep-only"
${SPHERE_ONLY} && mode_str="sphere-only"

echo "============================================================"
echo " SmartTwinPostProcessor — Post Analyze"
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
echo "============================================================"

# ============================================================
# Step 1: unified_analyzer --recursive
#  - sphere_report 가 analysis_results/ 를 필요로 함
#  - 이미 있으면 스킵 (--force 로 강제)
# ============================================================
run_step_unified() {
    echo ""
    echo "=== [Step 1] unified_analyzer --recursive ==="

    if ${FORCE}; then
        echo "  FORCE 모드 — 기존 analysis_results/ 삭제"
        rm -rf "${ANALYSIS_DIR}"
    elif [ -d "${ANALYSIS_DIR}" ] && \
         [ "$(find "${ANALYSIS_DIR}" -name "analysis_result.json" 2>/dev/null | head -1)" != "" ]; then
        echo "  기존 analysis_results/ 존재 — SKIP"
        return 0
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

    mkdir -p "${ANALYSIS_DIR}"
    local cmd=(
        unified_analyzer
        --recursive "${OUTPUT_DIR}"
        --config "${CONFIG_FILE}"
        --output "${ANALYSIS_DIR}"
        --skip-existing
    )
    echo "  $ ${cmd[*]}"
    "${cmd[@]}"
}

# ============================================================
# Step 2: koo_deep_report batch --skip-existing
#  - 각 sim 별 deep 분석 + 개별 HTML 생성
#  - --deep-config 있으면 deep_report --config 로 전달
#  - DEEP_EXTRA 배열로 임의 옵션 pass-through
# ============================================================
run_step_deep() {
    echo ""
    echo "=== [Step 2] koo_deep_report batch ==="

    if ${FORCE}; then
        echo "  FORCE 모드 — 기존 deep_reports/ 삭제"
        rm -rf "${DEEP_REPORTS_DIR}"
    fi

    if [ ! -d "${OUTPUT_DIR}" ]; then
        echo "  ERROR: ${OUTPUT_DIR} 없음 (시뮬레이션 output 디렉토리)"
        return 1
    fi

    mkdir -p "${DEEP_REPORTS_DIR}"
    local cmd=(
        koo_deep_report batch "${OUTPUT_DIR}"
        --output "${DEEP_REPORTS_DIR}"
        --skip-existing
        --threads "${THREADS}"
    )
    [ -n "${DEEP_CONFIG}" ]  && cmd+=(--config "${DEEP_CONFIG}")
    [ -n "${YIELD_STRESS}" ] && cmd+=(--yield-stress "${YIELD_STRESS}")
    [ "${#DEEP_EXTRA[@]}" -gt 0 ] && cmd+=("${DEEP_EXTRA[@]}")

    echo "  $ ${cmd[*]}"
    "${cmd[@]}"
}

# ============================================================
# Step 3: koo_sphere_report --test-dir
#  - 전각도 DOE 종합 리포트 (analysis_results/ 필수)
# ============================================================
run_step_sphere() {
    echo ""
    echo "=== [Step 3] koo_sphere_report ==="

    if [ ! -d "${ANALYSIS_DIR}" ] || \
       [ "$(find "${ANALYSIS_DIR}" -name "analysis_result.json" 2>/dev/null | head -1)" = "" ]; then
        echo "  ERROR: analysis_results/ 없음 또는 비어있음"
        echo "         Step 1 을 먼저 실행하거나 --config 를 지정하세요"
        return 1
    fi

    local cmd=(koo_sphere_report --test-dir "${TEST_DIR}")
    [ -n "${YIELD_STRESS}" ] && cmd+=(--yield-stress "${YIELD_STRESS}")
    [ "${#SPHERE_EXTRA[@]}" -gt 0 ] && cmd+=("${SPHERE_EXTRA[@]}")

    echo "  $ ${cmd[*]}"
    "${cmd[@]}"
}

# ============================================================
# 실행 분기
# ============================================================
if ${DEEP_ONLY}; then
    # deep 만: unified_analyzer 선행 실행은 불필요 (deep 내부에서 처리)
    run_step_deep
elif ${SPHERE_ONLY}; then
    # sphere 만: unified_analyzer 필수
    run_step_unified
    run_step_sphere
else
    # 전체: unified_analyzer → deep → sphere
    run_step_unified
    run_step_deep
    run_step_sphere
fi

echo ""
echo "============================================================"
echo " 완료"
echo "============================================================"
echo "  결과 위치:"
${SPHERE_ONLY} || { [ -d "${DEEP_REPORTS_DIR}" ] && echo "    ${DEEP_REPORTS_DIR}/ (개별 deep HTML)"; }
${DEEP_ONLY}   || { [ -f "${TEST_DIR}/report.html" ] && echo "    ${TEST_DIR}/report.html (sphere 종합)"; }
