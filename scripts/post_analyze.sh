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
ANALYSIS_GROUPS=()   # unified_analyzer 가 발견한 그룹 목록 (Output, Output2 등)
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
    cat << 'HELPEOF'
사용법:
    post_analyze <test_dir> [options]

  전체 파이프라인: unified_analyzer → sphere_report (빠름) → deep_report (느림)
  각 단계는 기존 결과가 있으면 자동 스킵 (--force 로 강제 재계산)

[모드]
    --deep-only             deep report 만
    --sphere-only           sphere report 만
    --force                 기존 결과 무시하고 전체 재계산

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
    -h|--help

예시:
    post_analyze /data/drop_test_001
    post_analyze /data/drop_test_001 --yield-stress 250 --threads 8
    post_analyze /data/drop_test_001 --deep-only --no-render
    post_analyze /data/drop_test_001 --sphere-only
    post_analyze /data/drop_test_001 --section-view --section-view-backend lsprepost
HELPEOF
    exit 0
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
    echo "=== [Step 1] unified_analyzer (Run 별 개별 분석) ==="

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

        # skip-existing 체크
        if [ -f "${result_dir}/analysis_result.json" ] && ! ${FORCE}; then
            _skip=$(( _skip + 1 ))
            continue
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

        printf "  [%d/%d] %s/%s → analysis_results/%s/%s ... " "${_idx}" "${_total}" "${run_name}" "${sub_path}" "${sub_path}" "${run_name}"

        if unified_analyzer --config "${tmp_yaml}" 2>&1 | tail -5; then
            echo "OK"
            _done=$(( _done + 1 ))
        else
            echo "FAIL"
            _fail=$(( _fail + 1 ))
        fi

        rm -f "${tmp_yaml}"
    done

    echo ""
    echo "  완료: ${_done} / 스킵: ${_skip} / 실패: ${_fail} / 전체: ${_total}"

    # 그룹 목록을 전역으로 저장 (sphere_report 에서 사용)
    ANALYSIS_GROUPS=()
    while read -r g; do
        [ -n "${g}" ] && ANALYSIS_GROUPS+=("${g}")
    done <<< "${UNIQUE_GROUPS}"
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
    echo "=== [Step 3] koo_deep_report batch (개별 분석 + 렌더) ==="

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
# 실행 분기
#   전체: unified_analyzer → sphere (빠름) → deep (느림)
#   sphere 먼저 → 종합 결과 빨리 확인, deep 은 렌더까지 하므로 나중에
# ============================================================
if ${DEEP_ONLY}; then
    # deep 만: unified_analyzer 선행 실행은 불필요 (deep 내부에서 처리)
    run_step_deep
elif ${SPHERE_ONLY}; then
    # sphere 만: unified_analyzer 필수
    run_step_unified
    run_step_sphere
else
    # 전체: unified_analyzer → sphere (빠름) → deep (느림)
    run_step_unified
    run_step_sphere
    run_step_deep
fi

echo ""
echo "============================================================"
echo " 완료"
echo "============================================================"
echo "  결과 위치:"
${SPHERE_ONLY} || { [ -d "${DEEP_REPORTS_DIR}" ] && echo "    ${DEEP_REPORTS_DIR}/ (개별 deep HTML)"; }
${DEEP_ONLY}   || { [ -f "${TEST_DIR}/report.html" ] && echo "    ${TEST_DIR}/report.html (sphere 종합)"; }
