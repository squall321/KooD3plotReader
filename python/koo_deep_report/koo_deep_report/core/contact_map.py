# LS-DYNA *CONTACT 카드에서 인터페이스→파트 매핑을 해석하는 파서
"""
contact_map.py — Resolve which parts each *CONTACT interface (CID) connects.

rcforc only records per-interface force time series and carries no part
mapping. This parser bridges that gap by reading the *CONTACT cards of a
keyword (.k) deck and resolving each interface's slave/master side down to a
concrete part (or an honestly-demoted pseudo node when it cannot).

Resolution priority (never invents parts — demotes honestly instead):
  1. SSTYP/MSTYP == 3  → SSID/MSID is a part ID (direct read),      conf 1.0
  2. SSTYP/MSTYP == 2  → *SET_PART: single member → that part,      conf 1.0
                         multiple members → kind="set"
  3. SSTYP/MSTYP == 0  → *SET_SEGMENT: segment nodes → element PID
                         majority vote. top share is confidence;
                         share < 0.9 → demote to kind="iface".
  4. SSTYP == 5 or SSID == 0 → single-surface / ALL → kind="all",   conf 1.0
  5. keyword absent / CID not found → both ends kind="iface",       conf 0.0

Limitations:
  - *INCLUDE files are NOT followed. Referenced sets/elements living in an
    included deck resolve as demotions (kind="iface"), never as an exception.
  - *ELEMENT_SOLID/SHELL connectivity is assumed single-line per element
    (standard 8-node hex / 4-node shell). Multi-line tet10 node lists are
    not stitched.
  - Only *CONTACT variants with the _ID option (explicit CID heading) are
    mapped; contacts numbered implicitly by order are noted, not mapped.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Return schema — consumed by the P3 energy-flow builder. DO NOT change shape.
# ---------------------------------------------------------------------------
@dataclass
class PartRef:
    kind: str                 # "part" | "set" | "all" | "iface"
    part_id: int | None       # real PID only when kind=="part", else None
    node_id: str              # graph node key: part→str(pid), set→"set:<sid>",
                              #                 all/iface→"iface:<cid>"
    name: str                 # display name


@dataclass
class ContactEndpoint:
    cid: int
    name: str                 # card NAME (or "Contact_<cid>")
    slave: PartRef
    master: PartRef
    confidence: float         # 1.0=direct part id, <1.0=vote share, 0.0=demoted


@dataclass
class ContactMap:
    endpoints: dict[int, ContactEndpoint] = field(default_factory=dict)
    note: str = ""


# ---------------------------------------------------------------------------
# Field readers
# ---------------------------------------------------------------------------
def _int_fields(line: str) -> list[int | None]:
    """Split a keyword data line into integer fields.

    Handles comma-separated and whitespace-separated (fixed 10-/8-col) forms.
    Non-numeric tokens (e.g. solver name "MECH") become None.
    """
    raw = line.strip()
    if not raw:
        return []
    toks = [t.strip() for t in raw.split(",")] if "," in raw else raw.split()
    out: list[int | None] = []
    for t in toks:
        if not t:
            out.append(None)
            continue
        try:
            out.append(int(float(t)))
        except ValueError:
            out.append(None)
    return out


def _parse_heading(line: str) -> tuple[int | None, str]:
    """Parse a CID/NAME heading line: leading integer CID, rest is the name.

    NAME may contain spaces (e.g. "Contact Region"), so only the first token
    is taken as the CID and everything after it is the name.
    """
    parts = line.split(None, 1)
    if not parts:
        return None, ""
    try:
        cid = int(float(parts[0]))
    except ValueError:
        return None, ""
    name = parts[1].strip() if len(parts) > 1 else ""
    return cid, name


def _is_comment(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("$")


def _skip_comments(lines: list[str], i: int) -> int:
    while i < len(lines) and (not lines[i].strip() or _is_comment(lines[i])):
        i += 1
    return i


# ---------------------------------------------------------------------------
# Raw contact record (pre-resolution)
# ---------------------------------------------------------------------------
@dataclass
class _RawContact:
    cid: int
    name: str
    ssid: int
    sstyp: int
    msid: int
    mstyp: int


# ---------------------------------------------------------------------------
# Pass 1 — parse *CONTACT, *SET_PART, *SET_SEGMENT (collect wanted nodes)
# ---------------------------------------------------------------------------
def _parse_contact(lines: list[str], i: int, keyword: str) -> tuple[_RawContact | None, int]:
    """Parse one *CONTACT block. Returns (raw, next_index).

    Only _ID variants (with a CID/NAME heading) are mapped; others return None.
    Consumes up through Card 1 (SSID MSID SSTYP MSTYP ...); the outer loop
    harmlessly skips remaining option cards until the next keyword.
    """
    has_id = keyword.upper().rstrip().endswith("_ID")
    if not has_id:
        return None, i

    # Heading card: CID + NAME
    i = _skip_comments(lines, i)
    if i >= len(lines):
        return None, i
    cid, name = _parse_heading(lines[i])
    i += 1
    if cid is None:
        return None, i

    # Card 1: SSID MSID SSTYP MSTYP SBOXID MBOXID SPR MPR
    i = _skip_comments(lines, i)
    if i >= len(lines):
        return None, i
    f = _int_fields(lines[i])
    i += 1

    def g(idx: int) -> int:
        return f[idx] if idx < len(f) and f[idx] is not None else 0

    if not name:
        name = f"Contact_{cid}"
    return _RawContact(cid=cid, name=name, ssid=g(0), sstyp=g(2),
                       msid=g(1), mstyp=g(3)), i


def _parse_set_part(lines: list[str], i: int, has_title: bool,
                    set_part: dict[int, list[int]],
                    set_part_title: dict[int, str]) -> int:
    """Parse *SET_PART[_LIST][_TITLE]: SID line then 8-per-line member PIDs."""
    title = ""
    i = _skip_comments(lines, i)
    if has_title:
        if i < len(lines):
            title = lines[i].strip()
            i += 1
        i = _skip_comments(lines, i)
    if i >= len(lines):
        return i
    # SID line
    sid_fields = _int_fields(lines[i])
    i += 1
    sid = sid_fields[0] if sid_fields and sid_fields[0] is not None else None
    # Member lines until next keyword
    members: list[int] = []
    while i < len(lines):
        s = lines[i]
        if s.lstrip().startswith("*"):
            break
        if s.strip() and not _is_comment(s):
            for v in _int_fields(s):
                if v is not None and v > 0:
                    members.append(v)
        i += 1
    if sid is not None:
        set_part[sid] = members
        set_part_title[sid] = title or f"PartSet_{sid}"
    return i


def _parse_set_segment(lines: list[str], i: int, has_title: bool,
                       seg_sets: dict[int, set[int]],
                       wanted: set[int]) -> int:
    """Parse *SET_SEGMENT[_TITLE]: SID line then segment rows (N1 N2 N3 N4)."""
    i = _skip_comments(lines, i)
    if has_title:
        if i < len(lines):
            i += 1  # title line
        i = _skip_comments(lines, i)
    if i >= len(lines):
        return i
    # SID line (first field = SID; rest are floats + solver string)
    sid_fields = _int_fields(lines[i])
    i += 1
    sid = sid_fields[0] if sid_fields and sid_fields[0] is not None else None
    nodes: set[int] = seg_sets.setdefault(sid, set()) if sid is not None else set()
    # Segment rows until next keyword
    while i < len(lines):
        s = lines[i]
        if s.lstrip().startswith("*"):
            break
        if s.strip() and not _is_comment(s):
            f = _int_fields(s)
            for v in f[:4]:  # N1..N4
                if v is not None and v > 0:
                    nodes.add(v)
                    wanted.add(v)
        i += 1
    return i


# ---------------------------------------------------------------------------
# Pass 2 — stream *ELEMENT_SOLID / *ELEMENT_SHELL, build node→PID for wanted
# ---------------------------------------------------------------------------
def _scan_elements(lines: list[str], wanted: set[int]) -> dict[int, int]:
    """One streaming pass over element cards → {node: pid} for wanted nodes."""
    node2pid: dict[int, int] = {}
    i = 0
    n = len(lines)
    in_element = False
    while i < n:
        s = lines[i]
        ls = s.lstrip()
        if ls.startswith("*"):
            up = ls.upper()
            in_element = up.startswith("*ELEMENT_SOLID") or up.startswith("*ELEMENT_SHELL")
            i += 1
            continue
        if in_element and s.strip() and not _is_comment(s):
            f = _int_fields(s)
            # EID(0) PID(1) N1..
            if len(f) >= 3 and f[1] is not None:
                pid = f[1]
                for v in f[2:]:
                    if v is not None and v in wanted:
                        node2pid.setdefault(v, pid)
        i += 1
    return node2pid


# ---------------------------------------------------------------------------
# Side resolution
# ---------------------------------------------------------------------------
def _resolve_side(styp: int, sid: int, cid: int, card_name: str,
                  part_names: dict[int, str],
                  set_part: dict[int, list[int]],
                  set_part_title: dict[int, str],
                  seg_vote: dict[int, Counter]) -> tuple[PartRef, float]:
    """Resolve one contact side to a PartRef + side confidence."""
    def part_ref(pid: int, conf: float) -> tuple[PartRef, float]:
        return PartRef(kind="part", part_id=pid, node_id=str(pid),
                       name=part_names.get(pid) or f"Part_{pid}"), conf

    def iface_ref(conf: float) -> tuple[PartRef, float]:
        return PartRef(kind="iface", part_id=None, node_id=f"iface:{cid}",
                       name=card_name), conf

    # Rule 1: part id direct
    if styp == 3:
        return part_ref(sid, 1.0)

    # Rule 2: *SET_PART
    if styp == 2:
        members = set_part.get(sid)
        if members is None:
            return iface_ref(0.0)          # set not found (e.g. *INCLUDE) → demote
        if len(members) == 1:
            return part_ref(members[0], 1.0)
        title = set_part_title.get(sid) or f"PartSet_{sid}"
        return PartRef(kind="set", part_id=None, node_id=f"set:{sid}",
                       name=title), 1.0

    # Rule 4: single surface / ALL
    if styp == 5 or sid == 0:
        return PartRef(kind="all", part_id=None, node_id=f"iface:{cid}",
                       name=card_name), 1.0

    # Rule 3: *SET_SEGMENT majority vote
    if styp == 0:
        vote = seg_vote.get(sid)
        if not vote:
            return iface_ref(0.0)          # no votes (guard-skipped / empty) → demote
        top_pid, top_count = vote.most_common(1)[0]
        total = sum(vote.values())
        share = top_count / total if total else 0.0
        if share >= 0.9:
            return part_ref(top_pid, share)
        return iface_ref(share)

    # Unknown SSTYP → honest demotion
    return iface_ref(0.0)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
_WANTED_NODE_LIMIT = 2_000_000


def parse_contact_map(kfile: Path, part_names: dict[int, str] | None = None) -> ContactMap:
    """Parse a keyword deck's *CONTACT cards into a CID → part mapping.

    Args:
        kfile: path to the LS-DYNA keyword (.k) file.
        part_names: {pid: name} already parsed by the caller's keyword_parser.
                    Used for PartRef.name; falls back to "Part_<pid>" when None.

    Returns:
        ContactMap with one ContactEndpoint per resolvable CID. `note` records
        demotions / limitations (*INCLUDE untracked, giant-deck guard, etc.).
    """
    part_names = part_names or {}
    kfile = Path(kfile)

    if not kfile.exists():
        return ContactMap(note="keyword file not found; interfaces unresolved")

    lines = kfile.read_text(encoding="utf-8", errors="replace").splitlines()

    contacts: list[_RawContact] = []
    set_part: dict[int, list[int]] = {}
    set_part_title: dict[int, str] = {}
    seg_sets: dict[int, set[int]] = {}
    wanted: set[int] = set()
    non_id_contacts = 0

    # --- Pass 1: contacts + sets ---
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        ls = line.lstrip()
        if not ls.startswith("*"):
            i += 1
            continue
        up = ls.upper().rstrip()

        if up.startswith("*CONTACT"):
            raw, i = _parse_contact(lines, i + 1, up)
            if raw is not None:
                contacts.append(raw)
            elif not up.endswith("_ID"):
                non_id_contacts += 1
            continue

        if up.startswith("*SET_PART"):
            has_title = "_TITLE" in up
            i = _parse_set_part(lines, i + 1, has_title, set_part, set_part_title)
            continue

        if up.startswith("*SET_SEGMENT") and not up.startswith("*SET_SEGMENT_GENERAL"):
            has_title = "_TITLE" in up
            i = _parse_set_segment(lines, i + 1, has_title, seg_sets, wanted)
            continue

        i += 1

    # --- Pass 2: element scan + majority vote (guarded) ---
    seg_vote: dict[int, Counter] = {}
    guard_hit = len(wanted) > _WANTED_NODE_LIMIT
    if wanted and not guard_hit:
        node2pid = _scan_elements(lines, wanted)
        for sid, nodes in seg_sets.items():
            c: Counter = Counter()
            for nd in nodes:
                pid = node2pid.get(nd)
                if pid is not None:
                    c[pid] += 1
            if c:
                seg_vote[sid] = c

    # --- Build endpoints ---
    cmap = ContactMap()
    demoted = 0
    low_share = 0
    for raw in contacts:
        slave, sc = _resolve_side(raw.sstyp, raw.ssid, raw.cid, raw.name,
                                  part_names, set_part, set_part_title, seg_vote)
        master, mc = _resolve_side(raw.mstyp, raw.msid, raw.cid, raw.name,
                                   part_names, set_part, set_part_title, seg_vote)
        conf = min(sc, mc)
        cmap.endpoints[raw.cid] = ContactEndpoint(
            cid=raw.cid, name=raw.name, slave=slave, master=master, confidence=conf)
        if slave.kind == "iface" or master.kind == "iface":
            demoted += 1
            if 0.0 < conf < 0.9:
                low_share += 1

    # --- Note ---
    notes = ["*INCLUDE not tracked"]
    if guard_hit:
        notes.append(f"segment-set nodes ({len(wanted)}) exceeded "
                     f"{_WANTED_NODE_LIMIT} guard — majority vote skipped, "
                     f"all *SET_SEGMENT sides demoted")
    if demoted:
        notes.append(f"{demoted} CID(s) demoted to pseudo-node "
                     f"({low_share} by low vote share)")
    if non_id_contacts:
        notes.append(f"{non_id_contacts} non-_ID *CONTACT card(s) skipped "
                     f"(no explicit CID)")
    cmap.note = "; ".join(notes)
    return cmap
