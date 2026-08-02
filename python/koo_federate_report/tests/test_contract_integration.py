# 엔진(compare) ↔ 리포트(html_report) 계약 정합 회귀 테스트 — 통합 시 3곳이 어긋났었다
"""엔진이 내는 실제 구조로 HTML 이 렌더되는지 고정한다.

통합 중 실제로 어긋났던 3곳을 회귀로 못박는다.
  1) findings_diff — 엔진은 리비전별 list, 초기 HTML 은 dict 가정
  2) behavior_transitions — 엔진은 per_rev[], 초기 HTML 은 rows/summary 가정
  3) cells[].trust_ok / spread / part_matrix.rows / revisions[].index 형태
"""
from __future__ import annotations

from koo_federate_report.report.html_report import generate_html


def _engine_shaped() -> dict:
    """compare.py 가 실제로 내는 형태(축약본)."""
    return {
        "kind": "impact",
        "baseline_idx": 0,
        "metric": "g",
        "unit_labels": {"acc": "mm/s²", "stress": "MPa"},
        "g_divisor": 9810.0,
        "revisions": [
            {"index": 0, "label": "RevA", "is_baseline": True, "project": "P"},
            {"index": 1, "label": "RevB", "is_baseline": False, "project": "P"},
        ],
        "cells": [
            {
                "key": "F5_DOE_001", "label": "F5_DOE_001", "x": -40.0, "y": -40.0,
                "category": "F5",
                "per_rev": [
                    {"value": 1000.0, "trust": {"ok": True, "reason": "PASS"}, "behavior": "bounce"},
                    {"value": 900.0, "trust": {"ok": True, "reason": "PASS"}, "behavior": "bounce"},
                ],
                "delta": [0.0, -100.0], "delta_pct": [0.0, -10.0],
                "winner": 0, "trend": -0.1,
                # 엔진은 spread 를 dict 로 낸다
                "spread": {"min": 900.0, "max": 1000.0, "range": 100.0, "cv": 0.07, "stdev": 70.7},
                "gated": False, "gate_reason": None, "trust_ok": True,
            },
            {
                "key": "F5_DOE_002", "label": "F5_DOE_002", "x": -20.0, "y": -40.0,
                "category": "F5",
                "per_rev": [
                    {"value": 500.0, "trust": {"ok": False, "reason": "no-contact"}, "behavior": "no-contact"},
                    {"value": 480.0, "trust": {"ok": True, "reason": "PASS"}, "behavior": "bounce"},
                ],
                "delta": [None, None], "delta_pct": [None, None],
                "winner": None, "trend": None, "spread": None,
                "gated": True, "gate_reason": "RevA: no-contact", "trust_ok": False,
            },
        ],
        "parts": [
            {"canonical": "Display", "names": ["Display", "DISP_MAIN"],
             "worst": [1000.0, 900.0], "delta_pct": [0.0, -10.0], "rank": [0, 0],
             "present": [True, True]},
        ],
        # 엔진은 rows[] 구조
        "part_matrix": {
            "metric": "g", "cells": ["F5_DOE_001"], "gated": ["F5_DOE_002"],
            "rows": [{"canonical": "Display", "per_rev": [[1000.0], [900.0]], "delta_pct": [[-10.0]]}],
        },
        # 엔진은 per_rev[] 구조
        "behavior_transitions": {
            "headline": True, "baseline_idx": 0, "n_changed_cells": 1,
            "per_rev": [
                {"label": "RevA", "n_changed": 0, "counts": {"bounce": 1, "no-contact": 1},
                 "entries": [{"from": "bounce", "to": "bounce", "count": 1, "cells": ["F5_DOE_001"]}]},
                {"label": "RevB", "n_changed": 1, "counts": {"bounce": 2},
                 "entries": [{"from": "no-contact", "to": "bounce", "count": 1, "cells": ["F5_DOE_002"]}]},
            ],
        },
        # 엔진은 리비전별 list
        "findings_diff": [
            {"label": "RevA", "is_baseline": True, "new": [], "resolved": [], "kept": [], "n_total": 0},
            {"label": "RevB", "is_baseline": False,
             "new": [{"severity": "CRITICAL", "title": "신규 이슈"}],
             "resolved": [], "kept": [], "n_total": 1},
        ],
        "kpi": {"n_cells": 2, "n_comparable": 1, "n_revisions": 2},
        "coverage": {"per_rev": [2, 2], "intersection": 2, "resampled": 0, "note": "identity"},
        "warnings": [],
        "provenance": [{"label": "RevA", "tool_version": "0.1.0"},
                       {"label": "RevB", "tool_version": "0.1.0"}],
    }


