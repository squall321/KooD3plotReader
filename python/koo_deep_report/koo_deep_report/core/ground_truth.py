# 시험 불량 데이터(ground truth)를 읽어 시뮬 결과와 정합성을 계산하는 모듈
"""시험 불량 데이터 ↔ 시뮬레이션 정합.

**왜 이 모듈이 있나.**
후처리는 시뮬만 본다 — 정합성 계산 자체가 없었다. 2026-09 검증에서
`crack_locations.tsv` / `defect_parts.tsv` / `experiment_matrix.tsv` 를 전부
손으로 다뤘다. 스키마가 없으면 매번 다른 모양이 되고, 매번 다시 맞춰야 한다.

**스키마 (TSV, 탭 구분, 첫 줄이 머리글).**
필수 열은 `case`, `face`, `part_id`, `verdict` 네 개다.

| 열 | 뜻 | 예 |
|---|---|---|
| `case` | 과제·리비전 이름 | `T1_DV1` |
| `face` | 면 코드 | `F1` (없으면 빈칸) |
| `part_id` | 파트 ID | `15` |
| `verdict` | `NG`(불량) / `OK`(양호) | `NG` |
| `mechanism` | 선택 — 불량 메커니즘 | `crack` |
| `location` | 선택 — 위치 설명 | `INP_03` |
| `x` `y` `z` | 선택 — 실물 불량 좌표 (해석 좌표계) | `12.5` |
| `note` | 선택 — 비고 | |

좌표 세 개가 **모두** 있어야 위치로 쓴다. 하나라도 빠지면 위치 없음으로 둔다 —
두 축만 맞춰 그리면 엉뚱한 자리에 표시된다.

**설계 규칙.** 예외를 던지지 않는다. 읽지 못한 줄은 건너뛰고 사유를 남긴다.
`verdict` 를 해석하지 못하면 그 줄을 **버린다** — 모르는 것을 OK 로 치면
회수율이 부풀려진다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .stats_ranking import recall_at_k

REQUIRED_COLUMNS = ("case", "face", "part_id", "verdict")
OPTIONAL_COLUMNS = ("mechanism", "location", "note", "x", "y", "z")

#: verdict 로 인정하는 표기. 대소문자·공백은 무시한다.
_NG = {"ng", "fail", "failed", "defect", "crack", "불량", "1", "true"}
_OK = {"ok", "pass", "passed", "good", "양호", "0", "false"}


@dataclass
class GroundTruthRow:
    case: str = ""
    face: str = ""
    part_id: int | None = None
    is_ng: bool = False
    mechanism: str = ""
    location: str = ""
    note: str = ""
    #: 실물 불량 좌표 (해석 좌표계). 셋 다 있을 때만 채운다.
    xyz: tuple | None = None


@dataclass
class GroundTruth:
    rows: list = field(default_factory=list)
    skipped: list = field(default_factory=list)   #: (줄 번호, 사유)
    note: str = ""

    @property
    def n_ng(self) -> int:
        return sum(1 for r in self.rows if r.is_ng)

    def cases(self) -> list:
        return sorted({r.case for r in self.rows if r.case})

    def ng_points(self, case: str = "", face: str = "") -> list:
        """좌표가 있는 불량 위치 [(x, y, z, 라벨)]. 없으면 빈 목록."""
        out = []
        for r in self.rows:
            if not r.is_ng or not r.xyz:
                continue
            if case and r.case != case:
                continue
            if face and r.face != face:
                continue
            lab = r.location or r.mechanism or (f"part {r.part_id}" if r.part_id else "")
            out.append((r.xyz[0], r.xyz[1], r.xyz[2], lab))
        return out

    def ng_parts(self, case: str = "", face: str = "") -> set:
        """조건에 맞는 불량 파트 ID 집합. 빈 조건은 전체를 뜻한다."""
        out = set()
        for r in self.rows:
            if not r.is_ng or r.part_id is None:
                continue
            if case and r.case != case:
                continue
            if face and r.face != face:
                continue
            out.add(r.part_id)
        return out


def _verdict(s: str):
    k = str(s or "").strip().lower()
    if k in _NG:
        return True
    if k in _OK:
        return False
    return None          # 모르는 표기 — 줄을 버린다


def load_ground_truth(path) -> GroundTruth:
    """TSV 를 읽는다. 파일이 없거나 형식이 틀려도 예외를 던지지 않는다."""
    gt = GroundTruth()
    try:
        p = Path(path)
    except TypeError:
        gt.note = "경로를 해석하지 못했습니다"
        return gt
    if not p.is_file():
        gt.note = f"파일이 없습니다: {p}"
        return gt
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        gt.note = f"읽지 못했습니다 ({type(e).__name__}: {e})"
        return gt

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        gt.note = "내용이 비어 있습니다"
        return gt
    head = [h.strip().lower() for h in lines[0].split("\t")]
    missing = [c for c in REQUIRED_COLUMNS if c not in head]
    if missing:
        gt.note = (f"필수 열이 없습니다: {', '.join(missing)} "
                   f"(머리글: {', '.join(head) or '없음'})")
        return gt
    idx = {c: head.index(c) for c in head}

    def cell(parts, name):
        i = idx.get(name)
        return parts[i].strip() if (i is not None and i < len(parts)) else ""

    for lineno, ln in enumerate(lines[1:], start=2):
        parts = ln.split("\t")
        v = _verdict(cell(parts, "verdict"))
        if v is None:
            gt.skipped.append((lineno, f"verdict 를 해석하지 못했습니다: "
                                       f"{cell(parts, 'verdict')!r}"))
            continue
        row = GroundTruthRow(
            case=cell(parts, "case"),
            face=cell(parts, "face").upper(),
            is_ng=v,
            mechanism=cell(parts, "mechanism"),
            location=cell(parts, "location"),
            note=cell(parts, "note"),
        )
        # 좌표 — 셋 다 있고 셋 다 숫자일 때만 쓴다
        cs = [cell(parts, k) for k in ("x", "y", "z")]
        if all(c for c in cs):
            try:
                row.xyz = tuple(float(c) for c in cs)
            except (TypeError, ValueError):
                gt.skipped.append((lineno, f"좌표가 숫자가 아닙니다: {cs}"))
                continue

        pid = cell(parts, "part_id")
        if pid:
            try:
                row.part_id = int(float(pid))
            except (TypeError, ValueError):
                gt.skipped.append((lineno, f"part_id 가 정수가 아닙니다: {pid!r}"))
                continue
        gt.rows.append(row)

    if not gt.rows:
        gt.note = f"쓸 수 있는 줄이 없습니다 (건너뜀 {len(gt.skipped)}줄)"
    return gt


@dataclass
class MatchResult:
    n_candidates: int = 0
    n_ng: int = 0
    k: int = 0
    recall: float | None = None
    baseline: float | None = None
    hit_parts: list = field(default_factory=list)
    miss_parts: list = field(default_factory=list)
    note: str = ""


def part_recall(scores_by_part: dict, gt: GroundTruth, k: int,
                case: str = "", face: str = "",
                higher_is_worse: bool = True) -> MatchResult:
    """시뮬 상위 k 파트에 실제 불량 파트가 몇 개 들어오는가.

    Args:
        scores_by_part: {파트 ID: 위험도 점수}
        gt: 시험 불량 데이터
        k: 상위 몇 개를 검사한다고 볼 것인가
        case/face: 비우면 전체

    Returns:
        MatchResult — 계산 못 하면 `recall=None` 이고 `note` 에 사유가 있다.
    """
    res = MatchResult()
    if not isinstance(scores_by_part, dict) or not scores_by_part:
        res.note = "파트별 점수가 없습니다"
        return res
    ng = gt.ng_parts(case=case, face=face)
    if not ng:
        res.note = ("해당 조건에 불량 파트가 없습니다"
                    + (f" (case={case!r}, face={face!r})" if case or face else ""))
        return res

    pids, scores, pos = [], [], []
    for pid, sc in scores_by_part.items():
        try:
            p = int(pid)
            s = float(sc)
        except (TypeError, ValueError):
            continue
        pids.append(p)
        scores.append(s)
        pos.append(p in ng)
    if not pids:
        res.note = "점수를 숫자로 해석할 수 있는 파트가 없습니다"
        return res

    r = recall_at_k(scores, pos, k, higher_is_worse=higher_is_worse)
    res.n_candidates = r.n_candidates
    res.n_ng = r.n_positive
    res.k = r.k
    res.recall = r.recall
    res.baseline = r.baseline
    res.note = r.note
    if r.recall is None:
        return res

    order = sorted(range(len(pids)),
                   key=lambda i: (-scores[i] if higher_is_worse else scores[i], pos[i]))
    top = {pids[i] for i in order[: r.k]}
    res.hit_parts = sorted(p for p in ng if p in top)
    res.miss_parts = sorted(p for p in ng if p not in top)
    return res
