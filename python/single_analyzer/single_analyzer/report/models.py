"""Data models for single_analyzer."""
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
    mass: list[float] = field(default_factory=list)
    energy_ratio: list[float] = field(default_factory=list)  # internal/total

    @property
    def energy_ratio_min(self) -> float | None:
        return min(self.energy_ratio) if self.energy_ratio else None

    @property
    def energy_ratio_max(self) -> float | None:
        return max(self.energy_ratio) if self.energy_ratio else None

    @property
    def has_mass_added(self) -> bool:
        """질량 추가 여부 (초기 질량 대비 1% 이상 증가)."""
        if len(self.mass) < 2 or self.mass[0] == 0:
            return False
        return (self.mass[-1] - self.mass[0]) / self.mass[0] > 0.01


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
        """global_max 시점의 max_element_id."""
        for d in self.data:
            if abs(d["time"] - self.time_of_max) < 1e-12:
                return d.get("max_element_id")
        # 가장 가까운 시점
        if self.data:
            closest = min(self.data, key=lambda d: abs(d["time"] - self.time_of_max))
            return closest.get("max_element_id")
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
    def peak_disp_mag(self) -> float:
        return max(self.disp_mag) if self.disp_mag else 0.0

    @property
    def peak_vel_mag(self) -> float:
        return max(self.vel_mag) if self.vel_mag else 0.0

    @property
    def peak_acc_mag(self) -> float:
        return max(self.acc_mag) if self.acc_mag else 0.0

    @property
    def peak_max_disp(self) -> float:
        return max(self.max_disp_mag) if self.max_disp_mag else 0.0


@dataclass
class D3plotResult:
    metadata: dict                            # unified_analyzer metadata
    stress: list[PartTimeSeries]              # stress_history[]
    strain: list[PartTimeSeries]              # strain_history[]
    acceleration: list[PartTimeSeries]        # acceleration_history[]
    motion: dict[int, MotionData]             # part_id → motion CSV
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


# ---------------------------------------------------------------------------
# Aggregated result for one simulation (compare 입력용)
# ---------------------------------------------------------------------------

@dataclass
class PartSummary:
    part_id: int
    part_name: str
    peak_stress: float = 0.0
    time_of_peak_stress: float = 0.0
    peak_element_id: int | None = None
    peak_strain: float = 0.0
    peak_disp_mag: float = 0.0
    peak_vel_mag: float = 0.0
    peak_acc_mag: float = 0.0
    internal_energy: float = 0.0
    safety_factor: float | None = None   # peak_stress / yield_stress (있을 때)


@dataclass
class SingleResult:
    sim_info: SimInfo
    d3plot_result: D3plotResult | None = None
    glstat_data: GlstatData | None = None
    binout_data: "BinoutData | None" = None
    parts: dict[int, PartSummary] = field(default_factory=dict)
    label: str = ""
    yield_stress: float = 0.0

    # 글로벌 요약
    peak_stress_global: float = 0.0
    peak_stress_part_id: int | None = None
    peak_strain_global: float = 0.0
    peak_disp_global: float = 0.0
    energy_ratio_min: float | None = None

    def to_compare_dict(self) -> dict:
        """compare 모드 입력용 JSON 직렬화."""
        return {
            "schema": "single_analyzer/1.0",
            "label": self.label,
            "tier": self.sim_info.tier,
            "metadata": {
                "d3plot_path": str(self.sim_info.d3plot) if self.sim_info.d3plot else "",
                "project_name": self.sim_info.path.name,
                "normal_termination": self.sim_info.normal_termination,
                "termination_source": self.sim_info.termination_source,
                "num_states": self.d3plot_result.num_states if self.d3plot_result else 0,
                "t_end": self.d3plot_result.t_end if self.d3plot_result else 0.0,
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
                    "peak_strain": p.peak_strain,
                    "peak_disp_mag": p.peak_disp_mag,
                    "peak_acc_mag": p.peak_acc_mag,
                    "safety_factor": p.safety_factor,
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
