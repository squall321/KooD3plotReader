# 리포트 조립과 CLI 가 합성 캠페인에서 끝까지 도는지 검증하는 시험
"""`koo_scatter_report` 통합 시험.

핵심은 **있을 때/없을 때** 규율이다. 데이터가 없는 그림은 자리를 남기고 사유를
적어야 하고, 값을 지어내면 안 된다.
"""
import json
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from koo_scatter_report.loader import load
from koo_scatter_report.report.html_report import build_html
from koo_scatter_report.__main__ import main as cli_main

fails = []


def chk(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


def _make_campaign(root: Path, runs):
    for name, ang, items in runs:
        ad = root / "analysis_results" / name
        ad.mkdir(parents=True, exist_ok=True)
        doc = {"metadata": {"tool_commit": "abc1234"}}
        if items is not None:
            doc["hotspot_clusters"] = items
        (ad / "analysis_result.json").write_text(json.dumps(doc), encoding="utf-8")
        od = root / "output" / name
        od.mkdir(parents=True, exist_ok=True)
        (od / "DropSet.json").write_text(json.dumps({
            "initial_conditions": {"orientation_euler_deg":
                                   {"roll": ang[0], "pitch": ang[1], "yaw": ang[2]}}
        }), encoding="utf-8")


def _item(pid, crit="von_mises", n=2, base=100.0):
    return {
        "part_id": pid, "element_type": "solid", "criterion": crit,
        "direction": "max",
        "bbox_min": [-10, -10, -5], "bbox_max": [10, 10, 5],
        "n_yield": 3, "vol_yield": 1.0, "vol_total": 5.0,
        "element_count_total": 50,
        "clusters": [
            {"rank": i + 1, "center": [i * 2.0, i * 1.0, i * 0.5],
             "radius_enclosing": 1.0 + i, "stress_max": base - i * 10,
             "stress_mean": base - i * 20, "volume": 1.0,
             "element_count": 7}
            for i in range(n)
        ],
    }


tmp = Path(tempfile.mkdtemp(prefix="scat_"))
try:
    print("[1] 캠페인 로딩")
    root = tmp / "c1"
    _make_campaign(root, [
        ("Run_A", (0.0, 0.0, 0.0), [_item(7)]),
        ("Run_B", (3.0, 0.0, 0.0), [_item(7, base=140.0)]),
        ("Run_C", (180.0, 0.0, 0.0), [_item(7, base=90.0)]),
    ])
    si = load(root)
    chk("로딩 성공", si.ok)
    chk("런 3개", si.table.n_runs == 3)
    chk("군집 항목 3개", len(si.table.items) == 3)
    chk("파트 목록", si.part_ids == [7])

    print("[2] 데이터가 없을 때 — 사유를 적고 지어내지 않는다")
    html = build_html(si, "von_mises", "c1_stress_max")
    chk("HTML 생성", html.startswith("<!DOCTYPE html>"))
    # 그림 9종 + 통계 섹션(⑤b) = 10
    chk("섹션 10개", html.count("<section>") == 10)
    chk("회수율은 불량데이터 없음을 말한다", "시험 불량 데이터가 없습니다" in html)
    chk("구간도는 정의 없음을 말한다", "구간 정의가 없습니다" in html)
    chk("외부 스크립트를 쓰지 않는다", "<script" not in html and "cdn." not in html)
    # SVG 가 전부 유효한가
    import re
    svgs = re.findall(r"<svg.*?</svg>", html, re.S)
    chk(f"SVG {len(svgs)}개 모두 유효한 XML",
        all(ET.fromstring(s) is not None for s in svgs))
    chk("SVG 9개 (통계 섹션은 표라 SVG 가 아니다)", len(svgs) == 9)

    print("[3] 불량 데이터(좌표 포함)가 있을 때")
    gt = tmp / "ng.tsv"
    gt.write_text("case\tface\tpart_id\tverdict\tx\ty\tz\n"
                  "T1\tF1\t7\tNG\t0.0\t0.0\t0.0\n", encoding="utf-8")
    si2 = load(root, gt_path=gt)
    chk("불량 데이터 로딩", si2.gt is not None and si2.gt.n_ng == 1)
    chk("좌표 인식", len(si2.gt.ng_points()) == 1)
    html2 = build_html(si2, "von_mises", "c1_stress_max")
    chk("회수율이 그려진다", "시험 불량 데이터가 없습니다" not in html2)
    chk("오버레이가 그려진다", "실물 불량 5곳" in html2 or "실물 불량 1곳" in html2)
    chk("불량 표시 색", "#00e5ff" in html2)

    print("[4] 구간 정의가 있을 때")
    seg = tmp / "seg.json"
    seg.write_text(json.dumps({"part_id": 7, "segments": [
        {"name": "Q1", "type": "box", "min": [-10, -10, -5], "max": [0, 0, 5]},
        {"name": "Q2", "type": "box", "min": [0, -10, -5], "max": [10, 10, 5]}]}),
        encoding="utf-8")
    si3 = load(root, gt_path=gt, segments_path=seg)
    html3 = build_html(si3, "von_mises", "c1_stress_max")
    chk("구간도가 그려진다", "구간 정의가 없습니다" not in html3)
    chk("구간 이름이 나온다", "Q1" in html3 and "Q2" in html3)

    print("[4b] 통계 섹션 — 귀무가설을 산출물에 적는다")
    chk("공통 파트 표본을 말한다", "런 간 공통 파트" in html)
    # 순위검정은 파트가 2개 이상이어야 성립한다 (1개면 순위에 정보가 없다).
    # 위 캠페인은 파트 7 하나뿐이라 나오지 않는 것이 **정상**이다.
    chk("파트 1개면 순위검정을 내지 않는다", "평균순위" not in html)
    root_r = tmp / "c1r"
    _make_campaign(root_r, [
        ("Run_A", (0.0, 0.0, 0.0), [_item(7, base=300.0), _item(8, base=100.0)]),
        ("Run_B", (3.0, 0.0, 0.0), [_item(7, base=310.0), _item(8, base=110.0)]),
    ])
    si_r = load(root_r)
    html_r = build_html(si_r, "von_mises", "c1_stress_max")
    chk("파트 2개면 순위검정이 나온다", "평균순위" in html_r)
    chk("귀무가설 문구가 실린다", "귀무가설" in html_r and "(N+1)/2" in html_r)
    chk("파트 7 이 1위 (항상 더 뜨겁다)", "파트 7: 평균순위 1.00" in html_r)

    print("[5] 없는 기준량·지표를 요청해도 죽지 않는다")
    html4 = build_html(si, "nonexistent_crit", "c1_stress_max")
    chk("HTML 은 나온다", html4.startswith("<!DOCTYPE html>"))
    chk("값 없음을 말한다", "값이 없습니다" in html4)

    print("[6] 군집 없는 캠페인")
    root2 = tmp / "c2"
    _make_campaign(root2, [("Run_A", (0.0, 0.0, 0.0), None)])
    si5 = load(root2)
    chk("로딩은 성공", si5.ok)
    html5 = build_html(si5, "von_mises", "c1_stress_max")
    chk("군집 없음을 말한다", "군집 데이터가 없습니다" in html5)
    # 값이 없으면 통계 섹션은 붙지 않는다 — 빈 표를 내밀지 않는다
    chk("그림 9종은 그대로", html5.count("<section>") == 9)

    print("[7] 코너 결함 캠페인은 경고한다")
    root3 = tmp / "c3"
    _make_campaign(root3, [
        ("Run_A", (45.0, 45.0, 0.0), [_item(7)]),     # 옛 코너 = off_lattice
        ("Run_B", (0.0, 0.0, 0.0), [_item(7)]),
    ])
    si6 = load(root3)
    html6 = build_html(si6, "von_mises", "c1_stress_max")
    chk("격자 벗어남을 경고한다", "격자에서 벗어난 런" in html6)

    print("[8] CLI")
    out = tmp / "r.html"
    rc = cli_main([str(root), "-o", str(out)])
    chk("CLI 성공", rc == 0 and out.is_file())
    chk("파일이 비어 있지 않다", out.stat().st_size > 5000)
    rc = cli_main([str(tmp / "nope"), "-o", str(tmp / "x.html")])
    chk("없는 캠페인은 exit 1", rc == 1)
    rc = cli_main([str(root)])          # -o 없음
    chk("출력 경로 없이도 성공", rc == 0)
    rc = cli_main([str(root), "-o", "/proc/cannot/write.html"])
    chk("쓸 수 없는 경로는 exit 2", rc == 2)

    print("[9] 에러를 내지 않는가")
    cases = [
        ("load: None", lambda: load(None)),
        ("load: 숫자", lambda: load(123)),
        ("load: 없는 폴더", lambda: load(tmp / "nope")),
        ("load: 없는 gt", lambda: load(root, gt_path=tmp / "nope.tsv")),
        ("load: 없는 seg", lambda: load(root, segments_path=tmp / "nope.json")),
        ("build: part 없음", lambda: build_html(si, "von_mises", "c1_stress_max", 999)),
        ("build: 빈 지표", lambda: build_html(si, "", "")),
    ]
    for name, fn in cases:
        try:
            fn()
            print(f"  OK  예외 없음: {name}")
        except Exception as e:      # noqa: BLE001
            fails.append(f"예외 발생: {name} → {type(e).__name__}: {e}")
            print(f"  NG  예외 발생: {name} → {type(e).__name__}: {e}")

    si7 = load(root, gt_path=tmp / "nope.tsv")
    chk("없는 불량파일은 사유를 남긴다", bool(si7.note))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()


def test_all():
    """pytest 진입점 — 이 함수가 없으면 `no tests ran` 으로 조용히 지나간다."""
    assert not fails, "실패 %d 건:\n  - %s" % (len(fails), "\n  - ".join(fails))


if __name__ == "__main__":
    if fails:
        print(f"[FAIL] 실패 {len(fails)} 건")
        for f in fails:
            print("   -", f)
        sys.exit(1)
    print("[PASS] 실패 0 건")
