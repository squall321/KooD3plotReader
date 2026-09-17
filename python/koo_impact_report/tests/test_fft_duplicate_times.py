# 시각이 일부 중복된 motion CSV 에서 주파수 분석이 살아남는지(그리고 사유가 남는지) 검증하는 시험
"""옛 산출물의 motion CSV 는 Time 이 소수 6자리 고정이라 출력 간격이 1 µs 근처면
몇 구간이 같은 시각으로 뭉갠다(실측 992구간 중 5개, 0.5%).

중복이 조금이면 표본율은 중앙값 간격으로 충분히 알 수 있다 — 패널을 통째로 끄면
멀쩡한 분석이 사라진다. 중복이 많으면(>5%) 표본율을 알 수 없으므로 값을 내지 않는다.
"""
import math

from koo_impact_report.report.payload.analytics import _fft_dominant_freq


def _signal(n, dt, freq, round_to=None):
    times, acc = [], []
    for i in range(n):
        t = i * dt
        if round_to is not None:
            t = round(t, round_to)
        times.append(t)
        acc.append(math.sin(2 * math.pi * freq * i * dt))
    return times, acc


def test_few_duplicate_times_still_analyzed():
    # 0.995 µs 간격을 소수 6자리로 반올림 → 991구간 중 5개가 같은 시각 (실덱과 같은 0.5%)
    times, acc = _signal(992, 0.995e-6, 5000.0, round_to=6)
    dups = sum(1 for a, b in zip(times, times[1:]) if b <= a)
    assert 0 < dups / (len(times) - 1) < 0.05, f"표본이 의도한 모양이 아니다 (중복 {dups})"

    res = _fft_dominant_freq(times, acc, f_lo=10.0)
    assert res is not None, "중복이 0.5% 뿐인데 분석을 통째로 포기했다"
    f_dom, _peak, _freqs, _amps, fs = res
    assert abs(fs - 1.0 / 0.995e-6) / (1.0 / 0.995e-6) < 0.02, f"표본율이 크게 틀렸다: {fs}"
    assert abs(f_dom - 5000.0) / 5000.0 < 0.05, f"주파수가 틀렸다: {f_dom}"


def test_many_duplicate_times_refused():
    # 간격의 절반이 뭉개진 경우 — 표본율을 알 수 없다
    times, acc = _signal(992, 0.5e-6, 5000.0, round_to=6)
    dups = sum(1 for a, b in zip(times, times[1:]) if b <= a)
    assert dups / (len(times) - 1) > 0.05
    assert _fft_dominant_freq(times, acc, f_lo=10.0) is None


def test_clean_times_unchanged():
    times, acc = _signal(512, 1e-6, 4000.0)
    res = _fft_dominant_freq(times, acc, f_lo=10.0)
    assert res is not None
    f_dom, _peak, _freqs, _amps, fs = res
    assert abs(fs - 1e6) / 1e6 < 1e-6
    assert abs(f_dom - 4000.0) / 4000.0 < 0.05


def test_all():
    for name, fn in list(globals().items()):
        if name.startswith("test_") and name != "test_all":
            fn()


if __name__ == "__main__":
    test_all()
    print("OK")
