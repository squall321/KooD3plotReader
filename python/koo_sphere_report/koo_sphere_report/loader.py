"""Data loader: reads simulation configs, analysis results, and DropSet files."""
import csv
import json
import math
from pathlib import Path

from .models import (
    AngleCondition, MotionData, PartInfo, PartResult,
    SimulationParams, SimulationResult, TimeSeriesData,
)


def _classify_angle(name: str) -> str:
    if name.startswith("F"):
        return "face"
    if name.startswith("E"):
        return "edge"
    if name.startswith("C"):
        return "corner"
    if name.startswith("P"):
        return "fibonacci"
    return "unknown"


def load_runner_config(test_dir: Path) -> tuple[str, str, SimulationParams, dict[str, AngleCondition]]:
    """Load runner_config.json and return project info + DOE angles.

    Returns: (project_name, doe_strategy, sim_params, {angle_key: AngleCondition})
    """
    rc_path = test_dir / "runner_config.json"
    if not rc_path.exists():
        return "", "unknown", SimulationParams(), {}

    with open(rc_path, encoding="utf-8") as f:
        rc = json.load(f)

    project_name = rc.get("project_name", rc.get("project", {}).get("name", ""))

    # DOE strategy from scenario
    scenarios = rc.get("scenarios", [])
    doe_strategy = "unknown"
    if scenarios:
        sid = scenarios[0].get("scenario_name", scenarios[0].get("scenario_id", ""))
        if "fibonacci" in sid.lower():
            doe_strategy = "fibonacci"
        elif "cuboid" in sid.lower() or "26" in sid:
            doe_strategy = "cuboid_26"
        elif "6faces" in sid.lower():
            doe_strategy = "6faces"
        else:
            doe_strategy = sid

    # Simulation params
    sp = rc.get("simulation_params", {})
    sim_params = SimulationParams(
        t_final=sp.get("tFinal", 0.001),
        dt=sp.get("dt", 1e-6),
        drop_height=sp.get("height", 1500.0),
        density=sp.get("density", 7850.0),
        youngs_modulus=sp.get("youngs_modulus", 2e11),
        poisson_ratio=sp.get("poisson_ratio", 0.3),
    )

    # DOE angles
    doe_angles: dict[str, AngleCondition] = {}
    scenario = rc.get("scenario", {})
    raw_angles = scenario.get("doe_angles", {})
    for doe_idx, steps in raw_angles.items():
        for step_key, angle_def in steps.items():
            name = angle_def.get("angle_name", f"DOE{doe_idx}")
            ac = AngleCondition(
                angle_name=name,
                roll=angle_def.get("roll", 0.0),
                pitch=angle_def.get("pitch", 0.0),
                yaw=angle_def.get("yaw", 0.0),
                category=_classify_angle(name),
            )
            key = f"{ac.roll:.1f}_{ac.pitch:.1f}_{ac.yaw:.1f}"
            doe_angles[key] = ac

    return project_name, doe_strategy, sim_params, doe_angles


#: 단위계별 G 환산 계수 (가속도 1G 를 그 단위계로 표현한 값).
#: 9.80665 m/s² = 9806.65 mm/s² = 9.80665e-3 mm/ms².
_G_FACTOR_BY_UNIT = {
    "SI": 9.80665,
    "ton-mm-s": 9806.65,
    "ton-mm-ms": 9.80665e-3,
    "g-mm-ms": 9.80665e-3,
}


