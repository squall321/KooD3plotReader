#!/bin/bash
# ============================================================
# apptainer/build.sh — Build KooD3plotReader Apptainer images
# ============================================================
#
# Usage:
#   ./apptainer/build.sh headless    # Slurm-ready (no GUI)
#   ./apptainer/build.sh full        # Desktop (with GUI viewer)
#   ./apptainer/build.sh both        # Both variants
#
# Output: apptainer/kood3plot_{headless,full}.sif
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

VARIANT="${1:-headless}"

build_one() {
    local variant="$1"
    local def_file="KooD3plotReader_${variant}.def"
    local sif_file="kood3plot_${variant}.sif"

    if [ ! -f "${def_file}" ]; then
        echo "ERROR: ${def_file} not found"
        exit 1
    fi

    echo "==============================================="
    echo " Building ${sif_file}"
    echo "==============================================="
    apptainer build --force "${sif_file}" "${def_file}"

    echo ""
    echo "Built: ${SCRIPT_DIR}/${sif_file}"
    ls -lh "${sif_file}"
    echo ""
}

case "${VARIANT}" in
    headless) build_one headless ;;
    full)     build_one full ;;
    both)     build_one headless; build_one full ;;
    *)
        echo "Usage: $0 {headless|full|both}"
        exit 1
        ;;
esac

echo "Done. Test with:"
echo "  apptainer run SmartTwinPostprocessor_headless.sif"
echo "  apptainer exec SmartTwinPostprocessor_headless.sif post_analyze --help"
