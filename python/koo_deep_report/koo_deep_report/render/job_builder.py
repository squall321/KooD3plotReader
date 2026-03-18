"""Build render_jobs for unified_analyzer based on analysis config."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SectionViewRenderConfig:
    """Configuration for software-rasterized section view rendering (VTK-free)."""
    enabled: bool = True
    view_mode: str = "section"  # "section" (2D) or "section_3d" (3D half-model)
    axes: list[str] = field(default_factory=lambda: ["x", "y", "z"])  # x | y | z
    scalar_fields: list[str] = field(default_factory=lambda: ["von_mises", "strain"])  # 복수 필드
    scalar_field: str = ""       # 단일 필드 (하위 호환) — 설정 시 scalar_fields 무시
    target_part_ids: list[int] = field(default_factory=list)     # [] = all parts as target
    target_patterns: list[str] = field(default_factory=list)     # e.g. ["*PKG*", "*CELL*"]
    fade_distance: float = 0.0   # 0 = flat categorical bg; >0 = semi-transparent bg by dist
    global_range: bool = True    # true = consistent red=max/blue=min across all states
    per_part_render: bool = False  # True = also generate per-part section views
    sv_threads: int = 2           # Parallel section view renderers (default 2)
    width: int = 1280
    height: int = 720
    fps: int = 24
    supersampling: int = 2
    png_frames: bool = False

    @property
    def effective_fields(self) -> list[str]:
        """Return the list of fields to render."""
        if self.scalar_field:
            return [self.scalar_field]
        return self.scalar_fields


def _sv_yaml_block(
    axis: str,
    output_dir: str,
    config: SectionViewRenderConfig,
    target_ids: list[int] | None = None,
    field_name: str = "",
) -> str:
    """Build a single section_view YAML block body."""
    if target_ids is not None:
        ids_str = "[" + ", ".join(str(i) for i in target_ids) + "]"
        target_block = f"target_parts:\n  ids: {ids_str}"
    elif config.target_part_ids:
        ids_str = "[" + ", ".join(str(i) for i in config.target_part_ids) + "]"
        target_block = f"target_parts:\n  ids: {ids_str}"
    elif config.target_patterns:
        pats = "[" + ", ".join(f'"{p}"' for p in config.target_patterns) + "]"
        target_block = f"target_parts:\n  patterns: {pats}"
    else:
        target_block = "target_parts:\n  ids: []"

    actual_field = field_name or config.scalar_field or "von_mises"

    view_mode_line = f"view_mode: {config.view_mode}\n" if config.view_mode != "section" else ""

    return (
        f"{view_mode_line}"
        f"plane:\n"
        f"  axis: {axis}\n"
        f"  point: [0.0, 0.0, 0.0]\n"
        f"auto_center: true\n"
        f"{target_block}\n"
        f"background_parts:\n"
        f'  patterns: ["*"]\n'
        f"field: {actual_field}\n"
        f"colormap: rainbow\n"
        f"global_range: {'true' if config.global_range else 'false'}\n"
        f"scale_factor: 3.0\n"
        f"supersampling: {config.supersampling}\n"
        f"fade_distance: {config.fade_distance}\n"
        f"output:\n"
        f"  width: {config.width}\n"
        f"  height: {config.height}\n"
        f"  png_frames: {'true' if config.png_frames else 'false'}\n"
        f"  mp4: true\n"
        f"  fps: {config.fps}\n"
        f'  output_dir: "{output_dir}"\n'
    )


def build_section_view_yaml_entries(
    output_dir: str,
    config: SectionViewRenderConfig,
    part_ids: list[int] | None = None,
) -> list[tuple[str, str]]:
    """Return list of (name, yaml_block) tuples for section_views: YAML entries.

    Overview: one entry per (field, axis), all parts as fringe target.
    Per-part: one entry per (field, part, axis) when per_part_render=True and part_ids given.
    """
    if not config.enabled:
        return []

    renders_dir = str(Path(output_dir) / "renders")
    entries: list[tuple[str, str]] = []
    fields = config.effective_fields

    # Overview entries (all parts × all fields)
    for fld in fields:
        for axis in config.axes:
            # single field → no field suffix (backward compat)
            if len(fields) == 1:
                name = f"section_view_{axis}"
            else:
                name = f"section_view_{fld}_{axis}"
            axis_dir = str(Path(renders_dir) / name)
            entries.append((name, _sv_yaml_block(axis, axis_dir, config, field_name=fld)))

    # Per-part entries
    if config.per_part_render and part_ids:
        for fld in fields:
            for pid in part_ids:
                for axis in config.axes:
                    if len(fields) == 1:
                        name = f"section_view_part_{pid}_{axis}"
                    else:
                        name = f"section_view_{fld}_part_{pid}_{axis}"
                    part_dir = str(Path(renders_dir) / name)
                    entries.append((name, _sv_yaml_block(axis, part_dir, config,
                                                         target_ids=[pid], field_name=fld)))

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
