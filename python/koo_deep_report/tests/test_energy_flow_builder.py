# energy_flow_builder 의 시간축 리샘플·cumtrapz 임펄스/work·BFS depth 를 합성 픽스처로 검증
"""Synthetic-fixture tests for energy_flow_builder.

3파트·2접촉 mock BinoutData + mock ContactMap 로 손계산한 cumtrapz 임펄스/work,
BFS depth, 노드/엣지 축 정합을 검증한다. lasso 등 외부 의존 없음.
"""
from __future__ import annotations

import math

import pytest

from koo_deep_report.core.binout_reader import (
    BinoutData, MatSumData, RcforcInterface,
)
from koo_deep_report.core.energy_flow_builder import (
    build_flow_graph, _downsample_indices, _cumtrapz,
)


# --- mock ContactMap (P2 스키마 최소 재현) ---------------------------------

class _PartRef:
    def __init__(self, kind, part_id, node_id, name):
        self.kind = kind
        self.part_id = part_id
        self.node_id = node_id
        self.name = name


class _Endpoint:
    def __init__(self, cid, name, slave, master, confidence):
        self.cid = cid
        self.name = name
        self.slave = slave
        self.master = master
        self.confidence = confidence


class _ContactMap:
    def __init__(self, endpoints):
        self.endpoints = endpoints


def _make_binout():
    """3파트(1=임팩터,2,3), 2접촉(10: 1→2, 20: 2→3) 의 합성 BinoutData."""
    matsum = MatSumData(
        part_ids=[1, 2, 3],
        t=[0.0, 1.0, 2.0],
        kinetic_energy=[[100.0, 0.0, 0.0],
                        [60.0, 20.0, 5.0],
                        [40.0, 30.0, 15.0]],
        internal_energy=[[0.0, 0.0, 0.0],
                         [0.0, 10.0, 2.0],
                         [0.0, 20.0, 8.0]],
        hourglass_energy=[[0.0, 0.0, 0.0],
                          [0.0, 1.0, 0.5],
                          [0.0, 3.0, 1.5]],
        x_rbvelocity=[[10.0, 0.0, 0.0],
                      [8.0, 2.0, 1.0],
                      [6.0, 4.0, 2.0]],
        y_rbvelocity=[[0.0, 0.0, 0.0]] * 3,
        z_rbvelocity=[[0.0, 0.0, 0.0]] * 3,
    )
    rcforc = [
        RcforcInterface(interface_id=10, name="C10", side=0, t=[0.0, 1.0, 2.0],
                        fx=[0.0, 100.0, 200.0], fy=[0.0, 0.0, 0.0], fz=[0.0, 0.0, 0.0]),
        RcforcInterface(interface_id=10, name="C10", side=1, t=[0.0, 1.0, 2.0],
                        fx=[0.0, 100.0, 200.0], fy=[0.0, 0.0, 0.0], fz=[0.0, 0.0, 0.0]),
        RcforcInterface(interface_id=20, name="C20", side=0, t=[0.0, 1.0, 2.0],
                        fx=[0.0, 50.0, 80.0], fy=[0.0, 0.0, 0.0], fz=[0.0, 0.0, 0.0]),
        RcforcInterface(interface_id=20, name="C20", side=1, t=[0.0, 1.0, 2.0],
                        fx=[0.0, 50.0, 80.0], fy=[0.0, 0.0, 0.0], fz=[0.0, 0.0, 0.0]),
    ]
    return BinoutData(matsum=matsum, rcforc=rcforc, glstat=None)


def _make_contact_map():
    p1 = _PartRef("part", 1, "1", "P1")
    p2 = _PartRef("part", 2, "2", "P2")
    p3 = _PartRef("part", 3, "3", "P3")
    return _ContactMap({
        10: _Endpoint(10, "C10", slave=p1, master=p2, confidence=0.9),
        20: _Endpoint(20, "C20", slave=p2, master=p3, confidence=0.8),
    })


PART_NAMES = {1: "P1", 2: "P2", 3: "P3"}


# --- 단위 함수 -------------------------------------------------------------

def test_downsample_indices_basic():
    assert _downsample_indices(3, 120) == [0, 1, 2]
    idx = _downsample_indices(201, 120)
    assert idx[0] == 0 and idx[-1] == 200
    assert len(idx) <= 120 + 2  # last + peak splice 여유
    # peak splice 반영
    idx2 = _downsample_indices(201, 120, peak_idx=101)
    assert 101 in idx2 and idx2[0] == 0 and idx2[-1] == 200


def test_cumtrapz_hand():
    # f=[0,100,200], t=[0,1,2] → [0, 50, 200]
    assert _cumtrapz([0.0, 100.0, 200.0], [0.0, 1.0, 2.0]) == [0.0, 50.0, 200.0]


# --- 메인 그래프 -----------------------------------------------------------

def test_build_none_when_no_matsum():
    assert build_flow_graph(BinoutData(matsum=None), None, {}, 1) is None


