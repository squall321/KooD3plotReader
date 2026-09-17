"""JSON report serialization."""
import dataclasses
import json
from enum import Enum
from pathlib import Path

from ..loader import extreme_indices, round_keep_sig
from ..models import MotionData, Report


class ReportEncoder(json.JSONEncoder):
    def default(self, obj):
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


def save_json(report: Report, path: str, include_timeseries: bool = True) -> None:
    # Build a summary dict
    summary = {
        "project_name": report.project_name,
        "doe_strategy": report.doe_strategy,
        "test_dir": str(report.test_dir) if hasattr(report, 'test_dir') and report.test_dir else "",
        "total_runs": report.total_runs,
        "successful_runs": report.successful_runs,
        "failed_runs": report.failed_runs,
        "angular_spacing_deg": report.angular_spacing_deg,
        "sphere_coverage": report.sphere_coverage,
        "simulation_params": dataclasses.asdict(report.simulation_params),
        "findings": [dataclasses.asdict(f) for f in report.findings],
        "parts": {},
        "results_summary": [],
        # 파트간 에너지 흐름(run_folder→중립 flow dict). --from-json 재생성 시
        # 흐름 탭을 유지하려면 그대로 실어 보낸다.
        "energy_flows": getattr(report, "energy_flows", {}) or {},
    }

    # Enum fix for findings
    for f in summary["findings"]:
        if "severity" in f and isinstance(f["severity"], str):
            pass  # already string from Enum.value

    # Part info
    for pid, pi in report.part_info.items():
        summary["parts"][str(pid)] = {
            "part_name": pi.part_name,
            "group": pi.group,
        }

    # Per-run summary (without full time series)
    for sr in report.results:
        run_summary = {
            "run_folder": sr.run_folder,
            "angle": {
                "name": sr.angle.angle_name,
                "roll": sr.angle.roll,
                "pitch": sr.angle.pitch,
                "yaw": sr.angle.yaw,
                "category": sr.angle.category,
            },
            "num_states": sr.num_states,
            "parts": {},
        }
        # 핫스팟 군집 — 없는 런에는 키를 만들지 않는다 (빈 배열도 '있다' 로 읽힌다)
        if sr.hotspot_clusters:
            run_summary["hotspot_clusters"] = sr.hotspot_clusters
        # Adaptive time series resolution
        n_results = len(report.results)
        ts_pts = 100 if n_results <= 50 else 30 if n_results <= 200 else 15 if n_results <= 500 else 10

        for pid, pr in sr.parts.items():
            # 자릿수는 유효숫자를 지키며 줄인다 — 고정 소수점이면 SI 덱 변위
            # 0.0004 m 나 GPa 응력 0.0863 이 0.0/0.09 로 뭉쳐 federate Δ 가 0% 가 된다.
            pd = {
                "peak_stress": round_keep_sig(pr.peak_stress, 2),
                "peak_strain": round_keep_sig(pr.peak_strain, 6),
                "peak_g": round_keep_sig(pr.peak_g, 1),
                "peak_disp": round_keep_sig(pr.peak_disp, 3),
                "time_of_peak_stress": pr.stress.peak_time if pr.stress else 0.0,
                "time_of_peak_g": pr.motion.peak_g_time if pr.motion else 0.0,
            }

            # 최대 주응력 σ1 — 구버전 산출물엔 CSV 가 없어 키 자체를 넣지 않는다.
            # von Mises 로 대체하면 전혀 다른 물리량을 같은 칸에 넣는 셈이다.
            if pr.principal is not None:
                pd["peak_principal_stress"] = round_keep_sig(pr.peak_principal, 2)
                pd["time_of_peak_principal"] = pr.principal.peak_time
            if pr.principal_min is not None and pr.min_principal is not None:
                # σ3 은 압축측이라 최소값이 의미 있다 (부호 유지).
                pd["min_principal_stress"] = round_keep_sig(pr.min_principal, 2)
            # 주변형률 — 변형률 텐서가 실린 덱에서만. 없으면 키 자체를 안 넣는다.
            if pr.peak_principal_strain is not None:
                pd["peak_principal_strain"] = round_keep_sig(pr.peak_principal_strain, 6)
            if pr.min_principal_strain is not None:
                pd["min_principal_strain"] = round_keep_sig(pr.min_principal_strain, 6)
            if pr.peak_vm_strain is not None:
                pd["peak_vm_strain"] = round_keep_sig(pr.peak_vm_strain, 6)

            # 파트별 에너지 (binout matsum). 계측 안 된 파트는 키 자체를 넣지
            # 않는다 — 0 으로 채우면 '흡수 없음' 으로 오독된다.
            if pr.energy is not None:
                e = pr.energy
                pd["energy"] = {
                    "peak_ie": e.peak_ie, "peak_ie_time": e.peak_ie_time,
                    "peak_ke": e.peak_ke, "peak_ke_time": e.peak_ke_time,
                    "final_ie": e.final_ie, "final_ke": e.final_ke,
                }

            if include_timeseries:
                # 매 N번째 행 대신 구간별 최대·최소를 남긴다 — 피크가 빠진
                # 시계열을 사이드카로 넘기면 federate 가 그것을 실측으로 읽는다.
                if pr.stress and pr.stress.times:
                    idx = extreme_indices(len(pr.stress.times), [pr.stress.max_values], ts_pts)
                    pd["stress_ts"] = {
                        "t": [round_keep_sig(pr.stress.times[i], 7) for i in idx],
                        "max": [round_keep_sig(pr.stress.max_values[i], 1) for i in idx],
                    }
                if pr.strain and pr.strain.times:
                    idx = extreme_indices(len(pr.strain.times), [pr.strain.max_values], ts_pts)
                    pd["strain_ts"] = {
                        "t": [round_keep_sig(pr.strain.times[i], 7) for i in idx],
                        "max": [round_keep_sig(pr.strain.max_values[i], 6) for i in idx],
                    }
                if pr.motion and pr.motion.times:
                    g_factor = MotionData.G_FACTOR  # single source of truth
                    gidx = extreme_indices(len(pr.motion.times), [pr.motion.avg_acc_mag], ts_pts)
                    pd["g_ts"] = {
                        "t": [round_keep_sig(pr.motion.times[i], 7) for i in gidx],
                        "g": [round_keep_sig(abs(pr.motion.avg_acc_mag[i]) / g_factor, 1) for i in gidx],
                    }
                    didx = extreme_indices(len(pr.motion.times), [pr.motion.avg_disp_mag], ts_pts)
                    pd["disp_ts"] = {
                        "t": [round_keep_sig(pr.motion.times[i], 7) for i in didx],
                        "mag": [round_keep_sig(pr.motion.avg_disp_mag[i], 2) for i in didx],
                    }

            run_summary["parts"][str(pid)] = pd
        summary["results_summary"].append(run_summary)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, cls=ReportEncoder, ensure_ascii=False, indent=2)
