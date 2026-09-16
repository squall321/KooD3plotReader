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
    ap.add_argument("--coord-transform", action="store_true",
                    help="원본 모델(runner_config 의 model_file)과 런 덱을 노드 ID 로 "
                         "대응시켜 좌표 변환을 추정한다. 덩어리 중심을 도면 좌표로도 낸다")
    ap.add_argument("--segment-boxes", default=None, metavar="JSON",
                    help="파트 구간 정의. 군집 중심을 구간에 배정해 구간별 통계를 낸다 "
                         "(인터포저가 한 파트로 묶인 과제용)")
    ap.add_argument("--elout-check", action="store_true",
                    help="elout(촘촘한 요소 이력)과 견주어 d3plot 이 피크를 "
                         "놓쳤는지 확인한다 (*DATABASE_ELOUT 이 켜진 덱에서만)")
    args = ap.parse_args(argv)

    # elout 교차 확인은 클러스터 원형(peak_element_id)이 필요하다.
    # keep_clusters 를 안 켜면 순회할 항목이 없어 **아무 말 없이** 지나간다.
    tbl = collect_campaign(args.test_dir, part_ids=args.part,
                           keep_clusters=bool(args.elout_check or args.segment_boxes),
                           coord_transform=bool(args.coord_transform))

    if tbl.note:
        print(f"[campaign] {tbl.note}", file=sys.stderr)
    print(f"[campaign] 런 {tbl.n_runs}개, 줄 {len(tbl.rows)}개, "
          f"건너뜀 {len(tbl.skipped)}건")
    for name, why in tbl.skipped[:5]:
        print(f"           건너뜀 {name}: {why}", file=sys.stderr)
    if len(tbl.skipped) > 5:
        print(f"           … 외 {len(tbl.skipped) - 5}건", file=sys.stderr)

    # 🔴 읽은 런이 없으면 여기서 끝낸다. 계속 가면 -o 로 준 경로에 머리글만 있는
    #    빈 표를 써서, 기존 결과 파일을 **조용히 덮어쓴다** (경로를 잘못 줬을 때).
    if tbl.n_runs == 0:
        print("[campaign] 읽은 런이 없어 아무것도 저장하지 않습니다", file=sys.stderr)
        return 1

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
        if r[9]:
            runs_by_lat.setdefault(r[9], set()).add(r[0])
    n_noangle = sum(1 for r in tbl.runs if not r[9])
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
    n_hs = sum(1 for r in tbl.runs if r[11])
    if tbl.n_runs and not n_hs:
        print("[campaign] 핫스팟 군집이 있는 런이 없습니다 — "
              "unified_analyzer 를 --hotspot-clusters 로 돌리면 지표가 채워집니다",
              file=sys.stderr)

    # ── 좌표 변환 ──
    if args.coord_transform:
        _report_coord(tbl)

    # ── 구간별 통계 ──
    if args.segment_boxes:
        _segment_stats(args.segment_boxes, tbl)

    # ── elout 교차 확인 ──
    if args.elout_check:
        _elout_check(args.test_dir, tbl)

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


def _report_coord(tbl) -> None:
    """런별 좌표 변환을 묶어 보여 준다. 대부분 같으므로 서로 다른 것만 센다."""
    from .core.campaign_metrics import RUN_COLUMNS
    i0 = RUN_COLUMNS.index("ct_method")
    if tbl.coord_note:
        print(f"[campaign] 좌표 변환: {tbl.coord_note}", file=sys.stderr)
    if tbl.source_model:
        print(f"[campaign] 원본 모델: {tbl.source_model}")
    groups: dict = {}
    missing = 0
    worst_res = 0.0
    for r in tbl.runs:
        m, dx, dy, dz, rot, res, n = r[i0:i0 + 7]
        if m is None:
            missing += 1
            continue
        key = (m, round(dx, 4), round(dy, 4), round(dz, 4), round(rot or 0.0, 4))
        groups[key] = groups.get(key, 0) + 1
        worst_res = max(worst_res, res or 0.0)
    for (m, dx, dy, dz, rot), cnt in sorted(groups.items(), key=lambda kv: -kv[1]):
        print(f"[campaign] 좌표 변환 [{m}] 평행이동 ({dx:g}, {dy:g}, {dz:g}), "
              f"회전 {rot:g}° — {cnt}런")
    if groups:
        print(f"[campaign]   뜻: 결과 = R·도면 + t. 최대 잔차 {worst_res:.3g} "
              f"(덩어리 중심의 도면 좌표는 c1_center_src_x/y/z 지표로 실립니다)")
    if len(groups) > 1:
        print(f"[campaign] ⚠ 런마다 좌표 변환이 {len(groups)}가지입니다 — "
              f"도면과 비교할 때 런별 변환을 써야 합니다", file=sys.stderr)
    if tbl.coord_skipped_parts:
        print(f"[campaign] 원본 모델에 없는 파트 {sorted(tbl.coord_skipped_parts)} 는 "
              f"도면 좌표를 내지 않았습니다 (전처리가 붙인 바닥·벽 등)")
    if missing:
        print(f"[campaign] 좌표 변환을 구하지 못한 런 {missing}개 "
              f"(런 덱 DropSet.k 없음 또는 공통 노드 없음)", file=sys.stderr)


