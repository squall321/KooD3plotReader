"""Run unified_analyzer and parse its JSON/CSV outputs."""
from __future__ import annotations
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from ..report.models import D3plotResult, ElementQualityData, ElementTensorHistory, MotionData, PartTimeSeries

if TYPE_CHECKING:
    from ..render.job_builder import RenderConfig, SectionViewRenderConfig


# unified_analyzer 바이너리 탐색: install_dir → 패키지 상대 경로 → PATH
def find_unified_analyzer(install_dir: Path | None = None) -> Path | None:
    import shutil
    import platform

    exe = "unified_analyzer.exe" if platform.system() == "Windows" else "unified_analyzer"

    # 0) install_dir 지정 시 최우선 탐색
    if install_dir is not None:
        for rel in [Path("bin") / exe, Path(exe)]:
            cand = (install_dir / rel).resolve()
            if cand.exists():
                return cand

    # 1) PyInstaller frozen exe: same directory as the executable
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).resolve().parent
        cand = exe_dir / exe
        if cand.exists():
            return cand
        # Also check parent/bin/ in case exe is in a subdirectory
        cand = exe_dir.parent / "bin" / exe
        if cand.exists():
            return cand

    # 2) 패키지와 함께 배포된 bin/ 디렉토리
    pkg_dir = Path(__file__).resolve().parent.parent.parent.parent  # koo_deep_report/ root
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
    install_dir: Path | None = None,
    section_view_config: "SectionViewRenderConfig | None" = None,
) -> D3plotResult:
    """
    1. analysis_jobs + render_jobs 통합 YAML 생성
    2. unified_analyzer subprocess 실행
    3. analysis_result.json + motion CSVs 파싱
    4. renders/ 폴더 스캔
    5. per_part_render이고 part_ids 미지정 시: 분석 결과에서 part IDs 추출 후 2nd render pass
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    # Clean existing renders to avoid stale files from previous runs
    renders_dir = output_dir / "renders"
    if renders_dir.exists():
        import shutil
        shutil.rmtree(renders_dir)
    ua = find_unified_analyzer(install_dir)
    if ua is None:
        raise RuntimeError("unified_analyzer not found. Build it first: cd build && make -j4 unified_analyzer")

    import copy
    from ..render.job_builder import RenderConfig as RC, SectionViewRenderConfig as SVC

    # Determine if we need a 2nd pass for per-part rendering
    sv_needs_second_pass = (
        section_view_config is not None
        and section_view_config.enabled
        and section_view_config.per_part_render
        and part_ids is None
    )
    lsp_needs_second_pass = (
        not (section_view_config and section_view_config.enabled)
        and render_config is not None
        and isinstance(render_config, RC)
        and render_config.enabled
        and render_config.per_part_render
        and part_ids is None
    )
    needs_second_pass = sv_needs_second_pass or lsp_needs_second_pass

    # First pass: analysis + overview renders (no per-part IDs yet)
    sv_first = section_view_config
    rc_first = render_config
    if sv_needs_second_pass:
        sv_first = copy.copy(section_view_config)
        sv_first.per_part_render = False  # skip per-part for 1st pass
    if lsp_needs_second_pass:
        rc_first = copy.copy(render_config)
        rc_first.per_part_render = False

    yaml_content = _build_yaml(d3plot_path, output_dir, rc_first, part_ids, threads, render_threads, verbose, element_quality=element_quality, install_dir=install_dir, section_view_config=sv_first)
    _run_ua(ua, yaml_content, verbose)

    result = _parse_outputs(output_dir)

    # Second pass: per-part renders using part IDs from analysis results
    if needs_second_pass:
        extracted_ids = _extract_part_ids(result)
        if extracted_ids:
            if sv_needs_second_pass:
                sv_per_part = copy.copy(section_view_config)
                yaml2 = _build_yaml(
                    d3plot_path, output_dir, None,
                    extracted_ids, threads, render_threads, verbose,
                    render_only=True,
                    install_dir=install_dir,
                    section_view_config=sv_per_part,
                )
            else:
                rc_per_part = copy.copy(render_config)
                yaml2 = _build_yaml(
                    d3plot_path, output_dir, rc_per_part,
                    extracted_ids, threads, render_threads, verbose,
                    render_only=True,
                    install_dir=install_dir,
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
    # Keep a debug copy
    debug_yaml = Path(tempfile.gettempdir()) / "last_ua_config.yaml"
    try:
        debug_yaml.write_text(yaml_content, encoding="utf-8")
    except OSError:
        pass  # best-effort debug copy
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
    install_dir: Path | None = None,
    section_view_config: "SectionViewRenderConfig | None" = None,
) -> str:
    parts_list = part_ids if part_ids else []

    lsprepost = _resolve_lsprepost(render_config, install_dir)
    sv_threads = 2
    if section_view_config and hasattr(section_view_config, 'sv_threads'):
        sv_threads = section_view_config.sv_threads
    perf_lines = [
        "performance:",
        f"  threads: {threads}",
        f"  render_threads: {render_threads}",
        f"  sv_threads: {sv_threads}",
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

    # render_jobs (LSPrePost) — skip when section_view_config is active
    if render_config and render_config.enabled and not (section_view_config and section_view_config.enabled):
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

    # section_views (software-rasterized, VTK-free) — replaces LSPrePost section renders
    if section_view_config and section_view_config.enabled:
        from ..render.job_builder import build_section_view_yaml_entries
        sv_entries = build_section_view_yaml_entries(str(output_dir), section_view_config, part_ids)
        if sv_entries:
            lines.append("section_views:")
            for name, yaml_block in sv_entries:
                lines.append(f'  - name: "{name}"')
                for bl in yaml_block.splitlines():
                    if bl.strip():
                        lines.append(f"    {bl}")

    return "\n".join(lines) + "\n"


def _resolve_lsprepost(render_config: "RenderConfig | None", install_dir: Path | None = None) -> str | None:
    """Return absolute lsprepost path, or None if render disabled / not found."""
    if render_config is None or not render_config.enabled:
        return None
    if render_config.lsprepost_path and render_config.lsprepost_path != "auto":
        return render_config.lsprepost_path

    import platform
    import shutil

    exe_name = "lsprepost.exe" if platform.system() == "Windows" else "lsprepost"

    # 0) install_dir 지정 시 최우선 탐색
    if install_dir is not None:
        for rel in [Path("lsprepost") / exe_name, Path("bin") / exe_name]:
            p = (install_dir / rel).resolve()
            if p.exists():
                return str(p)

    # 플랫폼별 기본 탐색 경로
    if platform.system() == "Windows":
        candidates = [
            Path(r"C:\Program Files\LSTC\LS-PrePost\lsprepost.exe"),
            Path(r"C:\LSTC\lsprepost\lsprepost.exe"),
            Path(r"C:\lsprepost\lsprepost.exe"),
        ]
    else:
        candidates = [
            Path("/usr/local/lsprepost/lsprepost"),
        ]

    # 패키지 기준 상대 경로 (배포 패키지 내 포함 시)
    pkg_root = Path(__file__).resolve().parent.parent.parent.parent  # python/
    for rel in [
        Path("lsprepost") / exe_name,                          # python/lsprepost/
        Path("..") / "installed" / "lsprepost" / exe_name,     # installed/lsprepost/ (dev build)
        Path("..") / "lsprepost" / exe_name,                   # 프로젝트루트/lsprepost/
        Path("installed") / "lsprepost" / exe_name,            # python/installed/
    ]:
        p = (pkg_root / rel).resolve()
        if p.exists():
            candidates.insert(0, p)
            break

    for p in candidates:
        if p.exists():
            return str(p)

    found = shutil.which("lsprepost")
    return found or None


def _parse_outputs(output_dir: Path) -> D3plotResult:
    """Parse analysis_result.json and motion CSVs."""
    json_path = output_dir / "analysis_result.json"
    if not json_path.exists():
        raise RuntimeError(f"analysis_result.json not found in {output_dir}")

    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)

    metadata = raw.get("metadata", {})
    stress = [_parse_series(s) for s in raw.get("stress_history", [])]
    strain = [_parse_series(s) for s in raw.get("strain_history", [])]
    max_principal = [_parse_series(s) for s in raw.get("max_principal_history", [])]
    min_principal = [_parse_series(s) for s in raw.get("min_principal_history", [])]
    max_principal_strain = [_parse_series(s) for s in raw.get("max_principal_strain_history", [])]
    min_principal_strain = [_parse_series(s) for s in raw.get("min_principal_strain_history", [])]
    accel = [_parse_series(s) for s in raw.get("acceleration_history", [])]

    # motion CSVs: motion/part_<id>_motion.csv (parallel loading)
    motion_dir = output_dir / "motion"
    motion: dict[int, MotionData] = {}
    if motion_dir.exists():
        csv_paths = sorted(motion_dir.glob("part_*_motion.csv"))
        if len(csv_paths) > 8:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(8, len(csv_paths))) as pool:
                results = pool.map(_parse_motion_csv, csv_paths)
            for md in results:
                if md is not None:
                    motion[md.part_id] = md
        else:
            for csv_path in csv_paths:
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

    # peak_element_tensors
    tensor_list: list[ElementTensorHistory] = []
    for t in raw.get("peak_element_tensors", []):
        tensor_list.append(ElementTensorHistory(
            element_id=t.get("element_id", 0),
            part_id=t.get("part_id", 0),
            reason=t.get("reason", ""),
            peak_value=t.get("peak_value", 0.0),
            peak_time=t.get("peak_time", 0.0),
            time=t.get("time", []),
            sxx=t.get("sxx", []),
            syy=t.get("syy", []),
            szz=t.get("szz", []),
            sxy=t.get("sxy", []),
            syz=t.get("syz", []),
            szx=t.get("szx", []),
        ))

    # renders/ — exclude intermediate frame_NNNN.png files from software renderer
    render_files: list[Path] = []
    renders_dir = output_dir / "renders"
    if renders_dir.exists():
        render_files.extend(sorted(renders_dir.rglob("*.mp4")))
        render_files.extend(sorted(renders_dir.rglob("*.gif")))
        for p in sorted(renders_dir.rglob("*.png")):
            if not p.name.startswith("frame_"):
                render_files.append(p)

    return D3plotResult(
        metadata=metadata,
        stress=stress,
        strain=strain,
        acceleration=accel,
        motion=motion,
        max_principal=max_principal,
        min_principal=min_principal,
        max_principal_strain=max_principal_strain,
        min_principal_strain=min_principal_strain,
        peak_element_tensors=tensor_list,
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
        with open(csv_path, newline="", encoding="utf-8") as f:
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
