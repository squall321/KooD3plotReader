"""koo_deep_report CLI entry point."""
from __future__ import annotations
import argparse
import io
import json
import os
import re
import sys
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows (prevents cp949 UnicodeEncodeError)
if sys.platform == "win32":
    for _stream_name in ("stdout", "stderr"):
        _stream = getattr(sys, _stream_name)
        if _stream and hasattr(_stream, "buffer"):
            setattr(sys, _stream_name,
                    io.TextIOWrapper(_stream.buffer, encoding="utf-8",
                                     errors="replace", line_buffering=True))

from .core.sim_detector import find_files
from .core.glstat_reader import parse_glstat
from .core.d3plot_reader import run_analysis
from .core.binout_reader import parse_binout
from .render.job_builder import RenderConfig, SectionViewRenderConfig
from .report.models import SingleResult, PartSummary
from .report.html_report import generate_html


_SUBCOMMANDS = {"batch", "compare", "gui"}


def main() -> None:
    # Detect subcommand manually to avoid argparse positional conflict
    argv = sys.argv[1:]
    command = argv[0] if argv and argv[0] in _SUBCOMMANDS else "single"

    # No arguments at all → launch GUI
    if not argv or command == "gui":
        try:
            from .gui.app import launch
            launch()
        except ImportError:
            print("ERROR: GUI를 사용할 수 없습니다 (tkinter 미설치).", file=sys.stderr)
            print("사용법: koo_deep_report <path> [options]", file=sys.stderr)
            print("도움말: koo_deep_report --help", file=sys.stderr)
            sys.exit(1)
        return

    if command == "batch":
        parser = argparse.ArgumentParser(
            prog="koo_deep_report batch",
            description="디렉토리 내 모든 시뮬 배치 분석",
        )
        parser.add_argument("path", help="배치 분석할 루트 디렉토리")
        _add_single_args(parser)
        parser.add_argument("--skip-existing", action="store_true",
                            help="result.json이 이미 있으면 스킵")
        parser.add_argument("--threads", type=int, default=1,
                            help="병렬 처리 스레드 수 (기본 1)")
        args = parser.parse_args(argv[1:])
        args.command = "batch"
        run_batch(args)
    else:
        parser = argparse.ArgumentParser(
            prog="koo_deep_report",
            description="LS-DYNA 단일 시뮬레이션 깊은 분석 + HTML 리포트",
        )
        _add_single_args(parser)
        args = parser.parse_args(argv)
        args.command = "single"
        run_single(args)


