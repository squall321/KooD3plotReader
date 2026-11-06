# 리포트 그림(figures) 시험 — 바깥 면 · 카메라 · 색 범위 · 장면 · SVG · 차트 · 대상 고르기 · 상태 번호 · HTML 탭 · 실데이터 대조
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from koo_deep_report.figures import camera as C
from koo_deep_report.figures import charts, colors as K, mesh, pack, scene, svg
from koo_deep_report.report.models import PartTimeSeries

CUBE = np.array([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                 (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)], float)


def _normals(coords, faces):
    return scene.face_normals(coords, faces)


def _surface(coords, conn, part, vm, kind=mesh.SOLID, titles=None):
    """lasso 없이 StateSurface 를 짓는다(read_state 와 같은 길: 바깥 면 → 바깥쪽 감김)."""
    conn, part, vm = np.asarray(conn), np.asarray(part), np.asarray(vm, float)
    f, own = mesh.solid_faces(conn)
    ext = mesh.exterior(f, own, part)
    f, own = f[ext], own[ext]
    f = mesh.orient_outward(f, coords, coords[conn[own]].mean(axis=1))
    pm = {}
    for p, v in zip(part.tolist(), vm.tolist()):
        pm[p] = max(v, pm.get(p, -np.inf))
    return mesh.StateSurface(coords=coords, faces=f, face_part=part[own], face_value=vm[own],
                             face_elem=own + 1, face_kind=np.full(len(f), kind, np.int8), state_index=3,
                             time=1e-3, part_titles=titles or {}, part_max=pm)


# ── 바깥 면 ────────────────────────────────────────────────────────────────
def test_hex_has_six_outward_quads():
    s = _surface(CUBE, [[0, 1, 2, 3, 4, 5, 6, 7]], [1], [10.0])
    assert s.faces.shape == (6, 4) and (s.faces >= 0).all()
    c = CUBE.mean(axis=0)
    fc = scene.face_centers(s.coords, s.faces)
    assert (np.einsum("ij,ij->i", _normals(s.coords, s.faces), fc - c) > 0).all()


def test_tet_pattern_uses_real_four_triangles():
    coords = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)], float)
    s = _surface(coords, [[0, 1, 2, 3, 3, 3, 3, 3]], [1], [5.0])
    assert len(s.faces) == 4 and (s.faces[:, 3] == -1).all()
    # 네 면이 네 꼭짓점 조합을 하나씩 — 사면체 실제 위상(퇴화 육면체 면이 아니다)
    assert {tuple(sorted(f[:3])) for f in s.faces.tolist()} == {(0, 1, 2), (0, 1, 3), (1, 2, 3), (0, 2, 3)}
    fc = scene.face_centers(coords, s.faces)
    assert (np.einsum("ij,ij->i", _normals(coords, s.faces), fc - coords.mean(axis=0)) > 0).all()


def test_wedge_degenerate_hex_gives_two_triangles_three_quads():
    coords = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1)], float)
    s = _surface(coords, [[0, 1, 2, 2, 3, 4, 5, 5]], [1], [1.0])
    tri = (s.faces[:, 3] < 0).sum()
    assert (tri, len(s.faces) - tri) == (2, 3)


def test_shared_face_inside_a_part_is_dropped_but_kept_between_parts():
    coords = np.vstack([CUBE, CUBE[4:] + (0, 0, 1)])
    conn = [[0, 1, 2, 3, 4, 5, 6, 7], [4, 5, 6, 7, 8, 9, 10, 11]]
    assert len(_surface(coords, conn, [1, 1], [1, 2]).faces) == 10
    assert len(_surface(coords, conn, [1, 2], [1, 2]).faces) == 12


def test_environment_part_is_the_oversized_floor():
    floor = CUBE * (100, 100, 1) - (50, 50, 1)
    dev = CUBE * (10, 5, 1) + (0, 0, 0.5)
    other = CUBE * (10, 5, 1) + (0, 0, 2)
    coords = np.vstack([floor, dev, other])
    conn = [list(range(0, 8)), list(range(8, 16)), list(range(16, 24))]
    s = _surface(coords, conn, [9, 1, 2], [0, 5, 7])
    assert mesh.environment_parts(s) == [9]
    assert mesh.environment_parts(_surface(CUBE, [list(range(8))], [1], [1])) == []


