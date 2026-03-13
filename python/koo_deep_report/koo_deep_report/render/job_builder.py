"""Build render_jobs for unified_analyzer based on analysis config."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SectionViewRenderConfig:
    """Configuration for software-rasterized section view rendering (VTK-free)."""
    enabled: bool = True
    axes: list[str] = field(default_factory=lambda: ["z"])       # x | y | z
    scalar_field: str = "von_mises"                              # von_mises | eps | displacement
    target_part_ids: list[int] = field(default_factory=list)     # [] = all parts as target
    target_patterns: list[str] = field(default_factory=list)     # e.g. ["*PKG*", "*CELL*"]
    fade_distance: float = 0.0   # 0 = flat categorical bg; >0 = semi-transparent bg by dist
    global_range: bool = True    # true = consistent red=max/blue=min across all states
    width: int = 1280
    height: int = 720
    fps: int = 24
    supersampling: int = 2
    png_frames: bool = False


def build_section_view_yaml_entries(
    output_dir: str,
    config: SectionViewRenderConfig,
) -> list[tuple[str, str]]:
    """Return list of (name, yaml_block) tuples for section_views: YAML entries.

    Each yaml_block is the body of one SectionViewJobSpec (no surrounding name/header).
    The output MP4 files land in renders/ (root level = "Overview" in the gallery).
    """
    if not config.enabled:
        return []

    renders_dir = str(Path(output_dir) / "renders")
    entries: list[tuple[str, str]] = []

    # Build target_parts block
    if config.target_part_ids:
        ids_str = "[" + ", ".join(str(i) for i in config.target_part_ids) + "]"
        target_block = f"target_parts:\n  ids: {ids_str}"
    elif config.target_patterns:
        pats = "[" + ", ".join(f'"{p}"' for p in config.target_patterns) + "]"
        target_block = f"target_parts:\n  patterns: {pats}"
    else:
        target_block = "target_parts:\n  ids: []"

    for axis in config.axes:
        name = f"section_view_{axis}"
        # Each axis needs its own subdirectory; renderer always writes "section_view.mp4"
        axis_dir = str(Path(renders_dir) / name)
        yaml_block = (
            f"plane:\n"
            f"  axis: {axis}\n"
            f"  point: [0.0, 0.0, 0.0]\n"
            f"auto_center: true\n"
            f"{target_block}\n"
            f"background_parts:\n"
            f'  patterns: ["*"]\n'
            f"field: {config.scalar_field}\n"
            f"colormap: rainbow\n"
            f"global_range: {'true' if config.global_range else 'false'}\n"
            f"scale_factor: 1.2\n"
            f"supersampling: {config.supersampling}\n"
            f"fade_distance: {config.fade_distance}\n"
            f"output:\n"
            f"  width: {config.width}\n"
            f"  height: {config.height}\n"
            f"  png_frames: {'true' if config.png_frames else 'false'}\n"
            f"  mp4: true\n"
            f"  fps: {config.fps}\n"
            f'  output_dir: "{axis_dir}"\n'
        )
        entries.append((name, yaml_block))

    return entries


@dataclass
class RenderConfig:
    enabled: bool = True
    lsprepost_path: str = "auto"
    per_part_render: bool = False
    section_axes: list[str] = field(default_factory=lambda: ["x", "y", "z"])  # 단면 애니메이션 축
    fringe: str = "von_mises"
    format: str = "mp4"
    fps: int = 30
    resolution: list[int] = field(default_factory=lambda: [2560, 1440])
    part_pattern: str = ""          # 빈 문자열 = 전체


def build_render_jobs(
    d3plot_path: str,
    output_dir: str,
    config: RenderConfig,
    part_ids: list[int] | None = None,
) -> list[dict]:
    """
    Returns a list of render_job dicts to embed in unified_analyzer YAML.

    Overview: X/Y/Z 단면 애니메이션 (각 축에 수직한 뷰 자동 선택)
    Per-part: 각 부품 bbox 중심을 통과하는 X/Y/Z 단면 애니메이션
    """
    if not config.enabled:
        return []

    jobs: list[dict] = []
    renders_dir = str(Path(output_dir) / "renders")
    out_base = {
        "format": config.format,
        "fps": config.fps,
        "resolution": config.resolution,
        "directory": renders_dir,
    }

    # 전체 모델 X/Y/Z 단면 애니메이션
    # view 키 없음 → C++이 axis 기반 자동 선택 (X→right, Y→front, Z→top)
    for axis in config.section_axes:
        job: dict = {
            "name": f"overview_{axis}",
            "type": "section_view",
            "fringe": config.fringe,
            "section": {"axis": axis, "position": "center"},
            "states": "all",
            "output": {**out_base, "filename": f"overview_{axis}"},
        }
        if config.part_pattern:
            job["part_pattern"] = config.part_pattern
        jobs.append(job)

    # 부품별 X/Y/Z 단면 (해당 부품 bbox 중심 통과)
    # splane allcut: 모든 축에서 drawcut 동작 (keep_allcut은 메모리 crash 유발)
    # genselect: 선택 파트=fringe 컬러, 나머지=mesh 뷰
    if config.per_part_render and part_ids:
        for pid in part_ids:
            part_dir = str(Path(output_dir) / "renders" / f"part_{pid}")
            for axis in config.section_axes:
                jobs.append({
                    "name": f"part_{pid}_{axis}",
                    "type": "section_view",
                    "fringe": config.fringe,
                    "parts": [pid],
                    "section": {"axis": axis, "position": "center"},
                    "states": "all",
                    "output": {
                        "format": config.format,
                        "fps": config.fps,
                        "resolution": config.resolution,
                        "directory": part_dir,
                        "filename": f"part_{pid}_{axis}",
                    },
                })

    return jobs
