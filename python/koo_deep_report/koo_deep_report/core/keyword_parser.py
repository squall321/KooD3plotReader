"""
keyword_parser.py — Parse LS-DYNA keyword files for material properties.

Extracts:
  - *PART → PID, SECID, MID mapping
  - *MAT_* → yield stress (SIGY), failure strain (FAIL)
  - Builds per-part design criteria (stress limit, strain limit)

Supports fixed-width (10-col) and comma-separated keyword formats.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class MaterialInfo:
    """Material properties extracted from *MAT_ card."""
    mid: int
    mat_type: str = ""           # e.g. "PIECEWISE_LINEAR_PLASTICITY", "ELASTIC"
    mat_number: int = 0          # e.g. 24, 1, 3
    density: float = 0.0         # RO (kg/mm³ or t/mm³)
    youngs_modulus: float = 0.0  # E (MPa)
    poissons_ratio: float = 0.0  # PR
    yield_stress: float = 0.0    # SIGY (MPa) — 0 means not defined
    failure_strain: float = 0.0  # FAIL — 0 means not defined
    tangent_modulus: float = 0.0 # ETAN


@dataclass
class PartMaterialMap:
    """Part ID → Section ID, Material ID mapping from *PART."""
    pid: int
    name: str = ""
    secid: int = 0
    mid: int = 0


@dataclass
class DesignCriteria:
    """Per-part design criteria for warning evaluation."""
    part_id: int
    part_name: str = ""
    mat_type: str = ""
    # Stress-based criterion
    stress_limit: float = 0.0      # MPa (from SIGY or manual override)
    stress_source: str = "none"    # "mat_card" | "manual" | "none"
    # Strain-based criterion
    strain_limit: float = 0.002    # default 0.2% (0.002) if not defined
    strain_source: str = "default" # "mat_card" | "manual" | "default"

    @property
    def has_stress_limit(self) -> bool:
        return self.stress_limit > 0

    @property
    def has_strain_limit(self) -> bool:
        return self.strain_limit > 0


@dataclass
class KeywordData:
    """All parsed data from keyword file."""
    parts: dict[int, PartMaterialMap] = field(default_factory=dict)   # PID → PartMaterialMap
    materials: dict[int, MaterialInfo] = field(default_factory=dict)  # MID → MaterialInfo
    source_path: str = ""

    def get_design_criteria(
        self,
        overrides: dict[int, dict] | None = None,
        material_overrides: dict[str, dict] | None = None,
    ) -> dict[int, DesignCriteria]:
        """Build per-part design criteria from material data + optional overrides.

        Priority (highest first):
          1. Per-part overrides (keyed by PID)
          2. Per-material overrides (keyed by MID number or MAT type name)
          3. Keyword auto-extraction (*MAT_ card SIGY/FAIL)
          4. Global fallback (handled by caller)

        Args:
            overrides: {part_id: {"stress_limit": float, "strain_limit": float}}
            material_overrides: {key: {"stress_limit": float, "strain_limit": float}}
                where key is MID (str of int) or MAT type name (e.g. "ELASTIC", "24")

        Returns:
            {part_id: DesignCriteria}
        """
        overrides = overrides or {}
        material_overrides = material_overrides or {}
        result: dict[int, DesignCriteria] = {}

        for pid, part in self.parts.items():
            mat = self.materials.get(part.mid)
            dc = DesignCriteria(part_id=pid, part_name=part.name)

            if mat:
                dc.mat_type = mat.mat_type

                # Stress limit from yield stress
                if mat.yield_stress > 0:
                    dc.stress_limit = mat.yield_stress
                    dc.stress_source = "mat_card"

                # Strain limit from failure strain
                if mat.failure_strain > 0:
                    dc.strain_limit = mat.failure_strain
                    dc.strain_source = "mat_card"
                else:
                    # Default: 0.2% for metals, keep default for others
                    dc.strain_limit = 0.002
                    dc.strain_source = "default"
            else:
                # No material info — use defaults
                dc.strain_limit = 0.002
                dc.strain_source = "default"

            # Apply per-material overrides (by MID number or MAT type name)
            if mat and material_overrides:
                mat_ov = (
                    material_overrides.get(str(part.mid))            # by MID number
                    or material_overrides.get(str(mat.mat_number))   # by MAT number (e.g. "24")
                    or material_overrides.get(mat.mat_type)          # by MAT type name (e.g. "PIECEWISE_LINEAR_PLASTICITY")
                )
                if mat_ov:
                    if "stress_limit" in mat_ov and mat_ov["stress_limit"] > 0:
                        dc.stress_limit = mat_ov["stress_limit"]
                        dc.stress_source = "material_override"
                    if "strain_limit" in mat_ov and mat_ov["strain_limit"] > 0:
                        dc.strain_limit = mat_ov["strain_limit"]
                        dc.strain_source = "material_override"

            # Apply per-part overrides (highest priority)
            if pid in overrides:
                ov = overrides[pid]
                if "stress_limit" in ov and ov["stress_limit"] > 0:
                    dc.stress_limit = ov["stress_limit"]
                    dc.stress_source = "manual"
                if "strain_limit" in ov and ov["strain_limit"] > 0:
                    dc.strain_limit = ov["strain_limit"]
                    dc.strain_source = "manual"

            result[pid] = dc

        return result


# ---------------------------------------------------------------------------
# Keyword file field reader
# ---------------------------------------------------------------------------
def _read_fields(line: str, n: int = 8) -> list[str]:
    """Read up to n fields from a keyword line.

    Supports:
      - Comma-separated: "1, 7.85e-9, 210000, 0.3, 250"
      - Fixed 10-col: "         1    7.85-9    210000       0.3       250"
      - Space-separated fallback: "1 7.85E-09 210000 0.3 250"
    """
    stripped = line.strip()
    if not stripped:
        return [""] * n

    # 1. Comma-separated
    if "," in stripped:
        parts = stripped.split(",")
        return [p.strip() for p in parts[:n]] + [""] * max(0, n - len(parts))

    # 2. Fixed 10-col: check if first 10-char field is a single token
    if len(stripped) >= 70:
        first_field = stripped[:10].strip()
        if first_field and " " not in first_field:
            fields = []
            for i in range(n):
                start = i * 10
                end = start + 10
                if start < len(stripped):
                    fields.append(stripped[start:end].strip())
                else:
                    fields.append("")
            return fields

    # 3. Space-separated fallback
    parts = stripped.split()
    return [p for p in parts[:n]] + [""] * max(0, n - len(parts))


def _to_float(s: str, default: float = 0.0) -> float:
    """Convert string to float, handling empty and scientific notation."""
    s = s.strip()
    if not s:
        return default
    try:
        # Handle LS-DYNA notation like "2.1+5" → "2.1e+5"
        s = re.sub(r'(\d)([+-])(\d)', r'\1e\2\3', s)
        return float(s)
    except ValueError:
        return default


def _to_int(s: str, default: int = 0) -> int:
    s = s.strip()
    if not s:
        return default
    try:
        return int(float(s))
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# MAT card definitions: which field index has SIGY, FAIL
# Each entry: (mat_number, mat_name, sigy_card, sigy_field, fail_card, fail_field)
# card = which data line (1-based), field = which column (0-based)
# ---------------------------------------------------------------------------
_MAT_SIGY_MAP: dict[int, tuple[int, int]] = {
    # MAT_NUMBER: (card_line, field_index) for SIGY
    # Card 1 layout: MID(0) RO(1) E(2) PR(3) SIGY(4) ETAN(5) FAIL(6) TDEL(7)
    3:   (1, 4),  # MAT_PLASTIC_KINEMATIC: Card 1, field 4
    15:  (1, 4),  # MAT_JOHNSON_COOK: Card 1, field 4 (A≈SIGY)
    18:  (1, 4),  # MAT_POWER_LAW_PLASTICITY: Card 1, field 4 (K)
    24:  (1, 4),  # MAT_PIECEWISE_LINEAR_PLASTICITY: Card 1, field 4
    36:  (1, 4),  # MAT_3-PARAMETER_BARLAT: Card 1, field 4
    98:  (1, 4),  # MAT_SIMPLIFIED_JOHNSON_COOK: Card 1, field 4
    123: (1, 4),  # MAT_MODIFIED_PIECEWISE_LINEAR_PLASTICITY
    124: (1, 4),  # MAT_PLASTICITY_COMPRESSION_TENSION
    # For elastic materials, there's no yield
}

_MAT_FAIL_MAP: dict[int, tuple[int, int]] = {
    # MAT_NUMBER: (card_line, field_index) for FAIL (failure strain)
    # Card 1 layout: MID(0) RO(1) E(2) PR(3) SIGY(4) ETAN(5) FAIL(6) TDEL(7)
    3:   (1, 6),  # MAT_PLASTIC_KINEMATIC: Card 1, field 6
    24:  (1, 6),  # MAT_PIECEWISE_LINEAR_PLASTICITY: Card 1, field 6
    98:  (1, 6),  # MAT_SIMPLIFIED_JOHNSON_COOK: Card 1, field 6
    123: (1, 6),
    124: (1, 6),
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def parse_keyword_file(path: str | Path) -> KeywordData:
    """Parse LS-DYNA keyword file for *PART and *MAT_ sections."""
    path = Path(path)
    data = KeywordData(source_path=str(path))

    if not path.exists():
        return data

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip comments and empty lines
        if not line or line.startswith("$"):
            i += 1
            continue

        # Detect keyword cards
        if line.startswith("*"):
            upper = line.upper()

            # *PART (not *PART_INERTIA etc.)
            if upper.startswith("*PART") and not upper.startswith("*PART_"):
                i = _parse_part(lines, i + 1, data)
                continue

            # *MAT_*
            mat_match = re.match(r'\*MAT_(\w+)', upper)
            if mat_match:
                mat_name = mat_match.group(1)
                mat_number = _mat_name_to_number(mat_name, upper)
                i = _parse_mat(lines, i + 1, mat_name, mat_number, data)
                continue

        i += 1

    return data


def _parse_part(lines: list[str], i: int, data: KeywordData) -> int:
    """Parse *PART section: title line + data line (PID, SECID, MID, ...)."""
    # Skip comment lines
    while i < len(lines) and lines[i].strip().startswith("$"):
        i += 1

    if i >= len(lines):
        return i

    # Line 1: title/name
    title = lines[i].strip()
    i += 1

    # Skip comments
    while i < len(lines) and lines[i].strip().startswith("$"):
        i += 1

    if i >= len(lines):
        return i

    # Line 2: PID, SECID, MID, EOSID, HGID, GRAV, ADPOPT, TMID
    fields = _read_fields(lines[i], 8)
    pid = _to_int(fields[0])
    secid = _to_int(fields[1])
    mid = _to_int(fields[2])

    if pid > 0:
        data.parts[pid] = PartMaterialMap(pid=pid, name=title, secid=secid, mid=mid)

    return i + 1


def _parse_mat(lines: list[str], i: int, mat_name: str, mat_number: int,
               data: KeywordData) -> int:
    """Parse *MAT_ section: read MID and key properties."""
    # Skip comments and title lines
    while i < len(lines) and lines[i].strip().startswith("$"):
        i += 1

    if i >= len(lines):
        return i

    # Card 1: always starts with MID, RO, E, PR, ...
    # (some MATs have a title line, but most don't — the first non-comment line is card 1)
    card1 = _read_fields(lines[i], 8)
    mid = _to_int(card1[0])

    if mid <= 0:
        return i + 1

    mat = MaterialInfo(
        mid=mid,
        mat_type=mat_name,
        mat_number=mat_number,
        density=_to_float(card1[1]),
        youngs_modulus=_to_float(card1[2]),
        poissons_ratio=_to_float(card1[3]),
    )

    # Read SIGY from known position
    sigy_pos = _MAT_SIGY_MAP.get(mat_number)
    if sigy_pos:
        card_line, field_idx = sigy_pos
        if card_line == 1:
            if field_idx < len(card1):
                mat.yield_stress = _to_float(card1[field_idx])
        else:
            # Need to read additional card lines
            target_i = i + card_line - 1
            if target_i < len(lines):
                card_n = _read_fields(lines[target_i], 8)
                if field_idx < len(card_n):
                    mat.yield_stress = _to_float(card_n[field_idx])

    # Read FAIL from known position
    fail_pos = _MAT_FAIL_MAP.get(mat_number)
    if fail_pos:
        card_line, field_idx = fail_pos
        if card_line == 1:
            if field_idx < len(card1):
                mat.failure_strain = _to_float(card1[field_idx])
        else:
            target_i = i + card_line - 1
            if target_i < len(lines):
                card_n = _read_fields(lines[target_i], 8)
                if field_idx < len(card_n):
                    mat.failure_strain = _to_float(card_n[field_idx])

    # Read ETAN if present (field 5 for most plasticity models)
    if mat_number in (3, 24, 98, 123) and len(card1) > 5:
        mat.tangent_modulus = _to_float(card1[5])

    data.materials[mid] = mat

    # Advance past remaining card lines for this MAT
    # Heuristic: skip until next keyword or end
    i += 1
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("*"):
            break
        i += 1

    return i


def _mat_name_to_number(name: str, full_line: str) -> int:
    """Map MAT type name to number. Handles both *MAT_024 and *MAT_PIECEWISE_LINEAR_PLASTICITY."""
    # Try direct number (e.g. *MAT_024)
    m = re.match(r'^0*(\d+)$', name)
    if m:
        return int(m.group(1))

    # Name-based mapping
    _name_map = {
        "ELASTIC": 1,
        "ORTHOTROPIC_ELASTIC": 2,
        "PLASTIC_KINEMATIC": 3,
        "ELASTIC_PLASTIC_THERMAL": 4,
        "SOIL_AND_FOAM": 5,
        "VISCOELASTIC": 6,
        "BLATZ_KO_RUBBER": 7,
        "HIGH_EXPLOSIVE_BURN": 8,
        "NULL": 9,
        "ELASTIC_PLASTIC_HYDRO": 10,
        "JOHNSON_COOK": 15,
        "POWER_LAW_PLASTICITY": 18,
        "RIGID": 20,
        "PIECEWISE_LINEAR_PLASTICITY": 24,
        "HONEYCOMB": 26,
        "MOONEY_RIVLIN_RUBBER": 27,
        "RESULTANT_PLASTICITY": 28,
        "FRAZER_NASH_RUBBER": 31,
        "LAMINATED_GLASS": 32,
        "BARLAT_ANISOTROPIC_PLASTICITY": 33,
        "FABRIC": 34,
        "3_PARAMETER_BARLAT": 36,
        "THREE_PARAMETER_BARLAT": 36,
        "TRANSVERSELY_ANISOTROPIC_ELASTIC_PLASTIC": 37,
        "BLATZ_KO_FOAM": 38,
        "OGDEN_RUBBER": 77,
        "HYSTERETIC_SOIL": 79,
        "SPOTWELD": 100,
        "SIMPLIFIED_JOHNSON_COOK": 98,
        "MODIFIED_PIECEWISE_LINEAR_PLASTICITY": 123,
        "PLASTICITY_COMPRESSION_TENSION": 124,
        "COMPOSITE_DAMAGE": 22,
        "ENHANCED_COMPOSITE_DAMAGE": 54,
        "LAMINATED_COMPOSITE_FABRIC": 58,
    }

    # Remove common prefixes/suffixes
    clean = name.replace("_TITLE", "").replace("TITLE", "")
    return _name_map.get(clean, 0)


# ---------------------------------------------------------------------------
# Convenience: find and parse keyword file near d3plot
# ---------------------------------------------------------------------------
def find_and_parse_keyword(d3plot_path: str | Path) -> KeywordData | None:
    """Find keyword file near d3plot and parse it for material data."""
    d3plot = Path(d3plot_path)
    if d3plot.is_file():
        search_dir = d3plot.parent
    else:
        search_dir = d3plot

    # Search for keyword files
    extensions = [".k", ".key", ".dyn", ".K", ".KEY", ".DYN"]
    candidates: list[Path] = []

    for ext in extensions:
        candidates.extend(search_dir.glob(f"*{ext}"))

    # Also check parent directory
    if search_dir.parent != search_dir:
        for ext in extensions:
            candidates.extend(search_dir.parent.glob(f"*{ext}"))

    # Prefer main.k, input.k, model.k
    preferred = ["main", "input", "model"]
    candidates.sort(key=lambda p: (
        0 if p.stem.lower() in preferred else 1,
        p.stat().st_size  # smaller files less likely to be the main keyword
    ))

    # Sort by size descending (main keyword file is usually the largest)
    candidates.sort(key=lambda p: -p.stat().st_size if p.exists() else 0)

    for cand in candidates:
        if cand.exists() and cand.stat().st_size > 100:
            result = parse_keyword_file(cand)
            if result.parts or result.materials:
                return result

    return None
