# 단면 영상 마지막 프레임의 범례로 LS-PrePost 응력 0 결함(K-1)을 가려내는 읽기 전용 점검 도구
"""사용: python3 -I zero_frame_check.py <목록.txt|영상.mp4|프레임.png ...> > 결과.tsv

결함(LS-PrePost 상태 메모리 예산 초과)은 단조라 영상이 0 이면 마지막 프레임이 반드시 0 이다.
판정
  ZERO     범례 글자 줄이 모두 같고, 그 줄이 「0.000e+00」 견본과 같다 (견본과 해상도가 같을 때만)
  UNIFORM  범례가 모두 같지만 0 견본과 다르다 — 실제 균일장(warpage 등)일 수 있어 눈으로 확인
  UNIFORM? 범례가 모두 같은데 해상도가 견본과 달라 0 인지 못 가림
  OK       범례 값이 서로 다르다
  NOLEGEND 범례 줄을 못 찾음 (자른 영상 등)
  ERROR    프레임을 못 뽑음
"""
import io
import subprocess
import sys

from PIL import Image

TEMPLATE_FRAME = "/data/koopark/drop_twin_p0/sv_proto/runs/R0_seed20M_vm_z/last_frame.png"


def last_frame(path):
    if path.endswith(".png"):
        return Image.open(path).convert("RGB")
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-sseof", "-0.5", "-i", path, "-update", "1",
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, timeout=300)
    if out.returncode != 0 or not out.stdout:
        raise RuntimeError(out.stderr.decode(errors="replace").strip()[-200:])
    return Image.open(io.BytesIO(out.stdout)).convert("RGB")


def label_bands(im):
    """범례 숫자 칸의 글자를 줄별 알파 그림(배경을 뺀 불투명도, 0~1)으로 돌려준다.

    글자는 흰색에 안티에일리어싱이고 배경(bgstyle fade)은 아래로 갈수록 밝아진다.
    흰 픽셀 문턱으로 자르면 같은 글자도 줄마다 모양이 달라진다 — 줄마다 배경을
    빼 알파로 바꾸면 배경과 무관하게 같은 글자는 같은 그림이 된다.
    """
    W, H = im.size
    x0, x1 = int(0.855 * W), int(0.953 * W)
    y0, y1 = int(0.06 * H), int(0.50 * H)
    px = im.load()
    lum = [[min(px[x, y]) for x in range(x0, x1)] for y in range(y0, y1)]
    sat = [[max(px[x, y]) - min(px[x, y]) for x in range(x0, x1)] for y in range(y0, y1)]
    # 글자 줄 찾기: 채도 낮고 밝은 픽셀이 있는 행
    rows = [sum(1 for l, s in zip(lr, sr) if l >= 200 and s <= 40) >= 2 for lr, sr in zip(lum, sat)]
    spans, start = [], None
    for i, on in enumerate(rows + [False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= 6:
                spans.append((max(0, start - 1), min(len(lum), i + 1)))
            start = None
    out = []
    for a, b in spans:
        bgv = sorted(l for lr, sr in zip(lum[a:b], sat[a:b]) for l, s in zip(lr, sr) if s > 40)
        bg = bgv[len(bgv) // 2] if bgv else 0
        alpha = [[max(0.0, min(1.0, (l - bg) / max(1, 255 - bg))) for l in lr] for lr in lum[a:b]]
        cols = [c for c in range(len(alpha[0])) if any(r[c] > 0.5 for r in alpha)]
        if not cols:
            continue
        c0 = min(cols)
        out.append([r[c0:c0 + 90] for r in alpha])
    return out


def same(a, b, tol=0.30):
    """두 줄 알파 그림의 평균 절대차가 tol 이하인가 (높이가 달라도 위 정렬로 비교)."""
    h = min(len(a), len(b))
    w = min(len(a[0]), len(b[0]))
    if h < 6 or w < 20:
        return False
    tot = sum(abs(a[y][x] - b[y][x]) for y in range(h) for x in range(w))
    ink = max(1e-6, sum(a[y][x] for y in range(h) for x in range(w)))
    return tot / ink <= tol


def main(args):
    tim = Image.open(TEMPLATE_FRAME).convert("RGB")
    tbands = label_bands(tim)
    zero_tmpl = tbands[0] if tbands else None
    paths = []
    for a in args:
        if a.endswith(".txt"):
            paths += [l.strip() for l in open(a, encoding="utf-8") if l.strip()]
        else:
            paths.append(a)
    print("verdict\tsize\tbands\tpath")
    for p in paths:
        try:
            im = last_frame(p)
        except Exception as e:  # noqa: BLE001 — 점검 도구, 사유를 줄에 남긴다
            print(f"ERROR\t-\t-\t{p}\t{e}", flush=True)
            continue
        bands = label_bands(im)
        size = f"{im.size[0]}x{im.size[1]}"
        if len(bands) < 5:
            v = "NOLEGEND"
        elif not all(same(bands[0], b) for b in bands[1:]):
            v = "OK"
        elif im.size != tim.size:
            v = "UNIFORM?"
        else:
            v = "ZERO" if zero_tmpl and same(bands[0], zero_tmpl) else "UNIFORM"
        print(f"{v}\t{size}\t{len(bands)}\t{p}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
