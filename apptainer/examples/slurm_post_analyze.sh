#!/bin/bash
#SBATCH --job-name=kood3plot_post
#SBATCH --partition=normal
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/kood3plot_%j.out
#SBATCH --error=logs/kood3plot_%j.err

# ============================================================
# KooD3plotReader — 단일 test_dir 후처리 (unified → deep → sphere)
#
# 사용법:
#   sbatch slurm_post_analyze.sh /data/drop_test_001
#
# 옵션 환경변수:
#   SIF=/path/to/kood3plot_headless.sif  (기본: 현재 디렉토리)
#   YIELD=250                            (기본: 미지정)
#   EXTRA="--section-view --section-view-backend lsprepost"
# ============================================================
set -euo pipefail

TEST_DIR="${1:-}"
if [ -z "$TEST_DIR" ]; then
    echo "Usage: sbatch $0 <test_dir>"
    exit 1
fi

SIF="${SIF:-/opt/containers/kood3plot_headless.sif}"
YIELD="${YIELD:-}"
EXTRA="${EXTRA:---section-view --section-view-backend lsprepost}"

mkdir -p logs

echo "============================================================"
echo " KooD3plotReader Post-Analyze (Slurm Job $SLURM_JOB_ID)"
echo "============================================================"
echo "  Node:      $(hostname)"
echo "  CPUs:      $SLURM_CPUS_PER_TASK"
echo "  Test dir:  $TEST_DIR"
echo "  SIF:       $SIF"
echo "  Yield:     ${YIELD:-(none)}"
echo "  Extra:     $EXTRA"
echo "============================================================"

ARGS=("$TEST_DIR" --threads "$SLURM_CPUS_PER_TASK")
[ -n "$YIELD" ] && ARGS+=(--yield-stress "$YIELD")
ARGS+=($EXTRA)

apptainer exec --bind /data:/data "$SIF" post_analyze "${ARGS[@]}"

echo ""
echo "Completed: $(date)"
