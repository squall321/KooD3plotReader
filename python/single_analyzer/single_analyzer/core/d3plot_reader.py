"""Run unified_analyzer and parse its JSON/CSV outputs."""
from __future__ import annotations
import csv
import json
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from ..report.models import D3plotResult, ElementQualityData, MotionData, PartTimeSeries

if TYPE_CHECKING:
    from ..render.job_builder import RenderConfig


# unified_analyzer 바이너리 탐색: 패키지 위치 기준 상대 경로 → PATH
def find_unified_analyzer() -> Path | None:
    import shutil
    import platform

    exe = "unified_analyzer.exe" if platform.system() == "Windows" else "unified_analyzer"

    # 1) 패키지와 함께 배포된 bin/ 디렉토리
    pkg_dir = Path(__file__).resolve().parent.parent.parent.parent  # single_analyzer/ root
    for rel in [
        Path("bin") / exe,                              # 배포 패키지: bin/unified_analyzer
        Path("..") / "bin" / exe,                       # 상위 bin/
        Path("..") / "build" / "examples" / exe,        # 개발 빌드
    ]:
        cand = (pkg_dir / rel).resolve()
        if cand.exists():
            return cand

    # 2) PATH에서 탐색
    found = shutil.which("unified_analyzer")
    return Path(found) if found else None


def run_analysis(
    d3plot_path: Path,
    output_dir: Path,
    render_config: "RenderConfig | None" = None,
    part_ids: list[int] | None = None,
    threads: int = 0,
    render_threads: int = 1,
    verbose: bool = False,
    element_quality: bool = False,
) -> D3plotResult:
    """
    1. analysis_jobs + render_jobs 통합 YAML 생성
    2. unified_analyzer subprocess 실행
    3. analysis_result.json + motion CSVs 파싱
    4. renders/ 폴더 스캔
    5. per_part_render이고 part_ids 미지정 시: 분석 결과에서 part IDs 추출 후 2nd render pass
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    ua = find_unified_analyzer()
    if ua is None:
        raise RuntimeError("unified_analyzer not found. Build it first: cd build && make -j4 unified_analyzer")

    # Determine if we need a 2nd render pass for per-part rendering
    from ..render.job_builder import RenderConfig as RC
    needs_second_pass = (
        render_config is not None
        and isinstance(render_config, RC)
        and render_config.enabled
        and render_config.per_part_render
        and part_ids is None
    )

    import copy

    # First pass: analysis + overview renders (no per-part IDs yet)
    rc_first = render_config
    if needs_second_pass:
        rc_first = copy.copy(render_config)
        rc_first.per_part_render = False  # skip per-part for 1st pass

    yaml_content = _build_yaml(d3plot_path, output_dir, rc_first, part_ids, threads, render_threads, verbose, element_quality=element_quality)
    _run_ua(ua, yaml_content, verbose)

    result = _parse_outputs(output_dir)

    # Second pass: per-part renders using part IDs from analysis results
    if needs_second_pass:
        extracted_ids = _extract_part_ids(result)
        if extracted_ids:
            rc_per_part = copy.copy(render_config)
            rc_per_part.section_z_center = False  # overview already done in 1st pass
            rc_per_part.final_snapshot = False
            yaml2 = _build_yaml(
                d3plot_path, output_dir, rc_per_part,
                extracted_ids, threads, render_threads, verbose,
                render_only=True,
            )
            try:
                _run_ua(ua, yaml2, verbose)
            except RuntimeError:
                pass  # best-effort; analysis already done
            # Refresh render_files list
            renders_dir = output_dir / "renders"
            render_files: list[Path] = []
            if renders_dir.exists():
                for ext in ("*.mp4", "*.png", "*.gif"):
                    render_files.extend(sorted(renders_dir.rglob(ext)))
            result.render_files = render_files

    return result


def _run_ua(ua: Path, yaml_content: str, verbose: bool) -> None:
    """Write YAML to temp file, run unified_analyzer, clean up."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, prefix="sa_") as f:
        f.write(yaml_content)
        yaml_path = Path(f.name)
    try:
        proc = subprocess.run(
            [str(ua), "--config", str(yaml_path)],
            capture_output=not verbose,
            text=True,
        )
        if proc.returncode != 0:
            stderr = getattr(proc, "stderr", "") or ""
            raise RuntimeError(f"unified_analyzer failed (rc={proc.returncode}):\n{stderr[:2000]}")
    finally:
        yaml_path.unlink(missing_ok=True)