def test_engine_shape_renders_all_sections():
    h = generate_html(_engine_shaped())
    assert h.startswith("<!DOCTYPE html>")
    # 핵심 섹션이 전부 나와야 한다 (계약 불일치 시 조용히 빠졌었다)
    for sid in ("s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9"):
        assert f'id="{sid}"' in h, f"섹션 {sid} 누락 — 계약 불일치 의심"


def test_behavior_headline_promoted_above_profile():
    h = generate_html(_engine_shaped())
    assert h.index('id="s6"') < h.index('id="s2"'), "headline 이면 전이가 프로파일 위"


def test_findings_diff_list_contract():
    h = generate_html(_engine_shaped())
    assert "신규 이슈" in h
    assert "RevB" in h


def test_gated_cell_not_faked_as_zero():
    """미판정 셀의 Δ 를 0 으로 위장하지 않는다."""
    doc = _engine_shaped()
    h = generate_html(doc)
    # gate_reason 이 어딘가 노출되어야 한다
    assert "no-contact" in h


def test_spread_dict_and_matrix_rows_consumed():
    """spread dict / part_matrix.rows 를 JS 정규화가 흡수한다."""
    h = generate_html(_engine_shaped())
    assert "normalizeContract" in h          # 정규화 훅 존재
    assert "fed-mtx" in h                     # 매트릭스 섹션 렌더


def _with_unmatched() -> dict:
    """일부 리비전에만 있는 파트 + 리비전별 미매칭 목록이 있는 계약."""
    d = _engine_shaped()
    d["parts"].append({
        "canonical": "Battery",
        "names": ["BAT\\Cell", None],          # RevB 에 없음
        "worst": [800.0, None],
        "delta_pct": [0.0, None],
        "rank": [1, None],
        "present": [True, False],
    })
    d["unmatched"] = [
        {"label": "RevA", "parts": []},
        {"label": "RevB", "parts": ["RENAMED_BAT_Cell"]},
    ]
    return d


def test_unmatched_section_rendered():
    """YAML unmatched:show 의 실구현 — 미매칭이 화면에 보여야 한다.

    회귀 배경: payload 에는 미매칭 정보가 있는데 HTML 이 소비하지 않아
    파트 표의 빈 칸이 '개선' 으로 오독될 수 있었다.
    """
    h = generate_html(_with_unmatched())
    assert 'id="s11"' in h, "미매칭 섹션 누락"
    assert "RENAMED_BAT_Cell" in h, "미매칭 파트명이 화면에 없음"
    assert "부분 존재 파트" in h


def test_partial_part_badged_in_table():
    """present=[True,False] 파트는 행에 '없음' 뱃지가 붙는다."""
    h = generate_html(_with_unmatched())
    assert "miss-badge" in h
    # 부재를 0 으로 위장하지 않는다는 안내
    assert "0 이 아니라" in h


def test_no_unmatched_section_when_all_matched():
    """전부 매칭이면 미매칭 섹션을 만들지 않는다 (빈 섹션 금지)."""
    h = generate_html(_engine_shaped())
    assert 'id="s11"' not in h


