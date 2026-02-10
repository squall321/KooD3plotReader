"""Analysis engine: loads data, computes metrics, generates Report with Findings."""
import math
import statistics
from pathlib import Path

from .loader import compute_angular_spacing, load_all
from .models import (
    AngleCondition, Finding, PartInfo, Report, Severity,
    SimulationParams, SimulationResult,
)


def _compute_sphere_coverage(angles: list[AngleCondition]) -> float:
    """Estimate sphere coverage as fraction of 4π steradians.

    Uses Voronoi-like estimation: each point covers ~4π/N steradians
    for uniform distribution. We measure actual uniformity vs ideal.
    """
    n = len(angles)
    if n == 0:
        return 0.0
    # For uniform sphere sampling, ideal spacing = arccos(1 - 2/N)
    # Simple heuristic: coverage ≈ min(1.0, N * avg_solid_angle / 4π)
    # For N=26 cuboid: ~0.6, for N=100 fibonacci: ~0.9, for N=1146: ~1.0
    spacing = compute_angular_spacing(angles)
    if spacing <= 0:
        return 0.0
    # Each point covers a cap of angular radius ≈ spacing/2
    cap_area = 2 * math.pi * (1 - math.cos(math.radians(spacing / 2)))
    total_coverage = n * cap_area / (4 * math.pi)
    return min(1.0, total_coverage)


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
            if pr.peak_stress > worst_stress:
                worst_stress = pr.peak_stress
                worst_angle = sr.angle.label
            if pr.peak_g > worst_g:
                worst_g = pr.peak_g
                worst_g_angle = sr.angle.label
            if pr.peak_strain > worst_strain:
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


def analyze(test_dir: str | Path, yield_stress: float = 0.0) -> Report:
    """Main analysis entry point. Load data and produce Report."""
    test_dir = Path(test_dir)
    project_name, doe_strategy, sim_params, part_info, results, doe_angles = load_all(test_dir)

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
    )

    report.findings = _generate_findings(report)
    return report
