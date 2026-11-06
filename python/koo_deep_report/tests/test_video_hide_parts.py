# 영상 숨김 · 타겟 파트별 단면 · 무시 옵션 경고 시험 — 리포트 그림 3단계(바닥이 커서 타겟이 안 보이던 문제)
import argparse
from pathlib import Path

import pytest

from koo_deep_report.core import d3plot_reader as R
from koo_deep_report.render.job_builder import (
    RenderConfig, SectionViewRenderConfig as SVC, _sv_yaml_block, build_lsprepost_section_jobs,
    build_part_section_render_yaml_entries, build_render_jobs, build_section_view_yaml_entries,
)
from koo_deep_report.report.models import D3plotResult, PartTimeSeries


def _svc(**kw):
    base = dict(enabled=True, axes=["z"], scalar_fields=["von_mises"])
    base.update(kw)
    return SVC(**base)


# ── YAML 블록마다 숨김이 실린다 ──────────────────────────────────────────────
def test_software_block_carries_hidden_parts_only_when_set():
    assert "hidden_parts:\n  ids: [23, 24]\n" in _sv_yaml_block("z", "/o", _svc(hide_part_ids=[23, 24]))
    assert "hidden_parts" not in _sv_yaml_block("z", "/o", _svc())          # 비면 키를 쓰지 않는다(종전 출력 그대로)


def test_section_view_jobs_turn_zoom_crop_off_but_legacy_keeps_it():
    jobs = build_lsprepost_section_jobs("/o", _svc(backend="lsprepost", target_part_ids=[17]), None)
    assert jobs and all(j["zoom_crop"] is False for j in jobs)          # 단면 영상 — 확대본 없음
    y = R._dict_to_yaml(jobs[0], indent=2)
    assert "zoom_crop: false" in y
    legacy = build_render_jobs("/d3", "/o", RenderConfig(per_part_render=True, section_axes=["z"]), [5])
    assert all("zoom_crop" not in j for j in legacy)                     # 예전 파트별 렌더는 종전대로(확대본 유지)


def test_single_software_target_is_not_rendered_twice():
    names = [n for n, _ in build_section_view_yaml_entries("/o", _svc(per_part_render=True, target_part_ids=[17]), [17])]
    assert names == ["section_view_z"]                       # 개관 = 그 파트 하나(카메라도 타겟) — 파트별은 같은 영상
    names = [n for n, _ in build_section_view_yaml_entries("/o", _svc(per_part_render=True, target_part_ids=[5, 7]),
                                                           [5, 7])]
    assert names == ["section_view_z", "section_view_part_5_z", "section_view_part_7_z"]


def test_per_part_lists_drop_hidden_parts_everywhere():
    sv = _svc(per_part_render=True, hide_part_ids=[23])
    names = [n for n, _ in build_section_view_yaml_entries("/o", sv, [5, 23, 7])]
    assert "section_view_part_23_z" not in names and "section_view_part_5_z" in names
    sv = _svc(per_part_render=True, hide_part_ids=[23], backend="lsprepost")
    (_, body), = build_part_section_render_yaml_entries("/o", sv, [5, 23, 7])
    assert "part_ids: [5, 7]\n" in body and "hide_part_ids: [23]\n" in body
    jobs = build_lsprepost_section_jobs("/o", sv, [5, 23, 7])
    assert all(j.get("hide_part_ids") == [23] for j in jobs)
    assert not any(j["name"].startswith("section_view_part_23") for j in jobs)
    rj = build_render_jobs("/d3", "/o", RenderConfig(per_part_render=True, section_axes=["z"], hide_part_ids=[23]),
                           [5, 23])
    assert [j["name"] for j in rj] == ["overview_z", "part_5_z"] and all(j["hide_part_ids"] == [23] for j in rj)
    assert "hide_part_ids" not in build_render_jobs("/d3", "/o", RenderConfig(section_axes=["z"]), None)[0]


# ── 타겟 id → 그 파트들의 파트별 단면, 분석 대상은 안 좁힘 ────────────────────────
@pytest.mark.parametrize("backend", ["lsprepost", "software"])
def test_target_ids_drive_per_part_without_narrowing_analysis(backend):
    sv = _svc(backend=backend, per_part_render=True, target_part_ids=[5, 7])
    y = R._build_yaml(Path("/d3"), Path("/o"), RenderConfig(lsprepost_path="/l/lsprepost"), None, 1,
                      section_view_config=sv)
    assert "    parts: []" in y                                  # 분석은 전체
    if backend == "lsprepost":
        assert "    part_ids: [5, 7]" in y
    else:
        assert "section_view_part_5_z" in y and "section_view_part_7_z" in y
        assert "section_view_part_9_z" not in y


