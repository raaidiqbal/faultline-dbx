from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
import time

from faultline.projector import CdcProjector
from faultline.simulator import FaultProfile, generate_order_events, inject_faults


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    name: str
    entities: int
    profile: FaultProfile


CASES = (
    BenchmarkCase("baseline-100", 100, FaultProfile()),
    BenchmarkCase("mixed-100", 100, FaultProfile(7, 11, 5)),
    BenchmarkCase("mixed-1000", 1_000, FaultProfile(7, 11, 5)),
    BenchmarkCase("mixed-10000", 10_000, FaultProfile(7, 11, 5)),
    BenchmarkCase("severe-10000", 10_000, FaultProfile(2, 13, 50)),
)


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * quantile + 0.5))
    return ordered[index]


def benchmark(case: BenchmarkCase, repeats: int) -> dict[str, object]:
    baseline = generate_order_events(case.entities, delete_every=10)
    delivered = inject_faults(baseline, case.profile)
    timings: list[float] = []
    final_report = None

    for _ in range(repeats):
        projector = CdcProjector()
        started = time.perf_counter()
        projector.ingest_many(delivered)
        final_report = projector.reconcile()
        timings.append(time.perf_counter() - started)

    assert final_report is not None
    assert final_report.reconciled, final_report.invariant_violations
    median_seconds = median(timings)
    return {
        "name": case.name,
        "entities": case.entities,
        "fault_profile": asdict(case.profile),
        "baseline_events": len(baseline),
        "delivered_events": len(delivered),
        "accepted_events": final_report.accepted_events,
        "duplicate_events": final_report.duplicate_events,
        "quarantined_events": final_report.quarantined_events,
        "current_records": final_report.current_records,
        "reconciled": final_report.reconciled,
        "median_seconds": round(median_seconds, 6),
        "p95_seconds": round(percentile(timings, 0.95), 6),
        "median_events_per_second": round(len(delivered) / median_seconds),
        "runs_seconds": [round(value, 6) for value in timings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark deterministic CDC projection")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error("--repeats must be at least 3")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "Median and p95 wall time across repeated in-memory ingest plus independent "
            "reconciliation; event generation and fault injection excluded."
        ),
        "repeats": args.repeats,
        "cases": [benchmark(case, args.repeats) for case in CASES],
    }
    serialized = json.dumps(output, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{serialized}\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