def test_nodes_axis_consistency():
    g = build_flow_graph(_make_binout(), _make_contact_map(), PART_NAMES, impactor_pid=1)
    assert g is not None
    assert len(g["nodes"]) == 3
    # 모든 (실)노드 times 길이 동일 + 엣지와도 동일
    lens = {len(n["times"]) for n in g["nodes"]}
    assert lens == {3}
    for n in g["nodes"]:
        assert len(n["kinetic_ts"]) == 3
    for e in g["edges"]:
        assert len(e["times"]) == 3
        assert len(e["force_mag_ts"]) == 3
        assert len(e["impulse_cum_ts"]) == 3


def test_node_series_values():
    g = build_flow_graph(_make_binout(), _make_contact_map(), PART_NAMES, impactor_pid=1)
    by_id = {n["node_id"]: n for n in g["nodes"]}
    assert by_id["1"]["is_impactor"] is True
    assert by_id["1"]["kinetic_ts"] == [100.0, 60.0, 40.0]
    assert by_id["2"]["kinetic_ts"] == [0.0, 20.0, 30.0]
    assert by_id["2"]["internal_ts"] == [0.0, 10.0, 20.0]
    assert by_id["3"]["kinetic_ts"] == [0.0, 5.0, 15.0]


def test_edge_impulse_and_work_hand_calc():
    g = build_flow_graph(_make_binout(), _make_contact_map(), PART_NAMES, impactor_pid=1)
    by_cid = {e["contact_id"]: e for e in g["edges"]}
    assert set(by_cid) == {10, 20}

    e10 = by_cid[10]
    # 방향: depth[1]=0 < depth[2]=1 → src=1, dst=2
    assert (e10["src"], e10["dst"]) == ("1", "2")
    assert e10["force_mag_ts"] == [0.0, 100.0, 200.0]
    assert e10["impulse_cum_ts"] == [0.0, 50.0, 200.0]
    assert e10["peak_force"] == 200.0
    assert e10["total_impulse"] == 200.0
    # work = cumtrapz(F·(v1-v2)) : power=[0,600,400] → [0,300,800]
    assert e10["work_cum_ts"] == [0.0, 300.0, 800.0]
    assert e10["total_work"] == 800.0
    assert e10["confidence"] == 0.9
    assert e10["first_engage_idx"] == 1
    assert e10["name"] == "C10"

    e20 = by_cid[20]
    assert (e20["src"], e20["dst"]) == ("2", "3")
    assert e20["impulse_cum_ts"] == [0.0, 25.0, 90.0]
    assert e20["total_impulse"] == 90.0
    # power=[0,50,160] → cumtrapz [0,25,130]
    assert e20["work_cum_ts"] == [0.0, 25.0, 130.0]
    assert e20["total_work"] == 130.0
    assert e20["confidence"] == 0.8


def test_depth_and_propagation():
    g = build_flow_graph(_make_binout(), _make_contact_map(), PART_NAMES, impactor_pid=1)
    assert g["depth_map"] == {"1": 0, "2": 1, "3": 2}
    assert g["propagation_order"] == ["1", "2", "3"]


def test_scalars():
    g = build_flow_graph(_make_binout(), _make_contact_map(), PART_NAMES, impactor_pid=1)
    # glstat 없음 → Σmatsum KE[0] = 100
    assert g["impactor_ke_initial"] == 100.0
    # 임팩터 노드 KE[-1] = 40
    assert g["impactor_ke_final"] == 40.0
    # glstat 없음 → Σ|hourglass[-1]| = 3 + 1.5 = 4.5
    assert g["energy_dissipated"] == 4.5


def test_contact_map_none_demotes_to_pseudo():
    """contact_map=None → 인터페이스 양끝이 유령 iface 노드, work 비어있음."""
    g = build_flow_graph(_make_binout(), None, PART_NAMES, impactor_pid=1)
    assert g is not None
    # 실노드 3 + 유령 4 (iface:10_a/_b, iface:20_a/_b)
    ids = {n["node_id"] for n in g["nodes"]}
    assert {"1", "2", "3"} <= ids
    assert "iface:10_a" in ids and "iface:10_b" in ids
    # 유령 노드는 빈 ts
    ghost = next(n for n in g["nodes"] if n["node_id"] == "iface:10_a")
    assert ghost["kinetic_ts"] == [] and ghost["times"] == []
    for e in g["edges"]:
        assert e["src"].startswith("iface:") and e["dst"].startswith("iface:")
        assert e["work_cum_ts"] == [] and e["total_work"] == 0.0
    # 임펄스는 여전히 계산 (엔드포인트 유령이어도)
    assert {e["contact_id"] for e in g["edges"]} == {10, 20}


def test_nan_inf_sanitized():
    """NaN/inf 입력이 0 으로 정규화되는지."""
    b = _make_binout()
    b.matsum.kinetic_energy[1][0] = float("nan")
    b.rcforc[0].fx[2] = float("inf")
    g = build_flow_graph(b, _make_contact_map(), PART_NAMES, impactor_pid=1)
    for n in g["nodes"]:
        for v in n["kinetic_ts"] + n["internal_ts"]:
            assert math.isfinite(v)
    for e in g["edges"]:
        for v in e["force_mag_ts"] + e["impulse_cum_ts"]:
            assert math.isfinite(v)
