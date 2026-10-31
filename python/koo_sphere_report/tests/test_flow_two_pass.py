# 2패스 적재 — 줄인 사실을 산출물에 적고, 내부 키를 내보내지 않는지
"""에너지 흐름 2패스 축약.

배경 (2026-10, M3_P2 979런). 예전에는 전 run 의 흐름을 **전부 메모리에 들고**
반환했다. 0.087 GB/run × 979 = 85 GB — 측정된 MaxRSS 84.7 GB 가 그것이다.
봉우리는 캐시 생성 비용이 아니라 최종 누적분이라, 앞단만 병렬화해도 안 내려간다.

1패스에서 스칼라만 남기고, 2패스에서 시계열이 필요한 상위
`FLOW_DETAIL_LIMIT` 개만 캐시에서 되읽는다.

여기서 못박는 것 —
- 줄인 런은 **`scalars_only` 로 표시**한다. `report.json` 은 energy_flows 를
  그대로 싣고 온톨로지·DynaForge 가 읽는다. 표식이 없으면 `first_engage_t` 가
  없는 것이 "안 쟀다" 인지 "메모리 때문에 뺐다" 인지 구분할 수 없다.
- 적재 중에만 쓰는 내부 키(`_part_energy`·`_pf_max`)는 **산출물로 안 나간다**.
- 전 각도 소비처(`_contact_profile`·`_contact_trust`)가 읽는 것은 다 남긴다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report import loader as L  # noqa: E402

_FULL = {
    "edges": [{"src": "1", "dst": "2", "contact_id": 9, "name": "C",
               "peak_force": 12.5, "total_impulse": 0.415073, "total_work": 3.0,
               "first_engage_t": 1.9998e-05, "confidence": 0.9,
               "force_mag_ts": [1.0] * 500}],
    "nodes": [{"node_id": "1", "peak_ie": 5.0, "final_ke": 1.0,
               "kinetic_ts": [0.0] * 500, "internal_ts": [0.0] * 500},
              {"node_id": "iface:3", "peak_ie": 9.9}],
    "contact_metrics": {"available": True, "n_interfaces": 2},
    "impactor_ke_initial": 100.0,
}


def test_slim_keeps_what_all_angle_consumers_read():
    """`_contact_profile`·`_contact_trust` 가 읽는 것은 전부 남는다."""
    s = L._slim_flow(_FULL)
    e = s["edges"][0]
    for k in ("src", "dst", "contact_id", "name",
              "peak_force", "total_impulse", "total_work"):
        assert k in e, f"{k} 가 빠지면 접촉 프로파일 탭이 깨진다"
    assert s["contact_metrics"]["available"] is True


def test_slim_drops_the_timeseries():
    """덩치는 시계열이다 — 그게 85 GB 의 정체다."""
    s = L._slim_flow(_FULL)
    assert "force_mag_ts" not in s["edges"][0]
    assert "nodes" not in s
    # 줄어든 정도가 실제로 크다
    import json
    assert len(json.dumps(s)) * 5 < len(json.dumps(_FULL))


def test_slim_declares_that_it_was_reduced():
    """**조용히 줄이지 않는다** — 읽는 쪽이 구분할 수 있어야 한다."""
    s = L._slim_flow(_FULL)
    assert s["scalars_only"] is True
    assert "first_engage_t" in s["dropped"]
    assert "confidence" in s["dropped"]


def test_part_energy_scalars_survive_for_all_runs():
    """파트별 IE/KE 는 전 각도에 필요하다 — 스칼라 6개만 남기면 된다."""
    s = L._slim_flow(_FULL)
    pe = s["_part_energy"]
    assert "1" in pe and pe["1"]["peak_ie"] == 5.0
    assert "iface:3" not in pe, "유령 노드는 파트가 아니다"


def test_ranking_key_is_the_max_peak_force():
    """2패스가 이 값으로 상위를 고른다 — `_flow_detail_folders` 와 같은 기준."""
    s = L._slim_flow(_FULL)
    assert s["_pf_max"] == pytest.approx(12.5)


def test_internal_keys_are_stripped_before_export():
    """`_part_energy`·`_pf_max` 가 report.json 으로 새면 안 된다.

    (load_all 이 2패스 뒤에 턴다. 여기서는 그 규약을 지킨다는 것만 못박는다.)
    """
    src = Path(L.__file__).read_text(encoding="utf-8")
    i = src.index("시계열 보유 {n_full}")
    before = src[max(0, i - 600):i]
    assert 'pop("_part_energy"' in before and 'pop("_pf_max"' in before, \
        "내부 키를 터는 자리가 없다"


def test_report_json_counts_reduced_runs():
    """몇 런이 줄었는지 사이드카가 말한다."""
    from koo_sphere_report.report import json_report as J
    src = Path(J.__file__).read_text(encoding="utf-8")
    assert "energy_flows_reduced" in src


def test_detail_limit_has_one_source():
    """로더와 리포트가 다른 수를 쓰면 조용히 어긋난다."""
    from koo_sphere_report.report import html_report as H
    assert H._FLOW_DETAIL_LIMIT is L.FLOW_DETAIL_LIMIT


@pytest.mark.parametrize("given,env,expect", [
    (4, None, 4), (1, None, 1), (0, "8", 8), (-1, None, 1),
])
def test_parallel_runs_resolution(given, env, expect, monkeypatch):
    """0 = auto 는 **배정받은 CPU** 를 따른다 — 노드 전체를 쓰면 남의 잡을 민다."""
    if env is None:
        monkeypatch.delenv("SLURM_CPUS_PER_TASK", raising=False)
    else:
        monkeypatch.setenv("SLURM_CPUS_PER_TASK", env)
    assert L._resolve_parallel_runs(given) == expect