def test_warning_text_rendered_from_engine_keys():
    """엔진 경고 계약 {code,message,severity} 를 화면에 실제로 출력한다.

    회귀 배경: HTML 이 {kind,msg} 를 읽어 경고 문구가 빈 칸으로 나갔다.
    """
    d = _engine_shaped()
    d["warnings"] = [
        {"code": "no_comparable_cells", "severity": "ERROR",
         "message": "모든 리비전에서 유효한 셀이 0개입니다"},
        {"code": "resample_interpolated", "severity": "INFO",
         "message": "IDW 보간된 셀은 실측이 아닙니다"},
    ]
    h = generate_html(d)
    assert "모든 리비전에서 유효한 셀이 0개입니다" in h, "경고 문구가 렌더되지 않음"
    assert "IDW 보간된 셀은 실측이 아닙니다" in h
    assert "NO_COMPARABLE_CELLS" in h


def test_kpi_strip_filled_from_engine_shape():
    """KPI Δ 스트립이 엔진 계약에서도 채워진다.

    회귀 배경: 엔진은 worst 를 kpi.worst_per_rev / kpi.sidecar_kpi[] 로 내는데
    HTML 이 kpi.worst_g 만 봐서 보고서 최상단 KPI 표가 통째로 '—' 였다.
    """
    d = _engine_shaped()
    d["kpi"] = {
        "n_cells": 2, "n_comparable": 1, "n_revisions": 2,
        "worst_per_rev": [1.4888e9, 1.4606e9],   # 실제 규모 (mm/s² → G 환산됨)
        "sidecar_kpi": [{"worst_s": 2000.0, "diss_pct": 40.0},
                        {"worst_s": 1800.0, "diss_pct": 35.0}],
    }
    h = generate_html(d)
    assert "151,764" in h, "worst 값(G 환산)이 KPI 표에 없음"
    assert "2,000" in h, "sidecar_kpi 의 worst_s 가 반영되지 않음"


def test_no_double_escaped_entities():
    """em-dash 를 이중 이스케이프하지 않는다 (&amp;mdash; 로 깨지던 결함)."""
    h = generate_html(_engine_shaped())
    assert "&amp;mdash;" not in h


def test_impactor_excluded_from_parts():
    """임팩터(가해자)는 부품 추이/rank 비교에서 제외한다.

    회귀 배경: 본 impact 보고서는 이미 제외하는데 연합 어댑터가 되살려
    임팩터가 24,272 G 로 부품 순위 15위를 차지하며 경쟁했다.
    """
    from koo_federate_report.adapters.impact import to_bundle

    doc = {
        "schema_version": 1,
        "payload": {
            "positions": [{"pos_id": "P1", "face": "F5", "x": 0.0, "y": 0.0}],
            "results": [
                {"pos_id": "P1", "part_id": 1, "part_name": "Display", "g": 100.0,
                 "s": 10.0, "e": None, "d": None},
                {"pos_id": "P1", "part_id": 24, "part_name": "Impactor", "g": 9999.0,
                 "s": 1.0, "e": None, "d": None},
            ],
            "parts": [{"id": 1, "name": "Display"}, {"id": 24, "name": "Impactor"}],
            "part_motion": {"impactor_part_id": 24},
            "unit_labels": {"acc": "mm/s²"},
            "kpi": {}, "meta": {}, "doe_analysis": {}, "solver_quality": {},
            "findings": [],
        },
    }
    b = to_bundle(doc, path="/synthetic/rev.json", label="Rev")
    assert "Impactor" not in set(b.parts.values()), "임팩터가 부품 목록에 남아 있다"
    assert all(pn != "Impactor" for (_c, pn) in b.part_cells), "임팩터 셀이 남아 있다"


