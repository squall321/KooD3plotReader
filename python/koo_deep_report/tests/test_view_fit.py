# 카메라 타겟 맞춤(--view-fit target · --view-margin) 시험 — 작업 키 · CLI · 설정 파일 · 쓰이지 않는 조합 안내 · 분석기가 걸지 않은 까닭
"""LS-PrePost 단면 영상의 화면을 보이는 모델 전체가 아니라 타겟의 단면(잘린 면)에 맞추는 옵션.

맞춤 자체는 분석기(C++)가 한다. deep 이 맡는 것은 셋이다.
  - 타겟이 있는 작업에만 `view_fit: target` · `view_margin` 을 단다(기본은 키를 쓰지 않아 종전 YAML 그대로).
  - 어디에도 걸리지 않는 조합(타겟 없음 · 소프트웨어 백엔드 · 여백만 줌)은 실행 전에 '[설정]' 으로 말한다.
  - 분석기가 실행 중에 걸지 않은 영상(모델에 없는 번호 · 전부 숨김 · 패턴 0개)은 그 줄을 건져 보고서에 싣는다.
"""
import argparse
import stat
import types
from pathlib import Path

import pytest

from koo_deep_report.core import d3plot_reader as R
from koo_deep_report.render.job_builder import (
    RenderConfig, SectionViewRenderConfig as SVC, build_lsprepost_section_jobs, build_render_jobs,
)
from koo_deep_report.report.models import D3plotResult

REPO = Path(__file__).resolve().parents[3]
CPP = REPO / "src" / "analysis" / "UnifiedAnalyzerRender.cpp"

# 분석기가 실제로 찍는 줄(UnifiedAnalyzerRender.cpp processRenderJobs — 2026-11-20 실행 로그에서 옮김)
FIT_OK = "    View fit: 타겟 파트 1개에 카메라를 맞춥니다(여백 -0.3)"
NO_VISIBLE = "    View fit: 보이는 타겟이 없다(모두 숨김 대상이거나 모델에 없는 번호) — 보이는 모델 전체에 맞춥니다"
NO_TARGET = "    View fit: 타겟 파트가 없다 — 보이는 모델 전체에 맞춥니다"


def _svc(**kw):
    base = dict(enabled=True, backend="lsprepost", axes=["z"], scalar_fields=["von_mises"])
    base.update(kw)
    return SVC(**base)


def _parser():
    from koo_deep_report.__main__ import _add_single_args
    p = argparse.ArgumentParser()
    _add_single_args(p)
    return p


# ── 작업 키 — 타겟이 있는 작업에만 ───────────────────────────────────────────
def test_section_job_gets_fit_keys_only_with_a_target():
    (job,) = build_lsprepost_section_jobs("/o", _svc(view_fit_target=True, target_part_ids=[6]), None)
    assert job["view_fit"] == "target" and job["view_margin"] == -0.3 and job["parts"] == [6]
    y = R._dict_to_yaml(job, indent=2)
    assert '    view_fit: "target"\n' in y + "\n" and "    view_margin: -0.3\n" in y + "\n"

    (job,) = build_lsprepost_section_jobs("/o", _svc(view_fit_target=True, target_patterns=["*PKG*"]), None)
    assert job["part_pattern"] == "*PKG*" and job["view_fit"] == "target"

    (job,) = build_lsprepost_section_jobs("/o", _svc(view_fit_target=True), None)      # 타겟 없음 — 맞출 것이 없다
    assert "view_fit" not in job and "view_margin" not in job


