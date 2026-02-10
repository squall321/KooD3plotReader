"""Rich terminal report output."""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..models import Report, Severity

SEVERITY_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.WARNING: "bold yellow",
    Severity.INFO: "bold blue",
}
SEVERITY_LABEL = {
    Severity.CRITICAL: "[CRITICAL]",
    Severity.WARNING: "[WARNING]",
    Severity.INFO: "[INFO]",
}


def print_report(report: Report) -> None:
    console = Console()

    # Header
    console.print()
    console.print(Panel(
        f"[bold]{report.project_name}[/bold]\n"
        f"DOE: {report.doe_strategy} | "
        f"Runs: {report.successful_runs}/{report.total_runs} | "
        f"Spacing: {report.angular_spacing_deg:.1f}° | "
        f"Coverage: {report.sphere_coverage*100:.0f}%",
        title="[bold cyan]KooReport - Drop Simulation Analysis[/]",
        border_style="cyan",
    ))

    # Findings
    n_crit = sum(1 for f in report.findings if f.severity == Severity.CRITICAL)
    n_warn = sum(1 for f in report.findings if f.severity == Severity.WARNING)
    n_info = sum(1 for f in report.findings if f.severity == Severity.INFO)

    console.print(Panel(
        f"[bold red]{n_crit} critical[/] | [bold yellow]{n_warn} warning[/] | [bold blue]{n_info} info[/]",
        title="Diagnostics",
    ))

    for f in report.findings:
        style = SEVERITY_STYLE[f.severity]
        label = SEVERITY_LABEL[f.severity]
        console.print(f"  [{style}]{label}[/] {f.title}")
        if f.detail:
            console.print(f"    [dim]{f.detail}[/]")
        if f.recommendation:
            console.print(f"    [italic]>> {f.recommendation}[/]")

    # Worst-case table
    if report.results:
        console.print()
        table = Table(title="Worst-Case Summary (All Angles)")
        table.add_column("Part", style="cyan", no_wrap=True)
        table.add_column("Group", style="dim")
        table.add_column("Peak Stress (MPa)", justify="right")
        table.add_column("Worst Angle", style="yellow")
        table.add_column("Peak MG", justify="right")
        table.add_column("G Angle", style="yellow")
        table.add_column("Peak Strain", justify="right")

        for pid in sorted(report.part_info.keys()):
            pi = report.part_info[pid]
            ws, wa, wg, wga, wst = 0.0, "", 0.0, "", 0.0
            for sr in report.results:
                pr = sr.parts.get(pid)
                if pr is None:
                    continue
                if pr.peak_stress > ws:
                    ws = pr.peak_stress
                    wa = sr.angle.label
                if pr.peak_g > wg:
                    wg = pr.peak_g
                    wga = sr.angle.label
                if pr.peak_strain > wst:
                    wst = pr.peak_strain

            if ws > 0 or wg > 0:
                table.add_row(
                    f"Part {pid}",
                    pi.group,
                    f"{ws:.1f}",
                    wa,
                    f"{wg/1e6:.2f}",
                    wga,
                    f"{wst:.4f}",
                )

        console.print(table)

    # Simulation params
    console.print()
    sp = report.simulation_params
    param_table = Table(title="Simulation Parameters")
    param_table.add_column("Parameter", style="cyan")
    param_table.add_column("Value")
    param_table.add_row("Drop Height", f"{sp.drop_height:.0f} mm")
    param_table.add_row("Duration", f"{sp.t_final*1000:.2f} ms")
    param_table.add_row("Time Step", f"{sp.dt*1e6:.2f} μs")
    param_table.add_row("Material Density", f"{sp.density:.0f} kg/m³")
    param_table.add_row("Young's Modulus", f"{sp.youngs_modulus/1e9:.0f} GPa")
    console.print(param_table)
    console.print()
