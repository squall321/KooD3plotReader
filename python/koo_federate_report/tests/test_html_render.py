# 연합 보고서 HTML 렌더 계약 테스트 — 필수 마커 존재와 빈 데이터 강등을 확인한다.

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_federate_report.report.html_report import generate_html  # noqa: E402


@pytest.fixture()
def sample():
    """계약 스키마를 그대로 따르는 3리비전 · 2셀 최소 픽스처."""
    return {
        "kind": "impact",
        "baseline_idx": 0,
        "revisions": [
            {"idx": 0, "label": "RevA", "project": "proj_a"},
            {"idx": 1, "label": "RevB", "project": "proj_b"},
            {"idx": 2, "label": "RevC", "project": "proj_c"},
        ],
        "cells": [
            {
                "key": "F5_DOE_001", "label": "F5_DOE_001", "x": -40, "y": -40, "category": "F5",
                "per_rev": [
                    {"value": 4.8e8, "trust": {"ok": False, "reason": "no-contact"}, "behavior": "no-contact"},
                    {"value": 2.8e8, "trust": {"ok": True, "reason": ""}, "behavior": "bounce"},
                    {"value": 5.1e8, "trust": {"ok": True, "reason": ""}, "behavior": "bounce"},
                ],
                "delta": [None, None, None], "delta_pct": [None, None, None],
                "winner": 2, "trend": 0.027, "spread": 2.3e8, "trust_ok": False,
            },
            {
                "key": "F5_DOE_003", "label": "F5_DOE_003", "x": -40, "y": 0, "category": "F5",
                "per_rev": [
                    {"value": 8.7e7, "trust": {"ok": True, "reason": ""}, "behavior": "bounce"},
                    {"value": 7.0e7, "trust": {"ok": True, "reason": ""}, "behavior": "bounce"},
                    {"value": 5.4e7, "trust": {"ok": True, "reason": ""}, "behavior": "bounce"},
                ],
                "delta": [0.0, -1.7e7, -3.3e7], "delta_pct": [0.0, -19.5, -37.4],
                "winner": 0, "trend": -0.186, "spread": 3.3e7, "trust_ok": True,
            },
        ],
        "parts": [
            {"canonical": "Display", "names": ["Display", "DISP_MAIN", "Display"],
             "worst": [8.2e8, 5.9e8, 7.1e8], "delta_pct": [0, -28.0, -13.4], "rank": [1, 1, 1]},
        ],
        "part_matrix": {"parts": ["Display"], "cells": ["F5_DOE_001", "F5_DOE_003"],
                        "delta_pct": [[-20.0, 6.8]]},
        # 엔진 계약: per_rev[{label,n_changed,counts,entries}] (baseline 포함)
        "behavior_transitions": {
            "headline": True,
            "baseline_idx": 0,
            "n_changed_cells": 1,
            "per_rev": [
                {"label": "RevA", "n_changed": 0,
                 "counts": {"bounce": 2},
                 "entries": [{"from": "bounce", "to": "bounce", "count": 2,
                              "cells": ["F5_DOE_001", "F5_DOE_002"]}]},
                {"label": "RevB", "n_changed": 1,
                 "counts": {"no-contact": 1, "bounce": 1},
                 "entries": [{"from": "no-contact", "to": "bounce", "count": 1,
                              "cells": ["F5_DOE_001"]},
                             {"from": "bounce", "to": "bounce", "count": 1,
                              "cells": ["F5_DOE_002"]}]},
            ],
        },
        # 엔진 계약: 리비전별 list
        "findings_diff": [
            {"label": "RevA", "is_baseline": True, "new": [], "resolved": [], "kept": [], "n_total": 1},
            {"label": "RevB", "is_baseline": False,
             "new": [{"severity": "CRITICAL", "title": "접촉 미발생 런 검토 필요"}],
             "resolved": [{"severity": "WARNING", "title": "outlier 해소"}],
             "kept": [{"severity": "INFO", "title": "1 face(s)"}], "n_total": 2},
        ],
        "_legacy_findings_diff": {
            "new": [{"severity": "CRITICAL", "title": "접촉 미발생 런 검토 필요"}],
            "resolved": [{"severity": "WARNING", "title": "outlier 해소"}],
            "kept": [{"severity": "INFO", "title": "1 face(s)"}],
        },
        "kpi": {"n_cells": 2, "n_comparable": 1, "n_revisions": 3,
                "worst_g": [1.49e9, 1.05e9, 1.25e9], "worst_s": [2255.4, 1690.0, 1350.0],
                "diss_pct": [41.2, 35.0, 30.1]},
        "coverage": {"per_rev": [2, 2, 2], "intersection": 2, "resampled": 0, "note": "격자 동일 — 리샘플 없음"},
        "warnings": [{"kind": "trust-gate", "msg": "1개 위치는 baseline 이 미접촉이라 Δ 미판정"}],
        "provenance": [
            {"label": "RevA", "tool_version": "0.1.0", "generated_utc": "2026-07-20T00:00:00+00:00",
             "test_dir": "/data/proj/RevA", "input_digest": "c18ff0a4"},
            {"label": "RevB", "tool_version": "0.1.0", "generated_utc": "2026-07-21T00:00:00+00:00",
             "test_dir": "/data/proj/RevB", "input_digest": "c18ff0a5"},
            {"label": "RevC", "tool_version": "0.1.0", "generated_utc": "2026-07-22T00:00:00+00:00",
             "test_dir": "/data/proj/RevC", "input_digest": "c18ff0a6"},
        ],
        "unit_labels": {"acc": "mm/s²", "stress": "MPa", "disp": "mm", "energy": "mJ", "time": "s"},
        "g_divisor": 9810.0,
    }


