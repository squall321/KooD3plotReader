#!/bin/bash
# =============================================================================
# KooD3plot Build and Install Script
# =============================================================================
# This script builds and installs the KooD3plot library with all components.
#
# Usage:
#   ./build_and_install.sh [OPTIONS]
#
# Options:
#   --prefix=<path>     Installation prefix (default: ./installed)
#   --build-type=<type> Build type: Release, Debug, RelWithDebInfo (default: Release)
#   --jobs=<n>          Number of parallel build jobs (default: auto)
#   --clean             Clean build directory before building
#   --no-install        Build only, do not install
#   --help              Show this help message
#
# Examples:
#   ./build_and_install.sh                          # Build and install to ./installed
#   ./build_and_install.sh --prefix=/usr/local      # Install to /usr/local
#   ./build_and_install.sh --build-type=Debug       # Debug build
#   ./build_and_install.sh --clean --jobs=8         # Clean build with 8 jobs
# =============================================================================

set -e  # Exit on error

# Default values
PREFIX="$(pwd)/installed"
BUILD_TYPE="Release"
JOBS=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
CLEAN=false
INSTALL=true

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

show_help() {
    echo "KooD3plot Build and Install Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --prefix=<path>     Installation prefix (default: ./installed)"
    echo "  --build-type=<type> Build type: Release, Debug, RelWithDebInfo (default: Release)"
    echo "  --jobs=<n>          Number of parallel build jobs (default: auto)"
    echo "  --clean             Clean build directory before building"
    echo "  --no-install        Build only, do not install"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                              # Build and install to ./installed"
    echo "  $0 --prefix=/usr/local          # Install to /usr/local"
    echo "  $0 --build-type=Debug           # Debug build"
    echo "  $0 --clean --jobs=8             # Clean build with 8 jobs"
}

# Parse arguments
for arg in "$@"; do
    case $arg in
        --prefix=*)
            PREFIX="${arg#*=}"
            shift
            ;;
        --build-type=*)
            BUILD_TYPE="${arg#*=}"
            shift
            ;;
        --jobs=*)
            JOBS="${arg#*=}"
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        --no-install)
            INSTALL=false
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            show_help
            exit 1
            ;;
    esac
done

# Get script directory (source directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"

print_header "KooD3plot Build and Install"
echo ""
echo "Configuration:"
echo "  Source directory: ${SCRIPT_DIR}"
echo "  Build directory:  ${BUILD_DIR}"
echo "  Install prefix:   ${PREFIX}"
echo "  Build type:       ${BUILD_TYPE}"
echo "  Parallel jobs:    ${JOBS}"
echo ""

# Check for required tools
print_header "Checking Prerequisites"

# Check CMake
if ! command -v cmake &> /dev/null; then
    print_error "CMake not found. Please install CMake 3.15 or higher."
    exit 1
fi
CMAKE_VERSION=$(cmake --version | head -n1 | cut -d' ' -f3)
print_success "CMake found: ${CMAKE_VERSION}"

# Check compiler
if command -v g++ &> /dev/null; then
    GCC_VERSION=$(g++ --version | head -n1)
    print_success "g++ found: ${GCC_VERSION}"
elif command -v clang++ &> /dev/null; then
    CLANG_VERSION=$(clang++ --version | head -n1)
    print_success "clang++ found: ${CLANG_VERSION}"
else
    print_error "No C++ compiler found. Please install g++ or clang++."
    exit 1
fi

# Check for OpenMP (optional)
echo ""
echo "Checking for OpenMP support..."
if g++ -fopenmp -x c++ -c /dev/null -o /dev/null 2>/dev/null; then
    print_success "OpenMP supported"
else
    print_warning "OpenMP not available - parallel features will be disabled"
fi

# Clean build directory if requested
if [ "$CLEAN" = true ]; then
    print_header "Cleaning Build Directory"
    if [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
        print_success "Removed ${BUILD_DIR}"
    fi
fi

# Create build directory
mkdir -p "$BUILD_DIR"

# Configure
print_header "Configuring (CMake)"
cd "$BUILD_DIR"

cmake .. \
    -DCMAKE_BUILD_TYPE=${BUILD_TYPE} \
    -DCMAKE_INSTALL_PREFIX=${PREFIX} \
    -DKOOD3PLOT_BUILD_TESTS=ON \
    -DKOOD3PLOT_BUILD_EXAMPLES=ON \
    -DKOOD3PLOT_BUILD_V3_QUERY=ON \
    -DKOOD3PLOT_BUILD_V4_RENDER=ON \
    -DKOOD3PLOT_ENABLE_OPENMP=ON

print_success "Configuration complete"

# Build
print_header "Building (make -j${JOBS})"
make -j${JOBS}
print_success "Build complete"

# Install
if [ "$INSTALL" = true ]; then
    print_header "Installing to ${PREFIX}"
    make install
    print_success "Installation complete"

    # Create symlinks for convenience
    if [ -d "${PREFIX}/bin" ]; then
        echo ""
        echo "Installed executables:"
        ls -la "${PREFIX}/bin/" 2>/dev/null || true
    fi

    echo ""
    echo "Installed libraries:"
    ls -la "${PREFIX}/lib/"*.so 2>/dev/null || ls -la "${PREFIX}/lib/"*.a 2>/dev/null || true

    echo ""
    echo "Installed config files:"
    ls -la "${PREFIX}/share/kood3plot/config/" 2>/dev/null || true
fi

# Summary
print_header "Build Summary"
echo ""
echo "Build successful!"
echo ""
echo "Build output: ${BUILD_DIR}"
if [ "$INSTALL" = true ]; then
    echo "Installed to: ${PREFIX}"
    echo ""
    echo "To use KooD3plot:"
    echo "  1. Add ${PREFIX}/lib to LD_LIBRARY_PATH:"
    echo "     export LD_LIBRARY_PATH=${PREFIX}/lib:\$LD_LIBRARY_PATH"
    echo ""
    echo "  2. Run comprehensive example:"
    echo "     ${PREFIX}/bin/examples/comprehensive_example path/to/d3plot output_dir"
    echo ""
    echo "  3. Run full extraction example:"
    echo "     ${PREFIX}/bin/examples/full_extraction_example path/to/d3plot output_dir"
    echo ""
    echo "  4. Use CLI tool:"
    echo "     ${PREFIX}/bin/kood3plot_cli --help"
    echo ""
    echo "  5. Example config files:"
    echo "     ${PREFIX}/share/kood3plot/config/"
fi
echo ""
print_success "Done!"
