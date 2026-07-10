# 보고서 출력 모드(inline/deferred/chunked) 결정·실행 — file:// 안전 청크 포함 (SOTA P4-3)
"""HTML 보고서 방출기.

- inline   (tier A/B): 단일 파일, ``const DATA = {...}`` JS 리터럴 (종전 동작)
- deferred (tier C)  : 단일 파일, payload 를 ``<script type="application/json">``
                       블록에 두고 boot 시 JSON.parse — 대용량에서 JS 리터럴
                       파싱보다 빠르고 메모리 피크가 낮다.
- chunked  (tier D)  : ``report.html`` + ``<stem>_data/pos_<id>.js`` 청크.
                       fetch/XHR 는 file:// 에서 막히므로 청크는 반드시
                       ``<script src>`` JSONP(window.KOO_CHUNKS) 방식.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .html_report import generate_html
from .payload import _build_payload
from .payload.common import _Encoder
from .payload.position import build_position_bundle
from .payload.tiers import tier_for, TierPolicy, CHUNK_MOTION_PTS, CHUNK_TRAJ_PTS

# --chunked 강제 시 인라인 payload 에 적용할 캡 — tier D 와 동일 (모드-캡 일치).
_CHUNK_FORCED_TIER = TierPolicy("D", 0, 40, 24, 0, 64, 3, "chunked")


def _resolve_mode(report, mode: str | None) -> str:
    if mode in ("inline", "deferred", "chunked"):
        return mode
    n_pos = sum(len(v or []) for v in (report.positions_by_face or {}).values())
    return tier_for(n_pos).emit_mode


def _chunk_fname(pos_id: str) -> str:
    """pos_id → 파일시스템 안전 청크 id (영숫자/_/- 만)."""
    return "pos_" + re.sub(r"[^A-Za-z0-9_-]", "_", str(pos_id))


def emit_report(report, out_path: str | Path, mode: str | None = None) -> Path:
    """report 를 out_path 에 방출. 반환값은 실제 쓴 HTML 경로."""
    out_path = Path(out_path)
    mode = _resolve_mode(report, mode)

    if mode == "inline":
        out_path.write_text(generate_html(report), encoding="utf-8")
        return out_path

    # chunked 는 인라인 payload 캡도 tier D 로 맞춘다 (곡선은 청크가 담당).
    payload = _build_payload(
        report, tier_override=_CHUNK_FORCED_TIER if mode == "chunked" else None)

    if mode == "chunked":
        # 청크 디렉터리: report.html 옆 <stem>_data/
        data_dir = out_path.parent / f"{out_path.stem}_data"
        data_dir.mkdir(parents=True, exist_ok=True)
        ids = []
        for positions in (report.positions_by_face or {}).values():
            for pos in positions or []:
                pid = str(pos.pos_id)
                cid = _chunk_fname(pid)
                bundle = build_position_bundle(
                    report, pid,
                    motion_pts=CHUNK_MOTION_PTS, traj_pts=CHUNK_TRAJ_PTS)
                blob = json.dumps(bundle, cls=_Encoder, separators=(",", ":"))
                blob = blob.replace("</", "<\\/")
                (data_dir / f"{cid}.js").write_text(
                    'window.KOO_CHUNKS=window.KOO_CHUNKS||{};'
                    f'window.KOO_CHUNKS[{json.dumps(cid)}]={blob};',
                    encoding="utf-8")
                ids.append(cid)
        payload["chunks"] = {"dir": data_dir.name, "ids": ids, "unit": "position"}

    # deferred | chunked: payload 를 JSON 블록으로, DATA 는 boot 시 파싱.
    html = generate_html(report, payload=payload, deferred=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
