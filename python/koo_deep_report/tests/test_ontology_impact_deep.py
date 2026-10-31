# 부분충격·단일 런 온톨로지 어댑터 시험 — G 환산, 위치 키, 줄인 흐름 엣지, 0 위장 금지, 단위 판정
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_PY = Path(__file__).resolve().parents[2]
for _sib in ("koo_sphere_report", "koo_impact_report"):
    if (_PY / _sib).is_dir() and str(_PY / _sib) not in sys.path:
        sys.path.insert(0, str(_PY / _sib))

from koo_deep_report.ontology import deep, impact  # noqa: E402
from koo_deep_report.report.models import (  # noqa: E402
    D3plotResult, MotionData, PartSummary, PartTimeSeries, SimInfo, SingleResult,
)


def _objs(doc, t):
    return {o["key"]: o["properties"] for o in doc["objects"] if o["type"] == t}


# ── 부분충격 ──────────────────────────────────────────────────────────────
def _impact_report(yields=None):
    rows = []
    for pos, g, s in (("F5_DOE_001", 98066.5, 50.0), ("F5_DOE_002", 196133.0, 120.0)):
        rows.append({"face": "F5", "pos_id": pos, "x": 0.0, "y": 0.0, "part_id": 1,
                     "peak_g": g, "peak_stress": s, "peak_strain": 1e-4, "peak_disp": 0.2})
    return {
        "project_name": "imp", "test_dir": "/x/Test_Impact_A",
        "impactor": {"part_id": 24, "initial_velocity": [0.0, 0.0, -4905.0]},
        "faces": [{"code": "F5", "name": "Top", "roll": 90.0, "pitch": 0.0, "yaw": 0.0}],
        "positions_by_face": {"F5": [
            {"pos_id": "F5_DOE_001", "face": "F5", "x": -40.0, "y": -40.0, "run_dir": "/x/output/Run_1"},
            {"pos_id": "F5_DOE_002", "face": "F5", "x": 0.0, "y": 0.0, "run_dir": "/x/output/Run_2"}]},
        "parts": [{"part_id": 1, "part_name": "Front\\Metal", "group": "ELASTIC"},
                  {"part_id": 2, "part_name": "Front\\Wall", "group": "ELASTIC"},
                  {"part_id": 24, "part_name": "", "group": "ELASTIC"}],
        "results": rows,
        "findings": [{"severity": "CRITICAL", "title": "접촉 미발생 런 1/2", "detail": "x", "recommendation": "y"}],
        "sim_params": {"units": "ton-mm-s", "unit_labels": {"stress": "MPa", "acc": "mm/s²"}, "n_states": 992,
                       "n_failed": 0, "doe_kind": "partial_impact_multi_position",
                       "yield_stress_by_part": yields or {}},
        "solver_quality": {"F5_DOE_001": {"pass_fail": "PASS"}, "F5_DOE_002": {"pass_fail": "FAIL"}},
        "provenance": {"tool_version": "0.1.0"},
    }


def _payload():
    return {
        "results": [{"pos_id": "F5_DOE_002", "part_id": 1, "s1": 90.0, "s3": -30.0}],
        "trajectories": {"F5_DOE_002": {"t_first_contact": 1e-5}},
        "energy_flows": {"F5_DOE_002": {"edges": [
            {"src": "2", "dst": "1", "cid": 92, "name": "Contact Region", "conf": 1.0,
             "peak_f": 34.9, "total_imp": 0.0151, "total_w": 0.6}], "depth_map": {"24": 0}}},
    }


def test_impact_g_is_converted_from_deck_acceleration():
    doc = impact.build(_impact_report(), payload=_payload())
    r = _objs(doc, "cae_part_response")
    assert r["resp/F5_DOE_001/1"]["peak_g"] == pytest.approx(10.0)
    assert r["resp/F5_DOE_002/1"]["peak_max_principal"] == 90.0 and r["resp/F5_DOE_002/1"]["min_principal"] == -30.0
    assert "peak_max_principal" not in r["resp/F5_DOE_001/1"]


def test_impact_runs_are_positions():
    doc = impact.build(_impact_report(), payload=_payload())
    runs = _objs(doc, "cae_run")
    r2 = runs["run/F5_DOE_002"]
    assert r2["case_key"] == "F5_DOE_002" and r2["run_folder"] == "Run_2" and r2["impact_face"] == "F5"
    assert r2["solver_quality"] == "FAIL" and r2["first_contact_time"] == 1e-5 and r2["roll_deg"] == 90.0
    camp = _objs(doc, "cae_campaign")["campaign"]
    assert camp["impactor_part_id"] == 24 and camp["impact_speed"] == 4905.0 and camp["g_factor"] == 9806.65
    x = _objs(doc, "cae_load_transfer")["xfer/F5_DOE_002/92"]
    assert x["from_part"] == "part/2" and x["to_part"] == "part/1" and x["total_impulse"] == 0.0151


