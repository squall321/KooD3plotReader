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


def save_json(report: Report, path: str) -> None:
    # Build a summary dict (skip raw time-series for compact output)
    summary = {
        "project_name": report.project_name,
        "doe_strategy": report.doe_strategy,
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
        for pid, pr in sr.parts.items():
            run_summary["parts"][str(pid)] = {
                "peak_stress": pr.peak_stress,
                "peak_strain": pr.peak_strain,
                "peak_g": pr.peak_g,
                "peak_disp": pr.peak_disp,
                "time_of_peak_stress": pr.stress.peak_time if pr.stress else 0.0,
                "time_of_peak_g": pr.motion.peak_g_time if pr.motion else 0.0,
            }
        summary["results_summary"].append(run_summary)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, cls=ReportEncoder, ensure_ascii=False, indent=2)
