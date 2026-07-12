# 파트간 에너지 흐름 엣지를 CSV 계약 파일로 출력 — DOE 상위 도구가 grep 가능하게
"""energy_flow_edges.csv writer.

deep single-sim 산출물에 파트간 접촉 에너지 전달을 한 줄=한 엣지로 기록한다.
build_flow_graph(공용 빌더)를 재사용하며, 의존성/데이터 부재는 조용히 skip
(빈 CSV 미생성) — 무회귀. impactor 개념이 없는 general sim 이라 impactor_pid=None.
"""
from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace


def write_energy_flow_csv(output_dir: Path, binout_data, keyword_path: Path | None,
                          d3plot_path: Path | None = None) -> Path | None:
    """energy_flow_edges.csv 를 output_dir 에 쓰고 경로 반환. 불가 시 None.

    binout_data = parse_binout 결과(BinoutData) 또는 None. matsum 없으면 skip.
    """
    if binout_data is None or getattr(binout_data, "matsum", None) is None:
        return None
    try:
        from .energy_flow_builder import build_flow_graph
    except Exception:
        return None

    # part_names: keyword 에서 (없으면 빈 dict → 빌더가 Part_<pid>)
    part_names: dict[int, str] = {}
    if keyword_path is not None or d3plot_path is not None:
        try:
            from .keyword_parser import find_and_parse_keyword
            kw = find_and_parse_keyword(keyword_path or d3plot_path)
            if kw and getattr(kw, "parts", None):
                part_names = {int(pid): p.name for pid, p in kw.parts.items()}
        except Exception:
            part_names = {}

    # contact_map: keyword 에서 (파트↔파트 실명 매핑; 없으면 pseudo 강등)
    contact_map = None
    if keyword_path is not None:
        try:
            from .contact_map import parse_contact_map
            contact_map = parse_contact_map(Path(keyword_path), part_names=part_names)
        except Exception:
            contact_map = None

    binout_obj = SimpleNamespace(
        matsum=binout_data.matsum,
        rcforc=getattr(binout_data, "rcforc", None) or [],
        glstat=getattr(binout_data, "glstat", None),
    )
    try:
        g = build_flow_graph(binout_obj, contact_map, part_names,
                             impactor_pid=None, max_pts=200)
    except Exception:
        return None
    if not g or not g.get("edges"):
        return None

    node_name = {n["node_id"]: n.get("name", n["node_id"]) for n in g.get("nodes", [])}
    csv_path = Path(output_dir) / "energy_flow_edges.csv"
    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["cid", "src_id", "src_name", "dst_id", "dst_name",
                        "name", "peak_force", "t_engage", "total_impulse",
                        "total_work", "confidence"])
            for e in g["edges"]:
                times = e.get("times") or []
                fe_idx = e.get("first_engage_idx")
                t_engage = ""
                if isinstance(fe_idx, int) and 0 <= fe_idx < len(times):
                    t_engage = times[fe_idx]
                w.writerow([
                    e.get("contact_id", -1),
                    e.get("src", ""), node_name.get(e.get("src", ""), e.get("src", "")),
                    e.get("dst", ""), node_name.get(e.get("dst", ""), e.get("dst", "")),
                    e.get("name", ""),
                    e.get("peak_force", 0.0),
                    t_engage,
                    e.get("total_impulse", 0.0),
                    e.get("total_work", 0.0),
                    e.get("confidence", 1.0),
                ])
    except OSError:
        return None
    return csv_path
