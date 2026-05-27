"""Data models for multi-face partial impact (drop-weight) DOE analysis.

Implements §17 (data model v2) and §22.4 (energy flow data model) of
docs/PartialImpactReport_Plan.md.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

class Severity(Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Finding:
    """Single diagnostic finding shown in the report."""
    severity: Severity
    title: str
    detail: str
    recommendation: str


# ---------------------------------------------------------------------------
# DOE geometry — face / position / impactor
# ---------------------------------------------------------------------------

@dataclass
class FaceOrientation:
    """One of the cuboid-26 standard faces (F1~F6)."""
    code: str            # "F1" ~ "F6"
    name: str            # "Back" / "Front" / "Right" / "Left" / "Top" / "Bottom"
    roll: float          # degrees
    pitch: float
    yaw: float


@dataclass
class ImpactPosition:
    """One (face, x, y) DOE position. Maps to a single LS-DYNA run."""
    pos_id: str          # e.g. "F1_P_001_001"
    face: str            # face code, e.g. "F1"
    x: float             # mm
    y: float             # mm
    run_dir: Path = field(default_factory=Path)


@dataclass
class ImpactorSpec:
    """Impactor geometry + material + drop kinematics (pyKooCAE schema).

    Sphere fields: ``radius``.
    Cylinder fields (asymmetric tumbler): ``front_radius``, ``outer_radius``,
    ``front_height``, ``back_height``, ``back_radius``.
    """
    type: str = "Sphere"                  # "Sphere" | "Cylinder"
    radius: float = 0.0                   # mm — Sphere radius
    height: float = 100.0                 # mm — free-fall drop height
    density: float = 7850.0               # kg/m³
    youngs_modulus: float = 2.0e11        # Pa
    poisson_ratio: float = 0.3
    # cylinder-only
    front_radius: float | None = None
    outer_radius: float | None = None
    front_height: float | None = None
    back_height: float | None = None
    back_radius: float | None = None

    # g in mm/s² (pyKooCAE convention)
    G_MM_S2: float = 9810.0

    @property
    def volume(self) -> float:
        """Volume in mm³."""
        if self.type == "Sphere":
            return (4.0 / 3.0) * math.pi * (self.radius ** 3)
        if self.type == "Cylinder":
            fr = self.front_radius or 0.0
            fh = self.front_height or 0.0
            outer = self.outer_radius or 0.0
            br = self.back_radius or outer
            bh = self.back_height or 0.0
            # rough volume: front cylinder + back cylinder
            return math.pi * (fr * fr * fh + br * br * bh)
        return 0.0

    @property
    def mass(self) -> float:
        """Mass in kg. ``volume`` is mm³ → convert to m³ via 1e-9."""
        return self.density * (self.volume * 1e-9)

    @property
    def velocity(self) -> float:
        """Impact velocity (mm/s) from free-fall height: v = sqrt(2 g h)."""
        if self.height <= 0:
            return 0.0
        return math.sqrt(2.0 * self.G_MM_S2 * self.height)

    @property
    def kinetic_energy(self) -> float:
        """KE = ½ m v² — units: kg · (mm/s)² = µJ. Caller may rescale."""
        return 0.5 * self.mass * (self.velocity ** 2)


# ---------------------------------------------------------------------------
# Parts and per-run results
# ---------------------------------------------------------------------------

@dataclass
class PartInfo:
    """Part metadata. ``footprint`` is the part's XY polygon for overlay viz."""
    part_id: int
    part_name: str
    group: str = ""
    footprint: list[tuple[float, float]] | None = None  # XY polygon (mm)
    z_range: tuple[float, float] | None = None          # (zmin, zmax) mm

    @staticmethod
    def extract_group(name: str) -> str:
        if "\\" in name:
            return name.split("\\")[0]
        if "/" in name:
            return name.split("/")[0]
        return "Other"


@dataclass
class TimeSeriesData:
    """Time series for a scalar quantity with min/max/avg per timestep.

    ``true_peak`` / ``true_peak_time`` retain the pre-downsample peak so
    downstream code never loses accuracy after lossy resampling.
    """
    times: list[float] = field(default_factory=list)
    max_values: list[float] = field(default_factory=list)
    min_values: list[float] = field(default_factory=list)
    avg_values: list[float] = field(default_factory=list)
    max_element_ids: list[int] = field(default_factory=list)
    true_peak: float | None = None
    true_peak_time: float | None = None

    @property
    def peak(self) -> float:
        if self.true_peak is not None:
            return self.true_peak
        return max(self.max_values) if self.max_values else 0.0

    @property
    def peak_time(self) -> float:
        if self.true_peak_time is not None:
            return self.true_peak_time
        if not self.max_values:
            return 0.0
        idx = self.max_values.index(max(self.max_values))
        return self.times[idx] if idx < len(self.times) else 0.0


@dataclass
class PartResult:
    """Per-part scalar peaks + stress time series for a single run."""
    part_id: int
    peak_g: float = 0.0
    peak_stress: float = 0.0
    peak_strain: float = 0.0
    peak_disp: float = 0.0
    stress_ts: TimeSeriesData = field(default_factory=TimeSeriesData)


