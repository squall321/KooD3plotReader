"""Data models for full-angle drop simulation analysis."""
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Finding:
    severity: Severity
    title: str
    detail: str
    recommendation: str


@dataclass
class AngleCondition:
    """Drop orientation definition."""
    angle_name: str       # "F1_Back", "P0001", etc.
    roll: float           # degrees
    pitch: float          # degrees
    yaw: float            # degrees
    category: str = ""    # "face", "edge", "corner", "fibonacci"
    swap_axes: bool = False  # True if pitch=lat, roll=lon (auto-detected)

    @property
    def label(self) -> str:
        return self.angle_name

    def to_spherical(self) -> tuple[float, float]:
        """Convert to (longitude, latitude) in radians for Mollweide projection.

        Default: lat=roll, lon=pitch.
        If swap_axes=True: lat=pitch, lon=roll (some DOE generators use this).
        """
        import math
        if self.swap_axes:
            lat = math.radians(self.pitch)
            lon = math.radians(self.roll)
        else:
            lat = math.radians(self.roll)
            lon = math.radians(self.pitch)
        lat = max(-math.pi / 2, min(math.pi / 2, lat))
        return lon, lat


@dataclass
class PartInfo:
    """Part metadata."""
    part_id: int
    part_name: str        # "PKG\\PKG 1", "Front\\Metal"
    group: str = ""       # "PKG", "Front", "PCB", etc.

    @staticmethod
    def extract_group(name: str) -> str:
        if "\\" in name:
            return name.split("\\")[0]
        if "/" in name:
            return name.split("/")[0]
        return "Other"