def test_fit_is_off_by_default_and_yaml_is_unchanged():
    assert SVC().view_fit_target is False and SVC().view_margin == -0.3
    assert RenderConfig().view_fit_target is False and RenderConfig().view_margin == -0.3
    for sv in (_svc(target_part_ids=[6]), _svc(target_patterns=["*PKG*"]), _svc(per_part_render=True)):
        for job in build_lsprepost_section_jobs("/o", sv, [5, 6]):
            assert "view_fit" not in job and "view_margin" not in job
    for rc in (RenderConfig(part_pattern="*PKG*"), RenderConfig(per_part_render=True)):
        for job in build_render_jobs("/d3", "/o", rc, [5, 6]):
            assert "view_fit" not in job and "view_margin" not in job
    y = R._build_yaml(Path("/d3"), Path("/o"), RenderConfig(lsprepost_path="/l/lsprepost"), None, 1,
                      section_view_config=_svc(target_part_ids=[6], per_part_render=True))
    assert "view_fit" not in y and "view_margin" not in y


@pytest.mark.parametrize("margin, text", [(0.0, "view_margin: 0.0"), (-1.5, "view_margin: -1.5"), (0.25, "view_margin: 0.25")])
def test_margin_is_written_as_given(margin, text):
    (job,) = build_lsprepost_section_jobs("/o", _svc(view_fit_target=True, view_margin=margin, target_part_ids=[6]), None)
    assert text in R._dict_to_yaml(job, indent=2)


def test_per_part_section_jobs_get_fit_keys():
    jobs = build_lsprepost_section_jobs("/o", _svc(view_fit_target=True, per_part_render=True), [5, 6])
    by = {j["name"]: j for j in jobs}
    assert "view_fit" not in by["section_view_z"]                            # 개관은 타겟이 없다
    assert by["section_view_part_5_z"]["view_fit"] == "target" and by["section_view_part_6_z"]["view_fit"] == "target"


def test_legacy_jobs_get_fit_keys_only_with_a_target():
    rc = RenderConfig(view_fit_target=True, view_margin=-0.5, section_axes=["z"], per_part_render=True)
    by = {j["name"]: j for j in build_render_jobs("/d3", "/o", rc, [5])}
    assert "view_fit" not in by["overview_z"]                                # 패턴이 없으면 개관은 모델 전체
    assert by["part_5_z"]["view_fit"] == "target" and by["part_5_z"]["view_margin"] == -0.5
    assert by["part_5_z"]["parts"] == [5] and by["part_5_z"]["output"]["filename"] == "part_5_z"   # 나머지는 그대로

    rc = RenderConfig(view_fit_target=True, section_axes=["z"], part_pattern="*PKG*")
    (job,) = build_render_jobs("/d3", "/o", rc, None)
    assert job["part_pattern"] == "*PKG*" and job["view_fit"] == "target" and job["view_margin"] == -0.3


def test_build_yaml_puts_fit_on_overview_jobs_only():
    rc = RenderConfig(lsprepost_path="/l/lsprepost")
    y = R._build_yaml(Path("/d3"), Path("/o"), rc, None, 1,
                      section_view_config=_svc(view_fit_target=True, view_margin=-0.1, target_part_ids=[6],
                                               per_part_render=True, axes=["x", "z"]))
    assert y.count('view_fit: "target"') == 2 and y.count("view_margin: -0.1") == 2      # 개관 두 축
    head, _, tail = y.partition("part_section_renders:")
    assert tail and "view_fit" not in tail                    # 파트별 영상(원래 그 파트에 맞춘다)에는 달지 않는다
    # 소프트웨어 단면은 이 옵션과 무관하다 — 타겟이 있으면 원래 그 상자에 맞춘다
    y = R._build_yaml(Path("/d3"), Path("/o"), rc, None, 1,
                      section_view_config=_svc(backend="software", view_fit_target=True, target_part_ids=[6]))
    assert "view_fit" not in y and "view_margin" not in y


