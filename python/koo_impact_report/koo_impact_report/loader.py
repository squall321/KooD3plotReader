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
from dataclasses import dataclass
from pathlib import Path

from .models import (
    FaceOrientation, ImpactPosition, ImpactReport, ImpactorSpec,
    ImpactorTrajectory, PairResult, PartInfo, PartMotion, TimeSeriesData,
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


def _face_code_from_velocity(v: tuple[float, float, float]) -> str | None:
    """Map an initial velocity vector to its impacted face code.

    The impactor travels along -v, so the face it hits is the one whose
    outward normal aligns most with -v. Returns None if v is zero.
    """
    vx, vy, vz = v
    mag = math.sqrt(vx * vx + vy * vy + vz * vz)
    if mag <= 0:
        return None
    # Direction of motion of the impactor (normalized)
    dx, dy, dz = vx / mag, vy / mag, vz / mag
    # Face outward normals in global frame (Top→+Z, Bottom→-Z, etc.)
    face_normals = {
        "F1": ( 0.0,  1.0,  0.0),   # Back  (+Y)
        "F2": ( 0.0, -1.0,  0.0),   # Front (-Y)
        "F3": ( 1.0,  0.0,  0.0),   # Right (+X)
        "F4": (-1.0,  0.0,  0.0),   # Left  (-X)
        "F5": ( 0.0,  0.0,  1.0),   # Top   (+Z)
        "F6": ( 0.0,  0.0, -1.0),   # Bottom(-Z)
    }
    # Impactor hits the face whose outward normal is most antiparallel to
    # its motion direction → max( dot(-motion, normal) )
    best, best_dot = None, -1.0
    for code, (nx, ny, nz) in face_normals.items():
        dot = -(dx * nx + dy * ny + dz * nz)
        if dot > best_dot:
            best_dot, best = dot, code
    return best


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
    """Build ImpactorSpec from scenario.json sim_params.

    No physical-constant fallbacks: missing fields stay 0.0 (meaning "unknown")
    so downstream code never silently uses a wrong material. Real values must
    come from the scenario, a keyword file (single-d3plot mode), or be set
    explicitly by the caller.

    Scenario fields are expected in LS-DYNA [ton, mm, s, MPa] units to match
    binout/d3plot data. If a scenario stores SI (kg/m³, Pa), supply a
    ``units`` field set to ``"SI"`` to trigger conversion.
    """
    imp = sim_params.get("impactor", {}) if sim_params else {}
    # type is unknown unless the scenario explicitly supplies it
    itype = imp.get("type", "")
    density = float(imp.get("density", 0.0) or 0.0)
    young = float(imp.get("youngs_modulus", 0.0) or 0.0)
    nu = float(imp.get("poisson_ratio", 0.0) or 0.0)
    # Convert SI → [ton, mm, s, MPa] only on explicit opt-in
    if (imp.get("units") or "").upper() == "SI":
        density *= 1.0e-12   # kg/m³ → ton/mm³
        young *= 1.0e-6      # Pa     → MPa
    spec = ImpactorSpec(
        type=itype,
        radius=float(imp.get("radius", 0.0) or imp.get("front_radius", 0.0) or 0.0),
        height=float(imp.get("height", sim_params.get("height", 0.0) if sim_params else 0.0) or 0.0),
        density=density,
        youngs_modulus=young,
        poisson_ratio=nu,
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

@dataclass(frozen=True)
class BehaviorThresholds:
    """Classification thresholds (ratios of the incident kinematics).

    These are exposed so consumers can override them per project/material.
    Defaults are conservative rules-of-thumb in the classification
    literature; they are unit-agnostic (relative to incident speed and
    initial KE).
    """
    bounce_min_retention: float = 0.40
    bounce_min_rel_z: float = 0.05
    embed_max_retention: float = 0.15
    embed_max_rel_z: float = 0.01
    slide_min_retention: float = 0.15


def classify_behavior(
    traj: ImpactorTrajectory,
    thresholds: BehaviorThresholds | None = None,
) -> str:
    """Classify the impactor's post-impact behavior.

    Thresholds are all unit-agnostic ratios (speed / incident_speed,
    retention) and live on a :class:`BehaviorThresholds` instance — pass
    a custom one to override the defaults.
    """
    if not traj.vel_z or traj.incident_speed <= 0:
        return "unknown"
    t = thresholds or BehaviorThresholds()
    r = traj.ke_retention
    inc = traj.incident_speed
    speed_z = abs(traj.vel_z[-1])
    speed_xy = math.hypot(traj.vel_x[-1], traj.vel_y[-1])
    rel_z = speed_z / inc
    if r >= t.bounce_min_retention and rel_z >= t.bounce_min_rel_z:
        return "bounce"
    if r < t.embed_max_retention and rel_z < t.embed_max_rel_z:
        return "embed"
    if speed_xy > speed_z and r >= t.slide_min_retention:
        return "slide"
    return "rebound"


def _compute_trajectory_summaries(traj: ImpactorTrajectory) -> None:
    """Populate derived scalar fields on ``traj`` in-place.

    LS-DYNA's first d3plot state is often the pre-step rest state with
    v = 0 even when a ``*INITIAL_VELOCITY_*`` card is active. Naively taking
    ``ke[0]`` and ``vel[0]`` would then yield zero, breaking ``ke_retention``
    and ``incident_speed``. We instead use the **max over the pre-contact
    window** for both — physically equivalent to "the impactor's energy just
    before it first touches the device".
    """
    if not traj.ke:
        return

    # Penetration & first-contact detection use the position field directly.
    z_ref = traj.pos_z[0] if traj.pos_z else 0.0
    for idx, eng in enumerate(traj.contact_engaged):
        if eng:
            z_ref = traj.pos_z[idx] if traj.pos_z else 0.0
            traj.t_first_contact = float(traj.times[idx])
            break
    if traj.pos_z:
        traj.max_penetration_depth = float(max(0.0, z_ref - min(traj.pos_z)))

    # Pre-contact cutoff: prefer t_first_contact if known; otherwise use the
    # full trajectory (caller may have skipped rcforc-based detection).
    cutoff = len(traj.times)
    if traj.t_first_contact is not None:
        for i, t in enumerate(traj.times):
            if t >= traj.t_first_contact:
                cutoff = i + 1
                break

    # Initial KE = peak KE in the pre-contact window (handles the t=0 v=0
    # artefact). Falls back to ke[0] when window has only one sample.
    pre_kes = [k for k in traj.ke[:cutoff] if k > 0]
    traj.initial_ke = float(max(pre_kes)) if pre_kes else float(traj.ke[0])
    traj.final_ke = float(traj.ke[-1])
    traj.ke_retention = (
        traj.final_ke / traj.initial_ke if traj.initial_ke > 0 else 0.0
    )

    traj.rebound_velocity_xy = (
        float(traj.vel_x[-1]), float(traj.vel_y[-1])
    )
    traj.rebound_speed = float(math.sqrt(
        traj.vel_x[-1] ** 2 + traj.vel_y[-1] ** 2 + traj.vel_z[-1] ** 2
    ))
    speeds = [math.sqrt(vx * vx + vy * vy + vz * vz)
              for vx, vy, vz in zip(traj.vel_x[:cutoff], traj.vel_y[:cutoff], traj.vel_z[:cutoff])]
    traj.incident_speed = float(max(speeds)) if speeds else 0.0
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


def _find_impactor_part_id(d3plot_path: Path, name_pattern: str | None = None) -> int | None:
    """Inspect a d3plot's keyword file to find the impactor part id by name.

    Looks for *.k near the d3plot and matches PART titles. When ``name_pattern``
    is supplied, it is checked first; otherwise (and as a fallback) the title
    is scanned for the heuristic tokens "ball", "impactor", "cylinder",
    "punch". Returns None if no match is found.
    """
    parent = d3plot_path.parent
    k_files = list(parent.glob("*.k")) + list(parent.glob("*.key")) + list(parent.glob("*.dyn"))
    pat_low = (name_pattern or "").lower()
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
                tlow = title.lower()
                matched = bool(pat_low and pat_low in tlow) or any(
                    tok in tlow for tok in ["ball", "impactor", "cylinder", "punch"]
                )
                if pid_line and matched:
                    try:
                        pid = int(pid_line.split()[0])
                        return pid
                    except (ValueError, IndexError):
                        pass
            i += 1
    return None


def _find_keyword_file(d3plot_path: Path) -> Path | None:
    """Locate the .k/.key/.dyn keyword file near a d3plot.

    Searches:
      1. d3plot's own directory (e.g. ball-drop layout)
      2. its parent directory (LS-DYNA jobs that place d3plot in ``Output/``
         while keeping the input deck at the run-dir level — e.g. the
         KooDWITestSetRunner layout)
    Returns the first match by extension preference (.k → .key → .dyn).
    """
    for parent in (d3plot_path.parent, d3plot_path.parent.parent):
        if parent == parent.parent:
            break  # reached filesystem root
        for ext in ("*.k", "*.key", "*.dyn"):
            for p in parent.glob(ext):
                return p
    return None


def _parse_initial_velocity_any(
    kfile: Path,
    pid: int | None = None,
) -> tuple[int | None, tuple[float, float, float]]:
    """Parse ``*INITIAL_VELOCITY_*`` cards and return (pid, (vx, vy, vz)).

    Supports two LS-DYNA card variants:
      • ``*INITIAL_VELOCITY_RIGID_BODY`` — fields: PID, VX, VY, VZ, VXR, VYR, VZR
      • ``*INITIAL_VELOCITY_GENERATION`` — fields: ID, STYP, OMEGA, VX, VY, VZ
        STYP = 2 means the ID is a PART ID (the case we care about).
        STYP = 1 means a PART SET ID — currently treated as an unresolved set
        (returns the SID as pid; caller must map to actual parts).

    Data lines are parsed with the same fixed-10-column splitter used by
    ``koo_deep_report.core.keyword_parser._read_fields`` — LS-DYNA decks
    routinely emit values like ``0.000e+00-4.905e+00`` with no whitespace
    between columns, which ``str.split()`` cannot resolve.

    If ``pid`` is supplied, only matching records are returned. If ``pid``
    is None, the first encountered record is returned (this is how the
    impactor part-id is auto-discovered when the .k has empty PART titles).
    """
    if not kfile.exists():
        return (None, (0.0, 0.0, 0.0))
    try:
        with open(kfile, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return (None, (0.0, 0.0, 0.0))

    try:
        from koo_deep_report.core.keyword_parser import _read_fields, _to_float, _to_int
    except ImportError:
        # Fallback: simple whitespace split (will fail on fused columns).
        def _read_fields(line, n=8):
            parts = line.split()
            return [parts[i] if i < len(parts) else "" for i in range(n)]
        def _to_float(s, default=0.0):
            try: return float(s)
            except (ValueError, TypeError): return default
        def _to_int(s, default=0):
            try: return int(s)
            except (ValueError, TypeError): return default

    def _next_data_line(start: int) -> int:
        j = start
        while j < len(lines) and (lines[j].lstrip().startswith("$") or not lines[j].strip()):
            j += 1
        return j

    i = 0
    while i < len(lines):
        upper = lines[i].strip().upper()
        if upper.startswith("*INITIAL_VELOCITY_RIGID_BODY"):
            j = _next_data_line(i + 1)
            if j < len(lines):
                fields = _read_fields(lines[j], 8)
                rec_pid = _to_int(fields[0])
                if rec_pid > 0 and (pid is None or rec_pid == pid):
                    vx = _to_float(fields[1])
                    vy = _to_float(fields[2])
                    vz = _to_float(fields[3])
                    return (rec_pid, (vx, vy, vz))
        elif upper.startswith("*INITIAL_VELOCITY_GENERATION"):
            j = _next_data_line(i + 1)
            if j < len(lines):
                fields = _read_fields(lines[j], 8)
                # Card 1 (LS-DYNA 971+ format):
                #   field 1: ID  (PART id when STYP=2, set id when STYP=1)
                #   field 2: STYP
                #   field 3: OMEGA (rotational speed about axis)
                #   field 4: VX
                #   field 5: VY
                #   field 6: VZ
                rec_id = _to_int(fields[0])
                styp = _to_int(fields[1], default=2)
                if rec_id > 0 and styp in (1, 2):
                    vx = _to_float(fields[3])
                    vy = _to_float(fields[4])
                    vz = _to_float(fields[5])
                    if pid is None or rec_id == pid:
                        return (rec_id, (vx, vy, vz))
        i += 1
    return (None, (0.0, 0.0, 0.0))


def _parse_initial_velocity_rigid_body(kfile: Path, pid: int) -> tuple[float, float, float]:
    """Back-compat shim: query *INITIAL_VELOCITY_* for a specific PID."""
    _, v = _parse_initial_velocity_any(kfile, pid=pid)
    return v


def _bbox_from_d3plot_part(d3plot_path: Path, pid: int, work_dir: Path) -> tuple[float, float] | None:
    """Return (max_radial_extent_mm, None_placeholder) from motion CSV at t=0.

    The unified_analyzer's ``Max_Disp_Mag`` at t=0 is the distance from the
    part centroid to its farthest node — i.e. the bounding sphere radius.
    Height/length cannot be inferred from a single scalar, so it is left as
    0.0 and downstream code must treat that as "unknown".

    Returns None if the CSV is missing.
    """
    csv_path = work_dir / "motion" / f"part_{pid}_motion.csv"
    if not csv_path.exists():
        return None
    try:
        with open(csv_path, encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                try:
                    far = float(row.get("Max_Disp_Mag", 0))
                    if far > 0:
                        return (far, 0.0)
                except ValueError:
                    continue
    except OSError:
        return None
    return None


def _build_impactor_from_keyword(
    d3plot_path: Path,
    impactor_part_name: str | None = None,
    impactor_part_id: int | None = None,
    work_dir: Path | None = None,
) -> ImpactorSpec | None:
    """Build ImpactorSpec from the .k keyword file beside the d3plot.

    Extracts:
      * impactor PID + name (by name match)
      * material (density [tonne/mm³], E [MPa], ν) from *MAT_ card
      * initial velocity from *INITIAL_VELOCITY_RIGID_BODY
      * geometric extent (radius/height) from motion CSV bounding info if work_dir provided

    Returns None if the keyword file can't be located or impactor not found.
    """
    try:
        from koo_deep_report.core.keyword_parser import parse_keyword_file
    except ImportError:
        print("[loader] keyword_parser not importable — falling back to hardcoded ImpactorSpec")
        return None

    kfile = _find_keyword_file(d3plot_path)
    if kfile is None:
        return None

    try:
        kw = parse_keyword_file(kfile)
    except Exception as e:
        print(f"[loader] keyword_parser failed: {e}")
        return None

    # Find impactor PID in priority order:
    #   1. Caller-supplied explicit id
    #   2. Caller-supplied name substring match
    #   3. PART title heuristic ("impactor"/"ball"/"punch")
    #   4. Any PART carrying a non-zero *INITIAL_VELOCITY_*  (last resort,
    #      essential when the deck has empty PART titles — e.g. the
    #      KooDWITestSetRunner output of Test_Impact_A)
    pid = impactor_part_id
    if pid is None and impactor_part_name:
        pat = impactor_part_name.lower()
        for p_id, part in kw.parts.items():
            if pat in part.name.lower():
                pid = p_id
                break
    if pid is None:
        for p_id, part in kw.parts.items():
            if any(tok in part.name.lower() for tok in ["impactor", "ball", "punch"]):
                pid = p_id
                break
    if pid is None:
        vel_pid, vel_v0 = _parse_initial_velocity_any(kfile, pid=None)
        if vel_pid is not None and vel_pid in kw.parts:
            pid = vel_pid
            print(f"[loader] impactor PID auto-found from *INITIAL_VELOCITY_* card: PID={pid}")
    if pid is None or pid not in kw.parts:
        return None

    part = kw.parts[pid]
    mat = kw.materials.get(part.mid)
    density = mat.density if mat else 0.0
    young = mat.youngs_modulus if mat else 0.0
    nu = mat.poissons_ratio if mat else 0.0
    mat_type = mat.mat_type if mat else ""

    _, v0 = _parse_initial_velocity_any(kfile, pid=pid)

    bbox = _bbox_from_d3plot_part(d3plot_path, pid, work_dir) if work_dir else None
    radius = bbox[0] if bbox else 0.0
    height = bbox[1] if bbox else 0.0

    # Geometry type cannot be inferred from a single *PART card alone — it
    # is left empty so downstream code never silently assumes a sphere.
    # mass derivation in ``load_single_d3plot_report`` uses matsum directly.
    spec = ImpactorSpec(
        type="",
        radius=radius,
        height=height,
        density=density,
        youngs_modulus=young,
        poisson_ratio=nu,
        part_id=pid,
        part_name=part.name,
        mat_type=mat_type,
        initial_velocity=v0,
    )
    print(f"[loader] impactor from .k: PID={pid} '{part.name}' MAT_{mat_type} "
          f"ρ={density:.3e} E={young:.3e} ν={nu:.3f} v₀={v0}")
    return spec


def _compute_contact_mask(
    rcforc_list,
    target_times: list[float],
    peak_ratio: float = 0.10,
    baseline_multiplier: float = 5.0,
) -> list[bool]:
    """Build a per-timestep ``contact_engaged`` boolean mask from rcforc data.

    Detection criteria (both data-driven, unit-agnostic):
      1. Each interface's |F(t)| must exceed ``peak_ratio × peak |F|``
         (default 10 % — well above DampingSpring noise but still catches
         the impact pulse).
      2. AND the force must be at least ``baseline_multiplier × median |F|``
         above the pre-contact baseline (the median of the lowest 20 % of
         force samples). This rejects steady-state preload that would
         otherwise be picked up at low peak_ratio.

    Only ``side == -1`` (total) interfaces are considered when present, so
    each contact contributes once (not twice via master+slave).
    """
    if not rcforc_list or not target_times:
        return [False] * len(target_times)

    # Prefer total-side interfaces. Some binouts emit per-side rows only.
    totals = [rc for rc in rcforc_list if getattr(rc, "side", -1) == -1]
    candidates = totals if totals else list(rcforc_list)

    n = len(target_times)
    mask = [False] * n
    for rc in candidates:
        if not rc.t:
            continue
        fmag = [abs(rc.fx[k]) + abs(rc.fy[k]) + abs(rc.fz[k])
                for k in range(len(rc.t))]
        peak = max(fmag) if fmag else 0.0
        if peak <= 0:
            continue
        # Baseline = median of lowest 20 % (preload / DampingSpring noise).
        sorted_f = sorted(fmag)
        k_lo = max(1, len(sorted_f) // 5)
        baseline = sorted_f[k_lo // 2] if k_lo > 0 else 0.0
        thresh_peak = peak_ratio * peak
        thresh_base = baseline_multiplier * baseline
        thresh = max(thresh_peak, thresh_base)
        for ti, t in enumerate(target_times):
            if rc.t[0] <= t <= rc.t[-1]:
                lo, hi = 0, len(rc.t) - 1
                while lo < hi:
                    mid = (lo + hi) // 2
                    if rc.t[mid] < t:
                        lo = mid + 1
                    else:
                        hi = mid
                if fmag[lo] > thresh:
                    mask[ti] = True
    return mask


_UNIT_PRESETS = {
    "SI": {
        "id": "SI",
        "labels": {
            "acc": "m/s²", "vel": "m/s", "disp": "m",
            "stress": "Pa", "strain": "", "force": "N",
            "energy": "J", "time": "s", "mass": "kg",
        },
    },
    "ton-mm-s": {
        "id": "ton-mm-s",
        "labels": {
            "acc": "mm/s²", "vel": "mm/s", "disp": "mm",
            "stress": "MPa", "strain": "", "force": "N",
            "energy": "mJ", "time": "s", "mass": "tonne",
        },
    },
    "ton-mm-ms": {
        "id": "ton-mm-ms",
        "labels": {
            "acc": "mm/ms²", "vel": "mm/ms", "disp": "mm",
            "stress": "MPa", "strain": "", "force": "kN",
            "energy": "kJ", "time": "ms", "mass": "tonne",
        },
    },
    "g-mm-ms": {
        "id": "g-mm-ms",
        "labels": {
            "acc": "mm/ms²", "vel": "mm/ms", "disp": "mm",
            "stress": "MPa", "strain": "", "force": "N",
            "energy": "mJ", "time": "ms", "mass": "g",
        },
    },
}
_UNIT_UNKNOWN = {"id": "", "labels": {k: "" for k in _UNIT_PRESETS["SI"]["labels"]}}


def _detect_unit_system(
    density: float,
    length_sample: float | None = None,
    velocity_sample: float | None = None,
) -> dict:
    """Guess the LS-DYNA unit system from typical magnitudes.

    LS-DYNA decks are unitless — the user picks a consistent set. Density alone
    is ambiguous when the user wrote SI-style ρ (7800) into a ton-mm-s deck;
    we therefore consult ``length_sample`` (e.g. impactor radius) and
    ``velocity_sample`` (e.g. initial velocity magnitude) when available.

    ============   ============  =============  ============  ==========
    name           length        mass           time          stress
    ============   ============  =============  ============  ==========
    SI             m             kg             s             Pa
    ton-mm-s       mm            tonne (1000 kg) s            MPa
    ton-mm-ms      mm            tonne           ms            MPa
    g-mm-ms        mm            g               ms            MPa
    ============   ============  =============  ============  ==========

    Decision tree (length wins when it disagrees with density):
      length > 10           → solver length is mm  (rules out SI)
      length < 0.5  & density>=1  → SI
      density <= 1e-5       → ton-mm-s
      otherwise unknown
    """
    if density <= 0 and length_sample is None:
        return _UNIT_UNKNOWN

    # Length is the strongest single discriminator: a 57-unit "radius" cannot be 57 m.
    length_says_mm = length_sample is not None and length_sample > 10.0
    length_says_m = length_sample is not None and 0 < length_sample < 0.5

    if length_says_mm:
        return _UNIT_PRESETS["ton-mm-s"]
    if length_says_m and density >= 1.0:
        return _UNIT_PRESETS["SI"]
    if density <= 1.0e-5:
        return _UNIT_PRESETS["ton-mm-s"]
    if density >= 1.0:
        # Falls back to SI when no length disagrees, but flag is weak.
        return _UNIT_PRESETS["SI"]
    return _UNIT_UNKNOWN


def get_unit_preset(name: str) -> dict | None:
    """CLI helper — return a copy of the preset by id or None if unknown."""
    p = _UNIT_PRESETS.get(name)
    if p is None:
        return None
    return {"id": p["id"], "labels": dict(p["labels"])}


def _derive_mass_from_matsum(
    matsum,
    pid: int,
    initial_velocity_mag: float,
) -> float | None:
    """Recover impactor mass [tonne] from matsum kinetic_energy + known v₀.

    Uses the first timestep with KE > 0 and |v| > 0:
        KE = ½ m v² → m = 2·KE / v²

    Returns None if matsum lacks the part or v₀ is zero.
    """
    if matsum is None or not matsum.kinetic_energy or pid not in matsum.part_ids:
        return None
    if initial_velocity_mag <= 0:
        return None
    idx = matsum.part_ids.index(pid)
    for row in matsum.kinetic_energy:
        ke = row[idx]
        if ke > 0:
            return 2.0 * ke / (initial_velocity_mag ** 2)
    return None


def load_per_part_motions(
    d3plot_path: Path,
    part_ids: list[int] | None = None,
    work_dir: Path | None = None,
    threads: int = 2,
) -> tuple[dict[int, PartMotion], object]:
    """Run unified_analyzer for the given parts → parse motion CSVs into PartMotion.

    Reads ALL columns (vel_x/y/z, acc_x/y/z, mag) into PartMotion. Computes
    peak_g and other derived scalars in-place.

    Returns a tuple ``(motions, d3plot_result)`` where ``d3plot_result`` is the
    raw ``koo_deep_report.core.d3plot_reader.D3plotResult`` (or None on
    failure). This exposes per-part stress/strain histories for downstream use.
    """
    try:
        from koo_deep_report.core.d3plot_reader import run_analysis
    except ImportError:
        print("[loader] koo_deep_report not importable — cannot extract per-part motion")
        return {}, None

    if work_dir is None:
        import tempfile
        work_dir = Path(tempfile.mkdtemp(prefix="koo_impact_motion_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    d3plot_result = None
    try:
        d3plot_result = run_analysis(
            d3plot_path=d3plot_path,
            output_dir=work_dir,
            part_ids=part_ids,
            threads=threads,
            verbose=False,
        )
    except Exception as e:
        print(f"[loader] unified_analyzer failed: {e}")
        return {}, None

    motions: dict[int, PartMotion] = {}
    motion_dir = work_dir / "motion"
    if not motion_dir.exists():
        return {}, d3plot_result
    for csv_path in sorted(motion_dir.glob("part_*_motion.csv")):
        try:
            pid = int(csv_path.stem.split("_")[1])
        except (ValueError, IndexError):
            continue
        pm = PartMotion(part_id=pid)
        try:
            with open(csv_path, encoding="utf-8") as f:
                rdr = csv.DictReader(f)
                for row in rdr:
                    def fv(k):
                        try:
                            return float(row.get(k, 0) or 0)
                        except ValueError:
                            return 0.0
                    pm.times.append(fv("Time"))
                    pm.disp_x.append(fv("Avg_Disp_X"))
                    pm.disp_y.append(fv("Avg_Disp_Y"))
                    pm.disp_z.append(fv("Avg_Disp_Z"))
                    pm.disp_mag.append(fv("Avg_Disp_Mag"))
                    pm.vel_x.append(fv("Avg_Vel_X"))
                    pm.vel_y.append(fv("Avg_Vel_Y"))
                    pm.vel_z.append(fv("Avg_Vel_Z"))
                    pm.vel_mag.append(fv("Avg_Vel_Mag"))
                    pm.acc_x.append(fv("Avg_Acc_X"))
                    pm.acc_y.append(fv("Avg_Acc_Y"))
                    pm.acc_z.append(fv("Avg_Acc_Z"))
                    pm.acc_mag.append(fv("Avg_Acc_Mag"))
        except OSError:
            continue
        # Derived scalar summaries — directly from real CSV (no synthetic differentiation)
        if pm.acc_mag:
            i_max = max(range(len(pm.acc_mag)), key=lambda i: pm.acc_mag[i])
            pm.peak_g = float(pm.acc_mag[i_max])
            pm.t_peak_g = float(pm.times[i_max])
            pm.peak_g_xyz = (
                float(pm.acc_x[i_max]) if pm.acc_x else 0.0,
                float(pm.acc_y[i_max]) if pm.acc_y else 0.0,
                float(pm.acc_z[i_max]) if pm.acc_z else 0.0,
            )
        # peak_disp = true displacement from initial position (NOT raw
        # disp_mag, which the unified_analyzer emits as the part centroid's
        # distance from the global origin).
        if pm.disp_x and pm.disp_y and pm.disp_z:
            x0, y0, z0 = pm.disp_x[0], pm.disp_y[0], pm.disp_z[0]
            pm.peak_disp = float(max(
                math.sqrt((x - x0) ** 2 + (y - y0) ** 2 + (z - z0) ** 2)
                for x, y, z in zip(pm.disp_x, pm.disp_y, pm.disp_z)
            ))
        elif pm.disp_mag:
            pm.peak_disp = float(max(pm.disp_mag) - pm.disp_mag[0])
        if pm.vel_mag:
            pm.peak_vel = float(max(pm.vel_mag))
        motions[pid] = pm
    return motions, d3plot_result


def _extract_part_stress_strain(d3plot_result) -> dict[int, dict]:
    """Per-part peak stress/strain + time-series from D3plotResult.

    Returns dict[part_id] = {
        "peak_stress": float (MPa),
        "peak_strain": float,
        "stress_times": list[float],
        "stress_values": list[float],   # max-of-elements per timestep
        "stress_max_series": list[float],
        "strain_times": list[float],
        "strain_values": list[float],
    }

    Uses ``D3plotResult.stress[*]`` and ``.strain[*]`` which are
    ``PartTimeSeries`` (one entry per part with ``global_max`` and
    ``data=[{t, max, min, avg}, ...]``).
    """
    out: dict[int, dict] = {}
    if d3plot_result is None:
        return out

    def _series_to_lists(ts):
        """Convert PartTimeSeries.data → (times, max_values).

        The unified_analyzer JSON uses the full word "time" for the
        timestamp key, NOT a single "t". Accept either to stay robust
        against legacy outputs.
        """
        times = []
        maxes = []
        for d in ts.data or []:
            if not isinstance(d, dict):
                continue
            t = d.get("time", d.get("t"))
            mx = d.get("max")
            if t is None:
                continue
            try:
                times.append(float(t))
                maxes.append(float(mx) if mx is not None else 0.0)
            except (ValueError, TypeError):
                continue
        return times, maxes

    for s in getattr(d3plot_result, "stress", []) or []:
        pid = getattr(s, "part_id", None)
        if pid is None:
            continue
        st_t, st_m = _series_to_lists(s)
        rec = out.setdefault(int(pid), {})
        rec["peak_stress"] = float(getattr(s, "global_max", 0.0) or 0.0)
        rec["stress_unit"] = getattr(s, "unit", "") or ""
        rec["stress_times"] = st_t
        rec["stress_max_series"] = st_m

    for s in getattr(d3plot_result, "strain", []) or []:
        pid = getattr(s, "part_id", None)
        if pid is None:
            continue
        sn_t, sn_m = _series_to_lists(s)
        rec = out.setdefault(int(pid), {})
        rec["peak_strain"] = float(getattr(s, "global_max", 0.0) or 0.0)
        rec["strain_times"] = sn_t
        rec["strain_max_series"] = sn_m

    return out


def load_impactor_trajectory_from_d3plot(
    d3plot_path: Path,
    impactor_part_id: int | None = None,
    impactor_part_name: str | None = None,
    work_dir: Path | None = None,
    threads: int = 2,
    impactor_mass: float | None = None,
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
                # KE per step. When ``impactor_mass`` is unknown, we store
                # the mass-normalised energy ½v² — units (mm/s)². The matsum
                # override block below replaces this with absolute KE from
                # binout (the authoritative source) when available.
                v_sq = vx * vx + vy * vy + vz * vz
                if impactor_mass is None:
                    traj.ke.append(0.5 * v_sq)
                else:
                    traj.ke.append(0.5 * impactor_mass * v_sq)
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
            traj.contact_engaged = _compute_contact_mask(binout.rcforc, traj.times)
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
        generation_mode=sim_params.get("generation_mode", ""),
        boundary_distance=float(sim_params.get("boundary_distance", 0.0)),
        offset_distance=float(sim_params.get("offset_distance", 0.0)),
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
    impactor_part_name: str | None = None,
    face_code: str | None = None,
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

    # 1) Parse keyword file: impactor spec + parts dict (PID → name, MID)
    impactor_spec = _build_impactor_from_keyword(
        d3plot_path, impactor_part_name=impactor_part_name
    )
    impactor_pid: int | None = impactor_spec.part_id if impactor_spec else None
    if impactor_pid is None:
        # Fallback to the older name-only heuristic
        impactor_pid = _find_impactor_part_id(d3plot_path, impactor_part_name)
        if impactor_pid is None:
            print(f"[loader] WARN  impactor part not found in keyword file")

    # 2) Run unified_analyzer once for ALL parts → motion CSVs
    kw_data = None
    try:
        from koo_deep_report.core.keyword_parser import parse_keyword_file
        kfile = _find_keyword_file(d3plot_path)
        if kfile is not None:
            kw_data = parse_keyword_file(kfile)
    except Exception as e:
        print(f"[loader] keyword_parser unavailable: {e}")

    part_ids_to_extract: list[int] | None = None
    if kw_data and kw_data.parts:
        part_ids_to_extract = sorted(kw_data.parts.keys())

    if work_dir is None:
        import tempfile
        work_dir = Path(tempfile.mkdtemp(prefix="koo_impact_single_"))
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"[loader] running unified_analyzer for parts={part_ids_to_extract or 'auto'}")
    motions, d3plot_result = load_per_part_motions(
        d3plot_path=d3plot_path,
        part_ids=part_ids_to_extract,
        work_dir=work_dir,
        threads=threads,
    )
    stress_strain = _extract_part_stress_strain(d3plot_result)

    # Refresh impactor bbox from motion CSV now that work_dir is populated
    if impactor_spec is not None and impactor_pid is not None and impactor_pid in motions:
        bbox = _bbox_from_d3plot_part(d3plot_path, impactor_pid, work_dir)
        if bbox is not None:
            impactor_spec.radius, impactor_spec.height = bbox

    # 3) Binout: matsum/rcforc + mass derivation
    bin_data = load_binout_energy(parent)
    matsum = bin_data.get("matsum")
    rcforc = bin_data.get("rcforc") or []

    impactor_mass: float | None = None
    if impactor_spec is not None and impactor_pid is not None:
        v0 = impactor_spec.initial_velocity
        v0_mag = math.sqrt(v0[0] ** 2 + v0[1] ** 2 + v0[2] ** 2)
        impactor_mass = _derive_mass_from_matsum(matsum, impactor_pid, v0_mag)
        if impactor_mass is None and impactor_spec.density > 0 and impactor_spec.volume > 0:
            impactor_mass = impactor_spec.density * impactor_spec.volume
        if impactor_mass is not None:
            impactor_spec.mass_override = impactor_mass
            print(f"[loader] impactor mass = {impactor_mass:.4e} tonne "
                  f"(from {'matsum KE/v²' if matsum else 'ρ·V'})")

    # 4) Build impactor trajectory using REAL mass (not placeholder 1.0)
    traj = ImpactorTrajectory()
    if impactor_pid is not None and impactor_pid in motions:
        pm = motions[impactor_pid]
        traj.times = list(pm.times)
        traj.pos_x = list(pm.disp_x)
        traj.pos_y = list(pm.disp_y)
        traj.pos_z = list(pm.disp_z)
        traj.vel_x = list(pm.vel_x)
        traj.vel_y = list(pm.vel_y)
        traj.vel_z = list(pm.vel_z)
        # KE in absolute units only if mass is known. Otherwise store the
        # mass-normalised ½v² (the matsum override below replaces both).
        if impactor_mass is not None:
            traj.ke = [0.5 * impactor_mass * (vx * vx + vy * vy + vz * vz)
                       for vx, vy, vz in zip(pm.vel_x, pm.vel_y, pm.vel_z)]
        else:
            traj.ke = [0.5 * (vx * vx + vy * vy + vz * vz)
                       for vx, vy, vz in zip(pm.vel_x, pm.vel_y, pm.vel_z)]
        traj.contact_engaged = [False] * len(traj.times)

        # Override KE with binout matsum if present (authoritative)
        if matsum and impactor_pid in matsum.part_ids:
            idx = matsum.part_ids.index(impactor_pid)
            ms_t = matsum.t
            ke_series = [row[idx] for row in matsum.kinetic_energy]
            if len(ms_t) >= 2 and len(traj.times) >= 1:
                interp = []
                for t in traj.times:
                    j = 0
                    while j < len(ms_t) - 1 and ms_t[j + 1] < t:
                        j += 1
                    if j >= len(ms_t) - 1:
                        interp.append(ke_series[-1])
                    else:
                        dt = ms_t[j + 1] - ms_t[j] or 1
                        f = (t - ms_t[j]) / dt
                        interp.append(ke_series[j] + f * (ke_series[j + 1] - ke_series[j]))
                traj.ke = interp

        # Derive contact_engaged from rcforc (data-driven, unit-agnostic).
        if rcforc:
            traj.contact_engaged = _compute_contact_mask(rcforc, traj.times)

        _compute_trajectory_summaries(traj)

    # 5) Build parts list from keyword file (authoritative) or matsum fallback
    parts: list[PartInfo] = []
    if kw_data and kw_data.parts:
        for pid in sorted(kw_data.parts.keys()):
            part = kw_data.parts[pid]
            mat = kw_data.materials.get(part.mid)
            mat_label = (mat.mat_type if mat else "") or ""
            parts.append(PartInfo(
                part_id=pid,
                part_name=part.name,
                group=mat_label or PartInfo.extract_group(part.name),
            ))
    elif matsum:
        for pid, pname in zip(matsum.part_ids, matsum.part_names):
            parts.append(PartInfo(part_id=int(pid), part_name=pname,
                                  group=PartInfo.extract_group(pname)))
    if not parts:
        parts = [PartInfo(part_id=1, part_name="Part_1", group="Default")]

    # 6) Single position. Face code is derived from the impactor's initial
    # velocity direction (the face whose outward normal opposes v₀). The
    # caller can still force a specific face via the ``face_code`` argument.
    if face_code is None and impactor_spec is not None:
        face_code = _face_code_from_velocity(impactor_spec.initial_velocity)
    if face_code is None or face_code not in FACE_STANDARD:
        # No initial velocity data and no caller override — emit an explicit
        # "Unknown" face rather than a hardcoded fallback. Direction-zero
        # orientation reflects the absence of derivable data.
        face_code = "FX"
        face = FaceOrientation(code="FX", name="Unknown", yaw=0.0, pitch=0.0, roll=0.0)
        print(f"[loader] WARN  face could not be derived from v₀ — labelled 'FX/Unknown'")
    else:
        face = FACE_STANDARD[face_code]
        print(f"[loader] face auto-detected from v₀: {face_code} ({face.name})")
    pos = ImpactPosition(
        pos_id=f"{face_code}_P_0001",
        face=face_code,
        x=float(traj.pos_x[0]) if traj.pos_x else 0.0,
        y=float(traj.pos_y[0]) if traj.pos_y else 0.0,
        run_dir=parent,
    )

    results: list[PairResult] = []
    for p in parts:
        pm = motions.get(p.part_id)
        ss = stress_strain.get(p.part_id, {})
        # Prefer real element-level stress (MPa) from d3plot. Fall back to
        # internal-energy proxy (mJ) from binout matsum when stress is absent.
        peak_stress = float(ss.get("peak_stress", 0.0) or 0.0)
        if peak_stress <= 0.0 and matsum and p.part_id in matsum.part_ids:
            idx = matsum.part_ids.index(p.part_id)
            ies = [row[idx] for row in matsum.internal_energy]
            peak_stress = max(ies) if ies else 0.0

        # Stress time series: real (times + max-per-step), else empty
        stress_ts = TimeSeriesData(
            times=list(ss.get("stress_times") or []),
            max_values=list(ss.get("stress_max_series") or []),
        )

        results.append(PairResult(
            face=face_code,
            position=pos,
            part_id=p.part_id,
            peak_g=float(pm.peak_g) if pm else 0.0,
            peak_stress=peak_stress,
            peak_strain=float(ss.get("peak_strain", 0.0) or 0.0),
            peak_disp=float(pm.peak_disp) if pm else 0.0,
            peak_vel=float(pm.peak_vel) if pm else 0.0,
            stress_ts=stress_ts,
            impactor_trajectory=traj,
            part_motion=pm,
        ))

    # 7) Fallback ImpactorSpec when keyword parsing failed: leave geometry
    # type empty rather than assuming "Sphere"; all numeric fields stay 0.0.
    if impactor_spec is None:
        impactor_spec = ImpactorSpec(type="")
        print("[loader] WARN  ImpactorSpec empty (no keyword data); type left as ''")

    impactor_trajectories = {pos.pos_id: traj}
    part_motions_keyed = {(pos.pos_id, pid): pm for pid, pm in motions.items()}

    print(f"[loader] single d3plot: {len(parts)} part(s), "
          f"traj n_states={len(traj.times)}, "
          f"behavior={traj.behavior_class}, KE retention={traj.ke_retention:.3f}, "
          f"peak_g={'/'.join(f'{p.part_id}:{(motions[p.part_id].peak_g if p.part_id in motions else 0.0):.1e}' for p in parts)}")

    return ImpactReport(
        project_name=project_name,
        impactor=impactor_spec,
        # Single-d3plot mode: no DOE generation_mode/boundary/offset apply.
        # These are DOE-only parameters; leave them empty/zero so HTML
        # consumers know they are not derived from this dataset.
        generation_mode="",
        boundary_distance=0.0,
        offset_distance=0.0,
        faces=[face],
        positions_by_face={face_code: [pos]},
        parts=parts,
        results=results,
        findings=[],
        sim_params={
            "t_final": float(traj.times[-1]) if traj.times else 0.0,
            "n_states": len(traj.times),
            "impactor_mass": impactor_mass or 0.0,
            "impactor_v0":   impactor_spec.initial_velocity,
            # Unit system is auto-detected from material density magnitude;
            # see ``_detect_unit_system``. Either "SI" or "ton-mm-s" (or ""
            # when undetectable). The HTML/terminal layers consume only the
            # labels, never the numeric magnitudes, so this is purely
            # presentational metadata.
            **(
                lambda _d: {"units": _d["id"], "unit_labels": _d["labels"]}
            )(_detect_unit_system(
                impactor_spec.density,
                length_sample=max(
                    impactor_spec.radius or 0.0,
                    getattr(impactor_spec, "front_radius", 0.0) or 0.0,
                    getattr(impactor_spec, "outer_radius", 0.0) or 0.0,
                ),
                velocity_sample=abs(
                    impactor_spec.initial_velocity[-1]
                    if impactor_spec.initial_velocity else 0.0
                ),
            )),
            # Per-part yield stress (MPa) sourced from the *MAT_ card. Empty
            # when keyword data is missing or the material exposes no yield.
            "yield_stress_by_part": (
                {
                    pid: float(kw_data.materials[part.mid].yield_stress)
                    for pid, part in kw_data.parts.items()
                    if part.mid in kw_data.materials
                       and kw_data.materials[part.mid].yield_stress > 0
                } if kw_data else {}
            ),
        },
        doe_config={"single_d3plot": True, "source": str(d3plot_path)},
        test_dir=str(parent),
        impactor_trajectories=impactor_trajectories,
        part_motions=part_motions_keyed,
    )


# ---------------------------------------------------------------------------
# Multi-position DOE adapter — KooDWITestSetRunner layout (e.g. Test_Impact_A)
# ---------------------------------------------------------------------------

def _parse_step_config_kv(path: Path) -> dict[str, str]:
    """Parse a ``step_config.txt`` produced by KooDWITestSetRunner.

    The file is a comma-prefixed-keyword format::
        *Description,DOE001 Step1 IMPACT P_001_001
        LocationX,-40.0
        LocationY,-40.0
        Height,0.5
        Type,Sphere
        Dimension,0.008
        Density,7800
        YoungsModulus,201000000000
        PoissonRatio,0.3
        tFinal,0.001
        dt,1e-06

    Returns a flat ``{key: value_str}`` dict. Lines starting with ``*`` and
    ``**`` are also captured (key includes the asterisk prefix), so callers
    can pick out ``*Description`` if needed.
    """
    out: dict[str, str] = {}
    if not path.exists():
        return out
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or "," not in line:
                continue
            key, _, val = line.partition(",")
            out[key.strip()] = val.strip()
    except OSError as exc:
        print(f"[doe] WARN  step_config unreadable: {path}: {exc}")
        return {}
    return out


def _discover_test_impact_runs(test_dir: Path) -> list[dict]:
    """List ``output/Run_*`` directories with their step_config + d3plot path.

    Returns a list of dicts sorted by DOE index (parsed from
    ``*Description``):

        [{"run_dir": Path(...), "d3plot": Path(...),
          "step_config": Path(...), "config": {...kv...},
          "doe_index": int, "pos_name": str,
          "location_x": float, "location_y": float}, ...]

    Skips runs with missing d3plot or step_config.
    """
    output_dir = test_dir / "output"
    if not output_dir.exists():
        return []

    items: list[dict] = []
    for run in sorted(output_dir.iterdir()):
        if not run.is_dir() or not run.name.startswith("Run_"):
            continue
        d3plot = run / "Output" / "d3plot"
        cfg_path = run / "step_config.txt"
        if not d3plot.exists() or not cfg_path.exists():
            continue
        cfg = _parse_step_config_kv(cfg_path)
        # *Description = "DOE001 Step1 IMPACT P_001_001"
        desc = cfg.get("*Description", "")
        doe_idx = 0
        # KooDWITestSetRunner currently emits the SAME "P_001_001" token in
        # *Description for every DOE entry — only the leading "DOE###" is
        # unique. We therefore key positions by DOE index (and fall back to
        # the discovery order). The raw upstream token is kept for traceability.
        raw_pos_token = ""
        if desc:
            tokens = desc.split()
            for tok in tokens:
                if tok.upper().startswith("DOE"):
                    try:
                        doe_idx = int(tok[3:].lstrip("0") or "0")
                    except ValueError:
                        doe_idx = 0
                if tok.upper().startswith("P_"):
                    raw_pos_token = tok
        if doe_idx > 0:
            pos_name = f"DOE_{doe_idx:03d}"
            sort_index = doe_idx
        else:
            # *Description missing or unparseable: keep discovery order stable
            # by assigning a synthetic high doe_index (10000 + 1-based seq) so
            # these runs (a) get unique pos_name and (b) sort deterministically
            # AFTER any successfully-parsed DOE entries.
            seq = len(items) + 1
            pos_name = f"DOE_{seq:03d}"
            sort_index = 10000 + seq
            print(f"[loader] WARN  {run.name}: could not parse DOE index from "
                  f"*Description={desc!r} — using fallback pos_name={pos_name}")
        try:
            lx = float(cfg.get("LocationX", "0"))
        except ValueError:
            lx = 0.0
        try:
            ly = float(cfg.get("LocationY", "0"))
        except ValueError:
            ly = 0.0
        items.append({
            "run_dir":     run,
            "d3plot":      d3plot,
            "step_config": cfg_path,
            "config":      cfg,
            "doe_index":   doe_idx,
            "pos_name":    pos_name,
            "raw_pos":     raw_pos_token,
            "location_x":  lx,
            "location_y":  ly,
            "_sort_index": sort_index,
        })
    items.sort(key=lambda x: x["_sort_index"])
    return items


def _load_one_run_subreport(args: tuple) -> ImpactReport | None:
    """Worker: load one Test_Impact_A run as a 1-position ImpactReport.

    Defined at module scope so it can be pickled for use with
    ``concurrent.futures.ProcessPoolExecutor``. The arg is a tuple to ease
    parameter passing through the executor.
    """
    d3plot_path, project_name, impactor_part_name, threads, work_dir_str = args
    work_dir = Path(work_dir_str) if work_dir_str else None
    return load_single_d3plot_report(
        d3plot_path=Path(d3plot_path),
        project_name=project_name,
        impactor_part_name=impactor_part_name,
        face_code=None,             # auto-detect from v₀
        work_dir=work_dir,
        threads=threads,
    )


def load_partial_impact_doe_report(
    test_dir: Path,
    impactor_part_name: str | None = None,
    threads_per_run: int = 2,
    parallel_runs: int = 4,
) -> ImpactReport:
    """Load a multi-position partial-impact DOE (KooDWITestSetRunner layout).

    The expected directory layout::

        test_dir/
            scenario.json
            jobs.json                 (optional — slurm submission manifest)
            output/
                Run_<ts>_<hash>/
                    DropWeightImpactTestSet.k
                    step_config.txt       # LocationX/Y, Height, etc.
                    Output/
                        d3plot, binout0000, glstat, ...
                Run_<ts>_<hash>/
                    ...

    Each ``Run_*`` becomes one ``ImpactPosition`` keyed by its (LocationX,
    LocationY). All runs share the same impactor and (typically) the same
    parts list, which is auto-detected from the first run's keyword file.

    Args:
        test_dir: project root containing ``scenario.json`` and ``output/``.
        impactor_part_name: optional name override; defaults to auto-detect
            via ``*INITIAL_VELOCITY_*`` card.
        threads_per_run: ``unified_analyzer`` thread count per run.
        parallel_runs: number of runs processed concurrently (process pool).
    """
    test_dir = Path(test_dir).resolve()
    scenario_path = test_dir / "scenario.json"
    scenario = load_scenario(scenario_path)
    project_name = scenario.get("project_name", test_dir.name) if scenario else test_dir.name

    runs = _discover_test_impact_runs(test_dir)
    if not runs:
        raise FileNotFoundError(
            f"No usable runs found under {test_dir/'output'}/Run_* (need d3plot + step_config.txt)"
        )
    print(f"[doe] {project_name}: {len(runs)} runs discovered")

    # Process each run as its own single-d3plot report, in parallel.
    import tempfile
    work_root = Path(tempfile.mkdtemp(prefix="koo_impact_doe_"))
    job_args = [
        (
            str(run["d3plot"]),
            f"{project_name}_{run['pos_name']}",
            impactor_part_name,
            threads_per_run,
            str(work_root / f"{run['pos_name']}"),
        )
        for run in runs
    ]

    sub_reports: list[ImpactReport | None] = [None] * len(runs)
    if parallel_runs > 1 and len(runs) > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=parallel_runs) as ex:
            futs = {ex.submit(_load_one_run_subreport, a): i for i, a in enumerate(job_args)}
            for fut in as_completed(futs):
                idx = futs[fut]
                try:
                    sub_reports[idx] = fut.result()
                    print(f"[doe]   {runs[idx]['pos_name']:>9s}  ({runs[idx]['location_x']:+.1f}, {runs[idx]['location_y']:+.1f}) ✓")
                except Exception as e:
                    print(f"[doe]   {runs[idx]['pos_name']} FAILED: {type(e).__name__}: {e}")
    else:
        for i, a in enumerate(job_args):
            try:
                sub_reports[i] = _load_one_run_subreport(a)
                print(f"[doe]   {runs[i]['pos_name']:>9s}  ({runs[i]['location_x']:+.1f}, {runs[i]['location_y']:+.1f}) ✓")
            except Exception as e:
                print(f"[doe]   {runs[i]['pos_name']} FAILED: {type(e).__name__}: {e}")

    # Merge sub-reports into one multi-position ImpactReport. All runs share
    # the same face (auto-detected from v₀) and the same parts list.
    impactor_spec: ImpactorSpec | None = None
    face: FaceOrientation | None = None
    face_code: str = ""
    parts_by_id: dict[int, PartInfo] = {}
    positions: list[ImpactPosition] = []
    results: list[PairResult] = []
    impactor_trajectories: dict[str, ImpactorTrajectory] = {}
    part_motions: dict[tuple[str, int], PartMotion] = {}
    yield_stress_by_part: dict[int, float] = {}
    sample_sim_params: dict = {}
    seen_pos_ids: set[str] = set()

    # Two-pass face/spec selection: prefer the first sub-report whose face is
    # a real F1~F6 code (not "FX"/Unknown) so that an early v₀=0 run can't lock
    # the merged report to FX. Fall back to the first non-None sub-report if no
    # run has a real face.
    def _has_real_face(s: ImpactReport | None) -> bool:
        return s is not None and bool(s.results) and bool(s.faces) and s.faces[0].code != "FX"

    seed_sub: ImpactReport | None = next(
        (s for s in sub_reports if _has_real_face(s)),
        None,
    )
    if seed_sub is None:
        seed_sub = next(
            (s for s in sub_reports if s is not None and s.results),
            None,
        )
    if seed_sub is not None:
        impactor_spec = seed_sub.impactor
        face = seed_sub.faces[0] if seed_sub.faces else None
        face_code = face.code if face else "FX"
        sample_sim_params = dict(seed_sub.sim_params or {})
        yield_stress_by_part = dict((seed_sub.sim_params or {}).get("yield_stress_by_part", {}) or {})

    for run, sub in zip(runs, sub_reports):
        if sub is None or not sub.results:
            continue

        # Build the canonical pos_id from the project-level DOE name so it's
        # stable across the report (sub-reports used "F5_P_0001" generically).
        pos_id = f"{face_code}_{run['pos_name']}"
        if pos_id in seen_pos_ids:
            raise RuntimeError(
                f"Duplicate pos_id detected during DOE merge: {pos_id!r}. "
                f"Each run must have a unique 'pos_name' within the scenario."
            )
        seen_pos_ids.add(pos_id)
        pos = ImpactPosition(
            pos_id=pos_id,
            face=face_code,
            x=float(run["location_x"]),
            y=float(run["location_y"]),
            run_dir=run["run_dir"],
        )
        positions.append(pos)

        # Trajectory keyed by the new pos_id (sub-report had a different key)
        if sub.impactor_trajectories:
            traj = next(iter(sub.impactor_trajectories.values()))
            impactor_trajectories[pos_id] = traj
        else:
            traj = ImpactorTrajectory()

        for p in sub.parts:
            parts_by_id.setdefault(p.part_id, p)

        for r in sub.results:
            pm = r.part_motion
            if pm is not None:
                part_motions[(pos_id, r.part_id)] = pm
            results.append(PairResult(
                face=face_code,
                position=pos,
                part_id=r.part_id,
                peak_g=r.peak_g,
                peak_stress=r.peak_stress,
                peak_strain=r.peak_strain,
                peak_disp=r.peak_disp,
                peak_vel=r.peak_vel,
                stress_ts=r.stress_ts,
                impactor_trajectory=traj,
                part_motion=pm,
            ))

    n_failed = len(runs) - sum(1 for s in sub_reports if s is not None and s.results)
    if impactor_spec is None:
        raise RuntimeError("All runs failed to load — no usable sub-reports.")
    if n_failed > 0:
        print(f"[doe] WARN: {n_failed}/{len(runs)} runs failed to load — report covers only {len(runs) - n_failed} positions.")

    # Sanity check: warn if later sub-reports' impactor differs from the kept
    # spec by more than 1%. We do NOT swap specs — just surface the divergence
    # so a user can spot accidentally-mixed DOE runs.
    def _rel_diff(a: float, b: float) -> float:
        denom = max(abs(a), abs(b), 1e-30)
        return abs(a - b) / denom
    ref_density = float(impactor_spec.density or 0.0)
    ref_mass = impactor_spec.mass_override
    ref_v = tuple(float(c) for c in impactor_spec.initial_velocity)
    for run, sub in zip(runs, sub_reports):
        if sub is None or sub.impactor is impactor_spec:
            continue
        spec = sub.impactor
        mismatches: list[str] = []
        if _rel_diff(float(spec.density or 0.0), ref_density) > 0.01:
            mismatches.append(f"density {spec.density:.3e} vs {ref_density:.3e}")
        if (ref_mass is None) != (spec.mass_override is None):
            mismatches.append(f"mass_override {spec.mass_override} vs {ref_mass}")
        elif ref_mass is not None and spec.mass_override is not None \
                and _rel_diff(float(spec.mass_override), float(ref_mass)) > 0.01:
            mismatches.append(f"mass_override {spec.mass_override:.3e} vs {ref_mass:.3e}")
        sv = tuple(float(c) for c in spec.initial_velocity)
        v_ref_mag = (ref_v[0]**2 + ref_v[1]**2 + ref_v[2]**2) ** 0.5
        v_diff_mag = ((sv[0]-ref_v[0])**2 + (sv[1]-ref_v[1])**2 + (sv[2]-ref_v[2])**2) ** 0.5
        if v_diff_mag / max(v_ref_mag, 1e-30) > 0.01:
            mismatches.append(f"initial_velocity {sv} vs {ref_v}")
        if mismatches:
            print(f"[doe] WARN {run['pos_name']}: impactor mismatch — "
                  + "; ".join(mismatches))

    parts = [parts_by_id[k] for k in sorted(parts_by_id)]
    print(f"[doe] merged: {len(positions)} positions × {len(parts)} parts "
          f"= {len(results)} PairResult, face={face_code}")

    # Assemble final sim_params: keep unit metadata + yield map from any sub
    # (they should all match), plus DOE summary.
    sim_params = dict(sample_sim_params)
    # Override unit metadata at the DOE level — impactor.radius is the strongest
    # single discriminator (a 57-unit radius cannot be 57 m), and the sub-runs
    # were detected without that length context.
    if impactor_spec is not None and (impactor_spec.radius or 0.0) > 0:
        _u = _detect_unit_system(
            impactor_spec.density,
            length_sample=max(
                impactor_spec.radius or 0.0,
                getattr(impactor_spec, "front_radius", 0.0) or 0.0,
                getattr(impactor_spec, "outer_radius", 0.0) or 0.0,
            ),
            velocity_sample=abs(
                impactor_spec.initial_velocity[-1]
                if impactor_spec.initial_velocity else 0.0
            ),
        )
        if _u["id"]:
            sim_params["units"] = _u["id"]
            sim_params["unit_labels"] = _u["labels"]
    sim_params.update({
        "doe_kind":      "partial_impact_multi_position",
        "n_positions":   len(positions),
        "n_failed":      n_failed,
        "n_parts":       len(parts),
        "yield_stress_by_part": yield_stress_by_part,
    })
    # Scenario hint (grid bbox / nxm) if available
    if scenario and isinstance(scenario.get("scenarios"), list) and scenario["scenarios"]:
        src = scenario["scenarios"][0].get("position_source") or {}
        grid = src.get("grid_nxm") or {}
        if grid:
            sim_params["grid"] = {
                "nx": grid.get("nx"),
                "ny": grid.get("ny"),
                "bbox": grid.get("bbox"),
            }

    return ImpactReport(
        project_name=project_name,
        impactor=impactor_spec,
        generation_mode="",
        boundary_distance=0.0,
        offset_distance=0.0,
        faces=[face] if face else [],
        positions_by_face={face_code: positions},
        parts=parts,
        results=results,
        findings=[],
        sim_params=sim_params,
        doe_config={
            "kind": "partial_impact_multi_position",
            "source": str(test_dir),
            "n_runs": len(runs),
        },
        test_dir=str(test_dir),
        impactor_trajectories=impactor_trajectories,
        part_motions=part_motions,
    )
