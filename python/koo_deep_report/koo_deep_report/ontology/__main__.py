# 리포트 산출물에서 온톨로지 꾸러미를 만드는 CLI (python3 -m koo_deep_report.ontology)
"""사용

    python3 -m koo_deep_report.ontology sphere <report.json> [-o OUT] [--test-dir DIR]
                                               [--yield-map FILE] [--yield-stress MPA]
    python3 -m koo_deep_report.ontology impact <impact_report.json> [-o OUT]
    python3 -m koo_deep_report.ontology vocab [OUT]

기본 출력은 입력 옆 `<이름>.ontology.json` (report.json → report.ontology.json).
종료 코드: 0 성공, 2 입력을 못 읽음, 1 꾸러미가 어휘와 안 맞음(만드는 쪽 결함).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import package as P
from . import vocabulary as V


def _load_json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        print(f"Error: {path} 를 읽지 못했습니다 ({type(e).__name__}: {e})", file=sys.stderr)
        sys.exit(2)
    if not isinstance(doc, dict):
        print(f"Error: {path} 의 최상위가 객체가 아닙니다", file=sys.stderr)
        sys.exit(2)
    return doc


def _emit(doc: dict, out: Path) -> None:
    P.write(doc, out)
    c = doc["counts"]
    n_o = sum(c["objects"].values())
    n_r = sum(c["relations"].values())
    kinds = ", ".join(f"{k.removeprefix('cae_')} {v}" for k, v in c["objects"].items())
    print(f"온톨로지 꾸러미: {out} — 객체 {n_o} ({kinds}), 관계 {n_r}, "
          f"단위 {doc['units']['system']}{'' if doc['units']['normalized'] else ' (원값)'}, "
          f"{out.stat().st_size / 1e6:.1f} MB")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m koo_deep_report.ontology",
                                 description="후처리 결과 → DynaForge 온톨로지 꾸러미")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sphere", help="전각도 낙하 report.json")
    s.add_argument("report_json")
    s.add_argument("-o", "--output", default="")
    s.add_argument("--test-dir", default="", help="캠페인 폴더(생략하면 report.json 의 test_dir)")
    s.add_argument("--yield-map", default="", help="리포트에 준 것과 같은 파트별 항복 맵(덱 단위)")
    s.add_argument("--yield-stress", type=float, default=0.0, help="리포트에 준 것과 같은 기본 항복응력(MPa)")

    i = sub.add_parser("impact", help="전위치 부분충격 report json (옆의 impact_payload.json 도 읽는다)")
    i.add_argument("report_json")
    i.add_argument("-o", "--output", default="")

    v = sub.add_parser("vocab", help="어휘 JSON 을 쓴다(인자 없으면 표준출력)")
    v.add_argument("out", nargs="?", default="")

    a = ap.parse_args(argv)

    if a.cmd == "vocab":
        if a.out:
            Path(a.out).write_text(V.dumps(), encoding="utf-8")
        else:
            sys.stdout.write(V.dumps())
        return 0

    src = Path(a.report_json)
    out = Path(a.output) if a.output else src.with_name(src.stem + ".ontology.json")
    try:
        if a.cmd == "sphere":
            from . import sphere
            doc = sphere.build(_load_json(src), report_path=src,
                               test_dir=Path(a.test_dir) if a.test_dir else None,
                               yield_map_path=a.yield_map, yield_stress=a.yield_stress)
        elif a.cmd == "impact":
            from . import impact
            doc = impact.build(_load_json(src), report_path=src)
    except P.PackageError as e:
        print(f"Error: {e}", file=sys.stderr)
        for f in e.faults[:40]:
            print(f"  - {f}", file=sys.stderr)
        return 1
    _emit(doc, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