def test_markers_present(sample):
    h = generate_html(sample)
    assert h.startswith("<!DOCTYPE html>") and h.rstrip().endswith("</html>")
    # 모든 섹션이 계약대로 나온다.
    for sid in ("s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9"):
        assert f'id="{sid}"' in h, sid
    # 주력 뷰 / 지도 4종 / probe / 매트릭스 컨테이너.
    for marker in ("fed-prof", "fed-map-winner", "fed-map-trend", "fed-map-delta",
                   "fed-map-spread", "fed-probe-bars", "fed-part-tbl", "fed-mtx"):
        assert f'id="{marker}"' in h, marker
    # 토글 3종 x 2축.
    for attr in ('data-ord="severity"', 'data-ord="key"', 'data-ord="cat"',
                 'data-mode="abs"', 'data-mode="delta"', 'data-mode="log"'):
        assert attr in h, attr
    # 데이터 블록과 리비전 라벨.
    assert 'id="fed-data"' in h
    for label in ("RevA", "RevB", "RevC"):
        assert label in h
    # 거동 전이 승격 + 경고 배지 + provenance digest.
    assert "거동 전이" in h and "c18ff0a4" in h
    assert "baseline 이 미접촉이라" in h
    # 프로즈에 개선/악화 카운트가 들어간다.
    assert "개선" in h and "악화" in h


def test_promotion_order(sample):
    """headline=True 면 거동 전이 패널이 s2 프로파일보다 위에 온다."""
    h = generate_html(sample)
    assert h.index('id="s6"') < h.index('id="s2"')
    sample["behavior_transitions"]["headline"] = False
    h2 = generate_html(sample)
    assert h2.index('id="s6"') > h2.index('id="s2"')


def test_two_revision_trend_demoted(sample):
    """N=2 면 TREND 는 Δ 와 동일하므로 숨긴다."""
    sample["revisions"] = sample["revisions"][:2]
    for c in sample["cells"]:
        c["per_rev"] = c["per_rev"][:2]
        c["delta"] = c["delta"][:2]
        c["delta_pct"] = c["delta_pct"][:2]
    h = generate_html(sample)
    assert 'id="fed-map-trend"' not in h
    assert "N=2 강등" in h


def test_empty_degrades_gracefully():
    """빈 입력에서도 0 으로 위장하지 않고 강등된 HTML 을 낸다."""
    h = generate_html({})
    assert h.startswith("<!DOCTYPE html>")
    assert 'id="s0empty"' in h
    assert "비교 셀 데이터 없음" in h
    # 없는 섹션은 아예 만들지 않는다.
    for sid in ("s2", "s3", "s4", "s5", "s6", "s7"):
        assert f'id="{sid}"' not in h
    # 요약과 부록은 사유와 함께 남는다.
    assert "리비전 정보가 없다" in h and 'id="s9"' in h


def test_missing_values_not_faked(sample):
    """값이 없으면 0 이 아니라 em-dash 로 표기한다."""
    sample["kpi"]["worst_s"] = [None, None, None]
    h = generate_html(sample)
    assert "&mdash;" in h
    assert ">0<" not in h.split('id="fed-data"')[0].split("WORST STRESS")[1][:400]
