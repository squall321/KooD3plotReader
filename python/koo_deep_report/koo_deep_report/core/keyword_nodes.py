# LS-DYNA 키워드 덱에서 *NODE 좌표를 읽고 원본↔런 덱 좌표 변환을 추정하는 모듈
"""키워드 덱 노드 리더 + 원본↔런 덱 좌표 정합.

**왜 이 모듈이 있나 (A-6).**
KMM 이 DropSet 을 만들 때 모델을 평행이동한다. 결과(d3plot) 좌표는 런 덱
(`DropSet.k`) 좌표계라, 원본 도면과 그냥 비교하면 위치가 통째로 어긋난다. 지금까지
매번 파트 중심을 손으로 대조해 역추적했다.

KMM 은 **노드 ID 를 보존**한다(실측: 원본 `MinimumModel.k` 과 `DropSet.k` 의
노드 11946 이 같은 점). 그래서 파트 중심을 만들 필요 없이 `*NODE` 만 읽어
**같은 ID 끼리** 대응시키면 수천 쌍으로 강체 변환을 추정할 수 있다.

**설계 규칙.** 예외를 던지지 않는다. 읽지 못한 줄·파일은 사유를 남긴다.
형식을 추측해 읽다 틀리면 **잔차가 커져 드러나게** 둔다 — 잔차 판정은
`coordinate_transform.residual_verdict` 가 한다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .coordinate_transform import RigidTransform, estimate_transform

INCLUDE_DEPTH = 8

#: *NODE 고정폭 배치 (NID, X, Y, Z). 접미사에 따라 폭이 다르다.
#:   *NODE      → I8,  3×E16
#:   *NODE %    → I10, 3×E16   (큰 ID 용)
#:   *NODE +    → I20, 3×E20   (long format)
_WIDTHS = {"": (8, 16, 16, 16), "%": (10, 16, 16, 16), "+": (20, 20, 20, 20)}


@dataclass
class NodeTable:
    nodes: dict = field(default_factory=dict)     #: {nid: (x, y, z)}
    #: `*PART` 의 PID 집합. 런 덱에만 있는 파트(전처리가 붙인 바닥·벽)를 가려내는 데
    #: 쓴다 — 그런 파트에는 원본 도면 좌표가 의미가 없다.
    parts: set = field(default_factory=set)
    files: list = field(default_factory=list)     #: 실제로 읽은 파일
    bad_lines: int = 0                            #: 해석하지 못한 *NODE 데이터 줄
    notes: list = field(default_factory=list)

    @property
    def note(self) -> str:
        return " / ".join(self.notes)


def _parse_node_line(line: str, suffix: str):
    """(nid, x, y, z) 또는 None. 쉼표 → 자유형식, 아니면 고정폭, 실패하면 공백 분리."""
    s = line.rstrip("\r\n")
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
    else:
        w = _WIDTHS.get(suffix, _WIDTHS[""])
        parts, pos = [], 0
        for width in w:
            parts.append(s[pos:pos + width].strip())
            pos += width
    try:
        return int(float(parts[0])), float(parts[1]), float(parts[2]), float(parts[3])
    except (ValueError, IndexError):
        pass
    # 고정폭이 맞지 않는 덱(공백 구분으로 쓴 것) — 토큰 4개면 받아 준다
    toks = s.split()
    if len(toks) >= 4:
        try:
            return int(float(toks[0])), float(toks[1]), float(toks[2]), float(toks[3])
        except ValueError:
            return None
    return None


def read_nodes(path, follow_includes: bool = True) -> NodeTable:
    """덱의 *NODE 를 읽는다. *INCLUDE 를 따라간다(깊이 8, 순환 방지)."""
    nt = NodeTable()
    seen: set = set()

    def walk(p: Path, depth: int) -> None:
        try:
            rp = str(p.resolve())
        except (OSError, RuntimeError):
            nt.notes.append(f"경로를 해석하지 못했습니다: {p}")
            return
        if rp in seen:
            return
        if depth > INCLUDE_DEPTH:
            nt.notes.append(f"*INCLUDE 깊이 {INCLUDE_DEPTH} 초과: {p}")
            return
        seen.add(rp)
        if not p.is_file():
            nt.notes.append(f"파일이 없습니다: {p}")
            return
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            nt.notes.append(f"읽지 못했습니다 ({type(e).__name__}): {p}")
            return
        nt.files.append(str(p))

        mode = None          # "node" | "include" | None
        suffix = ""
        for raw in text.splitlines():
            line = raw.rstrip("\r")
            st = line.strip()
            if not st or st.startswith("$"):
                continue
            if st.startswith("*"):
                kw = st.split()[0].upper()
                tail = st[len(kw):].strip()
                if kw == "*NODE":
                    mode, suffix = "node", (tail[:1] if tail[:1] in ("%", "+") else "")
                elif kw == "*PART":
                    mode = "part"
                elif kw.startswith("*INCLUDE") and follow_includes \
                        and kw in ("*INCLUDE", "*INCLUDE_PATH_RELATIVE"):
                    mode = "include"
                else:
                    mode = None
                continue
            if mode == "node":
                r = _parse_node_line(line, suffix)
                if r is None:
                    nt.bad_lines += 1
                else:
                    nt.nodes[r[0]] = (r[1], r[2], r[3])
            elif mode == "part":
                # 블록 안에는 (제목 카드, 숫자 카드) 쌍이 반복된다. 제목은 텍스트이거나
                # 비어 있을 수 있으므로, **숫자가 2개 이상인 줄**을 PID 카드로 본다.
                toks = line.replace(",", " ").split()
                nums = 0
                for tk in toks[:3]:
                    try:
                        float(tk)
                        nums += 1
                    except ValueError:
                        break
                if nums >= 2:
                    try:
                        nt.parts.add(int(float(toks[0])))
                    except ValueError:
                        pass
            elif mode == "include":
                inc = Path(st)
                if not inc.is_absolute():
                    inc = p.parent / inc
                walk(inc, depth + 1)

    try:
        walk(Path(path), 0)
    except TypeError:
        nt.notes.append("경로를 해석하지 못했습니다")
    if nt.bad_lines:
        nt.notes.append(f"*NODE 줄 {nt.bad_lines}개를 해석하지 못했습니다")
    if not nt.nodes and not nt.notes:
        nt.notes.append("*NODE 가 없습니다")
    return nt


def find_scenario_model(test_dir):
    """캠페인이 참조하는 **원본** 모델 파일. 없으면 None.

    koo_sphere_report 의 `_scenario_model_file` 과 같은 규칙이다 —
    runner_config.json 이 1순위, 그다음 *scenario*.json, 그 밖의 *.json 에서
    `model_file` 키를 (최상위 또는 세 단계 안쪽까지) 찾는다.
    """
    try:
        base = Path(test_dir)
    except TypeError:
        return None
    if not base.is_dir():
        return None
    cands = [base / "runner_config.json"] + sorted(base.glob("*scenario*.json")) + \
        sorted(base.glob("*.json"))
    seen = set()
    for cf in cands:
        if cf in seen or not cf.is_file():
            continue
        seen.add(cf)
        try:
            d = json.loads(cf.read_text(encoding="utf-8"))
        except (ValueError, OSError, UnicodeDecodeError):
            continue

        def _find(o, depth=0):
            if isinstance(o, dict):
                if isinstance(o.get("model_file"), str):
                    return o["model_file"]
                if depth < 3:
                    for v in o.values():
                        r = _find(v, depth + 1)
                        if r:
                            return r
            return None

        mf = _find(d)
        if not mf:
            continue
        mp = Path(mf)
        if not mp.is_absolute():
            mp = base / mp
        if mp.is_file():
            return mp
    return None


def find_run_deck(run_dir):
    """런 폴더의 솔버 입력 덱. `DropSet.k` 가 1순위.

    없으면 *.k/*.key/*.dyn 이 **하나뿐일 때만** 쓴다. 여러 개면 None —
    어느 것이 솔버 입력인지 추측하면 엉뚱한 덱을 문다.
    """
    try:
        rd = Path(run_dir)
    except TypeError:
        return None
    if not rd.is_dir():
        return None
    ds = rd / "DropSet.k"
    if ds.is_file():
        return ds
    decks = [p for ext in ("*.k", "*.key", "*.dyn") for p in rd.glob(ext) if p.is_file()]
    return decks[0] if len(decks) == 1 else None


def deck_transform(source_deck, run_deck, source_nodes: NodeTable | None = None,
                   max_pairs: int = 20000) -> tuple:
    """원본 덱 → 런 덱 좌표 변환을 노드 ID 대응으로 추정한다.

    Returns:
        (RigidTransform, 사유 문자열). 변환이 뜻하는 것은 `run = R·source + t`.

    `max_pairs` 를 넘으면 ID 순으로 **고르게** 추려 쓴다 (앞쪽만 자르면 한 파트에
    몰린다). 원본 노드는 캠페인 안에서 같으므로 `source_nodes` 로 한 번만 읽어
    넘길 수 있다.
    """
    src = source_nodes if isinstance(source_nodes, NodeTable) else read_nodes(source_deck)
    run = read_nodes(run_deck)
    notes = [n for n in (src.note, run.note) if n]
    common = sorted(set(src.nodes) & set(run.nodes))
    if not common:
        tr = RigidTransform(note="원본과 런 덱에 공통 노드 ID 가 없습니다 "
                                 "(전처리가 노드를 재번호했을 수 있습니다)")
        return tr, " / ".join(notes + [tr.note])
    try:
        mp = max(3, int(max_pairs))
    except (TypeError, ValueError):
        mp = 20000
    if len(common) > mp:
        step = len(common) / mp
        common = [common[int(i * step)] for i in range(mp)]
    tr = estimate_transform([src.nodes[i] for i in common],
                            [run.nodes[i] for i in common])
    return tr, " / ".join(notes)