def _add_single_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("path", nargs="?", help="시뮬 디렉토리 또는 d3plot 파일 경로")
    p.add_argument("--config", "-c", default="", metavar="YAML",
                   help="YAML 설정 파일 (GUI에서 생성. CLI 인수보다 우선)")
    p.add_argument("--output", "-o", default="./single_report",
                   help="출력 디렉토리 (기본: ./single_report)")
    p.add_argument("--label", default="",
                   help="리포트 제목 레이블")
    p.add_argument("--yield-stress", type=float, default=0.0, metavar="MPa",
                   help="글로벌 항복 응력 (MPa). keyword 없을 때 fallback")
    p.add_argument("--strain-limit", type=float, default=0.0, metavar="EPS",
                   help="글로벌 변형률 한계 (0 = keyword 자동 또는 기본 0.2%%)")
    p.add_argument("--parts", nargs="+", type=int, default=None, metavar="ID",
                   help="분석할 부품 ID 목록 (기본: 전체)")
    p.add_argument("--part-pattern", default="", metavar="PATTERN",
                   help="렌더 부품 필터 패턴 (예: PKG*)")
    p.add_argument("--no-render", action="store_true",
                   help="렌더링 비활성화")
    p.add_argument("--per-part-render", action="store_true",
                   help="부품별 개별 렌더링 활성화")
    p.add_argument("--ua-threads", type=int, default=0,
                   help="unified_analyzer 스레드 수 (0=자동)")
    p.add_argument("--render-threads", type=int, default=1,
                   help="병렬 렌더링 LSPrePost 인스턴스 수 (기본 1)")
    p.add_argument("--element-quality", action="store_true",
                   help="요소 품질 분석 활성화 (aspect ratio, Jacobian 등)")
    p.add_argument("--design-overrides", default="", metavar="JSON",
                   help="per-part 설계 기준 JSON 파일 (GUI에서 자동 생성)")
    p.add_argument("--material-overrides", default="", metavar="JSON",
                   help="per-material 설계 기준 JSON 파일 (MID 또는 MAT 타입 키)")
    p.add_argument("--install-dir", default="", metavar="DIR",
                   help="설치 디렉토리 (unified_analyzer, lsprepost 자동 탐색 기준)")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="unified_analyzer 출력 표시")
    # Section view rendering (software-rasterized, VTK-free)
    p.add_argument("--section-view", action="store_true",
                   help="소프트웨어 단면뷰 렌더링 활성화 (VTK 불필요, LSPrePost 단면 렌더 대체)")
    p.add_argument("--section-view-mode", default="section",
                   choices=["section", "section_3d"],
                   help="단면뷰 모드: section=2D, section_3d=3D 반절단 뷰 (기본: section)")
    p.add_argument("--section-view-per-part", action="store_true",
                   help="파트별 단면뷰 렌더링 활성화")
    p.add_argument("--section-view-axes", nargs="+", default=["x", "y", "z"],
                   choices=["x", "y", "z"], metavar="AXIS",
                   help="단면 축 목록 (기본: x y z). 예: --section-view-axes x y z")
    p.add_argument("--section-view-fields", nargs="+", default=None,
                   choices=["von_mises", "eps", "strain", "displacement", "pressure", "max_shear"],
                   metavar="FIELD",
                   help="단면뷰 스칼라 필드 (기본: von_mises strain). strain=변위기반 총변형률, eps=소성변형률")
    p.add_argument("--section-view-target-ids", nargs="+", type=int, default=None, metavar="ID",
                   help="단면뷰 타겟 파트 ID 목록 (미지정=전체)")
    p.add_argument("--section-view-target-patterns", nargs="+", default=None, metavar="PAT",
                   help="단면뷰 타겟 파트 패턴 (예: \"*PKG*\")")
    p.add_argument("--section-view-fade", type=float, default=0.0, metavar="DIST",
                   help="비타겟 파트 페이드 거리 (0=단색, >0=거리별 반투명)")
    p.add_argument("--sv-threads", type=int, default=2, metavar="N",
                   help="병렬 단면뷰 렌더러 수 (default 2)")


def _load_design_overrides(path_str: str) -> dict[int, dict] | None:
    """Load per-part design overrides from JSON file."""
    if not path_str:
        return None
    p = Path(path_str)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return {int(k): v for k, v in raw.items()}
    except Exception:
        return None


def _load_material_overrides(path_str: str) -> dict[str, dict] | None:
    """Load per-material design overrides from JSON file.

    Keys can be MID numbers (as strings) or MAT type names.
    """
    if not path_str:
        return None
    p = Path(path_str)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Lightweight YAML config parser (no PyYAML dependency)