def test_part_max_counts_interior_elements():
    # 3×1×1 막대의 가운데 요소가 최대 — 바깥 면은 그 요소도 갖지만, 2×2×2 의 안쪽 없는 경우 대신 직접 확인
    coords = np.array([(x, y, z) for z in (0, 1) for y in (0, 1) for x in range(4)], float)
    idx = lambda x, y, z: z * 8 + y * 4 + x  # noqa: E731
    conn = [[idx(i, 0, 0), idx(i + 1, 0, 0), idx(i + 1, 1, 0), idx(i, 1, 0),
             idx(i, 0, 1), idx(i + 1, 0, 1), idx(i + 1, 1, 1), idx(i, 1, 1)] for i in range(3)]
    s = _surface(coords, conn, [1, 1, 1], [1.0, 9.0, 2.0])
    assert s.part_max == {1: 9.0}
    assert len(s.faces) == 14


# ── 카메라 · 색 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("view", ["iso", "top", "front", "right", "iso_back"])
def test_fit_keeps_points_inside_the_free_area(view):
    pts = np.random.default_rng(0).normal(size=(500, 3)) * (30, 5, 2) + (100, -40, 7)
    d, u = C.view_basis(view)
    cam = C.fit(pts, d, u, 1600, 1100, margin=1.06, right_frac=0.15, top_frac=0.09)
    xy = cam.project(pts)[:, :2]
    assert xy[:, 0].min() >= -1 and xy[:, 0].max() <= 1600 * 0.85 + 1
    assert xy[:, 1].min() >= 1100 * 0.09 - 1 and xy[:, 1].max() <= 1100 + 1


def test_color_range_modes():
    v = np.r_[np.linspace(0, 100, 999), 4000.0]
    lo, hi = K.color_range(v, "p99.5")
    assert lo == 0 and 99 < hi < 101                       # 요소 하나의 순간 최대가 범위를 정하지 않는다
    assert K.color_range(v, "max")[1] == 4000
    assert K.color_range(v, 250.0)[1] == 250
    assert K.color_range(np.array([np.nan]), "p99.5") == (0.0, 1.0)
    with pytest.raises(ValueError):
        K.color_range(v, "median")


def test_rgb_marks_above_and_missing():
    c = K.rgb(np.array([0.0, 50.0, 150.0, np.nan]), 0, 100)
    assert tuple(c[2]) == K.ABOVE and tuple(c[3]) == K.CONTEXT
    assert not np.allclose(c[0], c[1])


def test_label_box_flips_away_from_legend_and_title():
    x0, y0, x1, y1 = K.label_box(100, 500, 80, 1600, 1100)
    assert x0 > 100 and y1 < 500                           # 기본: 오른쪽 위
    x0, y0, x1, y1 = K.label_box(1350, 60, 80, 1600, 1100)
    assert x1 < 1350 and y0 > 60                           # 범례 · 제목 띠에 걸리면 왼쪽 · 아래


# ── 장면 · SVG ─────────────────────────────────────────────────────────────
def _two_parts():
    coords = np.vstack([CUBE, CUBE + (3, 0, 0)])
    return _surface(coords, [list(range(8)), list(range(8, 16))], [1, 2], [40.0, 70.0],
                    titles={1: "Frame<&>", 2: "PKG\\PKG 1"})


def test_scene_target_context_and_peak():
    s = _two_parts()
    sc = scene.build(s, [2], None, view="iso")
    assert sc.target_mask.sum() == 6 and sc.context_mask.sum() == 6
    assert sc.peak_value == 70.0 and sc.value_max == 70.0 and not sc.peak_inside
    sc = scene.build(s, [2], [1], view="peak")
    assert sc.context_mask.sum() == 0
    with pytest.raises(ValueError):
        scene.build(s, [1], [1])                           # 타겟을 숨기면 그릴 것이 없다


def test_scene_reports_peak_inside_when_surface_is_lower():
    s = _two_parts()
    s.part_max[2] = 95.0                                   # 안쪽 요소가 더 크다
    sc = scene.build(s, [2], None)
    assert sc.value_max == 95.0 and sc.peak_value == 70.0 and sc.peak_inside


