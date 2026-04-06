"""JSON report serialization."""
import dataclasses
import json
from enum import Enum
from pathlib import Path

from ..models import Report


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
        # Adaptive time series resolution
        n_results = len(report.results)
        ts_pts = 100 if n_results <= 50 else 30 if n_results <= 200 else 15 if n_results <= 500 else 10

        for pid, pr in sr.parts.items():
            pd = {
                "peak_stress": round(pr.peak_stress, 2),
                "peak_strain": round(pr.peak_strain, 6),
                "peak_g": round(pr.peak_g, 1),
                "peak_disp": round(pr.peak_disp, 3),
                "time_of_peak_stress": pr.stress.peak_time if pr.stress else 0.0,
                "time_of_peak_g": pr.motion.peak_g_time if pr.motion else 0.0,
            }

            if include_timeseries:
                if pr.stress and pr.stress.times:
                    step = max(1, len(pr.stress.times) // ts_pts)
                    pd["stress_ts"] = {
                        "t": [round(pr.stress.times[i], 7) for i in range(0, len(pr.stress.times), step)],
                        "max": [round(pr.stress.max_values[i], 1) for i in range(0, len(pr.stress.max_values), step)],
                    }
                if pr.strain and pr.strain.times:
                    step = max(1, len(pr.strain.times) // ts_pts)
                    pd["strain_ts"] = {
                        "t": [round(pr.strain.times[i], 7) for i in range(0, len(pr.strain.times), step)],
                        "max": [round(pr.strain.max_values[i], 6) for i in range(0, len(pr.strain.max_values), step)],
                    }
                if pr.motion and pr.motion.times:
                    step = max(1, len(pr.motion.times) // ts_pts)
                    g_factor = 9810.0
                    pd["g_ts"] = {
                        "t": [round(pr.motion.times[i], 7) for i in range(0, len(pr.motion.times), step)],
                        "g": [round(abs(pr.motion.avg_acc_mag[i]) / g_factor, 1) for i in range(0, len(pr.motion.avg_acc_mag), step)],
                    }
                    pd["disp_ts"] = {
                        "t": [round(pr.motion.times[i], 7) for i in range(0, len(pr.motion.times), step)],
                        "mag": [round(pr.motion.avg_disp_mag[i], 2) for i in range(0, len(pr.motion.avg_disp_mag), step)],
                    }

            run_summary["parts"][str(pid)] = pd
        summary["results_summary"].append(run_summary)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, cls=ReportEncoder, ensure_ascii=False, indent=2)
