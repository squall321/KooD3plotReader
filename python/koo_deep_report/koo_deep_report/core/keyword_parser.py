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
    #: 읽지 못한 것들의 사유 (따라가지 않은 *INCLUDE, 해석하지 않은 *PART_ 변형 등).
    #: 비어 있지 않으면 parts/materials 가 덱 전체를 담고 있지 않다는 뜻이다.
    warnings: list[str] = field(default_factory=list)

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

    Detect fixed-col format on the ORIGINAL (rstripped) line, since
    pre-stripping leading whitespace can fuse columns whose left field
    has only a value at the right edge of its 10-char slot (e.g. "         1"
    followed by "2.7000E-09" would otherwise collapse into "12.7000E-09").
    """
    raw = line.rstrip("\n").rstrip()
    stripped = raw.strip()
    if not stripped:
        return [""] * n

    # 1. Comma-separated
    if "," in stripped:
        parts = stripped.split(",")
        return [p.strip() for p in parts[:n]] + [""] * max(0, n - len(parts))

    # 2. Fixed 10-col: detect by checking whether each 10-col slot in the RAW
    #    line is internally a single token (no embedded whitespace) — this
    #    catches LS-DYNA fixed format regardless of total line length.
    if len(raw) >= 20:
        looks_fixed = True
        n_slots = min(n, (len(raw) + 9) // 10)
        for i in range(n_slots):
            slot = raw[i * 10:(i + 1) * 10].strip()
            if slot and " " in slot:
                looks_fixed = False
                break
        if looks_fixed:
            fields = []
            for i in range(n):
                start = i * 10
                end = start + 10
                fields.append(raw[start:end].strip() if start < len(raw) else "")
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
# MAT card definitions: which card line / field index has SIGY, FAIL
# card = which data line (1-based), field = which column (0-based)
#
# MAT 종류마다 카드 배치가 다르다. MAT_024 배치를 전부에 갖다 쓰면
# 포아송비(015)·경화규칙 플래그(036)·Cowper-Symonds 계수(124)를 항복응력
# 으로, BETA(003)·EPSO(098)를 파단변형률로 읽는다. 아래 배치는
# LS-DYNA R16 키워드 매뉴얼 Vol.II 에서 확인한 것이다.
# ---------------------------------------------------------------------------
_MAT_SIGY_MAP: dict[int, tuple[int, int]] = {
    # MAT_NUMBER: (card_line, field_index) for SIGY
    3:   (1, 4),  # 003 card1: MID RO E PR SIGY ETAN BETA
    15:  (2, 0),  # 015 card1: MID RO G E PR DTF VP RATEOP / card2: A B N C ...
    18:  (2, 0),  # 018 card1: MID RO E PR K N SRC SRP / card2: SIGY VP EPSF
    24:  (1, 4),  # 024 card1: MID RO E PR SIGY ETAN FAIL TDEL
    98:  (2, 0),  # 098 card1: MID RO E PR VP / card2: A B N C PSFAIL ...
    123: (1, 4),  # 123 card1: MID RO E PR SIGY ETAN FAIL TDEL
    # 036(3-PARAMETER_BARLAT)·124(PLASTICITY_COMPRESSION_TENSION)는 스칼라
    # 항복응력이 없다 (경화규칙/하중곡선으로 준다) — 이웃 필드를 주워오지 않는다.
}

_MAT_FAIL_MAP: dict[int, tuple[int, int]] = {
    # MAT_NUMBER: (card_line, field_index) for FAIL (failure strain)
    3:   (2, 2),  # 003 card2: SRC SRP FS VP
    24:  (1, 6),  # 024 card1 field 6 = FAIL
    98:  (2, 4),  # 098 card2 field 4 = PSFAIL
    123: (1, 6),
    124: (1, 6),  # 124 card1: MID RO E PR C P FAIL TDEL
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
# *PART 의 OPTION 조합 — 어느 조합이든 '제목 줄 + PID SECID MID ...' 로 시작한다
# (R16 Vol.I *PART Card Summary). 세트는 다음 '*' 키워드 전까지 반복될 수 있다.
_PART_STD_RE = re.compile(
    r"^\*PART(_(INERTIA|REPOSITION|CONTACT|PRINT|ATTACHMENT_NODES|AVERAGED|FIELD|TITLE))*\s*$")
# *PART_COMPOSITE 는 카드 3 이 'PID ELFORM SHRF ...' 라 MID 열이 없다.
_PART_COMPOSITE_RE = re.compile(
    r"^\*PART_COMPOSITE(_(LONG|TSHELL|IGA_SHELL|CONTACT|TITLE))*\s*$")

_MAX_INCLUDE_DEPTH = 8


def parse_keyword_file(path: str | Path) -> KeywordData:
    """Parse LS-DYNA keyword file for *PART and *MAT_ sections.

    *INCLUDE 로 끌어온 파일도 따라간다 — 따라가지 않으면 그 파일의 파트가
    통째로 없는 것이 되어 이름도 설계기준도 붙지 않는다.
    """
    path = Path(path)
    data = KeywordData(source_path=str(path))
    _parse_into(path, data, seen=set(), depth=0)
    return data


def _parse_into(path: Path, data: KeywordData, seen: set[str], depth: int) -> None:
    """path 를 읽어 data 에 누적한다. *INCLUDE 는 재귀로 따라간다."""
    try:
        key = str(path.resolve())
    except OSError:
        key = str(path)
    if key in seen:
        return
    seen.add(key)

    if not path.exists():
        data.warnings.append(f"키워드 파일을 찾지 못했다: {path}")
        return

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        data.warnings.append(f"키워드 파일을 읽지 못했다: {path} ({e})")
        return

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

            if _PART_COMPOSITE_RE.match(upper):
                # 카드 3 에 MID 가 없다 — 이웃 열(SHRF)을 MID 로 읽지 않는다.
                i = _parse_part(lines, i + 1, data, multi=False, has_mid=False)
                continue

            if _PART_STD_RE.match(upper):
                # 옵션이 붙으면 세트마다 추가 카드가 따라온다. 그 장수는
                # 옵션마다 달라 추측할 수 없으므로 첫 세트만 읽는다.
                std = upper.rstrip() == "*PART"
                i = _parse_part(lines, i + 1, data, multi=std, has_mid=True)
                continue

            if upper.startswith("*PART"):
                data.warnings.append(
                    f"{line.split()[0]} 는 해석하지 않았다 — 이 블록의 파트는 빠져 있다")
                i += 1
                continue

            if upper.startswith("*INCLUDE"):
                i = _parse_include(lines, i, path, data, seen, depth)
                continue

            # *MAT_*  — capture both *MAT_RIGID_TITLE and *MAT_MOONEY-RIVLIN_RUBBER
            mat_match = re.match(r'\*MAT_([\w-]+)', upper)
            if mat_match:
                mat_name = mat_match.group(1)
                mat_number = _mat_name_to_number(mat_name, upper)
                i = _parse_mat(lines, i + 1, mat_name, mat_number, data)
                continue

        i += 1


def _parse_include(lines: list[str], i: int, src: Path, data: KeywordData,
                   seen: set[str], depth: int) -> int:
    """*INCLUDE 블록을 처리하고 다음 키워드 줄 위치를 돌려준다.

    옵션 없는 *INCLUDE 만 따라간다. *INCLUDE_TRANSFORM 은 ID 오프셋을
    함께 적용해야 하므로 여기서 따라가면 PID 가 어긋난다 — 사유만 남긴다.
    """
    header = lines[i].strip()
    plain = header.upper().rstrip() == "*INCLUDE"
    i += 1
    names: list[str] = []
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("*"):
            break
        if stripped and not stripped.startswith("$"):
            names.append(stripped)
        i += 1

    if not plain:
        data.warnings.append(
            f"{header.split()[0]} 는 따라가지 않았다 (ID 오프셋 미적용): "
            + ", ".join(names[:1] or ["<파일명 없음>"]))
        return i

    if depth >= _MAX_INCLUDE_DEPTH:
        data.warnings.append(f"*INCLUDE 중첩이 {_MAX_INCLUDE_DEPTH}단을 넘어 멈췄다: {src}")
        return i

    for name in names:
        cand = Path(name)
        target = cand if cand.is_absolute() else (src.parent / cand)
        if not target.exists():
            data.warnings.append(f"*INCLUDE 파일을 찾지 못했다: {name} (기준 {src.parent})")
            continue
        _parse_into(target, data, seen, depth + 1)
    return i


def _parse_part(lines: list[str], i: int, data: KeywordData,
                multi: bool = True, has_mid: bool = True) -> int:
    """Parse *PART section: (title line + data line) sets.

    LS-DYNA 는 다음 '*' 키워드 전까지 세트를 반복할 수 있다. 첫 세트만
    읽으면 나머지 파트는 이름도 설계기준도 없이 사라진다 (multi=True).
    옵션이 붙은 *PART_xxx 는 세트마다 추가 카드가 따라오고 그 장수가
    옵션마다 달라, 첫 세트만 읽고 나머지는 건너뛴다 (multi=False).
    """
    n = len(lines)
    while i < n:
        # Skip comment lines
        while i < n and lines[i].strip().startswith("$"):
            i += 1
        if i >= n or lines[i].strip().startswith("*"):
            break

        # Line 1: title/name
        title = lines[i].strip()
        i += 1

        # Skip comments
        while i < n and lines[i].strip().startswith("$"):
            i += 1
        if i >= n or lines[i].strip().startswith("*"):
            break

        # Line 2: PID, SECID, MID, EOSID, HGID, GRAV, ADPOPT, TMID
        #   (*PART_COMPOSITE: PID, ELFORM, SHRF, ... — MID 열이 없다)
        fields = _read_fields(lines[i], 8)
        pid = _to_int(fields[0])
        secid = _to_int(fields[1]) if has_mid else 0
        mid = _to_int(fields[2]) if has_mid else 0
        i += 1

        if pid > 0:
            data.parts[pid] = PartMaterialMap(pid=pid, name=title, secid=secid, mid=mid)

        if not multi:
            break

    return i


def _parse_mat(lines: list[str], i: int, mat_name: str, mat_number: int,
               data: KeywordData) -> int:
    """Parse *MAT_ section: read MID and key properties."""
    # Skip comments
    while i < len(lines) and lines[i].strip().startswith("$"):
        i += 1

    if i >= len(lines):
        return i

    # Normalize hyphens (MOONEY-RIVLIN → MOONEY_RIVLIN) for consistent storage
    mat_name = mat_name.replace("-", "_")

    # *MAT_XXX_TITLE has an extra title line before card 1. Detect any
    # non-numeric / non-comment leading line as a title and skip it.
    if mat_name.endswith("_TITLE"):
        # Strip the _TITLE suffix from the type name to match material number maps
        mat_name = mat_name[:-len("_TITLE")]
        # Skip the title line
        if i < len(lines) and not lines[i].lstrip().startswith(("$", "*")):
            i += 1
            while i < len(lines) and lines[i].strip().startswith("$"):
                i += 1

    if i >= len(lines):
        return i

    # 이 MAT 의 데이터 카드를 먼저 모은다. 카드 사이의 '$#' 주석 줄을 세면
    # 카드 2 를 주석에서 읽게 된다 (LS-PrePost 출력이 그렇다).
    cards = _collect_cards(lines, i, 4)
    if not cards:
        return i + 1

    def card_field(card_line: int, field_idx: int) -> float | None:
        if card_line - 1 >= len(cards):
            return None
        fields = _read_fields(cards[card_line - 1], 8)
        if field_idx >= len(fields):
            return None
        return _to_float(fields[field_idx])

    # Card 1: always starts with MID, RO, E, PR, ...
    card1 = _read_fields(cards[0], 8)
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
        v = card_field(*sigy_pos)
        if v is not None:
            mat.yield_stress = v

    # Read FAIL from known position
    fail_pos = _MAT_FAIL_MAP.get(mat_number)
    if fail_pos:
        v = card_field(*fail_pos)
        if v is not None:
            mat.failure_strain = v

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


def _collect_cards(lines: list[str], i: int, max_cards: int) -> list[str]:
    """i 부터 다음 키워드('*') 전까지의 데이터 카드를 최대 max_cards 개 모은다.

    '$' 주석 줄과 빈 줄은 카드로 세지 않는다.
    """
    cards: list[str] = []
    while i < len(lines) and len(cards) < max_cards:
        stripped = lines[i].strip()
        if stripped.startswith("*"):
            break
        if stripped and not stripped.startswith("$"):
            cards.append(lines[i])
        i += 1
    return cards


def _mat_name_to_number(name: str, full_line: str) -> int:
    """Map MAT type name to number. Handles both *MAT_024 and *MAT_PIECEWISE_LINEAR_PLASTICITY."""
    # Normalize hyphens to underscores (LS-DYNA accepts both, e.g. MOONEY-RIVLIN_RUBBER)
    name = name.replace("-", "_")
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
    """Find keyword file near d3plot and parse it for material data.

    후보 중 하나만 골라 읽으면 다중 파일 덱을 놓친다. 마스터 덱은 *INCLUDE
    몇 줄만 든 몇백 바이트짜리라, '크기 내림차순 + 첫 성공' 규칙으로는 결코
    닿지 못하고 수 MB 짜리 메시 파일에서 멈춘다 — 그러면 *MAT_ 카드가 통째로
    빠져 전 파트가 stress_source='none' 이 되고 안전율·경고색이 사라진다.
    후보를 모두 읽고 가장 많이 담은 것을 쓴다 (*INCLUDE 는 parse_keyword_file
    이 따라가므로, 마스터를 읽으면 메시·재료가 함께 들어온다).
    """
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

    # Sort by size descending (동점일 때 큰 파일이 이기도록 — 선택 자체는 아래 점수로 한다)
    candidates.sort(key=lambda p: -p.stat().st_size if p.exists() else 0)

    best: KeywordData | None = None
    best_score: tuple[int, int] = (-1, -1)
    seen_cand: set[str] = set()
    for cand in candidates:
        try:
            key = str(cand.resolve())
        except OSError:
            key = str(cand)
        if key in seen_cand:
            continue
        seen_cand.add(key)
        if not (cand.exists() and cand.stat().st_size > 100):
            continue
        result = parse_keyword_file(cand)
        if not (result.parts or result.materials):
            continue
        # 재료가 있는 쪽을 먼저 본다 — 파트만 있는 메시 파일은 설계기준을
        # 하나도 주지 못한다. 그 다음은 담은 양이 많은 쪽이다.
        score = (1 if result.materials else 0,
                 len(result.parts) + len(result.materials))
        if score > best_score:
            best, best_score = result, score

    if best is not None and not best.materials:
        # 재료 카드를 못 찾았다는 사실을 남긴다 — 조용히 지나가면 전 파트가
        # '기준 없음' 인 이유를 읽는 사람이 알 길이 없다.
        best.warnings.append(
            f"*MAT_ 카드를 찾지 못했다 ({best.source_path}) — 응력·변형률 "
            "기준이 없어 전 파트가 '기준 없음' 이 된다")
    return best