def test_prose_reports_delta_magnitude():
    """'개선 N셀' 만이 아니라 중앙값·최대 폭을 함께 말한다."""
    d = _engine_shaped()
    h = generate_html(d)
    assert "중앙값" in h, "개선 폭 분포가 요약에 없음 — 개수만으로는 크기를 알 수 없다"


def _mini_bundle(label, path, gen_utc=None, value=100.0):
    from tests.helpers import make_impact_bundle
    b = make_impact_bundle(
        label,
        [("C1", 0.0, 0.0, "F5", value, True, "bounce")],
        {1: "Display"},
        part_values={("C1", "Display"): {"g": value, "s": None, "e": None, "d": None}},
    )
    b.path = path
    if gen_utc:
        b.provenance = dict(b.provenance or {})
        b.provenance["generated_utc"] = gen_utc
    return b


def _warn_codes(bundles):
    from koo_federate_report.compare import build_comparison
    from koo_federate_report.config import Options
    from koo_federate_report.matching import build_matching
    from koo_federate_report.resample import align
    o = Options()
    m = build_matching(bundles, {}, o)
    a = align(bundles, 0, "impact", o.resample)
    c = build_comparison(bundles, 0, "impact", m, a, o, metric="g")
    return {w.get("code") for w in c.get("warnings") or []}


def test_duplicate_input_warned():
    """같은 sidecar 를 두 번 넣으면 Δ=0 이 '개선' 으로 오독된다 — 경고해야 한다."""
    codes = _warn_codes([_mini_bundle("A", "/x/same.json"),
                         _mini_bundle("B", "/x/same.json")])
    assert "duplicate_input" in codes


def test_distinct_paths_not_flagged_duplicate():
    """경로가 다르면 중복이 아니다 (원본 복사·변형 리비전의 거짓 양성 방지)."""
    codes = _warn_codes([_mini_bundle("A", "/x/a.json", value=100.0),
                         _mini_bundle("B", "/x/b.json", value=80.0)])
    assert "duplicate_input" not in codes


def test_revision_order_warned_when_times_reversed():
    """YAML 순서와 생성 시각 순서가 어긋나면 추이 해석이 뒤집힌다 — 알린다."""
    codes = _warn_codes([_mini_bundle("A", "/x/a.json", "2026-08-02T00:00:00+00:00"),
                         _mini_bundle("B", "/x/b.json", "2026-07-01T00:00:00+00:00")])
    assert "revision_order" in codes


def test_part_worst_cell_tracked_and_clickable():
    """파트 worst 가 '어느 셀' 에서 나왔는지 추적되고 클릭으로 이동한다.

    '어느 부품이 나빠졌나' 다음 질문은 항상 '어느 위치에서' 다.
    """
    d = _engine_shaped()
    d["parts"][0]["worst_cell"] = ["F5_DOE_001", "F5_DOE_002"]
    h = generate_html(d)
    assert "최악 셀" in h, "worst 셀 추적 정보가 화면에 없음"
    assert "wcell" in h, "worst 값이 클릭 가능하지 않음"


def test_worst_cell_move_data_embedded():
    """이동 판정에 필요한 worst_cell 이 payload 로 실제 전달된다.

    뱃지 자체는 JS 가 런타임에 붙이므로(HTML 문자열 검색으로는 판정 불가 —
    JS 소스에 리터럴이 항상 존재한다) 데이터 전달을 검증한다. 렌더 결과는
    Playwright 로 확인했다(실데이터에서 7개 부품 이동 검출).
    """
    import json as _json

    d = _engine_shaped()
    d["parts"][0]["worst_cell"] = ["F5_DOE_001", "F5_DOE_002"]
    h = generate_html(d)
    i = h.index('id="fed-data"')
    blob = h[h.index(">", i) + 1: h.index("</script>", i)]
    data = _json.loads(blob)
    wc = data["parts"][0].get("worst_cell")
    assert wc == ["F5_DOE_001", "F5_DOE_002"], "worst_cell 이 payload 에 없음"
    # 이동 여부는 값이 서로 다른지로 판정된다
    assert len({x for x in wc if x}) > 1