@dataclass
class ImpactorTrajectory:
    """3D position+velocity time history of the impactor (one per simulation run).

    Loader-derived scalar summaries are populated at construction time
    (see ``loader.load_impactor_trajectory``).
    """
    times: list[float] = field(default_factory=list)         # seconds (T points, e.g. 21)
    pos_x: list[float] = field(default_factory=list)          # mm
    pos_y: list[float] = field(default_factory=list)          # mm
    pos_z: list[float] = field(default_factory=list)          # mm
    vel_x: list[float] = field(default_factory=list)          # mm/s
    vel_y: list[float] = field(default_factory=list)          # mm/s
    vel_z: list[float] = field(default_factory=list)          # mm/s
    ke: list[float] = field(default_factory=list)             # J at each step
    contact_engaged: list[bool] = field(default_factory=list)  # True when impactor in active contact

    # Derived scalar summaries
    initial_ke: float = 0.0
    final_ke: float = 0.0
    ke_retention: float = 0.0           # final_ke / initial_ke (∈ [0, 1])
    max_penetration_depth: float = 0.0  # max negative z relative to impact surface (mm)
    t_first_contact: float | None = None
    rebound_velocity_xy: tuple[float, float] = (0.0, 0.0)
    rebound_speed: float = 0.0          # |v_final| (mm/s)
    incident_speed: float = 0.0         # |v_initial| (mm/s)
    behavior_class: str = "unknown"     # "bounce" | "embed" | "slide" | "rebound"


@dataclass
class TrajectoryClusters:
    """Result of impactor-trajectory clustering across all runs."""
    n_clusters: int = 0
    labels: list[int] = field(default_factory=list)         # cluster id per result (results order)
    centroids: list[list[float]] = field(default_factory=list)
    archetypes: list[str] = field(default_factory=list)     # human label per cluster
    features_used: list[str] = field(default_factory=list)


@dataclass
class PairResult:
    """A single (face × position × part) result row — the core 3D-DOE cell."""
    face: str
    position: ImpactPosition
    part_id: int
    peak_g: float = 0.0
    peak_stress: float = 0.0
    peak_strain: float = 0.0
    peak_disp: float = 0.0
    stress_ts: TimeSeriesData = field(default_factory=TimeSeriesData)
    impactor_trajectory: ImpactorTrajectory | None = None


# ---------------------------------------------------------------------------
# Energy-flow graph (§22.4)
# ---------------------------------------------------------------------------

@dataclass
class EnergyNode:
    """Graph node — impactor or a single part."""
    node_id: str                  # "impactor" or part_id stringified
    name: str
    is_impactor: bool = False
    kinetic_ts: list[float] = field(default_factory=list)
    internal_ts: list[float] = field(default_factory=list)
    times: list[float] = field(default_factory=list)


@dataclass
class EnergyEdge:
    """Graph edge — a contact interface between two nodes."""
    src: str
    dst: str
    contact_id: int = -1
    times: list[float] = field(default_factory=list)
    force_mag_ts: list[float] = field(default_factory=list)
    impulse_cum_ts: list[float] = field(default_factory=list)
    work_cum_ts: list[float] = field(default_factory=list)
    peak_force: float = 0.0
    total_impulse: float = 0.0
    total_work: float = 0.0


@dataclass
class EnergyGraphFrame:
    """Single-timestep snapshot of the energy graph."""
    t: float
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: dict[tuple[str, str], dict] = field(default_factory=dict)


@dataclass
class EnergyFlow:
    """Complete energy-flow data for one (face, position) case."""
    impactor_ke_initial: float = 0.0
    impactor_ke_final: float = 0.0
    energy_dissipated: float = 0.0
    nodes: list[EnergyNode] = field(default_factory=list)
    edges: list[EnergyEdge] = field(default_factory=list)
    frames: list[EnergyGraphFrame] = field(default_factory=list)
    propagation_order: list[tuple[str, float]] = field(default_factory=list)
    depth_map: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Top-level report
# ---------------------------------------------------------------------------

@dataclass
class ImpactReport:
    """Top-level container for a multi-face DWI DOE analysis."""
    project_name: str = ""
    impactor: ImpactorSpec = field(default_factory=ImpactorSpec)
    generation_mode: str = "DampingSpring"
    boundary_distance: float = 0.0
    offset_distance: float = 0.05
    faces: list[FaceOrientation] = field(default_factory=list)
    positions_by_face: dict[str, list[ImpactPosition]] = field(default_factory=dict)
    parts: list[PartInfo] = field(default_factory=list)
    results: list[PairResult] = field(default_factory=list)
    energy_flows: dict[str, EnergyFlow] = field(default_factory=dict)  # keyed by pos_id
    findings: list[Finding] = field(default_factory=list)
    sim_params: dict = field(default_factory=dict)
    doe_config: dict = field(default_factory=dict)
    test_dir: str = ""
    # Per-run impactor trajectories, keyed by pos_id (one trajectory shared
    # across all parts of the same run; also attached to each PairResult).
    impactor_trajectories: dict[str, ImpactorTrajectory] = field(default_factory=dict)
    trajectory_clusters: TrajectoryClusters | None = None