@dataclass
class TimeSeriesData:
    """Time series with min/max/avg per timestep.

    When loaded in streaming mode, `times`/`max_values`/... may be downsampled
    while `true_peak` / `true_peak_time` retain the exact values from the
    pre-downsampled source (kept for findings / worst-angle accuracy).
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
class MotionData:
    """Motion time series (displacement, velocity, acceleration)."""
    times: list[float] = field(default_factory=list)
    avg_disp_x: list[float] = field(default_factory=list)
    avg_disp_y: list[float] = field(default_factory=list)
    avg_disp_z: list[float] = field(default_factory=list)
    avg_disp_mag: list[float] = field(default_factory=list)
    avg_vel_x: list[float] = field(default_factory=list)
    avg_vel_y: list[float] = field(default_factory=list)
    avg_vel_z: list[float] = field(default_factory=list)
    avg_vel_mag: list[float] = field(default_factory=list)
    avg_acc_x: list[float] = field(default_factory=list)
    avg_acc_y: list[float] = field(default_factory=list)
    avg_acc_z: list[float] = field(default_factory=list)
    avg_acc_mag: list[float] = field(default_factory=list)
    max_disp_mag: list[float] = field(default_factory=list)
    true_peak_g: float | None = None
    true_peak_g_time: float | None = None
    true_peak_disp: float | None = None

    # 가속도 → G 환산 계수. 기본은 ton-mm-s(mm/s²) 이지만 **덱 단위계에 따라
    # 런타임에 바뀐다** (loader 가 검출해 set_unit_system 으로 주입).
    # 예전에는 9810 하드코딩이라 SI 덱(m/s²) 을 넣으면 peak-G 가 1000배 작게
    # 나오고 경고도 없었다 — 조용히 틀리는 종류라 가장 위험했다.
    G_FACTOR = 9810.0
    #: 검출된 단위계 id ("ton-mm-s" / "SI" / "" =미검출). 화면 표기용.
    UNIT_SYSTEM = "ton-mm-s"

    @classmethod
    def set_unit_system(cls, unit_id: str, g_factor: float) -> None:
        """검출된 단위계를 적용. 알 수 없으면 호출하지 않아 기본값이 유지된다."""
        cls.UNIT_SYSTEM = str(unit_id or "")
        try:
            gf = float(g_factor)
        except (TypeError, ValueError):
            return
        if gf > 0:
            cls.G_FACTOR = gf

    @property
    def peak_g(self) -> float:
        if self.true_peak_g is not None:
            return self.true_peak_g
        if not self.avg_acc_mag:
            return 0.0
        return max(abs(v) for v in self.avg_acc_mag) / self.G_FACTOR

    @property
    def peak_g_time(self) -> float:
        if self.true_peak_g_time is not None:
            return self.true_peak_g_time
        if not self.avg_acc_mag:
            return 0.0
        abs_vals = [abs(v) for v in self.avg_acc_mag]
        idx = abs_vals.index(max(abs_vals))
        return self.times[idx] if idx < len(self.times) else 0.0

    @property
    def peak_disp(self) -> float:
        if self.true_peak_disp is not None:
            return self.true_peak_disp
        return max(self.max_disp_mag) if self.max_disp_mag else 0.0

    def g_series(self) -> list[float]:
        """Return acceleration in G units."""
        return [abs(v) / self.G_FACTOR for v in self.avg_acc_mag]


@dataclass
class PartEnergy:
    """파트별 에너지 요약 (binout matsum 경유, 원해상도 참피크).

    값이 없으면 0.0 이 아니라 None 이다 — '계측 안 됨' 과 '0 이었음' 은 다르다.
    peak 와 final 을 함께 두는 이유: 피크만 보면 되튐(탄성 복원)을 흡수로
    오독한다. 끝까지 남은 final_ie 가 실제로 그 파트가 먹은 에너지다.
    """
    peak_ie: float | None = None
    peak_ie_time: float | None = None
    peak_ke: float | None = None
    peak_ke_time: float | None = None
    final_ie: float | None = None
    final_ke: float | None = None


@dataclass
class PartResult:
    """Analysis result for one part in one simulation run."""
    part: PartInfo
    stress: TimeSeriesData | None = None
    strain: TimeSeriesData | None = None
    motion: MotionData | None = None
    #: binout matsum 이 있을 때만 채워진다. 없으면 None (0 으로 위장 금지).
    energy: PartEnergy | None = None
    #: 최대 주응력 σ1. unified_analyzer 가 von Mises 와 **항상 함께** 내지만
    #: 구버전으로 돌린 산출물에는 CSV 가 없다 → 그때는 None (0 아님).
    principal: TimeSeriesData | None = None
    #: 최소 주응력 σ3 (압축측). 취성 파단·박리는 σ1 만으로 안 보인다.
    principal_min: TimeSeriesData | None = None
    #: 주변형률 ε1/ε3. d3plot 에 변형률 텐서가 실린 덱에서만 나온다
    #: (*DATABASE_EXTENT_BINARY STRFLG). 없으면 None — 0 이 아니다.
    principal_strain: TimeSeriesData | None = None
    principal_strain_min: TimeSeriesData | None = None
    #: von Mises 등가 변형률 ε_vm = sqrt(2/3·e_dev:e_dev).
    #: 유효소성변형률(eff_plastic)과 다른 양이다 — 탄성분을 포함한다.
    vm_strain: TimeSeriesData | None = None

    @property
    def peak_stress(self) -> float:
        return self.stress.peak if self.stress else 0.0

    @property
    def peak_principal(self) -> float | None:
        """최대 주응력 피크. 미계측이면 None — von Mises 로 대체하지 않는다."""
        return self.principal.peak if self.principal else None

    @property
    def peak_vm_strain(self) -> float | None:
        """von Mises 등가 변형률 피크. 미기록이면 None."""
        return self.vm_strain.peak if self.vm_strain else None

    @property
    def peak_principal_strain(self) -> float | None:
        """최대 주변형률 ε1. 미기록이면 None (유효소성변형률로 대체하지 않는다)."""
        return self.principal_strain.peak if self.principal_strain else None

    @property
    def min_principal_strain(self) -> float | None:
        """최소 주변형률 ε3 — 압축측이라 최소값이 의미 있다."""
        ts = self.principal_strain_min
        if ts is None:
            return None
        vals = list(ts.min_values or []) or list(ts.max_values or [])
        return min(vals) if vals else None

    @property
    def min_principal(self) -> float | None:
        """σ3 의 **최소값**(가장 큰 압축). peak 속성이 max 를 주므로 직접 뽑는다."""
        ts = self.principal_min
        if ts is None:
            return None
        vals = list(ts.min_values or []) or list(ts.max_values or [])
        return min(vals) if vals else None

    @property
    def peak_strain(self) -> float:
        return self.strain.peak if self.strain else 0.0

    @property
    def peak_g(self) -> float:
        return self.motion.peak_g if self.motion else 0.0

    @property
    def peak_disp(self) -> float:
        return self.motion.peak_disp if self.motion else 0.0


@dataclass
class SimulationResult:
    """Complete result for one simulation run (one drop angle)."""
    run_folder: str
    angle: AngleCondition
    parts: dict[int, PartResult] = field(default_factory=dict)
    num_states: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    success: bool = True


@dataclass
class SimulationParams:
    """Simulation parameters from runner_config.json."""
    t_final: float = 0.001
    dt: float = 1e-6
    drop_height: float = 1500.0
    density: float = 7850.0
    youngs_modulus: float = 2e11
    poisson_ratio: float = 0.3


@dataclass
class Report:
    """Top-level report object containing all analysis results."""
    project_name: str = ""
    doe_strategy: str = ""
    simulation_params: SimulationParams = field(default_factory=SimulationParams)
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    results: list[SimulationResult] = field(default_factory=list)
    part_info: dict[int, PartInfo] = field(default_factory=dict)
    angular_spacing_deg: float = 0.0
    sphere_coverage: float = 0.0
    findings: list[Finding] = field(default_factory=list)
    yield_stress: float = 0.0  # User-defined yield stress for safety factor
    test_dir: str = ""         # Source test directory (for d3plot access)
    # 파트간 에너지 흐름: {run_folder: neutral flow dict from build_flow_graph}.
    # binout/keyword/lasso 부재 run 은 조용히 누락(키 없음) — 무음 실패 대신
    # 로그를 남기되 보고서는 정상 진행. 자유낙하라 impactor 노드 없이 최조기
    # 접촉(바닥) 을 root 로 쓴다.
    energy_flows: dict = field(default_factory=dict)
