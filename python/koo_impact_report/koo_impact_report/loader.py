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
    """Real binout loader via ``koo_deep_report.core.binout_reader``.

    Returns ``{"glstat": ..., "matsum": ..., "rcforc": [...]}``.
    Auto-detects ``binout0000`` (preferred) or any ``binout*`` in run_dir.
    Returns dict of None values if no binout present.
    """
    binout_path = None
    for cand in ["binout0000", "binout", "binout00000"]:
        p = run_dir / cand
        if p.exists():
            binout_path = p
            break
    if binout_path is None:
        # try any binout-prefixed file
        bins = sorted(run_dir.glob("binout*"))
        binout_path = bins[0] if bins else None

    if binout_path is None or not binout_path.exists():
        return {"glstat": None, "matsum": None, "rcforc": None}

    try:
        from koo_deep_report.core.binout_reader import parse_binout
        data = parse_binout(binout_path)
        if data is None:
            return {"glstat": None, "matsum": None, "rcforc": None}
        return {
            "glstat": None,  # glstat parsed separately if needed
            "matsum": data.matsum,
            "rcforc": data.rcforc,
            "sleout": data.sleout,
        }
    except ImportError:
        # koo_deep_report not installed — fallback (CSV path)
        return {"glstat": None, "matsum": None, "rcforc": None}
    except Exception as e:
        print(f"[loader] binout parse failed for {binout_path}: {e}")
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
    """Read trajectory for one run.

    Priority order:
    1. ``impactor_trajectory.csv`` (synthetic / fast path)
    2. Real ``d3plot`` in run_dir → unified_analyzer extraction (slower, real data)

    Returns None if neither source available.
    """
    csv_path = run_dir / "impactor_trajectory.csv"
    if not csv_path.exists():
        # Fall back to real d3plot if present
        d3plot_path = run_dir / "d3plot"
        if d3plot_path.exists():
            print(f"[loader] {run_dir.name}: synthetic CSV missing → real d3plot path")
            return load_impactor_trajectory_from_d3plot(d3plot_path)
        print(f"[loader] WARN  no trajectory data in {run_dir.name}")
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


