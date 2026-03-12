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

    def peak_internal_energy(self, part_idx: int) -> float:
        if not self.internal_energy:
            return 0.0
        return max(abs(row[part_idx]) for row in self.internal_energy)


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

    return result


def _parse_matsum(b) -> MatSumData | None:
    try:
        import numpy as np
        t = b.read("matsum", "time")
        ids = b.read("matsum", "ids")
        legend = b.read("matsum", "legend")
        ie = b.read("matsum", "internal_energy")
        ke = b.read("matsum", "kinetic_energy")

        part_ids = [int(x) for x in ids]
        part_names = _parse_legend(legend, len(part_ids))

        md = MatSumData(
            part_ids=part_ids,
            part_names=part_names,
            t=t.tolist(),
            internal_energy=ie.tolist(),
            kinetic_energy=ke.tolist(),
        )
        return md
    except Exception:
        return None


def _parse_rcforc(b) -> list[RcforcInterface]:
    try:
        import numpy as np
        t = b.read("rcforc", "time")
        ids = b.read("rcforc", "ids")
        side = b.read("rcforc", "side")
        legend = b.read("rcforc", "legend")
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
            s = int(side[i])
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
        legend = b.read("sleout", "legend")
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
