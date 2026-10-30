from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark_local import BenchmarkCase, benchmark, percentile
from faultline.simulator import FaultProfile


class BenchmarkContractTests(unittest.TestCase):
    def test_percentile_is_bounded_and_deterministic(self) -> None:
        values = [0.4, 0.1, 0.3, 0.2]
        self.assertEqual(0.1, percentile(values, 0.0))
        self.assertEqual(0.4, percentile(values, 1.0))
        self.assertEqual(0.4, percentile(values, 0.95))

    def test_smoke_case_reconciles(self) -> None:
        result = benchmark(
            BenchmarkCase("test", 20, FaultProfile(duplicate_every=3, corrupt_every=7)),
            repeats=3,
        )
        self.assertTrue(result["reconciled"])
        self.assertGreater(result["median_events_per_second"], 0)


if __name__ == "__main__":
    unittest.main()

