# σ1·σ3·ε1·ε3·ε_vm 시계열 export(_series_payload) 규칙 — 피크를 버리지 않는다
"""DynaForge 요청(PR #2)으로 더해진 시계열 5종의 다운샘플 규약.

실측 배경 (2026-10-17): PR #2 는 2026-09-04 에 만들어졌고, 그 뒤 main 에서
**데이터 무결성 대수술**이 다운샘플 규약을 바꿨다 — 균등 간격으로 뽑으면 피크가
통째로 빠지므로 `extreme_indices` 로 구간 극값을 보존하고, 자릿수는 고정 소수점
대신 `round_keep_sig` 로 유효숫자를 지킨다. PR 을 그대로 머지하면 새로 나가는
시계열 5종만 **옛 규약으로 되돌아간다** — 이미 고친 결함을 다시 들이는 셈이다.

여기서 못박는 것:
1. 다운샘플해도 **최댓값·최솟값이 살아남는다**
2. 작은 값이 0 으로 뭉개지지 않는다 (ε 4.2e-5 는 '완전 탄성' 으로 오독된다)
3. 없는 값은 **키 자체가 없다** (0 으로 채우면 미계측과 구분이 안 된다)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.models import TimeSeriesData  # noqa: E402
from koo_sphere_report.report.json_report import _series_payload  # noqa: E402


def _ts(n=400, spike_at=137, spike=999.0, dip_at=251, dip=-888.0):
    """중간에 날카로운 피크·딥이 하나씩 있는 시계열."""
    ts = TimeSeriesData()
    ts.times = [i * 1e-5 for i in range(n)]
    ts.max_values = [1.0] * n
    ts.min_values = [-1.0] * n
    ts.avg_values = [0.5] * n
    ts.max_values[spike_at] = spike
    ts.min_values[dip_at] = dip
    return ts


def test_peak_survives_downsample():
    """**이 시험이 핵심이다.** 400점을 20점으로 줄여도 피크가 남아야 한다.

    균등 간격(step=20)이면 137번째가 뽑히지 않아 999 가 사라진다.
    """
    out = _series_payload(_ts(), prec=2, points=20)
    assert out is not None
    assert len(out["t"]) <= 40, "점 수가 요청의 2배를 넘는다"
    assert max(out["max"]) == 999.0, f"피크가 사라졌다 (최대 {max(out['max'])})"


def test_min_track_keeps_its_dip():
    """want_min 이면 압축측 극값도 살아야 한다 (σ3·ε3 이 그렇다)."""
    out = _series_payload(_ts(), prec=2, points=20, want_min=True)
    assert "min" in out
    assert min(out["min"]) == -888.0, f"딥이 사라졌다 (최소 {min(out['min'])})"


def test_min_absent_unless_requested():
    """want_min 이 아니면 min 키를 만들지 않는다 — 안 쓰는 값을 싣지 않는다."""
    assert "min" not in _series_payload(_ts(), prec=2, points=20)


def test_small_values_do_not_collapse():
    """ε 4.2e-5 가 0.0 이 되면 읽는 쪽이 '완전 탄성' 으로 해석한다."""
    ts = TimeSeriesData()
    ts.times = [i * 1e-5 for i in range(50)]
    ts.max_values = [4.2e-5] * 50
    out = _series_payload(ts, prec=4, points=20)
    assert all(v != 0 for v in out["max"]), f"작은 값이 0 으로 뭉개졌다: {out['max'][:3]}"


def test_no_data_means_no_payload():
    """값이 없으면 None — 빈 dict 를 주면 소비자가 '측정했는데 비었다' 로 읽는다."""
    assert _series_payload(None, 2, 20) is None
    assert _series_payload(TimeSeriesData(), 2, 20) is None
    only_t = TimeSeriesData()
    only_t.times = [0.0, 1.0]
    assert _series_payload(only_t, 2, 20) is None, "시각만 있고 값이 없으면 None"


def test_mismatched_track_is_ignored():
    """길이가 어긋난 배열은 싣지 않는다 — 시각과 값이 밀려 붙으면 거짓 그래프가 된다."""
    ts = _ts(n=400)
    ts.avg_values = [0.5] * 7          # 길이 불일치
    out = _series_payload(ts, prec=2, points=20)
    assert "max" in out
    assert "avg" not in out, "길이가 어긋난 avg 를 실었다"
    assert len(out["t"]) == len(out["max"])
