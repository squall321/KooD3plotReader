"""Data loader: reads simulation configs, analysis results, and DropSet files."""
import csv
import json
import math
from pathlib import Path

from .models import (
    AngleCondition, MotionData, PartInfo, PartResult,
    SimulationParams, SimulationResult, TimeSeriesData,
)


def _classify_angle(name: str) -> str:
    if name.startswith("F"):
        return "face"
    if name.startswith("E"):
        return "edge"
    if name.startswith("C"):
        return "corner"
    if name.startswith("P"):
        return "fibonacci"
    return "unknown"


def load_runner_config(test_dir: Path) -> tuple[str, str, SimulationParams, dict[str, AngleCondition]]:
    """Load runner_config.json and return project info + DOE angles.

    Returns: (project_name, doe_strategy, sim_params, {angle_key: AngleCondition})
    """
    rc_path = test_dir / "runner_config.json"
    if not rc_path.exists():
        return "", "unknown", SimulationParams(), {}

    with open(rc_path, encoding="utf-8") as f:
        rc = json.load(f)

    project_name = rc.get("project_name", rc.get("project", {}).get("name", ""))

    # DOE strategy from scenario
    scenarios = rc.get("scenarios", [])
    doe_strategy = "unknown"
    if scenarios:
        sid = scenarios[0].get("scenario_name", scenarios[0].get("scenario_id", ""))
        if "fibonacci" in sid.lower():
            doe_strategy = "fibonacci"
        elif "cuboid" in sid.lower() or "26" in sid:
            doe_strategy = "cuboid_26"
        elif "6faces" in sid.lower():
            doe_strategy = "6faces"
        else:
            doe_strategy = sid

    # Simulation params
    sp = rc.get("simulation_params", {})
    sim_params = SimulationParams(
        t_final=sp.get("tFinal", 0.001),
        dt=sp.get("dt", 1e-6),
        drop_height=sp.get("height", 1500.0),
        density=sp.get("density", 7850.0),
        youngs_modulus=sp.get("youngs_modulus", 2e11),
        poisson_ratio=sp.get("poisson_ratio", 0.3),
    )

    # DOE angles
    doe_angles: dict[str, AngleCondition] = {}
    scenario = rc.get("scenario", {})
    raw_angles = scenario.get("doe_angles", {})
    for doe_idx, steps in raw_angles.items():
        for step_key, angle_def in steps.items():
            name = angle_def.get("angle_name", f"DOE{doe_idx}")
            ac = AngleCondition(
                angle_name=name,
                roll=angle_def.get("roll", 0.0),
                pitch=angle_def.get("pitch", 0.0),
                yaw=angle_def.get("yaw", 0.0),
                category=_classify_angle(name),
            )
            key = f"{ac.roll:.1f}_{ac.pitch:.1f}_{ac.yaw:.1f}"
            doe_angles[key] = ac

    return project_name, doe_strategy, sim_params, doe_angles


def load_dropset(run_dir: Path) -> AngleCondition | None:
    """Load DropSet.json from a run folder."""
    ds_path = run_dir / "DropSet.json"
    if not ds_path.exists():
        return None

    with open(ds_path, encoding="utf-8") as f:
        ds = json.load(f)

    orient = ds.get("initial_conditions", {}).get("orientation_euler_deg", {})
    return AngleCondition(
        angle_name="",  # will be resolved from doe_angles
        roll=orient.get("roll", 0.0),
        pitch=orient.get("pitch", 0.0),
        yaw=orient.get("yaw", 0.0),
    )


def load_part_names(output_dir: Path) -> dict[int, PartInfo]:
    """Load part names from the first available DropSet.json."""
    parts: dict[int, PartInfo] = {}
    for run_dir in sorted(output_dir.iterdir()):
        ds_path = run_dir / "DropSet.json"
        if not ds_path.exists():
            continue
        with open(ds_path, encoding="utf-8") as f:
            ds = json.load(f)
        raw_parts = ds.get("model", {}).get("parts", {})
        for pid_str, pname in raw_parts.items():
            pid = int(pid_str)
            group = PartInfo.extract_group(pname)
            parts[pid] = PartInfo(part_id=pid, part_name=pname, group=group)
        break  # same model for all runs
    return parts