def _find_impactor_part_id(d3plot_path: Path, name_pattern: str = "Impactor") -> int | None:
    """Inspect a d3plot's keyword file to find the impactor part id by name.

    Looks for *.k near the d3plot and matches PART titles containing the
    pattern (case-insensitive). Returns None if not found.
    """
    parent = d3plot_path.parent
    k_files = list(parent.glob("*.k")) + list(parent.glob("*.key")) + list(parent.glob("*.dyn"))
    pat_low = name_pattern.lower()
    for kf in k_files:
        try:
            with open(kf, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            continue
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.strip().upper().startswith("*PART"):
                # *PART_TITLE: title line is the NEXT non-comment line; pid is on the line after
                j = i + 1
                title = ""
                pid_line = None
                while j < len(lines) and lines[j].lstrip().startswith("$"):
                    j += 1
                if j < len(lines):
                    title = lines[j].strip()
                    j += 1
                while j < len(lines) and lines[j].lstrip().startswith("$"):
                    j += 1
                if j < len(lines):
                    pid_line = lines[j]
                if pid_line and (pat_low in title.lower() or any(
                    tok in title.lower() for tok in ["ball", "impactor", "cylinder", "punch"]
                )):
                    try:
                        pid = int(pid_line.split()[0])
                        return pid
                    except (ValueError, IndexError):
                        pass
            i += 1
    return None


def load_impactor_trajectory_from_d3plot(
    d3plot_path: Path,
    impactor_part_id: int | None = None,
    impactor_part_name: str = "Impactor",
    work_dir: Path | None = None,
    threads: int = 2,
) -> ImpactorTrajectory | None:
    """Extract impactor trajectory directly from a d3plot via unified_analyzer.

    Calls ``koo_deep_report.core.d3plot_reader.run_analysis`` with the impactor
    part id and parses the resulting ``motion/part_<id>_motion.csv`` for full
    directional velocity (vx, vy, vz) data.

    Returns None if d3plot doesn't exist or extraction fails.
    """
    if not d3plot_path.exists():
        return None
    if impactor_part_id is None:
        impactor_part_id = _find_impactor_part_id(d3plot_path, impactor_part_name)
        if impactor_part_id is None:
            print(f"[loader] could not find impactor part in {d3plot_path}")
            return None

    try:
        from koo_deep_report.core.d3plot_reader import run_analysis
    except ImportError:
        print("[loader] koo_deep_report not importable — cannot run d3plot extraction")
        return None

    if work_dir is None:
        import tempfile
        work_dir = Path(tempfile.mkdtemp(prefix="koo_impact_traj_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        run_analysis(
            d3plot_path=d3plot_path,
            output_dir=work_dir,
            part_ids=[impactor_part_id],
            threads=threads,
            verbose=False,
        )
    except Exception as e:
        print(f"[loader] unified_analyzer failed: {e}")
        return None

    motion_csv = work_dir / "motion" / f"part_{impactor_part_id}_motion.csv"
    if not motion_csv.exists():
        print(f"[loader] motion CSV not found: {motion_csv}")
        return None

    # Parse motion CSV → ImpactorTrajectory
    traj = ImpactorTrajectory()
    with open(motion_csv) as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            try:
                traj.times.append(float(row["Time"]))
                traj.pos_x.append(float(row["Avg_Disp_X"]))
                traj.pos_y.append(float(row["Avg_Disp_Y"]))
                traj.pos_z.append(float(row["Avg_Disp_Z"]))
                vx = float(row.get("Avg_Vel_X", 0))
                vy = float(row.get("Avg_Vel_Y", 0))
                vz = float(row.get("Avg_Vel_Z", 0))
                traj.vel_x.append(vx)
                traj.vel_y.append(vy)
                traj.vel_z.append(vz)
                # KE per timestep (impactor mass unknown without binout; placeholder 1.0)
                v_sq = vx * vx + vy * vy + vz * vz
                traj.ke.append(0.5 * v_sq * 1e-6)  # mm/s → m/s scaling, mass=1
                traj.contact_engaged.append(False)  # will derive from rcforc separately
            except (KeyError, ValueError):
                continue

    if not traj.times:
        return None

    # Use binout matsum kinetic_energy if available for proper KE scaling
    parent = d3plot_path.parent
    try:
        from koo_deep_report.core.binout_reader import parse_binout
        binout = None
        for cand in ["binout0000", "binout"]:
            if (parent / cand).exists():
                binout = parse_binout(parent / cand)
                break
        if binout and binout.matsum and impactor_part_id in binout.matsum.part_ids:
            idx = binout.matsum.part_ids.index(impactor_part_id)
            ms_t = binout.matsum.t
            ke_series = [row[idx] for row in binout.matsum.kinetic_energy]
            # Interpolate matsum KE to trajectory times if mismatched
            if len(ms_t) >= 2 and abs(ms_t[-1] - traj.times[-1]) < 0.1 * abs(ms_t[-1] or 1):
                # Simple linear interp on traj.times grid
                interp_ke = []
                for t in traj.times:
                    j = 0
                    while j < len(ms_t) - 1 and ms_t[j + 1] < t:
                        j += 1
                    if j >= len(ms_t) - 1:
                        interp_ke.append(ke_series[-1])
                    else:
                        dt = ms_t[j + 1] - ms_t[j] or 1
                        f = (t - ms_t[j]) / dt
                        interp_ke.append(ke_series[j] + f * (ke_series[j + 1] - ke_series[j]))
                traj.ke = interp_ke
            else:
                # fallback: take last value as final, first as initial
                pass
    except Exception:
        pass

    # Derive contact_engaged from rcforc if available
    try:
        if 'binout' in locals() and binout and binout.rcforc:
            # mark steps where any contact involving impactor has nontrivial force
            n = len(traj.times)
            mask = [False] * n
            for rc in binout.rcforc:
                if not rc.t:
                    continue
                for ti, t in enumerate(traj.times):
                    # find nearest rcforc time
                    if rc.t and rc.t[0] <= t <= rc.t[-1]:
                        # binary search
                        lo, hi = 0, len(rc.t) - 1
                        while lo < hi:
                            mid = (lo + hi) // 2
                            if rc.t[mid] < t:
                                lo = mid + 1
                            else:
                                hi = mid
                        if abs(rc.fx[lo]) + abs(rc.fy[lo]) + abs(rc.fz[lo]) > 1e-3:
                            mask[ti] = True
            traj.contact_engaged = mask
    except Exception:
        pass

    _compute_trajectory_summaries(traj)
    return traj


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


# ---------------------------------------------------------------------------
# Single d3plot mode — for ball-drop / one-shot impact tests
# ---------------------------------------------------------------------------

def load_single_d3plot_report(
    d3plot_path: Path,
    project_name: str | None = None,
    impactor_part_name: str = "Impactor",
    face_code: str = "F2",
    work_dir: Path | None = None,
    threads: int = 2,
) -> ImpactReport:
    """Wrap a single d3plot as a 1-position ImpactReport (testing/demo path).

    Useful for validating the d3plot integration without a full multi-face DOE.
    Inflates one d3plot into a single (face=F2, position at origin) report.

    Returns an ImpactReport ready for analyzer.analyze() + html generation.
    """
    d3plot_path = Path(d3plot_path).resolve()
    if not d3plot_path.exists():
        raise FileNotFoundError(f"d3plot not found: {d3plot_path}")

    parent = d3plot_path.parent
    if project_name is None:
        project_name = parent.name

    # 1) Trajectory via unified_analyzer
    print(f"[loader] single d3plot → extracting impactor trajectory: {d3plot_path}")
    traj = load_impactor_trajectory_from_d3plot(
        d3plot_path=d3plot_path,
        impactor_part_name=impactor_part_name,
        work_dir=work_dir,
        threads=threads,
    )
    if traj is None:
        print("[loader] WARN  trajectory extraction failed — report will lack trajectory")
        traj = ImpactorTrajectory()

    # 2) Binout energy
    bin_data = load_binout_energy(parent)
    matsum = bin_data.get("matsum")
    rcforc = bin_data.get("rcforc") or []
    part_names_map = {}
    if matsum is not None and matsum.part_names:
        part_names_map = dict(zip(matsum.part_ids, matsum.part_names))

    # 3) Build minimal parts list from matsum (or just impactor + a placeholder)
    parts: list[PartInfo] = []
    if matsum:
        for pid, pname in zip(matsum.part_ids, matsum.part_names):
            parts.append(PartInfo(part_id=int(pid), part_name=pname, group=pname.split("_")[0]))
    if not parts:
        parts = [PartInfo(part_id=1, part_name="Part_1", group="Default")]

    # 4) Single position (origin) and single PairResult per part
    face = FACE_STANDARD.get(face_code, FACE_STANDARD["F2"])
    pos = ImpactPosition(
        pos_id=f"{face_code}_P_0001",
        face=face_code,
        x=float(traj.pos_x[0]) if traj.pos_x else 0.0,
        y=float(traj.pos_y[0]) if traj.pos_y else 0.0,
        run_dir=parent,
    )

    results: list[PairResult] = []
    for p in parts:
        # If matsum available, compute peak IE for this part → use as proxy for peak_stress
        peak_ie = 0.0
        if matsum and p.part_id in matsum.part_ids:
            idx = matsum.part_ids.index(p.part_id)
            ies = [row[idx] for row in matsum.internal_energy]
            peak_ie = max(ies) if ies else 0.0
        results.append(PairResult(
            face=face_code,
            position=pos,
            part_id=p.part_id,
            peak_g=0.0,           # not derivable from matsum directly
            peak_stress=peak_ie,  # using IE as a proxy (energy density)
            peak_strain=0.0,
            peak_disp=0.0,
            stress_ts=TimeSeriesData(),
            impactor_trajectory=traj,
        ))

    # 5) Impactor spec — best effort
    impactor = ImpactorSpec(type="Sphere", radius=5.0, height=100.0,
                            density=7850.0, youngs_modulus=2e11, poisson_ratio=0.3)

    impactor_trajectories = {pos.pos_id: traj}
    print(f"[loader] single d3plot: {len(parts)} part(s), traj n_states={len(traj.times)}, "
          f"behavior={traj.behavior_class}, KE retention={traj.ke_retention:.3f}")

    return ImpactReport(
        project_name=project_name,
        impactor=impactor,
        generation_mode="DampingSpring",
        boundary_distance=0.0,
        offset_distance=0.05,
        faces=[face],
        positions_by_face={face_code: [pos]},
        parts=parts,
        results=results,
        findings=[],
        sim_params={"drop_height": 100, "t_final": float(traj.times[-1]) if traj.times else 0.001, "dt": 1e-6},
        doe_config={"single_d3plot": True, "source": str(d3plot_path)},
        test_dir=str(parent),
        impactor_trajectories=impactor_trajectories,
    )