def test_impact_has_no_absolute_g_rule():
    # 부분충격 분석기는 가속도 절대 기준을 두지 않는다 — 20 G 든 20만 G 든 한계 없으면 unknown
    doc = impact.build(_impact_report(), payload=_payload())
    assert _objs(doc, "cae_part")["part/1"]["severity"] == "UNKNOWN"


def test_impact_part_yield_gives_safety_factor():
    doc = impact.build(_impact_report({"1": 100.0}), payload=_payload())
    p1 = _objs(doc, "cae_part")["part/1"]
    assert p1["min_safety_factor"] == pytest.approx(100 / 120) and p1["severity"] == "CRITICAL"
    assert _objs(doc, "cae_campaign")["campaign"]["yield_source"] == "mat_card"


def test_impact_unknown_units_drop_g():
    rep = _impact_report()
    rep["sim_params"]["units"] = ""
    doc = impact.build(rep, payload=_payload())
    assert "peak_g" not in _objs(doc, "cae_part_response")["resp/F5_DOE_001/1"]
    assert doc["units"]["normalized"] is False


# ── 단일 런 ───────────────────────────────────────────────────────────────
def _series(pid, q, gmax, gmin=0.0, t=0.001):
    return PartTimeSeries(part_id=pid, part_name="", quantity=q, unit="deck_units",
                          global_max=gmax, global_min=gmin, time_of_max=t, data=[])


def _single(end_time=0.003):
    si = SimInfo(path=Path("/x/output/Run_9/Output"), d3plot=Path("/x/output/Run_9/Output/d3plot"),
                 normal_termination=True)
    d3 = D3plotResult(
        metadata={"num_states": 100, "end_time": end_time, "tool_commit": "abc1234"},
        stress=[_series(1, "von_mises", 250.0), _series(2, "von_mises", 40.0)],
        strain=[_series(1, "eff_plastic_strain", 0.01)],
        acceleration=[],
        motion={1: MotionData(part_id=1, acc_mag=[0.0, 98066.5], max_disp_mag=[0.0, 2.0]),
                2: MotionData(part_id=2)},            # 가속도 열이 없다
        max_principal=[_series(1, "max_principal", 200.0)],
        hotspot_clusters=[{"part_id": 1, "criterion": "von_mises", "element_type": "solid",
                           "clusters": [{"rank": 1, "element_count": 5, "center": [0, 0, 0],
                                         "stress_max": 250.0}]}],
    )
    parts = {1: PartSummary(part_id=1, part_name="Front\\Metal", peak_disp_mag=2.0, stress_limit=200.0,
                            stress_source="mat_card"),
             2: PartSummary(part_id=2, part_name="PCB")}
    return SingleResult(sim_info=si, d3plot_result=d3, parts=parts, label="Run_9")


def _kw(rho):
    return SimpleNamespace(materials={1: SimpleNamespace(density=rho)})


def test_single_run_reads_histories_not_zero_defaults():
    doc = deep.build(_single(), flow=None, keyword=_kw(7.85e-9))
    r = _objs(doc, "cae_part_response")
    # 런 키는 DynaForge 가 deep 에 쓰는 single — 실제 폴더는 run_folder
    assert r["resp/single/1"]["peak_von_mises"] == 250.0 and r["resp/single/1"]["peak_g"] == pytest.approx(10.0)
    # 파트 2: 주응력·변형률·가속도 이력이 없다 — PartSummary 의 0.0 을 싣지 않는다
    assert set(r["resp/single/2"]) == {"run", "part", "peak_von_mises", "peak_von_mises_time"}
    run = _objs(doc, "cae_run")["run/single"]
    assert run["case_key"] == "single" and run["run_folder"] == "Run_9"
    assert run["analyzer_commit"] == "abc1234" and run["success"] is True
    p1 = _objs(doc, "cae_part")["part/1"]
    assert p1["min_safety_factor"] == pytest.approx(0.8) and p1["severity"] == "CRITICAL"
    assert "hs/single/1/von_mises/solid/1" in _objs(doc, "cae_hotspot")
    assert doc["units"]["system"] == "ton_mm_s"


def test_single_run_units_need_time_cross_check():
    # 밀도는 ton-mm-s 인데 끝 시각 3.0 → ms 덱일 수 있다 — 단정하지 않는다
    doc = deep.build(_single(end_time=3.0), flow=None, keyword=_kw(7.85e-9))
    assert doc["units"]["system"] == "unknown" and "ms" in doc["units"]["note"]
    assert "peak_g" not in _objs(doc, "cae_part_response")["resp/single/1"]
    doc = deep.build(_single(), flow=None, keyword=None)
    assert doc["units"]["system"] == "unknown"


def test_deep_writes_report_ontology_next_to_html(tmp_path):
    (tmp_path / "report.html").write_text("<html/>")
    out = deep.write_for_result(_single(), tmp_path)
    assert out.name == "report.ontology.json"
    import json
    doc = json.loads(out.read_text())
    assert doc["source"]["html"]["file"] == "report.html" and doc["scope"]["scenario_kind"] == "single_run"
