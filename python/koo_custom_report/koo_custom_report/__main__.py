# Custom Report CLI — d3plot + 세트설정 YAML 을 받아 분석·렌더·HTML 까지 한 번에
"""사용법.

    python3 -m koo_custom_report <d3plot 경로> --config custom.yaml [-o 출력폴더]

custom.yaml 예:

    sets:
      file: "sets.k"          # 생략 시 d3plot 옆 .k 자동 탐색
    set_reports:
      - name: "PKG 모듈"
        set_type: part        # part | node | segment
        set_id: 5
        fields: [von_mises, eff_plastic_strain]
        planes: [xy, yz, zx]
        video: true
        peak_snapshot: true
        max_frames: 60        # 0 = 전 상태

산출물: <out>/custom_report.html + <out>/set_reports/<세트>/...
KooChainRun per-run 관례: -o 를 Run_*/Output/report 로 주면 deep 산출물과
같은 폴더 계층에 실린다 (set_reports/ 는 deep 의 renders/ 스캔 밖이라 충돌 없음).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .runner import CustomReportConfig, SetSpec, find_unified_analyzer, load_config, run
from .report.html_report import build_html


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="koo_custom_report",
        description="LS-DYNA *SET_ 정의 기반 커스텀 후처리 보고서")
    ap.add_argument("d3plot", help="d3plot 파일 경로 (또는 run 디렉터리)")
    ap.add_argument("--config", "-c", help="sets/set_reports 설정 YAML")
    ap.add_argument("--sets", help="세트 파일 (.k) — --config 없이 빠르게 쓸 때")
    ap.add_argument("--part-set", type=int, action="append", default=[],
                    help="파트셋 SID (반복 가능) — --config 없이 빠르게 쓸 때")
    ap.add_argument("--output", "-o", help="출력 폴더 (기본: <d3plot 폴더>/custom_report)")
    ap.add_argument("--max-frames", type=int, default=0,
                    help="영상 프레임 다운샘플 (0=전 상태)")
    ap.add_argument("--ua", help="unified_analyzer 경로 (기본: 자동 탐색)")
    ap.add_argument("--no-html", action="store_true", help="분석·렌더만, HTML 생략")
    args = ap.parse_args(argv)

    d3plot = Path(args.d3plot)
    if d3plot.is_dir():
        cand = d3plot / "d3plot"
        if not cand.is_file():
            print(f"디렉터리에 d3plot 이 없음: {d3plot}", file=sys.stderr)
            return 2
        d3plot = cand

    # ---- 설정 ----
    if args.config:
        cfg = load_config(args.config)
    else:
        cfg = CustomReportConfig()
    if args.sets:
        cfg.sets_file = args.sets
    for sid in args.part_set:
        cfg.set_reports.append(SetSpec(name=f"part_set_{sid}", set_type="part",
                                       set_id=sid, max_frames=args.max_frames))
    if args.max_frames and args.config:
        for s in cfg.set_reports:
            if s.max_frames == 0:
                s.max_frames = args.max_frames

    if not cfg.set_reports:
        print("set_reports 가 비어 있음 — --config 또는 --part-set 필요", file=sys.stderr)
        return 2

    out_dir = Path(args.output) if args.output else d3plot.parent / "custom_report"

    ua = args.ua or find_unified_analyzer()
    if not ua:
        print("unified_analyzer 를 찾지 못함 (KOOD3PLOT_HOME 또는 --ua)", file=sys.stderr)
        return 2

    print(f"[custom_report] d3plot: {d3plot}")
    print(f"[custom_report] 출력  : {out_dir}")
    print(f"[custom_report] 세트  : {len(cfg.set_reports)}개")

    result = run(d3plot, out_dir, cfg, ua_path=ua)
    if not result.ok:
        print(f"[custom_report] 실패: {result.error}", file=sys.stderr)
        if result.ua_log_tail:
            print(result.ua_log_tail, file=sys.stderr)
        return 1

    for sr in result.sets:
        n_media = len(sr.media)
        notes = len(sr.metrics.get("notes") or [])
        print(f"  [{sr.name}] 미디어 {n_media}개"
              + (f", 경고 {notes}건" if notes else ""))

    if not args.no_html:
        html_path = build_html(result, str(d3plot), Path(out_dir) / "custom_report.html")
        print(f"[custom_report] HTML: {html_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
