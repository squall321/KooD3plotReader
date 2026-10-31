# 전각도 낙하 report.json → 온톨로지 꾸러미 어댑터 시험 — 포락·안전율 판정·하중 전달·경로 집계·핫스팟
import json
import math
import statistics
import sys
from pathlib import Path

import pytest

# 안전율은 koo_sphere_report.yield_map 으로 셈한다(분석기와 같은 함수) — 저장소에서 돌 때 형제 패키지를 잡는다
_SPHERE = Path(__file__).resolve().parents[2] / "koo_sphere_report"
if _SPHERE.is_dir() and str(_SPHERE) not in sys.path:
    sys.path.insert(0, str(_SPHERE))

from koo_deep_report.core.contact_map import ContactEndpoint, ContactMap, PartRef  # noqa: E402
from koo_deep_report.ontology import sphere  # noqa: E402


def _report(unit_id="ton-mm-s"):
    def part(vm, g, mp=None, ie=None):
        d = {"peak_stress": vm, "time_of_peak_stress": 0.001, "peak_g": g, "peak_strain": 0.002,
             "peak_disp": 1.5}
        if mp is not None:
            d["peak_principal_stress"] = mp
        if ie is not None:
            d["energy"] = {"peak_ie": ie, "peak_ie_time": 0.002, "peak_ke": None, "peak_ke_time": None,
                           "final_ie": ie / 2, "final_ke": None}
        return d
    runs = [
        ("Run_A", {"name": "F1_Back", "roll": 0.0, "pitch": 0.0, "yaw": 0.0, "category": "face"},
         {"1": part(100.0, 1000.0, 90.0, ie=5.0), "2": part(40.0, 60000.0)}),
        ("Run_B", {"name": "E1_x", "roll": 0.0, "pitch": 90.0, "yaw": 0.0, "category": "edge"},
         {"1": part(250.0, 2000.0, 120.0), "2": part(50.0, 70000.0)}),
        ("Run_C", {"name": "P0003", "roll": 30.0, "pitch": 10.0, "yaw": 0.0, "category": "fibonacci"},
         {"1": part(160.0, 3000.0), "2": {}}),
    ]
    return {
        "project_name": "Unit", "doe_strategy": "fibonacci", "test_dir": "", "total_runs": 4,
        "successful_runs": 3, "failed_runs": 1, "angular_spacing_deg": 30.0, "sphere_coverage": 0.9,
        "findings": [
            {"severity": "CRITICAL", "title": "Part 1 (Front\\Metal): stress exceeds yield",
             "detail": "Peak 250 MPa", "recommendation": "Review"},
            {"severity": "INFO", "title": "3/4 simulations analyzed", "detail": "", "recommendation": ""},
        ],
        "parts": {"1": {"part_name": "Front\\Metal", "group": "Front"},
                  "2": {"part_name": "PCB\\Board", "group": "PCB"},
                  "23": {"part_name": "Floor", "group": "Other"}},
        "results_summary": [{"run_folder": f, "angle": a, "num_states": 100, "parts": p} for f, a, p in runs],
        "unit_system": {"id": unit_id, "g_factor": 9806.65, "detected": bool(unit_id), "note": ""},
        "unit_labels": {"stress": "MPa", "disp": "mm"} if unit_id == "ton-mm-s" else {"stress": "Pa", "disp": "m"},
        "energy_flows": {
            # 원판(상위 런) — 깊이·첫 맞닿음·신뢰도가 있다
            "Run_A": {"edges": [
                {"src": "23", "dst": "1", "contact_id": 2, "name": "floor", "peak_force": 500.0,
                 "total_impulse": 0.8, "total_work": 30.0, "confidence": 1.0, "first_engage_t": 1e-5},
                {"src": "1", "dst": "2", "contact_id": 10, "name": "tied", "peak_force": 80.0,
                 "total_impulse": 0.1, "total_work": 2.0, "confidence": 1.0, "first_engage_t": 2e-5},
                {"src": "1", "dst": "iface:99", "contact_id": 99, "name": "single", "peak_force": 5.0,
                 "total_impulse": 0.01, "total_work": 0.0},
            ], "depth_map": {"23": 0, "1": 1, "2": 2, "iface:99": 2}},
            # slim 판 — 스칼라만, 방향이 반대
            "Run_B": {"edges": [
                {"src": "2", "dst": "1", "contact_id": 10, "name": "tied", "peak_force": 90.0,
                 "total_impulse": 0.3, "total_work": 4.0},
            ], "_part_energy": {}, "_pf_max": 90.0},
        },
    }


def _cmap():
    def pr(pid):
        return PartRef(kind="part", part_id=pid, node_id=str(pid), name=f"P{pid}")
    return ContactMap(endpoints={
        10: ContactEndpoint(cid=10, name="tied", slave=pr(1), master=pr(2), confidence=1.0,
                            keyword="*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET_ID"),
        2: ContactEndpoint(cid=2, name="floor", slave=pr(1), master=pr(23), confidence=1.0,
                           keyword="*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID"),
    })


