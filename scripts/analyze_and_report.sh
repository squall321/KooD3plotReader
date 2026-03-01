#!/bin/bash
# ============================================================
#  analyze_and_report.sh
#  전각도 낙하 시뮬레이션 통합 파이프라인
#  Step 1: unified_analyzer (d3plot → analysis_results)
#  Step 2: koo_report       (analysis_results → HTML report)
#  Step 3: render (선택) — render_config.yaml → 단면 영상 렌더링
# ============================================================
set -e

# ---- 경로 설정 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ANALYZER="$PROJECT_ROOT/installed/bin/unified_analyzer"
KOO_REPORT="$PROJECT_ROOT/installed/bin/koo_report"
KOO_REPORT_PY="$PROJECT_ROOT/python/koo_report"
DEFAULT_CONFIG="common_analysis.yaml"

# ---- 색상 ----
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

usage() {
    cat <<'USAGE'
Usage: analyze_and_report.sh <test-dir> [options]

필수:
  <test-dir>              테스트 디렉토리 (output/ 포함)

분석 옵션:
  --config <yaml>         분석 설정 파일 (기본: <test-dir>/common_analysis.yaml)
  --threads <N>           분석 스레드 수 (기본: 4)
  --force-reanalyze       기존 분석 결과 무시하고 전체 재분석

리포트 옵션:
  --yield-stress <MPa>    항복응력 (안전계수 계산용)
  --ts-points <N>         시계열 해상도 (0=자동)
  --output <path>         HTML 리포트 출력 경로
  --no-report             분석만 수행, 리포트 생성 안 함
  --no-analyze            분석 건너뛰기, 리포트만 생성
  --report-only           --no-analyze와 동일

렌더링 옵션:
  --render-config <yaml>  렌더 설정 파일 (KooReport에서 생성)
  --render-only           렌더링만 수행 (분석/리포트 건너뛰기)

예시:
  # 기본 실행 (분석 + 리포트)
  analyze_and_report.sh /data/Tests/Test_001_Full26_1Step

  # 항복응력 지정
  analyze_and_report.sh /data/Tests/Test_001 --yield-stress 275

  # 리포트만 재생성
  analyze_and_report.sh /data/Tests/Test_006 --report-only --ts-points 30

  # 강제 재분석 + 경량 리포트
  analyze_and_report.sh /data/Tests/Test_006 --force-reanalyze --ts-points 10

  # 리포트에서 생성한 render_config로 단면 영상 렌더링
  analyze_and_report.sh /data/Tests/Test_001 --render-config render_config.yaml

  # 렌더링만 수행 (분석/리포트 건너뛰기)
  analyze_and_report.sh /data/Tests/Test_001 --render-only --render-config render_config.yaml
USAGE
    exit 1
}

# ---- 인자 파싱 ----
[ $# -lt 1 ] && usage

TEST_DIR="$(cd "$1" 2>/dev/null && pwd)" || { echo -e "${RED}Error: $1 does not exist${NC}"; exit 1; }
shift

CONFIG=""
THREADS=4
YIELD_STRESS=0
TS_POINTS=0
OUTPUT_HTML=""
SKIP_EXISTING="--skip-existing"
DO_ANALYZE=true
DO_REPORT=true
RENDER_CONFIG=""
DO_RENDER=false

while [ $# -gt 0 ]; do
    case "$1" in
        --config)        CONFIG="$2"; shift 2 ;;
        --threads)       THREADS="$2"; shift 2 ;;
        --yield-stress)  YIELD_STRESS="$2"; shift 2 ;;
        --ts-points)     TS_POINTS="$2"; shift 2 ;;
        --output)        OUTPUT_HTML="$2"; shift 2 ;;
        --force-reanalyze) SKIP_EXISTING=""; shift ;;
        --no-report)     DO_REPORT=false; shift ;;
        --no-analyze|--report-only) DO_ANALYZE=false; shift ;;
        --render-config) RENDER_CONFIG="$2"; DO_RENDER=true; shift 2 ;;
        --render-only)   DO_RENDER=true; DO_ANALYZE=false; DO_REPORT=false; shift ;;
        -h|--help)       usage ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; usage ;;
    esac
