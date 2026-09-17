"""Load a Report object from a pre-generated report.json / results_summary JSON file.

This allows re-generating HTML reports from saved JSON without needing
the original d3plot simulation files.
"""
import json
from pathlib import Path

from .models import (
    AngleCondition, Finding, MotionData, PartEnergy, PartInfo, PartResult,
    Report, Severity, SimulationParams, SimulationResult, TimeSeriesData,
)


def _num(v):
    """숫자만 통과. 문자열·bool·null 은 None (0 으로 바꾸지 않는다)."""
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _series(ts_raw, peak, peak_time=None, min_value=None) -> TimeSeriesData | None:
    """저장된 시계열(있으면)과 참피크를 그대로 복원한다.

    **없는 파형을 지어내지 않는다.** 예전에는 피크 스칼라만으로 [0, peak] 2점
    램프를 만들고 avg 를 peak 과 같게 채웠다 — Impact Pulse 가 그 2점으로 펄스
    폭과 충격량을 계산했고, 에너지 흡수는 15배 큰 값을 냈다. 시계열이 없으면
    배열은 비워 두고 스칼라 피크만 남긴다(화면은 그 탭을 비운다).
    """
    t = list((ts_raw or {}).get("t") or [])
    mx = list((ts_raw or {}).get("max") or [])
    av = list((ts_raw or {}).get("avg") or [])
    if peak is None and min_value is None and not mx:
        return None
    ts = TimeSeriesData()
    if t and len(t) == len(mx):
        ts.times, ts.max_values = t, mx
        if len(av) == len(t):
            ts.avg_values = av
    ts.true_peak = peak if peak is not None else (max(mx) if mx else None)
    if peak_time is not None:
        ts.true_peak_time = peak_time
    if min_value is not None:
        ts.true_min = min_value
    return ts


def _motion(pd: dict) -> MotionData | None:
    """g_ts/disp_ts 와 피크 스칼라로 MotionData 복원. 아무것도 없으면 None."""
    G = MotionData.G_FACTOR  # mm/s² per G — single source of truth
    g_ts = pd.get("g_ts") or {}
    d_ts = pd.get("disp_ts") or {}
    peak_g = _num(pd.get("peak_g"))
    peak_disp = _num(pd.get("peak_disp"))
    peak_g_time = _num(pd.get("time_of_peak_g"))
    gt = list(g_ts.get("t") or [])
    gv = list(g_ts.get("g") or [])
    dt = list(d_ts.get("t") or [])
    dv = list(d_ts.get("mag") or [])
    if not gv and not dv and peak_g is None and peak_disp is None:
        return None
    mo = MotionData()
    if gt and len(gt) == len(gv):
        mo.times = gt
        mo.avg_acc_mag = [v * G for v in gv]
    if dt and len(dt) == len(dv):
        if not mo.times:
            mo.times = dt
        # 변위는 **제 시각을 그대로** 지킨다. g_ts 와 disp_ts 는 각자 제 구간
        # 극값으로 뽑혀 격자가 다르다 — 예전에는 길이가 다르면 변위를 통째로
        # 버리고(곡선이 조용히 사라졌다), 우연히 같으면 가속도 시각에 붙였다.
        mo.disp_times = dt
        mo.avg_disp_mag = dv
    mo.true_peak_g = peak_g
    mo.true_peak_g_time = peak_g_time
    mo.true_peak_disp = peak_disp
    return mo


def _energy(raw) -> PartEnergy | None:
    """저장된 에너지 요약. 없으면 None — 0 으로 채우면 '흡수 없음' 으로 읽힌다."""
    if not isinstance(raw, dict):
        return None
    return PartEnergy(
        peak_ie=_num(raw.get("peak_ie")), peak_ie_time=_num(raw.get("peak_ie_time")),
        peak_ke=_num(raw.get("peak_ke")), peak_ke_time=_num(raw.get("peak_ke_time")),
        final_ie=_num(raw.get("final_ie")), final_ke=_num(raw.get("final_ke")),
    )


def _filter_clusters(items: list, part_ids: set[int] | None) -> list[dict]:
    """report.json 에 실린 핫스팟 군집을 파트로 좁힌다 (loader 와 같은 규칙)."""
    out = []
    for item in items:
        if not isinstance(item, dict) or not item.get("clusters"):
            continue
        if part_ids is not None:
            try:
                pid = int(item.get("part_id"))
            except (TypeError, ValueError):
                continue
            if pid not in part_ids:
                continue
        out.append(item)
    return out


def load_report_from_json(json_path: str | Path, yield_stress: float = 0.0,
                          hotspot_part_ids: set[int] | None = None) -> Report:
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

    # 사이드카에 단위계가 적혀 있으면 되살린다. 없으면 건드리지 않는다 —
    # 옛 산출물에는 이 키가 없고, 그때는 기본 환산이 그대로 쓰인다.
    us = d.get("unit_system")
    if isinstance(us, dict):
        MotionData.set_unit_system(
            str(us.get("id") or ""), _num(us.get("g_factor")) or 0.0,
            note=str(us.get("note") or ""),
            labels=d.get("unit_labels") or {},
        )

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
            # 저장된 것을 읽을 뿐, 없는 것은 만들지 않는다. 변형률 피크 시각은
            # 응력의 것을 빌려 쓰지 않는다 — 서로 다른 사건이다.
            pr = PartResult(part=pi)
            pr.stress = _series(pd.get("stress_ts"), _num(pd.get("peak_stress")),
                                _num(pd.get("time_of_peak_stress")))
            pr.strain = _series(pd.get("strain_ts"), _num(pd.get("peak_strain")))
            pr.motion = _motion(pd)
            pr.energy = _energy(pd.get("energy"))
            # 주응력·주변형률 — 사이드카에 스칼라로만 실린다. 없으면 None.
            pr.principal = _series(None, _num(pd.get("peak_principal_stress")),
                                   _num(pd.get("time_of_peak_principal")))
            pr.principal_min = _series(None, None,
                                       min_value=_num(pd.get("min_principal_stress")))
            pr.principal_strain = _series(None, _num(pd.get("peak_principal_strain")))
            pr.principal_strain_min = _series(
                None, None, min_value=_num(pd.get("min_principal_strain")))
            pr.vm_strain = _series(None, _num(pd.get("peak_vm_strain")))
            parts[pid] = pr

        hs = r.get("hotspot_clusters")
        hs = _filter_clusters(hs, hotspot_part_ids) if isinstance(hs, list) else []

        results.append(SimulationResult(
            run_folder=r.get("run_folder", ""),
            angle=angle,
            parts=parts,
            num_states=r.get("num_states", 0),
            success=True,
            hotspot_clusters=hs,
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