def _test_dir(tmp_path, limits):
    out = tmp_path / "camp" / "output" / "Run_A"
    out.mkdir(parents=True)
    (out / "DropSet.json").write_text(json.dumps({"model": {"part_yield": {"unit": "MPa", "parts": limits}}}))
    return tmp_path / "camp"


def _objs(doc, t):
    return {o["key"]: o["properties"] for o in doc["objects"] if o["type"] == t}


def _rels(doc, r):
    return [(tuple(x["src"]), tuple(x["dst"]), x["properties"]) for x in doc["relations"] if x["relation"] == r]


def test_impact_direction_matches_report_js():
    assert sphere.impact_dir(0, 0, 0) == (0.0, 0.0, -1.0)
    assert sphere.impact_dir(0, 90, 0) == pytest.approx((1.0, 0.0, 0.0))
    d = sphere.impact_dir(30, 10, 20)
    assert math.isclose(sum(c * c for c in d), 1.0, rel_tol=1e-9)


def test_envelope_safety_factor_and_severity(tmp_path):
    td = _test_dir(tmp_path, {"1": {"limits": [{"value": 200.0, "criterion": "von_mises", "source": "MAT 1"}]},
                              "2": {"limits": [{"value": 300.0, "criterion": "max_principal"}]}})
    doc = sphere.build(_report(), test_dir=td, contact_map=_cmap())
    parts = _objs(doc, "cae_part")
    p1, p2 = parts["part/1"], parts["part/2"]
    assert p1["worst_von_mises"] == 250.0 and p1["worst_von_mises_run"] == "run/Run_B"
    assert p1["min_safety_factor"] == pytest.approx(0.8) and p1["severity"] == "critical"
    assert p1["safety_factor_complete"] is True and p1["yield_criterion"] == "von_mises"
    assert p1["von_mises_cov"] == pytest.approx(statistics.pstdev([100, 250, 160]) / statistics.fmean([100, 250, 160]))
    assert p1["n_runs_measured"] == 3
    # 파트 2: 한계는 σ1 인데 σ1 을 잰 런이 없다 → 안전율을 못 낸다. 가속도 70,000 G → warning
    assert "min_safety_factor" not in p2 and p2["severity"] == "warning" and p2["worst_g_run"] == "run/Run_B"
    # 바닥(23)은 응답이 없다 — 판정 unknown, 잰 런 0
    assert parts["part/23"]["severity"] == "unknown" and parts["part/23"]["n_runs_measured"] == 0
    camp = _objs(doc, "cae_campaign")["campaign"]
    assert camp["yield_source"] == "dropset_part_yield" and camp["unit_system"] == "ton_mm_s"


def test_incomplete_limits_warn_instead_of_critical(tmp_path):
    # 한계 둘 중 σ1 을 못 잰 런뿐 — 남은 von Mises 한계로 sf<1 이어도 불완전이라 warning (분석기 규칙)
    td = _test_dir(tmp_path, {"1": {"limits": [{"value": 200.0, "criterion": "von_mises"},
                                               {"value": 100.0, "criterion": "max_principal"}]}})
    rep = _report()
    for r in rep["results_summary"]:
        r["parts"]["1"].pop("peak_principal_stress", None)
    p1 = _objs(sphere.build(rep, test_dir=td, contact_map=_cmap()), "cae_part")["part/1"]
    assert p1["min_safety_factor"] == pytest.approx(0.8)
    assert p1["safety_factor_complete"] is False and p1["severity"] == "warning"


def test_no_limits_never_claims_ok():
    doc = sphere.build(_report(), contact_map=_cmap())
    p1 = _objs(doc, "cae_part")["part/1"]
    assert "min_safety_factor" not in p1 and p1["severity"] == "unknown"
    assert _objs(doc, "cae_campaign")["campaign"]["yield_source"] == "none"


def test_responses_runs_and_energy():
    doc = sphere.build(_report(), contact_map=_cmap())
    runs = _objs(doc, "cae_run")
    assert runs["run/Run_B"]["impact_dir_x"] == pytest.approx(1.0) and runs["run/Run_A"]["angle_category"] == "face"
    resp = _objs(doc, "cae_part_response")
    assert set(resp) == {"resp/Run_A/1", "resp/Run_A/2", "resp/Run_B/1", "resp/Run_B/2", "resp/Run_C/1"}
    a1 = resp["resp/Run_A/1"]
    assert a1["peak_von_mises"] == 100.0 and a1["peak_max_principal"] == 90.0
    assert a1["peak_plastic_strain"] == 0.002          # 옛 이름 peak_strain 에서
    assert a1["peak_internal_energy"] == 5.0 and a1["final_internal_energy"] == 2.5
    assert "peak_kinetic_energy" not in a1             # None 은 싣지 않는다
    assert ("cae_part_response", "resp/Run_A/1") in {s for s, _, _ in _rels(doc, "response_in")}