done

# ---- 설정 파일 탐색 ----
if [ "$DO_ANALYZE" = true ]; then
    if [ -z "$CONFIG" ]; then
        if [ -f "$TEST_DIR/$DEFAULT_CONFIG" ]; then
            CONFIG="$TEST_DIR/$DEFAULT_CONFIG"
        else
            echo -e "${RED}Error: $TEST_DIR/$DEFAULT_CONFIG not found${NC}"
            echo "  --config <yaml> 옵션으로 지정하세요."
            exit 1
        fi
    fi
fi

# ---- 단계 수 결정 ----
TOTAL_STEPS=2
if [ "$DO_RENDER" = true ]; then TOTAL_STEPS=3; fi

ANALYSIS_DIR="$TEST_DIR/analysis_results"
OUTPUT_DIR="$TEST_DIR/output"

echo -e "${CYAN}=========================================="
echo " 전각도 낙하 시뮬레이션 통합 파이프라인"
echo -e "==========================================${NC}"
echo -e "  테스트: ${GREEN}$(basename "$TEST_DIR")${NC}"
echo -e "  설정:  $CONFIG"
echo -e "  분석:  $DO_ANALYZE | 리포트: $DO_REPORT | 렌더: $DO_RENDER"
echo ""

# ============================================================
#  Step 1: unified_analyzer
# ============================================================
if [ "$DO_ANALYZE" = true ]; then
    echo -e "${YELLOW}[Step 1/${TOTAL_STEPS}] d3plot 분석 (unified_analyzer)${NC}"
    echo "────────────────────────────────────────"

    if [ ! -d "$OUTPUT_DIR" ]; then
        echo -e "${RED}Error: output/ 디렉토리가 없습니다.${NC}"
        echo "  LS-DYNA 시뮬레이션을 먼저 실행하세요."
        exit 1
    fi

    # d3plot 개수 확인
    N_D3PLOT=$(find "$OUTPUT_DIR" -maxdepth 2 -name "d3plot" -type f 2>/dev/null | wc -l)
    echo -e "  d3plot 파일: ${GREEN}${N_D3PLOT}개${NC}"

    if [ "$N_D3PLOT" -eq 0 ]; then
        echo -e "${RED}Error: d3plot 파일이 없습니다.${NC}"
        exit 1
    fi

    # 기존 분석 결과 확인
    if [ -d "$ANALYSIS_DIR" ]; then
        N_EXISTING=$(find "$ANALYSIS_DIR" -maxdepth 2 -name "analysis_result.json" -type f 2>/dev/null | wc -l)
        echo -e "  기존 분석: ${N_EXISTING}개"
        if [ -n "$SKIP_EXISTING" ]; then
            echo -e "  모드: ${GREEN}신규만 분석${NC} (--skip-existing)"
        else
            echo -e "  모드: ${YELLOW}전체 재분석${NC} (--force-reanalyze)"
        fi
    else
        echo "  기존 분석: 없음 (신규 분석)"
    fi

    if [ ! -x "$ANALYZER" ]; then
        echo -e "${RED}Error: unified_analyzer not found: $ANALYZER${NC}"
        echo "  cd build && cmake .. && make -j4 unified_analyzer"
        exit 1
    fi

    echo ""
    T_START=$SECONDS

    "$ANALYZER" \
        --recursive "$OUTPUT_DIR" \
        --config "$CONFIG" \
        --output "$ANALYSIS_DIR" \
        $SKIP_EXISTING

    T_ANALYZE=$((SECONDS - T_START))
    N_RESULTS=$(find "$ANALYSIS_DIR" -maxdepth 2 -name "analysis_result.json" -type f 2>/dev/null | wc -l)
    echo ""
    echo -e "  ${GREEN}분석 완료: ${N_RESULTS}개 결과 (${T_ANALYZE}초)${NC}"
    echo ""
