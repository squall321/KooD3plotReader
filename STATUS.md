# KooD3plotReader — Installation & Usage Manual

**Version**: v2.3.0 | **Date**: 2026-04-13 | **Repository**: github.com/squall321/KooD3plotReader

This document is a complete manual for building, installing, and running KooD3plotReader inside an Apptainer (Singularity) container or on a bare Linux system. Another AI or human should be able to set up the entire pipeline from this document alone.

---

## 1. System Overview

KooD3plotReader is a post-processing toolchain for LS-DYNA d3plot simulation results. It consists of:

```
┌─────────────────────────────────────────────────────────────────┐
│                     KooD3plotReader v2.3.0                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  C++ Core (libkood3plot.a)                                      │
│    ├─ D3plotReader: binary d3plot parser (multi-file, parallel)  │
│    ├─ SurfaceExtractor: exterior face extraction                │
│    ├─ SinglePassAnalyzer: stress/strain/motion per part per state│
│    ├─ SectionViewRenderer: software rasterizer (VTK-free)       │
│    └─ LSPrePostRenderer: batch cfile rendering                  │
│                                                                 │
│  unified_analyzer (C++ CLI executable)                          │
│    └─ Reads d3plot → outputs analysis_result.json + CSV files   │
│                                                                 │
│  koo_deep_report (Python package)                               │
│    └─ Wraps unified_analyzer → generates HTML report            │
│                                                                 │
│  koo_sphere_report (Python package)                             │
│    └─ Aggregates multi-angle results → sphere report            │
│                                                                 │
│  koo_viewer (C++ GUI executable)                                │
│    └─ Interactive desktop viewer (OpenGL 3.3 + ImGui)           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Component Relationships

```
                 ┌──────────────────────┐
                 │   unified_analyzer   │  C++ binary
                 │   (d3plot → CSV/JSON)│
                 └──────┬───────────────┘
                        │ subprocess call
           ┌────────────┼────────────────┐
           │            │                │
           ▼            ▼                ▼
    ┌──────────┐ ┌──────────────┐ ┌──────────────┐
    │koo_deep  │ │koo_sphere    │ │  koo_viewer   │
    │_report   │ │_report       │ │  (GUI)        │
    │(Python)  │ │(Python)      │ │  (C++)        │
    └──────────┘ └──────────────┘ └──────────────┘
    Single sim    Multi-angle DOE   Interactive
    HTML report   HTML + JSON       3D viewer
```

- `unified_analyzer` is the core engine. It reads d3plot binary files and produces CSV + JSON.
- `koo_deep_report` is a Python wrapper that calls `unified_analyzer` via subprocess, then reads CSV/JSON outputs to generate an HTML report.
- `koo_sphere_report` reads analysis_result.json from many run directories (produced by `unified_analyzer --recursive`) and generates a sphere coverage report.
- `koo_viewer` is a standalone GUI that reads JSON outputs for visualization. It does NOT need unified_analyzer at runtime (reads pre-generated data).

---

## 2. Prerequisites

### 2.1 System Packages (Ubuntu 22.04 / 24.04)

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    g++ \
    libomp-dev \
    python3 \
    python3-pip \
    python3-tk \
    ffmpeg \
    libpng-dev \
    libgl-dev \
    libx11-dev \
    libxrandr-dev \
    libxinerama-dev \
    libxcursor-dev \
    libxi-dev \
    libxext-dev \
    libwayland-dev \
    libxkbcommon-dev
```

| Package | Required By | Purpose |
|---------|-------------|---------|
| `cmake`, `g++`, `build-essential` | All C++ | Build system |
| `libomp-dev` | `kood3plot` | OpenMP parallel d3plot read |
| `python3` (>= 3.10) | Python packages | Runtime |
| `ffmpeg` | Section view render | MP4 encoding from PNG frames |
| `libpng-dev` | `kood3plot_section_render` | PNG frame output |
| `libgl-dev`, `libx11-dev`, etc. | `koo_viewer` | OpenGL 3.3 + GLFW windowing |

**Headless server (no viewer)**: skip all `lib*-dev` X11/GL packages. Only `cmake g++ libomp-dev python3 ffmpeg libpng-dev` needed.

### 2.2 Optional Dependencies

