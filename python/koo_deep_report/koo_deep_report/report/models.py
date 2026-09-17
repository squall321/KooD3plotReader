"""Data models for koo_deep_report."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# sim_detector output
# ---------------------------------------------------------------------------

@dataclass
class SimInfo:
    path: Path
    d3plot: Path | None = None
    glstat: Path | None = None
    binout: Path | None = None
    matsum: Path | None = None
    rcforc: Path | None = None
    rwforc: Path | None = None
    spcforc: Path | None = None
    sleout: Path | None = None
    keyword: Path | None = None

    normal_termination: bool | None = None   # None = 판단 불가 (계속 진행)
    termination_source: str = "unknown"       # "glstat" | "d3hsp" | "unknown"
    tier: int = 0

    @property
    def can_analyze(self) -> bool:
        """T0(명확 오류종료)만 스킵. unknown이면 계속."""
        return self.d3plot is not None and self.normal_termination is not False

    @property
    def can_analyze_energy(self) -> bool:
        return self.glstat is not None

    @property
    def tier_label(self) -> str:
        labels = {
            0: "T0 (종료 실패)",
            1: "T1 (d3plot)",
            2: "T2 (d3plot + glstat)",
            3: "T3 (d3plot + glstat + binout)",
            4: "T4 (전체)",
        }
        return labels.get(self.tier, f"T{self.tier}")


# ---------------------------------------------------------------------------
# glstat_reader output
# ---------------------------------------------------------------------------

@dataclass
class GlstatData:
    normal_termination: bool | None = None
    t: list[float] = field(default_factory=list)
    total_energy: list[float] = field(default_factory=list)
    kinetic_energy: list[float] = field(default_factory=list)
    internal_energy: list[float] = field(default_factory=list)
    hourglass_energy: list[float] = field(default_factory=list)
    #: glstat 'added mass' — 그 줄이 있는 블록만 담는다. 비어 있으면 LS-DYNA 가
    #: 'added mass' 블록을 아예 쓰지 않았다는 뜻이고, 그건 질량 스케일링을
    #: 쓰지 않았다는 뜻이다 (0 으로 채우면 둘을 구분할 수 없다).
    mass: list[float] = field(default_factory=list)
    #: glstat 'percentage increase' — 모델 질량 대비 추가 질량 비율(%).
    #: 그 줄이 없는 glstat 도 있어서, 비어 있으면 '판단 불가' 다.
    mass_pct_increase: list[float] = field(default_factory=list)
    energy_ratio: list[float] = field(default_factory=list)  # internal/total

    @property
    def energy_ratio_min(self) -> float | None:
        return min(self.energy_ratio) if self.energy_ratio else None

    @property
    def energy_ratio_max(self) -> float | None:
        return max(self.energy_ratio) if self.energy_ratio else None

    @property
    def mass_added_pct(self) -> float | None:
        """최종 질량 증가율(%). glstat 에 'percentage increase' 가 없으면 None."""
        return self.mass_pct_increase[-1] if self.mass_pct_increase else None

    @property
    def has_mass_added(self) -> bool | None:
        """질량 추가 여부 (모델 질량 대비 1% 이상 증가). 판단 불가면 None.

        'added mass' 는 보통 t=0 에 0 이다. 그 값의 자기 대비 증가율을 보면
        질량 스케일링이 있어도 잡히지 않는다 — LS-DYNA 가 직접 내놓는
        'percentage increase' 를 쓴다.

        그 줄이 없는 경우는 둘로 갈린다. 'added mass' 블록 자체가 없으면
        LS-DYNA 가 질량 스케일링을 하지 않은 것이라 추가 질량은 0 이다
        (판단 불가가 아니다). 블록은 있는데 증가율만 없을 때가 판단 불가다.
        """
        pct = self.mass_added_pct
        if pct is not None:
            return pct > 1.0
        if not self.mass:
            return False
        return None

    @property
    def mass_added_reason(self) -> str:
        """has_mass_added 를 그렇게 판단한 근거. 증가율을 읽었으면 빈 문자열."""
        if self.mass_pct_increase:
            return ""
        if not self.mass:
            return "glstat 에 'added mass' 블록이 없다 — 질량 스케일링 미사용"
        return "glstat 에 'percentage increase' 줄이 없다 — 질량 추가 판단 불가"


# ---------------------------------------------------------------------------
# d3plot_reader output
# ---------------------------------------------------------------------------

@dataclass
class PartTimeSeries:
    part_id: int
    part_name: str
    quantity: str          # "von_mises" | "eff_plastic_strain"
    unit: str
    global_max: float
    global_min: float
    time_of_max: float
    data: list[dict]       # [{time, max, min, avg, max_element_id}]
    #: analysis_result.json 의 num_points — 해석이 실제로 남긴 점 수.
    #: data 보다 크면 JSON 이 잘린 것이다 (0 = 미기록).
    num_points: int = 0

    @property
    def truncated(self) -> bool:
        """JSON 이 시계열을 잘랐는가 (남은 점이 num_points 보다 적다)."""
        return self.num_points > len(self.data)

    @property
    def omitted_points(self) -> int:
        """잘려나간 점 수. 잘리지 않았으면 0."""
        return max(0, self.num_points - len(self.data)) if self.num_points else 0

    @property
    def t(self) -> list[float]:
        return [d["time"] for d in self.data]

    @property
    def max_vals(self) -> list[float]:
        return [d["max"] for d in self.data]

    @property
    def avg_vals(self) -> list[float]:
        return [d["avg"] for d in self.data]

    @property
    def peak_element_id(self) -> int | None:
        """global_max 시점의 max_element_id. 그 시점이 없으면 None.

        가장 가까운 남은 점으로 대체하지 않는다 — 다른 시각의 요소를
        '피크 위치' 라고 부르게 된다. 사유는 peak_element_reason 에 있다.
        """
        d = self._peak_point()
        return d.get("max_element_id") if d else None

    @property
    def peak_element_reason(self) -> str:
        """peak_element_id 가 None 인 사유. 정상이면 빈 문자열."""
        d = self._peak_point()
        if d is None:
            if self.truncated:
                return f"시계열 잘림 — {self.omitted_points}점 생략되어 피크 시점이 없다"
            return "피크 시점(time_of_max)의 점이 시계열에 없다"
        if d.get("max_element_id") is None:
            return "이 시점에 max_element_id 가 기록되지 않았다"
        return ""

    def _peak_point(self) -> dict | None:
        """time_of_max 와 같은 시각의 점. 없으면 None."""
        tol = max(1e-12, abs(self.time_of_max) * 1e-9)
        for d in self.data:
            if abs(d["time"] - self.time_of_max) <= tol:
                return d
        return None


@dataclass
class MotionData:
    part_id: int
    part_name: str = ""
    t: list[float] = field(default_factory=list)
    disp_x: list[float] = field(default_factory=list)
    disp_y: list[float] = field(default_factory=list)
    disp_z: list[float] = field(default_factory=list)
    disp_mag: list[float] = field(default_factory=list)
    vel_mag: list[float] = field(default_factory=list)
    acc_mag: list[float] = field(default_factory=list)
    max_disp_mag: list[float] = field(default_factory=list)
    max_disp_node: list[int] = field(default_factory=list)

    @property
    def peak_disp_mag(self) -> float | None:
        """절점 변위의 최대 (Max_Disp_Mag). 그 열이 없으면 None.

        Avg_Disp_Mag 는 파트 평균 변위 '벡터' 의 크기라 굽힘·회전에서
        상쇄된다 — 절점 최대의 대역으로 쓰면 실제보다 작게 나온다.
        """
        return max(self.max_disp_mag) if self.max_disp_mag else None

    @property
    def peak_avg_disp_mag(self) -> float | None:
        """파트 평균 변위 벡터 크기의 최대 (Avg_Disp_Mag). 없으면 None."""
        return max(self.disp_mag) if self.disp_mag else None

    @property
    def peak_disp_node(self) -> int | None:
        """peak_disp_mag 시점의 최대 변위 절점 ID. 미기록이면 None."""
        if not self.max_disp_mag or not self.max_disp_node:
            return None
        i = max(range(len(self.max_disp_mag)), key=lambda k: self.max_disp_mag[k])
        return self.max_disp_node[i] if i < len(self.max_disp_node) else None

    @property
    def peak_disp_reason(self) -> str:
        """peak_disp_mag 가 None 인 사유. 정상이면 빈 문자열."""
        if self.max_disp_mag:
            return ""
        return "motion CSV 에 Max_Disp_Mag 열이 없다 — 절점 최대 변위 미계측"

    @property
    def peak_vel_mag(self) -> float:
        return max(self.vel_mag) if self.vel_mag else 0.0

    @property
    def peak_acc_mag(self) -> float:
        return max(self.acc_mag) if self.acc_mag else 0.0


@dataclass
class ElementQualityData:
    """Element quality time-history for one part."""
    part_id: int
    part_name: str = ""
    element_type: str = "shell"
    num_elements: int = 0
    # *_measured 가 False 면 그 지표는 미산출이다 (축퇴 요소뿐이거나 셸이라
    # 정의되지 않음). 0/1.0 을 그대로 보여주면 '완벽한 메시' 로 오독된다.
    aspect_measured: bool = False
    peak_aspect_ratio: float = 0.0
    aspect_unavailable_count: int = 0
    jacobian_measured: bool = False
    min_jacobian: float = 1.0
    jacobian_unavailable_count: int = 0
    warpage_measured: bool = False
    peak_warpage: float = 0.0
    skewness_measured: bool = False
    peak_skewness: float = 0.0
    volume_measured: bool = False
    min_volume_change: float = 1.0
    max_volume_change: float = 1.0
    max_negative_jacobian_count: int = 0
    data: list[dict] = field(default_factory=list)
    # data[i] = {time, ar_max, ar_avg, jac_min, skew_max, warp_max, vol_min, vol_max, n_neg_jac, n_high_ar}


@dataclass
class ElementTensorHistory:
    """Full stress tensor time history for a single peak element."""
    element_id: int
    part_id: int
    reason: str = ""       # "peak_von_mises", "peak_max_principal", "peak_min_principal"
    peak_value: float = 0.0
    peak_time: float = 0.0
    time: list[float] = field(default_factory=list)
    sxx: list[float] = field(default_factory=list)
    syy: list[float] = field(default_factory=list)
    szz: list[float] = field(default_factory=list)
    sxy: list[float] = field(default_factory=list)
    syz: list[float] = field(default_factory=list)
    szx: list[float] = field(default_factory=list)


@dataclass
class D3plotResult:
    metadata: dict                            # unified_analyzer metadata
    stress: list[PartTimeSeries]              # stress_history[]
    strain: list[PartTimeSeries]              # strain_history[]
    acceleration: list[PartTimeSeries]        # acceleration_history[]
    motion: dict[int, MotionData]             # part_id → motion CSV
    max_principal: list[PartTimeSeries] = field(default_factory=list)  # max_principal_history[]
    min_principal: list[PartTimeSeries] = field(default_factory=list)  # min_principal_history[]
    max_principal_strain: list[PartTimeSeries] = field(default_factory=list)  # max_principal_strain_history[]
    min_principal_strain: list[PartTimeSeries] = field(default_factory=list)  # min_principal_strain_history[]
    #: von Mises 등가 변형률 (변형률 텐서가 있는 덱에서만)
    vm_strain: list[PartTimeSeries] = field(default_factory=list)
    peak_element_tensors: list[ElementTensorHistory] = field(default_factory=list)
    element_quality: list[ElementQualityData] = field(default_factory=list)
    #: 핫스팟 군집 — analysis_result.json 의 hotspot_clusters 원형(파트×기준 항목).
    #: 필드 뜻은 docs/hotspot-cluster-usage.md. 비활성이면 빈 리스트.
    hotspot_clusters: list[dict] = field(default_factory=list)
    render_files: list[Path] = field(default_factory=list)
    output_dir: Path | None = None

    @property
    def num_states(self) -> int:
        return self.metadata.get("num_states", 0)

    @property
    def t_end(self) -> float:
        return self.metadata.get("end_time", 0.0)

    @property
    def analyzed_parts(self) -> list[int]:
        return self.metadata.get("analyzed_parts", [])

    def get_stress(self, part_id: int) -> PartTimeSeries | None:
        return next((s for s in self.stress if s.part_id == part_id), None)

    def get_strain(self, part_id: int) -> PartTimeSeries | None:
        return next((s for s in self.strain if s.part_id == part_id), None)

    def get_motion(self, part_id: int) -> MotionData | None:
        return self.motion.get(part_id)

    def get_max_principal(self, part_id: int) -> PartTimeSeries | None:
        return next((s for s in self.max_principal if s.part_id == part_id), None)

    def get_min_principal(self, part_id: int) -> PartTimeSeries | None:
        return next((s for s in self.min_principal if s.part_id == part_id), None)

    def get_max_principal_strain(self, part_id: int) -> PartTimeSeries | None:
        return next((s for s in self.max_principal_strain if s.part_id == part_id), None)

    def get_min_principal_strain(self, part_id: int) -> PartTimeSeries | None:
        return next((s for s in self.min_principal_strain if s.part_id == part_id), None)

    def get_vm_strain(self, part_id: int) -> PartTimeSeries | None:
        return next((s for s in self.vm_strain if s.part_id == part_id), None)


# ---------------------------------------------------------------------------
# Aggregated result for one simulation (compare 입력용)
# ---------------------------------------------------------------------------

@dataclass
class PartSummary:
    part_id: int
    part_name: str
    #: 응력 이력이 없는 파트(셸·두꺼운셸 등)는 미산출이다 — 0 이 아니다.
    peak_stress: float | None = None
    time_of_peak_stress: float | None = None
    #: peak_stress 가 None 인 사유.
    peak_stress_reason: str = ""
    peak_element_id: int | None = None
    #: peak_element_id 가 None 인 사유 (시계열 잘림 등). 정상이면 빈 문자열.
    peak_element_reason: str = ""
    peak_strain: float = 0.0
    peak_max_principal: float = 0.0
    peak_min_principal: float = 0.0
    peak_max_principal_strain: float = 0.0
    peak_min_principal_strain: float = 0.0
    #: ε_vm. 미기록이면 None — 0 이 아니다(유효소성변형률로 대체 금지).
    peak_vm_strain: float | None = None
    #: 절점 최대 변위. Max_Disp_Mag 열이 없으면 None — 0 이 아니다.
    peak_disp_mag: float | None = None
    #: 파트 평균 변위 벡터 크기의 최대 (참고용).
    peak_avg_disp_mag: float | None = None
    #: peak_disp_mag 시점의 절점 ID.
    peak_disp_node: int | None = None
    #: peak_disp_mag 가 None 인 사유.
    peak_disp_reason: str = ""
    peak_vel_mag: float = 0.0
    peak_acc_mag: float = 0.0
    internal_energy: float = 0.0
    safety_factor: float | None = None   # yield_stress / peak_stress

    # Design criteria evaluation (per-part, from keyword MAT card)
    mat_type: str = ""
    stress_limit: float = 0.0             # design stress limit (MPa)
    stress_source: str = "none"           # "mat_card" | "manual" | "none"
    strain_limit: float = 0.002           # design strain limit (default 0.2%)
    strain_source: str = "default"        # "mat_card" | "manual" | "default"
    stress_ratio: float | None = None     # peak_stress / stress_limit
    strain_ratio: float | None = None     # peak_strain / strain_limit

    @property
    def stress_warning(self) -> str:
        """'ok' | 'warn' (>=80%) | 'crit' (>=100%) | 'none'."""
        if self.stress_ratio is None:
            return "none"
        if self.stress_ratio >= 1.0:
            return "crit"
        if self.stress_ratio >= 0.8:
            return "warn"
        return "ok"

    @property
    def strain_warning(self) -> str:
        if self.strain_ratio is None:
            return "none"
        if self.strain_ratio >= 1.0:
            return "crit"
        if self.strain_ratio >= 0.8:
            return "warn"
        return "ok"

    @property
    def worst_warning(self) -> str:
        levels = {"none": 0, "ok": 1, "warn": 2, "crit": 3}
        return max(self.stress_warning, self.strain_warning, key=lambda w: levels[w])


@dataclass
class SingleResult:
    sim_info: SimInfo
    d3plot_result: D3plotResult | None = None
    glstat_data: GlstatData | None = None
    binout_data: "BinoutData | None" = None
    #: rcforc 접촉력 계측·검증 (core.contact_metrics 계약). 계측 안 됐으면
    #: available=False 와 사유가 들어온다 — 빈 dict 가 아니다.
    contact_metrics: dict = field(default_factory=dict)
    parts: dict[int, PartSummary] = field(default_factory=dict)
    label: str = ""
    yield_stress: float = 0.0  # legacy global override (0 = use per-part)

    # 글로벌 요약
    #: 응력이 산출된 파트가 하나도 없으면 None.
    peak_stress_global: float | None = None
    peak_stress_part_id: int | None = None
    #: 집계된 파트가 하나도 없으면 None (0.0 으로 채우면 '변형률 0 으로
    #: 측정됐다' 로 읽힌다).
    peak_strain_global: float | None = None
    #: 절점 최대 변위의 전체 최대. 아무 파트도 계측되지 않았으면 None.
    peak_disp_global: float | None = None
    energy_ratio_min: float | None = None

    def to_compare_dict(self) -> dict:
        """compare 모드 입력용 JSON 직렬화."""
        return {
            "schema": "koo_deep_report/1.0",
            "label": self.label,
            "tier": self.sim_info.tier,
            "metadata": {
                "d3plot_path": str(self.sim_info.d3plot) if self.sim_info.d3plot else "",
                "project_name": self.sim_info.path.name,
                "normal_termination": self.sim_info.normal_termination,
                "termination_source": self.sim_info.termination_source,
                "num_states": self.d3plot_result.num_states if self.d3plot_result else 0,
                # d3plot 을 못 읽었으면 해석 종료 시각을 모른다 — 0.0 으로 채우면
                # 배치 표에 '0 초에 끝났다' 로 찍힌다.
                "t_end": self.d3plot_result.t_end if self.d3plot_result else None,
                "num_parts": len(self.parts),
            },
            "summary": {
                "peak_stress_global": self.peak_stress_global,
                "peak_stress_part_id": self.peak_stress_part_id,
                "peak_strain_global": self.peak_strain_global,
                "peak_disp_global": self.peak_disp_global,
                "energy_ratio_min": self.energy_ratio_min,
            },
            "parts": {
                str(pid): {
                    "name": p.part_name,
                    "peak_stress": p.peak_stress,
                    "time_of_peak_stress": p.time_of_peak_stress,
                    "peak_stress_reason": p.peak_stress_reason,
                    "peak_strain": p.peak_strain,
                    "peak_disp_mag": p.peak_disp_mag,
                    "peak_avg_disp_mag": p.peak_avg_disp_mag,
                    "peak_disp_node": p.peak_disp_node,
                    "peak_disp_reason": p.peak_disp_reason,
                    "peak_acc_mag": p.peak_acc_mag,
                    "safety_factor": p.safety_factor,
                    "mat_type": p.mat_type,
                    "stress_limit": p.stress_limit,
                    "stress_source": p.stress_source,
                    "strain_limit": p.strain_limit,
                    "strain_source": p.strain_source,
                    "stress_ratio": p.stress_ratio,
                    "strain_ratio": p.strain_ratio,
                    "stress_warning": p.stress_warning,
                    "strain_warning": p.strain_warning,
                }
                for pid, p in self.parts.items()
            },
            "glstat": {
                "t": self.glstat_data.t,
                "total_energy": self.glstat_data.total_energy,
                "kinetic_energy": self.glstat_data.kinetic_energy,
                "internal_energy": self.glstat_data.internal_energy,
                "energy_ratio": self.glstat_data.energy_ratio,
            } if self.glstat_data else None,
        }