def _deck_density(output_dir: Path) -> float | None:
    """덱의 *MAT 카드에서 밀도 대푯값(중앙값). 못 읽으면 None.

    **runner_config.simulation_params.density 는 쓰면 안 된다.** 그것은 시나리오
    템플릿 값이라 덱과 어긋난다 — Test_006 은 config 7850(SI 풍) / 덱 2.33e-9
    (ton-mm-s) 였다. 그 값으로 판정하면 정상 보고서를 SI 로 뒤집어 peak-G 가
    1000배 커진다(실측으로 확인).
    """
    # 덱은 test_dir 루트나 첫 run 폴더에 있다. _find_kfile 은 run 폴더 전용이라
    # 여기서 둘 다 훑는다 (없으면 None → 호출자가 기본값 유지).
    kf = None
    for cand in [output_dir.parent, output_dir]:
        if not cand or not cand.exists():
            continue
        ks = sorted(cand.glob("*.k")) + sorted(cand.glob("*.key"))
        if ks:
            kf = ks[0]
            break
    if kf is None and output_dir.exists():
        for run in sorted(output_dir.iterdir())[:3]:
            if run.is_dir():
                kf = _find_kfile(run)
                if kf is not None:
                    break
    if kf is None:
        return None
    dens: list[float] = []
    try:
        lines = kf.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    want = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("*"):
            want = s.upper().startswith("*MAT_")
            continue
        if not want or not s or s.startswith("$"):
            continue
        # *MAT 첫 데이터 줄: MID RO ... (제목 줄은 숫자가 아니라 걸러진다)
        f = s.replace(",", " ").split()
        if len(f) >= 2:
            try:
                ro = float(f[1])
            except ValueError:
                continue        # _TITLE 의 제목 줄 → 다음 줄이 데이터
            if ro > 0:
                dens.append(ro)
            want = False
    if not dens:
        return None
    dens.sort()
    return dens[len(dens) // 2]


def _apply_unit_system(sim_params, output_dir: Path) -> None:
    """덱 단위계를 추정해 MotionData 에 주입.

    impact 쪽 검출기(koo_impact_report.loader._detect_unit_system)를 재사용한다.
    없으면(패키지 부재) 조용히 기본값을 유지한다 — 세 패키지가 항상 함께
    설치되는 것은 아니므로 import 실패로 보고서를 죽이지 않는다.

    판정 근거는 **덱의 *MAT 밀도**다. 애매하면 기본값을 유지하고 사유를 남긴다
    — 틀린 단위로 자신 있게 환산하는 것보다 낫다.
    """
    density = _deck_density(output_dir)
    if density is None:
        print(f"[sphere] 덱 밀도를 못 읽어 단위계 판정 생략 — "
              f"기본 {MotionData.UNIT_SYSTEM} 유지")
        return
    try:
        from koo_impact_report.loader import _detect_unit_system
    except Exception:
        print("[sphere] 단위계 검출기 없음(koo_impact_report 미설치) — "
              f"기본 {MotionData.UNIT_SYSTEM} 유지")
        return

    preset = _detect_unit_system(density)
    uid = str((preset or {}).get("id") or "")
    gf = _G_FACTOR_BY_UNIT.get(uid)
    if not uid or gf is None:
        print(f"[sphere] 단위계 판정 불가 (덱 밀도={density:g}) — "
              f"기본 {MotionData.UNIT_SYSTEM} 유지. peak-G 해석에 주의.")
        return
    if uid != MotionData.UNIT_SYSTEM:
        print(f"[sphere] 단위계 검출: {uid} (덱 밀도={density:g}) — "
              f"G 환산 {MotionData.G_FACTOR:g} → {gf:g}")
    else:
        print(f"[sphere] 단위계 확인: {uid} (덱 밀도={density:g})")
    MotionData.set_unit_system(uid, gf)


def load_dropset(run_dir: Path) -> AngleCondition | None:
    """Load DropSet.json from a run folder."""
    ds_path = run_dir / "DropSet.json"
    if not ds_path.exists():
        return None

    with open(ds_path, encoding="utf-8") as f:
        ds = json.load(f)

    orient = ds.get("initial_conditions", {}).get("orientation_euler_deg", {})
    return AngleCondition(
        angle_name="",  # will be resolved from doe_angles
        roll=orient.get("roll", 0.0),
        pitch=orient.get("pitch", 0.0),
        yaw=orient.get("yaw", 0.0),
    )


def load_part_names(output_dir: Path) -> dict[int, PartInfo]:
    """Load part names from the first available DropSet.json."""
    parts: dict[int, PartInfo] = {}
    for run_dir in sorted(output_dir.iterdir()):
        ds_path = run_dir / "DropSet.json"
        if not ds_path.exists():
            continue
        with open(ds_path, encoding="utf-8") as f:
            ds = json.load(f)
        raw_parts = ds.get("model", {}).get("parts", {})
        for pid_str, pname in raw_parts.items():
            pid = int(pid_str)
            group = PartInfo.extract_group(pname)
            parts[pid] = PartInfo(part_id=pid, part_name=pname, group=group)
        break  # same model for all runs
    return parts


def _downsample_step(n: int, target: int) -> int:
    """Every Nth row to keep, or 1 if target unset / >= n."""
    if target is None or target <= 0 or n <= target:
        return 1
    return max(1, n // target)


def _load_stress_strain_csv(csv_path: Path, target_points: int | None = None) -> TimeSeriesData:
    """Load stress or strain CSV file.

    When target_points is set, the returned lists are downsampled but
    true_peak / true_peak_time retain the exact pre-downsample values.
    """
    ts = TimeSeriesData()
    # Single-pass read: keep all rows, then downsample after computing true peak.
    # (CSV files are small individually; memory bloat comes from retaining
    #  1144 of them simultaneously.)
    all_t: list[float] = []
    all_max: list[float] = []
    all_min: list[float] = []
    all_avg: list[float] = []
    all_eid: list[int] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        max_col = min_col = avg_col = None
        has_eid = False
        for row in reader:
            if max_col is None:
                max_col = next(c for c in row if c.startswith("Max_") and c != "Max_Element_ID")
                min_col = next(c for c in row if c.startswith("Min_") and c != "Min_Element_ID")
                avg_col = next(c for c in row if c.startswith("Avg_"))
                has_eid = "Max_Element_ID" in row
            all_t.append(float(row["Time"]))
            all_max.append(float(row[max_col]))
            all_min.append(float(row[min_col]))
            all_avg.append(float(row[avg_col]))
            if has_eid:
                all_eid.append(int(row["Max_Element_ID"]))

    # Capture true peak before downsampling
    if all_max:
        peak_idx = max(range(len(all_max)), key=all_max.__getitem__)
        ts.true_peak = all_max[peak_idx]
        ts.true_peak_time = all_t[peak_idx]

    step = _downsample_step(len(all_t), target_points)
    ts.times = all_t[::step]
    ts.max_values = all_max[::step]
    ts.min_values = all_min[::step]
    ts.avg_values = all_avg[::step]
    if all_eid:
        ts.max_element_ids = all_eid[::step]
    return ts


def _load_motion_csv(csv_path: Path, target_points: int | None = None) -> MotionData:
    """Load motion CSV file. Downsamples to target_points if given."""
    md = MotionData()
    cols = {
        "avg_disp_x": "Avg_Disp_X", "avg_disp_y": "Avg_Disp_Y", "avg_disp_z": "Avg_Disp_Z",
        "avg_disp_mag": "Avg_Disp_Mag",
        "avg_vel_x": "Avg_Vel_X", "avg_vel_y": "Avg_Vel_Y", "avg_vel_z": "Avg_Vel_Z",
        "avg_vel_mag": "Avg_Vel_Mag",
        "avg_acc_x": "Avg_Acc_X", "avg_acc_y": "Avg_Acc_Y", "avg_acc_z": "Avg_Acc_Z",
        "avg_acc_mag": "Avg_Acc_Mag",
        "max_disp_mag": "Max_Disp_Mag",
    }
    buf: dict[str, list[float]] = {k: [] for k in cols}
    all_t: list[float] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_t.append(float(row["Time"]))
            for k, col in cols.items():
                buf[k].append(float(row[col]))

    # True peaks captured before downsampling
    if buf["avg_acc_mag"]:
        abs_acc = [abs(v) for v in buf["avg_acc_mag"]]
        idx = max(range(len(abs_acc)), key=abs_acc.__getitem__)
        md.true_peak_g = abs_acc[idx] / MotionData.G_FACTOR
        md.true_peak_g_time = all_t[idx]
    if buf["max_disp_mag"]:
        # Eroded elements leave free nodes whose displacement diverges to
        # inf/nan; a single such sample would make true_peak_disp inf and
        # poison the all-angle sphere ranking. Peak over finite samples only.
        finite_disp = [v for v in buf["max_disp_mag"] if math.isfinite(v)]
        n_dropped = len(buf["max_disp_mag"]) - len(finite_disp)
        if n_dropped:
            print(f"[sphere] WARN  {csv_path.name}: dropped {n_dropped} non-finite "
                  f"max_disp sample(s) (eroded free node?) from peak_disp")
        if finite_disp:
            md.true_peak_disp = max(finite_disp)

    step = _downsample_step(len(all_t), target_points)
    md.times = all_t[::step]
    for k in cols:
        setattr(md, k, buf[k][::step])
    return md


def _resolve_angle(
    dropset_angle: AngleCondition,
    doe_angles: dict[str, AngleCondition],
) -> AngleCondition:
    """Match DropSet angle to named DOE angle."""
    key = f"{dropset_angle.roll:.1f}_{dropset_angle.pitch:.1f}_{dropset_angle.yaw:.1f}"
    if key in doe_angles:
        matched = doe_angles[key]
        return AngleCondition(
            angle_name=matched.angle_name,
            roll=dropset_angle.roll,
            pitch=dropset_angle.pitch,
            yaw=dropset_angle.yaw,
            category=matched.category,
        )
    # No match - generate name from angles
    return AngleCondition(
        angle_name=f"R{dropset_angle.roll:.0f}_P{dropset_angle.pitch:.0f}",
        roll=dropset_angle.roll,
        pitch=dropset_angle.pitch,
        yaw=dropset_angle.yaw,
        category="unknown",
    )


def load_simulation_result(
    analysis_dir: Path,
    output_dir: Path,
    run_name: str,
    doe_angles: dict[str, AngleCondition],
    part_info: dict[int, PartInfo],
    target_points: int | None = None,
) -> SimulationResult | None:
    """Load complete analysis result for one run."""
    result_dir = analysis_dir / run_name
    run_output_dir = output_dir / run_name

    # Load angle from DropSet.json
    ds_angle = load_dropset(run_output_dir)
    if ds_angle is None:
        return None
    angle = _resolve_angle(ds_angle, doe_angles)

    # Load analysis_result.json for metadata
    json_path = result_dir / "analysis_result.json"
    if not json_path.exists():
        return None

    with open(json_path, encoding="utf-8") as f:
        ar = json.load(f)

    meta = ar.get("metadata", {})
    sim_result = SimulationResult(
        run_folder=run_name,
        angle=angle,
        num_states=meta.get("num_states", 0),
        start_time=meta.get("start_time", 0.0),
        end_time=meta.get("end_time", 0.0),
    )

    analyzed_parts = set(meta.get("analyzed_parts", []))

    # Load CSV data for each part
    for pid in analyzed_parts:
        pi = part_info.get(pid, PartInfo(part_id=pid, part_name=f"Part_{pid}", group="Unknown"))
        pr = PartResult(part=pi)

        # Stress CSV
        stress_csv = result_dir / "stress" / f"part_{pid}_von_mises.csv"
        if stress_csv.exists():
            pr.stress = _load_stress_strain_csv(stress_csv, target_points)

        # 주응력 CSV (있을 때만 — 구버전 산출물엔 없다). σ1/σ3 각각 독립적으로
        # 없을 수 있으므로 따로 확인한다.
        principal_csv = result_dir / "stress" / f"part_{pid}_max_principal_stress.csv"
        if principal_csv.exists():
            pr.principal = _load_stress_strain_csv(principal_csv, target_points)
        principal_min_csv = result_dir / "stress" / f"part_{pid}_min_principal_stress.csv"
        if principal_min_csv.exists():
            pr.principal_min = _load_stress_strain_csv(principal_min_csv, target_points)

        # 주변형률 ε1/ε3 — 변형률 텐서가 실린 덱에서만 나온다. 없으면 건너뛴다.
        for _attr, _fn in (("principal_strain", "max_principal_strain"),
                           ("principal_strain_min", "min_principal_strain"),
                           ("vm_strain", "von_mises_strain")):
            _csv = result_dir / "strain" / f"part_{pid}_{_fn}.csv"
            if _csv.exists():
                setattr(pr, _attr, _load_stress_strain_csv(_csv, target_points))

        # Strain CSV
        strain_csv = result_dir / "strain" / f"part_{pid}_eff_plastic_strain.csv"
        if strain_csv.exists():
            pr.strain = _load_stress_strain_csv(strain_csv, target_points)

        # Motion CSV
        motion_csv = result_dir / "motion" / f"part_{pid}_motion.csv"
        if motion_csv.exists():
            pr.motion = _load_motion_csv(motion_csv, target_points)

        sim_result.parts[pid] = pr

    return sim_result


def compute_angular_spacing(angles: list[AngleCondition]) -> float:
    """Compute mean nearest-neighbor angular distance in degrees."""
    if len(angles) < 2:
        return 0.0

    # Convert to unit vectors on sphere
    vectors = []
    for a in angles:
        lon, lat = a.to_spherical()
        x = math.cos(lat) * math.cos(lon)
        y = math.cos(lat) * math.sin(lon)
        z = math.sin(lat)
        vectors.append((x, y, z))

    min_dists = []
    for i, v1 in enumerate(vectors):
        nearest = float("inf")
        for j, v2 in enumerate(vectors):
            if i == j:
                continue
            dot = max(-1.0, min(1.0, v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]))
            angle_rad = math.acos(dot)
            nearest = min(nearest, angle_rad)
        if nearest < float("inf"):
            min_dists.append(nearest)

    return math.degrees(sum(min_dists) / len(min_dists)) if min_dists else 0.0


def _import_energy_flow_deps():
    """koo_deep_report 의 flow 빌더/컨택맵/바이나웃 리더를 소프트 임포트.

    설치 안 됐거나 sys.path 에 없으면 sibling 패키지 경로(python/koo_deep_report)
    를 한 번 추가해 재시도. 그래도 실패하면 (None, None, None) — 호출측이 조용히
    에너지 흐름을 건너뛴다(무음 실패 금지 위해 호출측이 로그를 남김).
    """
    try:
        from koo_deep_report.core.binout_reader import parse_binout
        from koo_deep_report.core.contact_map import parse_contact_map
        from koo_deep_report.core.energy_flow_builder import build_flow_graph
        return parse_binout, parse_contact_map, build_flow_graph
    except Exception:
        pass
    try:
        import sys
        # loader.py → koo_sphere_report → python/ → koo_deep_report
        sibling = Path(__file__).resolve().parents[2] / "koo_deep_report"
        if sibling.exists() and str(sibling) not in sys.path:
            sys.path.insert(0, str(sibling))
        from koo_deep_report.core.binout_reader import parse_binout
        from koo_deep_report.core.contact_map import parse_contact_map
        from koo_deep_report.core.energy_flow_builder import build_flow_graph
        return parse_binout, parse_contact_map, build_flow_graph
    except Exception:
        return None, None, None


def _find_binout(run_output_dir: Path) -> Path | None:
    """run 폴더에서 binout 파일 탐색. Output/ 하위 우선."""
    for base in (run_output_dir / "Output", run_output_dir):
        for cand in ("binout0000", "binout", "binout00000"):
            p = base / cand
            if p.exists():
                return p
        bins = sorted(base.glob("binout*")) if base.exists() else []
        if bins:
            return bins[0]
    return None


def _find_kfile(run_output_dir: Path) -> Path | None:
    """run 폴더에서 keyword(.k) 파일 탐색. DropSet.k 우선."""
    for base in (run_output_dir, run_output_dir / "Output"):
        p = base / "DropSet.k"
        if p.exists():
            return p
    for base in (run_output_dir, run_output_dir / "Output"):
        ks = sorted(base.glob("*.k")) if base.exists() else []
        if ks:
            return ks[0]
    return None


def _attach_part_energy(sr, flow: dict) -> None:
    """흐름 그래프의 파트 노드 → SimulationResult.parts[pid].energy.

    흐름 탭(최상위 energy_flows)에만 있던 파트별 IE/KE 를 파트 단위로도
    쓸 수 있게 승격한다. 노드가 없거나 값이 없는 파트는 건드리지 않는다
    (None 유지 — 0 으로 채우면 '계측 안 됨' 이 '0 이었음' 으로 둔갑한다).
    """
    from .models import PartEnergy

    for node in (flow.get("nodes") or []):
        nid = str(node.get("node_id") or "")
        if not nid.isdigit():          # iface:/set: 유령 노드는 파트가 아니다
            continue
        pr = sr.parts.get(int(nid))
        if pr is None:
            continue
        vals = {k: node.get(k) for k in
                ("peak_ie", "peak_ie_time", "peak_ke", "peak_ke_time",
                 "final_ie", "final_ke")}
        if all(v is None for v in vals.values()):
            continue
        pr.energy = PartEnergy(**vals)


def load_energy_flow(
    run_output_dir: Path,
    part_names: dict[int, str],
    deps=None,
) -> dict:
    """한 run 의 binout + keyword → 중립 에너지 흐름 dict.

    자유낙하(임팩터 파트 없음)라 impactor_pid=None — 빌더가 최조기 접촉
    엔드포인트를 root 로 승격한다. 조립 불가(파일 부재/lasso 부재/파싱 실패)면
    빈 dict 를 돌려주고 사유를 stdout 에 남긴다(무음 실패 금지).
    """
    if deps is None:
        deps = _import_energy_flow_deps()
    parse_binout, parse_contact_map, build_flow_graph = deps
    if parse_binout is None:
        return {}

    binout_path = _find_binout(run_output_dir)
    if binout_path is None:
        print(f"[sphere] energy-flow skip {run_output_dir.name}: no binout* file")
        return {}
    try:
        binout = parse_binout(binout_path)
    except Exception as e:
        print(f"[sphere] energy-flow skip {run_output_dir.name}: binout parse failed ({e})")
        return {}
    if binout is None or binout.matsum is None:
        print(f"[sphere] energy-flow skip {run_output_dir.name}: "
              f"no matsum (lasso missing or empty binout)")
        return {}

    # contact_map 은 소프트 — .k 부재/파싱실패면 None(빌더가 pseudo 강등)
    contact_map = None
    kfile = _find_kfile(run_output_dir)
    if kfile is not None:
        try:
            contact_map = parse_contact_map(kfile, part_names=part_names)
        except Exception as e:
            print(f"[sphere] energy-flow {run_output_dir.name}: contact_map failed ({e}), "
                  f"demoting to pseudo nodes")
            contact_map = None

    try:
        g = build_flow_graph(binout, contact_map, part_names,
                             impactor_pid=None, max_pts=120)
    except Exception as e:
        print(f"[sphere] energy-flow skip {run_output_dir.name}: build failed ({e})")
        return {}
    if not g or not g.get("nodes"):
        print(f"[sphere] energy-flow skip {run_output_dir.name}: builder returned empty")
        return {}

    # 접촉력 계측·검증 — binout/contact_map 을 이미 만들었으니 여기서 함께 낸다.
    # 흐름 dict 안에 넣어 두면 per-run 캐시가 그대로 살린다.
    try:
        from koo_deep_report.core.contact_metrics import build_contact_metrics
        g["contact_metrics"] = build_contact_metrics(binout, contact_map, part_names)
    except Exception as e:      # noqa: BLE001
        print(f"[sphere] contact-metrics skip {run_output_dir.name}: {e}")
    return g


# --- per-run 흐름 캐시 --------------------------------------------------------
# <test_dir>/.sphere_flow_cache/v<N>/<run_folder>.json — 흐름이 순수 dict 라
# JSON 왕복이 무손실. best-effort: 읽기/쓰기 실패는 조용히 miss/skip
# (읽기전용 NFS 안전). 지문은 내용 해시가 아닌 stat(size:mtime_ns) — ~ms.
_FLOW_CACHE_SCHEMA = 3   # v3: 흐름 dict 에 contact_metrics(rcforc 계측·검증) 추가


def _flow_fingerprint(run_output_dir: Path) -> str:
    """binout + 사용 .k 의 size:mtime_ns 지문. 파일 부재도 지문에 반영."""
    parts = [f"schema={_FLOW_CACHE_SCHEMA}"]
    for tag, p in (("binout", _find_binout(run_output_dir)),
                   ("kfile", _find_kfile(run_output_dir))):
        if p is None:
            parts.append(f"{tag}=none")
            continue
        try:
            st = p.stat()
            parts.append(f"{tag}={st.st_size}:{st.st_mtime_ns}")
        except OSError:
            parts.append(f"{tag}=missing")
    return "|".join(parts)


def _flow_cache_path(test_dir: Path, run_folder: str) -> Path:
    return test_dir / ".sphere_flow_cache" / f"v{_FLOW_CACHE_SCHEMA}" / f"{run_folder}.json"


def _flow_cache_load(test_dir: Path, run_folder: str, fp: str) -> dict | None:
    """지문 일치 시 캐시된 흐름 dict, 아니면 None(=miss)."""
    try:
        with open(_flow_cache_path(test_dir, run_folder), encoding="utf-8") as f:
            obj = json.load(f)
        if obj.get("fp") != fp:
            return None
        flow = obj.get("flow")
        return flow if isinstance(flow, dict) and flow.get("nodes") else None
    except Exception:  # noqa: BLE001 — 캐시는 언제나 miss 로 강등
        return None


def _flow_cache_save(test_dir: Path, run_folder: str, fp: str, flow: dict) -> None:
    """tmp 에 쓰고 rename(atomic) — 동시 실행/중단에도 반파일 없음. 실패는 skip."""
    import tempfile
    path = _flow_cache_path(test_dir, run_folder)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=str(path.parent), delete=False,
                                         suffix=".tmp", encoding="utf-8") as tf:
            json.dump({"fp": fp, "flow": flow}, tf, ensure_ascii=False)
            tmp_name = tf.name
        Path(tmp_name).replace(path)
    except Exception:  # noqa: BLE001
        pass


