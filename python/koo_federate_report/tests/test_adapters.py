# 어댑터 검증 — 합성 최소 sidecar → RevisionBundle 정규화, kind 판별/혼합 금지
from __future__ import annotations

import json

import pytest

from koo_federate_report import load_bundles
from koo_federate_report.adapters import AdapterError, detect_kind, load_bundle
from koo_federate_report.adapters.impact import to_bundle as impact_bundle
from koo_federate_report.adapters.sphere import to_bundle as sphere_bundle
from koo_federate_report.config import parse_config

from .helpers import minimal_impact_sidecar, minimal_sphere_sidecar


# --------------------------------------------------------------------------
# impact
# --------------------------------------------------------------------------
def test_impact_bundle_shape():
    b = impact_bundle(minimal_impact_sidecar(), path="/x/impact_payload.json", label="RevA")
    assert b.kind == "impact" and b.label == "RevA" and b.schema_version == 1
    assert [c.key for c in b.cells] == ["P1", "P2"]
    assert b.parts == {1: "Display\\Display", 2: "PCB\\PCB"}
    assert b.unit_labels["stress"] == "MPa"
    assert b.meta["project"] == "SYN"
    assert b.provenance["tool"] == "koo_impact_report"
    assert len(b.findings) == 1


def test_impact_cell_metrics_and_coords():
    b = impact_bundle(minimal_impact_sidecar())
    p2 = b.cell_by_key("P2")
    assert (p2.x, p2.y, p2.category) == (10.0, 0.0, "F5")
    assert p2.metrics == {"g": 200.0, "s": 20.0, "e": 2e-3, "d": 0.4}
    assert p2.behavior == "bounce"
    assert p2.energy["ke_retention"] == 0.3
    assert p2.energy["diss_pct"] == 41.2


def test_impact_trust_rule():
    """ok = (impact_visible is not False) and pass_fail != 'FAIL'."""
    raw = minimal_impact_sidecar()
    b = impact_bundle(raw)
    assert b.cell_by_key("P1").trust.ok is False  # impact_visible=False
    assert "impact_visible" in b.cell_by_key("P1").trust.reason
    assert b.cell_by_key("P2").trust.ok is True
    assert b.trust["n_gated"] == 1 and b.trust["n_ok"] == 1

    raw["payload"]["solver_quality"]["per_position"]["P2"]["pass_fail"] = "FAIL"
    raw["payload"]["solver_quality"]["per_position"]["P2"]["flags"] = ["TE_drift>=5.0%"]
    b2 = impact_bundle(raw)
    assert b2.cell_by_key("P2").trust.ok is False
    assert "TE_drift" in b2.cell_by_key("P2").trust.reason


def test_impact_trust_without_solver_quality():
    raw = minimal_impact_sidecar()
    raw["payload"]["solver_quality"] = {}
    b = impact_bundle(raw)
    assert all(c.trust.ok for c in b.cells)
    assert b.cell_by_key("P1").trust.reason == "no gate"


def test_impact_part_cells():
    b = impact_bundle(minimal_impact_sidecar())
    assert b.part_cells[("P1", "Display\\Display")]["g"] == 100.0
    assert b.part_metric("P2", "PCB\\PCB", "s") == 16.0
    assert b.part_metric("P2", "없는파트", "g") is None


def test_impact_position_metrics_fallback():
    raw = minimal_impact_sidecar()
    raw["payload"]["doe_analysis"]["position_metrics"] = {}
    b = impact_bundle(raw)
    # results 에서 위치별 최대치를 직접 집계
    assert b.cell_by_key("P2").metrics["g"] == 200.0
    assert b.cell_by_key("P1").metrics["s"] == 10.0


def test_impact_missing_payload():
    with pytest.raises(ValueError, match="payload"):
        impact_bundle({"schema_version": 1})


# --------------------------------------------------------------------------
# sphere
# --------------------------------------------------------------------------
def test_sphere_bundle_shape():
    b = sphere_bundle(minimal_sphere_sidecar(), path="/x/report.json", label="S1")
    assert b.kind == "sphere" and b.label == "S1"
    assert [c.key for c in b.cells] == ["F1_Back", "C1_Corner"]
    assert b.parts == {1: "Display\\Display", 2: "PCB\\PCB"}
    assert b.meta["project"] == "SYN_SPHERE"
    assert b.kpi["worst_g"] == 1500.0