# ── CLI ────────────────────────────────────────────────────────────────────
def test_cli_defaults_and_values():
    p = _parser()
    a = p.parse_args(["x"])
    assert a.view_fit is None and a.view_margin is None                       # 안 줌 — 설정 파일이 채울 수 있다
    a = p.parse_args(["x", "--view-fit", "target", "--view-margin", "-0.5"])
    assert a.view_fit == "target" and a.view_margin == -0.5
    assert p.parse_args(["x", "--view-margin=-0.5"]).view_margin == -0.5      # 자동화 셸이 쓰는 꼴
    assert p.parse_args(["x", "--view-margin", "0"]).view_margin == 0.0
    assert p.parse_args(["x", "--view-margin", "0.49"]).view_margin == 0.49


@pytest.mark.parametrize("argv", [
    ["--view-margin", "0.5"],          # 0.5 부터는 맞춤 사각형이 뒤집힌다
    ["--view-margin", "2"],
    ["--view-margin", "nan"],
    ["--view-margin", "inf"],
    ["--view-margin=-inf"],
    ["--view-margin", "wide"],
    ["--view-fit", "box"],
    ["--view-fit", "Target"],
])
def test_cli_rejects_bad_values(argv, capsys):
    with pytest.raises(SystemExit):
        _parser().parse_args(["x", *argv])
    assert argv[0].split("=")[0] in capsys.readouterr().err                   # 어느 옵션이 틀렸는지 말한다


def test_apply_view_fit_sets_both_configs(capsys):
    from koo_deep_report.__main__ import _apply_view_fit
    rc, sv = RenderConfig(), _svc()
    assert _apply_view_fit(argparse.Namespace(view_fit="target", view_margin=-0.1), rc, sv) is True
    assert rc.view_fit_target and sv.view_fit_target and rc.view_margin == -0.1 and sv.view_margin == -0.1
    assert "카메라 맞춤: 타겟(여백 -0.1)" in capsys.readouterr().out

    rc, sv = RenderConfig(), _svc()
    assert _apply_view_fit(argparse.Namespace(view_fit="target", view_margin=None), rc, None) is True
    assert rc.view_fit_target and rc.view_margin == -0.3 and not sv.view_fit_target      # sv 는 안 넘겼다

    for ns in (argparse.Namespace(), argparse.Namespace(view_fit=None, view_margin=None),
               argparse.Namespace(view_fit="model", view_margin=0.2)):
        rc, sv = RenderConfig(), _svc()
        capsys.readouterr()
        assert _apply_view_fit(ns, rc, sv) is False
        assert not rc.view_fit_target and not sv.view_fit_target
        assert capsys.readouterr().out == ""                                  # 끄면 조용하다
    assert rc.view_margin == 0.2 and sv.view_margin == 0.2                     # 여백만 준 것은 안내가 알아본다


# ── single · batch 가 같은 옵션을 같게 싣는다 ─────────────────────────────────
class _Stop(Exception):
    """분석기를 부르기 직전에 멈추는 표식 — 그때까지 만들어진 렌더 설정만 본다."""


def _configs_reaching_analysis(monkeypatch, tmp_path, run, *argv):
    from koo_deep_report import __main__ as M
    seen = {}

    def _capture(**kw):
        seen.update(kw)
        raise _Stop

    sim = types.SimpleNamespace(path=tmp_path, d3plot=tmp_path / "d3plot", glstat=None, binout=None,
                                tier_label="T", normal_termination=True, termination_source="시험",
                                can_analyze=True)
    monkeypatch.setattr(M, "find_files", lambda d: sim)
    monkeypatch.setattr(M, "_apply_video_hide", lambda *a, **k: [])       # 바닥 판별은 d3plot 을 읽는다
    monkeypatch.setattr(M, "_build_hotspot_config", lambda *a, **k: None)
    monkeypatch.setattr(M, "run_analysis", _capture)
    args = _parser().parse_args([str(tmp_path), "--output", str(tmp_path / "out"), *argv])
    with pytest.raises(_Stop):
        run(M, sim, args)
    return seen["render_config"], seen["section_view_config"]


_RUNNERS = {
    "single": lambda M, sim, args: M.run_single(args),
    "batch": lambda M, sim, args: M._run_one(sim, Path(args.output), args),
}