def _downsample_step(n: int, target: int) -> int:
    """Every Nth row to keep, or 1 if target unset / >= n."""
    if target is None or target <= 0 or n <= target:
        return 1
    return max(1, n // target)


def _load_stress_strain_csv(csv_path: Path, target_points: int | None = None) -> TimeSeriesData:
    """Load stress or strain CSV file.

    When target_points is set, the returned lists are downsampled but
    true_peak / true_peak_time retain the exact pre-downsample values.
    """
    ts = TimeSeriesData()
    # Single-pass read: keep all rows, then downsample after computing true peak.
    # (CSV files are small individually; memory bloat comes from retaining
    #  1144 of them simultaneously.)
    all_t: list[float] = []
    all_max: list[float] = []
    all_min: list[float] = []
    all_avg: list[float] = []
    all_eid: list[int] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        max_col = min_col = avg_col = None
        has_eid = False
        for row in reader:
            if max_col is None:
                max_col = next(c for c in row if c.startswith("Max_") and c != "Max_Element_ID")
                min_col = next(c for c in row if c.startswith("Min_") and c != "Min_Element_ID")
                avg_col = next(c for c in row if c.startswith("Avg_"))
                has_eid = "Max_Element_ID" in row
            all_t.append(float(row["Time"]))
            all_max.append(float(row[max_col]))
            all_min.append(float(row[min_col]))
            all_avg.append(float(row[avg_col]))
            if has_eid:
                all_eid.append(int(row["Max_Element_ID"]))

    # Capture true peak before downsampling
    if all_max:
        peak_idx = max(range(len(all_max)), key=all_max.__getitem__)
        ts.true_peak = all_max[peak_idx]
        ts.true_peak_time = all_t[peak_idx]

    step = _downsample_step(len(all_t), target_points)
    ts.times = all_t[::step]
    ts.max_values = all_max[::step]
    ts.min_values = all_min[::step]
    ts.avg_values = all_avg[::step]
    if all_eid:
        ts.max_element_ids = all_eid[::step]
    return ts


def _load_motion_csv(csv_path: Path, target_points: int | None = None) -> MotionData:
    """Load motion CSV file. Downsamples to target_points if given."""
    md = MotionData()
    cols = {
        "avg_disp_x": "Avg_Disp_X", "avg_disp_y": "Avg_Disp_Y", "avg_disp_z": "Avg_Disp_Z",
        "avg_disp_mag": "Avg_Disp_Mag",
        "avg_vel_x": "Avg_Vel_X", "avg_vel_y": "Avg_Vel_Y", "avg_vel_z": "Avg_Vel_Z",
        "avg_vel_mag": "Avg_Vel_Mag",
        "avg_acc_x": "Avg_Acc_X", "avg_acc_y": "Avg_Acc_Y", "avg_acc_z": "Avg_Acc_Z",
        "avg_acc_mag": "Avg_Acc_Mag",
        "max_disp_mag": "Max_Disp_Mag",
    }
    buf: dict[str, list[float]] = {k: [] for k in cols}
    all_t: list[float] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_t.append(float(row["Time"]))
            for k, col in cols.items():
                buf[k].append(float(row[col]))

    # True peaks captured before downsampling
    if buf["avg_acc_mag"]:
        abs_acc = [abs(v) for v in buf["avg_acc_mag"]]
        idx = max(range(len(abs_acc)), key=abs_acc.__getitem__)
        md.true_peak_g = abs_acc[idx] / MotionData.G_FACTOR
        md.true_peak_g_time = all_t[idx]
    if buf["max_disp_mag"]:
        md.true_peak_disp = max(buf["max_disp_mag"])

    step = _downsample_step(len(all_t), target_points)
    md.times = all_t[::step]
    for k in cols:
        setattr(md, k, buf[k][::step])
    return md


def _resolve_angle(
    dropset_angle: AngleCondition,
    doe_angles: dict[str, AngleCondition],
) -> AngleCondition:
    """Match DropSet angle to named DOE angle."""
    key = f"{dropset_angle.roll:.1f}_{dropset_angle.pitch:.1f}_{dropset_angle.yaw:.1f}"
    if key in doe_angles:
        matched = doe_angles[key]
        return AngleCondition(
            angle_name=matched.angle_name,
            roll=dropset_angle.roll,
            pitch=dropset_angle.pitch,
            yaw=dropset_angle.yaw,
            category=matched.category,
        )
    # No match - generate name from angles
    return AngleCondition(
        angle_name=f"R{dropset_angle.roll:.0f}_P{dropset_angle.pitch:.0f}",
        roll=dropset_angle.roll,
        pitch=dropset_angle.pitch,
        yaw=dropset_angle.yaw,
        category="unknown",
    )


def load_simulation_result(
    analysis_dir: Path,
    output_dir: Path,
    run_name: str,
    doe_angles: dict[str, AngleCondition],
    part_info: dict[int, PartInfo],
    target_points: int | None = None,
) -> SimulationResult | None:
    """Load complete analysis result for one run."""
    result_dir = analysis_dir / run_name
    run_output_dir = output_dir / run_name

    # Load angle from DropSet.json
    ds_angle = load_dropset(run_output_dir)
    if ds_angle is None:
        return None
    angle = _resolve_angle(ds_angle, doe_angles)

    # Load analysis_result.json for metadata
    json_path = result_dir / "analysis_result.json"
    if not json_path.exists():
        return None

    with open(json_path, encoding="utf-8") as f:
        ar = json.load(f)

    meta = ar.get("metadata", {})
    sim_result = SimulationResult(
        run_folder=run_name,
        angle=angle,
        num_states=meta.get("num_states", 0),
        start_time=meta.get("start_time", 0.0),
        end_time=meta.get("end_time", 0.0),
    )

    analyzed_parts = set(meta.get("analyzed_parts", []))

    # Load CSV data for each part
    for pid in analyzed_parts:
        pi = part_info.get(pid, PartInfo(part_id=pid, part_name=f"Part_{pid}", group="Unknown"))
        pr = PartResult(part=pi)

        # Stress CSV
        stress_csv = result_dir / "stress" / f"part_{pid}_von_mises.csv"
        if stress_csv.exists():
            pr.stress = _load_stress_strain_csv(stress_csv, target_points)

        # Strain CSV
        strain_csv = result_dir / "strain" / f"part_{pid}_eff_plastic_strain.csv"
        if strain_csv.exists():
            pr.strain = _load_stress_strain_csv(strain_csv, target_points)

        # Motion CSV
        motion_csv = result_dir / "motion" / f"part_{pid}_motion.csv"
        if motion_csv.exists():
            pr.motion = _load_motion_csv(motion_csv, target_points)

        sim_result.parts[pid] = pr

    return sim_result


def compute_angular_spacing(angles: list[AngleCondition]) -> float:
    """Compute mean nearest-neighbor angular distance in degrees."""
    if len(angles) < 2:
        return 0.0

    # Convert to unit vectors on sphere
    vectors = []
    for a in angles:
        lon, lat = a.to_spherical()
        x = math.cos(lat) * math.cos(lon)
        y = math.cos(lat) * math.sin(lon)
        z = math.sin(lat)
        vectors.append((x, y, z))

    min_dists = []
    for i, v1 in enumerate(vectors):
        nearest = float("inf")
        for j, v2 in enumerate(vectors):
            if i == j:
                continue
            dot = max(-1.0, min(1.0, v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]))
            angle_rad = math.acos(dot)
            nearest = min(nearest, angle_rad)
        if nearest < float("inf"):
            min_dists.append(nearest)

    return math.degrees(sum(min_dists) / len(min_dists)) if min_dists else 0.0


