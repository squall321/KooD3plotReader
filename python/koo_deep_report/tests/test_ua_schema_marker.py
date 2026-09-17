# 산출물 스키마 번호가 셸 스크립트와 갈리지 않는지 검증하는 시험
"""`koo_deep_report.__main__.UA_OUTPUT_SCHEMA` 시험.

같은 `.ua_schema` 마커 규약이 두 곳에 사본으로 있다 — scripts/post_analyze.sh
와 이 파이썬 패키지다. 한쪽만 올리면 다른 쪽은 수정 전 산출물을 계속 '최신'
으로 보고 `batch --skip-existing` 이 옛 result.json 을 그대로 배치 리포트로
내보낸다. 값이 갈리는 순간 실패하도록 시험으로 묶는다.
"""
import re
import sys
from pathlib import Path

from koo_deep_report.__main__ import (
    UA_OUTPUT_SCHEMA, UA_SCHEMA_MARKER, _outputs_are_current,
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


REPO = Path(__file__).resolve().parents[3]
SH = REPO / "scripts" / "post_analyze.sh"

# ---------------------------------------------------------------------------
print("[1] 셸 사본과 파이썬 사본의 스키마 번호가 같다")

if not SH.exists():
    print(f"  -- {SH} 없음 — 건너뜀")
else:
    m = re.search(r"^UA_OUTPUT_SCHEMA=(\d+)\s*$", SH.read_text(encoding="utf-8"),
                  re.MULTILINE)
    chkb("post_analyze.sh 에서 UA_OUTPUT_SCHEMA 를 찾았다", m is not None)
    if m:
        chk("두 사본의 값이 같다", UA_OUTPUT_SCHEMA, int(m.group(1)))

print()

# ---------------------------------------------------------------------------
print("[2] 수정 전 산출물(마커 '2')은 낡은 것으로 판정한다")

import tempfile

with tempfile.TemporaryDirectory() as td:
    old = Path(td) / "old_case"
    old.mkdir()
    (old / "result.json").write_text("{}", encoding="utf-8")
    (old / UA_SCHEMA_MARKER).write_text("2\n", encoding="utf-8")
    chkb("마커 '2' 는 최신이 아니다", _outputs_are_current(old) is False)

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