@pytest.mark.parametrize("mode", sorted(_RUNNERS))
def test_single_and_batch_both_carry_the_option(monkeypatch, tmp_path, mode):
    rc, sv = _configs_reaching_analysis(
        monkeypatch, tmp_path, _RUNNERS[mode],
        "--section-view", "--section-view-target-ids", "6", "--view-fit", "target", "--view-margin=-0.1")
    assert sv.view_fit_target is True and sv.view_margin == -0.1 and sv.target_part_ids == [6]
    assert rc.view_fit_target is True and rc.view_margin == -0.1


@pytest.mark.parametrize("mode", sorted(_RUNNERS))
def test_single_and_batch_leave_it_off_by_default(monkeypatch, tmp_path, mode):
    rc, sv = _configs_reaching_analysis(monkeypatch, tmp_path, _RUNNERS[mode], "--part-pattern", "*PKG*")
    assert sv is None and rc.view_fit_target is False and rc.view_margin == -0.3


# ── 설정 파일 ───────────────────────────────────────────────────────────────
def _from_config(tmp_path, body, *argv):
    from koo_deep_report.__main__ import _apply_config_to_args
    cfg = tmp_path / "a.yaml"
    cfg.write_text(body, encoding="utf-8")
    a = _parser().parse_args(["x", "--config", str(cfg), *argv])
    _apply_config_to_args(a)
    return a


@pytest.mark.parametrize("body", [
    "view_fit: target\nview_margin: -0.1\n",                                  # 맨 위
    "section_view:\n  enabled: true\n  view_fit: target   # 타겟에 맞춘다\n  view_margin: -0.1\n",
    'render_jobs:\n  - name: "a"\n    view_fit: "Target"\n    view_margin: "-0.1"\n',      # 분석기 YAML 꼴 · 따옴표 · 대문자
])
def test_config_file_fills_fit_and_margin(tmp_path, body):
    a = _from_config(tmp_path, body)
    assert a.view_fit == "target" and a.view_margin == -0.1


def test_cli_beats_config_file(tmp_path):
    body = "view_fit: target\nview_margin: -0.1\n"
    a = _from_config(tmp_path, body, "--view-fit", "model", "--view-margin", "-0.3")
    assert a.view_fit == "model" and a.view_margin == -0.3            # 기본값과 같은 값을 직접 줘도 이긴다
    a = _from_config(tmp_path, body, "--view-margin=-2")
    assert a.view_fit == "target" and a.view_margin == -2.0


def test_commented_config_line_is_not_read(tmp_path, capsys):
    a = _from_config(tmp_path, "# view_fit: target\nsection_view:\n  enabled: true\n  # view_margin: -2\n")
    assert a.view_fit is None and a.view_margin is None
    assert "view_" not in capsys.readouterr().err


@pytest.mark.parametrize("body, key", [
    ("view_fit: box\n", "view_fit"),
    ("view_fit:\n", "view_fit"),                       # 빈 값
    ("view_fit: tar get\n", "view_fit"),
    ("view_margin: 0.5\n", "view_margin"),
    ("view_margin: wide\n", "view_margin"),
    ("view_margin: nan\n", "view_margin"),
])
def test_bad_config_values_are_reported_not_applied(tmp_path, capsys, body, key):
    a = _from_config(tmp_path, body)
    assert a.view_fit is None and a.view_margin is None
    err = capsys.readouterr().err
    assert f"설정 파일 {key}:" in err and "무시" in err