def test_svg_is_valid_culls_back_faces_and_draws_target_last(tmp_path):
    s = _two_parts()
    sc = scene.build(s, [2], None, view="iso")
    out = svg.write(sc, tmp_path / "f.svg", ["Part 2 <x> & y", "t"], {1: {"name": "Frame<&>", "value": 40.0}},
                    unit="MPa")
    root = ET.parse(out).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    paths = root.find(f"{ns}g[@id='mesh']").findall(f"{ns}path")
    parts = [p.get("data-p") for p in paths]
    assert parts.count("2") == 3 and parts.count("1") >= 1     # 닫힌 상자는 iso 에서 세 면만(주변은 화면 밖 면이 빠진다)
    assert parts == sorted(parts, key=lambda p: p == "2")      # 주변 먼저, 타겟이 맨 위
    assert all(p.get("class") == "c" for p in paths if p.get("data-p") == "1")
    txt = out.read_text(encoding="utf-8")
    assert "Frame&lt;&amp;&gt;" in txt and "<script>" in txt and 'id="tip"' in txt


def test_svg_drops_faces_outside_the_picture(tmp_path):
    coords = np.vstack([CUBE, CUBE * 0.2 + (500, 0, 0)])
    s = _surface(coords, [list(range(8)), list(range(8, 16))], [1, 2], [1.0, 2.0])
    sc = scene.build(s, [1], None, view="iso")              # 카메라는 파트 1 에 맞춘다 — 파트 2 는 화면 밖
    root = ET.parse(svg.write(sc, tmp_path / "f.svg", ["t"])).getroot()
    assert all(p.get("data-p") == "1" for p in root.iter("{http://www.w3.org/2000/svg}path"))


# ── 차트 ───────────────────────────────────────────────────────────────────
def test_line_chart_keeps_peak_and_skips_empty_series(tmp_path):
    x = np.linspace(0, 1, 5000)
    y = np.sin(x * 40)
    y[3217] = 9.0
    out = charts.line_chart(tmp_path / "l.svg", [{"name": "a", "x": x.tolist(), "y": y.tolist()},
                                                 {"name": "빈", "x": x.tolist(), "y": []}], "제목", "t", "v")
    txt = out.read_text(encoding="utf-8")
    ET.fromstring(txt)
    assert "최대 9" in txt and ">빈<" not in txt


def test_bar_chart_and_stack_are_valid_svg(tmp_path):
    b = charts.bar_chart(tmp_path / "b.svg", [{"label": "1 a<b", "value": 3.0, "severity": "CRITICAL"},
                                              {"label": "2", "value": None}], "t", "y")
    ET.parse(b)
    st = charts.stack(tmp_path / "s.svg", [charts.line_svg([], "a", "x", "y"), charts.line_svg([], "b", "x", "y")])
    root = ET.parse(st).getroot()
    assert root.get("height") == "840"


# ── 꾸러미: 상태 번호 · 대상 · 단위 ──────────────────────────────────────────
def _series(pid, n, t_max, gmax=10.0, num_points=None, unit="deck_units"):
    t = np.linspace(0, 1e-3, n)
    data = [{"time": float(tt), "max": float(gmax if abs(tt - t_max) < 1e-12 else 1.0)} for tt in t]
    return PartTimeSeries(part_id=pid, part_name="", quantity="von_mises", unit=unit, global_max=gmax,
                          global_min=0.0, time_of_max=t_max, data=data, num_points=num_points or n)


def test_state_index_from_history_and_refusals():
    t = np.linspace(0, 1e-3, 11)
    notes = []
    parts = pack._from_series([_series(1, 11, t[7]), _series(2, 11, t[3], num_points=20), _series(3, 11, t[2])],
                              {}, 11, {1: ("A", 0.8, "crit")}, notes)
    assert parts[1].state == 7 and parts[1].severity == "CRITICAL" and parts[1].sf == 0.8
    assert parts[2].state is None                          # 잘린 이력 — 순번을 믿지 않는다
    assert parts[3].state == 2
    parts = pack._from_series([_series(1, 11, t[7])], {}, 12, {}, notes)
    assert parts[1].state is None                          # 점 수 ≠ 상태 수
    assert len(notes) == 2


def _pp(pid, peak, sf=None, state=1):
    return pack.PartPeak(pid, f"P{pid}", peak, 0.0, state, sf)


