# 같은 이름을 쓰는 pid 가 여럿일 때 sphere 어댑터가 파트 지표를 잃지 않는지 검증
"""sphere sidecar 의 동명(同名) 파트 병합 규칙.

덱에서 `Screw` 같은 이름은 여러 pid 로 나뉘어 있는 것이 정상이다(체결부 5·6 …).
sphere 어댑터의 `part_cells[(각도, 이름)]` 는 키가 이름이라 pid 가 여럿이면
**마지막 pid 가 앞의 값을 덮어쓴다** — 480 MPa 짜리 나사가 35 MPa 로 바뀌어
연합 보고서의 파트 추이·순위·Δ 가 엉뚱한 pid 에서 나온다.

여기서 못박는 규칙은 impact 어댑터와 같다 — **지표별로 더 나쁜 쪽을 남긴다.**
압축측(σ3/ε3)은 음수라 max() 로 고르면 '가장 약한 압축' 이 이기므로
severity() 로 방향을 맞춘다.
"""
from __future__ import annotations

from koo_federate_report.adapters.sphere import to_bundle as sphere_bundle


def _sidecar():
    """pid 5·6 이 이름을 공유하는 최소 sphere sidecar."""
    return {
        "project_name": "SYN_DUP",
        "parts": {
            "5": {"part_name": "Screw", "group": "Screw"},
            "6": {"part_name": "Screw", "group": "Screw"},
            "7": {"part_name": "PCB\\PCB", "group": "PCB"},
        },
        "results_summary": [
            {
                "run_folder": "run_0001",
                "angle": {"name": "C1_Corner", "roll": 45.0, "pitch": 45.0, "yaw": 0.0,
                          "category": "corner"},
                "parts": {
                    "5": {"peak_stress": 480.0, "peak_g": 900.0, "peak_disp": 1.2,
                          "min_principal_stress": -300.0},
                    # 뒤에 오는 pid 가 모든 면에서 더 약하다 — 덮어쓰기면 이 값이 남는다.
                    "6": {"peak_stress": 35.0, "peak_disp": 0.1,
                          "min_principal_stress": -20.0},
                    "7": {"peak_stress": 60.0, "peak_g": 500.0, "peak_disp": 0.4,
                          "min_principal_stress": -90.0},
                },
            },
        ],
    }


def test_same_name_pids_keep_worst_tensile():
    """인장측(von Mises)은 더 큰 쪽이 남아야 한다."""
    b = sphere_bundle(_sidecar())
    assert b.part_metric("C1_Corner", "Screw", "s") == 480.0


def test_same_name_pids_keep_worst_compressive():
    """압축측(σ3)은 더 작은(더 압축된) 쪽이 남아야 한다."""
    b = sphere_bundle(_sidecar())
    assert b.part_metric("C1_Corner", "Screw", "s3") == -300.0


def test_same_name_merge_does_not_invent_values():
    """한쪽에만 있는 지표는 그대로 살고, 양쪽에 없으면 None 이다."""
    b = sphere_bundle(_sidecar())
    # peak_g 는 pid 5 에만 있다 — 병합으로 사라지면 안 된다.
    assert b.part_metric("C1_Corner", "Screw", "g") == 900.0
    # peak_strain 은 둘 다 없다 — 0 으로 채우면 '변형 없음' 으로 오독된다.
    assert b.part_metric("C1_Corner", "Screw", "e") is None


def test_other_parts_untouched():
    """이름이 겹치지 않는 파트는 병합의 영향을 받지 않는다."""
    b = sphere_bundle(_sidecar())
    assert b.part_metric("C1_Corner", "PCB\\PCB", "s") == 60.0
    assert b.part_metric("C1_Corner", "PCB\\PCB", "s3") == -90.0


def test_cell_agg_still_worst_over_all_pids():
    """셀 집계는 병합과 무관하게 전 pid 중 최악이다(회귀 방지)."""
    b = sphere_bundle(_sidecar())
    c = b.cell_by_key("C1_Corner")
    assert c.metrics["s"] == 480.0
    assert c.metrics["s3"] == -300.0


def test_all():
    """pytest 진입점 — 이 파일의 모든 규칙을 한 번에 돌린다."""
    test_same_name_pids_keep_worst_tensile()
    test_same_name_pids_keep_worst_compressive()
    test_same_name_merge_does_not_invent_values()
    test_other_parts_untouched()
    test_cell_agg_still_worst_over_all_pids()


if __name__ == "__main__":
    test_all()
    print("[PASS] 동명 파트 병합 규칙 5건")
