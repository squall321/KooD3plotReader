"""Analysis engine: loads data, computes metrics, generates Report with Findings."""
import math
import statistics
from pathlib import Path

from . import yield_map as YM
from .loader import compute_angular_spacing, load_all
from .models import (
    AngleCondition, Finding, MotionData, PartInfo, Report, Severity,
    SimulationParams, SimulationResult,
)


def _compute_sphere_coverage(angles: list[AngleCondition]) -> float:
    """Estimate sphere coverage using ideal spacing comparison.

    Computes ideal_spacing = sqrt(4π/N) for N points, then compares
    with actual nearest-neighbor spacing. If actual spacing ≤ ideal,
    points are at least as dense as uniform → coverage 100%.
    Otherwise, coverage = (ideal/actual)² capped at 1.0.
    """
    n = len(angles)
    if n == 0:
        return 0.0
    spacing = compute_angular_spacing(angles)
    if spacing <= 0:
        return 0.0
    ideal_spacing = math.degrees(math.sqrt(4 * math.pi / n))
    if spacing <= ideal_spacing:
        return 1.0
    return min(1.0, (ideal_spacing / spacing) ** 2)


def _generate_findings(report: Report) -> list[Finding]:
    """Generate findings based on analysis results."""
    findings: list[Finding] = []

    if not report.results:
        findings.append(Finding(
            severity=Severity.WARNING,
            title="No analysis results found",
            detail="No completed simulation results were found in the analysis_results directory.",
            recommendation="Run the unified_analyzer with --recursive to generate results.",
        ))
        return findings

    # --- INFO findings ---
    findings.append(Finding(
        severity=Severity.INFO,
        title=f"{report.successful_runs}/{report.total_runs} simulations analyzed",
        detail=f"DOE strategy: {report.doe_strategy}, "
               f"Angular spacing: {report.angular_spacing_deg:.1f}°, "
               f"Sphere coverage: {report.sphere_coverage*100:.0f}%",
        recommendation="",
    ))

    if report.failed_runs > 0:
        findings.append(Finding(
            severity=Severity.WARNING,
            title=f"{report.failed_runs} simulation(s) failed or missing",
            detail="Some DOE angles have no analysis results.",
            recommendation="Check simulation logs and re-run failed cases.",
        ))

    # --- 단위계 미검출 ---
    # peak-G 는 단위계에 따라 1e6 배까지 달라진다. 못 정했으면 그 사실이 보고서에
    # 있어야 한다 — stdout 한 줄은 아무도 다시 보지 않는다. 검출은 했지만
    # 단서(note)가 붙은 경우도 같은 자리에 싣는다.
    if not MotionData.UNIT_SYSTEM or MotionData.UNIT_NOTE:
        _detected = bool(MotionData.UNIT_SYSTEM)
        findings.append(Finding(
            severity=Severity.WARNING,
            title=(f"단위계 판정에 단서가 있습니다 ({MotionData.UNIT_SYSTEM}) — "
                   f"peak-G 를 읽기 전에 확인하십시오"
                   if _detected else "단위계 미검출 — peak-G 는 기본 환산값입니다"),
            detail=(MotionData.UNIT_NOTE
                    or f"덱 단위계를 판정하지 못했습니다. peak-G 는 환산 "
                       f"{MotionData.G_FACTOR:g} 로 계산한 값입니다."),
            recommendation=("덱의 *MAT 밀도와 *CONTROL_TERMINATION 종료시각으로 "
                            "단위계를 확인한 뒤 peak-G 를 읽으십시오."),
        ))

    # --- 화면 단위 표기와 덱 단위의 불일치 ---
    # 표·지도·툴팁의 단위 글자는 ton-mm-s(MPa·mm·mm/s) 로 **고정**돼 있다. 값은
    # 덱 단위 그대로 실리므로 SI 덱(Pa·m)이면 글자만 틀린다. 검출에 성공하면 위
    # 미검출 경고도 안 뜨므로, 그 사실을 여기서 말하지 않으면 보고서 안에 단서가
    # 하나도 남지 않는다 (같은 런의 report.json 은 Pa·m 이라고 적는다).
    _SCREEN_UNITS = {"stress": "MPa", "disp": "mm", "vel": "mm/s"}
    _labels = MotionData.UNIT_LABELS or {}
    _off = {k: _labels[k] for k, fixed in _SCREEN_UNITS.items()
            if _labels.get(k) and _labels[k] != fixed}
    if _off:
        findings.append(Finding(
            severity=Severity.WARNING,
            title=f"화면 단위 표기가 이 덱의 단위와 다릅니다 ({MotionData.UNIT_SYSTEM})",
            detail=("화면의 단위 글자는 ton-mm-s 기준(응력 MPa, 변위 mm, 속도 mm/s)"
                    "으로 고정돼 있습니다. 이 덱의 단위는 "
                    + ", ".join(f"{k}={v}" for k, v in sorted(_off.items()))
                    + " 이고 값은 환산 없이 덱 단위 그대로 실려 있습니다 — "
                      "숫자는 맞고 옆에 붙은 단위 글자만 틀립니다."),
            recommendation=("report.json 의 unit_labels 를 기준으로 읽으십시오 "
                            "(federate 비교도 그 라벨을 씁니다)."),
        ))

    # --- Stress-based findings ---
    yield_stress = report.yield_stress
    # 표기 단위는 **검출된 라벨**을 쓴다. 미검출이면 지어내지 않는다.
    ulab = (MotionData.UNIT_LABELS or {}).get("stress", "")
    default_lim, default_note = YM.default_limit(yield_stress, ulab)
    n_default = 0          # 맵에 없어 --yield-stress 로 판정한 파트 수
    n_skipped_unit = 0     # 단위를 몰라 판정을 건너뛴 파트 수
    observed_peaks: dict[int, float] = {}   # 맵 위생 검사용 (파트별 관측 σ_vm)
    for pid, pi in report.part_info.items():
        worst_stress = 0.0
        worst_angle = ""
        worst_g = 0.0
        worst_g_angle = ""
        worst_strain = 0.0
        worst_strain_angle = ""
        worst_principal: float | None = None

        for sr in report.results:
            pr = sr.parts.get(pid)
            if pr is None:
                continue
            # 미계측(None)은 건너뛴다 — 0 으로 비교하면 CSV 가 없는 파트가
            # '응력 0·가속도 0' 으로 findings 에 섞인다.
            if pr.peak_stress is not None and pr.peak_stress > worst_stress:
                worst_stress = pr.peak_stress
                worst_angle = sr.angle.label
            if pr.peak_g is not None and pr.peak_g > worst_g:
                worst_g = pr.peak_g
                worst_g_angle = sr.angle.label
            if pr.peak_strain is not None and pr.peak_strain > worst_strain:
                worst_strain = pr.peak_strain
                worst_strain_angle = sr.angle.label
            # σ1 은 미계측이면 None 이다 — von Mises 로 대체하지 않는다.
            if pr.peak_principal is not None and (
                    worst_principal is None or pr.peak_principal > worst_principal):
                worst_principal = pr.peak_principal

        if worst_stress > 0:
            observed_peaks[pid] = worst_stress

        # ── 항복 판정 ────────────────────────────────────────────────
        # 🔴 예전에는 `--yield-stress`(도움말상 MPa)를 **덱 단위** 응력과 바로
        #    비교하고 표기도 "MPa" 로 박아 두었다. SI 덱에서는 350 을 2.7e8 Pa
        #    와 견주어 안전율이 1.3e-6 으로 나오고 화면에는 "Peak 270000000.0
        #    MPa" 가 떴다 — 항복 판정이 통째로 무의미한데 경고가 없었다.
        #    이제 한계는 **덱 단위**로 맞추고(yield_map), 표기는 검출된 라벨을
        #    쓴다. 단위를 모르면 환산하지 않고 **판정을 건너뛴다.**
        peaks = {YM.VON_MISES: worst_stress or None,
                 YM.MAX_PRINCIPAL: worst_principal}
        lims = (report.part_yields.get(pid).limits
                if getattr(report, "part_yields", None) and pid in report.part_yields
                else [])
        used_default = False
        if not lims and default_lim is not None:
            lims, used_default = [default_lim], True

        if lims and worst_stress > 0:
            v = YM.evaluate(lims, peaks)
            if v.sf is not None:
                b = v.binding
                # 단위가 미검출이면 **지어내지 않는다** — 빈 라벨로 두되
                # 공백이 늘어지지 않게 붙인다. 사유는 별도 finding 이 말한다.
                u = f" {ulab}" if ulab else ""
                where = f" ({b.source})" if b.source else ""
                detail = (f"Peak {v.measured:.4g}{u} [{b.criterion}] at {worst_angle}, "
                          f"한계 {b.value:.4g}{u}{where}, 안전율 {v.sf:.2f}")
                if not v.complete:
                    # 구속하는 한계를 못 쟀을 수 있다 — 안전율이 **실제보다 큰**
                    # 쪽이므로 CRITICAL 로 단정하지 않는다.
                    findings.append(Finding(
                        severity=Severity.WARNING,
                        title=f"Part {pid} ({pi.part_name}): 안전율 {v.sf:.2f} (불완전)",
                        detail=detail + " — " + "; ".join(v.skipped),
                        recommendation="그 기준을 내도록 해석 작업을 걸어 다시 "
                                       "돌리면 완전한 판정이 나옵니다.",
                    ))
                elif v.sf < 1.0:
                    findings.append(Finding(
                        severity=Severity.CRITICAL,
                        title=f"Part {pid} ({pi.part_name}): stress exceeds yield",
                        detail=detail,
                        recommendation=f"Review part design or material for "
                                       f"{worst_angle} direction.",
                    ))
                elif v.sf < 1.5:
                    findings.append(Finding(
                        severity=Severity.WARNING,
                        title=f"Part {pid} ({pi.part_name}): low safety factor {v.sf:.2f}",
                        detail=detail,
                        recommendation="Consider reinforcement or design change.",
                    ))
                if used_default:
                    n_default += 1
        elif worst_stress > 0 and default_note:
            n_skipped_unit += 1

        if worst_g > 50000:
            findings.append(Finding(
                severity=Severity.CRITICAL if worst_g > 200000 else Severity.WARNING,
                title=f"Part {pid} ({pi.part_name}): peak {worst_g/1e6:.2f} MG",
                detail=f"Extreme impact acceleration at {worst_g_angle}",
                recommendation="Verify component shock tolerance specification.",
            ))

    # ── 항복 판정의 바탕을 사실대로 적는다 ───────────────────────────
    # 어떤 값으로 판정했는지 모르면 안전율은 숫자일 뿐이다.
    if n_default:
        findings.append(Finding(
            severity=Severity.INFO,
            title=f"항복 기본값으로 판정한 파트 {n_default}개",
            detail=f"항복 맵에 없는 파트는 --yield-stress {yield_stress:g} MPa 를 "
                   f"썼습니다" + (f" (덱 단위 {ulab} 로 환산)" if ulab else ""),
            recommendation="파트별 값이 필요하면 DropSet.json 의 model.part_yield "
                           "또는 --yield-map 을 쓰십시오.",
        ))
    if n_skipped_unit:
        findings.append(Finding(
            severity=Severity.WARNING,
            title=f"단위를 몰라 항복 판정을 건너뛴 파트 {n_skipped_unit}개",
            detail=f"{default_note or ''} — {MotionData.UNIT_NOTE or '덱 단위 미검출'}",
            recommendation="--yield-map 을 덱 단위로 주거나, 덱의 *MAT 밀도를 "
                           "읽을 수 있게 하면 판정이 됩니다.",
        ))
    _sn = YM.sanity_note(getattr(report, "part_yields", None) or {}, observed_peaks)
    if _sn:
        findings.append(Finding(
            severity=Severity.WARNING,
            title="항복 맵의 자릿수가 관측 응력과 맞지 않습니다",
            detail=_sn,
            recommendation="맵 생성기(KMM)의 단위와 커브 해석을 확인하십시오.",
        ))
    for _n in (getattr(report, "yield_notes", None) or []):
        findings.append(Finding(severity=Severity.INFO, title="항복 맵 안내",
                                detail=str(_n), recommendation=""))

    return findings


