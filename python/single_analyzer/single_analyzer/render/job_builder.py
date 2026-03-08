"""Build render_jobs for unified_analyzer based on analysis config."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RenderConfig:
    enabled: bool = True
    lsprepost_path: str = "auto"
    per_part_render: bool = False
    section_axes: list[str] = field(default_factory=lambda: ["x", "y", "z"])  # 단면 애니메이션 축
    fringe: str = "von_mises"
    format: str = "mp4"
    fps: int = 30
    resolution: list[int] = field(default_factory=lambda: [1920, 1080])
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
    # parts: [pid] → C++이 해당 파트 bbox 중심으로 단면 위치 자동 계산
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