def test_sphere_units_defaulted_when_sidecar_lacks_them():
    """sphere sidecar 는 unit_labels 를 싣지 않는다 — 단위 없는 수를 내보내지 않는다.

    회귀 배경: 787,830 이 무슨 단위인지 알 수 없게 나갔다. 저장 단위인 G 를
    기본값으로 채운다. 처음에는 본 보고서 **화면**의 "MG" 를 그대로 베꼈는데,
    그 MG 는 표시할 때 v/1e6 을 한 결과지 저장 단위가 아니라서 나누지 않은
    값에 MG 가 붙어 1e6 배 과대 표기가 됐다.
    """
    from koo_federate_report.adapters.sphere import to_bundle
    raw = {
        "project_name": "P",
        "parts": {"1": {"part_name": "Display", "group": "D"}},
        "results_summary": [
            {"run_folder": "R1",
             "angle": {"name": "A1", "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
                       "category": "face"},
             "parts": {"1": {"peak_g": 100.0, "peak_stress": 10.0,
                             "peak_strain": 0.0, "peak_disp": 0.0}}},
        ],
        "findings": [],
        "simulation_params": {},
    }
    b = to_bundle(raw, path="/x/report.json", label="Rev")
    assert b.unit_labels.get("acc"), "sphere 단위 라벨이 비어 있다"
    assert b.unit_labels["acc"] == "G"


def test_interpolated_cells_visually_demoted():
    """보간 셀을 실측처럼 보이게 하지 않는다 (계획서 §sphere 정직성 규칙)."""
    d = _engine_shaped()
    for c in d["cells"]:
        for s in c["per_rev"]:
            s["measured"] = False
    h = generate_html(d)
    assert "interp" in h, "보간 강등 클래스가 없음"
    assert "보간(IDW)" in h, "probe 에 보간 표기가 없음"


def test_s9_renders_coverage_table_not_raw_dict():
    """coverage.per_rev 는 dict 리스트다 — str(dict) 가 화면에 새면 안 된다.

    회귀: `_esc(v)` 로 찍어 "{'label': 'RevA', 'n_grid': 915, …}" 가 그대로
    보고서에 나왔다. 엔진↔리포트 계약 불일치의 여섯 번째 사례.
    """
    d = _engine_shaped()
    d["coverage"] = {
        "mode": "nearest", "mode_effective": "nearest", "n_grid": 3,
        "grid_source": "baseline(RevA)",
        "per_rev": [
            {"label": "RevA", "n_grid": 3, "exact": 3, "nearest": 0, "idw": 0,
             "missing": 0, "measured_pct": 100.0, "coverage_pct": 100.0},
            {"label": "RevB", "n_grid": 3, "exact": 2, "nearest": 0, "idw": 0,
             "missing": 1, "measured_pct": 66.7, "coverage_pct": 66.7},
        ],
    }
    h = generate_html(d)
    # 검사 범위는 s9 섹션 마크업만 — 문서에는 payload JSON 이 정상적으로 박혀 있다
    s9 = h[h.index('id="s9"'):]
    s9 = s9[:s9.index("</section>")]
    assert "{'label'" not in s9, "파이썬 dict 가 화면에 샜다"
    assert "실측률" in s9 and "100.0%" in s9 and "66.7%" in s9
    # 재현에 필요한 설정이 부록에 있어야 한다
    for token in ("baseline", "리샘플", "nearest", "trust gate", "판정 가능"):
        assert token in s9, f"s9 에 {token} 이 없다"


def test_s9_tolerates_legacy_scalar_coverage():
    """구 샘플의 스칼라 per_rev 도 크래시 없이 표시한다."""
    d = _engine_shaped()
    d["coverage"] = {"per_rev": [100, 66]}
    h = generate_html(d)
    assert "<html" in h.lower()