# ---------------------------------------------------------------------------
def _parse_config_yaml(path: str) -> dict:
    """Parse koo_deep_report YAML config file into a flat dict.

    Handles the YAML format generated by GUI's build_yaml().
    Returns a dict with keys matching argparse namespace attributes.
    """
    text = Path(path).read_text(encoding="utf-8")

    cfg: dict = {}

    # input.d3plot
    m = re.search(r'^\s*d3plot:\s*["\']?([^"\'#\n]+)', text, re.MULTILINE)
    if m:
        cfg["path"] = m.group(1).strip()

    # output.directory
    m = re.search(r'directory:\s*["\']?([^"\'#\n]+)', text)
    if m:
        cfg["output"] = m.group(1).strip()

    # performance
    m = re.search(r'(?<!\w)threads:\s*(\d+)', text)
    if m:
        cfg["ua_threads"] = int(m.group(1))

    m = re.search(r'render_threads:\s*(\d+)', text)
    if m:
        cfg["render_threads"] = int(m.group(1))

    m = re.search(r'verbose:\s*(true|false)', text, re.IGNORECASE)
    if m:
        cfg["verbose"] = m.group(1).lower() == "true"

    m = re.search(r'install_dir:\s*["\']?([^"\'#\n]+)', text)
    if m:
        cfg["install_dir"] = m.group(1).strip()

    # design_criteria
    m = re.search(r'global_stress_limit:\s*([\d.eE+\-]+)', text)
    if m:
        v = float(m.group(1))
        if v > 0:
            cfg["yield_stress"] = v

    m = re.search(r'global_strain_limit:\s*([\d.eE+\-]+)', text)
    if m:
        v = float(m.group(1))
        if v > 0:
            cfg["strain_limit"] = v

    # design_criteria.material_overrides → write temp JSON
    mat_overrides: dict[str, dict] = {}
    mo_start = text.find("material_overrides:")
    if mo_start >= 0:
        mo_block = text[mo_start:]
        # Truncate at next sibling key (2-space indented, like "  overrides:" or "  global_")
        sib = re.search(r'\n  \w', mo_block[len("material_overrides:"):])
        if sib:
            mo_block = mo_block[:len("material_overrides:") + sib.start()]
        # Each key: indented 4+ spaces, can be number (MID) or name (MAT type)
        for key_m in re.finditer(r'^\s{4,}(\w+):\s*$', mo_block, re.MULTILINE):
            key = key_m.group(1)
            after = mo_block[key_m.end():key_m.end() + 300]
            after = re.split(r'\n\s{4}\w+:|^\S', after, maxsplit=1, flags=re.MULTILINE)[0]
            mov: dict[str, float] = {}
            sl = re.search(r'stress_limit:\s*([\d.eE+\-]+)', after)
            if sl:
                mov["stress_limit"] = float(sl.group(1))
            el = re.search(r'strain_limit:\s*([\d.eE+\-]+)', after)
            if el:
                mov["strain_limit"] = float(el.group(1))
            if mov:
                mat_overrides[key] = mov
    if mat_overrides:
        import tempfile
        mo_path = Path(tempfile.mkdtemp()) / "material_overrides.json"
        mo_path.write_text(json.dumps(mat_overrides, indent=2))
        cfg["material_overrides"] = str(mo_path)

    # design_criteria.overrides → write temp JSON
    overrides: dict[int, dict] = {}
    # Find "overrides:" that is NOT "material_overrides:"
    for ov_m in re.finditer(r'(?<!material_)overrides:', text):
        ov_block = text[ov_m.start():]
        for pid_m in re.finditer(r'^\s{4,}(\d+):\s*$', ov_block, re.MULTILINE):
            pid = int(pid_m.group(1))
            after = ov_block[pid_m.end():pid_m.end() + 300]
            after = re.split(r'\n\s{4}\d+:|^\S', after, maxsplit=1, flags=re.MULTILINE)[0]
            ov: dict[str, float] = {}
            sl = re.search(r'stress_limit:\s*([\d.eE+\-]+)', after)
            if sl:
                ov["stress_limit"] = float(sl.group(1))
            el = re.search(r'strain_limit:\s*([\d.eE+\-]+)', after)
            if el:
                ov["strain_limit"] = float(el.group(1))
            if ov:
                overrides[pid] = ov
        break  # only first match
    if overrides:
        import tempfile
        ov_path = Path(tempfile.mkdtemp()) / "design_overrides.json"
        ov_path.write_text(json.dumps({str(k): v for k, v in overrides.items()}, indent=2))
        cfg["design_overrides"] = str(ov_path)

    # analysis_jobs → determine analysis types + parts
    analysis_types = re.findall(r'type:\s*(\w+)', text)
    if "element_quality" in analysis_types:
        cfg["element_quality"] = True

    # parts (from any analysis_job)
    m = re.search(r'parts:\s*\[([^\]]+)\]', text)
    if m:
        try:
            cfg["parts"] = [int(x.strip().strip('"')) for x in m.group(1).split(",") if x.strip()]
        except ValueError:
            pass

    # part_pattern
    m = re.search(r'part_pattern:\s*["\']?([^"\'#\n]+)', text)
    if m:
        cfg["part_pattern"] = m.group(1).strip()

    # render_jobs → render enabled/disabled
    cfg["no_render"] = "render_jobs:" not in text

    return cfg


