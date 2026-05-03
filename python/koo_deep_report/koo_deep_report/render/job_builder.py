"""Build render_jobs for unified_analyzer based on analysis config."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SectionViewRenderConfig:
    """Configuration for section view rendering.

    backend="lsprepost" (default): uses LSPrePost drawcut+projectview via Xvfb.
        Produces high-quality section views identical to interactive LSPrePost.
    backend="software": uses built-in software rasterizer (VTK-free, slower).

    For per-part rendering with TRUE fringe isolation (genselect) and iso clip
    views, set per_part_render=True. This routes through the C++ side's new
    `part_section_renders` block which calls `LSPrePostRenderer::renderAllPartSections`.
    """
    enabled: bool = True
    backend: str = "lsprepost"   # "lsprepost" (default) or "software"
    view_mode: str = "section"  # "section" (2D) or "section_3d" (3D half-model, software only)
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

    # ── per-part renderAllPartSections options (LSPrePost backend only) ──
    # Active only when per_part_render=True and backend="lsprepost".
    iso_clip_view: bool = True       # generate isometric+clipplane views per part
    section_position: float = 0.5    # 0..1 within part bbox
    section_margin: float = -0.3     # zin margin for section view (negative = zoom out)
    iso_clip_margin: float = -0.3    # zin margin for iso clip view (negative = zoom out; -0.3 ≈ 1.6x out)
    edge_width: int = 2              # edge/outline width 1-5
    crf: int = 23                    # H264 CRF for ffmpeg re-encode (18=high, 23=default)
    reverse_cut: bool = True         # flip cut side so interior faces camera
    # ── sliding section view ──
    sliding_view: bool = False           # master toggle for sliding videos
    sliding_section_style: bool = True   # generate section-style sliding (drawcut + projectview)
    sliding_iso_style: bool = True       # generate iso-style sliding (clipplane + isometric)
    sliding_steps: int = 20              # number of cut positions across part bbox
    sliding_near_to_far: bool = True     # bbox.max → bbox.min (camera-near to far)
    sliding_pad: float = 0.05            # padding fraction outside bbox
    sliding_freeze_time: bool = False    # Phase B: freeze sim time at peak_state
    sliding_peak_time: float = -1.0      # Phase B: explicit peak time (-1 = auto)

    @property
    def effective_fields(self) -> list[str]:
        """Return the list of fields to render."""
        if self.scalar_field:
            return [self.scalar_field]
        return self.scalar_fields


def _parse_signed_axis(s: str) -> tuple[str, int]:
    """Parse 'y' / '+y' / '-y' / 'Y' → ('y', +1 / -1)."""
    s = s.strip()
    sign = 1
    if s.startswith('+'):
        s = s[1:]
    elif s.startswith('-'):
        sign = -1
        s = s[1:]
    return (s.lower()[0] if s else 'z'), sign


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

    # Sliding support (SW backend reads these via SectionViewConfig)
    axis_letter, axis_sign = _parse_signed_axis(axis)
    sliding_block = ""
    if config.sliding_view:
        sliding_block = (
            f"sliding_view: true\n"
            f"sliding_steps: {config.sliding_steps}\n"
            f"sliding_pad: {config.sliding_pad}\n"
            f"sliding_axis_sign: {axis_sign}\n"
            f"sliding_peak_time: {config.sliding_peak_time}\n"
        )

    # In sliding mode the plane sweeps through every element along the slide
    # axis; rendering the full background ("*") flickers because non-target
    # element edges glance the cut plane differently at each step. Drawing
    # only the target part keeps the slice clean.
    background_patterns = "[]" if config.sliding_view else '["*"]'

    return (
        f"{view_mode_line}"
        f"plane:\n"
        f"  axis: {axis_letter}\n"
        f"  point: [0.0, 0.0, 0.0]\n"
        f"auto_center: true\n"
        f"{target_block}\n"
        f"background_parts:\n"
        f'  patterns: {background_patterns}\n'
        f"field: {actual_field}\n"
        f"colormap: rainbow\n"
        f"global_range: {'true' if config.global_range else 'false'}\n"
        f"scale_factor: 3.0\n"
        f"supersampling: {config.supersampling}\n"
        f"fade_distance: {config.fade_distance}\n"
        f"{sliding_block}"
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


_FRINGE_MAP = {
    "von_mises": "von_mises",
    "strain": "eff_plastic_strain",
    "eps": "eff_plastic_strain",
    "displacement": "displacement_mag",
    "pressure": "pressure",
    "max_shear": "max_shear",
}


def build_part_section_render_yaml_entries(
    output_dir: str,
    config: SectionViewRenderConfig,
    part_ids: list[int] | None = None,
) -> list[tuple[str, str]]:
    """Return list of (name, yaml_block) tuples for part_section_renders: entries.

    One entry per scalar_field (since the C++ struct holds one fringe_type
    per job). The C++ side then loops over part_ids × axes internally and
    renders per-part section + iso_clip views with genselect fringe isolation.

    output_dir: report root (renders/part_sections lives under it)
    """
    if not config.enabled:
        return []
    if config.backend != "lsprepost":
        # part_section_renders only supports lsprepost backend
        return []

    fields = config.effective_fields
    entries: list[tuple[str, str]] = []
    for fld in fields:
        # Map koo_deep_report field names to fringe types accepted by the C++ side.
        fringe = _FRINGE_MAP.get(fld, fld)
        # Per-field subdirectory keeps fields from clobbering each other.
        sub = f"renders/part_sections/{fld}"

        axes_list = "[" + ", ".join(config.axes) + "]"
        ids_list = "[]"
        if part_ids:
            ids_list = "[" + ", ".join(str(i) for i in part_ids) + "]"

        body = (
            f"fringe_type: {fringe}\n"
            f"axes: {axes_list}\n"
            f"part_ids: {ids_list}\n"
            f"section_view: true\n"
            f"iso_clip_view: {'true' if config.iso_clip_view else 'false'}\n"
            f"section_position: {config.section_position}\n"
            f"section_margin: {config.section_margin}\n"
            f"iso_clip_margin: {config.iso_clip_margin}\n"
            f"edge_width: {config.edge_width}\n"
            f"crf: {config.crf}\n"
            f"reverse_cut: {'true' if config.reverse_cut else 'false'}\n"
            f"sliding_view: {'true' if config.sliding_view else 'false'}\n"
            f"sliding_section_style: {'true' if config.sliding_section_style else 'false'}\n"
            f"sliding_iso_style: {'true' if config.sliding_iso_style else 'false'}\n"
            f"sliding_steps: {config.sliding_steps}\n"
            f"sliding_near_to_far: {'true' if config.sliding_near_to_far else 'false'}\n"
            f"sliding_pad: {config.sliding_pad}\n"
            f"sliding_freeze_time: {'true' if config.sliding_freeze_time else 'false'}\n"
            f"sliding_peak_time: {config.sliding_peak_time}\n"
            f"output:\n"
            f'  directory: "{sub}"\n'
            f"  resolution: [{config.width}, {config.height}]\n"
            f"  fps: {config.fps}\n"
        )
        name = f"Per-Part Sections ({fld})"
        entries.append((name, body))
    return entries


def build_lsprepost_section_jobs(
    output_dir: str,
    config: SectionViewRenderConfig,
    part_ids: list[int] | None = None,
) -> list[dict]:
    """Build render_jobs dicts for LSPrePost section view rendering.

    Same output folder structure as software renderer so HTML gallery
    picks up results unchanged.
    """
    if not config.enabled:
        return []

    renders_dir = str(Path(output_dir) / "renders")
    jobs: list[dict] = []
    fields = config.effective_fields
    resolution = [config.width, config.height]

    # Overview: all parts, per field × axis
    for fld in fields:
        fringe = _FRINGE_MAP.get(fld, fld)
        for axis in config.axes:
            if len(fields) == 1:
                name = f"section_view_{axis}"
            else:
                name = f"section_view_{fld}_{axis}"

            job: dict = {
                "name": name,
                "type": "section_view",
                "fringe": fringe,
                "section": {"axis": axis, "position": "center"},
                "states": "all",
                "output": {
                    "format": "mp4",
                    "fps": config.fps,
                    "resolution": resolution,
                    "directory": str(Path(renders_dir) / name),
                    "filename": "section_view",
                },
            }
            if config.target_part_ids:
                job["parts"] = config.target_part_ids
            elif config.target_patterns:
                job["part_pattern"] = config.target_patterns[0]
            jobs.append(job)

    # Per-part: each part × field × axis
    if config.per_part_render and part_ids:
        for fld in fields:
            fringe = _FRINGE_MAP.get(fld, fld)
            for pid in part_ids:
                for axis in config.axes:
                    if len(fields) == 1:
                        name = f"section_view_part_{pid}_{axis}"
                    else:
                        name = f"section_view_{fld}_part_{pid}_{axis}"

                    jobs.append({
                        "name": name,
                        "type": "section_view",
                        "fringe": fringe,
                        "parts": [pid],
                        "section": {"axis": axis, "position": "center"},
                        "states": "all",
                        "output": {
                            "format": "mp4",
                            "fps": config.fps,
                            "resolution": resolution,
                            "directory": str(Path(renders_dir) / name),
                            "filename": "section_view",
                        },
                    })

    return jobs


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