else
    echo -e "${YELLOW}[Step 1/${TOTAL_STEPS}] 분석 건너뛰기 (--no-analyze)${NC}"
    if [ ! -d "$ANALYSIS_DIR" ]; then
        echo -e "${RED}Error: analysis_results/ 가 없습니다. --no-analyze를 제거하세요.${NC}"
        exit 1
    fi
    N_RESULTS=$(find "$ANALYSIS_DIR" -maxdepth 2 -name "analysis_result.json" -type f 2>/dev/null | wc -l)
    echo -e "  기존 분석 결과: ${GREEN}${N_RESULTS}개${NC}"
    echo ""
fi

# ============================================================
#  Step 2: koo_report
# ============================================================
if [ "$DO_REPORT" = true ]; then
    echo -e "${YELLOW}[Step 2/${TOTAL_STEPS}] HTML 리포트 생성 (koo_report)${NC}"
    echo "────────────────────────────────────────"

    # koo_report 실행 방법 결정
    REPORT_CMD=""
    REPORT_ARGS=()

    if [ -x "$KOO_REPORT" ]; then
        REPORT_CMD="$KOO_REPORT"
    elif [ -d "$KOO_REPORT_PY/koo_report" ]; then
        REPORT_CMD="python3 -m koo_report"
        cd "$KOO_REPORT_PY"
    else
        echo -e "${RED}Error: koo_report not found${NC}"
        echo "  바이너리: $KOO_REPORT"
        echo "  Python:   $KOO_REPORT_PY"
        exit 1
    fi

    REPORT_ARGS+=("--test-dir" "$TEST_DIR")

    if [ -n "$OUTPUT_HTML" ]; then
        REPORT_ARGS+=("--output" "$OUTPUT_HTML")
    fi

    if [ "$YIELD_STRESS" != "0" ]; then
        REPORT_ARGS+=("--yield-stress" "$YIELD_STRESS")
    fi

    if [ "$TS_POINTS" != "0" ]; then
        REPORT_ARGS+=("--ts-points" "$TS_POINTS")
    fi

    echo -e "  명령: $REPORT_CMD ${REPORT_ARGS[*]}"
    echo ""

    T_START=$SECONDS
    $REPORT_CMD "${REPORT_ARGS[@]}"
    T_REPORT=$((SECONDS - T_START))

    # 리포트 경로/크기 출력
    FINAL_HTML="${OUTPUT_HTML:-$TEST_DIR/report.html}"
    if [ -f "$FINAL_HTML" ]; then
        SIZE_KB=$(du -k "$FINAL_HTML" | cut -f1)
        echo ""
        echo -e "  ${GREEN}리포트 생성 완료 (${T_REPORT}초, ${SIZE_KB} KB)${NC}"
        echo -e "  경로: ${CYAN}${FINAL_HTML}${NC}"
    fi
    echo ""
else
    echo -e "${YELLOW}[Step 2/${TOTAL_STEPS}] 리포트 건너뛰기 (--no-report)${NC}"
    echo ""
fi

# ============================================================
#  Step 3: 렌더링 (선택)
# ============================================================
N_RENDERED=0
if [ "$DO_RENDER" = true ]; then
    echo -e "${YELLOW}[Step 3/${TOTAL_STEPS}] 단면 영상 렌더링${NC}"
    echo "────────────────────────────────────────"

    if [ -z "$RENDER_CONFIG" ]; then
        echo -e "${RED}Error: --render-config <yaml> 이 필요합니다.${NC}"
        echo "  KooReport의 Render Export 탭에서 YAML을 다운로드하세요."
        exit 1
    fi

    if [ ! -f "$RENDER_CONFIG" ]; then
        echo -e "${RED}Error: $RENDER_CONFIG 파일이 없습니다.${NC}"
        exit 1
    fi

    if [ ! -x "$ANALYZER" ]; then
        echo -e "${RED}Error: unified_analyzer not found: $ANALYZER${NC}"
        exit 1
    fi

    # YAML에서 render_jobs 수 확인
    N_JOBS=$(grep -c '^\s*- name:' "$RENDER_CONFIG" 2>/dev/null || echo 0)
    echo -e "  렌더 설정: ${CYAN}${RENDER_CONFIG}${NC}"
    echo -e "  렌더 작업: ${GREEN}${N_JOBS}개${NC}"

    if [ "$N_JOBS" -eq 0 ]; then
        echo -e "${YELLOW}Warning: render_jobs가 없습니다.${NC}"
    else
        # YAML에서 각 job을 분리하여 순차 실행
        # 각 job은 고유한 input(d3plot) 경로를 가지므로 개별 실행 필요
        RENDER_TMP_DIR=$(mktemp -d)
        trap "rm -rf $RENDER_TMP_DIR" EXIT

        # Python으로 YAML 분할 (가장 안정적인 방법)
        python3 -c "