def test_choose_targets_sf_first_then_peak_and_overrides():
    parts = {1: _pp(1, 500), 2: _pp(2, 50, sf=2.0), 3: _pp(3, 80, sf=0.9), 4: _pp(4, 900, state=None), 5: _pp(5, 0)}
    assert pack.choose_targets(parts, 5, None, set()) == [3, 2, 1]
    assert pack.choose_targets({k: v for k, v in parts.items() if v.sf is None}, 5, None, set()) == [1]
    assert pack.choose_targets(parts, 2, None, {3}) == [2, 1]
    assert pack.choose_targets(parts, 5, [4, 4, 1, 9], {1}) == [4, 9]


def test_units_label_rules():
    st = [SimpleNamespace(unit="deck_units")]
    assert pack._units(st, None, None)[:2] == ("", pack.DECK)
    assert pack._units([SimpleNamespace(unit="MPa")], None, None)[1] == "MPa"
    inp = pack.RunInputs(Path("x"), "r", {}, "ton-mm-s", "MPa")
    assert inp.t_text(2.5e-3) == "2.5 ms" and inp.stress_label == "MPa"
    inp = pack.RunInputs(Path("x"), "r", {}, "", pack.DECK)
    assert "deck" in inp.t_text(2.5e-3) and inp.stress_label == "deck units"


def test_cleanup_pattern_only_matches_pack_files():
    ok = ["overview_peak.png", "part_12_peak_iso.svg", "part_3_history.svg", "energy.svg", "manifest.json"]
    no = ["notes.txt", "my_part_1.png", "part_x_peak_iso.png", "overview_peak.png.bak"]
    assert all(pack._OURS.match(n) for n in ok) and not any(pack._OURS.match(n) for n in no)


# ── HTML 탭 ───────────────────────────────────────────────────────────────
def test_html_tab_appears_with_figures(tmp_path):
    from koo_deep_report.report.html_report import _figures_for_js, generate_html
    from koo_deep_report.report.models import SimInfo, SingleResult
    m = {"units": {"stress": "MPa"}, "notes": ["n"], "targets": [2],
         "figures": [{"id": "overview_peak", "camera": {"x": 1}, "caption": "c<1>",
                      "files": {"png": "overview_peak.png", "svg": "overview_peak.svg"}}]}
    js = _figures_for_js(m)
    assert "camera" not in js["figures"][0] and js["notes"] == ["n"]
    r = SingleResult(sim_info=SimInfo(path=tmp_path), figures=m)
    generate_html(r, tmp_path / "r.html")
    html = (tmp_path / "r.html").read_text(encoding="utf-8")
    assert 'data-tab="figures"' in html and "function renderFigures" in html
    r = SingleResult(sim_info=SimInfo(path=tmp_path))
    generate_html(r, tmp_path / "r2.html")
    assert 'data-tab="figures"' not in (tmp_path / "r2.html").read_text(encoding="utf-8")


# ── 실데이터(v14) — 그림의 최대가 해석기 최대와 같다 ───────────────────────────
V14 = Path("/data/koopark/Test_Postprocess_v14/output/Run_20260522_103123_7ad7d9/Output/report")


@pytest.mark.skipif(not (V14 / "analysis_result.json").exists(), reason="v14 실데이터 없음")
def test_pack_on_v14_matches_analyzer(tmp_path):
    pytest.importorskip("lasso")
    pytest.importorskip("pyvista")
    inp = pack.inputs_from_dir(V14)
    m = pack.build(inp, tmp_path, top=1, views=("iso",))
    snaps = [f for f in m["figures"] if (f.get("files") or {}).get("png")]
    assert [f["id"] for f in snaps] == ["overview_peak", "part_21_peak_iso"]
    peak = inp.parts[21].peak
    assert math.isclose(snaps[1]["value"], peak, rel_tol=1e-6)
    assert m["settings"]["hidden_parts"] == [23]
    assert not [n for n in m["notes"] if "다르다" in n]
    for f in m["figures"]:
        for name in f["files"].values():
            assert (tmp_path / name).stat().st_size > 1000
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["format"] == pack.FORMAT


def test_strip_cjk_keeps_punctuation_dejavu_can_draw():
    from koo_deep_report.figures.png import strip_cjk
    assert strip_cjk("Part 2 Wall — max 103 MPa · color 0–103") == "Part 2 Wall — max 103 MPa · color 0–103"
    assert strip_cjk("Part 7 브라켓(좌) — max 5") == "Part 7 — max 5"