def test_sphere_cell_aggregation_and_angles():
    b = sphere_bundle(minimal_sphere_sidecar())
    c = b.cell_by_key("C1_Corner")
    assert (c.roll, c.pitch, c.yaw) == (45.0, 45.0, 0.0)
    assert c.category == "corner"
    # 파트 피크의 최대치가 셀 값
    # 지표가 9종으로 늘었다(주응력·주변형률 5종 추가). 상류에 없으면 None 이며
    # 그 지표로 비교하면 전 셀이 미판정이 된다 — 0 으로 채우지 않는다.
    assert {k: c.metrics[k] for k in ("g", "s", "e", "d")} == {
        "g": 1500.0, "s": 30.0, "e": 0.003, "d": 1.2}
    assert all(c.metrics[k] is None for k in ("s1", "s3", "e1", "e3", "evm"))
    assert b.part_metric("C1_Corner", "PCB\\PCB", "g") == 1300.0


def test_sphere_trust_always_ok():
    b = sphere_bundle(minimal_sphere_sidecar())
    assert all(c.trust.ok for c in b.cells)
    assert all(c.trust.reason == "no gate" for c in b.cells)
    assert b.trust["n_gated"] == 0


def test_sphere_missing_results_summary():
    with pytest.raises(ValueError, match="results_summary"):
        sphere_bundle({"project_name": "x"})


# --------------------------------------------------------------------------
# kind 판별 / 혼합 금지
# --------------------------------------------------------------------------
def test_detect_kind():
    assert detect_kind(minimal_impact_sidecar()) == "impact"
    assert detect_kind(minimal_sphere_sidecar()) == "sphere"
    with pytest.raises(AdapterError, match="판별할 수 없습니다"):
        detect_kind({"hello": 1}, path="/x.json")


def test_detect_kind_without_generated_by():
    raw = minimal_impact_sidecar()
    del raw["generated_by"]
    assert detect_kind(raw) == "impact"


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_load_bundle_kind_conflict(tmp_path):
    p = _write(tmp_path, "a.json", minimal_impact_sidecar())
    with pytest.raises(AdapterError, match="sphere sidecar 입니다|impact sidecar 입니다"):
        load_bundle(p, kind="sphere")


def test_load_bundle_bad_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(AdapterError, match="JSON 파싱 실패"):
        load_bundle(str(p))


def test_mixed_kinds_rejected(tmp_path):
    a = _write(tmp_path, "a.json", minimal_impact_sidecar())
    s = _write(tmp_path, "s.json", minimal_sphere_sidecar())
    cfg = parse_config({"reports": [{"path": a, "label": "I"}, {"path": s, "label": "S"}]})
    with pytest.raises(AdapterError, match="비교할 수 없습니다"):
        load_bundles(cfg)


def test_load_bundles_ok(tmp_path):
    a = _write(tmp_path, "a.json", minimal_impact_sidecar())
    b = _write(tmp_path, "b.json", minimal_impact_sidecar())
    cfg = parse_config({"baseline": 2, "reports": [{"path": a, "label": "A"},
                                                   {"path": b, "label": "B"}]})
    fset = load_bundles(cfg)
    assert fset.kind == "impact"
    assert fset.baseline_idx == 1
    assert fset.labels() == ["A", "B"]
    assert fset.baseline.label == "B"


def test_sphere_acc_unit_is_G_not_MG():
    """peak_g 는 G 로 저장된다 — MG 라벨은 1e6 배 과대 표기를 만든다.

    구면 보고서 화면의 "MG" 는 표시할 때 v/1e6 을 한 결과지 저장 단위가 아니다.
    라벨을 MG 로 달면 나누지 않은 값(1.45e6)에 MG 가 붙어 1.45e12 G 로 읽힌다.
    """
    b = sphere_bundle(minimal_sphere_sidecar(), path="/x/report.json", label="RevA")
    assert b.unit_labels["acc"] == "G"


def test_sphere_report_units_win_over_defaults():
    """보고서가 단위를 실어오면 그것이 이긴다 (기본값은 부재 시 보완일 뿐)."""
    raw = minimal_sphere_sidecar()
    raw["unit_labels"] = {"acc": "mm/s²", "stress": "Pa"}
    b = sphere_bundle(raw, path="/x/report.json", label="RevA")
    assert b.unit_labels["acc"] == "mm/s²" and b.unit_labels["stress"] == "Pa"
