# 캠페인·불량데이터·구간정의를 모아 그림에 바로 쓸 형태로 만드는 모듈
"""산포 보고서 입력 수집.

`koo_deep_report.core` 의 유틸을 쓴다. 그 패키지가 없으면 **명확히 실패**한다 —
조용히 빈 보고서를 내면 "왜 비었지" 를 아무도 답하지 못한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScatterInput:
    ok: bool = False
    note: str = ""
    table: object = None          #: CampaignTable
    gt: object = None             #: GroundTruth 또는 None
    segments: object = None       #: SegmentSet 또는 None
    part_ids: list = field(default_factory=list)


def _import_core():
    try:
        from koo_deep_report.core.campaign_metrics import collect_campaign
        from koo_deep_report.core.ground_truth import load_ground_truth
        from koo_deep_report.core.segment_boxes import load_segments
        return collect_campaign, load_ground_truth, load_segments
    except ImportError as e:
        return None, None, str(e)


def load(test_dir, part_ids=None, gt_path=None, segments_path=None) -> ScatterInput:
    """캠페인 + (선택) 불량데이터 + (선택) 구간정의를 읽는다."""
    si = ScatterInput()
    collect_campaign, load_ground_truth, load_segments = _import_core()
    if collect_campaign is None:
        si.note = (f"koo_deep_report 를 가져오지 못했습니다 ({load_segments}). "
                   f"PYTHONPATH 에 koo_deep_report 를 넣으세요 "
                   f"(배포본은 env.sh 가 설정합니다).")
        return si

    tbl = collect_campaign(test_dir, part_ids=part_ids, keep_clusters=True)
    si.table = tbl
    if tbl.n_runs == 0:
        si.note = tbl.note or "읽은 런이 없습니다"
        return si

    if gt_path:
        si.gt = load_ground_truth(gt_path)
        if not si.gt.rows:
            # 경로를 줬는데 못 읽은 것은 조용히 넘어가면 안 된다
            si.note = (si.note + f" / 불량데이터를 읽지 못했습니다: "
                       f"{si.gt.note}").strip(" /")
    if segments_path:
        si.segments = load_segments(segments_path)
        if not si.segments.segments:
            si.note = (si.note + f" / 구간정의를 읽지 못했습니다: "
                       f"{si.segments.note}").strip(" /")

    si.part_ids = sorted({r[7] for r in tbl.rows})
    si.ok = True
    return si