def _apply_config_to_args(args: argparse.Namespace) -> None:
    """If --config is given, parse YAML and fill in unset args."""
    config_path = getattr(args, "config", "")
    if not config_path:
        return

    p = Path(config_path)
    if not p.exists():
        print(f"ERROR: 설정 파일을 찾을 수 없습니다: {config_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[koo_deep_report] config: {p}")
    cfg = _parse_config_yaml(config_path)

    # YAML values fill in defaults; explicit CLI args take priority.
    # argparse defaults: path=None, output="./single_report", yield_stress=0.0, etc.
    if not args.path and "path" in cfg:
        args.path = cfg["path"]
    if args.output == "./single_report" and "output" in cfg:
        args.output = cfg["output"]
    if args.yield_stress == 0.0 and "yield_stress" in cfg:
        args.yield_stress = cfg["yield_stress"]
    if getattr(args, "strain_limit", 0.0) == 0.0 and "strain_limit" in cfg:
        args.strain_limit = cfg["strain_limit"]
    if args.ua_threads == 0 and "ua_threads" in cfg:
        args.ua_threads = cfg["ua_threads"]
    if args.render_threads == 1 and "render_threads" in cfg:
        args.render_threads = cfg["render_threads"]
    if not args.verbose and cfg.get("verbose"):
        args.verbose = True
    if not getattr(args, "element_quality", False) and cfg.get("element_quality"):
        args.element_quality = True
    if not getattr(args, "no_render", False) and cfg.get("no_render"):
        args.no_render = True
    if not getattr(args, "design_overrides", "") and "design_overrides" in cfg:
        args.design_overrides = cfg["design_overrides"]
    if not getattr(args, "material_overrides", "") and "material_overrides" in cfg:
        args.material_overrides = cfg["material_overrides"]
    if not args.parts and "parts" in cfg:
        args.parts = cfg["parts"]
    if not getattr(args, "part_pattern", "") and "part_pattern" in cfg:
        args.part_pattern = cfg["part_pattern"]
    if not getattr(args, "install_dir", "") and "install_dir" in cfg:
        args.install_dir = cfg["install_dir"]


def _resolve_install_dir(explicit: str) -> Path | None:
    """Resolve install directory for binary discovery.

    Priority: --install-dir > auto-detect from script location.
    Auto-detect: if sys.argv[0] is inside an installed bin/ dir,
    use its parent as install root (e.g. installed/bin/koo_deep_report → installed/).
    """
    if explicit:
        p = Path(explicit).resolve()
        if p.is_dir():
            return p
    # Auto-detect: script in .../bin/koo_deep_report → parent is .../bin/ → grandparent is install root
    script = Path(sys.argv[0]).resolve()
    bin_dir = script.parent
    if bin_dir.name == "bin":
        install_root = bin_dir.parent
        # Sanity check: install root should have bin/ with unified_analyzer
        if (bin_dir / "unified_analyzer").exists() or (bin_dir / "unified_analyzer.exe").exists():
            return install_root
    return None


