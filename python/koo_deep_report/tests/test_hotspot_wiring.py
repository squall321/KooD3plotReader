# 핫스팟 기준 7종·시간 집계가 CLI·YAML 에서 엔진까지 배선되는지 검증하는 시험
"""koo_deep_report → unified_analyzer 핫스팟 배선 시험.

엔진에 기준(max_shear, x/y/z_tension)과 time_aggregate 를 더한 커밋이 파이썬
쪽 허용 목록을 몰라, deep report 가 엔진이 아는 이름을 "알 수 없는 기준량" 으로
거절했다(요청서 docs/requests/hotspot-wiring-request-2026-10-16.md). 같은 목록이
두 곳에 있으면 다시 어긋나므로, 허용 목록은 엔진 --capabilities 에서 읽고
별칭은 C++ 파서 소스와 대조한다.
"""
import argparse
import json
import re
import stat
from pathlib import Path

import pytest

from koo_deep_report import __main__ as M
from koo_deep_report.core import d3plot_reader as R

REPO = Path(__file__).resolve().parents[3]
CPP = REPO / "src" / "analysis" / "HotspotClusterAnalyzer.cpp"
SEVEN = ("von_mises", "max_principal", "min_principal", "max_shear",
         "x_tension", "y_tension", "z_tension")
AGGS = ("elemmax_then_mean", "mean_then_timemax", "both")


@pytest.fixture(autouse=True)
def _fresh_caps():
    M._engine_hotspot_caps.cache_clear()
    yield
    M._engine_hotspot_caps.cache_clear()


def _no_engine(monkeypatch):
    monkeypatch.setattr(M, "find_unified_analyzer", lambda install_dir=None: None)