def analyze(test_dir: str | Path, yield_stress: float = 0.0,
            yield_map_path: str = "",
            hotspot_part_ids: set[int] | None = None) -> Report:
    """Main analysis entry point. Load data and produce Report.

    hotspot_part_ids: 핫스팟 군집을 이 파트들로만 좁힌다. None 이면 전부 싣는다.
    """
    test_dir = Path(test_dir)
    (project_name, doe_strategy, sim_params, part_info, results,
     doe_angles, energy_flows, tool_builds, drop_reasons) = load_all(
         test_dir, hotspot_part_ids=hotspot_part_ids)

    # Count output run folders to determine total expected
    output_dir = test_dir / "output"
    total_expected = 0
    if output_dir.exists():
        total_expected = sum(
            1 for d in output_dir.iterdir()
            if d.is_dir() and d.name.startswith("Run_")
        )

    all_angles = [sr.angle for sr in results]
    spacing = compute_angular_spacing(all_angles)
    coverage = _compute_sphere_coverage(all_angles)

    report = Report(
        project_name=project_name,
        doe_strategy=doe_strategy,
        simulation_params=sim_params,
        total_runs=max(total_expected, len(results)),
        successful_runs=len(results),
        failed_runs=max(0, total_expected - len(results)),
        results=results,
        part_info=part_info,
        angular_spacing_deg=spacing,
        sphere_coverage=coverage,
        yield_stress=yield_stress,
        test_dir=str(test_dir.resolve()),
        energy_flows=energy_flows,
        tool_builds=tool_builds,
        drop_reasons=drop_reasons,
    )

    # ── 파트별 항복 한계 ─────────────────────────────────────────────
    # 기본은 첫 DropSet.json 의 model.part_yield (경로 배선 불요).
    # --yield-map 은 **명시적 덮어쓰기**다 — 둘 다 덱 단위.
    _py, _unit, _notes = YM.load_from_dropset(output_dir)
    if yield_map_path:
        try:
            _py, _unit, _n2 = YM.load_from_file(yield_map_path)
            _notes = _notes + _n2 + [f"--yield-map {yield_map_path} 로 덮어썼습니다"]
        except (OSError, UnicodeDecodeError, ValueError) as e:
            _notes.append(f"--yield-map {yield_map_path} 를 읽지 못했습니다 "
                          f"({type(e).__name__}: {e}) — 맵 없이 진행합니다")
    # 맵이 말한 단위와 내 검출이 어긋나면 **내 검출을 따르고 말한다**.
    _ulab = (MotionData.UNIT_LABELS or {}).get("stress", "")
    if _unit and _ulab and _unit != _ulab:
        _notes.append(f"항복 맵은 단위를 {_unit} 라 하는데 덱 검출은 {_ulab} 입니다 "
                      f"— 덱 쪽({_ulab})을 따릅니다. 맵 생성기를 확인하십시오.")
    report.part_yields = _py
    report.yield_notes = _notes

    report.findings = _generate_findings(report)
    return report
