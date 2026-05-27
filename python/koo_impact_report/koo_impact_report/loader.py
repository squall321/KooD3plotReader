"""Data loader for koo_impact_report.

Reads a multi-face DWI test directory:

    test_dir/
        scenario.json
        manifest.json
        F1_back/Run_xxx/analysis_result.json
        F2_front/Run_xxx/analysis_result.json
        ...

Reuses per-run analysis_result.json from koo_deep_report (same format).

NOTE on binout integration:
    ``load_binout_energy`` is currently a stub. When ready, integrate with
    ``koo_deep_report.core.binout_reader.parse_binout`` which already
    handles matsum / rcforc / sleout via lasso.dyna.
"""
from __future__ import annotations
import csv
import math
import json
from pathlib import Path

from .models import (
    FaceOrientation, ImpactPosition, ImpactReport, ImpactorSpec,
    ImpactorTrajectory, PairResult, PartInfo, TimeSeriesData,
)


# Cuboid-26 face standard (§15.2). Used when scenario doesn't enumerate faces
# explicitly — discover by directory prefix.
FACE_STANDARD: dict[str, FaceOrientation] = {
    "F1": FaceOrientation("F1", "Back",   0.0,   0.0, 0.0),
    "F2": FaceOrientation("F2", "Front",  180.0, 0.0, 0.0),
    "F3": FaceOrientation("F3", "Right",  0.0, -90.0, 0.0),
    "F4": FaceOrientation("F4", "Left",   0.0,  90.0, 0.0),
    "F5": FaceOrientation("F5", "Top",    90.0, 0.0, 0.0),
    "F6": FaceOrientation("F6", "Bottom",-90.0, 0.0, 0.0),
}


def load_scenario(scenario_path: Path) -> dict:
    """Read scenario.json — multi-face DWI scenario spec."""
    if not scenario_path.exists():
        return {}
    with open(scenario_path, encoding="utf-8") as f:
        return json.load(f)


def load_manifest(manifest_path: Path) -> dict:
    """Read manifest.json — flat list of every (face, position) run."""
    if not manifest_path.exists():
        return {}
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def load_part_result(analysis_json: Path) -> dict:
    """Read a single run's analysis_result.json (koo_deep_report format)."""
    if not analysis_json.exists():
        return {}
    with open(analysis_json, encoding="utf-8") as f:
        return json.load(f)


def load_binout_energy(run_dir: Path) -> dict:
    """Placeholder for binout (matsum/rcforc/glstat) loading.

    Returns dict shaped ``{"glstat": ..., "matsum": ..., "rcforc": ...}``.

    TODO: integrate with ``koo_deep_report.core.binout_reader.parse_binout``
    and ``glstat_reader.parse_glstat`` once energy_flow.build_energy_flow is
    wired up. Until then, returns all-None.
    """
    return {"glstat": None, "matsum": None, "rcforc": None}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_impactor(sim_params: dict) -> ImpactorSpec:
    imp = sim_params.get("impactor", {}) if sim_params else {}
    itype = imp.get("type", "Sphere")
    spec = ImpactorSpec(
        type=itype,
        radius=imp.get("radius", 0.0) or imp.get("front_radius", 0.0) or 0.0,
        height=imp.get("height", sim_params.get("height", 100.0) if sim_params else 100.0),
        density=imp.get("density", 7850.0),
        youngs_modulus=imp.get("youngs_modulus", 2.0e11),
        poisson_ratio=imp.get("poisson_ratio", 0.3),
    )
    if itype == "Cylinder":
        spec.front_radius = imp.get("front_radius")
        spec.outer_radius = imp.get("outer_radius")
        spec.front_height = imp.get("front_height")
        spec.back_height = imp.get("back_height")
        spec.back_radius = imp.get("back_radius")
    return spec