# ── 쓰이지 않는 조합은 실행 전에 말한다 ─────────────────────────────────────────
def test_no_note_when_fit_is_off_or_has_a_target():
    assert R._view_fit_warnings(RenderConfig(), _svc()) == []
    assert R._view_fit_warnings(RenderConfig(), None) == []
    assert R._view_fit_warnings(None, None) == []
    assert R._view_fit_warnings(RenderConfig(), _svc(view_fit_target=True, target_part_ids=[6])) == []
    assert R._view_fit_warnings(RenderConfig(), _svc(view_fit_target=True, target_patterns=["*PKG*"])) == []
    assert R._view_fit_warnings(RenderConfig(view_fit_target=True, part_pattern="*PKG*"), None) == []
    assert R._view_fit_warnings(RenderConfig(view_fit_target=True, per_part_render=True), None) == []
    # 영상을 만들지 않는 실행 — 할 말이 없다
    assert R._view_fit_warnings(RenderConfig(enabled=False, view_fit_target=True), None) == []
    assert R._view_fit_warnings(RenderConfig(enabled=False, view_fit_target=True), _svc(enabled=False)) == []


def test_notes_for_combinations_where_fit_cannot_apply(capsys):
    (w,) = R._view_fit_warnings(RenderConfig(), _svc(view_fit_target=True))
    assert w.startswith("[설정] --view-fit target") and "--section-view-target-ids" in w
    assert f"[koo_deep_report] {w}" in capsys.readouterr().err                 # 실행 전에 단말에도 나온다

    (w,) = R._view_fit_warnings(RenderConfig(), _svc(view_fit_target=True, backend="software", target_part_ids=[6]))
    assert w.startswith("[설정] --view-fit target") and "LS-PrePost 영상에만" in w
    (w,) = R._view_fit_warnings(RenderConfig(), _svc(view_fit_target=True, backend="software"))
    assert "LS-PrePost 영상에만" in w                                          # 소프트웨어면 타겟 유무와 무관하게 한 줄

    (w,) = R._view_fit_warnings(RenderConfig(view_fit_target=True), None)      # 단면뷰를 끈 예전 경로
    assert w.startswith("[설정] --view-fit target") and "--part-pattern" in w and "--per-part-render" in w
    (w,) = R._view_fit_warnings(RenderConfig(view_fit_target=True), _svc(enabled=False))
    assert "--part-pattern" in w

    # 단면뷰가 켜져 있으면 그 설정을 본다 — 예전 경로의 --part-pattern 은 쓰이지 않으니 타겟으로 치지 않는다
    (w,) = R._view_fit_warnings(RenderConfig(view_fit_target=True, part_pattern="*PKG*"), _svc(view_fit_target=True))
    assert "--section-view-target-ids" in w


def test_margin_without_fit_is_reported():
    (w,) = R._view_fit_warnings(RenderConfig(), _svc(view_margin=0.2))
    assert w == "[설정] --view-margin 0.2 은 --view-fit target 과 함께일 때만 쓰인다"
    (w,) = R._view_fit_warnings(RenderConfig(view_margin=-1.0), None)
    assert "--view-margin -1" in w
    assert R._view_fit_warnings(RenderConfig(view_margin=-0.3), _svc(view_margin=-0.3)) == []


def test_existing_option_notes_are_unchanged_by_fit():
    assert R._ignored_option_warnings(RenderConfig(view_fit_target=True), _svc(view_fit_target=True)) == []
    w = R._ignored_option_warnings(RenderConfig(per_part_render=True, part_pattern="*PKG*", view_fit_target=True),
                                   _svc(view_fit_target=True, target_part_ids=[6]))
    assert len(w) == 2 and not any("view-fit" in x for x in w)


def test_run_analysis_carries_the_note_into_the_report(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "find_unified_analyzer", lambda d=None: Path("/bin/true"))
    monkeypatch.setattr(R, "_run_ua", lambda ua, y, v: None)
    monkeypatch.setattr(R, "_parse_outputs", lambda out, parse_motion=True, series=None: D3plotResult(
        metadata={}, stress=[], strain=[], acceleration=[], motion={}))
    res = R.run_analysis(Path("/d3"), tmp_path, RenderConfig(lsprepost_path="/l/lsprepost"), None,
                         section_view_config=_svc(view_fit_target=True))
    assert [w for w in res.render_warnings if w.startswith("[설정] --view-fit target")]
    res = R.run_analysis(Path("/d3"), tmp_path, RenderConfig(lsprepost_path="/l/lsprepost"), None,
                         section_view_config=_svc(view_fit_target=True, target_part_ids=[6]))
    assert res.render_warnings == []


