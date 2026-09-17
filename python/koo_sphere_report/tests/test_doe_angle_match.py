# DropSet 각도 ↔ runner_config DOE 이름 매칭 규칙(-0.0 정규화·허용오차·대체 이름) 검증
"""DOE 각도 조회의 정직성 규칙.

실측 배경: Test_006 runner_config 의 P0001 은 (roll,pitch,yaw)=(-90.0,-0.0,0.0) 이다.
조회 키가 `f"{v:.1f}"` 문자열이라 `-0.0` 은 '-0.0', `0.0` 은 '0.0' 으로 **서로 다른
키**가 된다 — DropSet 쪽이 부호 없는 0 을 적는 순간 그 런은 DOE 이름을 잃고
category 가 'unknown' 으로 떨어진다(화면의 면/모서리/코너 탭에서 통째로 빠진다).
대체 이름은 yaw 를 빼고 정수로 반올림해서 (35.26,45,0) 과 (35.26,45,90) 이 둘 다
'R35_P45' 가 됐다 — 서로 다른 런이 한 이름으로 겹친다.

여기서 못박는 규칙은 둘이다.
  1. 같은 각도는 부호 없는 0 이든 마지막 자리 반올림이든 같은 DOE 로 붙는다.
  2. 붙일 DOE 가 없으면 이름을 지어내되 **런끼리 겹치지 않게** 세 축을 다 쓴다
     (없는 이름을 만들지 않는다 — category 는 'unknown' 그대로).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.loader import (  # noqa: E402
    _resolve_angle, load_runner_config,
)
from koo_sphere_report.models import AngleCondition  # noqa: E402


def _doe(entries):
    """(name, roll, pitch, yaw) 목록 → load_runner_config 가 만든 DOE 사전.

    조회 키를 만드는 쪽(load_runner_config)과 쓰는 쪽(_resolve_angle)을 같이
    태워야 키 형식이 어긋나는 결함이 잡힌다.
    """
    doe = {}
    for i, (name, roll, pitch, yaw) in enumerate(entries, start=1):
        doe[str(i)] = {"1": {"angle_name": name, "roll": roll, "pitch": pitch, "yaw": yaw}}
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "runner_config.json"
        p.write_text(json.dumps({"scenario": {"doe_angles": doe}}), encoding="utf-8")
        return load_runner_config(Path(td))[3]


def _ds(roll, pitch, yaw):
    return AngleCondition(angle_name="", roll=roll, pitch=pitch, yaw=yaw)


def test_negative_zero_matches_positive_zero():
    """DOE pitch=-0.0, DropSet pitch=0.0 — 같은 각도다."""
    doe = _doe([("P0001", -90.0, -0.0, 0.0)])
    got = _resolve_angle(_ds(-90.0, 0.0, 0.0), doe)
    assert got.angle_name == "P0001", f"이름을 잃었다: {got.angle_name}"
    assert got.category == "fibonacci"


def test_positive_zero_matches_negative_zero():
    """반대 방향(DOE 0.0, DropSet -0.0)도 같아야 한다."""
    doe = _doe([("P0001", -90.0, 0.0, 0.0)])
    got = _resolve_angle(_ds(-90.0, -0.0, 0.0), doe)
    assert got.angle_name == "P0001", f"이름을 잃었다: {got.angle_name}"


def test_rounding_boundary_still_matches():
    """마지막 자리 반올림 경계(45.04 vs 45.06)에서 갈라지면 안 된다."""
    doe = _doe([("C1_Corner", 35.26, 45.04, 0.0)])
    got = _resolve_angle(_ds(35.26, 45.06, 0.0), doe)
    assert got.angle_name == "C1_Corner", f"반올림 경계에서 놓쳤다: {got.angle_name}"
    assert got.category == "corner"


def test_resolved_angle_keeps_dropset_values():
    """이름·분류만 DOE 에서 가져오고 각도 값은 DropSet 것을 쓴다(회귀 방지)."""
    doe = _doe([("P0001", -90.0, -0.0, 0.0)])
    got = _resolve_angle(_ds(-90.0, 0.0, 0.0), doe)
    assert (got.roll, got.pitch, got.yaw) == (-90.0, 0.0, 0.0)


def test_far_angle_is_not_matched():
    """허용오차 밖 각도를 가까운 DOE 이름으로 붙이면 안 된다 — 추측 금지."""
    doe = _doe([("P0001", -90.0, -0.0, 0.0)])
    got = _resolve_angle(_ds(10.0, 10.0, 0.0), doe)
    assert got.angle_name != "P0001"
    assert got.category == "unknown"


def test_fallback_name_separates_yaw():
    """DOE 가 없을 때 yaw 만 다른 두 런이 같은 이름이 되면 안 된다."""
    a = _resolve_angle(_ds(35.26, 45.0, 0.0), {})
    b = _resolve_angle(_ds(35.26, 45.0, 90.0), {})
    assert a.angle_name != b.angle_name, f"이름이 겹쳤다: {a.angle_name}"
    assert a.category == "unknown" and b.category == "unknown"


def test_fallback_name_separates_sub_degree():
    """1° 안쪽으로 다른 각도도 갈라져야 한다(정수 반올림이면 겹친다)."""
    a = _resolve_angle(_ds(35.2, 45.0, 0.0), {})
    b = _resolve_angle(_ds(35.4, 45.0, 0.0), {})
    assert a.angle_name != b.angle_name, f"이름이 겹쳤다: {a.angle_name}"


def test_fallback_name_has_no_negative_zero():
    """대체 이름에 '-0' 이 새어 나오면 같은 각도가 두 이름이 된다."""
    a = _resolve_angle(_ds(-90.0, -0.0, 0.0), {})
    b = _resolve_angle(_ds(-90.0, 0.0, 0.0), {})
    assert a.angle_name == b.angle_name, f"{a.angle_name} != {b.angle_name}"
    assert "-0" not in a.angle_name.replace("R-90", ""), a.angle_name


def test_small_negative_rounds_to_unsigned_zero():
    """-0.04° 처럼 0 으로 반올림되는 **진짜 음수**도 '-0' 을 남기면 안 된다.

    `v + 0.0` 은 IEEE 음의 0 만 접는다. 크기가 0.05 미만인 음수는 '-0.0' 으로
    반올림돼 대체 이름이 'P-0' 이 되고, +0.04 인 런은 'P0' 이라 0.08° 차이가
    부호 차이처럼 보인다. 조회 키도 같은 이유로 '0.0' 짜리 DOE 를 놓친다.
    """
    from koo_sphere_report.loader import _angle_key, _angle_text
    assert _angle_text(-0.04) == "0", _angle_text(-0.04)
    assert _angle_text(-0.02) == "0", _angle_text(-0.02)
    assert _angle_text(-0.05) == "-0.1", _angle_text(-0.05)   # 진짜 0.1° 는 그대로
    assert _angle_text(-1.5) == "-1.5"
    assert _angle_key(12.3, -0.04, 0.0) == _angle_key(12.3, 0.0, 0.0)

    a = _resolve_angle(_ds(12.3, -0.04, 0.0), {})
    assert "P-0" not in a.angle_name, a.angle_name


def test_all():
    """pytest 진입점 — 이 파일의 모든 규칙을 한 번에 돌린다."""
    test_negative_zero_matches_positive_zero()
    test_positive_zero_matches_negative_zero()
    test_rounding_boundary_still_matches()
    test_resolved_angle_keeps_dropset_values()
    test_far_angle_is_not_matched()
    test_fallback_name_separates_yaw()
    test_fallback_name_separates_sub_degree()
    test_fallback_name_has_no_negative_zero()
    test_small_negative_rounds_to_unsigned_zero()


if __name__ == "__main__":
    test_all()
    print("[PASS] DOE 각도 매칭 규칙 8건")