| Package | Purpose | Without It |
|---------|---------|------------|
| LSPrePost (`lspp412_mesa`) | Batch rendering (animations, per-part views) | Render features disabled; analysis still works |
| `customtkinter` (pip) | koo_deep_report GUI mode | GUI mode unavailable; CLI still works |
| `rich` (pip) | koo_sphere_report terminal output | Required by sphere report |
| `pyinstaller` (pip) | Build standalone exe | Use `python3 -m` instead |

---

## 3. Build Instructions

### 3.1 Clone and Build Everything

```bash
git clone git@github.com:squall321/KooD3plotReader.git
cd KooD3plotReader

# Configure (Release build, all features)
cmake -B build -DCMAKE_BUILD_TYPE=Release \
    -DKOOD3PLOT_BUILD_V4_RENDER=ON \
    -DKOOD3PLOT_BUILD_SECTION_RENDER=ON \
    -DKOOD3PLOT_ENABLE_OPENMP=ON

# Build all targets
cmake --build build -j$(nproc)

# Install Python packages
pip install -e python/koo_deep_report/
pip install -e python/koo_sphere_report/
```

### 3.2 Build Specific Targets Only

```bash
# Headless analysis only (no GUI, no viewer)
cmake --build build --target unified_analyzer -j$(nproc)

# Viewer only (needs OpenGL/X11 libs)
cmake --build build --target koo_viewer -j$(nproc)

# Both main executables
cmake --build build --target unified_analyzer koo_viewer -j$(nproc)
```

### 3.3 CMake Options Reference

| Option | Default | Description |
|--------|---------|-------------|
| `KOOD3PLOT_BUILD_V4_RENDER` | ON | LSPrePost batch rendering support |
| `KOOD3PLOT_BUILD_SECTION_RENDER` | OFF | Software section view renderer (needs libpng) |
| `KOOD3PLOT_BUILD_VIEWER` | ON | KooViewer GUI (needs OpenGL + X11 libs) |
| `KOOD3PLOT_ENABLE_OPENMP` | ON | Parallel d3plot reading |
| `KOOD3PLOT_ENABLE_SIMD` | ON | SIMD optimizations |
| `KOOD3PLOT_BUILD_V3_QUERY` | ON | Query system |
| `KOOD3PLOT_BUILD_V2_WRITER` | ON | D3plot write-back |
| `KOOD3PLOT_BUILD_V2_CONVERTER` | ON | Format converters |
| `KOOD3PLOT_BUILD_HDF5` | ON | HDF5 export (needs libhdf5) |
| `KOOD3PLOT_BUILD_CAPI` | ON | C API shared library (.NET) |
| `KOOD3PLOT_BUILD_TESTS` | ON | Unit tests |
| `KOOD3PLOT_BUILD_EXAMPLES` | ON | Example programs |

### 3.4 Using install.sh (Recommended for Apptainer)

```bash
# Full install to ./dist/
./install.sh

# Custom install prefix
./install.sh --prefix=/opt/kood3plot

# After install, activate environment:
source /opt/kood3plot/activate.sh
```

`install.sh` produces this layout:

```
/opt/kood3plot/
├── bin/
│   ├── unified_analyzer          # C++ binary
│   ├── koo_deep_report           # Shell wrapper → python3 -m koo_deep_report
│   ├── koo_deep_report_gui       # PyInstaller standalone (if built)
│   └── koo_viewer                # GUI binary (if built with X11/GL)
├── python/
│   └── koo_deep_report/
│       └── koo_deep_report/      # Python source
├── activate.sh                   # source this to set PATH/PYTHONPATH
└── update.sh                     # git pull + rebuild
```

### 3.5 Build Output Locations

| Binary | Path | Size (approx) |
|--------|------|---------------|
| `unified_analyzer` | `build/examples/unified_analyzer` | ~15 MB |
| `koo_viewer` | `build/viewer/koo_viewer` | ~25 MB |
| `libkood3plot.a` | `build/libkood3plot.a` | ~8 MB |

---

## 4. Executable Reference

### 4.1 unified_analyzer (C++ CLI)

The core analysis engine. Reads LS-DYNA d3plot files and produces CSV + JSON output.

