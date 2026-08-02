# CLI — python -m koo_federate_report --config federate.yaml [--output X]
"""연합 비교 CLI.

HTML 보고서 모듈(report/html_report.py)이 아직 없거나 import 에 실패하면
비교 payload 를 JSON 으로 덤프하고 콘솔 요약만 출력한다 (엔진만으로도 사용 가능).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import federate
from .adapters import AdapterError
from .compare import CompareError
from .config import ConfigError, load_config
from .matching import MatchingError
from .models import METRIC_KEYS


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m koo_federate_report",
        description="N개 리비전 sidecar(impact/sphere)를 하나의 비교 보고서로 연합",
    )
    p.add_argument("--config", required=True, help="federate.yaml 경로")
    p.add_argument("--output", help="출력 HTML 경로 (YAML 의 output 을 덮어씀)")
    p.add_argument("--json", dest="json_path", help="비교 payload JSON 덤프 경로")
    p.add_argument(
        "--metric",
        default="g",
        choices=list(METRIC_KEYS),
        help="비교 주 지표 (g=peak acc, s=stress, e=strain, d=disp). 기본 g",
    )
    p.add_argument("--quiet", action="store_true", help="콘솔 요약 생략")
    return p


def _fmt(v, digits=4):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{digits}g}"
    return str(v)


def print_summary(cmp_dict: dict, out=sys.stdout) -> None:
    kpi = cmp_dict["kpi"]
    w = out.write
    w("\n=== FEDERATE 비교 요약 ===\n")
    w(f"종류: {cmp_dict['kind']} / 주 지표: {kpi['metric']} ({kpi['metric_label']})\n")
    w(f"기준 리비전: {kpi['baseline_label']} (1-based {cmp_dict['baseline_idx'] + 1})\n")
    for r in cmp_dict["revisions"]:
        mark = " *baseline" if r["is_baseline"] else ""
        w(
            f"  [{r['index'] + 1}] {r['label']}{mark} — cells={r['n_cells']} "
            f"parts={r['n_parts']} 미매칭={len(r['unmatched_parts'])}\n"
        )
    cov = cmp_dict.get("coverage") or {}
    w(
        f"공통 격자: {cov.get('n_grid')}개 (모드 {cov.get('mode')} → "
        f"{cov.get('mode_effective')}, 출처 {cov.get('grid_source')})\n"
    )
    for row in cov.get("per_rev") or []:
        w(
            f"  - {row['label']}: 실측 {row['exact']} / 최근접 {row['nearest']} / "
            f"보간 {row['idw']} / 없음 {row['missing']} (커버리지 {row['coverage_pct']}%)\n"
        )
    w(
        f"Δ 판정 가능 셀: {kpi['n_comparable']}/{kpi['n_cells']} "
        f"({kpi['comparable_pct']}%), 미판정 {kpi['n_gated']} "
        f"[trust_gate={kpi['trust_gate']}]\n"
    )
    w(
        f"파트: canonical {kpi['n_parts_canonical']}개 (2개 이상 리비전 매칭 "
        f"{kpi['n_parts_matched']}개), 리비전별 미매칭 {kpi['n_parts_unmatched']}\n"
    )
    w("리비전별 worst: " + ", ".join(_fmt(v) for v in kpi["worst_per_rev"]) + "\n")

    bt = cmp_dict.get("behavior_transitions")
    if bt:
        w(f"behavior 전이: 변화 셀 {bt['n_changed_cells']}개 (headline={bt['headline']})\n")
        for row in bt["per_rev"]:
            if row["n_changed"]:
                trs = ", ".join(
                    f"{e['from']}→{e['to']}×{e['count']}" for e in row["entries"] if e["changed"]
                )
                w(f"  - {row['label']}: {trs}\n")

    for fd in cmp_dict.get("findings_diff") or []:
        if fd["is_baseline"]:
            continue
        w(
            f"findings diff [{fd['label']}]: 신규 {len(fd['new'])} / 해소 "
            f"{len(fd['resolved'])} / 유지 {len(fd['kept'])}\n"
        )

    warns = cmp_dict.get("warnings") or []
    if warns:
        w(f"경고 {len(warns)}건:\n")
        for wr in warns:
            w(f"  [{wr.get('severity')}] {wr.get('code')}: {wr.get('message')}\n")
    w("\n")


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
        if args.output:
            cfg.output = os.path.abspath(args.output)
        comparison = federate(cfg, metric=args.metric)
    except (ConfigError, AdapterError, MatchingError, CompareError) as exc:
        print(f"[federate] 오류: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print_summary(comparison)

    out_dir = os.path.dirname(os.path.abspath(cfg.output)) or "."
    os.makedirs(out_dir, exist_ok=True)

    # HTML 렌더보다 payload 덤프를 먼저 한다 — 렌더가 실패해도 비교 결과는 남는다.
    report_mod = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report", "html_report.py")
    has_html = os.path.isfile(report_mod)
    json_path = args.json_path or (None if has_html else os.path.join(out_dir, "federate_payload.json"))
    if json_path:
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(comparison, fh, ensure_ascii=False, indent=2)
        print(f"[federate] payload: {json_path}")

    # F5(HTML) 모듈이 있으면 쓴다. 있는데 깨진 경우는 삼키지 않는다 (무음 실패 금지).
    if not has_html:
        print("[federate] HTML 보고서 모듈(report/html_report.py)이 없어 payload JSON 만 출력합니다")
        return 0

    from .report.html_report import generate_html  # type: ignore

    with open(cfg.output, "w", encoding="utf-8") as fh:
        fh.write(generate_html(comparison))
    print(f"[federate] HTML: {cfg.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
