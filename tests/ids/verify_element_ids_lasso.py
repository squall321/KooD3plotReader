# d3plot 요소 실제 ID(NARBS)를 원본 .k 덱 및 lasso 와 대조해 순서 어긋남을 잡는 검증 도구
"""
사용:
    g++ -std=c++17 -O2 -I include tests/ids/dump_element_ids.cpp build/libkood3plot.a \\
        -fopenmp -lz -o /tmp/dump_ids
    python3 tests/ids/verify_element_ids_lasso.py <d3plot> /tmp/dump_ids [원본.k ...]

대조 기준은 둘이고 하나만 있어도 판정한다. 둘 다 없으면 통과가 아니라 '검증 못 함' 이다.
  1) 원본 키워드 덱의 *ELEMENT_SOLID/BEAM/SHELL/TSHELL 카드 (외부 라이브러리 불요)
     — **집합만** 대조한다. 카드가 적힌 순서가 d3plot 배열 순서와 같다는 보장이 없다.
  2) lasso-python 의 element_*_ids — **순서까지** 대조한다.

잡으려는 결함이 '배열이 통째로 어긋난 것' 이므로 순서를 보는 기준이 반드시 하나는
있어야 한다. 집합만 보면 요소 인덱스 i 가 전부 엉뚱한 ID 를 가리켜도 통과한다.

2026-09-17: NARBS 블록을 절점→솔리드→**두꺼운셸**→빔→셸 순으로 읽어, 셸과 두꺼운 셸이
함께 있는 덱에서 두 ID 배열이 통째로 어긋나 있었다. 규격 순서는
절점→솔리드→빔→셸→두꺼운셸 이다 (ls-dyna_database.txt:728-732).
"""
import json
import subprocess
import sys
from pathlib import Path

KINDS = ("solid", "beam", "shell", "tshell")
CARD = {"*ELEMENT_SOLID": "solid", "*ELEMENT_BEAM": "beam",
        "*ELEMENT_SHELL": "shell", "*ELEMENT_TSHELL": "tshell"}


def from_deck(paths):
    """원본 .k 에서 요소 종류별 ID 집합. 빈 dict 면 덱을 못 읽은 것."""
    ids = {k: set() for k in KINDS}
    seen_any = False
    for p in paths:
        kind = None
        for line in Path(p).read_text(errors="ignore").splitlines():
            if line.startswith("*"):
                key = line.strip().upper().split()[0]
                kind = next((v for k, v in CARD.items() if key.startswith(k)), None)
                continue
            if kind is None or not line.strip() or line.startswith("$"):
                continue
            tok = line.split()
            if not tok or not tok[0].lstrip("-").isdigit():
                continue
            ids[kind].add(int(tok[0]))
            seen_any = True
    return ids if seen_any else {}


def from_lasso(d3plot):
    """lasso 의 요소 ID를 **순서 그대로** 돌려준다. 순서를 버리면 순열 결함을 놓친다."""
    try:
        from lasso.dyna import D3plot, ArrayType as A
    except Exception as e:  # noqa: BLE001
        print(f"  (lasso 없음: {e})")
        return {}
    keys = {"solid": A.element_solid_ids, "beam": A.element_beam_ids,
            "shell": A.element_shell_ids, "tshell": A.element_tshell_ids}
    d = D3plot(str(d3plot), state_array_filter=[A.global_timesteps])
    return {k: d.arrays[v].tolist() for k, v in keys.items() if v in d.arrays}


def first_diff(a, b):
    """두 배열이 처음 어긋나는 자리. 없으면 None."""
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    d3plot, dump_bin = sys.argv[1], sys.argv[2]
    decks = sys.argv[3:] or sorted(Path(d3plot).parent.glob("*.k"))
    got = json.loads(subprocess.run([dump_bin, d3plot], capture_output=True, text=True, check=True).stdout)
    mine = {k: list(got.get(k) or []) for k in KINDS}   # 순서를 버리지 않는다
    print("리더: " + ", ".join(f"{k} {len(mine[k])}개" for k in KINDS if mine[k]))

    bad = 0
    compared = 0

    # 1) 원본 덱 — 집합만. 카드 순서가 d3plot 배열 순서와 같다는 보장이 없다.
    deck_ref = from_deck(decks)
    if not deck_ref:
        print(f"  원본 덱: 대조 자료 없음 — 건너뜀 ({len(decks)}개 읽음)")
    else:
        print(f"  원본 덱({len(decks)}개): 집합만 대조합니다 — 순서 어긋남은 이 기준으로")
        print("           잡을 수 없습니다. *INCLUDE 는 따라가지 않으므로 포함 파일이 다른")
        print("           디렉토리에 있으면 .k 경로를 인자로 직접 넘기세요.")
        for k in KINDS:
            ms, rs = set(mine[k]), set(deck_ref.get(k) or [])
            if not ms and not rs:
                continue
            compared += 1
            if ms != rs:
                bad += 1
                print(f"  [FAIL] 원본 덱 {k}: 리더 {len(ms)}개 / 기준 {len(rs)}개, "
                      f"리더에만 {sorted(ms - rs)[:3]}, 기준에만 {sorted(rs - ms)[:3]}")
            else:
                print(f"  [OK  ] 원본 덱 {k}: {len(ms)}개 집합 일치 (순서 미검증)")

    # 2) lasso — 순서까지. 순열 결함을 잡는 것은 이 기준뿐이다.
    lasso_ref = from_lasso(d3plot)
    if not lasso_ref:
        print("  lasso: 대조 자료 없음 — 건너뜀")
    else:
        for k in KINDS:
            ml, rl = mine[k], list(lasso_ref.get(k) or [])
            if not ml and not rl:
                continue
            compared += 1
            i = first_diff(ml, rl)
            if i is not None:
                bad += 1
                same_set = " (집합은 같음 — 순서만 어긋남)" if set(ml) == set(rl) else ""
                print(f"  [FAIL] lasso {k}: 리더 {len(ml)}개 / 기준 {len(rl)}개, "
                      f"첫 불일치 [{i}] 리더 {ml[i] if i < len(ml) else '없음'} "
                      f"≠ 기준 {rl[i] if i < len(rl) else '없음'}{same_set}")
            else:
                print(f"  [OK  ] lasso {k}: {len(ml)}개 순서까지 일치")

    if compared == 0:
        print("[검증 못 함] 대조 자료가 하나도 없습니다 — 통과가 아닙니다.")
        print("             원본 .k 를 인자로 넘기거나 lasso-python 을 설치하세요.")
        return 2
    print("[PASS]" if bad == 0 else f"[FAIL] 불일치 {bad}건")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