```bash
# Single d3plot analysis with YAML config
unified_analyzer --config analysis.yaml

# Generate example YAML config
unified_analyzer --generate-config > analysis.yaml

# Recursive batch analysis (for sphere report pipeline)
unified_analyzer --recursive /data/test_dir/output \
    --config analysis.yaml \
    --output /data/test_dir/analysis_results \
    --skip-existing \
    --threads 4

# Analysis only (skip rendering)
unified_analyzer --config analysis.yaml --analysis-only

# Render only (skip analysis, use existing CSV/JSON)
unified_analyzer --config analysis.yaml --render-only
```

**CLI Options:**

| Flag | Description |
|------|-------------|
| `--config <file>` | YAML configuration file (required for analysis) |
| `--recursive <dir>` | Scan directory for d3plot files recursively |
| `--output <dir>` | Output directory (default: `./analysis_output`) |
| `--skip-existing` | Skip folders with existing `analysis_result.json` |
| `--threads N` | OpenMP threads (0 = auto) |
| `--analysis-only` | Run analysis, skip rendering |
| `--render-only` | Run rendering, skip analysis |
| `--generate-config` | Print example YAML to stdout |
| `--help` | Show help |

**YAML Configuration (generated by `--generate-config`):**

```yaml
version: "2.0"
input:
  d3plot: "results/d3plot"
output:
  directory: "./analysis_output"
  json: true
  csv: true
performance:
  threads: 0
  render_threads: 1
  sv_threads: 2
  verbose: true
analysis_jobs:
  - name: "All Parts Stress"
    type: von_mises
    parts: []           # empty = all parts
    output_prefix: "stress"
  - name: "Strain"
    type: eff_plastic_strain
    parts: [1, 2, 3]
    output_prefix: "strain"
  - name: "Motion"
    type: part_motion
    parts: [100, 101]
    quantities: [avg_displacement, avg_velocity, avg_acceleration]
    output_prefix: "motion"
```

**Output Structure:**

```
analysis_output/
├── analysis_result.json       # Metadata + per-part summaries
├── stress/
│   ├── part_1_von_mises.csv   # Time, Max_VonMises, Min_VonMises, Avg_VonMises, Max_Element_ID
│   ├── part_2_von_mises.csv
│   └── ...
├── strain/
│   ├── part_1_eff_plastic_strain.csv
│   └── ...
├── motion/
│   ├── part_1_motion.csv      # Time, Avg_Disp_X/Y/Z/Mag, Avg_Vel_*, Avg_Acc_*, Max_Disp_Mag
│   └── ...
├── surface/
│   └── (surface stress data)
└── renders/                   # Only if rendering enabled + LSPrePost available
    ├── overview.mp4
    └── section_view_z/
        └── section_view.mp4
```

### 4.2 koo_deep_report (Python CLI)

Wraps `unified_analyzer` and generates a comprehensive HTML report for a single simulation.

**Internally calls `unified_analyzer` via subprocess** — the user does NOT need to run unified_analyzer manually.

```bash
# Basic: single d3plot → HTML report
koo_deep_report /path/to/d3plot
# or
python3 -m koo_deep_report /path/to/d3plot

# With options
koo_deep_report /path/to/d3plot \
    --output ./my_report \
    --yield-stress 250 \
    --parts 1 2 3 4 \
    --section-view \
    --section-view-axes x y z \
    --ua-threads 4 \
    --verbose

# Batch mode: analyze all d3plot files under a directory
koo_deep_report batch /data/simulations \
    --skip-existing \
    --threads 2

# GUI mode (requires customtkinter)
koo_deep_report gui

# If unified_analyzer is not in PATH, specify install dir:
koo_deep_report /path/to/d3plot --install-dir /opt/kood3plot
```

**Key CLI Options:**

| Flag | Description |
|------|-------------|
| `path` | d3plot file or simulation directory |
| `--output, -o` | Output directory (default: `./single_report`) |
| `--yield-stress MPa` | Material yield stress for safety factor |
| `--strain-limit EPS` | Strain limit (default: 0.002 = 0.2%) |
| `--parts ID [ID ...]` | Specific part IDs to analyze (default: all) |
| `--no-render` | Skip LSPrePost rendering |
| `--per-part-render` | Render each part individually |
| `--ua-threads N` | Threads for unified_analyzer (0=auto) |
| `--render-threads N` | Parallel LSPrePost instances |
| `--section-view` | Enable software section view rendering |
| `--section-view-axes AXIS [...]` | Section axes: x, y, z (default: all) |
| `--install-dir DIR` | Where to find unified_analyzer binary |
| `--verbose, -v` | Show unified_analyzer output |
| `--config, -c YAML` | Use YAML config file (overrides CLI args) |
| `--element-quality` | Enable element quality analysis |

