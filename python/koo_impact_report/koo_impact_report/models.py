"""Data models for multi-face partial impact (drop-weight) DOE analysis.

Implements §17 (data model v2) and §22.4 (energy flow data model) of
docs/PartialImpactReport_Plan.md.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar


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

    Units (LS-DYNA [ton, mm, s, MPa] convention used by koo_deep_report):
        density        → tonne/mm³   (e.g. steel = 7.85e-9)
        youngs_modulus → MPa         (e.g. steel = 210000)
        mass (derived) → tonne
        radius, height → mm
    """
    # Geometry type — must be set explicitly. Empty string means "unknown"
    # (volume / mass derivation falls back to mass_override in that case).
    type: str = ""                        # "Sphere" | "Cylinder" | ""
    radius: float = 0.0                   # mm
    height: float = 0.0                   # mm — free-fall drop height (if known)
    density: float = 0.0                  # tonne/mm³
    youngs_modulus: float = 0.0           # MPa
    poisson_ratio: float = 0.0
    mass_override: float | None = None    # tonne — when computed externally
    part_id: int | None = None            # source part id in the keyword file
    part_name: str = ""
    mat_type: str = ""                    # MAT keyword (e.g. "RIGID")
    initial_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)  # mm/s
    # Provenance of the geometry (type/radius). "step_config" = authoritative
    # (the exact mesh-generation radius); "motion-bbox" = estimated from the
    # d3plot bounding extent (over-reads radius → trust badge should fire);
    # "" = no geometry resolved.
    geometry_source: str = ""
    # cylinder-only
    front_radius: float | None = None
    outer_radius: float | None = None
    front_height: float | None = None
    back_height: float | None = None
    back_radius: float | None = None

    # Gravitational acceleration g in mm/s². Declared as ``ClassVar`` so it
    # is NOT a per-instance dataclass field (no serialization, no override
    # surface — it's a physical constant, not data).
    G_MM_S2: ClassVar[float] = 9810.0

    @property
    def volume(self) -> float:
        """Volume in mm³.

        type 미지정인데 radius>0 이면 Sphere fallback. drop-weight impact 의
        표준 geometry 는 sphere 이므로 합리적 default. 이전 코드는 type=""
        일 때 V=0 → mass=0/KE=0 으로 떨어졌음. 정확한 geometry 필요하면
        scenario.json 의 ``impactor.type`` 명시 권장.
        """
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
        # Type unspecified — sphere fallback when we at least have a radius.
        if not self.type and self.radius > 0:
            return (4.0 / 3.0) * math.pi * (self.radius ** 3)
        return 0.0

    @property
    def mass(self) -> float:
        """Mass in tonne (LS-DYNA [ton, mm, s] convention).

        Prefer ``mass_override`` (derived from matsum/keyword) over geometric
        density × volume; the latter ignores mass scaling and rigid-body
        inertia keywords.
        """
        if self.mass_override is not None:
            return self.mass_override
        return self.density * self.volume  # tonne/mm³ · mm³ = tonne

    @property
    def velocity(self) -> float:
        """Impact velocity magnitude (mm/s).

        Prefer the parsed ``initial_velocity`` (from ``*INITIAL_VELOCITY*``);
        fall back to free-fall energy: v = sqrt(2 g h) when only height known.
        """
        vx, vy, vz = self.initial_velocity
        v = math.sqrt(vx * vx + vy * vy + vz * vz)
        if v > 0:
            return v
        if self.height > 0:
            return math.sqrt(2.0 * self.G_MM_S2 * self.height)
        return 0.0

    @property
    def kinetic_energy(self) -> float:
        """KE in mJ (= N·mm). [ton, mm, s] → ton·(mm/s)² = mJ."""
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
class PartMotion:
    """Per-part rigid-body motion history (from unified_analyzer motion CSV).

    Units: position [mm], velocity [mm/s], acceleration [mm/s²].
    `peak_g` is the maximum acceleration magnitude.
    """
    part_id: int
    part_name: str = ""
    times: list[float] = field(default_factory=list)         # s
    disp_x: list[float] = field(default_factory=list)
    disp_y: list[float] = field(default_factory=list)
    disp_z: list[float] = field(default_factory=list)
    disp_mag: list[float] = field(default_factory=list)
    vel_x: list[float] = field(default_factory=list)
    vel_y: list[float] = field(default_factory=list)
    vel_z: list[float] = field(default_factory=list)
    vel_mag: list[float] = field(default_factory=list)
    acc_x: list[float] = field(default_factory=list)
    acc_y: list[float] = field(default_factory=list)
    acc_z: list[float] = field(default_factory=list)
    acc_mag: list[float] = field(default_factory=list)
    # Derived scalar summaries
    peak_g: float = 0.0                  # mm/s² — max(|a|)
    peak_g_xyz: tuple[float, float, float] = (0.0, 0.0, 0.0)
    t_peak_g: float = 0.0                # s
    peak_disp: float = 0.0               # max disp_mag
    peak_vel: float = 0.0                # max vel_mag


