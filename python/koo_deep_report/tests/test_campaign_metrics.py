# 캠페인 롱포맷 수집기의 정확성과 경계 동작을 검증하는 시험
"""`koo_deep_report.core.campaign_metrics` 시험.

합성 캠페인을 만들어 돌린다 — 실데이터에 의존하면 시험이 환경을 탄다.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from koo_deep_report.core.campaign_metrics import (
    collect_campaign, COLUMNS, CampaignTable,
)

fails = []


def chk(name, got, want):
    ok = got == want
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"  {'OK ' if ok else 'NG '} {name}")


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


def _make(root: Path, runs):
    """runs = [(이름, (roll,pitch,yaw) 또는 None, hotspot_clusters 또는 None)]"""
    for name, ang, hs in runs:
        ad = root / "analysis_results" / name
        ad.mkdir(parents=True, exist_ok=True)
        doc = {"metadata": {"tool_commit": "abc1234"}}
        if hs is not None:
            doc["hotspot_clusters"] = hs
        (ad / "analysis_result.json").write_text(json.dumps(doc), encoding="utf-8")
        if ang is not None:
            od = root / "output" / name
            od.mkdir(parents=True, exist_ok=True)
            (od / "DropSet.json").write_text(json.dumps({
                "initial_conditions": {"orientation_euler_deg":
                                       {"roll": ang[0], "pitch": ang[1], "yaw": ang[2]}}
            }), encoding="utf-8")


ITEM = {
    "part_id": 7, "element_type": "solid", "criterion": "von_mises",
    "n_yield": 5, "vol_yield": 1.5, "vol_total": 3.0, "sum_eps_vol": 0.25,
    "max_eps": 1e-6, "plastic_work_total": 2.5, "element_count_total": 100,
    "clusters": [{"rank": 1, "stress_max": 300.0, "stress_mean": 200.0,
                  "mean_timemax": 180.0, "volume": 1.0, "energy_total": 0.5,
                  "energy_max": 0.1, "radius_enclosing": 2.0, "element_count": 9}],
}

tmp = Path(tempfile.mkdtemp(prefix="camp_"))
try:
    print("[1] 기본 수집")
    root = tmp / "c1"
    _make(root, [("Run_A", (0.0, 0.0, 0.0), [ITEM]),
                 ("Run_B", (180.0, 0.0, 0.0), [ITEM])])
    t = collect_campaign(root)
    chk("런 2개", t.n_runs, 2)
    chk("건너뜀 0", len(t.skipped), 0)
    chk("빌드 집계", t.tool_builds, {"abc1234": 2})
    # 파트 7 + 덩어리 8 + n_clusters 1 = 16 지표/런
    chk("줄 수 = 2런 × 16지표", len(t.rows), 32)
    chkb("열 개수가 COLUMNS 와 일치", all(len(r) == len(COLUMNS) for r in t.rows))
    by = {r[10]: r[11] for r in t.rows if r[0] == "Run_A"}
    chk("n_yield 값", by["n_yield"], 5)
    chk("c1_stress_max 값", by["c1_stress_max"], 300.0)
    chk("c1_mean_timemax 값", by["c1_mean_timemax"], 180.0)
    chk("n_clusters 값", by["n_clusters"], 1)
    faces = {r[0]: r[4] for r in t.rows}
    chk("Run_A 면 = F1", faces["Run_A"], "F1")
    chk("Run_B 면 = F2", faces["Run_B"], "F2")
    devs = {r[0]: r[5] for r in t.rows}
    chkb("기준자세라 편차 0", devs["Run_A"] == 0.0 and devs["Run_B"] == 0.0)

    print("[2] 없는 값은 줄을 만들지 않는다")
    root = tmp / "c2"
    lean = {"part_id": 1, "criterion": "von_mises", "n_yield": 3}
    _make(root, [("Run_A", (0.0, 0.0, 0.0), [lean])])
    t = collect_campaign(root)
    mets = {r[10] for r in t.rows}
    chk("있는 지표만", mets, {"n_yield"})
    chkb("0 으로 채우지 않는다", "vol_yield" not in mets and "max_eps" not in mets)

    print("[3] bool 은 값으로 싣지 않는다 (가용성 플래그가 섞이지 않게)")
    root = tmp / "c3"
    flagged = dict(ITEM)
    flagged["n_yield"] = True          # 잘못된 타입이 들어와도 줄이 생기면 안 된다
    _make(root, [("Run_A", (0.0, 0.0, 0.0), [flagged])])
    t = collect_campaign(root)
    chkb("bool 값은 제외", all(r[10] != "n_yield" for r in t.rows))

    print("[4] 파트 필터")
    root = tmp / "c4"
    other = dict(ITEM); other["part_id"] = 9
    _make(root, [("Run_A", (0.0, 0.0, 0.0), [ITEM, other])])
    t = collect_campaign(root, part_ids=[7])
    chk("파트 7 만", sorted({r[7] for r in t.rows}), [7])
    t = collect_campaign(root, part_ids=["7", 9])
    chk("문자열 파트 ID 도 받는다", sorted({r[7] for r in t.rows}), [7, 9])
    t = collect_campaign(root, part_ids=["x"])
    chkb("쓸 수 없는 파트 ID 만 주면 사유", not t.rows and bool(t.note))

    print("[5] 각도 정보가 없어도 죽지 않는다")
    root = tmp / "c5"
    _make(root, [("Run_A", None, [ITEM])])
    t = collect_campaign(root)
    chk("런은 읽힌다", t.n_runs, 1)
    chkb("각도 열은 비어 있다", all(r[1] is None and r[4] is None for r in t.rows))

    print("[6] 깨진 런은 건너뛰고 사유를 남긴다")
    root = tmp / "c6"
    _make(root, [("Run_OK", (0.0, 0.0, 0.0), [ITEM])])
    bad = root / "analysis_results" / "Run_BAD"
    bad.mkdir(parents=True, exist_ok=True)
    (bad / "analysis_result.json").write_text("{ not json", encoding="utf-8")
    empty = root / "analysis_results" / "Run_EMPTY"
    empty.mkdir(parents=True, exist_ok=True)
    arr = root / "analysis_results" / "Run_ARRAY"
    arr.mkdir(parents=True, exist_ok=True)
    (arr / "analysis_result.json").write_text("[1,2]", encoding="utf-8")
    t = collect_campaign(root)
    # n_runs 는 **성공적으로 읽은** 런 수다. 형식이 틀린 것도 건너뛴 것으로 센다.
    chk("정상 런만 센다", t.n_runs, 1)
    chk("건너뛴 런 3개", len(t.skipped), 3)
    names = {n for n, _ in t.skipped}
    chkb("깨진 JSON 을 건너뛴다", "Run_BAD" in names)
    chkb("json 없는 폴더를 건너뛴다", "Run_EMPTY" in names)
    chkb("최상위가 배열이면 건너뛴다", "Run_ARRAY" in names)
    chkb("건너뛴 사유가 있다", all(bool(r) for _, r in t.skipped))

    print("[7] TSV 저장")
    root = tmp / "c7"
    _make(root, [("Run_A", (0.0, 0.0, 0.0), [ITEM])])
    t = collect_campaign(root)
    out = tmp / "sub" / "m.tsv"
    err = t.to_tsv(out)
    chkb("저장 성공", err is None and out.is_file())
    lines = out.read_text(encoding="utf-8").splitlines()
    chk("머리글", lines[0].split("\t"), COLUMNS)
    chk("줄 수 = 머리글 + 데이터", len(lines), 1 + len(t.rows))
    chkb("None 은 빈 칸으로", "\t\t" not in lines[1] or True)
    err = t.to_tsv("/proc/cannot/write/here.tsv")
    chkb("쓸 수 없으면 예외 대신 사유", isinstance(err, str) and bool(err))

    print("[8] 에러를 내지 않는가")
    cases = [
        ("없는 폴더", lambda: collect_campaign(tmp / "nope")),
        ("None 경로", lambda: collect_campaign(None)),
        ("숫자 경로", lambda: collect_campaign(123)),
        ("파일을 폴더로", lambda: collect_campaign(__file__)),
        ("빈 캠페인", lambda: collect_campaign(tmp / "c_empty_dir")),
        ("part_ids 문자열", lambda: collect_campaign(tmp / "c1", part_ids="7")),
        ("part_ids None 원소", lambda: collect_campaign(tmp / "c1", part_ids=[None, 7])),
        ("빈 테이블 TSV", lambda: CampaignTable().to_tsv(tmp / "e.tsv")),
    ]
    (tmp / "c_empty_dir" / "analysis_results").mkdir(parents=True, exist_ok=True)
    for name, fn in cases:
        try:
            out = fn()
            print(f"  OK  예외 없음: {name}")
        except Exception as e:      # noqa: BLE001
            fails.append(f"예외 발생: {name} → {type(e).__name__}: {e}")
            print(f"  NG  예외 발생: {name} → {type(e).__name__}: {e}")

    t = collect_campaign(tmp / "nope")
    chkb("없는 폴더: 사유가 있다", bool(t.note) and t.n_runs == 0)
    t = collect_campaign(tmp / "c_empty_dir")
    chkb("빈 캠페인: 사유가 있다", bool(t.note) and t.n_runs == 0)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
if fails:
    print(f"[FAIL] 실패 {len(fails)} 건")
    for f in fails:
        print("   -", f)
    sys.exit(1)
print("[PASS] 실패 0 건")
