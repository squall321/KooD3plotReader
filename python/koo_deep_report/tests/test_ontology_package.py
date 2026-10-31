# 온톨로지 어휘·꾸러미 작성기 시험 — 어휘 정본과 docs 사본 일치, DynaForge 검증기 통과, 검증·단위 환산
import importlib.util
import json
from pathlib import Path

import pytest

from koo_deep_report.ontology import package as P
from koo_deep_report.ontology import vocabulary as V

_REPO = Path(__file__).resolve().parents[3]
_DOCS_JSON = _REPO / "docs" / "ontology_2026-10" / "dynaforge-cae.draft.json"
_DF_VALIDATOR = Path("/home/koopark/claude/KooRemapper/platform/backend/app/runner/ontology_def.py")


def test_docs_copy_is_generated_from_module():
    # docs 의 JSON 은 사람이 고치지 않는다 — `python3 -m koo_deep_report.ontology vocab <파일>` 로 뽑는다
    assert _DOCS_JSON.read_text(encoding="utf-8") == V.dumps()


@pytest.mark.skipif(not _DF_VALIDATOR.exists(), reason="DynaForge 저장소가 이 머신에 없다")
def test_dynaforge_validator_accepts_vocabulary():
    spec = importlib.util.spec_from_file_location("ontology_def", _DF_VALIDATOR)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    rep = m.validate(json.loads(V.dumps()))
    assert rep.faults == [] and rep.notes == []
    core = json.loads((_DF_VALIDATOR.parents[3] / "core" / "ontology" / "dynaforge-core.json").read_text())
    merged = json.loads(V.dumps())
    merged["groups"] += core["groups"]
    merged["types"] += core["types"]
    merged["relation_types"] += core["relation_types"]
    rep = m.validate(merged)
    assert rep.faults == [] and rep.notes == []


def test_units_on_vocabulary_are_known():
    for t in V.VOCABULARY["types"]:
        for p in t["properties"]:
            u = p.get("unit")
            assert u is None or u in V.UNIT_KINDS or u in ("deg", "G"), (t["slug"], p["key"], u)


def test_ref_relations_match_property_targets():
    types = V.types_by_slug()
    rels = V.relations_by_slug()
    for (t, k), r in V.REF_RELATIONS.items():
        prop = {p["key"]: p for p in types[t]["properties"]}[k]
        assert prop["data_type"] == "object_ref"
        assert t in rels[r]["src_type_slugs"] and prop["ref_type_slug"] in rels[r]["dst_type_slugs"]


def _pkg(system="ton-mm-s"):
    return P.Package(scenario_kind="drop_all_angle", units=P.Units(system), adapter="test")


def _campaign(pkg):
    pkg.add("cae_campaign", "campaign", "c", {"scenario_kind": "drop_all_angle", "unit_system": pkg.units.system})


def test_si_values_are_converted_to_vocabulary_units():
    pkg = _pkg("SI")
    _campaign(pkg)
    pkg.add("cae_run", "run/r1", "r1", {"campaign": "campaign", "case_key": "r1"})
    pkg.add("cae_part", "part/1", "p", {"campaign": "campaign", "part_id": 1})
    pkg.add("cae_part_response", "resp/r1/1", "x", {
        "run": "run/r1", "part": "part/1",
        "peak_von_mises": 2.5e8,          # Pa → 250 MPa
        "peak_displacement": 0.004,       # m → 4 mm
        "peak_internal_energy": 1.2,      # J → 1200 mJ
        "peak_von_mises_time": 0.002,     # s 그대로
        "peak_g": 1234.0,                 # G — 바꾸지 않는다
        "peak_plastic_strain": 0.01,      # 무차원
    })
    doc = pkg.finish()
    r = next(o for o in doc["objects"] if o["type"] == "cae_part_response")["properties"]
    assert r["peak_von_mises"] == pytest.approx(250.0)
    assert r["peak_displacement"] == pytest.approx(4.0)
    assert r["peak_internal_energy"] == pytest.approx(1200.0)
    assert r["peak_von_mises_time"] == 0.002 and r["peak_g"] == 1234.0 and r["peak_plastic_strain"] == 0.01
    assert doc["units"] == {"system": "si", "normalized": True, "factors": P._FACTORS["si"],
                            "deck_labels": {}, "note": ""}


def test_unknown_units_keep_raw_values():
    pkg = _pkg("")
    assert pkg.units.system == "unknown" and not pkg.units.normalized
    assert pkg.units.convert("MPa", 2.5e8) == 2.5e8


def test_ref_properties_draw_their_relations_and_none_is_dropped():
    pkg = _pkg()
    _campaign(pkg)
    pkg.add("cae_run", "run/r1", "r1", {"campaign": "campaign", "case_key": "r1", "end_time": None})
    doc = pkg.finish()
    run = next(o for o in doc["objects"] if o["type"] == "cae_run")
    assert "end_time" not in run["properties"]
    assert doc["relations"] == [{"relation": "run_of", "src": ["cae_run", "run/r1"],
                                 "dst": ["cae_campaign", "campaign"], "properties": {}}]
    assert doc["counts"] == {"objects": {"cae_campaign": 1, "cae_run": 1}, "relations": {"run_of": 1}}


def test_faults_are_collected_not_first_only():
    pkg = _pkg()
    _campaign(pkg)
    pkg.add("cae_run", "run/r1", "r1", {"campaign": "campaign", "case_key": "r1",
                                        "no_such": 1, "angle_category": "diagonal", "num_states": True})
    pkg.add("cae_run", "run/r2", "r2", {"campaign": "campaign"})               # case_key 빠짐
    pkg.add("cae_part_response", "resp/x", "x", {"run": "run/zz", "part": "part/9"})   # 가리킬 곳 없음
    pkg.add("cae_nothing", "k", "k", {})
    with pytest.raises(P.PackageError) as ei:
        pkg.finish()
    text = "\n".join(ei.value.faults)
    for frag in ("어휘에 없는 속성 'no_such'", "열거값 밖('diagonal')", "수가 아니다(True)",
                 "필수 속성 'case_key'", "run/zz", "part/9", "어휘에 없는 타입"):
        assert frag in text, frag


def test_report_ref_is_left_for_dynaforge():
    # 캠페인의 report(→ impact_report)는 필수지만 만드는 쪽은 리포트 키를 모른다
    pkg = _pkg()
    _campaign(pkg)
    doc = pkg.finish()
    assert "report" not in doc["objects"][0]["properties"]


def test_write_is_atomic_and_compact(tmp_path):
    pkg = _pkg()
    _campaign(pkg)
    out = P.write(pkg.finish(), tmp_path / "o.json")
    assert json.loads(out.read_text())["format"] == "dynaforge.onto_package"
    assert not (tmp_path / "o.json.tmp").exists()
