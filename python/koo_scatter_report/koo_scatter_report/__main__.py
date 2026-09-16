# 각도 산포 캠페인 보고서를 만드는 명령줄 도구
"""koo_scatter_report CLI.

    python3 -m koo_scatter_report <test_dir> -o report.html
    python3 -m koo_scatter_report <test_dir> --part 15 --criterion max_principal
    python3 -m koo_scatter_report <test_dir> --ground-truth ng.tsv --segments seg.json

캠페인(여러 각도 런)을 가로로 묶어 편차각 산포·방향도·히트맵·회수율·리스크맵을
한 장으로 낸다. 그림은 외부 라이브러리 없이 SVG 로 그린다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loader import load
from .report.html_report import build_html


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="koo_scatter_report",
        description="각도 산포 캠페인 보고서 (편차각 산포·방향도·회수율)")
    ap.add_argument("test_dir", help="analysis_results/ 를 가진 캠페인 폴더")
    ap.add_argument("-o", "--output", default=None, help="HTML 출력 경로")
    ap.add_argument("--part", type=int, default=None, help="이 파트만 (생략하면 전부)")
    ap.add_argument("--criterion", default="von_mises",
                    help="기준량 (기본 von_mises)")
    ap.add_argument("--metric", default="c1_stress_max",
                    help="지표 (기본 c1_stress_max). 파트 절대량은 n_yield/vol_yield 등")
    ap.add_argument("--ground-truth", default=None, metavar="TSV",
                    help="시험 불량 데이터 (회수율 계산에 필요)")
    ap.add_argument("--segments", default=None, metavar="JSON",
                    help="파트 구간 정의 (구간도에 필요)")
    ap.add_argument("--title", default="각도 산포 리포트")
    args = ap.parse_args(argv)

    si = load(args.test_dir,
              part_ids=[args.part] if args.part is not None else None,
              gt_path=args.ground_truth, segments_path=args.segments)
    if not si.ok:
        print(f"[scatter] {si.note}", file=sys.stderr)
        return 1
    if si.note:
        print(f"[scatter] {si.note}", file=sys.stderr)

    tbl = si.table
    print(f"[scatter] 런 {tbl.n_runs}개, 지표 줄 {len(tbl.rows)}개, "
          f"군집 항목 {len(tbl.items)}개")

    # 요청한 기준량·지표가 실제로 있는지 먼저 말한다 — 빈 그림을 내밀지 않는다
    crits = sorted({r[9] for r in tbl.rows if r[9]})
    mets = sorted({r[10] for r in tbl.rows if r[10]})
    if args.criterion not in crits:
        print(f"[scatter] ⚠ 기준량 '{args.criterion}' 가 이 캠페인에 없습니다. "
              f"있는 것: {', '.join(crits) or '없음'}", file=sys.stderr)
    if args.metric not in mets:
        print(f"[scatter] ⚠ 지표 '{args.metric}' 가 이 캠페인에 없습니다. "
              f"있는 것: {', '.join(mets) or '없음'}", file=sys.stderr)

    html = build_html(si, args.criterion, args.metric, args.part, args.title)

    out = args.output
    if not out:
        print("[scatter] -o 로 출력 경로를 주면 저장합니다.")
        return 0
    try:
        p = Path(out)
        if str(p.parent):
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
    except OSError as e:
        print(f"[scatter] 저장 실패 ({type(e).__name__}: {e})", file=sys.stderr)
        return 2
    print(f"[scatter] 저장: {out} ({len(html) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