# ── 분석기가 걸지 않은 영상 — 그 줄을 건진다 ─────────────────────────────────────
def test_declined_lines_become_one_note():
    assert R._view_fit_declined("") is None
    assert R._view_fit_declined(f"  Preparing: section_view_z\n{FIT_OK}\n") is None        # 건 것은 말할 것이 없다
    w = R._view_fit_declined(f"  Preparing: a\n{NO_VISIBLE}\n  Preparing: b\n{NO_VISIBLE}\n  Preparing: c\n{FIT_OK}\n")
    assert w == ("[설정] --view-fit target 이 영상 2개에 걸리지 않았다(모델 전체에 맞췄다) — "
                 "보이는 타겟이 없다(모두 숨김 대상이거나 모델에 없는 번호)")                # 같은 까닭은 한 번만
    w = R._view_fit_declined(f"{NO_VISIBLE}\r\n{NO_TARGET}\r\n")                           # 줄 끝이 달라도
    assert "영상 2개" in w and w.endswith("보이는 타겟이 없다(모두 숨김 대상이거나 모델에 없는 번호) · 타겟 파트가 없다")


@pytest.mark.skipif(not CPP.exists(), reason="C++ 소스 없음(설치본에서 돌리는 중)")
def test_analyzer_still_prints_the_line_this_module_reads():
    src = CPP.read_text(encoding="utf-8")
    assert f'"    {R._VIEW_FIT_HEAD} "' in src                                 # 머리 — 건 줄 · 안 건 줄 공통
    assert f'" {R._VIEW_FIT_DECLINED_TAIL}"' in src                            # 꼬리 — 안 건 줄만
    for line in (NO_VISIBLE, NO_TARGET):                                       # 시험이 쓰는 까닭 문구도 소스에 있다
        reason = line.split(R._VIEW_FIT_HEAD)[1].split(R._VIEW_FIT_DECLINED_TAIL)[0].strip()
        assert f'"{reason}"' in src


def _fake_ua(tmp_path: Path, rc: int, stdout: str = "", stderr: str = "") -> Path:
    exe = tmp_path / "unified_analyzer"
    exe.write_text(
        "#!/bin/sh\n"
        f"cat <<'EOF'\n{stdout}\nEOF\n"
        f"cat >&2 <<'EOF'\n{stderr}\nEOF\n"
        f"exit {rc}\n",
        encoding="utf-8",
    )
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


def test_run_ua_returns_the_note_when_the_run_succeeded(tmp_path):
    ua = _fake_ua(tmp_path, 0, stdout=f"  Preparing: section_view_z\n{NO_VISIBLE}\n[RENDER] All render jobs completed successfully.")
    w = R._run_ua(ua, "version: 2.0\n", verbose=False)
    assert w is not None and w.startswith("[설정] --view-fit target 이 영상 1개")
    ok = _fake_ua(tmp_path, 0, stdout=f"  Preparing: section_view_z\n{FIT_OK}")
    assert R._run_ua(ok, "version: 2.0\n", verbose=False) is None


def test_run_ua_keeps_the_note_beside_a_render_failure(tmp_path):
    ua = _fake_ua(tmp_path, 3, stdout=f"{NO_VISIBLE}\n    FAILED: section_view_z [z center] - LSPrePost exited with code 134")
    w = R._run_ua(ua, "version: 2.0\n", verbose=False)
    assert w.startswith("unified_analyzer 렌더 일부 실패 (rc=3)")              # 제목은 실패 쪽 — '[설정]' 으로 시작하지 않는다
    assert "FAILED: section_view_z" in w and "--view-fit target 이 영상 1개에 걸리지 않았다" in w
