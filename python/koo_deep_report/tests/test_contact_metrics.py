# 접촉력 계측·검증 회귀 — 측정 대상 side 선택과 '한쪽만 기록' 구분
"""contact_metrics 의 실측 기반 규칙.

실측에서 잡은 두 가지 함정을 못박는다.

1. **큰 쪽 side 로 재야 한다.** SSTYP=5(slave='ALL') 정의에서는 한쪽이 거의
   0 으로만 기록된다. Test_006 의 CID 172 는 slave 0.2 / master 36251 이라
   slave 를 먼저 고르면 모델 최대 접촉을 0 으로 측정한다.
2. **한쪽만 기록된 접촉은 뉴턴 3법칙 위반이 아니다.** 섞어서 통계를 내면
   max_rel 이 1.0 이 되어 정상 모델도 늘 실패처럼 보인다(실측 확인).
"""
from __future__ import annotations

import pytest

from koo_deep_report.core.binout_reader import BinoutData, MatSumData, RcforcInterface
from koo_deep_report.core.contact_metrics import build_contact_metrics


class _PartRef:
    def __init__(self, kind, node_id):
        self.kind = kind
        self.node_id = node_id


class _Endpoint:
    def __init__(self, slave, master):
        self.slave = slave
        self.master = master


class _CMap:
    def __init__(self, endpoints):
        self.endpoints = endpoints


T = [0.0, 1.0, 2.0, 3.0]


def _iface(cid, side, fz, name="C"):
    return RcforcInterface(interface_id=cid, name=name, side=side, t=list(T),
                           fx=[0.0] * len(T), fy=[0.0] * len(T), fz=list(fz))


def _binout(ifaces, matsum=True):
    ms = MatSumData(part_ids=[1, 2], t=list(T),
                    kinetic_energy=[[1.0, 1.0]] * len(T),
                    internal_energy=[[0.0, 0.0]] * len(T)) if matsum else None
    return BinoutData(matsum=ms, rcforc=ifaces, sleout=[], glstat=None)


def test_no_rcforc_is_not_available_and_says_why():
    """RCFORC 가 없으면 조용히 0 을 내지 않고 사유를 낸다."""
    m = build_contact_metrics(_binout([]))
    assert m["available"] is False
    assert "rcforc" in m["reason"] and "0 이 아닙니다" in m["reason"]
    assert m["interfaces"] == []


def test_measures_the_larger_side():
    """한쪽이 거의 0 이면 큰 쪽으로 잰다 (실측 CID 172: slave 0.2 / master 36251)."""
    b = _binout([
        _iface(172, 0, [0.0, 0.2, 0.1, 0.0]),          # slave — 사실상 미기록
        _iface(172, 1, [0.0, 36251.5, 100.0, 0.0]),    # master — 실제 접촉
    ])
    m = build_contact_metrics(b)
    it = m["interfaces"][0]
    assert it["peak_force"] == pytest.approx(36251.5)
    assert it["side_used"] == 1
    assert it["one_sided_record"] is True


def test_one_sided_excluded_from_newton3():
    """한쪽만 기록된 접촉이 3법칙 통계를 오염시키면 안 된다."""
    b = _binout([
        # 정상 접촉쌍 — 양쪽 동일
        _iface(10, 0, [0.0, 100.0, 50.0, 0.0]),
        _iface(10, 1, [0.0, 100.0, 50.0, 0.0]),
        # 한쪽만 기록
        _iface(20, 0, [0.0, 0.1, 0.0, 0.0]),
        _iface(20, 1, [0.0, 900.0, 400.0, 0.0]),
    ])
    n3 = build_contact_metrics(b)["checks"]["newton3"]
    assert n3["n_checked"] == 1, "한쪽만 기록된 접촉이 검증에 섞였다"
    assert n3["n_one_sided"] == 1
    assert n3["max_rel"] == pytest.approx(0.0, abs=1e-9)


def test_newton3_detects_real_imbalance():
    """진짜 불균형은 잡아야 한다 (양쪽 다 유의미한데 값이 다름)."""
    b = _binout([
        _iface(10, 0, [0.0, 100.0, 100.0, 0.0]),
        _iface(10, 1, [0.0, 150.0, 150.0, 0.0]),
    ])
    n3 = build_contact_metrics(b)["checks"]["newton3"]
    assert n3["n_checked"] == 1 and n3["n_one_sided"] == 0
    assert n3["max_rel"] == pytest.approx(1.0 / 3.0, rel=1e-6)


def test_engagement_window_is_relative_not_absolute():
    """접촉 구간 판정은 그 인터페이스 피크의 상대값이라 단위에 무관하다."""
    small = build_contact_metrics(_binout([_iface(1, 0, [0.0, 1.0, 0.5, 0.0])]))
    big = build_contact_metrics(_binout([_iface(1, 0, [0.0, 1e6, 5e5, 0.0])]))
    a, c = small["interfaces"][0], big["interfaces"][0]
    assert a["engage_t0"] == c["engage_t0"]
    assert a["engage_t1"] == c["engage_t1"]


def test_pair_resolution_and_note():
    """파트로 분해된 것과 아닌 것을 구분하고, 후자는 note 로 알린다."""
    b = _binout([
        _iface(10, 0, [0.0, 10.0, 0.0, 0.0]),
        _iface(20, 0, [0.0, 20.0, 0.0, 0.0]),
    ])
    cm = _CMap({
        10: _Endpoint(_PartRef("part", "1"), _PartRef("part", "2")),
        20: _Endpoint(_PartRef("all", "iface:20"), _PartRef("part", "3")),
    })
    m = build_contact_metrics(b, cm, {1: "A", 2: "B", 3: "C"})
    by = {i["cid"]: i for i in m["interfaces"]}
    assert by[10]["resolved"] is True and by[10]["src_name"] == "A"
    assert by[20]["resolved"] is False and by[20]["src_name"] == "iface:20"
    assert m["n_resolved"] == 1
    assert "분해되지 않았습니다" in m["note"]


def test_no_impulse_momentum_check():
    """충격량↔운동량 비교는 싣지 않는다 (부호 규약상 늘 불일치로 보인다)."""
    m = build_contact_metrics(_binout([_iface(1, 0, [0.0, 10.0, 0.0, 0.0])]))
    assert "impulse_momentum" not in m["checks"]
    assert set(m["checks"]) == {"newton3", "timing", "sliding_energy"}


def test_blank_part_name_falls_back():
    """키워드에 이름이 비어 있어도 화면에서 파트가 사라지면 안 된다."""
    b = _binout([_iface(10, 0, [0.0, 10.0, 0.0, 0.0])])
    cm = _CMap({10: _Endpoint(_PartRef("part", "1"), _PartRef("part", "23"))})
    m = build_contact_metrics(b, cm, {1: "A", 23: "   "})
    it = m["interfaces"][0]
    assert it["src_name"] == "A"
    assert it["dst_name"] == "Part_23"
