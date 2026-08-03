# impact 파트쌍 접촉력 프로파일 회귀 — 미접촉을 0 으로 위장하지 않는지
"""build_contact_profile 규칙.

sphere 의 contact_profile 과 같은 계약(pairs/pf/ti/tw)이라 렌더러를 공유한다.
핵심 규칙은 하나 — **그 위치에 그 접촉이 없으면 None 이지 0 이 아니다.**
0 으로 채우면 화면에서 '힘이 0 이었다' 로 읽힌다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.report.payload.core import build_contact_profile  # noqa: E402


class _E:
    def __init__(self, src, dst, cid, pf, ti=1.0, tw=2.0, name=""):
        self.src, self.dst, self.contact_id = src, dst, cid
        self.peak_force, self.total_impulse, self.total_work = pf, ti, tw
        self.name = name


class _F:
    def __init__(self, edges):
        self.edges = edges


POS = [{"pos_id": "P1"}, {"pos_id": "P2"}, {"pos_id": "P3"}]


def test_missing_position_is_none_not_zero():
    flows = {"P1": _F([_E("1", "2", 10, 100.0)]),
             "P3": _F([_E("1", "2", 10, 300.0)])}     # P2 에는 접촉 없음
    cp = build_contact_profile(flows, POS)
    assert len(cp["pairs"]) == 1
    assert cp["pf"][0] == [100.0, None, 300.0]


def test_unresolved_pair_marked_and_sorted_last():
    flows = {"P1": _F([_E("1", "2", 10, 10.0),
                       _E("iface:99", "3", 99, 9000.0)])}
    cp = build_contact_profile(flows, POS)
    by = {p["key"]: p for p in cp["pairs"]}
    assert by["1>2"]["resolved"] is True
    assert by["iface:99>3"]["resolved"] is False
    assert cp["pairs"][0]["key"] == "1>2", "해결된 쌍이 먼저여야 한다"


def test_empty_inputs_do_not_raise():
    """데이터가 없으면 빈 구조를 돌려준다 — 예외로 보고서를 죽이지 않는다."""
    assert build_contact_profile({}, POS)["pairs"] == []
    assert build_contact_profile({"P1": _F([])}, [])["pairs"] == []
    assert build_contact_profile(None, None)["pairs"] == []


def test_unknown_position_is_skipped():
    """payload positions 에 없는 pos_id 는 조용히 건너뛴다 (인덱스 오류 금지)."""
    cp = build_contact_profile({"ZZZ": _F([_E("1", "2", 10, 5.0)])}, POS)
    assert cp["pairs"] == []
