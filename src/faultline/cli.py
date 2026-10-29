from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Sequence

from .projector import CdcProjector
from .simulator import FaultProfile, generate_order_events, inject_faults


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="faultline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    simulate = subparsers.add_parser("simulate", help="run a deterministic CDC fault scenario")
    simulate.add_argument("--entities", type=int, default=100)
    simulate.add_argument("--delete-every", type=int, default=10)
    simulate.add_argument("--duplicate-every", type=int, default=7)
    simulate.add_argument("--corrupt-every", type=int, default=11)
    simulate.add_argument("--reverse-window", type=int, default=5)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "simulate":
        raise AssertionError(f"unsupported command: {args.command}")

    baseline = generate_order_events(args.entities, delete_every=args.delete_every)
    profile = FaultProfile(
        duplicate_every=args.duplicate_every,
        corrupt_every=args.corrupt_every,
        reverse_window=args.reverse_window,
    )
    delivered = inject_faults(baseline, profile)
    projector = CdcProjector()
    projector.ingest_many(delivered)
    report = projector.reconcile()

    output = {
        "scenario": {
            "baseline_events": len(baseline),
            "delivered_events": len(delivered),
            "entities": args.entities,
            **asdict(profile),
        },
        "result": {
            **asdict(report),
            "reconciled": report.reconciled,
        },
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if report.reconciled else 1