def load_all(test_dir: Path) -> tuple[
    str, str, SimulationParams, dict[int, PartInfo],
    list[SimulationResult], dict[str, AngleCondition],
]:
    """Load all data for a test directory.

    Returns: (project_name, doe_strategy, sim_params, part_info, results, doe_angles)
    """
    test_dir = Path(test_dir)
    output_dir = test_dir / "output"
    analysis_dir = test_dir / "analysis_results"

    # Load config
    project_name, doe_strategy, sim_params, doe_angles = load_runner_config(test_dir)

    # Load part names
    part_info = load_part_names(output_dir)

    # Load each analysis result with downsampling to cap RAM use.
    # Target points chosen to give 4x safety margin over the final report's
    # downsample step (html_report/json_report use these same thresholds).
    results: list[SimulationResult] = []
    if analysis_dir.exists():
        run_dirs = [
            d for d in sorted(analysis_dir.iterdir())
            if d.is_dir() and d.name.startswith("Run_")
        ]
        n_runs = len(run_dirs)
        # Same tier formula as html_report.py, but 4x to preserve resolution
        # for possible re-aggregation / alt report configs.
        if n_runs <= 50:
            report_pts = 100
        elif n_runs <= 200:
            report_pts = 30
        elif n_runs <= 500:
            report_pts = 15
        else:
            report_pts = 10
        load_target = report_pts * 4
        for result_folder in run_dirs:
            sr = load_simulation_result(
                analysis_dir, output_dir, result_folder.name, doe_angles, part_info,
                target_points=load_target,
            )
            if sr is not None:
                results.append(sr)

    # Auto-detect pitch/roll convention swap.
    # Standard: roll ∈ [-90, 90] (latitude), pitch ∈ [-180, 180] (longitude).
    # Some DOE generators swap them: pitch ∈ [-90, 90], roll ∈ [-180, 180].
    all_angles = [sr.angle for sr in results]
    if all_angles:
        max_abs_roll = max(abs(a.roll) for a in all_angles)
        max_abs_pitch = max(abs(a.pitch) for a in all_angles)
        need_swap = max_abs_roll > 91 and max_abs_pitch <= 91
        if need_swap:
            for sr in results:
                sr.angle.swap_axes = True
            for ac in doe_angles.values():
                ac.swap_axes = True

    return project_name, doe_strategy, sim_params, part_info, results, doe_angles
