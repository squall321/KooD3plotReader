# 배치 케이스 출력 폴더 이름이 서로 겹쳐 결과를 덮어쓰지 않는지 검증하는 시험
"""`koo_deep_report.__main__._batch_case_names` 시험.

배치는 d3plot 을 트리 전체에서 긁어온다. 출력 폴더를 잎 폴더 이름만으로
정하면 SmartTwin 표준 배치(output/Run_xxx/Output/d3plot)는 모든 런이
'Output' 하나로 겹쳐 서로를 덮어쓴다. 실패로도 기록되지 않아 그냥
사라진다.
"""
import sys
from pathlib import Path

from koo_deep_report.__main__ import _batch_case_names

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


# ---------------------------------------------------------------------------
print("[1] 잎 폴더 이름이 같아도 케이스가 겹치지 않는다")

root = Path("/data/campaigns")
names = _batch_case_names(
    [root / "Test_A/output/Run_001", root / "Test_B/output/Run_001"], root)
chk("두 캠페인의 Run_001 이 서로 다른 폴더", len(set(names)), 2)
chk("상대 경로로 이름을 만든다", names[0], "Test_A__output__Run_001")
chk("두 번째도 마찬가지", names[1], "Test_B__output__Run_001")

# SmartTwin 표준 배치: output/Run_xxx/Output/d3plot — 잎이 전부 'Output'.
root2 = Path("/data/koopark/Test_010/output")
names2 = _batch_case_names(
    [root2 / "Run_001/Output", root2 / "Run_002/Output", root2 / "Run_003/Output"], root2)
chk("Run 3개가 3개 폴더로", len(set(names2)), 3)
chk("Run_001", names2[0], "Run_001__Output")

print()

# ---------------------------------------------------------------------------
print("[2] 그래도 겹치면 번호를 붙인다 (조용히 덮어쓰지 않는다)")

# 'a/b' 와 'a__b' 는 상대 경로가 달라도 이름이 같아진다.
names3 = _batch_case_names([root / "a/b", root / "a__b"], root)
chk("이름이 겹치지 않는다", len(set(names3)), 2)
chkb("한쪽에 번호가 붙는다", names3[1].endswith("__2"))

# 루트 자체가 해석 폴더인 경우 (상대 경로가 '.')
names4 = _batch_case_names([root], root)
chk("루트 자신은 폴더 이름으로", names4, ["campaigns"])

print()


def test_all():
    """pytest 진입점."""
    assert not fails, "실패 %d 건:\n  - %s" % (len(fails), "\n  - ".join(fails))


if __name__ == "__main__":
    if fails:
        print(f"[FAIL] 실패 {len(fails)} 건")
        for f in fails:
            print("   -", f)
        sys.exit(1)
    print("[PASS] 실패 0 건")