def test_transfers_and_load_paths():
    doc = sphere.build(_report(), contact_map=_cmap())
    x = _objs(doc, "cae_load_transfer")
    assert set(x) == {"xfer/Run_A/2", "xfer/Run_A/10", "xfer/Run_A/99", "xfer/Run_B/10"}
    a10 = x["xfer/Run_A/10"]
    assert a10["from_part"] == "part/1" and a10["to_part"] == "part/2" and a10["propagation_depth"] == 2
    assert a10["first_engage_time"] == 2e-5 and a10["contact"] == "contact/10"
    a99 = x["xfer/Run_A/99"]
    assert "to_part" not in a99 and a99["unresolved_side"] == "iface:99" and "total_work" not in a99
    contacts = _objs(doc, "cae_contact")
    assert contacts["contact/10"]["contact_card"].startswith("*CONTACT_TIED")
    assert "contact_card" not in contacts["contact/99"]          # 덱에서 못 푼 접촉 — 엣지가 말한 것만
    sides = {(s[1], d[1], p["role"]) for s, d, p in _rels(doc, "contact_side")}
    assert ("contact/10", "part/1", "slave") in sides and ("contact/2", "part/23", "master") in sides
    paths = _objs(doc, "cae_load_path")
    assert set(paths) == {"path/1-23", "path/1-2"}
    p12 = paths["path/1-2"]
    assert p12["n_runs_engaged"] == 2 and p12["engage_ratio"] == 1.0
    assert (p12["n_runs_a_to_b"], p12["n_runs_b_to_a"]) == (1, 1)
    assert p12["impulse_max"] == 0.3 and p12["impulse_max_run"] == "run/Run_B"
    assert p12["impulse_median"] == pytest.approx(0.2) and p12["impulse_p90"] == pytest.approx(0.28)
    ends = {d[1] for s, d, _ in _rels(doc, "path_between") if s[1] == "path/1-2"}
    assert ends == {"part/1", "part/2"}


def test_findings_point_at_parts():
    doc = sphere.build(_report(), contact_map=_cmap())
    f = _objs(doc, "cae_finding")
    assert f["finding/1"]["severity"] == "critical" and "detail" not in f["finding/2"]
    assert _rels(doc, "finding_about") == [(("cae_finding", "finding/1"), ("cae_part", "part/1"), {})]


def test_hotspots_hang_on_responses():
    rep = _report()
    rep["results_summary"][2]["hotspot_clusters"] = [
        {"part_id": 2, "criterion": "max_principal", "element_type": "solid", "clusters": [
            {"rank": 1, "element_count": 20, "center": [1.0, 2.0, 3.0], "radius_enclosing": 3.0,
             "stress_mean": 98.7, "stress_max": 173.5, "peak_element_id": 11476, "peak_time": 2.1e-5}]}]
    doc = sphere.build(rep, contact_map=_cmap())
    hs = _objs(doc, "cae_hotspot")
    h = hs["hs/Run_C/2/max_principal/solid/1"]
    assert h["response"] == "resp/Run_C/2" and h["center_z"] == 3.0 and h["stress_max"] == 173.5
    # Run_C 파트 2 는 응답 값이 없었다 — 군집이 매달릴 빈 응답이 선다
    assert _objs(doc, "cae_part_response")["resp/Run_C/2"] == {"run": "run/Run_C", "part": "part/2"}


def test_si_deck_is_normalized_but_g_and_ratio_are_not(tmp_path):
    rep = _report("SI")
    for r in rep["results_summary"]:
        for pd in r["parts"].values():
            if "peak_stress" in pd:
                pd["peak_stress"] *= 1e6          # Pa
                pd["peak_disp"] /= 1e3            # m
    td = _test_dir(tmp_path, {"1": {"limits": [{"value": 200e6, "criterion": "von_mises"}]}})
    doc = sphere.build(rep, test_dir=td, contact_map=_cmap())
    p1 = _objs(doc, "cae_part")["part/1"]
    assert p1["worst_von_mises"] == pytest.approx(250.0) and p1["yield_limit"] == pytest.approx(200.0)
    assert p1["min_safety_factor"] == pytest.approx(0.8)          # 비율은 덱 단위에서 셈해 그대로
    assert _objs(doc, "cae_part_response")["resp/Run_A/1"]["peak_displacement"] == pytest.approx(1.5)
    assert _objs(doc, "cae_part_response")["resp/Run_A/1"]["peak_g"] == 1000.0
    assert doc["units"]["system"] == "si" and doc["units"]["deck_labels"]["stress"] == "Pa"


def test_old_report_without_units_keeps_raw_values():
    rep = _report()
    del rep["unit_system"], rep["unit_labels"]
    doc = sphere.build(rep, contact_map=_cmap())
    camp = _objs(doc, "cae_campaign")["campaign"]
    assert camp["unit_system"] == "unknown" and camp["values_normalized"] is False
    assert "옛 산출물" in camp["unit_note"]