def test_no_second_pass_when_target_ids_given(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(R, "find_unified_analyzer", lambda d=None: Path("/bin/true"))
    monkeypatch.setattr(R, "_run_ua", lambda ua, y, v: calls.append(y))

    def fake(out, parse_motion=True, series=None):
        st = [PartTimeSeries(p, "", "von_mises", "", 1.0, 0.0, 0.0, [{"time": 0.0, "max": 1.0}], 1) for p in (5, 7, 9)]
        return D3plotResult(metadata={}, stress=st, strain=[], acceleration=[], motion={})
    monkeypatch.setattr(R, "_parse_outputs", fake)
    R.run_analysis(Path("/d3"), tmp_path, RenderConfig(enabled=False), None,
                   section_view_config=_svc(backend="software", per_part_render=True, target_part_ids=[5]))
    assert len(calls) == 1                                   # 분석 결과로 파트를 다시 뽑는 2차 패스가 없다
    calls.clear()
    R.run_analysis(Path("/d3"), tmp_path, RenderConfig(enabled=False), None,
                   section_view_config=_svc(backend="software", per_part_render=True))
    assert len(calls) == 2                                   # 타겟이 없으면 종전대로 2차 패스


# ── 쓰이지 않는 옵션은 말한다 ──────────────────────────────────────────────
def test_ignored_render_options_are_reported():
    w = R._ignored_option_warnings(RenderConfig(per_part_render=True, part_pattern="*PKG*"), _svc())
    assert len(w) == 2 and all(x.startswith("[설정]") for x in w)
    w = R._ignored_option_warnings(RenderConfig(), _svc(backend="software", target_patterns=["*PKG*"]))
    assert len(w) == 1 and "target-ids" in w[0]
    w = R._ignored_option_warnings(RenderConfig(), _svc(backend="lsprepost", target_patterns=["*A*", "*B*"]))
    assert len(w) == 1 and "'*A*'" in w[0]
    w = R._ignored_option_warnings(RenderConfig(), _svc(backend="software", state_step=20))
    assert len(w) == 1 and "state-step" in w[0]                    # 소프트웨어는 프레임 보폭을 안 쓴다(전 상태)
    assert R._ignored_option_warnings(RenderConfig(), _svc(backend="lsprepost", state_step=20)) == []
    assert R._ignored_option_warnings(RenderConfig(per_part_render=True), None) == []      # 단면이 꺼져 있으면 없음
    assert R._ignored_option_warnings(RenderConfig(per_part_render=True), _svc(enabled=False)) == []


# ── deep 이 숨김을 두 렌더 설정에 싣는다 ─────────────────────────────────────
def test_apply_video_hide_sets_both_configs():
    from koo_deep_report.__main__ import _apply_video_hide
    rc, sv = RenderConfig(), _svc()
    ids = _apply_video_hide(argparse.Namespace(hide_parts=[9, 3], hide_floor=False), None, rc, sv)
    assert ids == [3, 9] and rc.hide_part_ids == [3, 9] and sv.hide_part_ids == [3, 9]
    assert _apply_video_hide(argparse.Namespace(), None, RenderConfig(), None) == []    # d3plot 없으면 감지 못 함


V14 = Path("/data/koopark/Test_Postprocess_v14/output/Run_20260522_103123_7ad7d9/Output/d3plot")


@pytest.mark.skipif(not V14.exists(), reason="v14 실데이터 없음")
def test_hide_floor_detects_v14_floor():
    pytest.importorskip("lasso")
    from koo_deep_report.__main__ import _apply_video_hide
    rc = RenderConfig()
    assert _apply_video_hide(argparse.Namespace(hide_parts=None, hide_floor=True), V14, rc, None) == [23]


def test_cli_hide_floor_is_on_by_default():
    from koo_deep_report.__main__ import _add_single_args
    p = argparse.ArgumentParser()
    _add_single_args(p)
    assert p.parse_args(["x"]).hide_floor is True                     # 기본 켬(사용자 결정 11-06)
    assert p.parse_args(["x", "--no-hide-floor"]).hide_floor is False
    a = p.parse_args(["x", "--hide-floor", "--hide-parts", "4"])
    assert a.hide_floor and a.hide_parts == [4]


@pytest.mark.skipif(not V14.exists(), reason="v14 실데이터 없음")
def test_namespace_without_flag_still_hides_floor():
    """GUI 처럼 Namespace 를 손으로 지어 hide_floor 가 없으면 기본(켬)을 따른다."""
    pytest.importorskip("lasso")
    from koo_deep_report.__main__ import _apply_video_hide
    assert _apply_video_hide(argparse.Namespace(), V14, RenderConfig(), None) == [23]