@dataclass
class PairResult:
    """A single (face × position × part) result row — the core 3D-DOE cell."""
    face: str
    position: ImpactPosition
    part_id: int
    peak_g: float = 0.0          # mm/s² — max |a| from PartMotion
    peak_stress: float = 0.0     # MPa (or IE proxy when stress not available)
    peak_strain: float = 0.0
    peak_disp: float = 0.0       # mm
    peak_vel: float = 0.0        # mm/s
    #: 주응력·주변형률·등가변형률. 산출물에 없으면 None — 0 이 아니다.
    #: σ3/ε3 는 압축측이라 음수이며 부호를 유지한다.
    peak_principal_stress: float | None = None
    min_principal_stress: float | None = None
    peak_principal_strain: float | None = None
    min_principal_strain: float | None = None
    peak_vm_strain: float | None = None
    stress_ts: TimeSeriesData = field(default_factory=TimeSeriesData)
    impactor_trajectory: ImpactorTrajectory | None = None
    part_motion: PartMotion | None = None


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
    name: str = ""                 # 접촉 카드 NAME (sankey/heatmap 라벨)
    confidence: float = 1.0        # 파트 매핑 신뢰도 (1.0=part-id 직독, <1=다수결)
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
    #: rcforc 접촉력 계측·검증 (koo_deep_report.core.contact_metrics 계약).
    #: 계측 안 됐으면 available=False 와 사유가 들어온다 — 빈 dict 가 아니다.
    contact_metrics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Top-level report
# ---------------------------------------------------------------------------

@dataclass
class ImpactReport:
    """Top-level container for a multi-face DWI DOE analysis."""
    project_name: str = ""
    impactor: ImpactorSpec = field(default_factory=ImpactorSpec)
    # DOE generation parameters — populated from scenario.json. Defaults of
    # empty / 0.0 mean "not specified" (no implicit physical assumption).
    generation_mode: str = ""
    boundary_distance: float = 0.0
    offset_distance: float = 0.0
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
    # Per-(pos_id, part_id) rigid-body motion. Populated for single-d3plot mode
    # and any path that runs the unified_analyzer motion extraction.
    part_motions: dict[tuple[str, int], PartMotion] = field(default_factory=dict)
    trajectory_clusters: TrajectoryClusters | None = None
    # 구조화된 로드 진단 (stdout-only 소멸 금지 — SOTA P1b).
    # 각 항목: {"kind": str, "pos_name": str|None, "exc_class": str|None,
    #           "msg": str}. loader 가 채우고 payload meta.load_issues 로 노출,
    # analyzer 가 집계 Finding 으로 승격한다.
    load_issues: list[dict] = field(default_factory=list)
    # per-position solver_quality 감사 결과 (audit_run() dict), pos_id 키.
    # DOE 워커가 병렬로 채운다 — 비어 있으면 payload 가 직렬 fallback 감사
    # (face-tree 경로 등)를 수행한다 (SOTA P2-4).
    solver_quality: dict[str, dict] = field(default_factory=dict)
    # 출처 메타 (tool_version/SIF/UTC/argv/입력 digest). CLI 레이어만 채운다 —
    # loader 는 건드리지 않으므로 골든 테스트가 타임스탬프에 오염되지 않는다
    # (SOTA P2-5). 비어 있으면 payload/JSON 에 키 자체가 나가지 않는다.
    provenance: dict = field(default_factory=dict)