def _segment_stats(seg_path, tbl) -> None:
    """군집 중심을 구간에 배정해 구간별 최댓값을 낸다."""
    from .core.segment_boxes import load_segments

    ss = load_segments(seg_path)
    if not ss.segments:
        print(f"[campaign] 구간 정의를 쓸 수 없습니다 — {ss.note}", file=sys.stderr)
        return
    if ss.note:
        print(f"[campaign] 구간 정의 경고: {ss.note}", file=sys.stderr)

    best, cnt, unassigned = {}, {}, 0
    for it in (tbl.items or []):
        if ss.part_id is not None and it.get("part_id") != ss.part_id:
            continue
        for c in it.get("clusters") or []:
            ctr = c.get("center")
            v = c.get("stress_max")
            if not (isinstance(ctr, list) and len(ctr) == 3):
                continue
            nm = ss.assign(ctr)
            if nm is None:
                unassigned += 1
                continue
            cnt[nm] = cnt.get(nm, 0) + 1
            if isinstance(v, (int, float)):
                if nm not in best or v > best[nm]:
                    best[nm] = v
    if not cnt:
        print(f"[campaign] 구간에 배정된 군집이 없습니다 "
              f"(파트 {ss.part_id} 의 군집이 구간 밖입니다)", file=sys.stderr)
        return
    print(f"[campaign] 구간별 통계 (파트 {ss.part_id}):")
    for s_ in ss.segments:
        n = cnt.get(s_.name, 0)
        v = best.get(s_.name)
        # 배정이 없는 구간은 값을 지어내지 않는다
        print(f"             {s_.name:16s} 군집 {n:4d}개  최대 "
              + (f"{v:.6g}" if v is not None else "—"))
    if unassigned:
        print(f"             (어느 구간에도 없는 군집 {unassigned}개 — "
              f"구간이 파트를 다 덮는지 확인하세요)", file=sys.stderr)


def _elout_check(test_dir, tbl) -> None:
    """런별로 elout 과 d3plot 피크를 견준다. 없으면 없다고 말하고 끝낸다."""
    from pathlib import Path
    from .core.elout_peaks import read_elout, compare_peaks

    root = Path(test_dir)
    checked = missing = 0
    if not (tbl.items or []):
        print("[campaign] elout 확인: 군집 항목이 없습니다 "
              "(unified_analyzer --hotspot-clusters 로 돌린 산출물이 필요합니다)",
              file=sys.stderr)
        return
    for it in (tbl.items or []):
        run = it.get("run")
        # binout 은 output/<run>/ 아래에 있다 (binout0000, binout* 등)
        cands = sorted((root / "output" / str(run)).glob("binout*")) \
            if run else []
        if not cands:
            missing += 1
            continue
        ed = read_elout(cands[0])
        if not ed.ok:
            if missing == 0:      # 첫 번째만 사유를 보여 준다 (같은 이유가 반복된다)
                print(f"[campaign] elout 없음 — {ed.note}", file=sys.stderr)
            missing += 1
            continue
        # d3plot 피크: 덩어리의 peak_element_id / stress_max / peak_time
        d3 = {}
        for c in it.get("clusters") or []:
            eid = c.get("peak_element_id")
            v = c.get("stress_max")
            if isinstance(eid, int) and isinstance(v, (int, float)):
                d3[eid] = (float(v), c.get("peak_time"))
        if not d3:
            continue
        kind = {"solid": "solid", "shell": "shell",
                "thick_shell": "thick_shell"}.get(it.get("element_type"), "solid")
        cmp = compare_peaks(d3, ed, kind=kind)
        checked += 1
        if cmp.n_missed:
            print(f"[campaign] {run} part {it.get('part_id')}: {cmp.summary()}",
                  file=sys.stderr)
    if checked:
        print(f"[campaign] elout 교차 확인: {checked}개 항목")
    if missing:
        print(f"[campaign] elout 을 쓸 수 없는 항목 {missing}개 — "
              f"*DATABASE_ELOUT 을 켜면 d3plot 이 피크를 놓쳤는지 확인할 수 있습니다",
              file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