def run_single(args: argparse.Namespace) -> None:
    # Apply YAML config if provided (fills unset args)
    _apply_config_to_args(args)

    if not args.path:
        print("ERROR: 경로를 지정하세요. 예: koo_deep_report /data/sim_dir", file=sys.stderr)
        print("       또는: koo_deep_report --config analysis.yaml", file=sys.stderr)
        sys.exit(1)

    target = Path(args.path).resolve()
    output_dir = Path(args.output).resolve()

    # 경로가 d3plot 파일이면 부모 디렉토리를 sim_dir로
    if target.is_file() and target.name.startswith("d3plot"):
        sim_dir = target.parent
    elif target.is_dir():
        sim_dir = target
    else:
        print(f"ERROR: '{target}' 는 유효한 디렉토리 또는 d3plot 파일이 아닙니다.", file=sys.stderr)
        sys.exit(1)

    print(f"[koo_deep_report] 시뮬 경로: {sim_dir}")
    print(f"[koo_deep_report] 출력 디렉토리: {output_dir}")

    # 1. 파일 탐지 + 종료 판단
    sim_info = find_files(sim_dir)
    print(f"[koo_deep_report] 분석 Tier: {sim_info.tier_label} | 종료: {'정상' if sim_info.normal_termination else ('오류' if sim_info.normal_termination is False else '불명')} ({sim_info.termination_source})")

    if not sim_info.can_analyze:
        print("ERROR: 분석 불가 (오류 종료 또는 d3plot 없음). --verbose로 상세 확인.", file=sys.stderr)
        sys.exit(2)

    # 2. glstat 파싱
    glstat_data = None
    if sim_info.glstat:
        glstat_data = parse_glstat(sim_info.glstat)
        if glstat_data and glstat_data.t:
            print(f"[koo_deep_report] glstat: {len(glstat_data.t)}개 타임스텝, "
                  f"에너지 비율 min={glstat_data.energy_ratio_min:.4f}" if glstat_data.energy_ratio_min else "")

    # 2b. binout 파싱 (lasso 있을 때)
    binout_data = None
    if sim_info.binout:
        binout_data = parse_binout(sim_info.binout)
        if binout_data:
            n_rc = len(binout_data.rcforc)
            n_sl = len(binout_data.sleout)
            print(f"[koo_deep_report] binout: 접촉 인터페이스 {n_rc}개, 슬라이딩 {n_sl}개")

    # 3. unified_analyzer 실행 (analysis + render)
    render_cfg = RenderConfig(
        enabled=not args.no_render,
        per_part_render=args.per_part_render,
        part_pattern=args.part_pattern or "",
    )
    # install_dir: 명시 > 스크립트 위치 자동 탐색
    install_dir = _resolve_install_dir(getattr(args, "install_dir", ""))

    # Section view rendering config
    sv_cfg = None
    if getattr(args, "section_view", False):
        sv_fields = getattr(args, "section_view_fields", None) or ["von_mises", "strain"]
        sv_cfg = SectionViewRenderConfig(
            enabled=True,
            view_mode=getattr(args, "section_view_mode", "section"),
            axes=getattr(args, "section_view_axes", ["x", "y", "z"]),
            scalar_fields=sv_fields,
            target_part_ids=getattr(args, "section_view_target_ids", None) or [],
            target_patterns=getattr(args, "section_view_target_patterns", None) or [],
            fade_distance=getattr(args, "section_view_fade", 0.0),
            per_part_render=getattr(args, "section_view_per_part", False),
            sv_threads=getattr(args, "sv_threads", 2),
        )

    print(f"[koo_deep_report] unified_analyzer 실행 중... (렌더{'ON' if render_cfg.enabled else 'OFF'}"
          f"{' | 단면뷰ON' if sv_cfg else ''})")
    try:
        d3plot_result = run_analysis(
            d3plot_path=sim_info.d3plot,
            output_dir=output_dir,
            render_config=render_cfg,
            part_ids=args.parts,
            threads=args.ua_threads,
            render_threads=args.render_threads,
            verbose=args.verbose,
            element_quality=getattr(args, "element_quality", False),
            install_dir=install_dir,
            section_view_config=sv_cfg,
        )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(3)

    # 4. 집계 (SingleResult)
    design_overrides = _load_design_overrides(getattr(args, "design_overrides", ""))
    material_overrides = _load_material_overrides(getattr(args, "material_overrides", ""))
    result = _aggregate(
        sim_info=sim_info,
        d3plot_result=d3plot_result,
        glstat_data=glstat_data,
        binout_data=binout_data,
        yield_stress=args.yield_stress,
        strain_limit=getattr(args, "strain_limit", 0.0),
        label=args.label or sim_dir.name,
        design_overrides=design_overrides,
        material_overrides=material_overrides,
    )

    # 5. result.json 저장
    result_json_path = output_dir / "result.json"
    result_json_path.write_text(
        json.dumps(result.to_compare_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[koo_deep_report] result.json 저장: {result_json_path}")

    # 6. HTML 생성
    html_path = output_dir / "report.html"
    generate_html(result, html_path)
    print(f"[koo_deep_report] 완료: {html_path}")

    _print_summary(result)

    # 7. 브라우저에서 리포트 자동 열기
    import webbrowser
    try:
        webbrowser.open(html_path.as_uri())
    except Exception:
        pass


def run_batch(args: argparse.Namespace) -> None:
    import concurrent.futures
    import threading
    from .core.sim_detector import find_all
    from .report.batch_report import generate_batch_html, load_results_from_dir

    target = Path(args.path).resolve()
    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    print(f"[batch] 탐색 중: {target}")
    sims = find_all(target, recursive=True)
    all_sims = sims
    sims = [s for s in sims if s.can_analyze]
    skipped_t0 = [s.path.name for s in all_sims if not s.can_analyze]
    print(f"[batch] 분석 가능: {len(sims)}개 | T0(스킵): {len(skipped_t0)}개")

    failed: list[str] = []
    skipped_existing: list[str] = []
    lock = threading.Lock()

    def run_one_safe(sim_info):
        case_out = output_root / sim_info.path.name
        if args.skip_existing and (case_out / "result.json").exists():
            with lock:
                skipped_existing.append(sim_info.path.name)
            return "skip", sim_info.path.name

        try:
            _run_one(sim_info, case_out, args)
            return "ok", sim_info.path.name
        except Exception as e:
            with lock:
                failed.append(sim_info.path.name)
            return "fail", f"{sim_info.path.name}: {e}"

    n = len(sims)
    threads = max(1, args.threads)
    done = [0]

    if threads == 1:
        for i, sim_info in enumerate(sims, 1):
            status, name = run_one_safe(sim_info)
            tag = {"ok": "OK", "skip": "SKIP", "fail": "FAIL"}[status]
            print(f"[batch] [{i}/{n}] {name} → {tag}")
    else:
        print(f"[batch] 병렬 실행: {threads}개 스레드")
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
            futures = {ex.submit(run_one_safe, s): s for s in sims}
            for f in concurrent.futures.as_completed(futures):
                with lock:
                    done[0] += 1
                    i = done[0]
                status, name = f.result()
                tag = {"ok": "OK", "skip": "SKIP", "fail": "FAIL"}[status]
                print(f"[batch] [{i}/{n}] {name} → {tag}")

    # failed_cases.txt
    all_skipped = skipped_existing + skipped_t0
    if failed:
        fail_path = output_root / "failed_cases.txt"
        fail_path.write_text("\n".join(failed), encoding="utf-8")
        print(f"\n실패: {len(failed)}개 → {fail_path}")

    # batch_report.html
    results, _ = load_results_from_dir(output_root)
    batch_html = output_root / "batch_report.html"
    generate_batch_html(
        results=results,
        failed=failed,
        skipped=all_skipped,
        output_root=output_root,
        output_path=batch_html,
        yield_stress=getattr(args, "yield_stress", 0.0),
    )
    print(f"[batch] 완료. 출력: {output_root}")
    print(f"[batch] 배치 리포트: {batch_html}")


def _run_one(sim_info, output_dir: Path, args: argparse.Namespace) -> None:
    glstat_data = None
    if sim_info.glstat:
        glstat_data = parse_glstat(sim_info.glstat)

    binout_data = None
    if sim_info.binout:
        binout_data = parse_binout(sim_info.binout)

    render_cfg = RenderConfig(
        enabled=not args.no_render,
        per_part_render=getattr(args, "per_part_render", False),
        part_pattern=getattr(args, "part_pattern", "") or "",
    )
    install_dir = _resolve_install_dir(getattr(args, "install_dir", ""))
    sv_cfg = None
    if getattr(args, "section_view", False):
        sv_fields = getattr(args, "section_view_fields", None) or ["von_mises", "strain"]
        sv_cfg = SectionViewRenderConfig(
            enabled=True,
            view_mode=getattr(args, "section_view_mode", "section"),
            axes=getattr(args, "section_view_axes", ["x", "y", "z"]),
            scalar_fields=sv_fields,
            target_part_ids=getattr(args, "section_view_target_ids", None) or [],
            target_patterns=getattr(args, "section_view_target_patterns", None) or [],
            fade_distance=getattr(args, "section_view_fade", 0.0),
            per_part_render=getattr(args, "section_view_per_part", False),
            sv_threads=getattr(args, "sv_threads", 2),
        )
    d3plot_result = run_analysis(
        d3plot_path=sim_info.d3plot,
        output_dir=output_dir,
        render_config=render_cfg,
        part_ids=getattr(args, "parts", None),
        threads=getattr(args, "ua_threads", 0),
        render_threads=getattr(args, "render_threads", 1),
        verbose=False,
        element_quality=getattr(args, "element_quality", False),
        install_dir=install_dir,
        section_view_config=sv_cfg,
    )
    result = _aggregate(
        sim_info=sim_info,
        d3plot_result=d3plot_result,
        glstat_data=glstat_data,
        binout_data=binout_data,
        yield_stress=getattr(args, "yield_stress", 0.0),
        strain_limit=getattr(args, "strain_limit", 0.0),
        label=getattr(args, "label", "") or sim_info.path.name,
    )
    (output_dir / "result.json").write_text(
        json.dumps(result.to_compare_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    generate_html(result, output_dir / "report.html")


def _aggregate(
    sim_info,
    d3plot_result,
    glstat_data,
    yield_stress: float,
    label: str,
    binout_data=None,
    strain_limit: float = 0.0,
    design_overrides: dict[int, dict] | None = None,
    material_overrides: dict[str, dict] | None = None,
) -> SingleResult:
    from .core.keyword_parser import find_and_parse_keyword

    result = SingleResult(
        sim_info=sim_info,
        d3plot_result=d3plot_result,
        glstat_data=glstat_data,
        binout_data=binout_data,
        label=label,
        yield_stress=yield_stress,
    )

    if d3plot_result is None:
        return result

    # Parse keyword file for per-part material data
    design_criteria = {}
    kw_data = None
    if sim_info.d3plot:
        kw_data = find_and_parse_keyword(sim_info.d3plot)
        if kw_data:
            n_mat = len(kw_data.materials)
            n_part = len(kw_data.parts)
            print(f"[koo_deep_report] keyword: {n_part} parts, {n_mat} materials parsed from {kw_data.source_path}")
            design_criteria = kw_data.get_design_criteria(design_overrides, material_overrides)

    # Back-fill keyword part names into PartTimeSeries and MotionData
    # (C++ output may have empty part_name since d3plot doesn't store names)
    if kw_data:
        for series_list in [d3plot_result.stress, d3plot_result.strain, d3plot_result.acceleration,
                           d3plot_result.max_principal, d3plot_result.min_principal,
                           d3plot_result.max_principal_strain, d3plot_result.min_principal_strain]:
            for s in series_list:
                if not s.part_name:
                    pm = kw_data.parts.get(s.part_id)
                    if pm and pm.name:
                        s.part_name = pm.name
        for pid, md in d3plot_result.motion.items():
            if not md.part_name:
                pm = kw_data.parts.get(pid)
                if pm and pm.name:
                    md.part_name = pm.name

    # Build part name lookup from keyword parser (most reliable source)
    kw_name_map: dict[int, str] = {}
    if kw_data:
        for pid_k, pm in kw_data.parts.items():
            if pm.name:
                kw_name_map[pid_k] = pm.name

    # 부품별 집계
    all_part_ids = set(
        [s.part_id for s in d3plot_result.stress] +
        [s.part_id for s in d3plot_result.strain] +
        list(d3plot_result.motion.keys())
    )

    for pid in all_part_ids:
        st = d3plot_result.get_stress(pid)
        sr = d3plot_result.get_strain(pid)
        mo = d3plot_result.get_motion(pid)
        s1 = d3plot_result.get_max_principal(pid)
        s3 = d3plot_result.get_min_principal(pid)
        e1 = d3plot_result.get_max_principal_strain(pid)
        e3 = d3plot_result.get_min_principal_strain(pid)

        # Priority: keyword name > C++ output name > fallback
        part_name = kw_name_map.get(pid, "")
        if not part_name:
            part_name = (
                (st.part_name if st and st.part_name else "")
                or (sr.part_name if sr and sr.part_name else "")
                or (mo.part_name if mo and mo.part_name else "")
            )

        ps = PartSummary(
            part_id=pid,
            part_name=part_name,
            peak_stress=st.global_max if st else 0.0,
            time_of_peak_stress=st.time_of_max if st else 0.0,
            peak_element_id=st.peak_element_id if st else None,
            peak_strain=sr.global_max if sr else 0.0,
            peak_max_principal=s1.global_max if s1 else 0.0,
            peak_min_principal=s3.global_min if s3 else 0.0,
            peak_max_principal_strain=e1.global_max if e1 else 0.0,
            peak_min_principal_strain=e3.global_min if e3 else 0.0,
            peak_disp_mag=mo.peak_disp_mag if mo else 0.0,
            peak_vel_mag=mo.peak_vel_mag if mo else 0.0,
            peak_acc_mag=mo.peak_acc_mag if mo else 0.0,
        )

        # Apply design criteria (per-part from keyword, or global fallback)
        dc = design_criteria.get(pid)
        if dc:
            ps.mat_type = dc.mat_type
            ps.stress_limit = dc.stress_limit
            ps.stress_source = dc.stress_source
            ps.strain_limit = dc.strain_limit
            ps.strain_source = dc.strain_source
        else:
            # Global fallback overrides (when keyword data not available for this part)
            if yield_stress > 0:
                ps.stress_limit = yield_stress
                ps.stress_source = "manual"
            if strain_limit > 0:
                ps.strain_limit = strain_limit
                ps.strain_source = "manual"

        # Compute ratios and safety factor
        if ps.stress_limit > 0 and ps.peak_stress > 0:
            ps.safety_factor = ps.stress_limit / ps.peak_stress
            ps.stress_ratio = ps.peak_stress / ps.stress_limit
        if ps.strain_limit > 0 and ps.peak_strain > 0:
            ps.strain_ratio = ps.peak_strain / ps.strain_limit

        result.parts[pid] = ps

    # 글로벌 요약
    if result.parts:
        best = max(result.parts.values(), key=lambda p: p.peak_stress)
        result.peak_stress_global = best.peak_stress
        result.peak_stress_part_id = best.part_id
        result.peak_strain_global = max(p.peak_strain for p in result.parts.values())
        result.peak_disp_global = max(p.peak_disp_mag for p in result.parts.values())

    if glstat_data:
        result.energy_ratio_min = glstat_data.energy_ratio_min

    return result


def _print_summary(result: SingleResult) -> None:
    warn_icon = {"ok": "  ", "warn": "!! ", "crit": "[X]", "none": "  "}

    print("\n-- Summary ------------------------------------------")
    print(f"  Tier         : {result.sim_info.tier_label}")
    print(f"  종료 상태    : {'정상' if result.sim_info.normal_termination else ('오류' if result.sim_info.normal_termination is False else '불명')}")
    peak_part_name = result.parts.get(result.peak_stress_part_id, None)
    peak_label = f"Part {result.peak_stress_part_id}"
    if peak_part_name and peak_part_name.part_name:
        peak_label += f" ({peak_part_name.part_name})"
    print(f"  피크 응력    : {result.peak_stress_global:.2f} MPa ({peak_label})")
    print(f"  피크 변형률  : {result.peak_strain_global:.4f}")
    print(f"  피크 변위    : {result.peak_disp_global:.2f} mm")
    if result.energy_ratio_min is not None:
        print(f"  에너지 비율  : {result.energy_ratio_min:.4f} (min)")
    if result.d3plot_result and result.d3plot_result.element_quality:
        worst_ar = max(q.peak_aspect_ratio for q in result.d3plot_result.element_quality)
        worst_jac = min(q.min_jacobian for q in result.d3plot_result.element_quality)
        n_neg = max(q.max_negative_jacobian_count for q in result.d3plot_result.element_quality)
        print(f"  요소 품질    : AR={worst_ar:.2f} | Jac={worst_jac:.2f} | 음수Jac={n_neg}개")

    # Per-part design criteria warnings
    warnings = [(ps, ps.worst_warning) for ps in result.parts.values() if ps.worst_warning in ("warn", "crit")]
    if warnings:
        print("\n-- Design Criteria Warnings -------------------------")
        for ps, level in sorted(warnings, key=lambda x: ("crit", "warn").index(x[1]) if x[1] in ("crit", "warn") else 2):
            icon = warn_icon[level]
            details = []
            if ps.stress_warning in ("warn", "crit"):
                details.append(f"σ={ps.peak_stress:.1f}/{ps.stress_limit:.1f}MPa ({ps.stress_ratio:.0%})")
            if ps.strain_warning in ("warn", "crit"):
                details.append(f"ε={ps.peak_strain:.4f}/{ps.strain_limit:.4f} ({ps.strain_ratio:.0%})")
            print(f"  {icon} Part {ps.part_id} ({ps.part_name}): {', '.join(details)}")
            if ps.mat_type:
                print(f"       MAT: {ps.mat_type} | source: σ={ps.stress_source}, ε={ps.strain_source}")

    print("---------------------------------------------")


if __name__ == "__main__":
    main()
