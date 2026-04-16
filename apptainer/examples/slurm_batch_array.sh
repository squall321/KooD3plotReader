#!/bin/bash
#SBATCH --job-name=kood3plot_batch
#SBATCH --partition=normal
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --array=0-19%4
#SBATCH --output=logs/batch_%A_%a.out

# ============================================================
# KooD3plotReader — 배열 Job으로 여러 test_dir 병렬 처리
#
# 사용법:
#   1) test_dirs.txt 에 한 줄에 하나씩 test_dir 경로 작성
#   2) sbatch --array=0-$((N-1))%4 slurm_batch_array.sh
#
# %4 = 동시 실행 최대 4개
# ============================================================
set -euo pipefail

SIF="${SIF:-/opt/apptainers/SmartTwinPostprocessor.sif}"
LIST="${LIST:-test_dirs.txt}"

TEST_DIR=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" "$LIST")

if [ -z "$TEST_DIR" ]; then
    echo "No test_dir for array index $SLURM_ARRAY_TASK_ID"
    exit 1
fi

mkdir -p logs

echo "[Array $SLURM_ARRAY_TASK_ID/$SLURM_ARRAY_TASK_COUNT] $TEST_DIR"
echo "[Node] $(hostname) ($SLURM_CPUS_PER_TASK CPUs)"

apptainer exec --bind /data:/data "$SIF" \
    post_analyze "$TEST_DIR" \
    --threads "$SLURM_CPUS_PER_TASK" \
    --section-view --section-view-backend lsprepost
