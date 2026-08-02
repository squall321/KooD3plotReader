# 파트 매칭 테스트 — 매칭표/auto/normalize/충돌/부재/unmatched 정책
from __future__ import annotations

import pytest

from koo_federate_report.config import Options
from koo_federate_report.matching import MatchingError, build_matching, normalize_name

from .helpers import make_impact_bundle

CELLS = [("P1", 0.0, 0.0, "F5", 100.0, True, "bounce")]


def _bundle(label, parts):
    return make_impact_bundle(label, CELLS, parts)


def test_normalize_name():
    assert normalize_name("Display\\Display") == "display/display"
    assert normalize_name("  PKG / PKG 1 ") == "pkg/pkg 1"
    assert normalize_name("Display\\Display", enabled=False) == "Display\\Display"


def test_auto_match_identical():
    a = _bundle("A", {1: "Display\\Display", 2: "PCB\\PCB"})
    b = _bundle("B", {1: "Display\\Display", 2: "PCB\\PCB"})
    m = build_matching([a, b], {}, Options())
    assert sorted(m.canonicals) == ["Display\\Display", "PCB\\PCB"]
    assert all(m.source[c] == "auto" for c in m.canonicals)
    assert m.per_rev["PCB\\PCB"] == ["PCB\\PCB", "PCB\\PCB"]
    assert m.unmatched == [[], []]


def test_normalize_makes_them_match():
    a = _bundle("A", {1: "Display\\Display"})
    b = _bundle("B", {1: "display/DISPLAY"})
    m = build_matching([a, b], {}, Options(name_normalize=True))
    assert len(m.canonicals) == 1
    assert m.per_rev[m.canonicals[0]] == ["Display\\Display", "display/DISPLAY"]

    m2 = build_matching([a, b], {}, Options(name_normalize=False, unmatched="show"))
    assert m2.canonicals == []
    assert m2.unmatched == [["Display\\Display"], ["display/DISPLAY"]]


def test_table_beats_auto():
    """표가 자동 매칭과 충돌하면 표가 이긴다 (명시 > 암묵)."""
    a = _bundle("A", {1: "Display\\Display", 2: "PCB\\PCB"})
    b = _bundle("B", {1: "Display\\Display", 2: "PCB\\PCB"})
    table = {"교차": ["Display\\Display", "PCB\\PCB"]}
    m = build_matching([a, b], table, Options())
    assert m.per_rev["교차"] == ["Display\\Display", "PCB\\PCB"]
    assert m.source["교차"] == "table"
    # 표가 선점한 이름은 자동 풀에서 빠지고, 남은 것끼리 자동 매칭된다
    autos = [c for c in m.canonicals if m.source[c] == "auto"]
    assert autos == []
    assert m.unmatched == [["PCB\\PCB"], ["Display\\Display"]]


def test_table_renamed_parts():
    """이름이 바뀐 파트는 매칭표로만 이어진다."""
    a = _bundle("A", {1: "Display\\Display", 2: "PCB\\PCB", 3: "Front\\Metal"})
    b = _bundle("B", {1: "DISP_MAIN", 2: "MainPCB", 3: "Front\\Metal"})
    table = {"Display": "Display\\Display, DISP_MAIN", "PCB": "PCB\\PCB, MainPCB"}
    m = build_matching([a, b], {k: v.split(", ") for k, v in table.items()}, Options())
    assert m.per_rev["Display"] == ["Display\\Display", "DISP_MAIN"]
    assert m.per_rev["PCB"] == ["PCB\\PCB", "MainPCB"]
    assert m.per_rev["Front\\Metal"] == ["Front\\Metal", "Front\\Metal"]
    assert m.source["Front\\Metal"] == "auto"
    assert m.unmatched == [[], []]


def test_absent_part_marked_none():
    a = _bundle("A", {1: "BAT\\Cell", 2: "Front\\Metal"})
    b = _bundle("B", {1: "Front\\Metal"})
    m = build_matching([a, b], {"Battery": ["BAT\\Cell", None]}, Options())
    assert m.per_rev["Battery"] == ["BAT\\Cell", None]
    assert m.presence("Battery") == [True, False]


def test_table_name_not_found_warns():
    a = _bundle("A", {1: "Front\\Metal"})
    b = _bundle("B", {1: "Front\\Metal"})
    m = build_matching([a, b], {"X": ["없는파트", "Front\\Metal"]}, Options())
    assert m.per_rev["X"] == [None, "Front\\Metal"]
    codes = [w["code"] for w in m.warnings]
    assert "part_not_found" in codes


def test_duplicate_claim_warns():
    a = _bundle("A", {1: "Front\\Metal"})
    b = _bundle("B", {1: "Front\\Metal"})
    table = {"X": ["Front\\Metal", "Front\\Metal"], "Y": ["Front\\Metal", "Front\\Metal"]}
    m = build_matching([a, b], table, Options())
    assert m.per_rev["X"] == ["Front\\Metal", "Front\\Metal"]
    assert m.per_rev["Y"] == [None, None]
    assert "duplicate_claim" in [w["code"] for w in m.warnings]


def test_single_revision_part_is_unmatched():
    a = _bundle("A", {1: "Front\\Metal", 2: "OnlyInA"})
    b = _bundle("B", {1: "Front\\Metal"})
    m = build_matching([a, b], {}, Options())
    assert m.unmatched == [["OnlyInA"], []]
    assert "unmatched_parts" in [w["code"] for w in m.warnings]


def test_unmatched_error_policy():
    a = _bundle("A", {1: "Front\\Metal", 2: "OnlyInA"})
    b = _bundle("B", {1: "Front\\Metal"})
    with pytest.raises(MatchingError, match="OnlyInA"):
        build_matching([a, b], {}, Options(unmatched="error"))


def test_auto_match_disabled():
    a = _bundle("A", {1: "Front\\Metal"})
    b = _bundle("B", {1: "Front\\Metal"})
    m = build_matching([a, b], {}, Options(auto_match_identical=False))
    assert m.canonicals == []
    assert m.unmatched == [["Front\\Metal"], ["Front\\Metal"]]


def test_three_revisions_partial_presence():
    a = _bundle("A", {1: "Display\\Display", 2: "BAT\\Cell"})
    b = _bundle("B", {1: "DISP_MAIN", 2: "BAT\\Cell"})
    c = _bundle("C", {1: "Display\\Display"})
    table = {"Display": ["Display\\Display", "DISP_MAIN", "Display\\Display"],
             "Battery": ["BAT\\Cell", "BAT\\Cell", None]}
    m = build_matching([a, b, c], table, Options())
    assert m.presence("Display") == [True, True, True]
    assert m.presence("Battery") == [True, True, False]
    assert m.unmatched == [[], [], []]
