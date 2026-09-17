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


def _fmt(v, spec: str) -> str:
    """미계측은 '미계측' 으로 — 0 으로 찍지 않는다."""
    if v is None:
        return "미계측"
    return format(float(v), spec)


def print_report(report: ImpactReport) -> None:
    console = Console()

    # ── Header panel ─────────────────────────────────────────────
    n_positions = sum(len(v) for v in report.positions_by_face.values())
    imp = report.impactor

    # Detect dataset unit system from sim_params (set by the loader).
    units_label = str(report.sim_params.get("units", "")) if report.sim_params else ""

    console.print()
    console.print(Panel(
        f"[bold]{report.project_name or '(unnamed)'}[/bold]\n"
        f"Impactor: {imp.type or 'unknown'}  h={imp.height:.3g}  "
        f"v={imp.velocity:.3g}  KE={imp.kinetic_energy:.3g}\n"
        f"Mode: {report.generation_mode or '(none)'}  "
        f"boundary={report.boundary_distance:.3g}  offset={report.offset_distance:.3g}  "
        f"units={units_label or '(unspecified)'}",
        title="[bold cyan]KooImpactReport — Multi-Face DWI Analysis[/]",
        border_style="cyan",
    ))

    # ── KPI table ─────────────────────────────────────────────────
    kpi = Table(title="Key Performance Indicators")
    kpi.add_column("Metric", style="cyan")
    kpi.add_column("Value", justify="right")

    # 미계측(None)은 빼고 최대를 구한다 — 0 으로 세지 않는다.
    def _vals(metric):
        return [getattr(r, metric) for r in report.results
                if getattr(r, metric, None) is not None]

    gmax = max(_vals("peak_g"), default=0.0)
    smax = max(_vals("peak_stress"), default=0.0)
    emax = max(_vals("peak_strain"), default=0.0)

    kpi.add_row("Faces",      str(len(report.faces)))
    kpi.add_row("Positions",  str(n_positions))
    kpi.add_row("Parts",      str(len(report.parts)))
    kpi.add_row("Pair rows",  str(len(report.results)))
    kpi.add_row("Peak |a|",   f"{gmax:.3e}")
    kpi.add_row("Peak σ",     f"{smax:.3e}")
    kpi.add_row("Peak ε",     f"{emax:.3g}")
    console.print(kpi)

    # ── Top 5 worst pairs ─────────────────────────────────────────
    if report.results:
        worst = sorted((r for r in report.results if r.peak_g is not None),
                       key=lambda r: r.peak_g, reverse=True)[:5]
        tbl = Table(title="Top 5 Worst (face × position × part) — by peak_g")
        tbl.add_column("#", style="dim")
        tbl.add_column("Face", style="cyan")
        tbl.add_column("Position")
        tbl.add_column("Part", style="yellow")
        tbl.add_column("Peak |a|", justify="right")
        tbl.add_column("Peak σ", justify="right")
        tbl.add_column("Peak ε", justify="right")

        part_lookup = {p.part_id: p for p in report.parts}
        for i, r in enumerate(worst, 1):
            pi = part_lookup.get(r.part_id)
            pname = pi.part_name if pi else f"Part {r.part_id}"
            tbl.add_row(
                str(i),
                r.face,
                f"{r.position.pos_id} ({r.position.x:.1f},{r.position.y:.1f})",
                pname,
                _fmt(r.peak_g, ".3e"),
                _fmt(r.peak_stress, ".3e"),
                # ε 은 1e-5 규모가 흔하다 — .4f 는 전부 0.0000 이 된다.
                _fmt(r.peak_strain, ".3g"),
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
