"""CLI entry point: python -m koo_impact_report"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path


def _parse_severity_weights(spec: str) -> dict[str, float]:
    """Parse ``g=0.5,s=0.3,e=0.2`` → {'g':0.5,'s':0.3,'e':0.2}."""
    out: dict[str, float] = {}
    if not spec:
        return out
    for token in spec.split(","):
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        try:
            out[k.strip()] = float(v.strip())
        except ValueError:
            continue
    return out


def _parse_face_list(spec: str | None) -> list[str] | None:
    if not spec:
        return None
    return [s.strip() for s in spec.split(",") if s.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="koo_impact_report",
        description="Multi-face partial-impact (DWI) DOE analysis report generator",
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--test-dir",
        help="Path to test directory (scenario.json + F*/Run_*/analysis_result.json layout)",
    )
    input_group.add_argument(
        "--from-json",
        metavar="JSON_FILE",
        help="Re-generate report from a previously saved report.json",
    )

    parser.add_argument("--output", "-o", default=None, help="Output HTML file")
    parser.add_argument("--json", default=None, help="Also save report JSON to this path")
    parser.add_argument(
        "--format", nargs="+", default=["html", "terminal"],
        choices=["html", "json", "terminal"],
        help="Output formats (default: html terminal)",
    )

    parser.add_argument(
        "--metric", default="peak_g",
        choices=["peak_g", "peak_stress", "peak_strain", "peak_disp"],
        help="Primary metric used in plots & rankings",
    )
    parser.add_argument("--threshold-critical", type=float, default=None,
                        help="Critical threshold for the primary metric. "
                             "Units match the dataset (no implicit default).")
    parser.add_argument("--threshold-warning", type=float, default=None,
                        help="Warning threshold for the primary metric "
                             "(units match the dataset).")
    parser.add_argument("--yield-stress", type=float, default=None,
                        help="Global yield-stress override (units match peak_stress). "
                             "When omitted, per-part yield comes from the *MAT_ "
                             "card via the loader.")
    parser.add_argument("--faces", default=None,
                        help="Comma-separated face subset (e.g. F1,F2,F5). Default: all discovered.")
    parser.add_argument("--compare-faces", action="store_true",
                        help="Force the 'ALL faces compare' visualization mode")
    parser.add_argument("--severity-weight", default=None,
                        help="Severity weights as 'g=0.5,s=0.3,e=0.2'. "
                             "When omitted, severity score is not computed "
                             "(no implicit default ratio).")
    parser.add_argument("--units", default=None,
                        choices=["SI", "ton-mm-s", "ton-mm-ms", "g-mm-ms"],
                        help="Override solver unit system. When omitted the loader "
                             "auto-detects from density + impactor radius. "
                             "Use this when auto-detection picks the wrong system "
                             "(e.g. SI-style density in a ton-mm-s deck).")

    args = parser.parse_args()

    # Sibling modules — import lazily so missing pieces don't kill --help
    from . import loader, analyzer
    try:
        from .report.html_report import generate_html
    except ImportError:
        def generate_html(report, path: str | None = None, **_):  # type: ignore
            html = "<html><body>STUB - html_report not available</body></html>"
            if path:
                Path(path).write_text(html, encoding="utf-8")
            return html
    try:
        from .report.json_report import save_json
    except ImportError:
        save_json = None  # type: ignore
    try:
        from .report.terminal import print_report
    except ImportError:
        print_report = None  # type: ignore

    # ── Load ──────────────────────────────────────────────────────
    if args.from_json:
        json_in = Path(args.from_json)
        if not json_in.exists():
            print(f"Error: {json_in} does not exist", file=sys.stderr)
            sys.exit(1)
        # No from_json loader implemented yet — placeholder
        print(f"[main] --from-json not yet implemented — please rebuild via --test-dir.")
        sys.exit(2)
    else:
        test_dir = Path(args.test_dir)
        if not test_dir.exists():
            print(f"Error: {test_dir} does not exist", file=sys.stderr)
            sys.exit(1)
        print(f"[main] Loading {test_dir} …")
        t0 = time.time()

        # Layout-aware dispatch:
        #   F*/Run_*/analysis_result.json present  → load_impact_report (face-tree)
        #   else output/Run_* with step_config + (d3plot OR deep_report output)
        #        → load_partial_impact_doe_report (flat DOE). _discover_test_impact_runs
        #        detects runs even when the d3plot was deleted but deep_report output
        #        (analysis_result.json + motion/) survives.
        face_dirs = loader._discover_face_dirs(test_dir)
        flat_runs = loader._discover_test_impact_runs(test_dir)
        if not face_dirs and flat_runs:
            _n_d3 = sum(1 for r in flat_runs if r["d3plot"].exists())
            _n_reuse = sum(1 for r in flat_runs if r.get("deep_dir"))
            print(
                f"[main] flat output/Run_* layout detected ({len(flat_runs)} runs; "
                f"{_n_d3} with d3plot, {_n_reuse} reusing deep_report output) "
                f"→ load_partial_impact_doe_report"
            )
            report = loader.load_partial_impact_doe_report(
                test_dir=test_dir, threads_per_run=2, parallel_runs=4
            )
        else:
            report = loader.load_impact_report(test_dir)
        print(f"[main] Loaded in {time.time() - t0:.1f}s")

        if not report.results:
            print(
                f"[main] ERROR: no (face, position, part) results discovered under {test_dir}. "
                f"Check that either F*/Run_*/analysis_result.json or "
                f"output/Run_*/Output/d3plot exists.",
                file=sys.stderr,
            )
            sys.exit(2)

    # Optional explicit unit-system override (highest priority).
    if args.units:
        preset = loader.get_unit_preset(args.units)
        if preset:
            report.sim_params["units"] = preset["id"]
            report.sim_params["unit_labels"] = preset["labels"]
            print(f"[main] --units override: {preset['id']} "
                  f"(acc={preset['labels']['acc']}, stress={preset['labels']['stress']})")

    # Optional face filter
    face_subset = _parse_face_list(args.faces)
    if face_subset:
        before = len(report.results)
        report.results = [r for r in report.results if r.face in face_subset]
        report.faces = [f for f in report.faces if f.code in face_subset]
        report.positions_by_face = {
            k: v for k, v in report.positions_by_face.items() if k in face_subset
        }
        print(f"[main] Face filter {face_subset}: {before} → {len(report.results)} pair results")

    # Severity weights are parsed for downstream report layers (HTML/severity)
    _ = _parse_severity_weights(args.severity_weight) if args.severity_weight else None
    _ = args.compare_faces  # consumed by html_report

    # Yield-stress dispatch:
    #   • Per-part from the *MAT_ cards (already in sim_params) is preferred.
    #   • Global --yield-stress overrides every part if supplied.
    yield_by_part = dict(report.sim_params.get("yield_stress_by_part", {}) or {})
    if args.yield_stress is not None:
        for p in report.parts:
            yield_by_part[p.part_id] = float(args.yield_stress)

    # ── Analyze ───────────────────────────────────────────────────
    analyzer.analyze(
        report,
        threshold_critical=args.threshold_critical,
        threshold_warning=args.threshold_warning,
        yield_stress_by_part=yield_by_part or None,
    )

    # ── Output ────────────────────────────────────────────────────
    formats = set(args.format)

    if "terminal" in formats and print_report is not None:
        try:
            print_report(report)
        except Exception as e:  # noqa: BLE001
            print(f"[main] terminal output failed: {e}", file=sys.stderr)

    if "html" in formats:
        html_path = args.output or (
            str(Path(args.test_dir) / "report.html") if args.test_dir else "report.html"
        )
        print(f"[main] Generating HTML report: {html_path}")
        t0 = time.time()
        html_str = generate_html(report)
        Path(html_path).write_text(html_str, encoding="utf-8")
        try:
            size_kb = Path(html_path).stat().st_size / 1024
        except OSError:
            size_kb = 0
        print(f"[main] HTML saved in {time.time() - t0:.1f}s ({size_kb:.0f} KB)")

    if "json" in formats and save_json is not None:
        json_path = args.json or (
            str(Path(args.test_dir) / "report.json") if args.test_dir else "report.json"
        )
        save_json(report, json_path)
        print(f"[main] JSON saved: {json_path}")

    print("[main] Done.")


if __name__ == "__main__":
    main()
