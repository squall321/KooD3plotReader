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
    G = 9810.0
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

    # Support both top-level key names
    results_raw = d.get("results_summary") or d.get("results") or []

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
        name = pi.get("name", f"Part {pid}")
        group = pi.get("group", PartInfo.extract_group(name))
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
    results: list[SimulationResult] = []
    for r in results_raw:
        ang = r.get("angle", {})
        angle = AngleCondition(
            angle_name=ang.get("name", ""),
            roll=ang.get("roll", 0.0),
            pitch=ang.get("pitch", 0.0),
            yaw=ang.get("yaw", 0.0),
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
    )
