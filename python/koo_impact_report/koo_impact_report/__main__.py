"""CLI entry point: python -m koo_impact_report"""
from __future__ import annotations
import argparse
import os
import sys
import time
from pathlib import Path


def _parse_face_list(spec: str | None) -> list[str] | None:
    if not spec:
        return None
    return [s.strip() for s in spec.split(",") if s.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="koo_impact_report",
        description="Multi-face partial-impact (DWI) DOE analysis report generator",
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--test-dir",
        help="Path to test directory (scenario.json + F*/Run_*/analysis_result.json layout)",
    )
    input_group.add_argument(
        "--from-json",
        metavar="JSON_FILE",
        help="impact_payload.json sidecar 에서 HTML 재렌더 (loader/analyzer 생략, ~2s). "
             "schema_version 불일치 시 에러.",
    )

    parser.add_argument("--output", "-o", default=None, help="Output HTML file")
    parser.add_argument("--json", default=None, help="Also save report JSON to this path")
    parser.add_argument(
        "--format", nargs="+", default=["html", "terminal"],
        choices=["html", "json", "terminal"],
        help="Output formats (default: html terminal)",
    )

    parser.add_argument("--threshold-critical", type=float, default=None,
                        help="Critical threshold for the primary metric. "
                             "Units match the dataset (no implicit default).")
    parser.add_argument("--threshold-warning", type=float, default=None,
                        help="Warning threshold for the primary metric "
                             "(units match the dataset).")
    parser.add_argument("--yield-stress", type=float, default=None,
                        help="Global yield-stress override (units match peak_stress). "
                             "When omitted, per-part yield comes from the *MAT_ "
                             "card via the loader.")
    parser.add_argument("--faces", default=None,
                        help="Comma-separated face subset (e.g. F1,F2,F5). Default: all discovered.")
    parser.add_argument("--units", default=None,
                        choices=["SI", "ton-mm-s", "ton-mm-ms", "g-mm-ms"],
                        help="Override solver unit system. When omitted the loader "
                             "auto-detects from density + impactor radius. "
                             "Use this when auto-detection picks the wrong system "
                             "(e.g. SI-style density in a ton-mm-s deck).")
    parser.add_argument("--parallel-runs", type=int, default=0, metavar="N",
                        help="Concurrent DOE run workers (process pool). "
                             "0 = auto: SLURM_CPUS_PER_TASK (or CPU count) // threads-per-run. "
                             "Was hardcoded to 4 before — unreachable from chainrun.")
    parser.add_argument("--threads-per-run", type=int, default=2, metavar="N",
                        help="unified_analyzer threads per DOE worker (default 2).")
    parser.add_argument("--single-file", action="store_true",
                        help="HTML 출력 모드를 inline 단일 파일로 강제 (tier 자동 결정 무시).")
    parser.add_argument("--chunked", action="store_true",
                        help="HTML 출력 모드를 chunked(report_data/ 청크)로 강제.")
    parser.add_argument("--no-cache", action="store_true",
                        help="per-run 증분 캐시(.impact_cache) 읽기/쓰기 모두 끔.")
    parser.add_argument("--refresh-cache", action="store_true",
                        help="캐시를 무시하고 전량 재계산 후 캐시 재작성.")

    args = parser.parse_args()

    # Sibling modules — import lazily so missing pieces don't kill --help
    from . import loader, analyzer
    try:
        from .report.html_report import generate_html
    except ImportError:
        def generate_html(report, path: str | None = None, **_):  # type: ignore
            html = "<html><body>STUB - html_report not available</body></html>"
            if path:
                Path(path).write_text(html, encoding="utf-8")
            return html
    try:
        from .report.json_report import save_json
    except ImportError:
        save_json = None  # type: ignore
    try:
        from .report.terminal import print_report
    except ImportError:
        print_report = None  # type: ignore

    # ── Load ──────────────────────────────────────────────────────
    if args.from_json:
        # sidecar → HTML 재렌더 전용 경로 (loader/analyzer 생략, P5-1).
        import json as _json
        json_in = Path(args.from_json)
        if not json_in.exists():
            print(f"Error: {json_in} does not exist", file=sys.stderr)
            sys.exit(1)
        from .report.emit import render_from_payload, SCHEMA_VERSION
        t0 = time.time()
        doc = _json.loads(json_in.read_text(encoding="utf-8"))
        got_ver = doc.get("schema_version")
        if got_ver != SCHEMA_VERSION:
            print(f"[main] ERROR: sidecar schema_version={got_ver!r} ≠ "
                  f"지원 버전 {SCHEMA_VERSION} — --test-dir 로 재생성하세요.",
                  file=sys.stderr)
            sys.exit(2)
        payload = doc.get("payload") or {}
        html_path = args.output or str(json_in.parent / "report.html")
        if payload.get("chunks") and Path(html_path).parent != json_in.parent:
            print(f"[main] WARN: chunks 매니페스트 존재 — 청크 상대경로가 깨지지 "
                  f"않도록 출력을 sidecar 와 같은 디렉터리에 두는 것을 권장.")
        render_from_payload(payload, html_path,
                            deferred=(None if not args.single_file else False))
        print(f"[main] --from-json re-render: {html_path} "
              f"({time.time() - t0:.1f}s)")
        return
    else:
        test_dir = Path(args.test_dir)
        if not test_dir.exists():
            print(f"Error: {test_dir} does not exist", file=sys.stderr)
            sys.exit(1)
        print(f"[main] Loading {test_dir} …")
        t0 = time.time()

        # Layout-aware dispatch:
        #   F*/Run_*/analysis_result.json present  → load_impact_report (face-tree)
        #   else output/Run_* with step_config + (d3plot OR deep_report output)
        #        → load_partial_impact_doe_report (flat DOE). _discover_test_impact_runs
        #        detects runs even when the d3plot was deleted but deep_report output
        #        (analysis_result.json + motion/) survives.
        face_dirs = loader._discover_face_dirs(test_dir)
        flat_runs = loader._discover_test_impact_runs(test_dir)
        if not face_dirs and flat_runs:
            _n_d3 = sum(1 for r in flat_runs if r["d3plot"].exists())
            _n_reuse = sum(1 for r in flat_runs if r.get("deep_dir"))
            print(
                f"[main] flat DOE / DWI layout detected "
                f"(output/Run_* or output/results/dwi_*/Run_*; {len(flat_runs)} runs; "
                f"{_n_d3} with d3plot, {_n_reuse} reusing deep_report output) "
                f"→ load_partial_impact_doe_report"
            )
            # 풀 크기: CLI > SLURM auto. 과거 4×2 하드코딩은 chainrun 에서
            # 조정 불가 + SLURM cpus-per-task 와 무관하게 고정이었다 (P2-3).
            threads_per_run = max(1, int(args.threads_per_run))
            parallel_runs = int(args.parallel_runs)
            if parallel_runs <= 0:
                cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", 0) or 0) \
                    or (os.cpu_count() or 8)
                parallel_runs = max(1, cpus // threads_per_run)
            print(f"[main] pool: parallel_runs={parallel_runs}, "
                  f"threads_per_run={threads_per_run}")
            report = loader.load_partial_impact_doe_report(
                test_dir=test_dir,
                threads_per_run=threads_per_run,
                parallel_runs=parallel_runs,
                use_cache=not args.no_cache,
                refresh_cache=args.refresh_cache,
            )
        else:
            report = loader.load_impact_report(test_dir)
        print(f"[main] Loaded in {time.time() - t0:.1f}s")

        # 출처 메타 — CLI 레이어에서만 주입 (loader 는 결정적 유지, P2-5).
        try:
            from .provenance import build_provenance
            report.provenance = build_provenance(report)
        except Exception as e:
            print(f"[main] WARN provenance skipped: {type(e).__name__}: {e}")

        if not report.results:
            print(
                f"[main] ERROR: no (face, position, part) results discovered under {test_dir}. "
                f"Check that either F*/Run_*/analysis_result.json or "
                f"output/Run_*/Output/d3plot exists.",
                file=sys.stderr,
            )
            sys.exit(2)

    # Optional explicit unit-system override (highest priority).
    if args.units:
        preset = loader.get_unit_preset(args.units)
        if preset:
            report.sim_params["units"] = preset["id"]
            report.sim_params["unit_labels"] = preset["labels"]
            print(f"[main] --units override: {preset['id']} "
                  f"(acc={preset['labels']['acc']}, stress={preset['labels']['stress']})")

    # Optional face filter
    face_subset = _parse_face_list(args.faces)
    if face_subset:
        before = len(report.results)
        report.results = [r for r in report.results if r.face in face_subset]
        report.faces = [f for f in report.faces if f.code in face_subset]
        report.positions_by_face = {
            k: v for k, v in report.positions_by_face.items() if k in face_subset
        }
        print(f"[main] Face filter {face_subset}: {before} → {len(report.results)} pair results")

    # Yield-stress dispatch:
    #   • Per-part from the *MAT_ cards (already in sim_params) is preferred.
    #   • Global --yield-stress overrides every part if supplied.
    yield_by_part = dict(report.sim_params.get("yield_stress_by_part", {}) or {})
    if args.yield_stress is not None:
        for p in report.parts:
            yield_by_part[p.part_id] = float(args.yield_stress)

    # ── Analyze ───────────────────────────────────────────────────
    analyzer.analyze(
        report,
        threshold_critical=args.threshold_critical,
        threshold_warning=args.threshold_warning,
        yield_stress_by_part=yield_by_part or None,
    )

    # ── Output ────────────────────────────────────────────────────
    formats = set(args.format)

    if "terminal" in formats and print_report is not None:
        try:
            print_report(report)
        except Exception as e:  # noqa: BLE001
            print(f"[main] terminal output failed: {e}", file=sys.stderr)

    if "html" in formats:
        html_path = args.output or (
            str(Path(args.test_dir) / "report.html") if args.test_dir else "report.html"
        )
        print(f"[main] Generating HTML report: {html_path}")
        t0 = time.time()
        # 출력 모드: --single-file/--chunked 오버라이드 > tier 자동 (P4-3)
        _emit_mode = None
        if args.single_file:
            _emit_mode = "inline"
        elif args.chunked:
            _emit_mode = "chunked"
        try:
            from .report.emit import emit_report
            emit_report(report, html_path, mode=_emit_mode)
        except ImportError:
            Path(html_path).write_text(generate_html(report), encoding="utf-8")
        try:
            size_kb = Path(html_path).stat().st_size / 1024
        except OSError:
            size_kb = 0
        print(f"[main] HTML saved in {time.time() - t0:.1f}s ({size_kb:.0f} KB)")

    if "json" in formats and save_json is not None:
        json_path = args.json or (
            str(Path(args.test_dir) / "report.json") if args.test_dir else "report.json"
        )
        save_json(report, json_path)
        print(f"[main] JSON saved: {json_path}")

    print("[main] Done.")


if __name__ == "__main__":
    main()