**unified_analyzer Discovery Order:**

1. `--install-dir` flag → `<dir>/bin/unified_analyzer`
2. PyInstaller frozen exe directory (same folder)
3. Package relative paths: `../../bin/`, `../../build/examples/`
4. System PATH (`which unified_analyzer`)

**Output:**

```
my_report/
├── analysis_result.json
├── stress/, strain/, motion/     # CSV data
├── renders/                      # MP4 animations (if rendering enabled)
└── deep_report.html              # Self-contained HTML report
```

### 4.3 koo_sphere_report (Python CLI)

Aggregates results from multiple drop angle simulations into a sphere coverage report.

**Does NOT call unified_analyzer** — expects `analysis_results/` to already exist (pre-generated by `unified_analyzer --recursive` or by `koo_deep_report batch`).

```bash
# From test directory (requires analysis_results/ and output/ subdirs)
koo_sphere_report --test-dir /data/drop_test_001 \
    --format html json terminal \
    --yield-stress 250

# From pre-generated JSON (no d3plot needed)
koo_sphere_report --from-json /data/drop_test_001/sphere_report.json

# JSON output only
koo_sphere_report --test-dir /data/drop_test_001 \
    --format json \
    --json sphere_report.json
```

**CLI Options:**

| Flag | Description |
|------|-------------|
| `--test-dir DIR` | Test directory with `output/` and `analysis_results/` |
| `--from-json FILE` | Re-generate report from existing JSON |
| `--output, -o FILE` | Output HTML path |
| `--json FILE` | Output JSON path |
| `--format [html json terminal]` | Output formats (default: html terminal) |
| `--yield-stress FLOAT` | Yield stress for safety factor |
| `--terminal-only` | Print to terminal only |
| `--ts-points N` | Time series points per chart (0=auto) |

**Required Input Directory Structure:**

```
test_dir/
├── runner_config.json              # DOE definition (from KooChainRun)
│   {
│     "project_name": "Galaxy_S25_Drop",
│     "scenarios": [{"scenario_name": "fibonacci_200"}],
│     "scenario": {
│       "doe_angles": {
│         "0": {"step_1": {"angle_name": "F_top", "roll": 0, "pitch": 0}},
│         "1": {"step_1": {"angle_name": "E_left_top", "roll": 45, "pitch": 0}},
│         ...
│       }
│     }
│   }
│
├── output/                         # Per-angle simulation results
│   ├── F_top/
│   │   ├── DropSet.json            # Angle definition for this run
│   │   │   {
│   │   │     "initial_conditions": {
│   │   │       "orientation_euler_deg": {"roll": 0, "pitch": 0, "yaw": 0}
│   │   │     },
│   │   │     "model": {"parts": {"1": "HOUSING", "2": "PCB"}}
│   │   │   }
│   │   └── d3plot, d3plot01, ...   # LS-DYNA binary results
│   ├── E_left_top/
│   │   ├── DropSet.json
│   │   └── d3plot, ...
│   └── P_fib_001/
│       ├── DropSet.json
│       └── d3plot, ...
│
└── analysis_results/               # Generated by unified_analyzer --recursive
    ├── F_top/
    │   ├── analysis_result.json
    │   ├── stress/part_1_von_mises.csv
    │   ├── strain/part_1_eff_plastic_strain.csv
    │   └── motion/part_1_motion.csv
    ├── E_left_top/
    │   └── ...
    └── P_fib_001/
        └── ...
```

**Output:**

```
test_dir/
├── sphere_report.html              # Self-contained HTML report
└── sphere_report.json              # JSON data for koo_viewer
```

### 4.4 koo_viewer (C++ GUI)

Interactive desktop viewer. Requires OpenGL 3.3 and a display (X11 or Wayland).

