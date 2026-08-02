"""Parse binout files using lasso.dyna.Binout (optional dependency)."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from pathlib import Path


@dataclass
class MatSumData:
    """Per-part material energy summary (from binout matsum)."""
    part_ids: list[int] = field(default_factory=list)
    part_names: list[str] = field(default_factory=list)
    t: list[float] = field(default_factory=list)
    internal_energy: list[list[float]] = field(default_factory=list)  # [n_times][n_parts]
    kinetic_energy: list[list[float]] = field(default_factory=list)
    # 파트간 에너지 흐름 빌더용 부가 필드 (전부 옵셔널 — 없으면 빈 리스트라
    # 기존 소비자 무영향). rbvelocity 는 강체 병진속도[mm/s], work(F·Δv) 계산용.
    hourglass_energy: list[list[float]] = field(default_factory=list)
    eroded_internal_energy: list[list[float]] = field(default_factory=list)
    eroded_kinetic_energy: list[list[float]] = field(default_factory=list)
    x_rbvelocity: list[list[float]] = field(default_factory=list)
    y_rbvelocity: list[list[float]] = field(default_factory=list)
    z_rbvelocity: list[list[float]] = field(default_factory=list)
    # 파트별 병진 운동량 [tonne·mm/s]. 접촉 충격량 ∫F dt 와 대조해
    # "접촉력이 운동량 변화를 설명하는가" 를 검증하는 데 쓴다.
    x_momentum: list[list[float]] = field(default_factory=list)
    y_momentum: list[list[float]] = field(default_factory=list)
    z_momentum: list[list[float]] = field(default_factory=list)

    def peak_internal_energy(self, part_idx: int) -> float:
        if not self.internal_energy:
            return 0.0
        return max(abs(row[part_idx]) for row in self.internal_energy)


@dataclass
class GlstatBranchData:
    """Global energy time series read directly from the binout ``glstat`` branch.

    ASCII glstat 파서(glstat_reader)와 별개 — binout 워커가 이미 파일을 열고
    있으므로 재사용 비용 0. 에너지 보존 체크·diss 총량의 권위 소스.
    """
    t: list[float] = field(default_factory=list)
    kinetic_energy: list[float] = field(default_factory=list)
    internal_energy: list[float] = field(default_factory=list)
    sliding_interface_energy: list[float] = field(default_factory=list)
    hourglass_energy: list[float] = field(default_factory=list)
    system_damping_energy: list[float] = field(default_factory=list)
    eroded_kinetic_energy: list[float] = field(default_factory=list)
    total_energy: list[float] = field(default_factory=list)
    energy_ratio: list[float] = field(default_factory=list)


@dataclass
class RcforcInterface:
    """Single contact interface from rcforc."""
    interface_id: int
    name: str
    side: int   # 0=slave, 1=master, -1=total(slave+master)
    t: list[float] = field(default_factory=list)
    fx: list[float] = field(default_factory=list)
    fy: list[float] = field(default_factory=list)
    fz: list[float] = field(default_factory=list)

    @property
    def fmag(self) -> list[float]:
        return [math.sqrt(x*x + y*y + z*z) for x, y, z in zip(self.fx, self.fy, self.fz)]

    @property
    def peak_fmag(self) -> float:
        vals = self.fmag
        return max(vals) if vals else 0.0


@dataclass
class SleoutInterface:
    """Single sliding contact interface from sleout."""
    interface_id: int
    name: str
    t: list[float] = field(default_factory=list)
    total_energy: list[float] = field(default_factory=list)
    friction_energy: list[float] = field(default_factory=list)


@dataclass
class BinoutData:
    matsum: MatSumData | None = None
    rcforc: list[RcforcInterface] = field(default_factory=list)
    sleout: list[SleoutInterface] = field(default_factory=list)
    glstat: GlstatBranchData | None = None


def parse_binout(binout_path: Path) -> BinoutData | None:
    """Parse binout file. Returns None if lasso not available or file unreadable."""
    try:
        from lasso.dyna import Binout  # type: ignore
    except ImportError:
        return None

    try:
        b = Binout(str(binout_path))
    except Exception:
        return None

    entries = b.read()
    result = BinoutData()

    if "matsum" in entries:
        result.matsum = _parse_matsum(b)

    if "rcforc" in entries:
        result.rcforc = _parse_rcforc(b)

    if "sleout" in entries:
        result.sleout = _parse_sleout(b)

    if "glstat" in entries:
        result.glstat = _parse_glstat_branch(b)

    return result


def _read_opt(b, branch: str, var: str, default=None):
    """옵셔널 binout 변수 read — 실패해도 필수 데이터를 죽이지 않는다.

    일부 lasso/binout 조합에서 legend(파트 이름) 디코딩이
    ``ValueError: chr() arg not in range(0x110000)`` 로 죽는데, 포괄 except 가
    멀쩡한 time/ids/IE/KE 까지 통째로 버려 에너지 파이프라인 전체가 무음으로
    빈 값이 됐다 (2026-07 Test_Impact_A 실증). 이름/부가 필드는 실패 시
    default 로 진행한다.
    """
    try:
        return b.read(branch, var)
    except Exception:
        return default


def _parse_matsum(b) -> MatSumData | None:
    try:
        import numpy as np
        t = b.read("matsum", "time")
        ids = b.read("matsum", "ids")
        legend = _read_opt(b, "matsum", "legend")
        ie = b.read("matsum", "internal_energy")
        ke = b.read("matsum", "kinetic_energy")

        part_ids = [int(x) for x in ids]
        part_names = _parse_legend(legend, len(part_ids))

        def _opt2d(var):
            a = _read_opt(b, "matsum", var)
            try:
                return a.tolist() if a is not None else []
            except Exception:
                return []

        md = MatSumData(
            part_ids=part_ids,
            part_names=part_names,
            t=t.tolist(),
            internal_energy=ie.tolist(),
            kinetic_energy=ke.tolist(),
            hourglass_energy=_opt2d("hourglass_energy"),
            eroded_internal_energy=_opt2d("eroded_internal_energy"),
            eroded_kinetic_energy=_opt2d("eroded_kinetic_energy"),
            x_rbvelocity=_opt2d("x_rbvelocity"),
            y_rbvelocity=_opt2d("y_rbvelocity"),
            z_rbvelocity=_opt2d("z_rbvelocity"),
            x_momentum=_opt2d("x_momentum"),
            y_momentum=_opt2d("y_momentum"),
            z_momentum=_opt2d("z_momentum"),
        )
        return md
    except Exception:
        return None


def _parse_glstat_branch(b) -> "GlstatBranchData | None":
    """binout glstat 브랜치 → GlstatBranchData. 필수는 time+KE, 나머지 옵셔널."""
    try:
        t = b.read("glstat", "time")
        ke = b.read("glstat", "kinetic_energy")

        def _opt1d(var):
            a = _read_opt(b, "glstat", var)
            try:
                return a.tolist() if a is not None else []
            except Exception:
                return []

        return GlstatBranchData(
            t=t.tolist(),
            kinetic_energy=ke.tolist(),
            internal_energy=_opt1d("internal_energy"),
            sliding_interface_energy=_opt1d("sliding_interface_energy"),
            hourglass_energy=_opt1d("hourglass_energy"),
            system_damping_energy=_opt1d("system_damping_energy"),
            eroded_kinetic_energy=_opt1d("eroded_kinetic_energy"),
            total_energy=_opt1d("total_energy"),
            energy_ratio=_opt1d("energy_ratio"),
        )
    except Exception:
        return None


def _parse_rcforc(b) -> list[RcforcInterface]:
    try:
        import numpy as np
        t = b.read("rcforc", "time")
        ids = b.read("rcforc", "ids")
        # side/legend 는 deck 설정에 따라 브랜치에 없을 수 있음 — 부가 필드라
        # 실패해도 힘 시계열은 살린다 (_read_opt docstring 참조).
        side = _read_opt(b, "rcforc", "side")
        legend = _read_opt(b, "rcforc", "legend")
        xf = b.read("rcforc", "x_force")
        yf = b.read("rcforc", "y_force")
        zf = b.read("rcforc", "z_force")

        t_list = t.tolist()
        n_entries = len(ids)
        unique_ids = sorted(set(int(x) for x in ids))
        names = _parse_legend(legend, len(unique_ids))
        name_map = dict(zip(unique_ids, names))

        interfaces: list[RcforcInterface] = []
        for i in range(n_entries):
            iid = int(ids[i])
            s = int(side[i]) if side is not None else 0
            col = xf[:, i] if xf.ndim > 1 else xf
            iface = RcforcInterface(
                interface_id=iid,
                name=name_map.get(iid, f"Interface_{iid}"),
                side=s,
                t=t_list,
                fx=(xf[:, i].tolist() if xf.ndim > 1 else xf.tolist()),
                fy=(yf[:, i].tolist() if yf.ndim > 1 else yf.tolist()),
                fz=(zf[:, i].tolist() if zf.ndim > 1 else zf.tolist()),
            )
            interfaces.append(iface)
        return interfaces
    except Exception:
        return []


def _parse_sleout(b) -> list[SleoutInterface]:
    try:
        import numpy as np
        t = b.read("sleout", "time")
        ids = b.read("sleout", "ids")
        legend = _read_opt(b, "sleout", "legend")
        te = b.read("sleout", "total_energy")
        fe = b.read("sleout", "friction_energy")

        t_list = t.tolist()
        n = len(ids)
        names = _parse_legend(legend, n)

        interfaces: list[SleoutInterface] = []
        for i in range(n):
            interfaces.append(SleoutInterface(
                interface_id=int(ids[i]),
                name=names[i] if i < len(names) else f"Interface_{ids[i]}",
                t=t_list,
                total_energy=(te[:, i].tolist() if te.ndim > 1 else te.tolist()),
                friction_energy=(fe[:, i].tolist() if fe.ndim > 1 else fe.tolist()),
            ))
        return interfaces
    except Exception:
        return []


def _parse_legend(legend, n: int) -> list[str]:
    """Parse lasso legend field into list of strings."""
    if legend is None:
        return [f"Interface_{i+1}" for i in range(n)]
    if isinstance(legend, (bytes, str)):
        raw = legend.decode("utf-8", errors="ignore") if isinstance(legend, bytes) else legend
        # Each name is fixed-width padded; split by chunk size
        if n > 0 and len(raw) >= n:
            chunk = len(raw) // n
            return [raw[i*chunk:(i+1)*chunk].strip() for i in range(n)]
        return [raw.strip()]
    # numpy array of bytes
    try:
        import numpy as np
        if hasattr(legend, "tolist"):
            items = legend.tolist()
            result = []
            for item in items:
                if isinstance(item, bytes):
                    result.append(item.decode("utf-8", errors="ignore").strip())
                elif isinstance(item, (list, np.ndarray)):
                    # array of chars
                    result.append(b"".join(item).decode("utf-8", errors="ignore").strip()
                                  if isinstance(item[0], (bytes, np.bytes_))
                                  else "".join(str(c) for c in item).strip())
                else:
                    result.append(str(item).strip())
            return result
    except Exception:
        pass
    return [f"Interface_{i+1}" for i in range(n)]
