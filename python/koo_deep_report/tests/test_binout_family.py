# MPP 가 쪼갠 binout0000/0001… 가족 전체가 lasso 에 넘어가는지 검증하는 시험
"""`koo_deep_report.core.sim_detector` 의 binout 탐색 시험.

MPP 런은 binout0000, binout0001 … 로 브랜치를 나눠 쓴다. 탐색이 binout0000 만
집어 주면 뒤 파일에 실린 브랜치(rcforc/sleout/matsum 등)가 통째로 사라지고,
소비자는 "덱에 해당 DATABASE 카드가 없다" 로 잘못 보고한다. 그래서 탐색 결과는
**가족 전체를 가리켜야** 한다.

실덱 확인은 /data/shield_can_forming_study/defl_c5210_methodB_press 에서 한다
(binout0000=glstat+matsum, binout0001=nodout). 덱이나 lasso 가 없으면 그 항목은
건너뛴다 — 없는 것을 통과로 위장하지 않고 건너뛴 사유를 출력한다.
"""
import glob as _glob
import sys
import tempfile
from pathlib import Path

from koo_deep_report.core.sim_detector import find_files

fails = []
skips = []


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


def _expanded(p):
    """탐색이 돌려준 경로가 실제로 가리키는 파일 목록."""
    return sorted(Path(x) for x in _glob.glob(str(p)))


print("[1] 단일 binout — 있는 그대로")
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    (d / "binout").write_bytes(b"")
    info = find_files(d)
    chkb("binout 하나면 그 파일", info.binout == d / "binout")

print("[2] binout0000 하나뿐 — 그 파일")
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    (d / "binout0000").write_bytes(b"")
    info = find_files(d)
    chkb("binout0000 하나면 그 파일", info.binout == d / "binout0000")

print("[3] MPP 분할 — 가족 전체를 가리킨다")
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    for name in ("binout0000", "binout0001", "binout0002"):
        (d / name).write_bytes(b"")
    info = find_files(d)
    chkb("binout 경로가 있다", info.binout is not None)
    chkb("세 파일 모두 포함", _expanded(info.binout) == [
        d / "binout0000", d / "binout0001", d / "binout0002"])

print("[4] binout 없음 — None")
with tempfile.TemporaryDirectory() as td:
    info = find_files(Path(td))
    chkb("없으면 None", info.binout is None)

print("[5] 실덱 — lasso 가 두 파일의 브랜치를 합쳐 읽는다")
_REAL = Path("/data/shield_can_forming_study/defl_c5210_methodB_press")
if not (_REAL / "binout0001").exists():
    skips.append(f"실덱 없음: {_REAL}")
    print(f"  -- 건너뜀: 실덱 없음 ({_REAL})")
else:
    try:
        from lasso.dyna import Binout  # type: ignore
    except ImportError:
        skips.append("lasso 미설치")
        print("  -- 건너뜀: lasso 미설치")
    else:
        info = find_files(_REAL)
        branches = set(Binout(str(info.binout)).read())
        # binout0000 = glstat+matsum, binout0001 = nodout
        chkb("glstat 보임", "glstat" in branches)
        chkb("matsum 보임", "matsum" in branches)
        chkb("뒤 파일의 nodout 도 보임", "nodout" in branches)

print()


def test_all():
    """pytest 진입점.

    이 파일의 본문은 import 시점에 이미 실행된다(스크립트로도 돌릴 수 있게
    그렇게 썼다). pytest 는 여기서 결과만 단언한다.
    """
    assert not fails, "실패 %d 건:\n  - %s" % (len(fails), "\n  - ".join(fails))


if __name__ == "__main__":
    for s in skips:
        print("   ~ 건너뜀:", s)
    if fails:
        print(f"[FAIL] 실패 {len(fails)} 건")
        for f in fails:
            print("   -", f)
        sys.exit(1)
    print("[PASS] 실패 0 건")
