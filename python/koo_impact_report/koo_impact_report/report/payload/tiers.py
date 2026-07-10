# 위치 수 기반 payload 축소 tier 정책 — 모든 다운샘플/캡/정밀도의 단일 소스 (SOTA P4)
"""Tier 정책 표.

| knob            | A ≤50 | B ≤100 | C ≤300      | D >300        |
|-----------------|-------|--------|-------------|---------------|
| part_motion pts | 600   | 250    | 200 (topK40)| 0 인라인, 청크 |
| trajectory pts  | 400   | 200    | 요약+청크    | 동일          |
| stress_ts pts   | 300   | 120    | 60          | envelope 만   |
| FFT/SRS bins    | 128   | 128    | 64          | 64 (worst-K)  |
| 정밀도(dp)      | 4     | 4      | 3           | 3             |
| 출력 모드       | inline| inline | deferred    | chunked       |

절대 임계값 발명 금지 원칙과 무관 — 이것은 물리 판정이 아니라 전송 예산.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TierPolicy:
    name: str                 # "A" | "B" | "C" | "D"
    part_motion_pts: int      # per-series 최대 샘플 수 (0 = 인라인 없음, 청크로)
    part_motion_topk: int     # 인라인 series 를 worst-K 위치로 제한 (0 = 무제한)
    trajectory_pts: int       # per-trajectory 최대 샘플 수 (0 = 요약 스칼라만 인라인)
    stress_ts_pts: int        # PairResult.stress_ts 최대 샘플 수 (0 = envelope 스칼라만)
    fft_bins: int             # FFT/SRS 스펙트럼 bin 상한
    precision: int            # 시계열 값 반올림 소수 자릿수
    emit_mode: str            # "inline" | "deferred" | "chunked"


_TIERS = (
    (50,          TierPolicy("A", 600, 0,  400, 300, 128, 4, "inline")),
    (100,         TierPolicy("B", 250, 0,  200, 120, 128, 4, "inline")),
    # C/D: trajectory 를 0 으로 비우면 5개 traj 패널이 NaN/TypeError 로
    # 죽는다 (Playwright 실측). 초저해상 인라인로 전 패널 무수정 생존 —
    # 풀해상은 per-position 청크가 담당 (드릴다운, P6).
    (300,         TierPolicy("C", 200, 40, 60,  60,  64,  3, "deferred")),
    (10 ** 9,     TierPolicy("D", 0,   40, 24,  0,   64,  3, "chunked")),
)


def tier_for(n_positions: int) -> TierPolicy:
    """DOE 위치 수 → tier 정책. 경계 포함(≤)."""
    for cap, policy in _TIERS:
        if n_positions <= cap:
            return policy
    return _TIERS[-1][1]


# 청크 파일(= 워커 pickle-back) 해상도 — 드릴다운 1개 위치를 볼 때의 충실도.
# tier C/D 에서 워커가 이 해상도로 선축소해 부모 프로세스 RSS 를 억제한다
# (in-worker tiering, P4-3). peak 샘플은 항상 보존.
CHUNK_MOTION_PTS = 600
CHUNK_TRAJ_PTS = 400