def _fake_engine(monkeypatch, tmp_path, criteria, aggs):
    exe = tmp_path / "unified_analyzer"
    body = json.dumps({"tool": "unified_analyzer",
                       "hotspot": {"criteria": list(criteria), "time_aggregate": list(aggs)}})
    exe.write_text(f"#!/bin/sh\ncat <<'EOF'\n{body}\nEOF\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(M, "find_unified_analyzer", lambda install_dir=None: exe)


def _args(argv):
    p = argparse.ArgumentParser()
    M._add_single_args(p)
    return p.parse_args(argv)


# ── 기준 이름 ────────────────────────────────────────────────

def test_seven_criteria_accepted(monkeypatch):
    _no_engine(monkeypatch)
    allowed, _ = M._engine_hotspot_caps(None)
    for name in SEVEN:
        assert M._normalize_criteria(name, allowed) == name
    assert M._normalize_criteria("max_shear, x_tension", allowed) == "max_shear,x_tension"


def test_unknown_criterion_rejected_with_allowed_list(monkeypatch, capsys):
    _no_engine(monkeypatch)
    allowed, _ = M._engine_hotspot_caps(None)
    with pytest.raises(SystemExit) as e:
        M._normalize_criteria("max_shaer", allowed)
    assert "max_shaer" in str(e.value) and "max_shear" in str(e.value)


def _engine_aliases() -> dict[str, str]:
    """parseHotspotCriterion 소스에서 (별칭 → 표준 이름) 표를 뽑는다."""
    src = CPP.read_text(encoding="utf-8")
    body = src[src.index("bool parseHotspotCriterion("):src.index("const char* hotspotCriterionName(")]
    names_src = src[src.index("const char* hotspotCriterionName("):]
    names_src = names_src[:names_src.index("\n}\n")]
    enum2name = dict(re.findall(r'case HotspotCriterion::(\w+):\s*return "(\w+)";', names_src))
    out: dict[str, str] = {}
    for chunk in body.split("return true; }")[:-1]:
        enum = re.findall(r"HotspotCriterion::(\w+)", chunk)[-1]
        for alias in re.findall(r'k == "([^"]+)"', chunk):
            out[alias] = enum2name[enum]
    return out


def test_aliases_match_engine_parser(monkeypatch):
    """C++ 파서가 받는 별칭은 파이썬도 같은 기준으로 받고, 그 반대도 같다."""
    _no_engine(monkeypatch)
    eng = _engine_aliases()
    assert set(eng.values()) == set(SEVEN), eng
    for alias, canon in eng.items():
        assert M._normalize_criteria(alias, SEVEN) == canon, alias
    py_only = set(M._HOTSPOT_CRITERION_ALIASES) - set(eng)
    assert not py_only, f"엔진이 모르는 파이썬 별칭: {sorted(py_only)}"


# ── 엔진 --capabilities ─────────────────────────────────────

def test_allowed_list_comes_from_engine(monkeypatch, tmp_path):
    _fake_engine(monkeypatch, tmp_path, ["von_mises", "max_shear"], ["elemmax_then_mean"])
    allowed, aggs = M._engine_hotspot_caps(None)
    assert allowed == ("von_mises", "max_shear") and aggs == ("elemmax_then_mean",)
    with pytest.raises(SystemExit):
        M._normalize_criteria("x_tension", allowed)


def test_fallback_when_engine_missing(monkeypatch, capsys):
    _no_engine(monkeypatch)
    allowed, aggs = M._engine_hotspot_caps(None)
    assert allowed == SEVEN and aggs == AGGS
    assert "--capabilities" in capsys.readouterr().err


def test_builtin_lists_match_built_engine():
    """내장 목록(대체·도움말용)이 실제 엔진과 같다 — 빌드가 있을 때만."""
    exe = R.find_unified_analyzer(None)
    if exe is None:
        pytest.skip("unified_analyzer 빌드 없음")
    allowed, aggs = M._engine_hotspot_caps(None)
    assert allowed == M._HOTSPOT_CRITERIA == SEVEN
    assert aggs == M._HOTSPOT_TIME_AGGREGATES == AGGS


# ── 시간 집계 ───────────────────────────────────────────────

def test_time_aggregate_cli(monkeypatch):
    _no_engine(monkeypatch)
    a = _args(["x", "--hotspot-clusters", "--hotspot-criterion", "tau_max,sxx",
               "--hotspot-time-aggregate", "both"])
    hs = M._build_hotspot_config(a, None)
    assert hs["criterion"] == "max_shear,x_tension" and hs["time_aggregate"] == "both"
    assert M._build_hotspot_config(_args(["x", "--hotspot-clusters"]), None)["time_aggregate"] \
        == "elemmax_then_mean"


def test_time_aggregate_unknown_rejected(monkeypatch):
    _no_engine(monkeypatch)
    a = _args(["x", "--hotspot-clusters", "--hotspot-time-aggregate", "mean"])
    with pytest.raises(SystemExit) as e:
        M._build_hotspot_config(a, None)
    assert "mean_then_timemax" in str(e.value)


def test_engine_yaml_carries_time_aggregate(tmp_path):
    hs = {"enabled": True, "criterion": "max_shear,x_tension", "time_aggregate": "both"}
    y = R._build_yaml(tmp_path / "d3plot", tmp_path, None, None, 1, hotspot=hs)
    block = y[y.index("hotspot_clusters:"):].split("\n\n")[0]
    assert "  criterion: max_shear,x_tension" in block
    assert "  time_aggregate: both" in block
    # 기본값이면 쓰지 않는다 — 옛 엔진은 모르는 키라고 경고한다
    hs["time_aggregate"] = "elemmax_then_mean"
    assert "time_aggregate" not in R._build_yaml(tmp_path / "d3plot", tmp_path, None, None, 1, hotspot=hs)


# ── YAML ────────────────────────────────────────────────────

@pytest.mark.parametrize("block", [
    "  criteria: [max_shear, x_tension]\n",
    "  criteria: max_shear, x_tension\n",
    "  criterion: max_shear,x_tension\n",
    "  criteria:\n    - max_shear\n    - x_tension\n",
    "  criteria:\n    - \"tau_max\"   # 별칭\n    - sxx\n",
])
def test_yaml_criteria_forms(monkeypatch, tmp_path, block):
    _no_engine(monkeypatch)
    cfg = tmp_path / "a.yaml"
    cfg.write_text("hotspot_clusters:\n  enabled: true\n" + block + "  time_aggregate: both\n")
    a = _args(["x", "--config", str(cfg)])
    M._apply_config_to_args(a)
    hs = M._build_hotspot_config(a, None)
    assert hs["criterion"] == "max_shear,x_tension", block
    assert hs["time_aggregate"] == "both"


def test_cli_overrides_yaml_time_aggregate(monkeypatch, tmp_path):
    _no_engine(monkeypatch)
    cfg = tmp_path / "a.yaml"
    cfg.write_text("hotspot_clusters:\n  enabled: true\n  time_aggregate: both\n")
    a = _args(["x", "--config", str(cfg), "--hotspot-time-aggregate", "mean_then_timemax"])
    M._apply_config_to_args(a)
    assert M._build_hotspot_config(a, None)["time_aggregate"] == "mean_then_timemax"


# ── 거절은 분석 전에 ─────────────────────────────────────────

def test_single_rejects_before_reading_files(monkeypatch, tmp_path):
    _no_engine(monkeypatch)
    monkeypatch.setattr(M, "find_files",
                        lambda *a, **k: pytest.fail("이름 검증 전에 파일을 읽었다"))
    a = _args([str(tmp_path), "--hotspot-clusters", "--hotspot-criterion", "bogus",
               "--output", str(tmp_path / "out")])
    with pytest.raises(SystemExit) as e:
        M.run_single(a)
    assert "bogus" in str(e.value)


def test_batch_rejects_before_scanning(monkeypatch, tmp_path):
    _no_engine(monkeypatch)
    from koo_deep_report.core import sim_detector
    monkeypatch.setattr(sim_detector, "find_all",
                        lambda *a, **k: pytest.fail("이름 검증 전에 폴더를 훑었다"))
    a = _args([str(tmp_path), "--hotspot-clusters", "--hotspot-time-aggregate", "bogus",
               "--output", str(tmp_path / "out")])
    with pytest.raises(SystemExit) as e:
        M.run_batch(a)
    assert "bogus" in str(e.value)


# ── 도움말 (MCP 도구 설명의 원천) ────────────────────────────

def test_help_lists_all_names():
    p = argparse.ArgumentParser()
    M._add_single_args(p)
    h = " ".join(p.format_help().split())
    for name in SEVEN + AGGS:
        assert name in h, name
    assert "--hotspot-time-aggregate" in h
