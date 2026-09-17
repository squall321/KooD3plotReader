# unified_analyzer 의 방향 표면 응력 CSV 를 lasso-python 독립 계산과 상태마다 대조하는 검증 도구
"""
사용:
    python3 tests/surface/verify_surface_stress_lasso.py <d3plot> <part_id|0> <direction> <angle> <surface_csv>
    예) ... d3plot 21 +z 45 out/surface/p21_top_stress.csv

독립 규약 (C++ 코드를 재사용하지 않는다):
  - 외피 = 대상 솔리드(파트 0 이면 전체)의 실제 면(사면체 삼각형 4, 쐐기·피라미드·육면체는
    중복 절점을 접은 면) 중 한 번만 나오는 면
  - 법선 = 대각선 외적, 방향은 요소 중심에서 멀어지는 쪽 (절점 순서 규약에 기대지 않음)
  - 넓이 0 인 퇴화 면은 제외, 좌표는 float64 (float32 면 정확히 45° 인 면이 경계에서 떨어진다)

주의: lasso 는 두꺼운 셸 변수 개수가 헤더와 다른 덱(예: 배터리 덱)에서 상태를 잘못 읽는다.
      "n_tshell_vars != n_tshell_vars_computed" 경고가 나오면 이 도구로 대조하지 말 것.
"""
import csv
import sys

import numpy as np
from lasso.dyna import D3plot, ArrayType as A

HEX_FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (0, 4, 7, 3), (1, 2, 6, 5)]


def face_node_sets(conn_row):
    """솔리드 한 개의 실제 면. LS-DYNA 는 사면체·쐐기·피라미드를 절점이 겹친 육면체로 적는다."""
    n = list(conn_row)
    uniq = list(dict.fromkeys(n))
    if len(uniq) == 4 and n[4] == n[3] and n[5] == n[3] and n[6] == n[3] and n[7] == n[3]:
        a, b, c, d = uniq                      # 사면체 — 삼각형 4개
        return [(a, b, c), (a, b, d), (a, c, d), (b, c, d)]
    out = []
    for f in HEX_FACES:                        # 육면체·쐐기·피라미드 — 중복 절점을 접는다
        poly = list(dict.fromkeys(n[i] for i in f))
        if len(poly) >= 3:
            out.append(tuple(poly))
    return out


DIRS = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}


def reference(d3plot_path, pid, ref_dir, angle):
    d = D3plot(d3plot_path, state_array_filter=[A.element_solid_stress, A.global_timesteps])
    a = d.arrays
    xyz = a[A.node_coordinates].astype(np.float64)
    conn = a[A.element_solid_node_indexes]
    pidx = a[A.element_solid_part_indexes]
    part_ids = a[A.part_ids] if A.part_ids in a else np.arange(1, pidx.max() + 2)
    eids = a[A.element_solid_ids]
    sig = a[A.element_solid_stress]
    if sig.ndim == 4:
        sig = sig[:, :, 0, :]
    sel = np.arange(len(pidx)) if pid == 0 else np.where(part_ids[pidx] == pid)[0]

    count, owner = {}, {}
    for e in sel:
        for poly in face_node_sets(conn[e].tolist()):
            key = tuple(sorted(poly))
            count[key] = count.get(key, 0) + 1
            owner.setdefault(key, (e, poly))
    ref = np.asarray(ref_dir, dtype=np.float64)
    ref /= np.linalg.norm(ref)
    cosang = np.cos(np.radians(angle))
    elems, normals = [], []
    for key, c in count.items():
        if c != 1:
            continue
        e, poly = owner[key]
        p = xyz[list(poly)]
        if len(poly) >= 4:
            n = np.cross(p[2] - p[0], p[3] - p[1])
        else:
            n = np.cross(p[1] - p[0], p[2] - p[0])
        if np.linalg.norm(n) < 1e-30:
            continue
        n /= np.linalg.norm(n)
        if np.dot(n, p.mean(0) - xyz[conn[e]].mean(0)) < 0:   # 요소 중심 기준 바깥쪽
            n = -n
        if np.dot(n, ref) >= cosang - 1e-12:
            elems.append(e)
            normals.append(n)
    elems = np.array(elems)
    s = sig[:, elems, :].astype(np.float64)
    sx, sy, sz, txy, tyz, tzx = (s[..., i] for i in range(6))
    vm = np.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2) + 3 * (txy ** 2 + tyz ** 2 + tzx ** 2))
    nx, ny, nz = np.array(normals).T
    sn = (sx * nx + txy * ny + tzx * nz) * nx + (txy * nx + sy * ny + tyz * nz) * ny + (tzx * nx + tyz * ny + sz * nz) * nz
    rows = []
    for k, t in enumerate(a[A.global_timesteps]):
        i = int(np.argmax(vm[k]))
        rows.append({"time": float(t), "vm_max": float(vm[k].max()), "vm_eid": int(eids[elems[i]]),
                     "vm_avg": float(vm[k].mean()), "sn_max": float(sn[k].max()), "sn_min": float(sn[k].min())})
    return len(elems), rows


def main():
    if len(sys.argv) != 6 or sys.argv[3] not in DIRS:
        print(__doc__)
        return 2
    d3plot_path, pid, dname, angle, csv_path = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4]), sys.argv[5]
    n_faces, ref = reference(d3plot_path, pid, DIRS[dname], angle)
    got = list(csv.DictReader(open(csv_path, newline="")))
    if len(got) != len(ref):
        print(f"[FAIL] 상태 수 불일치: CSV {len(got)} / 독립 {len(ref)}")
        return 1
    rel = lambda x, y: abs(x - y) / max(abs(y), 1e-9)
    # CSV 는 소수 6자리 — 그보다 큰 차이만 결함으로 본다
    tol = lambda y: 1.5e-6 / max(abs(y), 1e-9) + 1e-6
    bad = 0
    for k, (g, r) in enumerate(zip(got, ref)):
        vm = float(g["VonMises_Max"])
        if rel(vm, r["vm_max"]) > tol(r["vm_max"]) or (r["vm_max"] > 0 and int(g["VonMises_Max_ElemID"]) != r["vm_eid"]):
            bad += 1
            if bad <= 5:
                print(f"  상태 {k} t={r['time']:.6g}: CSV vM {vm} 요소 {g['VonMises_Max_ElemID']} / 독립 {r['vm_max']:.6f} 요소 {r['vm_eid']}")
    peak = max(ref, key=lambda r: r["vm_max"])
    print(f"독립 계산: 면 {n_faces}개, 상태 {len(ref)}, vM 최대 {peak['vm_max']:.6g} (t={peak['time']:.6g}, 요소 {peak['vm_eid']})")
    print(f"[{'PASS' if bad == 0 else 'FAIL'}] vM 최대·최대 요소 불일치 {bad}/{len(ref)} 상태")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