```bash
# Auto-detect mode from path contents
koo_viewer /path/to/something

# Explicit modes
koo_viewer deep   /path/to/report_output_dir     # Single sim report
koo_viewer sphere /path/to/test_dir_or_json       # Sphere report
koo_viewer 3d     /path/to/d3plot                 # Raw 3D viewer

# No args → restores last session (saved automatically)
koo_viewer
```

**Mode Auto-Detection:**

| Path Contains | Detected Mode |
|---------------|---------------|
| `report.json` or `*.json` | sphere |
| `analysis_result.json` or `result.json` | deep |
| File named `*d3plot*` | 3d |
| Other | deep (fallback) |

**Deep Mode Tabs (11):** Overview, Stress, Tensor, Motion, Energy (pie), Quality, Renders, Deep Dive, Contact, SysInfo, 3D

**Sphere Mode Tabs (12):** Mollweide, 3D Globe, A/B Delta, Angle Table, Part Risk, Heatmap, Directional, Failure, Statistics, Findings, Selected Compare, Angle Detail

**Keyboard Shortcuts:**
- `?` — Help overlay
- `Ctrl+E` — Export HTML report (sphere mode)
- `Ctrl+S` — Screenshot
- `F11` — Fullscreen toggle
- Double-click on Mollweide → Jump to Angle Detail 3D tab

---

## 5. Complete Pipeline Examples

### 5.1 Pipeline A: Single Simulation → Deep Report

```bash
# Step 1: Run LS-DYNA (produces d3plot files)
# (done externally, e.g., via Slurm)

# Step 2: One command does everything
koo_deep_report /data/sim_001/d3plot \
    --output /data/sim_001/report \
    --yield-stress 250 \
    --section-view \
    --ua-threads 4

# Step 3: View results
koo_viewer deep /data/sim_001/report
# or open /data/sim_001/report/deep_report.html in browser
```

**What happens internally in Step 2:**

```
koo_deep_report receives /data/sim_001/d3plot
  → Finds unified_analyzer binary (PATH or --install-dir)
  → Generates YAML config (which parts, what analysis)
  → Calls: unified_analyzer --config /tmp/tmpXXXX.yaml
    → unified_analyzer reads d3plot binary files
    → Writes: analysis_result.json, stress/*.csv, strain/*.csv, motion/*.csv
  → Parses glstat file (if exists) for energy data
  → Parses binout file (if exists) for contact data
  → Generates deep_report.html from all data
```

### 5.2 Pipeline B: Multi-Angle DOE → Sphere Report

```bash
# Step 1: KooChainRun generates DOE angles and submits LS-DYNA jobs
# (separate tool, produces test_dir/output/*/d3plot + DropSet.json)

# Step 2: Batch post-processing with unified_analyzer
unified_analyzer \
    --recursive /data/drop_test/output \
    --config analysis.yaml \
    --output /data/drop_test/analysis_results \
    --skip-existing \
    --threads 4

# Step 3: Generate sphere report
koo_sphere_report \
    --test-dir /data/drop_test \
    --format html json \
    --json /data/drop_test/sphere_report.json \
    --yield-stress 250

# Step 4: View results
koo_viewer sphere /data/drop_test
# or open sphere_report.html in browser
```

### 5.3 Pipeline C: Re-view Existing Results (No d3plot Needed)

```bash
# From existing JSON (no d3plot, no unified_analyzer needed)
koo_sphere_report --from-json /data/sphere_report.json --format html

# View in GUI (reads JSON only)
koo_viewer sphere /data/sphere_report.json
koo_viewer deep /data/report_output/
```

### 5.4 Pipeline D: Deep Report for a Specific Angle (from Sphere Run)

```bash
# After sphere pipeline, you can deep-dive into any specific angle:
koo_deep_report /data/drop_test/output/F_top/d3plot \
    --output /data/drop_test/output/F_top/deep_report \
    --yield-stress 250

# unified_analyzer was already run (analysis_results exists),
# but koo_deep_report will re-run it to the specific output dir.
# To reuse existing analysis:
koo_viewer deep /data/drop_test/analysis_results/F_top
```

---

## 6. Apptainer Container Setup

### 6.1 Definition File (Headless — Analysis Only)

