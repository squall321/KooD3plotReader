"""Load a Report object from a pre-generated report.json / results_summary JSON file.

This allows re-generating HTML reports from saved JSON without needing
the original d3plot simulation files.
"""
import json
from pathlib import Path

from .models import (
    AngleCondition, Finding, MotionData, PartInfo, PartResult,
    Report, Severity, SimulationParams, SimulationResult, TimeSeriesData,
)


def _make_stress_ts(peak: float, peak_time: float) -> TimeSeriesData:
    if peak <= 0:
        return TimeSeriesData()
    return TimeSeriesData(
        times=[0.0, peak_time],
        max_values=[0.0, peak],
        min_values=[0.0, 0.0],
        avg_values=[0.0, peak],
    )


def _make_motion(peak_g: float, peak_disp: float, peak_g_time: float) -> MotionData:
    G = MotionData.G_FACTOR  # mm/s² per G — single source of truth
    mo = MotionData()
    if peak_g > 0:
        t = peak_g_time if peak_g_time > 0 else 0.001
        mo.times = [0.0, t]
        gval = peak_g * G
        mo.avg_acc_mag = [0.0, gval]
        mo.max_disp_mag = [0.0, peak_disp] if peak_disp > 0 else []
    return mo


def load_report_from_json(json_path: str | Path, yield_stress: float = 0.0) -> Report:
    """Reconstruct a Report object from a saved report JSON file."""
    json_path = Path(json_path)
    with open(json_path, encoding="utf-8") as f:
        d = json.load(f)

    # 무관한 JSON 을 넣어도 '0/0 runs' 리포트를 exit 0 으로 만들어내던 문제 —
    # 성공으로 위장하지 않고 무엇이 잘못됐는지 말한다.
    if not isinstance(d, dict):
        raise ValueError(
            f"JSON 최상위가 객체가 아닙니다 ({type(d).__name__}) — --from-json 의 "
            f"입력은 koo_sphere_report 가 낸 report.json 입니다.")
    if "results_summary" not in d and "results" not in d:
        raise ValueError(
            "results_summary / results 키가 없습니다 — koo_sphere_report 의 "
            "report.json 이 아닌 것 같습니다. "
            f"(최상위 키: {', '.join(list(d)[:8]) or '없음'})")
    results_raw = d.get("results_summary") or d.get("results") or []
    if not isinstance(results_raw, list):
        raise ValueError(
            f"results 가 배열이 아닙니다 ({type(results_raw).__name__}) — "
            f"koo_sphere_report 의 report.json 형식이 아닙니다.")
    if not results_raw:
        raise ValueError(
            "각도 결과가 하나도 없습니다 — 빈 리포트를 성공으로 위장하지 않습니다.")

    sp_raw = d.get("simulation_params", {})
    sim_params = SimulationParams(
        t_final=sp_raw.get("t_final", 0.001),
        dt=sp_raw.get("dt", 1e-6),
        drop_height=sp_raw.get("drop_height", 1500.0),
        density=sp_raw.get("density", 7850.0),
        youngs_modulus=sp_raw.get("youngs_modulus", 2e11),
        poisson_ratio=sp_raw.get("poisson_ratio", 0.3),
    )

    # Part info
    part_info: dict[int, PartInfo] = {}
    for pid_str, pi in d.get("parts", {}).items():
        pid = int(pid_str)
        # json_report 는 "part_name" 으로 쓴다. "name" 만 보면 전 파트가
        # "Part <id>" 로 소실된다 — --from-json 재생성에서 실제로 그랬다.
        # 구 샘플 호환을 위해 "name" 도 받는다.
        name = pi.get("part_name") or pi.get("name") or f"Part {pid}"
        group = pi.get("group") or PartInfo.extract_group(name)
        part_info[pid] = PartInfo(part_id=pid, part_name=name, group=group)

    # Findings
    findings = []
    for f in d.get("findings", []):
        try:
            sev = Severity(f.get("severity", "INFO"))
        except ValueError:
            sev = Severity.INFO
        findings.append(Finding(
            severity=sev,
            title=f.get("title", ""),
            detail=f.get("detail", ""),
            recommendation=f.get("recommendation", ""),
        ))

    # Results
    def _ang(ang: dict, key: str, where: str) -> float:
        """각도값은 유한한 숫자여야 한다. null/문자열을 삼키면 지도와 표가 조용히 깨진다."""
        if key not in ang:
            return 0.0          # 키 부재 = 미지정. 기본값 0 은 정당하다.
        v = ang[key]
        if v is None:
            # 명시적 null 은 손상 데이터다. 0 으로 채우면 허구 각도를 만들어낸다.
            raise ValueError(
                f"각도 {key} 가 null 입니다 — {where}. 0 으로 채우면 실제와 다른 "
                f"낙하 방향을 지어내게 되므로 중단합니다.")
        if isinstance(v, bool):
            # 파이썬에서 bool 은 int 라 float(True)=1.0 으로 조용히 통과한다.
            # true/false 를 각도 1°/0° 로 바꾸는 것은 값을 지어내는 것이다.
            raise ValueError(
                f"각도 {key} 가 참/거짓 값입니다 ({v!r}) — {where}. "
                f"숫자가 아니므로 중단합니다.")
        if not isinstance(v, (int, float)):
            raise ValueError(
                f"각도 {key} 가 숫자가 아닙니다 ({v!r}) — {where}. "
                f"손상된 report.json 을 정상으로 위장하지 않습니다.")
        v = float(v)
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError(f"각도 {key} 가 유한한 수가 아닙니다 ({v!r}) — {where}")
        return v

    results: list[SimulationResult] = []
    for ridx, r in enumerate(results_raw):
        if not isinstance(r, dict):
            raise ValueError(
                f"results[{ridx}] 가 객체가 아닙니다 ({type(r).__name__}) — "
                f"koo_sphere_report 의 report.json 형식이 아닙니다.")
        ang = r.get("angle")
        if ang is None:
            # angle 자체가 null 이면 0/0/0 을 지어내는 대신 중단한다.
            raise ValueError(f"results[{ridx}] 의 angle 이 없습니다(null) — "
                             f"낙하 방향을 지어내지 않습니다.")
        if not isinstance(ang, dict):
            raise ValueError(f"results[{ridx}] 의 angle 이 객체가 아닙니다 "
                             f"({type(ang).__name__}).")
        _where = f"angle '{ang.get('name', '?')}'"
        angle = AngleCondition(
            angle_name=ang.get("name", ""),
            roll=_ang(ang, "roll", _where),
            pitch=_ang(ang, "pitch", _where),
            yaw=_ang(ang, "yaw", _where),
            category=ang.get("category", ""),
        )

        parts: dict[int, PartResult] = {}
        for pid_str, pd in r.get("parts", {}).items():
            pid = int(pid_str)
            pi = part_info.get(pid) or PartInfo(part_id=pid, part_name=f"Part {pid}")
            stress = _make_stress_ts(
                pd.get("peak_stress", 0.0),
                pd.get("time_of_peak_stress", 0.001),
            )
            strain = _make_stress_ts(
                pd.get("peak_strain", 0.0),
                pd.get("time_of_peak_stress", 0.001),
            )
            motion = _make_motion(
                pd.get("peak_g", 0.0),
                pd.get("peak_disp", 0.0),
                pd.get("time_of_peak_g", 0.001),
            )
            parts[pid] = PartResult(part=pi, stress=stress, strain=strain, motion=motion)

        results.append(SimulationResult(
            run_folder=r.get("run_folder", ""),
            angle=angle,
            parts=parts,
            num_states=r.get("num_states", 0),
            success=True,
        ))

    return Report(
        project_name=d.get("project_name", json_path.stem),
        doe_strategy=d.get("doe_strategy", ""),
        simulation_params=sim_params,
        total_runs=d.get("total_runs", len(results)),
        successful_runs=d.get("successful_runs", len(results)),
        failed_runs=d.get("failed_runs", 0),
        results=results,
        part_info=part_info,
        angular_spacing_deg=d.get("angular_spacing_deg", 0.0),
        sphere_coverage=d.get("sphere_coverage", 0.0),
        findings=findings,
        yield_stress=yield_stress,
        energy_flows=d.get("energy_flows", {}) or {},
    )
