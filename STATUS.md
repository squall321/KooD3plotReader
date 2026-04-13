# KooD3plotReader — Project Status

**Version**: v2.3.0 | **Date**: 2026-04-13 | **Branch**: main

## Architecture

```
KooD3plotReader/
├── include/kood3plot/       # Public C++ headers
├── src/                     # Core library source (35,413 lines, 78 files)
├── viewer/                  # KooViewer desktop app (9,291 lines, 52 files)
├── python/
│   ├── koo_deep_report/     # Single-sim analysis + HTML report
│   └── koo_sphere_report/   # All-angle sphere DOE report
├── examples/                # 20+ example programs
├── tests/                   # 5 unit test suites
└── .github/workflows/       # CI/CD (Linux + Windows)
```

## Build Targets

### C++ Libraries (CMake)

| Target | Type | Description |
|--------|------|-------------|
| `kood3plot` | Static lib | Core d3plot reader, mesh, state, analysis, surface extractor |
| `kood3plot_render` | Static lib | LSPrePost batch rendering (cfile generation) |
| `kood3plot_section_render` | Static lib | Software rasterizer section view (VTK-free) |
| `kood3plot_query` | Static lib | V3 query system (streaming, filtering) |
| `kood3plot_writer` | Static lib | D3plot write-back |
| `kood3plot_converter` | Static lib | VTK <-> d3plot, Radioss -> d3plot conversion |
| `kood3plot_hdf5` | Static lib | HDF5 quantized export (Blosc compression) |
| `kood3plot_cli` | Static lib | CLI utilities |

### C++ Executables

| Target | Description |
|--------|-------------|
| `koo_viewer` | Desktop GUI — 3 modes (deep / sphere / 3d) |
| `unified_analyzer` | CLI analysis engine — called by Python wrappers |

### Python Packages

| Package | Version | Install | Run |
|---------|---------|---------|-----|
| `koo_deep_report` | 1.1.0 | `pip install -e python/koo_deep_report/` | `koo_deep_report <d3plot>` |
| `koo_sphere_report` | 2.0.0 | `pip install -e python/koo_sphere_report/` | `koo_sphere_report --test-dir <dir>` |

## Build & Install

```bash
# Full build (all targets)
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j4

# Specific targets only
cmake --build build --target koo_viewer unified_analyzer -j4

# Python packages
pip install -e python/koo_deep_report/
pip install -e python/koo_sphere_report/
```

## KooViewer — 3 Modes

### deep — Single Simulation Report
```
koo_viewer deep <output_dir>
```
11 analysis tabs: Overview, Stress, Tensor, Motion, Energy (pie chart), Quality, Renders gallery, Deep Dive, Contact, SysInfo, 3D viewer (fringe + section view)

### sphere — All-Angle Sphere Report
```
koo_viewer sphere <test_dir_or_json>
```
12 analysis tabs: Mollweide (IDW contour, Top5 markers), 3D Globe, A/B Delta, Angle Table, Part Risk, Heatmap, Directional, Failure, Statistics, Findings, Selected Compare, Angle Detail (per-angle 3D)

### 3d — Direct Model Viewer
```
koo_viewer 3d <d3plot_path>
```
Von Mises fringe, deformation animation, section cut (X/Y/Z), play/pause

## Key Features (v2.0.0 ~ v2.3.0)

| Version | Features |
|---------|----------|
| v2.0.0 | Native desktop app (GLFW + ImGui + ImPlot + OpenGL 3.3), deep/sphere/3d modes, 3D fringe viewer |
| v2.1.0 | A/B compare, cross-tab highlight, category filter, help overlay, HTML export, energy pie, radar chart, session save/restore |
| v2.2.0 | Angle Detail tab (per-angle d3plot 3D with section cut), memory-budgeted state loading |
| v2.3.0 | Mollweide double-click -> Angle Detail jump, Top 5 worst markers, A/B comparison in HTML export |

## Pipeline: d3plot -> Report -> Viewer

```
d3plot ──> unified_analyzer (C++) ──> analysis_result.json
                                          │
           koo_deep_report (Python) ──────┤──> deep_report.html
                                          │
           koo_viewer deep ───────────────┘

DOE dir ──> koo_sphere_report (Python) ──> sphere_report.json
                                               │
              koo_viewer sphere ───────────────┘
```

## CI/CD

- **Trigger**: push to `main` or `v*` tag
- **Platforms**: Linux (ubuntu-22.04), Windows (windows-2022)
- **Release**: tag push -> GitHub Release with zip archives
- **Artifacts**: `unified_analyzer`, `koo_viewer`, `koo_deep_report` (PyInstaller exe), Python source packages

## Codebase Stats

| Component | Files | Lines |
|-----------|-------|-------|
| Core C++ library (`src/` + `include/`) | 78 | 35,413 |
| Viewer (`viewer/src/`) | 52 | 9,291 |
| Python packages | 45+ | 12,768 |
| Examples | 20+ | — |
| Tests | 5 | — |
| **Total** | **200+** | **~57,000** |

## Release History

| Tag | Date | Highlights |
|-----|------|------------|
| v1.0.0 | 2026-02 | Initial d3plot reader |
| v1.1.0 | — | Parallel read, OpenMP |
| v1.2.0 | — | Surface extractor, analysis engine |
| v1.3.0 | — | LSPrePost render, section view |
| v2.0.0 | 2026-03 | KooViewer native desktop app |
| v2.1.0 | 2026-03 | UX roadmap 8 features |
| v2.2.0 | 2026-04 | Angle Detail 3D tab |
| v2.3.0 | 2026-04 | Mollweide UX + A/B HTML export |
