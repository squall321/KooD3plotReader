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


def _load_stress_strain_csv(csv_path: Path) -> TimeSeriesData:
    """Load stress or strain CSV file."""
    ts = TimeSeriesData()
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts.times.append(float(row["Time"]))
            # Detect column names dynamically
            max_col = [c for c in row if c.startswith("Max_") and c != "Max_Element_ID"][0]
            min_col = [c for c in row if c.startswith("Min_") and c != "Min_Element_ID"][0]
            avg_col = [c for c in row if c.startswith("Avg_")][0]
            ts.max_values.append(float(row[max_col]))
            ts.min_values.append(float(row[min_col]))
            ts.avg_values.append(float(row[avg_col]))
            if "Max_Element_ID" in row:
                ts.max_element_ids.append(int(row["Max_Element_ID"]))
    return ts


def _load_motion_csv(csv_path: Path) -> MotionData:
    """Load motion CSV file."""
    md = MotionData()
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            md.times.append(float(row["Time"]))
            md.avg_disp_x.append(float(row["Avg_Disp_X"]))
            md.avg_disp_y.append(float(row["Avg_Disp_Y"]))
            md.avg_disp_z.append(float(row["Avg_Disp_Z"]))
            md.avg_disp_mag.append(float(row["Avg_Disp_Mag"]))
            md.avg_vel_x.append(float(row["Avg_Vel_X"]))
            md.avg_vel_y.append(float(row["Avg_Vel_Y"]))
            md.avg_vel_z.append(float(row["Avg_Vel_Z"]))
            md.avg_vel_mag.append(float(row["Avg_Vel_Mag"]))
            md.avg_acc_x.append(float(row["Avg_Acc_X"]))
            md.avg_acc_y.append(float(row["Avg_Acc_Y"]))
            md.avg_acc_z.append(float(row["Avg_Acc_Z"]))
            md.avg_acc_mag.append(float(row["Avg_Acc_Mag"]))
            md.max_disp_mag.append(float(row["Max_Disp_Mag"]))
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
            pr.stress = _load_stress_strain_csv(stress_csv)

        # Strain CSV
        strain_csv = result_dir / "strain" / f"part_{pid}_eff_plastic_strain.csv"
        if strain_csv.exists():
            pr.strain = _load_stress_strain_csv(strain_csv)

        # Motion CSV
        motion_csv = result_dir / "motion" / f"part_{pid}_motion.csv"
        if motion_csv.exists():
            pr.motion = _load_motion_csv(motion_csv)

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

    # Load each analysis result
    results: list[SimulationResult] = []
    if analysis_dir.exists():
        for result_folder in sorted(analysis_dir.iterdir()):
            if not result_folder.is_dir() or not result_folder.name.startswith("Run_"):
                continue
            sr = load_simulation_result(
                analysis_dir, output_dir, result_folder.name, doe_angles, part_info,
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