```singularity
Bootstrap: docker
From: ubuntu:22.04

%labels
    Author KooD3plotReader
    Version 2.3.0
    Description LS-DYNA d3plot post-processing toolchain (headless)

%post
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake g++ git \
        libomp-dev python3 python3-pip python3-venv \
        ffmpeg libpng-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

    # Clone and build
    cd /opt
    git clone --depth 1 --branch v2.3.0 \
        https://github.com/squall321/KooD3plotReader.git
    cd KooD3plotReader

    # Build C++ (headless: no viewer, no GUI)
    cmake -B build -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/kood3plot \
        -DKOOD3PLOT_BUILD_VIEWER=OFF \
        -DKOOD3PLOT_BUILD_V4_RENDER=ON \
        -DKOOD3PLOT_BUILD_SECTION_RENDER=ON \
        -DKOOD3PLOT_ENABLE_OPENMP=ON \
        -DKOOD3PLOT_BUILD_TESTS=OFF \
        -DKOOD3PLOT_BUILD_CAPI=OFF \
        -DKOOD3PLOT_BUILD_HDF5=OFF
    cmake --build build -j$(nproc) --target unified_analyzer

    # Install binary
    mkdir -p /opt/kood3plot/bin
    cp build/examples/unified_analyzer /opt/kood3plot/bin/
    chmod +x /opt/kood3plot/bin/unified_analyzer

    # Install Python packages
    pip install --break-system-packages rich
    pip install --break-system-packages -e python/koo_deep_report/
    pip install --break-system-packages -e python/koo_sphere_report/

    # Clean build artifacts to reduce image size
    rm -rf build /opt/KooD3plotReader/.git

%environment
    export PATH=/opt/kood3plot/bin:/opt/KooD3plotReader/python/koo_deep_report:$PATH
    export PYTHONPATH=/opt/KooD3plotReader/python/koo_deep_report:/opt/KooD3plotReader/python/koo_sphere_report:$PYTHONPATH
    export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-4}

%runscript
    exec "$@"

%test
    /opt/kood3plot/bin/unified_analyzer --help
    python3 -m koo_deep_report --help
    python3 -m koo_sphere_report --help
```

### 6.2 Definition File (Full — With GUI Viewer)

```singularity
Bootstrap: docker
From: ubuntu:22.04

%labels
    Author KooD3plotReader
    Version 2.3.0
    Description LS-DYNA d3plot post-processing toolchain (full, with GUI)

%post
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake g++ git \
        libomp-dev python3 python3-pip python3-venv \
        ffmpeg libpng-dev ca-certificates \
        libgl-dev libx11-dev libxrandr-dev libxinerama-dev \
        libxcursor-dev libxi-dev libxext-dev \
        libwayland-dev libxkbcommon-dev \
    && rm -rf /var/lib/apt/lists/*

    cd /opt
    git clone --depth 1 --branch v2.3.0 \
        https://github.com/squall321/KooD3plotReader.git
    cd KooD3plotReader

    cmake -B build -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/kood3plot \
        -DKOOD3PLOT_BUILD_VIEWER=ON \
        -DKOOD3PLOT_BUILD_V4_RENDER=ON \
        -DKOOD3PLOT_BUILD_SECTION_RENDER=ON \
        -DKOOD3PLOT_ENABLE_OPENMP=ON \
        -DKOOD3PLOT_BUILD_TESTS=OFF \
        -DKOOD3PLOT_BUILD_CAPI=OFF \
        -DKOOD3PLOT_BUILD_HDF5=OFF
    cmake --build build -j$(nproc) --target unified_analyzer koo_viewer

    mkdir -p /opt/kood3plot/bin
    cp build/examples/unified_analyzer /opt/kood3plot/bin/
    cp build/viewer/koo_viewer /opt/kood3plot/bin/
    chmod +x /opt/kood3plot/bin/*

    pip install --break-system-packages rich
    pip install --break-system-packages -e python/koo_deep_report/
    pip install --break-system-packages -e python/koo_sphere_report/

    rm -rf build /opt/KooD3plotReader/.git

%environment
    export PATH=/opt/kood3plot/bin:$PATH
    export PYTHONPATH=/opt/KooD3plotReader/python/koo_deep_report:/opt/KooD3plotReader/python/koo_sphere_report:$PYTHONPATH
    export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-4}

%runscript
    exec "$@"
```

### 6.3 Build and Run Apptainer

