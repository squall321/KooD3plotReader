# motion CSV 시각이 뭉개져 시각이 겹칠 때 주파수 결과를 내지 않는지 보는 시험
"""motion CSV 의 Time 은 소수 6자리 고정(1 µs 해상도)으로 쓰인다.

출력 간격이 1 µs 보다 촘촘하면 여러 상태가 **같은 시각**을 갖는다. 로더는
그 값을 그대로 읽고 아무 검사도 하지 않았고, FFT 는 `dts[dts > 0]` 로 0 간격을
버린 뒤 평균을 내 표본율을 간격비만큼 잘못 잡았다. 실측 재현: 20 kHz 가속도
신호를 1e-7 s 간격으로 2 ms 기록하면 참값 fs = 1e7 인데 CSV 를 거치면 1e6 이
되어 f_dom 이 20000 Hz 대신 2000 Hz 로 나온다 — 10배 틀린 숫자가 아무 표시
없이 스펙트럼에 실린다.

규칙. 시각이 단조증가하지 않으면 사유를 남기고 FFT/SRS 를 내지 않는다.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.models import PartMotion  # noqa: E402
from koo_impact_report.report.payload.analytics import (  # noqa: E402
    _build_fft_payload, _fft_dominant_freq,
)

F_TRUE = 20000.0      # Hz
DT_TRUE = 1.0e-07     # s — 출력 간격 (CSV 해상도 1e-6 보다 촘촘)
N = 20000


def _signal():
    t = [i * DT_TRUE for i in range(N)]
    a = [math.sin(2.0 * math.pi * F_TRUE * x) for x in t]
    return t, a


def _quantized(t):
    """CSV 왕복 — std::fixed << setprecision(6)."""
    return [float(f"{x:.6f}") for x in t]


def test_quantized_times_give_a_wrong_frequency():
    """원인 확인 — 뭉갠 시각을 그대로 FFT 에 넣으면 10배 틀린다."""
    t, a = _signal()
    true_res = _fft_dominant_freq(t, a, f_lo=10.0)
    assert true_res is not None
    assert abs(true_res[0] - F_TRUE) / F_TRUE < 0.01, true_res[0]
    q_res = _fft_dominant_freq(_quantized(t), a, f_lo=10.0)
    # 뭉갠 시각은 결과를 내면 안 된다 (내면 2000 Hz 같은 거짓 숫자가 된다).
    assert q_res is None, f"뭉갠 시각으로 f_dom={q_res[0]} 를 내놨다"


class _Part:
    def __init__(self, pid):
        self.part_id, self.part_name = pid, f"part_{pid}"


class _Rep:
    def __init__(self, motions, parts):
        self.part_motions = motions
        self.parts = parts


def _pm(times, acc, issue=None):
    m = PartMotion(part_id=7)
    m.times = list(times)
    m.acc_mag = list(acc)
    m.time_issue = issue
    return m


def test_fft_payload_reports_the_reason():
    """FFT 패널이 조용히 비지 않고 사유를 남긴다."""
    t, a = _signal()
    q = _quantized(t)
    n_dup = sum(1 for x, y in zip(q, q[1:]) if y <= x)
    rep = _Rep({("P1", 7): _pm(q, a, f"시각 중복 {n_dup}")}, [_Part(7)])
    out = _build_fft_payload(rep)
    assert not out.get("per_part_dominant_freq"), out
    assert out.get("time_issue"), out


def test_clean_times_still_work():
    """정상 시각은 종전대로 f_dom 을 낸다 — 회귀 방지."""
    t, a = _signal()
    rep = _Rep({("P1", 7): _pm(t, a)}, [_Part(7)])
    out = _build_fft_payload(rep)
    assert out["per_part_dominant_freq"], out
    f_dom = out["per_part_dominant_freq"]["7"]["mean_f_dom_Hz"]
    assert abs(f_dom - F_TRUE) / F_TRUE < 0.01, f_dom


def test_all():
    """pytest 진입점 — 위 시험들을 한 번에 돌린다."""
    test_quantized_times_give_a_wrong_frequency()
    test_fft_payload_reports_the_reason()
    test_clean_times_still_work()
