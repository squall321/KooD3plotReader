"""single_analyzer CLI entry point."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from .core.sim_detector import find_files
from .core.glstat_reader import parse_glstat
from .core.d3plot_reader import run_analysis
from .core.binout_reader import parse_binout
from .render.job_builder import RenderConfig
from .report.models import SingleResult, PartSummary
from .report.html_report import generate_html


_SUBCOMMANDS = {"batch", "compare"}


def main() -> None:
    # Detect subcommand manually to avoid argparse positional conflict
    argv = sys.argv[1:]
    command = argv[0] if argv and argv[0] in _SUBCOMMANDS else "single"

    if command == "batch":
        parser = argparse.ArgumentParser(
            prog="single_analyzer batch",
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
            prog="single_analyzer",
            description="LS-DYNA 단일 시뮬레이션 깊은 분석 + HTML 리포트",
        )
        _add_single_args(parser)
        args = parser.parse_args(argv)
        args.command = "single"
        run_single(args)


def _add_single_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("path", nargs="?", help="시뮬 디렉토리 또는 d3plot 파일 경로")
    p.add_argument("--output", "-o", default="./single_report",
                   help="출력 디렉토리 (기본: ./single_report)")
    p.add_argument("--label", default="",
                   help="리포트 제목 레이블")
    p.add_argument("--yield-stress", type=float, default=0.0, metavar="MPa",
                   help="항복 응력 (MPa). 지정 시 Safety Factor 계산")
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
    p.add_argument("--verbose", "-v", action="store_true",
                   help="unified_analyzer 출력 표시")


def run_single(args: argparse.Namespace) -> None:
    if not args.path:
        print("ERROR: 경로를 지정하세요. 예: single_analyzer /data/sim_dir", file=sys.stderr)
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

    print(f"[single_analyzer] 시뮬 경로: {sim_dir}")
    print(f"[single_analyzer] 출력 디렉토리: {output_dir}")

    # 1. 파일 탐지 + 종료 판단
    sim_info = find_files(sim_dir)
    print(f"[single_analyzer] 분석 Tier: {sim_info.tier_label} | 종료: {'정상' if sim_info.normal_termination else ('오류' if sim_info.normal_termination is False else '불명')} ({sim_info.termination_source})")

    if not sim_info.can_analyze:
        print("ERROR: 분석 불가 (오류 종료 또는 d3plot 없음). --verbose로 상세 확인.", file=sys.stderr)
        sys.exit(2)

    # 2. glstat 파싱
    glstat_data = None
    if sim_info.glstat:
        glstat_data = parse_glstat(sim_info.glstat)
        if glstat_data and glstat_data.t:
            print(f"[single_analyzer] glstat: {len(glstat_data.t)}개 타임스텝, "
                  f"에너지 비율 min={glstat_data.energy_ratio_min:.4f}" if glstat_data.energy_ratio_min else "")

    # 2b. binout 파싱 (lasso 있을 때)
    binout_data = None
    if sim_info.binout:
        binout_data = parse_binout(sim_info.binout)
        if binout_data:
            n_rc = len(binout_data.rcforc)
            n_sl = len(binout_data.sleout)
            print(f"[single_analyzer] binout: 접촉 인터페이스 {n_rc}개, 슬라이딩 {n_sl}개")

    # 3. unified_analyzer 실행 (analysis + render)
    render_cfg = RenderConfig(
        enabled=not args.no_render,
        per_part_render=args.per_part_render,
        part_pattern=args.part_pattern or "",
    )
    print(f"[single_analyzer] unified_analyzer 실행 중... (렌더{'ON' if render_cfg.enabled else 'OFF'})")
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
        )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(3)

    # 4. 집계 (SingleResult)
    result = _aggregate(
        sim_info=sim_info,
        d3plot_result=d3plot_result,
        glstat_data=glstat_data,
        binout_data=binout_data,
        yield_stress=args.yield_stress,
        label=args.label or sim_dir.name,
    )

    # 5. result.json 저장
    result_json_path = output_dir / "result.json"
    result_json_path.write_text(
        json.dumps(result.to_compare_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[single_analyzer] result.json 저장: {result_json_path}")

    # 6. HTML 생성
    html_path = output_dir / "report.html"
    generate_html(result, html_path)
    print(f"[single_analyzer] 완료: {html_path}")

    _print_summary(result)


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
    d3plot_result = run_analysis(
        d3plot_path=sim_info.d3plot,
        output_dir=output_dir,
        render_config=render_cfg,
        part_ids=getattr(args, "parts", None),
        threads=getattr(args, "ua_threads", 0),
        render_threads=getattr(args, "render_threads", 1),
        verbose=False,
        element_quality=getattr(args, "element_quality", False),
    )
    result = _aggregate(
        sim_info=sim_info,
        d3plot_result=d3plot_result,
        glstat_data=glstat_data,
        binout_data=binout_data,
        yield_stress=getattr(args, "yield_stress", 0.0),
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
) -> SingleResult:
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

        name = (st or sr or mo or None)
        part_name = (st.part_name if st else (sr.part_name if sr else (mo.part_name if mo else f"Part_{pid}")))

        ps = PartSummary(
            part_id=pid,
            part_name=part_name,
            peak_stress=st.global_max if st else 0.0,
            time_of_peak_stress=st.time_of_max if st else 0.0,
            peak_element_id=st.peak_element_id if st else None,
            peak_strain=sr.global_max if sr else 0.0,
            peak_disp_mag=mo.peak_disp_mag if mo else 0.0,
            peak_vel_mag=mo.peak_vel_mag if mo else 0.0,
            peak_acc_mag=mo.peak_acc_mag if mo else 0.0,
        )
        if yield_stress > 0 and ps.peak_stress > 0:
            ps.safety_factor = yield_stress / ps.peak_stress

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
    print("\n── 요약 ─────────────────────────────────────")
    print(f"  Tier         : {result.sim_info.tier_label}")
    print(f"  종료 상태    : {'정상' if result.sim_info.normal_termination else ('오류' if result.sim_info.normal_termination is False else '불명')}")
    print(f"  피크 응력    : {result.peak_stress_global:.2f} MPa (Part {result.peak_stress_part_id})")
    print(f"  피크 변형률  : {result.peak_strain_global:.4f}")
    print(f"  피크 변위    : {result.peak_disp_global:.2f} mm")
    if result.energy_ratio_min is not None:
        print(f"  에너지 비율  : {result.energy_ratio_min:.4f} (min)")
    if result.d3plot_result and result.d3plot_result.element_quality:
        worst_ar = max(q.peak_aspect_ratio for q in result.d3plot_result.element_quality)
        worst_jac = min(q.min_jacobian for q in result.d3plot_result.element_quality)
        n_neg = max(q.max_negative_jacobian_count for q in result.d3plot_result.element_quality)
        print(f"  요소 품질    : AR={worst_ar:.2f} | Jac={worst_jac:.2f} | 음수Jac={n_neg}개")
    print("─────────────────────────────────────────────")


if __name__ == "__main__":
    main()
