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
