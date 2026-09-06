"""Command-line entry point. ``python -m autoscaler_lab.cli run-offline ...``"""

from __future__ import annotations

import argparse
from pathlib import Path

from autoscaler_lab.experiment import run_matrix
from autoscaler_lab.report import render_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autoscaler_lab")
    sub = parser.add_subparsers(dest="command", required=True)

    offline = sub.add_parser("run-offline", help="run the offline experiment matrix")
    offline.add_argument("--config", type=Path, required=True)
    offline.add_argument("--output", type=Path, required=True)

    report = sub.add_parser("render-report", help="render docs/results.md from summary.json")
    report.add_argument("--summary", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.command == "run-offline":
        summaries = run_matrix(args.config, args.output)
        print(f"wrote {len(summaries)} runs to {args.output}/summary.json")
        return 0

    if args.command == "render-report":
        render_report(args.summary, args.output)
        print(f"wrote report to {args.output}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
