# 캠페인 롱포맷 테이블을 만들고 각도·빌드 건전성을 점검하는 명령줄 도구
"""캠페인 지표 수집 CLI.

    python3 -m koo_deep_report.campaign_cli <test_dir> -o metrics.tsv
    python3 -m koo_deep_report.campaign_cli <test_dir> --part 15 --part 21
    python3 -m koo_deep_report.campaign_cli <test_dir> --check-only

`analysis_results/Run_*/analysis_result.json` 를 한 번 훑어 롱포맷 TSV 로 만든다.
20MB × N 을 매번 다시 파싱하지 않아도 되게 하는 것이 목적이다.

함께 점검하는 것 (결과만 봐서는 알 수 없는 것들).
- 런마다 **다른 빌드**로 분석됐는가 (그러면 차이가 모델 탓인지 도구 탓인지 모른다)
- 26방향 DOE 의 각도가 **격자에 맞는가** (코너 각도 결함이 있던 도구로 만든
  캠페인은 꼭짓점이 9.74° 벗어난다)
"""

from __future__ import annotations

import argparse
import collections
import sys

from .core.campaign_metrics import collect_campaign


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="koo_deep_report.campaign_cli",
        description="캠페인 런들의 지표를 롱포맷 TSV 한 장으로 모은다")
    ap.add_argument("test_dir", help="analysis_results/ 를 가진 캠페인 폴더")
    ap.add_argument("-o", "--output", default=None,
                    help="TSV 출력 경로 (생략하면 저장하지 않고 요약만)")
    ap.add_argument("--part", action="append", default=None, metavar="PID",
                    help="이 파트만 (여러 번 지정 가능)")
    ap.add_argument("--check-only", action="store_true",
                    help="건전성 점검만 하고 표를 만들지 않는다")
    args = ap.parse_args(argv)

    tbl = collect_campaign(args.test_dir, part_ids=args.part)

    if tbl.note:
        print(f"[campaign] {tbl.note}", file=sys.stderr)
    print(f"[campaign] 런 {tbl.n_runs}개, 줄 {len(tbl.rows)}개, "
          f"건너뜀 {len(tbl.skipped)}건")
    for name, why in tbl.skipped[:5]:
        print(f"           건너뜀 {name}: {why}", file=sys.stderr)
    if len(tbl.skipped) > 5:
        print(f"           … 외 {len(tbl.skipped) - 5}건", file=sys.stderr)

    # ── 빌드 혼재 ──
    if len(tbl.tool_builds) > 1:
        detail = ", ".join(f"{k}({v}런)" for k, v in sorted(tbl.tool_builds.items()))
        print(f"[campaign] ⚠ 런마다 분석 빌드가 다릅니다 — {detail}", file=sys.stderr)
        print("           결과 차이가 모델 탓인지 도구 탓인지 구분할 수 없습니다.",
              file=sys.stderr)
    elif tbl.tool_builds:
        print(f"[campaign] 분석 빌드: {next(iter(tbl.tool_builds))}")
    n_unknown = tbl.n_runs - sum(tbl.tool_builds.values())
    if n_unknown > 0:
        print(f"[campaign] ⚠ 빌드 기록이 없는 런 {n_unknown}개 "
              f"(2026-09-13 이전 산출물)", file=sys.stderr)

    # ── 각도 격자 ──
    # 🔴 `rows`(군집 줄)가 아니라 `runs` 를 본다. 핫스팟을 안 돌린 캠페인은
    #    군집 줄이 0 개라, rows 로 점검하면 각도 건전성을 아예 못 본다.
    runs_by_lat = {}
    for r in tbl.runs:
        if r[6]:
            runs_by_lat.setdefault(r[6], set()).add(r[0])
    n_noangle = sum(1 for r in tbl.runs if not r[6])
    if runs_by_lat:
        print("[campaign] 각도 격자: " +
              ", ".join(f"{k} {len(v)}런" for k, v in sorted(runs_by_lat.items())))
        off = runs_by_lat.get("off_lattice")
        if off:
            print(f"[campaign] ⚠ 26방향 격자에서 벗어난 런 {len(off)}개 — "
                  f"코너 각도 결함이 있던 도구로 만든 캠페인일 수 있습니다.",
                  file=sys.stderr)

    if n_noangle:
        print(f"[campaign] 각도를 읽지 못한 런 {n_noangle}개 "
              f"(output/<run>/DropSet.json 확인)", file=sys.stderr)
    n_hs = sum(1 for r in tbl.runs if r[8])
    if tbl.n_runs and not n_hs:
        print("[campaign] 핫스팟 군집이 있는 런이 없습니다 — "
              "unified_analyzer 를 --hotspot-clusters 로 돌리면 지표가 채워집니다",
              file=sys.stderr)

    if args.check_only:
        return 0 if tbl.n_runs else 1

    if args.output:
        err = tbl.to_tsv(args.output)
        if err:
            print(f"[campaign] {err}", file=sys.stderr)
            return 2
        print(f"[campaign] 저장: {args.output}")
        run_out = str(args.output)
        run_out = (run_out[:-4] if run_out.endswith(".tsv") else run_out) + "_runs.tsv"
        err = tbl.runs_to_tsv(run_out)
        if err:
            print(f"[campaign] {err}", file=sys.stderr)
        else:
            print(f"[campaign] 런 표 저장: {run_out}")
    else:
        mets = collections.Counter(r[10] for r in tbl.rows)
        print("[campaign] 지표별 줄 수:")
        for k, v in sorted(mets.items()):
            print(f"             {k:24s} {v}")
        print("[campaign] -o 로 TSV 경로를 주면 저장합니다.")
    return 0 if tbl.n_runs else 1


if __name__ == "__main__":
    sys.exit(main())
