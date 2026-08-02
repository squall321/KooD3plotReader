# federate.yaml 스키마 검증 테스트 — 잘못된 입력이 친절한 에러로 막히는지
from __future__ import annotations

import os

import pytest

from koo_federate_report.config import ConfigError, load_config, parse_config

BASE = {
    "kind": "impact",
    "baseline": 1,
    "output": "out.html",
    "reports": [
        {"path": "a.json", "label": "RevA"},
        {"path": "b.json", "label": "RevB"},
    ],
}


def test_minimal_valid():
    cfg = parse_config(dict(BASE))
    assert cfg.kind == "impact"
    assert cfg.baseline == 1 and cfg.baseline_idx == 0
    assert [r.label for r in cfg.reports] == ["RevA", "RevB"]
    # options 기본값
    assert cfg.options.auto_match_identical is True
    assert cfg.options.name_normalize is True
    assert cfg.options.unmatched == "show"
    assert cfg.options.resample == "nearest"
    assert cfg.options.trust_gate is True
    assert cfg.options.unit_policy == "error"


def test_reports_as_bare_strings():
    cfg = parse_config({**BASE, "reports": ["a.json", "b.json", "c.json"]})
    assert cfg.n_revisions == 3
    assert cfg.reports[2].path == "c.json"


def test_empty_config():
    with pytest.raises(ConfigError, match="비어 있습니다"):
        parse_config({})


def test_unknown_top_key():
    with pytest.raises(ConfigError, match="알 수 없는 키"):
        parse_config({**BASE, "baselines": 1})


def test_bad_kind():
    with pytest.raises(ConfigError, match="kind"):
        parse_config({**BASE, "kind": "drop"})


def test_reports_needs_two():
    with pytest.raises(ConfigError, match="최소 2개"):
        parse_config({**BASE, "reports": [{"path": "a.json"}]})


def test_report_missing_path():
    with pytest.raises(ConfigError, match="2번째"):
        parse_config({**BASE, "reports": [{"path": "a.json"}, {"label": "no path"}]})


def test_report_unknown_key():
    with pytest.raises(ConfigError, match="1번째"):
        parse_config({**BASE, "reports": [{"path": "a.json", "color": "red"},
                                          {"path": "b.json"}]})


def test_baseline_range():
    with pytest.raises(ConfigError, match=r"1\.\.2"):
        parse_config({**BASE, "baseline": 3})
    with pytest.raises(ConfigError, match=r"1\.\.2"):
        parse_config({**BASE, "baseline": 0})


def test_baseline_type():
    with pytest.raises(ConfigError, match="1-based 정수"):
        parse_config({**BASE, "baseline": "RevA"})


def test_option_enum():
    with pytest.raises(ConfigError, match="options.resample"):
        parse_config({**BASE, "options": {"resample": "spline"}})
    with pytest.raises(ConfigError, match="options.unmatched"):
        parse_config({**BASE, "options": {"unmatched": "maybe"}})
    with pytest.raises(ConfigError, match="options.unit_policy"):
        parse_config({**BASE, "options": {"unit_policy": "ignore"}})


def test_option_bool():
    with pytest.raises(ConfigError, match="true/false"):
        parse_config({**BASE, "options": {"trust_gate": "yes"}})


def test_option_unknown_key():
    with pytest.raises(ConfigError, match="options 에 알 수 없는 키"):
        parse_config({**BASE, "options": {"resamples": "off"}})


def test_parts_table_parsing():
    cfg = parse_config({**BASE, "parts": {"Display": "Display\\Display, DISP_MAIN",
                                          "Battery": "BAT\\Cell, ~"}})
    assert cfg.parts["Display"] == ["Display\\Display", "DISP_MAIN"]
    assert cfg.parts["Battery"] == ["BAT\\Cell", None]


def test_parts_table_list_form():
    cfg = parse_config({**BASE, "parts": {"Display": ["Display\\Display", None]}})
    assert cfg.parts["Display"] == ["Display\\Display", None]


def test_parts_count_mismatch():
    with pytest.raises(ConfigError, match="3개인데 reports 는 2개"):
        parse_config({**BASE, "parts": {"Display": "a, b, c"}})


def test_load_config_resolves_paths_and_labels(tmp_path):
    (tmp_path / "revA").mkdir()
    (tmp_path / "revB").mkdir()
    (tmp_path / "revA" / "s.json").write_text("{}")
    (tmp_path / "revB" / "s.json").write_text("{}")
    yaml_text = (
        "kind: auto\n"
        "baseline: 2\n"
        "output: rep.html\n"
        "reports:\n"
        "  - path: revA/s.json\n"
        "  - path: revB/s.json\n"
        "    label: 'B 라벨'\n"
    )
    cfg_path = tmp_path / "federate.yaml"
    cfg_path.write_text(yaml_text, encoding="utf-8")
    cfg = load_config(str(cfg_path))
    assert cfg.reports[0].path == str(tmp_path / "revA" / "s.json")
    assert cfg.reports[0].label == "revA"  # 디렉터리명 fallback
    assert cfg.reports[1].label == "B 라벨"
    assert cfg.baseline_idx == 1
    assert os.path.isabs(cfg.output)


def test_load_config_missing_sidecar(tmp_path):
    cfg_path = tmp_path / "federate.yaml"
    cfg_path.write_text(
        "reports:\n  - path: nope.json\n  - path: nope2.json\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="1번째 sidecar 파일이 없습니다"):
        load_config(str(cfg_path))


def test_load_config_missing_file():
    with pytest.raises(ConfigError, match="찾을 수 없습니다"):
        load_config("/nonexistent/federate.yaml")


def test_load_config_bad_yaml(tmp_path):
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text("reports: [\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML 문법 오류"):
        load_config(str(cfg_path))
