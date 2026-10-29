from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from faultline.projector import CdcProjector
from faultline.simulator import FaultProfile, generate_order_events, inject_faults


class SimulatorTests(unittest.TestCase):
    def test_fault_injection_is_deterministic(self) -> None:
        events = generate_order_events(12, delete_every=4)
        profile = FaultProfile(duplicate_every=3, corrupt_every=5, reverse_window=4)

        first = inject_faults(events, profile)
        second = inject_faults(events, profile)

        self.assertEqual(first, second)

    def test_mixed_faults_preserve_reconciliation_invariant(self) -> None:
        events = generate_order_events(100, delete_every=10)
        delivered = inject_faults(
            events,
            FaultProfile(duplicate_every=7, corrupt_every=11, reverse_window=5),
        )
        projector = CdcProjector()

        projector.ingest_many(delivered)
        report = projector.reconcile()

        self.assertGreater(report.duplicate_events, 0)
        self.assertGreater(report.quarantined_events, 0)
        self.assertTrue(report.reconciled)

    def test_invalid_profile_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FaultProfile(duplicate_every=-1)


if __name__ == "__main__":
    unittest.main()
