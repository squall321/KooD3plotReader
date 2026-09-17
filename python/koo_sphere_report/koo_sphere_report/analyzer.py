"""Analysis engine: loads data, computes metrics, generates Report with Findings."""
import math
import statistics
from pathlib import Path

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
    # 있어야 한다 — stdout 한 줄은 아무도 다시 보지 않는다.
    # 검출은 했지만 단서(note)가 붙은 경우도 같은 자리에 싣는다 — 그 단서를
    # stdout 에만 두면 아무도 다시 보지 않는다.
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

    # --- Stress-based findings ---
    yield_stress = report.yield_stress
    for pid, pi in report.part_info.items():
        worst_stress = 0.0
        worst_angle = ""
        worst_g = 0.0
        worst_g_angle = ""
        worst_strain = 0.0
        worst_strain_angle = ""

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

        if yield_stress > 0 and worst_stress > yield_stress:
            sf = yield_stress / worst_stress if worst_stress > 0 else float("inf")
            findings.append(Finding(
                severity=Severity.CRITICAL,
                title=f"Part {pid} ({pi.part_name}): stress exceeds yield",
                detail=f"Peak {worst_stress:.1f} MPa at {worst_angle}, "
                       f"Safety Factor = {sf:.2f}",
                recommendation=f"Review part design or material for {worst_angle} direction.",
            ))
        elif worst_stress > 0:
            if yield_stress > 0:
                sf = yield_stress / worst_stress
                if sf < 1.5:
                    findings.append(Finding(
                        severity=Severity.WARNING,
                        title=f"Part {pid} ({pi.part_name}): low safety factor {sf:.2f}",
                        detail=f"Peak {worst_stress:.1f} MPa at {worst_angle}",
                        recommendation="Consider reinforcement or design change.",
                    ))

        if worst_g > 50000:
            findings.append(Finding(
                severity=Severity.CRITICAL if worst_g > 200000 else Severity.WARNING,
                title=f"Part {pid} ({pi.part_name}): peak {worst_g/1e6:.2f} MG",
                detail=f"Extreme impact acceleration at {worst_g_angle}",
                recommendation="Verify component shock tolerance specification.",
            ))

    return findings


def analyze(test_dir: str | Path, yield_stress: float = 0.0,
            hotspot_part_ids: set[int] | None = None) -> Report:
    """Main analysis entry point. Load data and produce Report.

    hotspot_part_ids: 핫스팟 군집을 이 파트들로만 좁힌다. None 이면 전부 싣는다.
    """
    test_dir = Path(test_dir)
    (project_name, doe_strategy, sim_params, part_info, results,
     doe_angles, energy_flows, tool_builds) = load_all(
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
    )

    report.findings = _generate_findings(report)
    return report
