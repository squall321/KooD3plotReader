"""Rich terminal output for ImpactReport."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..models import ImpactReport, Severity


SEVERITY_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.WARNING:  "bold yellow",
    Severity.INFO:     "bold blue",
}
SEVERITY_LABEL = {
    Severity.CRITICAL: "[CRITICAL]",
    Severity.WARNING:  "[WARNING]",
    Severity.INFO:     "[INFO]",
}


def print_report(report: ImpactReport) -> None:
    console = Console()

    # ── Header panel ─────────────────────────────────────────────
    n_positions = sum(len(v) for v in report.positions_by_face.values())
    imp = report.impactor

    console.print()
    console.print(Panel(
        f"[bold]{report.project_name or '(unnamed)'}[/bold]\n"
        f"Impactor: {imp.type}  h={imp.height:.0f} mm  v={imp.velocity:.0f} mm/s  "
        f"KE={imp.kinetic_energy*1e-6:.2f} J\n"
        f"Mode: {report.generation_mode}  "
        f"boundary={report.boundary_distance:.1f} mm  offset={report.offset_distance:.3f} mm",
        title="[bold cyan]KooImpactReport — Multi-Face DWI Analysis[/]",
        border_style="cyan",
    ))

    # ── KPI table ─────────────────────────────────────────────────
    kpi = Table(title="Key Performance Indicators")
    kpi.add_column("Metric", style="cyan")
    kpi.add_column("Value", justify="right")

    gmax = max((r.peak_g for r in report.results), default=0.0)
    smax = max((r.peak_stress for r in report.results), default=0.0)
    emax = max((r.peak_strain for r in report.results), default=0.0)

    kpi.add_row("Faces",      str(len(report.faces)))
    kpi.add_row("Positions",  str(n_positions))
    kpi.add_row("Parts",      str(len(report.parts)))
    kpi.add_row("Pair rows",  str(len(report.results)))
    kpi.add_row("Peak G",     f"{gmax/1e6:.2f} MG")
    kpi.add_row("Peak stress", f"{smax:.1f} MPa")
    kpi.add_row("Peak strain", f"{emax:.4f}")
    console.print(kpi)

    # ── Top 5 worst pairs ─────────────────────────────────────────
    if report.results:
        worst = sorted(report.results, key=lambda r: r.peak_g, reverse=True)[:5]
        tbl = Table(title="Top 5 Worst (face × position × part) — by peak_g")
        tbl.add_column("#", style="dim")
        tbl.add_column("Face", style="cyan")
        tbl.add_column("Position")
        tbl.add_column("Part", style="yellow")
        tbl.add_column("Peak G", justify="right")
        tbl.add_column("σ (MPa)", justify="right")
        tbl.add_column("ε", justify="right")

        part_lookup = {p.part_id: p for p in report.parts}
        for i, r in enumerate(worst, 1):
            pi = part_lookup.get(r.part_id)
            pname = pi.part_name if pi else f"Part {r.part_id}"
            tbl.add_row(
                str(i),
                r.face,
                f"{r.position.pos_id} ({r.position.x:.1f},{r.position.y:.1f})",
                pname,
                f"{r.peak_g/1e6:.2f} MG",
                f"{r.peak_stress:.1f}",
                f"{r.peak_strain:.4f}",
            )
        console.print(tbl)

    # ── Findings ──────────────────────────────────────────────────
    n_crit = sum(1 for f in report.findings if f.severity == Severity.CRITICAL)
    n_warn = sum(1 for f in report.findings if f.severity == Severity.WARNING)
    n_info = sum(1 for f in report.findings if f.severity == Severity.INFO)
    console.print(Panel(
        f"[bold red]{n_crit} critical[/] | "
        f"[bold yellow]{n_warn} warning[/] | "
        f"[bold blue]{n_info} info[/]",
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

    console.print()