def _build_faces(scenario: dict) -> list[FaceOrientation]:
    """Build FaceOrientation list from scenario.json.

    Falls back to FACE_STANDARD if scenario doesn't define faces.
    """
    sim = scenario.get("simulation_params", {})
    raw_faces = sim.get("faces", []) if sim else []
    if not raw_faces:
        return []
    out: list[FaceOrientation] = []
    for f in raw_faces:
        code = f.get("code", "")
        std = FACE_STANDARD.get(code)
        orient = f.get("orientation", {})
        out.append(FaceOrientation(
            code=code,
            name=f.get("name", std.name if std else code),
            roll=orient.get("roll", std.roll if std else 0.0),
            pitch=orient.get("pitch", std.pitch if std else 0.0),
            yaw=orient.get("yaw", std.yaw if std else 0.0),
        ))
    return out


def _discover_face_dirs(test_dir: Path) -> dict[str, Path]:
    """Find ``F1_back``, ``F2_front`` … subdirectories. Returns ``{code: path}``."""
    found: dict[str, Path] = {}
    if not test_dir.exists():
        return found
    for child in sorted(test_dir.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if len(name) >= 2 and name[0] == "F" and name[1].isdigit():
            code = name.split("_")[0]    # "F1_back" → "F1"
            found[code] = child
    return found


def _parse_position_from_run(run_dir: Path, face_code: str) -> ImpactPosition | None:
    """Parse ``Run_001_pos_x010_y020`` style folder name → ImpactPosition.

    Fallback: try to read scenario/run metadata if name doesn't encode coords.
    """
    name = run_dir.name
    x = y = 0.0
    # try suffix tokens like "x010" "y020"
    for tok in name.split("_"):
        if tok.startswith("x") and tok[1:].replace("-", "").replace(".", "").isdigit():
            try:
                x = float(tok[1:])
            except ValueError:
                pass
        elif tok.startswith("y") and tok[1:].replace("-", "").replace(".", "").isdigit():
            try:
                y = float(tok[1:])
            except ValueError:
                pass

    # also check DropSet.json or step_config.txt for explicit coords
    ds_path = run_dir / "DropSet.json"
    if ds_path.exists():
        try:
            with open(ds_path, encoding="utf-8") as f:
                ds = json.load(f)
            loc = ds.get("location", {}) or ds.get("impact_location", {})
            if "x" in loc:
                x = float(loc["x"])
            if "y" in loc:
                y = float(loc["y"])
        except (json.JSONDecodeError, OSError):
            pass

    pos_id = f"{face_code}_{name}"
    return ImpactPosition(pos_id=pos_id, face=face_code, x=x, y=y, run_dir=run_dir)


def _build_part_info_from_result(analysis: dict, registry: dict[int, PartInfo]) -> None:
    """Extend ``registry`` with any new parts found in analysis_result.json."""
    parts = analysis.get("parts", {})
    if isinstance(parts, list):
        # legacy list shape
        for entry in parts:
            pid = entry.get("part_id")
            if pid is None or pid in registry:
                continue
            name = entry.get("part_name", f"Part {pid}")
            registry[pid] = PartInfo(
                part_id=pid, part_name=name, group=PartInfo.extract_group(name),
            )
    else:
        for pid_str, entry in parts.items():
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            if pid in registry:
                continue
            name = entry.get("part_name", entry.get("name", f"Part {pid}"))
            registry[pid] = PartInfo(
                part_id=pid, part_name=name, group=PartInfo.extract_group(name),
            )


def _pair_results_from_run(analysis: dict, face: str, position: ImpactPosition) -> list[PairResult]:
    """Convert a single run's analysis_result.json → list of PairResult (one per part)."""
    out: list[PairResult] = []
    parts = analysis.get("parts", {})
    items = parts.items() if isinstance(parts, dict) else (
        (str(p.get("part_id")), p) for p in parts
    )
    for pid_str, entry in items:
        try:
            pid = int(pid_str)
        except (ValueError, TypeError):
            continue
        pr = PairResult(
            face=face,
            position=position,
            part_id=pid,
            peak_g=float(entry.get("peak_g", 0.0)),
            peak_stress=float(entry.get("peak_stress", 0.0)),
            peak_strain=float(entry.get("peak_strain", 0.0)),
            peak_disp=float(entry.get("peak_disp", 0.0)),
        )
        # Optional embedded stress series
        ts = entry.get("stress_ts") or {}
        if ts:
            pr.stress_ts = TimeSeriesData(
                times=list(ts.get("t", [])),
                max_values=list(ts.get("max", [])),
            )
        out.append(pr)
    return out


# ---------------------------------------------------------------------------
# Impactor trajectory loading
# ---------------------------------------------------------------------------

def classify_behavior(traj: ImpactorTrajectory) -> str:
    """Classify the impactor's post-impact behavior.

    Heuristic on final-velocity components and KE retention:
      * ``bounce``  — strong vertical rebound (|vz_final| > 100, retention > 0.4)
      * ``embed``   — retention < 0.15 and vz tiny → ball stuck
      * ``slide``   — lateral velocity dominates (vxy > vz) with moderate retention
      * ``rebound`` — everything else (moderate vertical rebound)
    """
    if not traj.vel_z:
        return "unknown"
    r = traj.ke_retention
    speed_z = abs(traj.vel_z[-1])
    speed_xy = math.hypot(traj.vel_x[-1], traj.vel_y[-1])
    if r > 0.4 and speed_z > 100:
        return "bounce"
    if r < 0.15 and speed_z < 50:
        return "embed"
    if speed_xy > speed_z and r > 0.15:
        return "slide"
    return "rebound"


def _compute_trajectory_summaries(traj: ImpactorTrajectory) -> None:
    """Populate derived scalar fields on ``traj`` in-place."""
    if not traj.ke:
        return

    traj.initial_ke = float(traj.ke[0])
    traj.final_ke = float(traj.ke[-1])
    traj.ke_retention = (
        traj.final_ke / traj.initial_ke if traj.initial_ke > 0 else 0.0
    )
    # Penetration: max negative z relative to the position at first contact.
    # If contact never engages, fall back to (initial z - min z) magnitude.
    z_ref = traj.pos_z[0]
    for idx, eng in enumerate(traj.contact_engaged):
        if eng:
            z_ref = traj.pos_z[idx]
            traj.t_first_contact = float(traj.times[idx])
            break
    traj.max_penetration_depth = float(max(0.0, z_ref - min(traj.pos_z)))

    traj.rebound_velocity_xy = (
        float(traj.vel_x[-1]), float(traj.vel_y[-1])
    )
    traj.rebound_speed = float(math.sqrt(
        traj.vel_x[-1] ** 2 + traj.vel_y[-1] ** 2 + traj.vel_z[-1] ** 2
    ))
    traj.incident_speed = float(math.sqrt(
        traj.vel_x[0] ** 2 + traj.vel_y[0] ** 2 + traj.vel_z[0] ** 2
    ))
    traj.behavior_class = classify_behavior(traj)


def load_impactor_trajectory(run_dir: Path) -> ImpactorTrajectory | None:
    """Read ``impactor_trajectory.csv`` from ``run_dir`` → ImpactorTrajectory.

    Returns None if the CSV is missing or malformed.
    """
    csv_path = run_dir / "impactor_trajectory.csv"
    if not csv_path.exists():
        print(f"[loader] WARN  no impactor_trajectory.csv in {run_dir.name}")
        return None

    traj = ImpactorTrajectory()
    try:
        with csv_path.open() as fh:
            reader = csv.DictReader(fh)
            required = {"time", "x", "y", "z", "vx", "vy", "vz", "ke", "contact"}
            if not required.issubset(set(reader.fieldnames or [])):
                print(f"[loader] WARN  bad header in {csv_path}: "
                      f"{reader.fieldnames}")
                return None
            for row in reader:
                traj.times.append(float(row["time"]))
                traj.pos_x.append(float(row["x"]))
                traj.pos_y.append(float(row["y"]))
                traj.pos_z.append(float(row["z"]))
                traj.vel_x.append(float(row["vx"]))
                traj.vel_y.append(float(row["vy"]))
                traj.vel_z.append(float(row["vz"]))
                traj.ke.append(float(row["ke"]))
                # accept "1"/"0", "True"/"False", "true"/"false"
                tok = str(row["contact"]).strip().lower()
                traj.contact_engaged.append(tok in ("1", "true", "t", "yes"))
    except (OSError, ValueError, KeyError) as exc:
        print(f"[loader] WARN  failed to parse {csv_path}: {exc}")
        return None

    _compute_trajectory_summaries(traj)
    return traj


def load_impactor_trajectory_from_d3plot(
    d3plot_path: Path,
    impactor_part_name: str = "Ball",
) -> ImpactorTrajectory | None:
    """Future: extract impactor trajectory directly from a d3plot.

    Intended to call ``KooD3plotReader/build/examples/unified_analyzer`` via
    subprocess (analogous to ``koo_deep_report.core.d3plot_reader``) to query
    the impactor part's node positions and velocities per state.

    Returns ``None`` for now — callers fall back to the CSV pipeline.
    """
    # TODO: subprocess unified_analyzer with --query impactor_trajectory
    _ = (d3plot_path, impactor_part_name)
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_impact_report(test_dir: Path) -> ImpactReport:
    """Walk a multi-face DWI test directory → ImpactReport."""
    test_dir = Path(test_dir)
    scenario = load_scenario(test_dir / "scenario.json")
    manifest = load_manifest(test_dir / "manifest.json")

    sim_params = scenario.get("simulation_params", {}) if scenario else {}
    impactor = _build_impactor(sim_params)

    faces = _build_faces(scenario)
    face_dirs = _discover_face_dirs(test_dir)

    # If scenario lacks faces, derive from on-disk folders using FACE_STANDARD
    if not faces:
        faces = [FACE_STANDARD[c] for c in face_dirs if c in FACE_STANDARD]

    positions_by_face: dict[str, list[ImpactPosition]] = {}
    results: list[PairResult] = []
    part_registry: dict[int, PartInfo] = {}
    impactor_trajectories: dict[str, ImpactorTrajectory] = {}

    face_codes = [f.code for f in faces] or list(face_dirs.keys())
    print(f"[loader] Discovered {len(face_codes)} face(s): {', '.join(face_codes)}")

    for face_code in face_codes:
        face_dir = face_dirs.get(face_code)
        if face_dir is None or not face_dir.exists():
            print(f"[loader] WARN  face {face_code}: directory not found, skipping")
            positions_by_face[face_code] = []
            continue

        run_dirs = sorted(d for d in face_dir.iterdir() if d.is_dir() and d.name.startswith("Run_"))
        print(f"[loader] face {face_code}: {len(run_dirs)} run(s)")

        face_positions: list[ImpactPosition] = []
        for run_dir in run_dirs:
            pos = _parse_position_from_run(run_dir, face_code)
            if pos is None:
                continue
            face_positions.append(pos)

            analysis_json = run_dir / "analysis_result.json"
            analysis = load_part_result(analysis_json)
            if not analysis:
                continue
            _build_part_info_from_result(analysis, part_registry)

            # Load shared trajectory once per run; attach the same instance to
            # every PairResult of this run (and store in the report-level dict).
            traj = load_impactor_trajectory(run_dir)
            if traj is not None:
                impactor_trajectories[pos.pos_id] = traj

            run_pairs = _pair_results_from_run(analysis, face_code, pos)
            if traj is not None:
                for pr in run_pairs:
                    pr.impactor_trajectory = traj
            results.extend(run_pairs)
        positions_by_face[face_code] = face_positions

    parts = [part_registry[pid] for pid in sorted(part_registry)]
    print(f"[loader] Total: {len(parts)} part(s), {len(results)} pair result(s)")

    return ImpactReport(
        project_name=scenario.get("project_name", test_dir.name),
        impactor=impactor,
        generation_mode=sim_params.get("generation_mode", "DampingSpring"),
        boundary_distance=float(sim_params.get("boundary_distance", 0.0)),
        offset_distance=float(sim_params.get("offset_distance", 0.05)),
        faces=faces,
        positions_by_face=positions_by_face,
        parts=parts,
        results=results,
        findings=[],
        sim_params=sim_params,
        doe_config=manifest if manifest else {},
        test_dir=str(test_dir.resolve()),
        impactor_trajectories=impactor_trajectories,
    )
