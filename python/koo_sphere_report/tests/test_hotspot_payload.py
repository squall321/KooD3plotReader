# 핫스팟 군집 payload(G2) 규칙 — 자릿수를 줄이되 '없음' 을 0 으로 위장하지 않는다
"""HTML 에 싣는 군집 payload 의 규칙.

실측 배경 (2026-10-17): 군집 원형은 10자리 부동소수라 하나에 583B 다. 1144각도
캠페인이면 3만개가 넘어 17MB — 리포트 본문(7MB)보다 크다. 그래서 화면이 쓰는
값만 자릿수를 줄여 담는다(실측 113B).

잘라야 하지만 **어떻게 자르느냐가 중요하다.**
- 런별로 뭉텅이로 자르면 뒤쪽 각도가 통째로 사라진다 — 전각도 인벨롭이 목적인데
  일부 각도가 없으면 그림 자체가 거짓이 된다.
- 전체를 값으로 줄 세우면 기준량이 다른 항목(von Mises 와 σ3)을 같은 자로 잰다.
그래서 **순위 라운드로빈** — 모든 (런 × 파트 × 기준량)의 1위를 먼저, 그 다음 2위를.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.report import html_report as H  # noqa: E402


class _Run:
    def __init__(self, folder, clusters):
        self.run_folder = folder
        self.hotspot_clusters = clusters


def _cluster(rank, **kw):
    c = {"rank": rank, "center": [1.0, 2.0, 3.0], "radius_enclosing": 1.5,
         "element_count": 7, "stress_max": 100.0 - rank}
    c.update(kw)
    return c


def _item(pid, criterion, n, **kw):
    return {"part_id": pid, "criterion": criterion,
            "clusters": [_cluster(i + 1, **kw) for i in range(n)]}


@pytest.fixture
def budget_10(monkeypatch):
    monkeypatch.setattr(H, "_HOTSPOT_CLUSTER_BUDGET", 10)


def test_missing_measures_have_no_key():
    """변형률·에너지가 없으면 **키를 만들지 않는다.** 0 으로 채우면 화면이
    '값 0' 과 '미계측' 을 구분하지 못하고, 선택지에서 감출 근거도 사라진다."""
    out = H._compact_cluster(_cluster(1), 2, 6, 7)
    assert "e" not in out and "w" not in out and "wd" not in out
    assert out["s"] == pytest.approx(99.0)

    full = H._compact_cluster(
        _cluster(1, strain_max=0.012, energy_total=0.5, energy_max=0.18, peak_time=6.2e-5),
        2, 6, 7)
    assert set(("e", "w", "wd", "t")) <= set(full)


def test_small_values_do_not_collapse_to_zero():
    """소성일은 1e-5 수준이다. 자릿수를 줄이면서 0 으로 뭉개면 안 된다."""
    out = H._compact_cluster(_cluster(1, energy_max=1.853e-5, strain_max=4.2e-5), 2, 6, 7)
    assert out["wd"] != 0
    assert out["e"] != 0


def test_everything_is_kept_under_budget():
    runs = [_Run(f"Run_{j}", [_item(1, "von_mises", 5)]) for j in range(3)]
    by, note = H._compact_hotspot(runs, 2, 6, 7)
    assert note == ""
    assert sum(len(i["cl"]) for v in by.values() for i in v) == 15


def test_runs_without_clusters_get_no_entry():
    """군집이 빈 항목은 담지 않는다 — 담으면 화면이 '군집 있음' 으로 보고
    빈 그림을 그린다."""
    runs = [_Run("Run_0", [{"part_id": 1, "criterion": "von_mises", "clusters": []}]),
            _Run("Run_1", []),
            _Run("Run_2", None)]
    by, note = H._compact_hotspot(runs, 2, 6, 7)
    assert by == {}
    assert note == ""


def test_budget_keeps_every_run(budget_10):
    """**이 시험이 핵심이다.** 상한에 걸려도 어느 런도 통째로 빠지지 않는다."""
    runs = [_Run(f"Run_{j}", [_item(1, "von_mises", 8)]) for j in range(5)]
    by, note = H._compact_hotspot(runs, 2, 6, 7)
    assert len(by) == 5, "런이 통째로 사라졌다"
    assert all(v[0]["cl"] for v in by.values()), "군집이 하나도 없는 런이 생겼다"
    assert sum(len(i["cl"]) for v in by.values() for i in v) == 10
    assert "20,000" not in note and "전체 40" in note


def test_budget_keeps_every_criterion(budget_10):
    """기준량이 다른 항목도 각각 1위부터 담는다 — von Mises 가 σ3 보다 수치가
    크다고 σ3 항목이 통째로 밀려나면 안 된다."""
    runs = [_Run(f"Run_{j}", [_item(1, "von_mises", 6), _item(1, "min_principal", 6)])
            for j in range(2)]
    by, note = H._compact_hotspot(runs, 2, 6, 7)
    for folder, items in by.items():
        assert len(items) == 2, folder
        for it in items:
            assert it["cl"], f"{folder} {it['cr']} 이 통째로 빠졌다"
            assert it["cl"][0]["k"] == 1, "1위가 아닌 것부터 담았다"
    assert note


def test_budget_fills_by_rank_order(budget_10):
    """깊이 순서대로 — 모두의 1위를 담기 전에 누군가의 2위를 담지 않는다."""
    runs = [_Run(f"Run_{j}", [_item(1, "von_mises", 8)]) for j in range(4)]
    by, _note = H._compact_hotspot(runs, 2, 6, 7)
    ranks = sorted(c["k"] for v in by.values() for i in v for c in i["cl"])
    assert ranks == [1, 1, 1, 1, 2, 2, 2, 2, 3, 3]


def test_unsorted_input_is_ranked_first(budget_10):
    """산출물이 순위순이 아니어도 1위부터 담는다."""
    item = _item(1, "von_mises", 6)
    item["clusters"].reverse()
    by, _note = H._compact_hotspot([_Run("Run_0", [item])], 2, 6, 7)
    assert [c["k"] for c in by["Run_0"][0]["cl"]] == [1, 2, 3, 4, 5, 6]
