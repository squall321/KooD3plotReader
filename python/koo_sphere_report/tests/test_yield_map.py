# 파트별 항복 한계 — 덱 단위로 비교하고, 못 잰 기준을 조용히 빼지 않는지
"""항복 판정.

**기존 결함 (지금도 틀리고 있던 것).** `--yield-stress` 는 도움말상 MPa 인데
덱 단위 응력과 바로 비교되고 표기도 "MPa" 로 박혀 있었다. SI 덱에서 350 을
2.7e8 Pa 와 견주면 안전율이 1.3e-6 으로 나오고 화면에는 "Peak 270000000.0 MPa"
가 떴다 — 항복 판정이 통째로 무의미한데 경고가 없었다. M3_P2 의
`YIELD_STRESS=350` 고정은 ton-mm-s 덱이라 **우연히** 맞았을 뿐이다.

**새 규칙.** 맵 값은 덱 단위 그대로 쓴다(안전율은 비율이라 약분된다).
`--yield-stress` 만 MPa 라 덱 단위로 환산하되, **단위를 모르면 판정을
건너뛴다** — 모르는 채로 합부를 판정하지 않는다.

**한계가 여럿이면 전부 보고 작은 쪽을 쓴다.** σ1 과 σvm 에는 대소가 없어
하나만 보면 삼축 인장에서 파괴응력을, 일축 압축에서 항복을 놓친다.
못 잰 기준이 있으면 남은 것으로 낸 안전율은 **실제보다 크다** — 조용히 빼면
"더 안전하다" 고 거짓말하게 되므로 불완전으로 표시하고 CRITICAL 로 단정하지
않는다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report import yield_map as YM  # noqa: E402

VM, MP = YM.VON_MISES, YM.MAX_PRINCIPAL


# ── --yield-stress 의 단위 ──────────────────────────────────────────
def test_mpa_default_converts_to_deck_units():
    """**이 시험이 2026-10 의 기존 결함을 잡는다.**"""
    assert YM.default_limit(350.0, "MPa")[0].value == pytest.approx(350.0)
    assert YM.default_limit(350.0, "Pa")[0].value == pytest.approx(3.5e8)


def test_unknown_unit_skips_rather_than_guesses():
    """단위를 모르면 환산하지 않는다 — 사유를 돌려준다."""
    lim, note = YM.default_limit(350.0, "")
    assert lim is None and note and "판정하지 못" in note


def test_si_deck_safety_factor_is_sane():
    """SI 덱(Pa)에서 안전율이 1 근처로 나온다 — 예전엔 1.3e-6 이었다."""
    lim, _ = YM.default_limit(350.0, "Pa")
    v = YM.evaluate([lim], {VM: 2.7e8, MP: None})
    assert 1.0 < v.sf < 1.5
    assert 350.0 / 2.7e8 < 1e-5, "전제: 옛 방식은 실제로 무의미한 값이었다"


# ── 한계가 여럿일 때 ────────────────────────────────────────────────
_MAT017 = [YM.YieldLimit(45.0, VM, "MAT_017 SIGY"),
           YM.YieldLimit(30.0, MP, "MAT_017 FS")]


def test_min_over_limits_catches_what_one_criterion_misses():
    """σvm 만 보면 1.125(안전), FS 까지 보면 0.600(파괴)."""
    v = YM.evaluate(_MAT017, {VM: 40.0, MP: 50.0})
    assert v.sf == pytest.approx(0.600)
    assert v.binding.source == "MAT_017 FS"
    assert v.complete


def test_unmeasured_criterion_is_flagged_not_dropped():
    """**놓치는 방향이 위험한 쪽**이라 조용히 빼면 안 된다."""
    v = YM.evaluate(_MAT017, {VM: 40.0, MP: None})
    assert v.sf == pytest.approx(1.125)      # 실제(0.600)보다 **크다**
    assert v.complete is False
    assert any("max_principal 미계측" in s for s in v.skipped)


def test_unknown_criterion_is_not_guessed():
    """모르는 기준은 von Mises 로 때우지 않는다."""
    py, notes = YM._parse_limits(7, {"limits": [
        {"value": 1.0, "criterion": "tresca_ish"},
        {"value": 2.0, "criterion": VM}]})
    assert [l.criterion for l in py.limits] == [VM]
    assert any("모르는 기준" in n for n in notes)


def test_old_map_without_limits_falls_back_to_yield():
    """KMM v126 이전 맵에는 limits 가 없다 — yield 를 von Mises 로 본다."""
    py, _ = YM._parse_limits(3, {"yield": 120.0, "source": "MAT_024 SIGY"})
    assert len(py.limits) == 1
    assert py.limits[0].criterion == VM and py.limits[0].value == 120.0


# ── 맵 위생 ────────────────────────────────────────────────────────
def test_sanity_note_catches_strain_in_a_stress_field():
    """EPS/ES 뒤바뀜류 — 항복 자리에 변형률(0.01)이 오면 전부 CRITICAL 이 된다."""
    bad = {1: YM.PartYield(1, [YM.YieldLimit(0.012, VM)]),
           2: YM.PartYield(2, [YM.YieldLimit(0.008, VM)])}
    assert YM.sanity_note(bad, {1: 210.0, 2: 180.0})


def test_sanity_note_is_quiet_for_normal_maps():
    """정상 맵에 오경보를 내지 않는다 — 재료 지식이 아니라 자릿수만 본다."""
    ok = {1: YM.PartYield(1, [YM.YieldLimit(350.0, VM)]),
          2: YM.PartYield(2, [YM.YieldLimit(280.0, VM)])}
    assert YM.sanity_note(ok, {1: 210.0, 2: 180.0}) is None


def test_sanity_note_needs_a_sample(tmp_path):
    """표본이 하나뿐이면 단정하지 않는다."""
    one = {1: YM.PartYield(1, [YM.YieldLimit(0.01, VM)])}
    assert YM.sanity_note(one, {1: 210.0}) is None


# ── 입력 경로 ──────────────────────────────────────────────────────
def test_reads_part_yield_from_first_readable_dropset(tmp_path):
    """깨진 DropSet.json 을 건너뛰고 다음 것에서 읽는다."""
    out = tmp_path / "output"
    (out / "Run_000").mkdir(parents=True)
    (out / "Run_000" / "DropSet.json").write_text("{ not json", encoding="utf-8")
    (out / "Run_001").mkdir(parents=True)
    (out / "Run_001" / "DropSet.json").write_text(json.dumps({"model": {"part_yield": {
        "unit": "MPa",
        "parts": {"10": {"yield": 30.0, "mid": 17, "limits": [
            {"value": 45.0, "criterion": VM, "source": "MAT_017 SIGY"},
            {"value": 30.0, "criterion": MP, "source": "MAT_017 FS"}]}}}}}),
        encoding="utf-8")
    py, unit, _ = YM.load_from_dropset(out)
    assert unit == "MPa"
    assert len(py[10].limits) == 2


def test_explicit_file_overrides(tmp_path):
    f = tmp_path / "m.json"
    f.write_text(json.dumps({"unit": "Pa", "parts": {
        "5": {"yield": 3.5e8, "source": "손으로"}}}), encoding="utf-8")
    py, unit, _ = YM.load_from_file(f)
    assert unit == "Pa" and py[5].limits[0].value == pytest.approx(3.5e8)
