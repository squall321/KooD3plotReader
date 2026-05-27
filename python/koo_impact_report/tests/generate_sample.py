"""Synthetic multi-face partial-impact (drop-weight) dataset generator.

Produces a complete realistic mock dataset directory tree that mirrors what a
real pyKooCAE ``drop_weight_impact_multiface`` run would emit, so the
``koo_impact_report`` loader / analyzer / html_report can be exercised end-to-
end without running LS-DYNA.

Schema references:
  - docs/PartialImpactReport_Plan.md §2 (input data schema)
  - docs/PartialImpactReport_Plan.md §14 (pyKooCAE)
  - docs/PartialImpactReport_Plan.md §15.4-15.5 (multi-face dir + scenario v2)
  - docs/PartialImpactReport_Plan.md §22.2 (energy data sources)
  - pyKooCAE/Examples/drop_weight_impact/scenario.json (real format)
  - pyKooCAE/Runner/ImpactPositionSource.py (P_<row>_<col> naming)

Usage::

    python3 tests/generate_sample.py --output examples/sample_multiface_dataset --seed 42

NOTE: All units follow pyKooCAE's mm / g / mm·s convention. Energies are
reported in J for human readability (matsum/glstat CSVs).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Static device + impactor specification
# ---------------------------------------------------------------------------

DEVICE_BBOX = {"x_min": -50.0, "x_max": 50.0, "y_min": -40.0, "y_max": 40.0, "z_min": 0.0, "z_max": 15.0}

# 12 parts arranged for a smartphone analogy.
#   z_max = 15.0 → "Front" surface (screen side, hit by F2 Front impacts)
#   z_min =  0.0 → "Back"  surface (back cover, hit by F1 Back  impacts)
#
# Front-side parts (near z=top, z_max=15):
#   PCB\Main, Motor, PKG\IC1, PKG\IC2 → exposed to F2 (Front) impacts.
# Mid-stack parts:
#   PKG\Memory_1, PKG\Memory_2, Connector.
# Back-side parts (near z=bottom, z_min=0):
#   Battery, Frame, Housing\Back → exposed to F1 (Back) impacts.
# Mid-side (full z-extent rim parts):
#   Front\Wall, Housing\Frame.
#
# footprint = (x0, y0, x1, y1) within device bbox; z_range = (zmin, zmax).
PARTS: list[dict] = [
    # --- Front-side (z ≈ 11-14) ---
    {"id": 1,  "name": r"PCB\Main",         "fp": (-35, -25,  35,  25), "z": (11.0, 12.5)},
    {"id": 2,  "name": r"Motor",            "fp": (-40, -15, -30,  -5), "z": (11.5, 13.5)},
    {"id": 3,  "name": r"PKG\IC1",          "fp": (-10,  -5,  10,   8), "z": (12.5, 13.8)},
    {"id": 4,  "name": r"PKG\IC2",          "fp": ( 15,  10,  35,  25), "z": (12.5, 13.8)},
    # --- Mid stack (z ≈ 6-10) ---
    {"id": 5,  "name": r"PKG\Memory_1",     "fp": ( 18,  12,  28,  22), "z": ( 8.5,  9.5)},
    {"id": 6,  "name": r"PKG\Memory_2",     "fp": (-28, -22, -18, -12), "z": ( 8.5,  9.5)},
    {"id": 7,  "name": r"Connector",        "fp": ( 30, -10,  45,  10), "z": ( 6.0, 10.0)},
    # --- Back-side (z ≈ 0-5) ---
    {"id": 8,  "name": r"Battery",          "fp": (-15, -30,  25,  10), "z": ( 1.5,  5.0)},
    {"id": 9,  "name": r"Frame",            "fp": (-40, -32,  40,  32), "z": ( 0.5,  3.0)},
    {"id": 10, "name": r"Housing\Back",     "fp": (-48, -38,  48,  38), "z": ( 0.0,  1.0)},
    # --- Mid-side rims (full-height side walls) ---
    {"id": 11, "name": r"Front\Wall",       "fp": (-48, -38, -45,  38), "z": ( 0.0, 15.0)},
    {"id": 12, "name": r"Housing\Frame",    "fp": (-48, -38,  48,  38), "z": ( 1.5, 14.5)},
]

# Each part's per-metric vulnerability multiplier (Bayesian "prior" on how
# fragile this part is). 1.0 = baseline, >1 = fragile.
PART_FRAGILITY: dict[int, dict] = {
    1:  {"g": 1.8, "stress": 1.3, "strain": 1.5, "disp": 1.0},  # PCB\Main: shock-sensitive
    2:  {"g": 1.0, "stress": 0.8, "strain": 0.9, "disp": 1.4},  # Motor: displacement-sensitive
    3:  {"g": 1.4, "stress": 1.2, "strain": 1.0, "disp": 0.8},  # IC1
    4:  {"g": 1.4, "stress": 1.2, "strain": 1.0, "disp": 0.8},  # IC2
    5:  {"g": 1.3, "stress": 1.0, "strain": 1.1, "disp": 0.7},  # Memory_1
    6:  {"g": 1.3, "stress": 1.0, "strain": 1.1, "disp": 0.7},  # Memory_2
    7:  {"g": 0.9, "stress": 1.1, "strain": 1.0, "disp": 1.0},  # Connector
    8:  {"g": 0.7, "stress": 0.6, "strain": 0.8, "disp": 1.3},  # Battery: disp matters
    9:  {"g": 0.5, "stress": 1.0, "strain": 0.4, "disp": 0.5},  # Frame: stiff
    10: {"g": 0.5, "stress": 0.9, "strain": 0.4, "disp": 0.6},  # Housing\Back: stiff
    11: {"g": 0.6, "stress": 1.2, "strain": 0.6, "disp": 0.5},  # Front\Wall
    12: {"g": 0.5, "stress": 1.0, "strain": 0.4, "disp": 0.5},  # Housing\Frame
}

# Faces: cuboid-6 standard (plan §15.2). Grid per face per spec.
# Each entry: (code, name, roll, pitch, yaw, nx, ny).
# The model layer still supports all 6 faces; the smartphone-scope default
# generation only uses F1 (Back) and F2 (Front). Pass ``--faces all`` (or a
# comma-separated subset) to override.
FACES: list[dict] = [
    {"code": "F1", "name": "Back",   "roll":    0, "pitch":   0, "yaw": 0, "nx": 5, "ny": 5},
    {"code": "F2", "name": "Front",  "roll":  180, "pitch":   0, "yaw": 0, "nx": 5, "ny": 5},
    {"code": "F3", "name": "Right",  "roll":    0, "pitch": -90, "yaw": 0, "nx": 3, "ny": 5},
    {"code": "F4", "name": "Left",   "roll":    0, "pitch":  90, "yaw": 0, "nx": 3, "ny": 5},
    {"code": "F5", "name": "Top",    "roll":   90, "pitch":   0, "yaw": 0, "nx": 5, "ny": 3},
    {"code": "F6", "name": "Bottom", "roll":  -90, "pitch":   0, "yaw": 0, "nx": 5, "ny": 3},
]

# Smartphone-scope default: only Front + Back impacts.
DEFAULT_FACES: list[str] = ["F1", "F2"]

# Impactor: Sphere, r=5mm, h=100mm drop, density=7850 kg/m^3.
IMPACTOR_SPEC = {
    "type": "Sphere",
    "radius": 5.0,
    "height": 100.0,
    "density": 7850.0,
    "youngs_modulus": 2.0e11,
    "poisson_ratio": 0.3,
}

# Alternate cylinder spec for scenario_cylinder.json
IMPACTOR_CYLINDER = {
    "type": "Cylinder",
    "front_radius": 3.0,
    "outer_radius": 6.0,
    "front_height": 5.0,
    "back_height": 10.0,
    "back_radius": 6.0,
    "height": 150.0,
    "density": 7850.0,
    "youngs_modulus": 2.0e11,
    "poisson_ratio": 0.3,
}

# 21 timesteps from 0 to 1ms (matches tFinal=0.001 used in pyKooCAE example).
NUM_STATES = 21
T_FINAL = 1.0e-3      # s
TIMES = np.linspace(0.0, T_FINAL, NUM_STATES)  # shape (21,)

# g in mm/s² (pyKooCAE convention)
G_MM_S2 = 9810.0


# ---------------------------------------------------------------------------
# Physics helpers
# ---------------------------------------------------------------------------

def impactor_velocity(spec: dict) -> float:
    """v0 = sqrt(2 g h) in mm/s."""
    return math.sqrt(2.0 * G_MM_S2 * spec["height"])


def sphere_mass_kg(spec: dict) -> float:
    """Mass in kg. radius in mm, density in kg/m³ → vol in mm³ → m³ * 1e-9."""
    vol_mm3 = (4.0 / 3.0) * math.pi * spec["radius"] ** 3
    return spec["density"] * vol_mm3 * 1e-9


def impactor_ke_joules(spec: dict) -> float:
    """KE in Joules. v in mm/s ⇒ (mm/s)² → divide by 1e6 to get (m/s)²."""
    v = impactor_velocity(spec)                  # mm/s
    m = sphere_mass_kg(spec)                     # kg
    v_si = v * 1e-3                              # m/s
    return 0.5 * m * v_si * v_si                 # Joules


# ---------------------------------------------------------------------------
# Face-aware geometry
# ---------------------------------------------------------------------------

def face_surface_z(face_code: str) -> float:
    """Z-coordinate of the impacted face. The impactor hits this surface.
    Used for distance-decay: parts near this z get higher response.
    """
    bb = DEVICE_BBOX
    if face_code == "F1":   # Back  (faces -Z up) → impacts z=zmax
        return bb["z_max"]
    if face_code == "F2":   # Front (faces +Z up) → impacts z=zmin
        return bb["z_min"]
    if face_code == "F3":   # Right → impacts x=xmax
        return bb["x_max"]
    if face_code == "F4":   # Left  → impacts x=xmin
        return bb["x_min"]
    if face_code == "F5":   # Top   → impacts y=ymax
        return bb["y_max"]
    if face_code == "F6":   # Bottom → impacts y=ymin
        return bb["y_min"]
    return 0.0


def face_grid_bbox(face_code: str) -> tuple[float, float, float, float]:
    """In-plane (u, v) bbox for the grid on this face.
    Returns (u_min, v_min, u_max, v_max) — the two coordinates we vary.
    """
    bb = DEVICE_BBOX
    margin = 0.9   # match pyKooCAE default
    if face_code in ("F1", "F2"):
        # XY plane
        u_lo, u_hi = bb["x_min"], bb["x_max"]
        v_lo, v_hi = bb["y_min"], bb["y_max"]
    elif face_code in ("F3", "F4"):
        # YZ plane (we vary x=y on report, y=z); use Y on horiz, Z on vert
        u_lo, u_hi = bb["y_min"], bb["y_max"]
        v_lo, v_hi = bb["z_min"], bb["z_max"]
    else:  # F5, F6
        # XZ plane
        u_lo, u_hi = bb["x_min"], bb["x_max"]
        v_lo, v_hi = bb["z_min"], bb["z_max"]

    # Apply margin: shrink by (1-margin)/2 on each side.
    inset_u = (u_hi - u_lo) * (1.0 - margin) * 0.5
    inset_v = (v_hi - v_lo) * (1.0 - margin) * 0.5
    return (u_lo + inset_u, v_lo + inset_v, u_hi - inset_u, v_hi - inset_v)


def impact_point_3d(face_code: str, u: float, v: float) -> tuple[float, float, float]:
    """Convert (face, u, v) → 3D impact point on the device surface."""
    if face_code == "F1":
        return (u, v, face_surface_z(face_code))
    if face_code == "F2":
        return (u, v, face_surface_z(face_code))
    if face_code == "F3":
        return (face_surface_z(face_code), u, v)   # x = surface_x; u=Y; v=Z
    if face_code == "F4":
        return (face_surface_z(face_code), u, v)
    if face_code == "F5":
        return (u, face_surface_z(face_code), v)   # y = surface_y; u=X; v=Z
    if face_code == "F6":
        return (u, face_surface_z(face_code), v)
    return (u, v, 0.0)


def part_center_3d(part: dict) -> tuple[float, float, float]:
    """3D centroid of a part."""
    x0, y0, x1, y1 = part["fp"]
    z0, z1 = part["z"]
    return ((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5)


def distance_3d(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))


# ---------------------------------------------------------------------------
# Per-part response generator (the "physics" mock)
# ---------------------------------------------------------------------------

def per_part_response(
    face_code: str,
    impact_xyz: tuple[float, float, float],
    part: dict,
    rng: np.random.Generator,
) -> dict:
    """Generate physically-plausible peak_g / peak_stress / peak_strain / peak_disp
    plus stress_ts dict for one (face, position, part).
    """
    part_xyz = part_center_3d(part)
    dist = distance_3d(impact_xyz, part_xyz)
    # decay characteristic length — about half the device diagonal
    L = 50.0
    decay = math.exp(-dist / L)              # 1.0 at zero distance → ~0.13 at 100mm
    # depth into device from impact surface: parts behind impact face get less
    surface_pos = face_surface_z(face_code)
    if face_code in ("F1", "F2"):
        depth = abs(part_xyz[2] - surface_pos)
    elif face_code in ("F3", "F4"):
        depth = abs(part_xyz[0] - surface_pos)
    else:  # F5, F6
        depth = abs(part_xyz[1] - surface_pos)
    depth_decay = math.exp(-depth / 12.0)    # 12mm characteristic depth

    spatial = decay * (0.4 + 0.6 * depth_decay)   # combine planar + depth

    # Scenario-specific vulnerabilities (smartphone analogy):
    #   F2 (Front, z_max=15) → PCB\Main(1), Motor(2), IC1(3), IC2(4) take the hit.
    #   F1 (Back,  z_min= 0) → Battery(8), Frame(9), Housing\Back(10) take the hit.
    # F5/F6/F3/F4 patterns remain for optional all-faces mode.
    scenario_boost = 1.0
    pid = part["id"]
    if face_code == "F2" and pid in (1, 2, 3, 4):
        # Front impact exposes front-side electronics; Motor near center peaks hardest.
        scenario_boost = 1.6
        if pid == 2:
            cx, cy = impact_xyz[0], impact_xyz[1]
            if math.sqrt(cx ** 2 + cy ** 2) < 15.0:
                scenario_boost = 2.0
    elif face_code == "F1" and pid in (8, 9, 10):
        # Back impact exposes battery + frame + back-cover; battery is the killer.
        scenario_boost = 1.8 if pid == 8 else 1.5
    elif face_code == "F5" and pid in (5, 6):
        # memory sensitive to F5 (top) right side (legacy all-faces pattern)
        if impact_xyz[0] > 10.0:
            scenario_boost = 1.7

    frag = PART_FRAGILITY[pid]

    # Lognormal multiplicative noise as specified.
    noise_g      = float(rng.lognormal(0.0, 0.20))
    noise_stress = float(rng.lognormal(0.0, 0.20))
    noise_strain = float(rng.lognormal(0.0, 0.20))
    noise_disp   = float(rng.lognormal(0.0, 0.20))

    # Cap response amplitudes per spec.
    G_MAX      = 1.5e6        # g
    STRESS_MAX = 800.0        # MPa
    STRAIN_MAX = 0.05         # unitless
    DISP_MAX   = 80.0         # mm

    peak_g      = G_MAX      * spatial * scenario_boost * frag["g"]      * noise_g
    peak_stress = STRESS_MAX * spatial * scenario_boost * frag["stress"] * noise_stress
    peak_strain = STRAIN_MAX * spatial * scenario_boost * frag["strain"] * noise_strain
    peak_disp   = DISP_MAX   * spatial * scenario_boost * frag["disp"]   * noise_disp

    # Clamp to physical ranges.
    peak_g      = min(peak_g,      G_MAX)
    peak_stress = min(peak_stress, STRESS_MAX)
    peak_strain = min(peak_strain, STRAIN_MAX)
    peak_disp   = min(peak_disp,   DISP_MAX)

    # stress_ts: rising ramp peaking around t=0.3-0.5 ms, then ringdown.
    t_peak = float(rng.uniform(0.30e-3, 0.50e-3))
    width = float(rng.uniform(0.10e-3, 0.18e-3))
    base = peak_stress * np.exp(-((TIMES - t_peak) / width) ** 2)
    # ringdown tail
    tail_mask = TIMES > t_peak
    ringdown = np.zeros_like(TIMES)
    if tail_mask.any():
        decay_rate = float(rng.uniform(2500.0, 4500.0))
        freq = float(rng.uniform(8000.0, 16000.0))
        phase = float(rng.uniform(0.0, math.pi))
        t_rel = TIMES[tail_mask] - t_peak
        ringdown[tail_mask] = (
            0.25 * peak_stress * np.exp(-decay_rate * t_rel)
            * np.cos(2.0 * math.pi * freq * t_rel + phase)
        )
    stress_curve = np.clip(base + ringdown, 0.0, None)
    # ensure exact peak match for downstream sanity
    if stress_curve.max() > 0:
        stress_curve = stress_curve * (peak_stress / stress_curve.max())

    # Per-state min/avg/max for richer schema (matches deep_report).
    rng_jitter = rng.uniform(0.85, 1.0, size=NUM_STATES)
    max_vals = stress_curve
    avg_vals = stress_curve * 0.20 * rng_jitter
    min_vals = np.zeros_like(stress_curve)
    elem_ids = (rng.integers(1000, 20000, size=NUM_STATES)).astype(int)

    return {
        "peak_g": float(peak_g),
        "peak_stress": float(peak_stress),
        "peak_strain": float(peak_strain),
        "peak_disp": float(peak_disp),
        "stress_ts": {
            "t": [float(x) for x in TIMES],
            "max": [float(x) for x in max_vals],
            "min": [float(x) for x in min_vals],
            "avg": [float(x) for x in avg_vals],
            "max_element_id": [int(x) for x in elem_ids],
        },
    }


# ---------------------------------------------------------------------------
# Energy-data generators (glstat / matsum / rcforc)
# ---------------------------------------------------------------------------

def generate_glstat(ke_initial_J: float, rng: np.random.Generator) -> list[dict]:
    """Mock glstat.csv: global energy time series.
    Conservation: KE(t) + IE(t) + dissipation(t) ≈ KE_initial.
    """
    t = TIMES
    # Sharp drop of KE during 0.1-0.4 ms, leveling out (impactor rebounds w/ ~10% KE).
    ke_final_frac = 0.10
    sigmoid = 1.0 / (1.0 + np.exp(-(t - 0.25e-3) / 6.0e-5))
    ke = ke_initial_J * ((1.0 - ke_final_frac) * (1.0 - sigmoid) + ke_final_frac)
    # internal energy: rises to absorb most of lost KE.
    # Budget at t=T: KE=10% + IE=78% + slide=10% + HG=2% = 100% (sums to 1.0).
    ie_fraction = 0.78
    ie = ke_initial_J * ie_fraction * sigmoid
    # sliding + hourglass: small leftover
    sliding = ke_initial_J * 0.10 * sigmoid * (1.0 + 0.05 * rng.normal(size=NUM_STATES))
    hourglass = ke_initial_J * 0.02 * sigmoid * (1.0 + 0.05 * rng.normal(size=NUM_STATES))
    sliding = np.clip(sliding, 0.0, None)
    hourglass = np.clip(hourglass, 0.0, None)
    total = ke + ie + sliding + hourglass
    rows = []
    for i, ti in enumerate(t):
        rows.append({
            "time": float(ti),
            "kinetic_energy": float(ke[i]),
            "internal_energy": float(ie[i]),
            "sliding_energy": float(sliding[i]),
            "hourglass_energy": float(hourglass[i]),
            "total_energy": float(total[i]),
        })
    return rows


def generate_matsum(
    ke_initial_J: float,
    parts: list[dict],
    direct_pid: int,
    rng: np.random.Generator,
) -> list[dict]:
    """Mock matsum.csv: per-part KE(t) and IE(t).
    The impactor (id 999) starts with all KE, decays to ~10%.
    The direct-contact part absorbs ~50% of incoming KE.
    Other parts share the remainder weighted by 1/dist.
    """
    t = TIMES
    sigmoid = 1.0 / (1.0 + np.exp(-(t - 0.25e-3) / 6.0e-5))
    delayed_sigmoid = 1.0 / (1.0 + np.exp(-(t - 0.35e-3) / 7.0e-5))

    rows: list[dict] = []
    # Impactor row: id 999
    ke_imp = ke_initial_J * ((1.0 - 0.10) * (1.0 - sigmoid) + 0.10)
    ie_imp = ke_initial_J * 0.02 * sigmoid  # rigid impactor barely deforms
    for i, ti in enumerate(t):
        rows.append({
            "time": float(ti), "part_id": 999,
            "internal_energy": float(ie_imp[i]),
            "kinetic_energy": float(ke_imp[i]),
        })

    # Total IE budget that needs to be distributed across parts.
    # Matches glstat's ie_fraction (0.78) so matsum sum(IE) ≈ glstat IE_total.
    total_ie_budget = ke_initial_J * 0.78 * sigmoid

    # Direct part weight = 0.5, others share remaining 0.5 by inverse-distance.
    direct_share = 0.50
    # Compute share weights for non-direct parts
    non_direct = [p for p in parts if p["id"] != direct_pid]
    direct_part = next(p for p in parts if p["id"] == direct_pid)
    direct_xyz = part_center_3d(direct_part)
    inv_dists = []
    for p in non_direct:
        d = distance_3d(direct_xyz, part_center_3d(p))
        inv_dists.append(1.0 / max(d, 5.0))
    inv_sum = sum(inv_dists)
    other_weights = [w / inv_sum for w in inv_dists]

    for p in parts:
        if p["id"] == direct_pid:
            share = direct_share
        else:
            idx = non_direct.index(p)
            share = (1.0 - direct_share) * other_weights[idx]
        # small per-part noise
        noise = float(rng.uniform(0.92, 1.08))
        # direct gets sharp engagement (sigmoid), distant gets delayed
        is_direct = (p["id"] == direct_pid)
        sig = sigmoid if is_direct else delayed_sigmoid
        ie_part = total_ie_budget * share * noise * (sig / sigmoid.max())
        # parts may have small kinetic energy too (rebound vibration)
        ke_part = ie_part * 0.05 * rng.uniform(0.5, 1.5)
        for i, ti in enumerate(t):
            rows.append({
                "time": float(ti), "part_id": int(p["id"]),
                "internal_energy": float(ie_part[i]),
                "kinetic_energy": float(ke_part[i]),
            })
    return rows


def generate_rcforc(
    impact_xyz: tuple[float, float, float],
    parts: list[dict],
    direct_pid: int,
    rng: np.random.Generator,
) -> list[dict]:
    """Mock rcforc.csv: contact force per contact_id, decomposed by part pairs.

    Generates 8-15 contact_ids. Force magnitude peaks during impact and decays.
    First-engage time propagates outward from impactor → direct → others.
    """
    t = TIMES
    # Build pair list: (impactor↔direct), then pairs between direct & nearby parts.
    direct_part = next(p for p in parts if p["id"] == direct_pid)
    direct_xyz = part_center_3d(direct_part)

    pairs: list[tuple[int, int]] = [(999, direct_pid)]
    # Choose 7-14 nearest other parts to direct, pair them with direct.
    non_direct = [p for p in parts if p["id"] != direct_pid]
    non_direct_sorted = sorted(
        non_direct,
        key=lambda p: distance_3d(direct_xyz, part_center_3d(p)),
    )
    n_extra = int(rng.integers(7, 15))
    for p in non_direct_sorted[:n_extra]:
        pairs.append((direct_pid, p["id"]))

    rows: list[dict] = []
    for contact_id, (a, b) in enumerate(pairs, start=1):
        # First-engage time: impactor→direct at 0.05ms, others 0.10-0.30ms.
        if a == 999:
            t_engage = 0.05e-3
            peak_force = float(rng.uniform(800.0, 1500.0))   # N — strong impact
        else:
            # distance from direct part center
            other = next(p for p in parts if p["id"] == b)
            d = distance_3d(direct_xyz, part_center_3d(other))
            t_engage = 0.05e-3 + 0.20e-3 * (d / 80.0)
            peak_force = float(rng.uniform(50.0, 600.0)) * math.exp(-d / 40.0)
        width = float(rng.uniform(0.08e-3, 0.15e-3))
        base = peak_force * np.exp(-((t - t_engage) / width) ** 2)
        # post-peak ringdown
        tail = np.zeros_like(t)
        m = t > t_engage
        if m.any():
            tail[m] = 0.20 * peak_force * np.exp(-3000.0 * (t[m] - t_engage)) * np.cos(2 * math.pi * 12000.0 * (t[m] - t_engage))
        f_mag = np.clip(base + tail, 0.0, None)

        # Direction: predominantly along -Z for impactor↔direct, otherwise random.
        if a == 999:
            dir_vec = np.array([0.0, 0.0, -1.0])
        else:
            other = next(p for p in parts if p["id"] == b)
            d_vec = np.array(part_center_3d(other)) - np.array(direct_xyz)
            n = np.linalg.norm(d_vec)
            dir_vec = d_vec / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])

        for i, ti in enumerate(t):
            rows.append({
                "time": float(ti),
                "contact_id": int(contact_id),
                "slave_pid": int(a),
                "master_pid": int(b),
                "force_x": float(f_mag[i] * dir_vec[0]),
                "force_y": float(f_mag[i] * dir_vec[1]),
                "force_z": float(f_mag[i] * dir_vec[2]),
            })
    return rows


# ---------------------------------------------------------------------------
# Synthetic impactor 3D trajectory
# ---------------------------------------------------------------------------

# Stiff parts → bounce; soft parts → embed.
_STIFF_PIDS = {9, 10, 11, 12}        # Frame, Housing, Front\Wall, Housing\Frame
_SOFT_PIDS = {1, 8}                  # PCB, Battery
# Other parts: rebound (default)

# Impactor mass — pre-compute once for KE column.
_IMPACTOR_MASS_KG = sphere_mass_kg(IMPACTOR_SPEC)


def _impactor_axis_for_face(face_code: str) -> tuple[int, int]:
    """Return ``(axis_index, sign)`` of the impact-normal direction.

    The impactor moves along ``axis_index`` (0=x, 1=y, 2=z) with ``sign``
    matching ``+1`` if hitting the *max* side of the device or ``-1`` if hitting
    the *min* side. The impactor *velocity* at impact is ``-sign * v0`` (it
    travels INTO the device).
    """
    if face_code == "F1":  # Back — impacts z=max from above → vel.z = -v0
        return 2, +1
    if face_code == "F2":  # Front — impacts z=min from below → vel.z = +v0
        return 2, -1
    if face_code == "F3":
        return 0, +1
    if face_code == "F4":
        return 0, -1
    if face_code == "F5":
        return 1, +1
    if face_code == "F6":
        return 1, -1
    return 2, +1


def _write_trajectory_csv(
    run_dir: Path,
    face_code: str,
    impact_xyz: tuple[float, float, float],
    direct_pid: int,
    seed: int,
) -> None:
    """Generate ``impactor_trajectory.csv`` with the per-state impactor state.

    Three-phase synthetic model (deterministic per ``seed`` = face+x+y hash):

    Phase 1 — Pre-contact free fall (t ∈ [0, t_engage]):
        Position starts ``height`` (5-8 mm) above the device surface along the
        impact-normal axis. Velocity is purely along that axis, magnitude
        ``v0 = sqrt(2 g h_drop)`` ≈ 1400 mm/s. Free-fall under g=9810 mm/s²;
        ``contact = False``.

    Phase 2 — Contact (t ∈ [t_engage, t_engage + dt_contact]):
        Velocity along normal axis decelerates linearly; position reaches a
        minimum (max-penetration). Off-center impacts on a part produce a
        lateral kick ~10% of |v_normal| in (x, y) directions if the impact
        misses the centroid of ``direct_pid``. ``contact = True``.

    Phase 3 — Post-contact (t > t_engage + dt_contact):
        Behavior class is derived from the direct part's stiffness:
          * Stiff parts (Frame/Housing) → bounce (KE retention ≈ 0.5-0.7)
          * Soft parts  (PCB/Battery)   → embed (KE retention < 0.15)
          * Edge-of-part impacts        → slide (lateral velocity dominates)
          * Otherwise                   → rebound (moderate)
        Final velocity is set accordingly; position propagates consistently.

    KE column: ``0.5 * m * |v|² / 1e6`` (J — converting (mm/s)² → (m/s)²).
    """
    rng = np.random.default_rng(seed)
    axis, sign = _impactor_axis_for_face(face_code)
    surface_coord = face_surface_z(face_code)

    v0 = impactor_velocity(IMPACTOR_SPEC)   # mm/s, scalar magnitude
    height_above = float(rng.uniform(5.0, 8.0))  # mm above surface at t=0

    # --- Initial state (pre-contact) ---
    pos0 = list(impact_xyz)
    pos0[axis] = surface_coord + sign * height_above
    vel0 = [0.0, 0.0, 0.0]
    vel0[axis] = -sign * v0                # travelling INTO the device

    # t_engage in seconds: height / v0
    t_engage = (height_above * 1e-3) / (v0 * 1e-3)  # s
    # Force t_engage into the simulation window
    t_engage = float(np.clip(t_engage, 0.5e-5, 1.5e-5))

    # Contact duration depends on stiffness of direct part.
    if direct_pid in _STIFF_PIDS:
        dt_contact = float(rng.uniform(0.15e-3, 0.22e-3))
    elif direct_pid in _SOFT_PIDS:
        dt_contact = float(rng.uniform(0.30e-3, 0.40e-3))
    else:
        dt_contact = float(rng.uniform(0.20e-3, 0.30e-3))

    # --- KE retention & behavior class ---
    # Pick a noisy retention by part class, then optionally promote to "slide".
    if direct_pid in _STIFF_PIDS:
        ke_retention = float(np.clip(rng.normal(0.55, 0.10), 0.42, 0.75))
    elif direct_pid in _SOFT_PIDS:
        ke_retention = float(np.clip(rng.normal(0.08, 0.04), 0.02, 0.14))
    else:
        ke_retention = float(np.clip(rng.normal(0.27, 0.07), 0.17, 0.38))

    # Detect "slide" condition: impact point near edge of direct part footprint.
    direct_part = next(p for p in PARTS if p["id"] == direct_pid)
    x0, y0, x1, y1 = direct_part["fp"]
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    half_w, half_h = 0.5 * (x1 - x0), 0.5 * (y1 - y0)
    dx = abs(impact_xyz[0] - cx) / max(half_w, 1e-3)
    dy = abs(impact_xyz[1] - cy) / max(half_h, 1e-3)
    edge_factor = max(dx, dy)              # 0 = centered, ~1 = at edge
    slide_mode = (edge_factor > 0.85) and (direct_pid not in _SOFT_PIDS)

    # Final velocity components.
    # v_normal_final magnitude = sqrt(retention) * v0 (sign flipped to leave)
    v_normal_final = math.sqrt(ke_retention) * v0
    # Lateral kick from off-center impact (~10% of |v_normal| baseline).
    # Direction is from impact point toward part centroid offset.
    lateral_dir = np.array([impact_xyz[0] - cx, impact_xyz[1] - cy], dtype=float)
    n = float(np.linalg.norm(lateral_dir))
    if n > 1e-6:
        lateral_dir /= n
    else:
        lateral_dir = np.array([1.0, 0.0])

    if slide_mode:
        # slide: lateral dominates, vz tiny
        v_lat = float(rng.uniform(0.45, 0.70)) * v0
        v_n_post = 0.10 * v0
    else:
        v_lat = float(rng.uniform(0.05, 0.15)) * v0 * edge_factor
        v_n_post = v_normal_final

    vel_final = [v_lat * lateral_dir[0], v_lat * lateral_dir[1], 0.0]
    if axis == 2:
        # bounce: normal axis sign reverses (+sign * v_n_post means leaving)
        vel_final[2] = +sign * v_n_post
    elif axis == 0:
        vel_final[0] = +sign * v_n_post
    elif axis == 1:
        vel_final[1] = +sign * v_n_post

    # If embed: position drifts very little post-contact, vz ≈ 0.
    embed_mode = (ke_retention < 0.15) and (not slide_mode)
    if embed_mode:
        vel_final = [0.05 * v0 * rng.normal(),
                     0.05 * v0 * rng.normal(),
                     0.0]
        vel_final[axis] = sign * float(rng.uniform(20.0, 50.0))  # tiny escape vel

    # Maximum penetration (negative-z relative to surface, magnitude).
    # Stiff: shallow; soft: deep.
    if direct_pid in _STIFF_PIDS:
        max_pen = float(rng.uniform(0.3, 1.2))
    elif direct_pid in _SOFT_PIDS:
        max_pen = float(rng.uniform(2.5, 5.0))
    else:
        max_pen = float(rng.uniform(1.0, 2.5))

    # --- Build per-timestep trajectory ---
    rows: list[dict] = []
    g = G_MM_S2
    surf = surface_coord

    for ti in TIMES:
        t = float(ti)
        if t <= t_engage:
            # Phase 1: free fall along impact-normal axis
            frac = t / t_engage if t_engage > 0 else 1.0
            pos = list(pos0)
            # apply gravity-augmented motion along impact-normal (sign-aware)
            displacement = (vel0[axis] * t) + (0.5 * (-sign * g) * t * t)
            pos[axis] = pos0[axis] + displacement
            vel = list(vel0)
            vel[axis] = vel0[axis] + (-sign * g) * t
            contact = False
        elif t <= t_engage + dt_contact:
            # Phase 2: contact — interpolate velocity from initial → max-pen → final
            tau = (t - t_engage) / dt_contact     # 0..1
            # Penetration profile: parabolic peak at tau=0.5
            pen_frac = 4.0 * tau * (1.0 - tau)     # 0..1..0
            pos = list(impact_xyz)
            pos[axis] = surf - sign * max_pen * pen_frac
            # Lateral position drift (small)
            if axis == 2:
                pos[0] = impact_xyz[0] + lateral_dir[0] * v_lat * (t - t_engage) * 0.5
                pos[1] = impact_xyz[1] + lateral_dir[1] * v_lat * (t - t_engage) * 0.5
            # Linear blend of normal velocity from -v0 → +v_n_post
            v_norm_now = vel0[axis] * (1.0 - tau) + (vel_final[axis]) * tau
            vel = [0.0, 0.0, 0.0]
            vel[axis] = v_norm_now
            # Lateral velocity ramps in during contact
            if axis == 2:
                vel[0] = vel_final[0] * tau
                vel[1] = vel_final[1] * tau
            contact = True
        else:
            # Phase 3: post-contact ballistic
            tau = t - (t_engage + dt_contact)
            pos = [0.0, 0.0, 0.0]
            pos_start_normal = surf  # leaves surface
            # propagate from end-of-contact at surface using final velocity
            pos[0] = impact_xyz[0] + vel_final[0] * tau
            pos[1] = impact_xyz[1] + vel_final[1] * tau
            pos[2] = impact_xyz[2]
            pos[axis] = pos_start_normal + vel_final[axis] * tau
            vel = list(vel_final)
            # Briefly re-engage contact at the peaks of any oscillation:
            # if embed_mode, mark intermittent contact True; else False.
            contact = bool(embed_mode and rng.random() < 0.3)

        vmag_mm_s = math.sqrt(vel[0] ** 2 + vel[1] ** 2 + vel[2] ** 2)
        v_si = vmag_mm_s * 1e-3
        ke_j = 0.5 * _IMPACTOR_MASS_KG * v_si * v_si

        rows.append({
            "time": f"{t:.7e}",
            "x":  f"{pos[0]:.4f}",
            "y":  f"{pos[1]:.4f}",
            "z":  f"{pos[2]:.4f}",
            "vx": f"{vel[0]:.4f}",
            "vy": f"{vel[1]:.4f}",
            "vz": f"{vel[2]:.4f}",
            "ke": f"{ke_j:.6e}",
            "contact": "1" if contact else "0",
        })

    write_csv(
        run_dir / "impactor_trajectory.csv",
        rows,
        ["time", "x", "y", "z", "vx", "vy", "vz", "ke", "contact"],
    )


# ---------------------------------------------------------------------------
# Closest "direct contact" part from impact point
# ---------------------------------------------------------------------------

def direct_contact_part(impact_xyz: tuple[float, float, float]) -> dict:
    """Return the part whose centroid is closest to the impact point in 3D."""
    return min(PARTS, key=lambda p: distance_3d(impact_xyz, part_center_3d(p)))


# ---------------------------------------------------------------------------
# CSV writer helper
# ---------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

def build_face_positions(face: dict) -> list[dict]:
    """Generate the (name, u, v) positions for a single face."""
    u_lo, v_lo, u_hi, v_hi = face_grid_bbox(face["code"])
    nx, ny = face["nx"], face["ny"]
    out = []
    for iy in range(ny):
        for ix in range(nx):
            u = u_lo if nx == 1 else u_lo + ix * (u_hi - u_lo) / (nx - 1)
            v = v_lo if ny == 1 else v_lo + iy * (v_hi - v_lo) / (ny - 1)
            name = f"P_{iy+1:03d}_{ix+1:03d}"
            out.append({"name": name, "u": round(u, 4), "v": round(v, 4),
                        "ix": ix, "iy": iy})
    return out


def write_scenario(output: Path, selected_faces: list[dict]) -> None:
    """Write multi-face scenario.json (plan §15.5 format)."""
    faces_payload = [
        {
            "code": f["code"], "name": f["name"],
            "orientation": {"roll": f["roll"], "pitch": f["pitch"], "yaw": f["yaw"]},
            "locations": {"mode": "grid", "x_count": f["nx"], "y_count": f["ny"], "margin": 0.9},
        }
        for f in selected_faces
    ]
    total_positions = sum(f["nx"] * f["ny"] for f in selected_faces)
    scenario = {
        "_comment": "Synthetic multi-face partial impact dataset (generated by tests/generate_sample.py)",
        "project_name": "MultiFaceImpactTest_Sample",
        "mode": "drop_weight_impact_multiface",
        "model_file": "device.k",
        "output_dir": "mf_output",
        "total_positions": total_positions,
        "simulation_params": {
            "tFinal": T_FINAL,
            "dt": 1.0e-6,
            "impactor": IMPACTOR_SPEC,
            "faces": faces_payload,
            "generation_mode": "DampingSpring",
            "boundary_distance": 0.0,
            "offset_distance": 0.05,
            "wall": {"youngs_modulus": 2.0e11, "poisson_ratio": 0.3, "density": 7850},
        },
        "environment": {
            "ncpu": 4,
            "memory": "4G",
            "partition": "normal",
        },
    }
    (output / "scenario.json").write_text(json.dumps(scenario, indent=2))

    # Cylinder alternative (single-face for testing cylinder visualization).
    scenario_cyl = {
        "_comment": "Synthetic cylinder-impactor variant (single-face)",
        "project_name": "MultiFaceImpactTest_Sample_Cylinder",
        "mode": "drop_weight_impact",
        "model_file": "device.k",
        "output_dir": "mf_output_cyl",
        "simulation_params": {
            "tFinal": T_FINAL,
            "dt": 1.0e-6,
            "impactor": IMPACTOR_CYLINDER,
            "locations": {"mode": "grid", "x_count": 3, "y_count": 3, "margin": 0.8},
            "generation_mode": "OutsideRigidPart",
            "boundary_distance": 30.0,
            "offset_distance": 0.05,
        },
    }
    (output / "scenario_cylinder.json").write_text(json.dumps(scenario_cyl, indent=2))


def write_impactor_spec(output: Path) -> None:
    """Write the §2.3-style impactor_spec.json."""
    v = impactor_velocity(IMPACTOR_SPEC)
    m = sphere_mass_kg(IMPACTOR_SPEC)
    spec = {
        "type": "ball",
        "ball": {
            "diameter": IMPACTOR_SPEC["radius"] * 2.0,
            "radius": IMPACTOR_SPEC["radius"],
            "mass_kg": m,
            "material": "steel",
            "density": IMPACTOR_SPEC["density"],
            "youngs_modulus": IMPACTOR_SPEC["youngs_modulus"],
            "poisson_ratio": IMPACTOR_SPEC["poisson_ratio"],
        },
        "initial_velocity_mm_s": v,
        "drop_height_mm": IMPACTOR_SPEC["height"],
        "kinetic_energy_J": impactor_ke_joules(IMPACTOR_SPEC),
        "contact_type": "automatic_surface_to_surface",
    }
    (output / "impactor_spec.json").write_text(json.dumps(spec, indent=2))


def write_device_layout(output: Path) -> None:
    """Write §2.4-style device_layout.json."""
    bb = DEVICE_BBOX
    layout = {
        "bounding_box": {"x_min": bb["x_min"], "x_max": bb["x_max"],
                          "y_min": bb["y_min"], "y_max": bb["y_max"]},
        "z_range": {"z_min": bb["z_min"], "z_max": bb["z_max"]},
        "outline_xy": [
            [bb["x_min"], bb["y_min"]], [bb["x_max"], bb["y_min"]],
            [bb["x_max"], bb["y_max"]], [bb["x_min"], bb["y_max"]],
        ],
        "parts": [
            {
                "id": p["id"], "name": p["name"],
                "footprint": [
                    [p["fp"][0], p["fp"][1]], [p["fp"][2], p["fp"][1]],
                    [p["fp"][2], p["fp"][3]], [p["fp"][0], p["fp"][3]],
                ],
                "z_range": [p["z"][0], p["z"][1]],
            } for p in PARTS
        ],
    }
    (output / "device_layout.json").write_text(json.dumps(layout, indent=2))


def write_face_config(face_dir: Path, face: dict, positions: list[dict]) -> None:
    """Write face_config.json inside the face's directory."""
    u_lo, v_lo, u_hi, v_hi = face_grid_bbox(face["code"])
    payload = {
        "code": face["code"], "name": face["name"],
        "orientation": {"roll": face["roll"], "pitch": face["pitch"], "yaw": face["yaw"]},
        "grid": {"x_count": face["nx"], "y_count": face["ny"]},
        "in_plane_bbox": {"u_min": u_lo, "v_min": v_lo, "u_max": u_hi, "v_max": v_hi},
        "surface_coordinate": face_surface_z(face["code"]),
        "num_positions": len(positions),
    }
    (face_dir / "face_config.json").write_text(json.dumps(payload, indent=2))


