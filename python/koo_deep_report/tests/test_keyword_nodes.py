# 키워드 덱 *NODE 리더와 원본↔런 덱 좌표 변환 추정을 검증하는 시험
"""`koo_deep_report.core.keyword_nodes` 시험.

실데이터 대조는 별도로 했다 — `DropSet.k` 노드 31,176개가 d3plot 초기 형상과
ID 전부 일치, 좌표 최대 차이 5.4e-06(단정밀도). 여기서는 형식 변형과 경계를 본다.
"""
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

from koo_deep_report.core.keyword_nodes import (
    read_nodes, find_scenario_model, find_run_deck, deck_transform,
)
from koo_deep_report.core.campaign_metrics import collect_campaign, RUN_COLUMNS
from koo_deep_report.campaign_cli import main as cli_main

fails = []


def chk(name, got, want, tol=0.0):
    if tol:
        ok = got is not None and want is not None and abs(got - want) <= tol
    else:
        ok = got == want
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"  {'OK ' if ok else 'NG '} {name}")


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


def fixed(nid, x, y, z, w=(8, 16, 16, 16)):
    return (f"{nid:>{w[0]}d}{x:>{w[1]}.8f}{y:>{w[2]}.8f}{z:>{w[3]}.8f}")


tmp = Path(tempfile.mkdtemp(prefix="kwn_"))
try:
    print("[1] 고정폭 *NODE (I8, 3×E16) + CRLF + 주석")
    p = tmp / "a.k"
    p.write_bytes(("*KEYWORD\r\n$ 주석\r\n*NODE\r\n"
                   + fixed(1, 1.5, 2.5, 3.5) + "\r\n"
                   + "$$ NID X Y Z\r\n"
                   + fixed(2, -10.0, 0.0, 7.25) + "      0.0     0.0\r\n"
                   + "*ELEMENT_SOLID\r\n"
                   + "       1       1       1       2       3       4\r\n"
                   + "*END\r\n").encode())
    nt = read_nodes(p)
    chk("노드 2개 (요소 줄은 노드로 읽지 않는다)", len(nt.nodes), 2)
    chk("노드 1 좌표", nt.nodes.get(1), (1.5, 2.5, 3.5))
    chk("노드 2 좌표 (TC/RC 열 무시)", nt.nodes.get(2), (-10.0, 0.0, 7.25))
    chk("해석 실패 줄 0", nt.bad_lines, 0)

    print("[2] 붙어 있는 과학표기 — 고정폭이어야만 읽힌다")
    p = tmp / "b.k"
    # 16폭을 꽉 채운 값이 공백 없이 붙어 있다 — 공백 분리로는 토큰 1개라 못 읽는다
    fields = ["-2.300000000e+01", "5.1000000000e+01", "-1.100000000e+00"]
    assert all(len(f) == 16 for f in fields)
    p.write_text("*NODE\n       7" + "".join(fields) + "\n", encoding="utf-8")
    chk("공백 없이 붙은 16폭 필드", read_nodes(p).nodes.get(7), (-23.0, 51.0, -1.1))

    print("[3] 접미사 % (I10) · + (I20, E20)")
    p = tmp / "c.k"
    p.write_text("*NODE %\n" + fixed(1234567890, 1.0, 2.0, 3.0, (10, 16, 16, 16)) + "\n"
                 "*NODE +\n" + fixed(98765, 4.0, 5.0, 6.0, (20, 20, 20, 20)) + "\n",
                 encoding="utf-8")
    nt = read_nodes(p)
    chk("% 형식", nt.nodes.get(1234567890), (1.0, 2.0, 3.0))
    chk("+ 형식", nt.nodes.get(98765), (4.0, 5.0, 6.0))

    print("[4] 자유형식 (쉼표·공백)")
    p = tmp / "d.k"
    p.write_text("*NODE\n5, 1.0, 2.0, 3.0\n   6   4.5   5.5   6.5\n", encoding="utf-8")
    nt = read_nodes(p)
    chk("쉼표", nt.nodes.get(5), (1.0, 2.0, 3.0))
    chk("공백", nt.nodes.get(6), (4.5, 5.5, 6.5))

    print("[5] 해석 못 하는 줄은 세고 사유를 남긴다")
    p = tmp / "e.k"
    p.write_text("*NODE\nabc def\n" + fixed(1, 0, 0, 0) + "\n", encoding="utf-8")
    nt = read_nodes(p)
    chk("정상 줄은 읽는다", len(nt.nodes), 1)
    chk("실패 줄 1", nt.bad_lines, 1)
    chkb("사유가 있다", "해석하지 못했습니다" in nt.note)

    print("[6] *INCLUDE — 상대경로 · 순환 · 없는 파일")
    sub = tmp / "inc"
    sub.mkdir()
    (sub / "nodes.k").write_text("*NODE\n" + fixed(100, 9, 9, 9) + "\n"
                                 "*INCLUDE\n../main.k\n", encoding="utf-8")   # 순환
    (tmp / "main.k").write_text("*INCLUDE\ninc/nodes.k\n*INCLUDE\nnope.k\n"
                                "*NODE\n" + fixed(1, 1, 1, 1) + "\n", encoding="utf-8")
    nt = read_nodes(tmp / "main.k")
    chk("include 안의 노드", nt.nodes.get(100), (9.0, 9.0, 9.0))
    chk("본문 노드", nt.nodes.get(1), (1.0, 1.0, 1.0))
    chk("순환해도 파일 2개만", len(nt.files), 2)
    chkb("없는 include 를 알린다", "파일이 없습니다" in nt.note)
    nt2 = read_nodes(tmp / "main.k", follow_includes=False)
    chkb("follow_includes=False 면 따라가지 않는다", 100 not in nt2.nodes)

    print("[6b] *PART — 텍스트 제목 · 빈 제목($) · 한 블록 여러 파트 · CRLF")
    p = tmp / "parts.k"
    p.write_bytes(("*PART\r\n"
                   "$ partname\r\n"
                   "                                                  Front\\Metal\r\n"
                   "$       ID     secid       mid\r\n"
                   "         1         1        25         0\r\n"
                   "PCB 2\r\n"
                   "         2         2        26\r\n"
                   "*PART\r\n$\r\n$$     PID     SECID       MID\r\n"
                   "        23        23        28\r\n"
                   "*SECTION_SOLID\r\n         5         1\r\n").encode())
    chk("PID 집합", read_nodes(p).parts, {1, 2, 23})
    chkb("*SECTION_SOLID 숫자 카드는 PID 로 읽지 않는다", 5 not in read_nodes(p).parts)

    print("[7] 원본 모델 찾기 (runner_config 중첩 · 상대경로)")
    camp = tmp / "camp"
    camp.mkdir()
    (camp / "Model.k").write_text("*NODE\n" + fixed(1, 0, 0, 0) + "\n", encoding="utf-8")
    (camp / "runner_config.json").write_text(
        json.dumps({"project": {"model_file": "Model.k"}}), encoding="utf-8")
    chk("중첩 + 상대경로", find_scenario_model(camp), camp / "Model.k")
    empty = tmp / "empty"
    empty.mkdir()
    chkb("없으면 None", find_scenario_model(empty) is None)
    (empty / "runner_config.json").write_text("{ broken", encoding="utf-8")
    chkb("깨진 JSON 이어도 None", find_scenario_model(empty) is None)

    print("[8] 런 덱 찾기 — 여러 개면 추측하지 않는다")
    r1 = tmp / "r1"; r1.mkdir()
    (r1 / "DropSet.k").write_text("", encoding="utf-8")
    (r1 / "other.k").write_text("", encoding="utf-8")
    chk("DropSet.k 우선", find_run_deck(r1), r1 / "DropSet.k")
    r2 = tmp / "r2"; r2.mkdir()
    (r2 / "only.key").write_text("", encoding="utf-8")
    chk("하나뿐이면 그것", find_run_deck(r2), r2 / "only.key")
    r3 = tmp / "r3"; r3.mkdir()
    (r3 / "a.k").write_text("", encoding="utf-8")
    (r3 / "b.k").write_text("", encoding="utf-8")
    chkb("여러 개면 None", find_run_deck(r3) is None)

    print("[9] 변환 추정 — 평행이동 + 회전 복원, 역변환 왕복")
    import random
    random.seed(3)
    src_pts = {i: (random.uniform(-50, 50), random.uniform(-80, 80), random.uniform(-5, 5))
               for i in range(1, 400)}
    a = math.radians(30.0)
    R = [[math.cos(a), -math.sin(a), 0.0], [math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]]
    t = (-35.5, -73.5, -4.5)
    run_pts = {i: tuple(sum(R[r][k] * p[k] for k in range(3)) + t[r] for r in range(3))
               for i, p in src_pts.items()}
    # 런 덱에는 바닥 노드가 더 있다 (원본에 없는 ID)
    run_pts.update({90000 + i: (0.0, 0.0, -100.0 - i) for i in range(20)})
    (tmp / "src.k").write_text("*NODE\n" + "\n".join(fixed(i, *p) for i, p in src_pts.items())
                               + "\n", encoding="utf-8")
    (tmp / "run.k").write_text("*NODE\n" + "\n".join(fixed(i, *p) for i, p in run_pts.items())
                               + "\n", encoding="utf-8")
    tr, note = deck_transform(tmp / "src.k", tmp / "run.k")
    chk("평행이동 x", tr.translation[0], t[0], 1e-6)
    chk("평행이동 y", tr.translation[1], t[1], 1e-6)
    chk("평행이동 z", tr.translation[2], t[2], 1e-6)
    chk("회전각 30°", tr.rotation_angle_deg, 30.0, 1e-6)
    chk("대응 = 공통 ID 399 (바닥 노드 제외)", tr.n_pairs, 399)
    back = tr.to_source(run_pts[7])
    chk("역변환 왕복 x", back[0], src_pts[7][0], 1e-6)
    chk("역변환 왕복 z", back[2], src_pts[7][2], 1e-6)
    tr2, _ = deck_transform(tmp / "src.k", tmp / "run.k", max_pairs=50)
    chk("max_pairs 로 고르게 추림", tr2.n_pairs, 50)
    chk("추려도 같은 답", tr2.translation[1], t[1], 1e-6)

    print("[10] 재번호된 덱 — 지어내지 않고 사유")
    (tmp / "renum.k").write_text("*NODE\n" + "\n".join(fixed(50000 + i, *p)
                                 for i, p in run_pts.items()) + "\n", encoding="utf-8")
    tr3, note3 = deck_transform(tmp / "src.k", tmp / "renum.k")
    chkb("ok=False", not tr3.ok)
    chkb("재번호 가능성을 말한다", "재번호" in note3)
    chkb("to_source 는 None", tr3.to_source((0, 0, 0)) is None)

    print("[11] 캠페인 수집기 배선 — 런 표 + 도면 좌표 지표")
    c = tmp / "campaign"
    (c / "analysis_results" / "Run_A").mkdir(parents=True)
    (c / "output" / "Run_A").mkdir(parents=True)
    (c / "Model.k").write_text((tmp / "src.k").read_text(encoding="utf-8")
                               + "*PART\nBoard\n         1         1         1\n",
                               encoding="utf-8")
    shutil.copy(tmp / "run.k", c / "output" / "Run_A" / "DropSet.k")
    (c / "runner_config.json").write_text(json.dumps({"model_file": "Model.k"}),
                                          encoding="utf-8")
    (c / "output" / "Run_A" / "DropSet.json").write_text(json.dumps(
        {"initial_conditions": {"orientation_euler_deg": {"roll": 0, "pitch": 0, "yaw": 0}}}),
        encoding="utf-8")
    ctr_run = run_pts[7]
    (c / "analysis_results" / "Run_A" / "analysis_result.json").write_text(json.dumps({
        "metadata": {"tool_commit": "abc"},
        "hotspot_clusters": [{"part_id": 1, "criterion": "von_mises",
                              "clusters": [{"rank": 1, "center": list(ctr_run),
                                            "stress_max": 10.0}]},
                             # 전처리가 붙인 바닥 — 원본 모델에 없는 파트
                             {"part_id": 99, "criterion": "von_mises",
                              "clusters": [{"rank": 1, "center": [0.0, 0.0, -100.0],
                                            "stress_max": 5.0}]}]}), encoding="utf-8")
    tb = collect_campaign(c, coord_transform=True)
    run = dict(zip(RUN_COLUMNS, tb.runs[0]))
    chk("런 표 ct_dy", run["ct_dy"], t[1], 1e-6)
    chk("런 표 ct_rot_deg", run["ct_rot_deg"], 30.0, 1e-6)
    chk("원본 모델 경로 기록", tb.source_model, str(c / "Model.k"))
    m = {r[10]: r[11] for r in tb.rows if r[7] == 1}
    chk("도면 좌표 x", m.get("c1_center_src_x"), src_pts[7][0], 1e-6)
    chk("도면 좌표 y", m.get("c1_center_src_y"), src_pts[7][1], 1e-6)
    m99 = {r[10] for r in tb.rows if r[7] == 99}
    chkb("원본에 없는 파트(바닥)는 도면 좌표를 내지 않는다",
         "c1_center_src_x" not in m99 and "c1_center_x" in m99)
    chk("건너뛴 파트 기록", tb.coord_skipped_parts, {99})
    tb0 = collect_campaign(c)
    chkb("요청 안 하면 계산하지 않는다", all(v is None for v in tb0.runs[0][-7:])
         and "c1_center_src_x" not in {r[10] for r in tb0.rows})
    chk("열 개수 일치", len(tb.runs[0]), len(RUN_COLUMNS))

    print("[11b] 원본에 *PART 가 없으면 도면 좌표를 내지 않는다")
    shutil.copy(tmp / "src.k", c / "Model.k")          # *PART 없는 판
    tb3 = collect_campaign(c, coord_transform=True)
    chkb("도면 좌표 없음", "c1_center_src_x" not in {r[10] for r in tb3.rows})
    chkb("사유가 있다", "*PART 를 읽지 못해" in tb3.coord_note)
    chkb("변환 자체는 구한다", tb3.runs[0][RUN_COLUMNS.index("ct_dy")] is not None)

    print("[12] 원본 모델이 없으면 사유 · 런 표는 빈 칸")
    (c / "runner_config.json").write_text("{}", encoding="utf-8")
    tb2 = collect_campaign(c, coord_transform=True)
    chkb("사유가 있다", "원본 모델을 찾지 못했습니다" in tb2.coord_note)
    chkb("변환 열은 비어 있다", all(v is None for v in tb2.runs[0][-7:]))

    print("[13] CLI — 런이 없으면 기존 파일을 덮어쓰지 않는다")
    keep = tmp / "keep.tsv"
    keep.write_text("기존 결과", encoding="utf-8")
    rc = cli_main([str(tmp / "nope"), "-o", str(keep)])
    chk("exit 1", rc, 1)
    chk("기존 파일 보존", keep.read_text(encoding="utf-8"), "기존 결과")

    print("[14] 에러를 내지 않는가")
    for name, fn in [
        ("read: None", lambda: read_nodes(None)),
        ("read: 없는 파일", lambda: read_nodes(tmp / "zz.k")),
        ("read: 디렉토리", lambda: read_nodes(tmp)),
        ("find_model: None", lambda: find_scenario_model(None)),
        ("find_model: 파일", lambda: find_scenario_model(tmp / "src.k")),
        ("find_deck: None", lambda: find_run_deck(None)),
        ("transform: None 들", lambda: deck_transform(None, None)),
        ("transform: max_pairs 문자열", lambda: deck_transform(tmp / "src.k", tmp / "run.k",
                                                               max_pairs="x")),
    ]:
        try:
            fn()
            print(f"  OK  예외 없음: {name}")
        except Exception as e:      # noqa: BLE001
            fails.append(f"예외 발생: {name} → {type(e).__name__}: {e}")
            print(f"  NG  예외 발생: {name} → {type(e).__name__}: {e}")
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
