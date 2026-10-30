# S1 파일을 lasso-python(독립 리더)으로 읽은 d3plot 값과 대조하는 검증 스크립트 — SIF 안에서 PYTHONNOUSERSITE=1 로
"""사용: python3 check_s1_against_lasso.py <s1.h5> <d3plot> [--full-gate]

계약(contract-c3-s1-draft.md)의 복원 식만으로 값을 되돌려, lasso 가 읽은 원값과 견준다.
- 고른 상태 4개(처음·1/3·2/3·끝): 겉면 변위·von Mises 오차 ≤ scale/2 (+float32 반올림), alive·시각 일치
- --full-gate: 전 상태 응력을 읽어 파트별 전 요소·겉면 최대를 독립으로 세어 /parts 와 견준다
"""
import sys

import h5py
import numpy as np
from lasso.dyna import ArrayType, D3plot


def decode(ds, f, group_idx):
    enc = ds.attrs["encoding"]
    enc = enc.decode() if isinstance(enc, bytes) else enc
    raw = ds[...]
    if enc == "float32":
        return raw.astype(np.float64), None
    scale = f[ds.attrs["scale_table"]][...]
    offset = f[ds.attrs["offset_table"]][...]
    s = scale[group_idx]
    o = offset[group_idx]
    return o + s * raw.astype(np.float64), s


def vm_of(stress):  # [..., 6] xx yy zz xy yz zx
    sxx, syy, szz, sxy, syz, szx = (stress[..., k] for k in range(6))
    return np.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
                   + 3.0 * (sxy ** 2 + syz ** 2 + szx ** 2))


def main():
    s1_path, d3_path = sys.argv[1], sys.argv[2]
    full_gate = "--full-gate" in sys.argv
    f = h5py.File(s1_path, "r")
    print("schema", f.attrs["schema"], f.attrs["schema_version"], "units", f.attrs["units"],
          "warnings", list(f.attrs["warnings"]))
    node_ids = f["mesh/node_ids"][...]
    elem_ids = f["mesh/elem_ids"][...]
    elem_part = f["mesh/elem_part_id"][...]
    part_ids = f["parts/part_id"][...]
    pidx = {p: i for i, p in enumerate(part_ids)}
    elem_g = np.array([pidx[p] for p in elem_part])
    node_g = f["mesh/node_group"][...].astype(int)
    sidx = f["states/state_index"][...]
    stime = f["states/time"][...]
    T = len(sidx)
    picks = sorted(set([0, T // 3, (2 * T) // 3, T - 1]))
    print("T", T, "picks", picks, "orig", [int(sidx[k]) for k in picks])

    disp_all, dscale = decode(f["states/displacement"], f, node_g)
    vm_all, vscale = decode(f["states/von_mises"], f, elem_g)
    alive = f["states/alive"][...]

    want = [int(sidx[k]) for k in picks]
    d3 = D3plot(d3_path, state_filter=set(want), buffered_reading=True,
                state_array_filter=[ArrayType.node_displacement, ArrayType.element_solid_stress,
                                    ArrayType.global_timesteps, ArrayType.element_solid_is_alive])
    nid = d3.arrays[ArrayType.node_ids]
    npos = {n: i for i, n in enumerate(nid)}
    ni = np.array([npos[n] for n in node_ids])
    x0 = d3.arrays[ArrayType.node_coordinates][ni]
    cur = d3.arrays[ArrayType.node_displacement][:, ni, :]
    sid = d3.arrays[ArrayType.element_solid_ids]
    spos = {e: i for i, e in enumerate(sid)}
    ei = np.array([spos[e] for e in elem_ids])
    stress = d3.arrays[ArrayType.element_solid_stress][:, ei, 0, :]
    vm_ref = vm_of(stress.astype(np.float64))
    t_ref = d3.arrays[ArrayType.global_timesteps]
    alive_ref = d3.arrays.get(ArrayType.element_solid_is_alive)

    worst_d = worst_v = 0.0
    for j, k in enumerate(picks):
        u_ref = cur[j].astype(np.float64) - x0.astype(np.float64)
        err_d = np.abs(disp_all[k] - u_ref)
        err_v = np.abs(vm_all[k] - vm_ref[j])
        if dscale is not None:
            # q16 오차 한계 scale/2, 원값이 float32 라 그 반올림을 더한다
            bound_d = 0.5 * dscale + 1e-6 * np.abs(u_ref).max() + 1e-6
            bound_v = 0.5 * vscale + 1e-6 * np.abs(vm_ref[j]).max()
            worst_d = max(worst_d, float((err_d / bound_d).max()))
            worst_v = max(worst_v, float((err_v / bound_v).max()))
        print(f"state {int(sidx[k])}: t s1={stime[k]:.9g} lasso={t_ref[j]:.9g} | "
              f"|du| max {err_d.max():.3e} | |dvm| max {err_v.max():.3e} (vm max {vm_ref[j].max():.4g})")
        if alive_ref is not None:
            a_ref = (alive_ref[j, ei] != 0).astype(np.uint8)
            print("   alive 불일치", int((a_ref != alive[k]).sum()))
    if dscale is not None:
        print(f"q16 오차/한계 최대 — 변위 {worst_d:.3f}, von Mises {worst_v:.3f} (1 이하여야 한다)")

    if full_gate:
        # 100 상태씩 끊어 읽어 요소별 전 상태 최대만 남긴다 (메모리 상한)
        n_src = int(f["states"].attrs["n_states_source"])
        vm_elem_max = None
        for s0 in range(0, n_src, 100):
            d3a = D3plot(d3_path, state_filter=set(range(s0, min(n_src, s0 + 100))), buffered_reading=True,
                         state_array_filter=[ArrayType.element_solid_stress])
            st = d3a.arrays[ArrayType.element_solid_stress][:, :, 0, :]
            m = vm_of(st.astype(np.float64)).max(axis=0)
            vm_elem_max = m if vm_elem_max is None else np.maximum(vm_elem_max, m)
        vm = vm_elem_max[None, :]
        spart = d3a.arrays[ArrayType.element_solid_part_indexes]
        pids = d3a.arrays[ArrayType.part_ids]
        solid_pid = pids[spart]
        surf_mask = np.zeros(len(sid), bool)
        surf_mask[ei] = True
        bad = 0
        for i, p in enumerate(part_ids):
            m = solid_pid == p
            all_max = vm[:, m].max()
            sm = m & surf_mask
            surf_max = vm[:, sm].max() if sm.any() else -1.0
            a = f["parts/vm_max_all"][i]
            s = f["parts/vm_max_surface"][i]
            ok = abs(a - all_max) <= 1e-6 * max(1, all_max) and abs(s - surf_max) <= 1e-6 * max(1, abs(surf_max))
            bad += not ok
            print(f"part {p}: all {a:.6g}/{all_max:.6g} surf {s:.6g}/{surf_max:.6g} "
                  f"on_surface={f['parts/max_elem_on_surface'][i]} {'OK' if ok else 'MISMATCH'}")
        print("게이트 불일치 파트", bad)


if __name__ == "__main__":
    main()
