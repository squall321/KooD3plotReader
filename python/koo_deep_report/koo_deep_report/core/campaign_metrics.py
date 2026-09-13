# 캠페인 런들의 지표를 롱포맷 한 장으로 모으는 모듈 — 20MB×N 재파싱을 없앤다
"""캠페인 롱포맷 지표 테이블.

**왜 이 모듈이 있나.**
후처리는 런마다 `analysis_result.json`(20MB)을 따로 뱉을 뿐 가로로 묶지 못한다.
186런을 볼 때마다 20MB × 186 을 다시 파싱해야 했고, 그래서 캠페인 분석이
임시 스크립트로 흘렀다. 여기서 한 번 모아 한 장으로 만든다.

**형식은 롱포맷이다.** 한 줄 = (런, 각도, 파트, 요소종류, 기준량, 지표) → 값.
지표가 늘어나도 열이 늘지 않아 스키마가 안 깨진다.

**설계 규칙.**
- 예외를 던지지 않는다. 읽지 못한 런은 건너뛰고 `skipped` 에 사유를 남긴다.
- 없는 값은 줄을 만들지 않는다. 0 으로 채우지 않는다.
- 각 줄에 `tool_commit` 을 넣는다 — 런마다 다른 빌드로 분석됐는지 나중에 알 수 있게.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .face_deviation import classify_direction, face_deviation, nearest_face

#: 롱포맷 열 순서. 바꾸면 기존 TSV 를 읽는 쪽이 깨지므로 끝에만 추가할 것.
COLUMNS = [
    "run", "roll", "pitch", "yaw", "face", "dev_angle", "lattice",
    "part_id", "element_type", "criterion", "metric", "value", "tool_commit",
]

#: 군집 항목에서 뽑을 파트 수준 지표 (top_percent 에 **독립**인 것들).
_PART_METRICS = (
    "n_yield", "vol_yield", "vol_total", "sum_eps_vol", "max_eps",
    "plastic_work_total", "element_count_total",
)

#: 덩어리 1위에서 뽑을 지표 (top_percent 에 종속 — 이름에 `c1_` 을 붙여 구분한다)
_CLUSTER_METRICS = (
    "stress_max", "stress_mean", "mean_timemax", "volume",
    "energy_total", "energy_max", "radius_enclosing", "element_count",
)


#: 런 단위 정보 열 — 군집이 없는 캠페인에서도 각도 건전성을 점검할 수 있게
#: `rows` 와 **따로** 보관한다. 각도를 군집 줄에만 실으면 핫스팟을 안 돌린
#: 캠페인에서는 점검 자체가 불가능해진다.
RUN_COLUMNS = ["run", "roll", "pitch", "yaw", "face", "dev_angle", "lattice",
               "tool_commit", "n_items"]


@dataclass
class CampaignTable:
    rows: list = field(default_factory=list)      #: COLUMNS 순서의 튜플 목록
    runs: list = field(default_factory=list)      #: RUN_COLUMNS 순서의 튜플 목록
    n_runs: int = 0
    skipped: list = field(default_factory=list)   #: (런 이름, 사유)
    tool_builds: dict = field(default_factory=dict)  #: {커밋: 런 수}
    note: str = ""

    def to_tsv(self, path) -> str | None:
        """지표 롱포맷을 TSV 로 저장. 성공하면 None, 실패하면 사유 문자열."""
        return _write_tsv(path, COLUMNS, self.rows)

    def runs_to_tsv(self, path) -> str | None:
        """런 단위 표(각도·면·격자·빌드)를 TSV 로 저장."""
        return _write_tsv(path, RUN_COLUMNS, self.runs)


def _write_tsv(path, columns, rows) -> str | None:
    try:
        p = Path(path)
        if p.parent and str(p.parent):
            p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write("\t".join(columns) + "\n")
            for r in rows:
                f.write("\t".join("" if v is None else str(v) for v in r) + "\n")
    except (OSError, TypeError) as e:
        return f"TSV 저장 실패 ({type(e).__name__}: {e})"
    return None


def _angle_of(run_dir: Path):
    """DropSet.json 에서 (roll, pitch, yaw). 없으면 None."""
    ds = run_dir / "DropSet.json"
    if not ds.is_file():
        return None
    try:
        j = json.loads(ds.read_text(encoding="utf-8", errors="replace"))
        e = j["initial_conditions"]["orientation_euler_deg"]
        return (float(e["roll"]), float(e["pitch"]), float(e.get("yaw", 0.0)))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def collect_campaign(test_dir, part_ids=None) -> CampaignTable:
    """캠페인 디렉토리를 훑어 롱포맷 지표를 모은다.

    Args:
        test_dir: `analysis_results/Run_*/analysis_result.json` 와
                  `output/Run_*/DropSet.json` 를 가진 캠페인 폴더
        part_ids: 이 파트들만. None 이면 전부.

    Returns:
        CampaignTable. 읽지 못한 런은 `skipped` 에 사유와 함께 남는다.
    """
    tbl = CampaignTable()
    try:
        root = Path(test_dir)
    except TypeError:
        tbl.note = "test_dir 을 경로로 해석하지 못했습니다"
        return tbl
    adir = root / "analysis_results"
    odir = root / "output"
    if not adir.is_dir():
        tbl.note = f"analysis_results 가 없습니다: {adir}"
        return tbl

    want = None
    if part_ids is not None:
        want = set()
        for v in part_ids:
            try:
                want.add(int(v))
            except (TypeError, ValueError):
                continue
        if not want:
            tbl.note = "part_ids 에 쓸 수 있는 파트 ID 가 없습니다"
            return tbl

    for d in sorted(adir.iterdir()):
        if not d.is_dir():
            continue
        jf = d / "analysis_result.json"
        if not jf.is_file():
            tbl.skipped.append((d.name, "analysis_result.json 없음"))
            continue
        try:
            doc = json.loads(jf.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError) as e:
            tbl.skipped.append((d.name, f"JSON 읽기 실패 ({type(e).__name__})"))
            continue
        if not isinstance(doc, dict):
            tbl.skipped.append((d.name, "JSON 최상위가 객체가 아님"))
            continue

        tbl.n_runs += 1
        meta = doc.get("metadata") or {}
        commit = meta.get("tool_commit") or ""
        if commit:
            tbl.tool_builds[commit] = tbl.tool_builds.get(commit, 0) + 1

        ang = _angle_of(odir / d.name)
        if ang is None:
            roll = pitch = yaw = None
            face = dev = lat = None
        else:
            roll, pitch, yaw = ang
            face, _ = nearest_face(roll, pitch, yaw)
            fd = face_deviation(roll, pitch, yaw, face or "")
            dev = fd.dev_angle
            lat, _ = classify_direction(roll, pitch, yaw)

        hs = doc.get("hotspot_clusters")
        n_items = len(hs) if isinstance(hs, list) else 0
        tbl.runs.append((d.name, roll, pitch, yaw, face, dev, lat, commit, n_items))

        if not isinstance(hs, list):
            continue
        for item in hs:
            if not isinstance(item, dict):
                continue
            try:
                pid = int(item.get("part_id"))
            except (TypeError, ValueError):
                continue
            if want is not None and pid not in want:
                continue
            etype = str(item.get("element_type") or "solid")
            crit = str(item.get("criterion") or "")

            def emit(metric, value):
                # 없는 값은 줄을 만들지 않는다 — 0 으로 채우면 "값이 0" 으로 읽힌다
                if value is None or isinstance(value, bool):
                    return
                tbl.rows.append((d.name, roll, pitch, yaw, face, dev, lat,
                                 pid, etype, crit, metric, value, commit))

            for m in _PART_METRICS:
                emit(m, item.get(m))
            clusters = item.get("clusters")
            if isinstance(clusters, list) and clusters:
                c0 = clusters[0]
                if isinstance(c0, dict):
                    for m in _CLUSTER_METRICS:
                        emit(f"c1_{m}", c0.get(m))
                emit("n_clusters", len(clusters))

    if tbl.n_runs == 0:
        tbl.note = f"런을 하나도 읽지 못했습니다 (건너뜀 {len(tbl.skipped)}건)"
    return tbl
