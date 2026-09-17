# 보고서 차트 다운샘플이 피크·최소를 잃지 않고 배열 정렬을 지키는지 검증하는 시험
"""`report.html_report` 의 차트 다운샘플 시험.

JSON 이 전 상태를 담게 된 뒤(2026-09) 균등 간격 500점 다운샘플이 실덱 응력
시리즈 23개 중 21개의 피크를 버렸다(파트 4: 32.2 → 29.4). 다운샘플은
그려지는 값의 극값을 반드시 남겨야 한다.
"""
import math

from koo_deep_report.report.html_report import _downsample_group, _series_to_dict
from koo_deep_report.report.models import PartTimeSeries


def _spiky(n, spike_at, spike, dip_at, dip):
    vals = [math.sin(i / 37.0) for i in range(n)]
    vals[spike_at] = spike
    vals[dip_at] = dip
    return vals


def test_short_series_unchanged():
    t = [0.0, 1.0, 2.0]
    out = _downsample_group(t, {"a": [1, 2, 3]}, n_max=500)
    assert out["t"] == t and out["a"] == [1, 2, 3]


def test_single_sample_spike_and_dip_survive():
    n = 4952
    t = [i * 1e-6 for i in range(n)]
    a = _spiky(n, 2711, 50.0, 1303, -40.0)
    b = _spiky(n, 4001, 9.0, 17, -7.0)
    out = _downsample_group(t, {"a": a, "b": b}, n_max=500)
    assert max(out["a"]) == 50.0 and min(out["a"]) == -40.0
    assert max(out["b"]) == 9.0 and min(out["b"]) == -7.0
    # 정렬: 같은 인덱스로 뽑혀야 한다
    assert len(out["t"]) == len(out["a"]) == len(out["b"])
    i = out["a"].index(50.0)
    assert out["t"][i] == t[2711]
    assert out["t"][0] == t[0] and out["t"][-1] == t[-1]
    assert out["t"] == sorted(out["t"])
    assert len(out["t"]) <= 500


def test_many_arrays_bounded():
    n = 5000
    t = list(range(n))
    arrays = {f"p{k}": _spiky(n, (k * 97) % n, 100.0 + k, (k * 53 + 11) % n, -100.0 - k) for k in range(80)}
    out = _downsample_group(t, arrays, n_max=500)
    for k in range(80):
        assert max(out[f"p{k}"]) == 100.0 + k and min(out[f"p{k}"]) == -100.0 - k
    assert len(out["t"]) <= 4 * 500 + 2 * 80 + 2


def test_non_finite_and_none_do_not_break():
    n = 2000
    t = list(range(n))
    a = [float(i % 7) for i in range(n)]
    a[5] = float("nan")
    a[6] = None
    a[1500] = 99.0
    out = _downsample_group(t, {"a": a}, n_max=100)
    assert 99.0 in out["a"]
    assert len(out["t"]) == len(out["a"])


def test_misaligned_array_is_not_silently_mixed():
    t = list(range(1000))
    good = [0.0] * 1000
    good[400] = 5.0
    short = list(range(10))
    out = _downsample_group(t, {"good": good, "short": short}, n_max=100)
    assert max(out["good"]) == 5.0
    # 길이가 다른 배열은 t 인덱스로 뽑을 수 없다 — 그대로 둔다 (자체 길이 ≤ n_max)
    assert out["short"] == short


def test_series_to_dict_keeps_peak():
    n = 4952
    data = [{"time": i * 1e-6, "max": 1.0, "min": 0.0, "avg": 0.5} for i in range(n)]
    data[3333]["max"] = 471.8
    data[100]["avg"] = 0.01
    s = PartTimeSeries(part_id=1, part_name="p", quantity="von_mises", unit="MPa",
                       global_max=471.8, global_min=0.0, time_of_max=3333e-6, data=data)
    d = _series_to_dict(s)
    assert max(d["max_vals"]) == 471.8
    assert min(d["avg_vals"]) == 0.01
    assert len(d["t"]) == len(d["max_vals"]) == len(d["avg_vals"]) <= 500


def test_all():
    for name, fn in list(globals().items()):
        if name.startswith("test_") and name != "test_all":
            fn()


if __name__ == "__main__":
    test_all()
    print("OK")
