"""CLI entry point: python -m koo_sphere_report"""
import argparse
import sys
import time
from pathlib import Path

from .analyzer import analyze
from .report.html_report import generate_html
from .report.json_report import save_json


def main():
    parser = argparse.ArgumentParser(
        prog="koo_sphere_report",
        description="KooReport - Full-angle drop simulation analysis report",
    )

    # Mutually exclusive input modes
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--test-dir",
        help="Path to test directory with analysis_results/ (d3plot mode)",
    )
    input_group.add_argument(
        "--from-json",
        metavar="JSON_FILE",
        help="Re-generate report from an existing report.json (no d3plot needed)",
    )

    parser.add_argument(
        "--output", "-o", default=None,
        help="Output HTML file path",
    )
    parser.add_argument(
        "--json", default=None,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--terminal-only", action="store_true",
        help="Print terminal report only, no file output",
    )
    parser.add_argument(
        "--format", nargs="+", default=["html", "terminal"],
        choices=["html", "json", "terminal"],
        help="Output formats (default: html terminal)",
    )
    parser.add_argument(
        "--yield-stress", type=float, default=0.0,
        help="Material yield stress (MPa) for safety factor calculation",
    )
    parser.add_argument(
        "--ts-points", type=int, default=0,
        help="Time series points per chart (0=auto)",
    )
    args = parser.parse_args()

    # ── Load data ────────────────────────────────────────────
    if args.from_json:
        from .from_json import load_report_from_json
        json_in = Path(args.from_json)
        if not json_in.exists():
            print(f"Error: {json_in} does not exist", file=sys.stderr)
            sys.exit(1)
        print(f"Loading from JSON: {json_in}")
        t0 = time.time()
        report = load_report_from_json(json_in, yield_stress=args.yield_stress)
        base_dir = str(json_in.parent.resolve())
        print(f"Loaded {report.successful_runs} results in {time.time()-t0:.1f}s")
    else:
        test_dir = Path(args.test_dir)
        if not test_dir.exists():
            print(f"Error: {test_dir} does not exist", file=sys.stderr)
            sys.exit(1)
        if not (test_dir / "analysis_results").exists():
            print(f"Error: No analysis_results in {test_dir}", file=sys.stderr)
            print("Run unified_analyzer --recursive first.", file=sys.stderr)
            sys.exit(1)
        print(f"Loading data from {test_dir}...")
        t0 = time.time()
        report = analyze(test_dir, yield_stress=args.yield_stress)
        base_dir = str(test_dir.resolve())
        print(f"Loaded {report.successful_runs} results in {time.time()-t0:.1f}s")

    formats = ["terminal"] if args.terminal_only else args.format

    # ── Terminal output ──────────────────────────────────────
    if "terminal" in formats:
        try:
            from .report.terminal import print_report
            print_report(report)
        except ImportError:
            print("Warning: rich not installed, skipping terminal output", file=sys.stderr)

    # ── HTML output ──────────────────────────────────────────
    if "html" in formats:
        if args.output:
            html_path = args.output
        elif args.from_json:
            html_path = str(Path(args.from_json).with_suffix(".html"))
        else:
            html_path = str(Path(args.test_dir) / "report.html")
        print(f"Generating HTML report: {html_path}")
        t0 = time.time()
        generate_html(report, html_path, ts_points=args.ts_points, test_dir=base_dir)
        print(f"HTML report saved in {time.time()-t0:.1f}s ({Path(html_path).stat().st_size/1024:.0f} KB)")

    # ── JSON output ──────────────────────────────────────────
    if "json" in formats:
        if args.json:
            json_path = args.json
        elif args.from_json:
            json_path = str(Path(args.from_json).parent / (report.project_name + "_regenerated.json"))
        else:
            json_path = str(Path(args.test_dir) / "report.json")
        save_json(report, json_path)
        print(f"JSON report saved: {json_path}")

    print("Done.")


if __name__ == "__main__":
    main()
