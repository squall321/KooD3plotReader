# 시험 불량 데이터 읽기와 정합(회수율) 계산을 검증하는 시험
"""`koo_deep_report.core.ground_truth` 시험."""
import shutil
import sys
import tempfile
from pathlib import Path

from koo_deep_report.core.ground_truth import (
    load_ground_truth, part_recall, REQUIRED_COLUMNS,
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


tmp = Path(tempfile.mkdtemp(prefix="gt_"))


def w(name, text):
    p = tmp / name
    p.write_text(text, encoding="utf-8")
    return p


try:
    print("[1] 정상 읽기")
    p = w("ok.tsv",
          "case\tface\tpart_id\tverdict\tmechanism\n"
          "T1\tF1\t15\tNG\tcrack\n"
          "T1\tF1\t7\tOK\t\n"
          "T1\tF2\t22\tng\t\n"
          "T2\tF1\t15\tNG\t\n")
    gt = load_ground_truth(p)
    chk("줄 4개", len(gt.rows), 4)
    chk("불량 3개", gt.n_ng, 3)
    chk("과제 목록", gt.cases(), ["T1", "T2"])
    chk("T1 전체 불량 파트", sorted(gt.ng_parts(case="T1")), [15, 22])
    chk("T1/F1 불량 파트", sorted(gt.ng_parts(case="T1", face="F1")), [15])
    chk("전체 불량 파트", sorted(gt.ng_parts()), [15, 22])
    chkb("소문자 ng 도 인식", 22 in gt.ng_parts())
    chk("메커니즘 보존", gt.rows[0].mechanism, "crack")

    print("[2] verdict 를 모르면 줄을 버린다 (OK 로 치지 않는다)")
    p = w("bad_verdict.tsv",
          "case\tface\tpart_id\tverdict\n"
          "T1\tF1\t15\tNG\n"
          "T1\tF1\t7\t???\n"
          "T1\tF1\t8\t\n")
    gt = load_ground_truth(p)
    chk("쓸 수 있는 줄 1개", len(gt.rows), 1)
    chk("건너뛴 줄 2개", len(gt.skipped), 2)
    chkb("건너뛴 사유가 있다", all(bool(r) for _, r in gt.skipped))
    chkb("줄 번호가 붙는다", {n for n, _ in gt.skipped} == {3, 4})

    print("[3] 열 순서가 달라도 된다")
    p = w("order.tsv",
          "verdict\tpart_id\tcase\tface\n"
          "NG\t15\tT1\tF1\n")
    gt = load_ground_truth(p)
    chk("파트 인식", sorted(gt.ng_parts()), [15])

    print("[4] 필수 열이 없으면 사유를 남긴다")
    p = w("nohead.tsv", "case\tpart_id\nT1\t15\n")
    gt = load_ground_truth(p)
    chkb("읽지 않는다", not gt.rows)
    chkb("없는 열을 짚어 준다", "face" in gt.note and "verdict" in gt.note)

    print("[5] 회수율 — 상위 k 에 불량이 들어오나")
    p = w("r.tsv",
          "case\tface\tpart_id\tverdict\n"
          "T1\tF1\t15\tNG\n"
          "T1\tF1\t22\tNG\n")
    gt = load_ground_truth(p)
    scores = {15: 900.0, 3: 800.0, 7: 700.0, 22: 100.0, 9: 50.0}
    r = part_recall(scores, gt, k=1)
    chk("상위 1개 → 1/2", r.recall, 0.5)
    chk("적중 파트", r.hit_parts, [15])
    chk("놓친 파트", r.miss_parts, [22])
    chk("기준선 1/5", r.baseline, 0.2)
    r = part_recall(scores, gt, k=5)
    chk("전부 검사 → 1.0", r.recall, 1.0)
    chk("놓친 파트 없음", r.miss_parts, [])
    # 압축 기준(작을수록 위험)
    r = part_recall({15: -900.0, 3: 10.0, 22: -800.0}, gt, k=2, higher_is_worse=False)
    chk("higher_is_worse=False", r.recall, 1.0)

    print("[6] 조건 필터")
    p = w("f.tsv",
          "case\tface\tpart_id\tverdict\n"
          "T1\tF1\t15\tNG\n"
          "T1\tF2\t22\tNG\n")
    gt = load_ground_truth(p)
    r = part_recall({15: 9.0, 22: 1.0, 3: 5.0}, gt, k=1, face="F1")
    chk("F1 만 보면 불량 1개", r.n_ng, 1)
    chk("상위 1개가 그 파트 → 1.0", r.recall, 1.0)
    r = part_recall({15: 9.0, 22: 1.0}, gt, k=1, case="T9")
    chkb("없는 과제면 사유", r.recall is None and bool(r.note))

    print("[7] 에러를 내지 않는가")
    cases = [
        ("없는 파일", lambda: load_ground_truth(tmp / "nope.tsv")),
        ("None 경로", lambda: load_ground_truth(None)),
        ("숫자 경로", lambda: load_ground_truth(123)),
        ("디렉토리", lambda: load_ground_truth(tmp)),
        ("빈 파일", lambda: load_ground_truth(w("empty.tsv", ""))),
        ("머리글만", lambda: load_ground_truth(w("h.tsv", "\t".join(REQUIRED_COLUMNS) + "\n"))),
        ("열 부족한 줄", lambda: load_ground_truth(
            w("short.tsv", "case\tface\tpart_id\tverdict\nT1\n"))),
        ("part_id 문자열", lambda: load_ground_truth(
            w("pid.tsv", "case\tface\tpart_id\tverdict\nT1\tF1\tabc\tNG\n"))),
        ("part_id 실수", lambda: load_ground_truth(
            w("pidf.tsv", "case\tface\tpart_id\tverdict\nT1\tF1\t15.0\tNG\n"))),
        ("비UTF8 바이트", lambda: load_ground_truth(
            (lambda q: (q.write_bytes(b"case\tface\tpart_id\tverdict\n\xff\tF1\t1\tNG\n"), q)[1])
            (tmp / "bin.tsv"))),
        ("recall: 빈 점수", lambda: part_recall({}, load_ground_truth(p), 1)),
        ("recall: dict 아님", lambda: part_recall([1, 2], load_ground_truth(p), 1)),
        ("recall: 문자열 점수", lambda: part_recall({"a": "b"}, load_ground_truth(p), 1)),
        ("recall: k 0", lambda: part_recall({15: 1.0}, load_ground_truth(p), 0)),
        ("recall: k 과다", lambda: part_recall({15: 1.0}, load_ground_truth(p), 99)),
    ]
    for name, fn in cases:
        try:
            fn()
            print(f"  OK  예외 없음: {name}")
        except Exception as e:      # noqa: BLE001
            fails.append(f"예외 발생: {name} → {type(e).__name__}: {e}")
            print(f"  NG  예외 발생: {name} → {type(e).__name__}: {e}")

    gt = load_ground_truth(w("pidf.tsv", "case\tface\tpart_id\tverdict\nT1\tF1\t15.0\tNG\n"))
    chk("실수 part_id 는 정수로", sorted(gt.ng_parts()), [15])
    gt = load_ground_truth(w("pid.tsv", "case\tface\tpart_id\tverdict\nT1\tF1\tabc\tNG\n"))
    chkb("숫자 아닌 part_id 는 버리고 사유", (not gt.rows) and len(gt.skipped) == 1)
    gt = load_ground_truth(tmp / "nope.tsv")
    chkb("없는 파일: 사유", (not gt.rows) and bool(gt.note))
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
