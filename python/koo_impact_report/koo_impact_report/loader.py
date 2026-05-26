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
import json
from pathlib import Path

from .models import (
    FaceOrientation, ImpactPosition, ImpactReport, ImpactorSpec,
    PairResult, PartInfo, TimeSeriesData,
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
            results.extend(_pair_results_from_run(analysis, face_code, pos))
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
    )