import sys, os
try:
    import yaml
except ImportError:
    # PyYAML 없으면 간단한 줄 기반 파서 사용
    print('NOYAML')
    sys.exit(0)

with open('$RENDER_CONFIG') as f:
    cfg = yaml.safe_load(f)

jobs = cfg.get('render_jobs', [])
perf = cfg.get('performance', {})

for i, job in enumerate(jobs):
    single = {
        'version': cfg.get('version', '2.0'),
        'performance': perf,
        'input': {'d3plot': job.get('input', '')},
        'render_jobs': [job]
    }
    out_path = os.path.join('$RENDER_TMP_DIR', f'job_{i:03d}.yaml')
    with open(out_path, 'w') as f:
        yaml.dump(single, f, default_flow_style=False, allow_unicode=True)
print(str(len(jobs)))
" > "$RENDER_TMP_DIR/count.txt" 2>/dev/null

        JOB_RESULT=$(cat "$RENDER_TMP_DIR/count.txt")

        if [ "$JOB_RESULT" = "NOYAML" ]; then
            # PyYAML 미설치: 전체 YAML을 그대로 unified_analyzer에 전달
            echo -e "  ${YELLOW}PyYAML 미설치 — 단일 실행 모드${NC}"
            echo ""
            T_START=$SECONDS
            "$ANALYZER" --config "$RENDER_CONFIG" --render-only || true
            T_RENDER=$((SECONDS - T_START))
            N_RENDERED=1
            echo ""
            echo -e "  ${GREEN}렌더링 완료 (${T_RENDER}초)${NC}"
        else
            # 분할된 job별 실행
            JOB_COUNT=$(ls "$RENDER_TMP_DIR"/job_*.yaml 2>/dev/null | wc -l)
            echo -e "  분할: ${JOB_COUNT}개 작업"
            echo ""

            T_START=$SECONDS
            JOB_IDX=0
            for JOB_YAML in "$RENDER_TMP_DIR"/job_*.yaml; do
                JOB_IDX=$((JOB_IDX + 1))
                JOB_NAME=$(grep 'name:' "$JOB_YAML" | head -1 | sed 's/.*name:\s*//' | tr -d '"' | tr -d "'")
                echo -e "  [${JOB_IDX}/${JOB_COUNT}] ${CYAN}${JOB_NAME}${NC}"

                "$ANALYZER" --config "$JOB_YAML" --render-only 2>&1 | while IFS= read -r line; do
                    echo "    $line"
                done || true

                N_RENDERED=$((N_RENDERED + 1))
            done
            T_RENDER=$((SECONDS - T_START))
            echo ""
            echo -e "  ${GREEN}렌더링 완료: ${N_RENDERED}개 작업 (${T_RENDER}초)${NC}"
        fi
    fi
    echo ""
else
    if [ -n "$RENDER_CONFIG" ]; then
        echo -e "${YELLOW}[Step 3/${TOTAL_STEPS}] 렌더 설정이 있으나 --render-only 미지정${NC}"
        echo ""
    fi
fi

# ============================================================
#  완료
# ============================================================
echo -e "${CYAN}=========================================="
echo -e " 완료"
echo -e "==========================================${NC}"
echo -e "  테스트:     $(basename "$TEST_DIR")"
echo -e "  분석 결과:  ${N_RESULTS:-0}개"
if [ "$DO_REPORT" = true ] && [ -f "${OUTPUT_HTML:-$TEST_DIR/report.html}" ]; then
    echo -e "  리포트:     ${OUTPUT_HTML:-$TEST_DIR/report.html}"
fi
if [ "$DO_RENDER" = true ] && [ "$N_RENDERED" -gt 0 ]; then
    echo -e "  렌더링:     ${N_RENDERED}개 완료"
fi
echo ""
