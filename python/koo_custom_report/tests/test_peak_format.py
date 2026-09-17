# 세트 피크 표가 단위계를 가정한 고정 자릿수로 값을 0 으로 만들지 않는지 검증
"""피크 표 표기 규칙.

실측 배경: 표는 응력·변위·속도·가속도를 `'.2f'`, 시각을 `'.6f'` 로 찍었다.
이는 "값은 수십~수백, 시각은 마이크로초 단위" 라는 **단위계 가정**이다.
GPa 로 푼 덱에서는 σ_vm 0.0863 이 '0.09', σ3 -0.0042 가 '-0.00' 으로 나오고,
SI(m) 덱에서는 |변위| 0.0034 m 가 '0.00' 이 된다. 출력 간격이 1e-7 s 면
1.5e-07 과 1.4e-07 이 둘 다 '0.000000' 이라 서로 다른 피크 시각이 같아 보인다.

여기서 못박는 규칙은 하나다 — **표기는 유효숫자로 하고 단위계를 가정하지 않는다.**
계측된 값이 표에서 0 으로 보이면 '값이 0' 과 구분할 수 없다.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_custom_report.report.html_report import build_html  # noqa: E402
from koo_custom_report.runner import RunResult, SetResult  # noqa: E402


def _field(name, peak, peak_time, measured=True, note=""):
    return {"field": name, "measured": measured, "peak": peak, "peak_time": peak_time,
            "peak_element_id": 1001, "peak_part_id": 7, "note": note}


def _html(fields):
    sr = SetResult(
        name="SET_1",
        safe_name="set_1",
        metrics={"set_type": "ELEMENT", "set_id": 1, "title": "t",
                 "resolved_parts": [7], "fields": fields},
    )
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "custom_report.html"
        build_html(RunResult(ok=True, out_dir=td, sets=[sr]), "/x/d3plot", out)
        return out.read_text(encoding="utf-8")


def test_gpa_stress_is_not_rounded_to_two_decimals():
    """GPa 덱의 σ_vm 0.0863 이 '0.09' 로 뭉개지면 안 된다."""
    h = _html([_field("von_mises", 0.0863, 1.2e-4)])
    assert ">0.0863<" in h, "유효숫자가 남지 않았다"


def test_small_negative_stress_does_not_become_minus_zero():
    """σ3 -0.0042 가 '-0.00' 이면 '압축 없음' 으로 오독된다."""
    h = _html([_field("min_principal_stress", -0.0042, 1.2e-4)])
    assert ">-0.0042<" in h, "작은 압축이 0 으로 보인다"


def test_si_displacement_is_not_zero():
    """SI 덱의 |변위| 0.0034 m 가 '0.00' 이면 계측값이 사라진다."""
    h = _html([_field("disp_mag", 0.0034, 1.2e-4)])
    assert ">0.0034<" in h


def test_distinct_peak_times_stay_distinct():
    """출력 간격 1e-7 s 에서 서로 다른 피크 시각이 같아 보이면 안 된다."""
    h = _html([_field("von_mises", 100.0, 1.5e-7),
               _field("disp_mag", 2.0, 1.4e-7)])
    assert "0.000000" not in h, "시각이 고정 6자리로 뭉개졌다"
    assert "1.5e-07" in h and "1.4e-07" in h


def test_large_values_still_readable():
    """큰 값은 그대로 읽혀야 한다(회귀 방지)."""
    h = _html([_field("von_mises", 480.25, 1.2e-4)])
    assert ">480.2<" in h or ">480.3<" in h


def test_strain_keeps_significant_digits():
    """소성변형률 8.6e-5 가 살아 있어야 한다(0 으로 보이면 '변형 없음')."""
    h = _html([_field("eff_plastic_strain", 8.6e-5, 1.2e-4)])
    assert "8.6e-05" in h or ">0.000086<" in h


def test_unmeasured_field_still_reports_reason():
    """미계측은 값이 아니라 사유다(회귀 방지)."""
    h = _html([_field("vel_mag", None, None, measured=False, note="노드셋 없음")])
    assert "노드셋 없음" in h


def test_all():
    """pytest 진입점 — 이 파일의 모든 규칙을 한 번에 돌린다."""
    test_gpa_stress_is_not_rounded_to_two_decimals()
    test_small_negative_stress_does_not_become_minus_zero()
    test_si_displacement_is_not_zero()
    test_distinct_peak_times_stay_distinct()
    test_large_values_still_readable()
    test_strain_keeps_significant_digits()
    test_unmeasured_field_still_reports_reason()


if __name__ == "__main__":
    test_all()
    print("[PASS] 피크 표 표기 규칙 7건")