def _extract_part_ids(result: "D3plotResult") -> list[int]:
    """Collect unique part IDs from analysis results."""
    ids: set[int] = set()
    for s in result.stress:
        ids.add(s.part_id)
    for s in result.strain:
        ids.add(s.part_id)
    ids.update(result.motion.keys())
    return sorted(ids)


def _build_yaml(
    d3plot_path: Path,
    output_dir: Path,
    render_config: "RenderConfig | None",
    part_ids: list[int] | None,
    threads: int,
    render_threads: int = 1,
    verbose: bool = False,
    render_only: bool = False,
    element_quality: bool = False,
) -> str:
    parts_list = part_ids if part_ids else []

    lsprepost = _resolve_lsprepost(render_config)
    perf_lines = [
        "performance:",
        f"  threads: {threads}",
        f"  render_threads: {render_threads}",
        f"  verbose: {'true' if verbose else 'false'}",
    ]
    if lsprepost:
        perf_lines.append(f'  lsprepost_path: "{lsprepost}"')

    output_flags = ["  json: true", "  csv: true"] if not render_only else []

    lines = [
        'version: "2.0"',
        "input:",
        f'  d3plot: "{d3plot_path}"',
        "output:",
        f'  directory: "{output_dir}"',
    ] + output_flags + perf_lines

    if not render_only:
        def parts_str(ids: list[int]) -> str:
            return str(ids) if ids else "[]"

        lines += [
            "analysis_jobs:",
            "  - name: All Parts Stress",
            "    type: von_mises",
            f"    parts: {parts_str(parts_list)}",
            '    output_prefix: "stress/all"',
            "  - name: All Parts Strain",
            "    type: eff_plastic_strain",
            f"    parts: {parts_str(parts_list)}",
            '    output_prefix: "strain/all"',
            "  - name: All Parts Motion",
            "    type: part_motion",
            f"    parts: {parts_str(parts_list)}",
            "    quantities: [avg_displacement, avg_velocity, avg_acceleration, max_displacement]",
            '    output_prefix: "motion/all"',
        ]
        if element_quality:
            lines += [
                "  - name: Element Quality",
                "    type: element_quality",
                f"    parts: {parts_str(parts_list)}",
                '    output_prefix: "quality/all"',
            ]

    # render_jobs
    if render_config and render_config.enabled:
        from ..render.job_builder import build_render_jobs
        jobs = build_render_jobs(
            str(d3plot_path),
            str(output_dir),
            render_config,
            part_ids,
        )
        if jobs:
            lines.append("render_jobs:")
            for job in jobs:
                lines.append(_dict_to_yaml(job, indent=2))

    return "\n".join(lines) + "\n"


_LSPREPOST_CANDIDATES = [
    "/home/koopark/claude/KooD3plotReader/KooD3plotReader/installed/lsprepost/lsprepost",
    "/usr/local/lsprepost/lsprepost",
]


def _resolve_lsprepost(render_config: "RenderConfig | None") -> str | None:
    """Return absolute lsprepost path, or None if render disabled / not found."""
    if render_config is None or not render_config.enabled:
        return None
    if render_config.lsprepost_path and render_config.lsprepost_path != "auto":
        return render_config.lsprepost_path
    # auto-detect
    for p in _LSPREPOST_CANDIDATES:
        if Path(p).exists():
            return p
    import shutil
    found = shutil.which("lsprepost")
    return found or None