def load_all(test_dir: Path) -> tuple[
    str, str, SimulationParams, dict[int, PartInfo],
    list[SimulationResult], dict[str, AngleCondition], dict,
]:
    """Load all data for a test directory.

    Returns: (project_name, doe_strategy, sim_params, part_info, results,
              doe_angles, energy_flows)

    energy_flows: {run_folder: neutral flow dict} — 파트간 접촉 에너지 전달.
    """
    test_dir = Path(test_dir)
    output_dir = test_dir / "output"
    analysis_dir = test_dir / "analysis_results"

    # Load config
    project_name, doe_strategy, sim_params, doe_angles = load_runner_config(test_dir)

    # 단위계 검출 — 실패해도 계속 진행한다(기본 ton-mm-s 유지 + 사유 출력).
    # 여기서 예외가 새면 보고서 전체가 죽으므로 절대 올리지 않는다.
    try:
        _apply_unit_system(sim_params, output_dir)
    except Exception as _e:      # noqa: BLE001
        print(f"[sphere] 단위계 검출 skip ({type(_e).__name__}: {_e}) — "
              f"기본 {MotionData.UNIT_SYSTEM} 유지")

    # Load part names
    part_info = load_part_names(output_dir)

    # Load each analysis result with downsampling to cap RAM use.
    # Target points chosen to give 4x safety margin over the final report's
    # downsample step (html_report/json_report use these same thresholds).
    results: list[SimulationResult] = []
    if analysis_dir.exists():
        run_dirs = [
            d for d in sorted(analysis_dir.iterdir())
            if d.is_dir() and d.name.startswith("Run_")
        ]
        n_runs = len(run_dirs)
        # Same tier formula as html_report.py, but 4x to preserve resolution
        # for possible re-aggregation / alt report configs.
        if n_runs <= 50:
            report_pts = 100
        elif n_runs <= 200:
            report_pts = 30
        elif n_runs <= 500:
            report_pts = 15
        else:
            report_pts = 10
        load_target = report_pts * 4
        for result_folder in run_dirs:
            sr = load_simulation_result(
                analysis_dir, output_dir, result_folder.name, doe_angles, part_info,
                target_points=load_target,
            )
            if sr is not None:
                results.append(sr)

    # Auto-detect pitch/roll convention swap.
    # Standard: roll ∈ [-90, 90] (latitude), pitch ∈ [-180, 180] (longitude).
    # Some DOE generators swap them: pitch ∈ [-90, 90], roll ∈ [-180, 180].
    all_angles = [sr.angle for sr in results]
    if all_angles:
        max_abs_roll = max(abs(a.roll) for a in all_angles)
        max_abs_pitch = max(abs(a.pitch) for a in all_angles)
        need_swap = max_abs_roll > 91 and max_abs_pitch <= 91
        if need_swap:
            for sr in results:
                sr.angle.swap_axes = True
            for ac in doe_angles.values():
                ac.swap_axes = True

    # --- 파트간 에너지 흐름: run 별 binout + keyword → 흐름 dict --------------
    # 결과가 있는 run 만 대상(보고서 탭이 소비). 의존성 부재/파일 부재는
    # load_energy_flow 가 로그 남기고 빈 dict → 여기서 스킵(무회귀).
    # per-run JSON 캐시: 지문(hit) 이면 파싱 생략, 빈 흐름은 캐시하지 않음.
    energy_flows: dict = {}
    part_names = {pid: pi.part_name for pid, pi in part_info.items()}
    deps = _import_energy_flow_deps()
    if deps[0] is not None and results:
        n_hit = 0
        for sr in results:
            run_dir = output_dir / sr.run_folder
            fp = _flow_fingerprint(run_dir)
            g = _flow_cache_load(test_dir, sr.run_folder, fp)
            if g is not None:
                n_hit += 1
            else:
                g = load_energy_flow(run_dir, part_names, deps=deps)
                if g:
                    _flow_cache_save(test_dir, sr.run_folder, fp, g)
            if g:
                energy_flows[sr.run_folder] = g
                _attach_part_energy(sr, g)
        print(f"[sphere] flow cache: {n_hit}/{len(results)} hit")
        n_e = sum(1 for sr in results for pr in sr.parts.values() if pr.energy)
        if n_e:
            print(f"[sphere] 파트별 에너지(IE/KE) 부착: {n_e}건")
    elif deps[0] is None and results:
        print("[sphere] energy-flow: koo_deep_report not importable — "
              "flow tab will be empty (install koo_deep_report + lasso to enable)")

    return (project_name, doe_strategy, sim_params, part_info, results,
            doe_angles, energy_flows)
