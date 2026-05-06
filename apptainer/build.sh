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
# Output: apptainer/SmartTwinPostprocessor.sif,
#         apptainer/SmartTwinPostProcessorGUI.sif
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

VARIANT="${1:-headless}"

build_one() {
    local variant="$1"
    local def_file
    local sif_file

    case "${variant}" in
        headless)
            def_file="SmartTwinPostprocessor.def"
            sif_file="SmartTwinPostprocessor.sif"
            ;;
        full)
            def_file="SmartTwinPostProcessorGUI.def"
            sif_file="SmartTwinPostProcessorGUI.sif"
            ;;
        *)
            echo "ERROR: unknown variant: ${variant}"
            exit 1
            ;;
    esac

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
echo "  apptainer run SmartTwinPostprocessor.sif"
echo "  apptainer exec SmartTwinPostprocessor.sif post_analyze --help"
