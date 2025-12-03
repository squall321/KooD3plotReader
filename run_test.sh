#!/bin/bash
# KooD3plot V4 Render Test Script
# 설치된 바이너리로 테스트를 실행합니다

# 프로젝트 루트 디렉토리
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 환경변수 설정
export LD_LIBRARY_PATH="${PROJECT_ROOT}/installed/lib:${PROJECT_ROOT}/installed/lsprepost/lib:${LD_LIBRARY_PATH}"
export PATH="${PROJECT_ROOT}/installed/bin:${PATH}"

# LSPrePost 경로 (상대경로)
LSPREPOST_PATH="./installed/lsprepost/lspp412_mesa"

echo "=========================================="
echo "KooD3plot V4 Render System Test"
echo "=========================================="
echo ""
echo "프로젝트 루트: $PROJECT_ROOT"
echo "LSPrePost 경로: $LSPREPOST_PATH"
echo ""

# 출력 디렉토리 생성
mkdir -p test_output

# 예제 선택
if [ "$1" == "batch" ]; then
    echo "=== 배치 처리 테스트 ==="
    echo ""

    # 설정 파일 생성
    cat > test_render_config.json << 'EOF'
{
  "analysis": {
    "data_path": "./results",
    "output_path": "./test_output"
  },
  "fringe": {
    "type": "von_mises",
    "min": 0,
    "max": 500,
    "auto_range": false
  },
  "output": {
    "movie": true,
    "images": false,
    "width": 1280,
    "height": 720,
    "fps": 30
  },
  "view": {
    "orientation": "left",
    "zoom_factor": 1.0,
    "auto_fit": true
  }
}
EOF

    # 배치 예제 실행
    ./installed/bin/v4_05_batch_with_config test_render_config.json

elif [ "$1" == "multisection" ]; then
    echo "=== 멀티섹션 테스트 ==="
    echo ""

    mkdir -p output_multisection
    # 멀티섹션 예제 실행
    ./installed/bin/v4_06_advanced_multisection

elif [ "$1" == "simple" ]; then
    echo "=== 간단한 렌더 테스트 ==="
    echo ""

    # 간단한 테스트 cfile 생성
    cat > test_simple.cfile << 'EOF'
open d3plot "results/d3plot"
ac
fringe 9
pfringe
range userdef 0 500
left
ac
fit
anim forward
movie mt 0
movie MP4/H264 1280x720 "test_output/simple_render.mp4" 30
exit
EOF

    echo "LSPrePost로 직접 렌더링..."
    export LD_LIBRARY_PATH="${PROJECT_ROOT}/installed/lsprepost/lib:${LD_LIBRARY_PATH}"
    timeout 180 "$LSPREPOST_PATH" -nographics c=test_simple.cfile

    if [ -f "test_output/simple_render.mp4" ]; then
        echo ""
        echo "✓ 렌더링 성공: test_output/simple_render.mp4"
        ls -lh test_output/simple_render.mp4
    else
        echo ""
        echo "✗ 렌더링 실패"
    fi

else
    echo "사용법: $0 {batch|multisection|simple}"
    echo ""
    echo "  batch        - 배치 처리 테스트 (v4_05_batch_with_config)"
    echo "  multisection - 멀티섹션 테스트 (v4_06_advanced_multisection)"
    echo "  simple       - LSPrePost 직접 실행 테스트"
    echo ""
    exit 1
fi

echo ""
echo "=========================================="
echo "테스트 완료"
echo "=========================================="