def _parse_outputs(output_dir: Path) -> D3plotResult:
    """Parse analysis_result.json and motion CSVs."""
    json_path = output_dir / "analysis_result.json"
    if not json_path.exists():
        raise RuntimeError(f"analysis_result.json not found in {output_dir}")

    with open(json_path) as f:
        raw = json.load(f)

    metadata = raw.get("metadata", {})
    stress = [_parse_series(s) for s in raw.get("stress_history", [])]
    strain = [_parse_series(s) for s in raw.get("strain_history", [])]
    accel = [_parse_series(s) for s in raw.get("acceleration_history", [])]

    # motion CSVs: motion/part_<id>_motion.csv
    motion_dir = output_dir / "motion"
    motion: dict[int, MotionData] = {}
    if motion_dir.exists():
        for csv_path in sorted(motion_dir.glob("part_*_motion.csv")):
            md = _parse_motion_csv(csv_path)
            if md is not None:
                motion[md.part_id] = md

    # part_name from stress for motion entries that don't have names
    name_map = {s.part_id: s.part_name for s in stress}
    for pid, md in motion.items():
        if not md.part_name and pid in name_map:
            md.part_name = name_map[pid]

    # element_quality from JSON
    eq_list: list[ElementQualityData] = []
    for eq in raw.get("element_quality", []):
        eq_list.append(ElementQualityData(
            part_id=eq.get("part_id", 0),
            part_name=eq.get("part_name", ""),
            element_type=eq.get("element_type", "shell"),
            num_elements=eq.get("num_elements", 0),
            peak_aspect_ratio=eq.get("peak_aspect_ratio", 0.0),
            min_jacobian=eq.get("min_jacobian", 1.0),
            peak_warpage=eq.get("peak_warpage", 0.0),
            peak_skewness=eq.get("peak_skewness", 0.0),
            min_volume_change=eq.get("min_volume_change", 1.0),
            max_volume_change=eq.get("max_volume_change", 1.0),
            max_negative_jacobian_count=eq.get("max_negative_jacobian_count", 0),
            data=eq.get("data", []),
        ))

    # renders/
    render_files: list[Path] = []
    renders_dir = output_dir / "renders"
    if renders_dir.exists():
        for ext in ("*.mp4", "*.png", "*.gif"):
            render_files.extend(sorted(renders_dir.rglob(ext)))

    return D3plotResult(
        metadata=metadata,
        stress=stress,
        strain=strain,
        acceleration=accel,
        motion=motion,
        element_quality=eq_list,
        render_files=render_files,
        output_dir=output_dir,
    )


def _parse_series(raw: dict) -> PartTimeSeries:
    # unified_analyzer inserts "...(omitted N entries)..." strings in data arrays
    # to truncate large outputs. Filter those out.
    data = [d for d in raw.get("data", []) if isinstance(d, dict)]
    return PartTimeSeries(
        part_id=raw.get("part_id", 0),
        part_name=raw.get("part_name", ""),
        quantity=raw.get("quantity", ""),
        unit=raw.get("unit", ""),
        global_max=raw.get("global_max", 0.0),
        global_min=raw.get("global_min", 0.0),
        time_of_max=raw.get("time_of_max", 0.0),
        data=data,
    )


def _parse_motion_csv(csv_path: Path) -> MotionData | None:
    """Parse part_N_motion.csv into MotionData."""
    # Extract part_id from filename: part_1_motion.csv → 1
    stem = csv_path.stem  # "part_1_motion"
    parts = stem.split("_")
    try:
        pid = int(parts[1])
    except (IndexError, ValueError):
        return None

    md = MotionData(part_id=pid)
    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                def fv(key: str) -> float:
                    try:
                        return float(row.get(key, 0) or 0)
                    except ValueError:
                        return 0.0

                md.t.append(fv("Time"))
                md.disp_x.append(fv("Avg_Disp_X"))
                md.disp_y.append(fv("Avg_Disp_Y"))
                md.disp_z.append(fv("Avg_Disp_Z"))
                md.disp_mag.append(fv("Avg_Disp_Mag"))
                md.vel_mag.append(fv("Avg_Vel_Mag"))
                md.acc_mag.append(fv("Avg_Acc_Mag"))
                md.max_disp_mag.append(fv("Max_Disp_Mag"))
                node_val = row.get("Max_Disp_Node_ID", "0") or "0"
                try:
                    md.max_disp_node.append(int(float(node_val)))
                except ValueError:
                    md.max_disp_node.append(0)
    except OSError:
        return None

    return md


def _dict_to_yaml(d: dict, indent: int = 0) -> str:
    """Simple dict-to-YAML serializer (no external dependency).

    For indent=2, generates:
      - name: "foo"    (dash at column 2, NOT column 0)
        key: val       (subsequent keys at column 4)
    The C++ parser treats indent==0 lines as root sections, so
    list items must have indent >= 1.
    """
    lines: list[str] = []
    prefix = " " * indent
    first = True
    for k, v in d.items():
        if first:
            kpfx = prefix + "- "    # e.g. "  - " for indent=2
            vpfx = prefix + "  "    # e.g. "    " for indent=2
            first = False
        else:
            kpfx = prefix + "  "
            vpfx = prefix + "  "
        if isinstance(v, dict):
            lines.append(f"{kpfx}{k}:")
            for sk, sv in v.items():
                lines.append(f"{vpfx}  {sk}: {_yaml_val(sv)}")
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            lines.append(f"{kpfx}{k}:")
            for item in v:
                sub = _dict_to_yaml(item, indent + 4)
                lines.append(sub)
        else:
            lines.append(f"{kpfx}{k}: {_yaml_val(v)}")
    return "\n".join(lines)


def _yaml_val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, list):
        return "[" + ", ".join(_yaml_val(x) for x in v) + "]"
    return str(v)