```bash
# Build container image
apptainer build kood3plot_v2.3.0.sif kood3plot_headless.def

# Run unified_analyzer
apptainer exec kood3plot_v2.3.0.sif \
    unified_analyzer --config /data/analysis.yaml --threads 4

# Run koo_deep_report
apptainer exec kood3plot_v2.3.0.sif \
    koo_deep_report /data/sim/d3plot --output /data/sim/report

# Run koo_sphere_report
apptainer exec kood3plot_v2.3.0.sif \
    koo_sphere_report --test-dir /data/drop_test --format html json

# Run koo_viewer (needs --nv for GPU, bind X11 socket)
apptainer exec --nv --bind /tmp/.X11-unix kood3plot_full.sif \
    koo_viewer sphere /data/sphere_report.json

# Bind data directories
apptainer exec --bind /data:/data kood3plot_v2.3.0.sif \
    koo_deep_report /data/sim/d3plot
```

### 6.4 Slurm Integration

```bash
#!/bin/bash
#SBATCH --job-name=kood3plot_analysis
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=01:00:00

SIF=/opt/containers/kood3plot_v2.3.0.sif

# Single analysis
apptainer exec --bind /data ${SIF} \
    koo_deep_report /data/sim_${SLURM_ARRAY_TASK_ID}/d3plot \
    --output /data/results/${SLURM_ARRAY_TASK_ID} \
    --ua-threads ${SLURM_CPUS_PER_TASK}

# Batch recursive analysis
apptainer exec --bind /data ${SIF} \
    unified_analyzer \
    --recursive /data/drop_test/output \
    --config /data/analysis.yaml \
    --output /data/drop_test/analysis_results \
    --skip-existing \
    --threads ${SLURM_CPUS_PER_TASK}
```

---

## 7. Memory and Performance Guidelines

| Data Size | Recommended | Flag |
|-----------|-------------|------|
| < 100 states, < 1M elements | 4 threads, 4 GB RAM | `--ua-threads 4` |
| 100-500 states, 1-5M elements | 4 threads, 8 GB RAM | `--ua-threads 4` |
| 500+ states, 5M+ elements | 8 threads, 16+ GB RAM | `--ua-threads 8` |
| Sphere DOE (200+ angles) | 4 threads per job, batch | `--threads 4 --skip-existing` |

**koo_viewer** memory budget: `loadStatesBudgeted()` defaults to 2 GB for state data. Automatically computes stride to skip states if needed.

---

## 8. Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `unified_analyzer not found` | Not in PATH | Use `--install-dir` or add to PATH |
| `No analysis_results in test_dir` | unified_analyzer not run yet | Run `unified_analyzer --recursive` first |
| `Failed to open d3plot` | File missing or wrong path | Check path; d3plot files may be multi-part (d3plot, d3plot01, d3plot02...) — only pass base `d3plot` |
| koo_viewer black screen | No OpenGL 3.3 support | Need GPU or Mesa with GL 3.3+ |
| Section view blank | libpng missing at build | Rebuild with `KOOD3PLOT_BUILD_SECTION_RENDER=ON` and `libpng-dev` installed |
| HTML report missing renders | LSPrePost not found | Install LSPrePost or use `--no-render` |
| OOM on large models | Too many states in memory | Use `--ua-threads 2` to reduce parallel memory |

---

## 9. Codebase Stats

| Component | Files | Lines |
|-----------|-------|-------|
| Core C++ library (`src/` + `include/`) | 78 | 35,413 |
| Viewer (`viewer/src/`) | 52 | 9,291 |
| Python packages | 45+ | 12,768 |
| Examples | 20+ | — |
| Tests | 5 | — |
| **Total** | **200+** | **~57,000** |

## 10. Release History

| Tag | Highlights |
|-----|------------|
| v1.0.0 | Initial d3plot reader |
| v1.1.0 | Parallel read, OpenMP |
| v1.2.0 | Surface extractor, analysis engine |
| v1.3.0 | LSPrePost render, section view |
| v2.0.0 | KooViewer native desktop app |
| v2.1.0 | UX roadmap: A/B compare, radar, session restore (8 features) |
| v2.2.0 | Angle Detail 3D tab, memory-budgeted loading |
| v2.3.0 | Mollweide double-click, Top5 markers, A/B HTML export |
