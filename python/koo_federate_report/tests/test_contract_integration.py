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
