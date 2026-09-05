"""Command-line entry point. ``python -m autoscaler_lab.cli run-offline ...``"""

from __future__ import annotations

import argparse
from pathlib import Path

from autoscaler_lab.experiment import run_matrix


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autoscaler_lab")
    sub = parser.add_subparsers(dest="command", required=True)

    offline = sub.add_parser("run-offline", help="run the offline experiment matrix")
    offline.add_argument("--config", type=Path, required=True)
    offline.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.command == "run-offline":
        summaries = run_matrix(args.config, args.output)
        print(f"wrote {len(summaries)} runs to {args.output}/summary.json")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