def write_analysis_result(
    run_dir: Path, run_id: str, face_code: str, pos: dict, parts_resp: dict
) -> None:
    """Write per-run analysis_result.json (§2.5 schema, matches deep_report)."""
    payload = {
        "run_id": run_id,
        "face": face_code,
        "position": {
            "name": pos["name"], "u": pos["u"], "v": pos["v"],
            "x": pos["impact_xyz"][0], "y": pos["impact_xyz"][1],
            "z": pos["impact_xyz"][2],
        },
        "num_states": NUM_STATES,
        "t_start": float(TIMES[0]),
        "t_end": float(TIMES[-1]),
        "parts": {
            str(pid): parts_resp[pid] for pid in sorted(parts_resp.keys())
        },
    }
    (run_dir / "analysis_result.json").write_text(json.dumps(payload, indent=2))


def _parse_faces_arg(raw: str) -> list[dict]:
    """Resolve a ``--faces`` CLI value to the corresponding FACES entries.

    Accepts ``all`` (= F1..F6) or a comma-separated list of face codes
    (e.g. ``F1,F2,F5``). Order in the input is preserved; unknown codes raise.
    """
    raw = raw.strip()
    if raw.lower() == "all":
        return list(FACES)
    by_code = {f["code"]: f for f in FACES}
    selected: list[dict] = []
    for tok in raw.split(","):
        code = tok.strip()
        if not code:
            continue
        if code not in by_code:
            raise SystemExit(f"--faces: unknown face code {code!r}; "
                             f"valid: {sorted(by_code)} or 'all'")
        selected.append(by_code[code])
    if not selected:
        raise SystemExit("--faces: at least one face code required")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "-o", required=True, type=Path,
                        help="Output directory for the synthetic dataset")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    parser.add_argument("--faces", type=str, default=",".join(DEFAULT_FACES),
                        help=("Comma-separated face codes to generate "
                              "(e.g. 'F1,F2,F5') or 'all' for F1-F6. "
                              "Default: F1,F2 (smartphone Back+Front)."))
    args = parser.parse_args()

    selected_faces = _parse_faces_arg(args.faces)

    output: Path = args.output
    output.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)
    random.seed(args.seed)

    # Top-level files
    write_scenario(output, selected_faces)
    write_impactor_spec(output)
    write_device_layout(output)

    ke_initial = impactor_ke_joules(IMPACTOR_SPEC)

    manifest: list[dict] = []

    for face in selected_faces:
        face_dir_name = f"{face['code']}_{face['name'].lower()}"
        face_dir = output / face_dir_name
        face_dir.mkdir(exist_ok=True)
        positions = build_face_positions(face)
        # Pre-compute 3D impact point for each position.
        for pos in positions:
            pos["impact_xyz"] = impact_point_3d(face["code"], pos["u"], pos["v"])
        write_face_config(face_dir, face, positions)

        for i, pos in enumerate(positions, start=1):
            run_id = f"{face['code']}_{i:03d}"
            run_dir_name = f"Run_{run_id}"
            run_dir = face_dir / run_dir_name
            run_dir.mkdir(exist_ok=True)

            # Per-part response
            parts_resp = {
                p["id"]: per_part_response(face["code"], pos["impact_xyz"], p, rng)
                for p in PARTS
            }
            write_analysis_result(run_dir, run_id, face["code"], pos, parts_resp)

            # Energy CSVs
            direct = direct_contact_part(pos["impact_xyz"])
            glstat_rows = generate_glstat(ke_initial, rng)
            matsum_rows = generate_matsum(ke_initial, PARTS, direct["id"], rng)
            rcforc_rows = generate_rcforc(pos["impact_xyz"], PARTS, direct["id"], rng)

            write_csv(run_dir / "glstat.csv", glstat_rows,
                      ["time", "kinetic_energy", "internal_energy",
                       "sliding_energy", "hourglass_energy", "total_energy"])
            write_csv(run_dir / "matsum.csv", matsum_rows,
                      ["time", "part_id", "internal_energy", "kinetic_energy"])
            write_csv(run_dir / "rcforc.csv", rcforc_rows,
                      ["time", "contact_id", "slave_pid", "master_pid",
                       "force_x", "force_y", "force_z"])

            # Per-run impactor 3D trajectory.
            # Deterministic seed from face+u+v keeps trajectories reproducible.
            traj_seed = abs(hash((face["code"], round(pos["u"], 3),
                                    round(pos["v"], 3), args.seed))) % (2 ** 31)
            _write_trajectory_csv(
                run_dir,
                face["code"],
                pos["impact_xyz"],
                int(direct["id"]),
                traj_seed,
            )

            manifest.append({
                "face": face["code"],
                "face_name": face["name"],
                "position": pos["name"],
                "position_index": i,
                "u": pos["u"], "v": pos["v"],
                "impact_xyz": list(pos["impact_xyz"]),
                "direct_contact_part_id": int(direct["id"]),
                "direct_contact_part_name": direct["name"],
                "run_dir": str(Path(face_dir_name) / run_dir_name),
                "analysis_json": str(Path(face_dir_name) / run_dir_name / "analysis_result.json"),
                "glstat_csv": str(Path(face_dir_name) / run_dir_name / "glstat.csv"),
                "matsum_csv": str(Path(face_dir_name) / run_dir_name / "matsum.csv"),
                "rcforc_csv": str(Path(face_dir_name) / run_dir_name / "rcforc.csv"),
                "impactor_trajectory_csv": str(
                    Path(face_dir_name) / run_dir_name / "impactor_trajectory.csv"
                ),
            })

    (output / "manifest.json").write_text(json.dumps({
        "project_name": "MultiFaceImpactTest_Sample",
        "total_runs": len(manifest),
        "num_states_per_run": NUM_STATES,
        "impactor_ke_initial_J": ke_initial,
        "runs": manifest,
    }, indent=2))

    # Summary print.
    face_codes = ",".join(f["code"] for f in selected_faces)
    print(f"Generated {len(manifest)} runs across {len(selected_faces)} faces "
          f"({face_codes}) in {output}")
    print(f"Impactor KE_initial = {ke_initial:.4g} J")
    print(f"Files per run: analysis_result.json, glstat.csv, matsum.csv, "
          f"rcforc.csv, impactor_trajectory.csv")


if __name__ == "__main__":
    main()
