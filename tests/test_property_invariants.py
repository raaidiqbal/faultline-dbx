from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from faultline.projector import CdcProjector
from faultline.simulator import FaultProfile, generate_order_events, inject_faults


def project(events: list) -> CdcProjector:
    projector = CdcProjector()
    projector.ingest_many(events)
    return projector


class ArrivalOrderPropertyTests(unittest.TestCase):
    """Seeded property checks for the projector's convergence contract."""

    def test_random_delivery_orders_converge_to_the_same_state(self) -> None:
        for seed in range(40):
            with self.subTest(seed=seed):
                canonical, shuffled = self._workload_pair(seed)

                expected = project(canonical)
                actual = project(shuffled)

                self.assertTrue(actual.reconcile().reconciled)
                self.assertEqual(expected.current, actual.current)

    def test_fault_counters_are_arrival_order_invariant(self) -> None:
        for seed in range(40):
            with self.subTest(seed=seed):
                canonical, shuffled = self._workload_pair(seed)

                expected_report = project(canonical).reconcile()
                actual_report = project(shuffled).reconcile()

                self.assertEqual(
                    (
                        expected_report.received_events,
                        expected_report.accepted_events,
                        expected_report.duplicate_events,
                        expected_report.quarantined_events,
                    ),
                    (
                        actual_report.received_events,
                        actual_report.accepted_events,
                        actual_report.duplicate_events,
                        actual_report.quarantined_events,
                    ),
                )

    def test_delete_tombstones_are_arrival_order_invariant(self) -> None:
        for seed in range(40):
            with self.subTest(seed=seed):
                canonical, shuffled = self._workload_pair(seed)

                expected_report = project(canonical).reconcile()
                actual_report = project(shuffled).reconcile()

                self.assertEqual(expected_report.deleted_entities, actual_report.deleted_entities)
                self.assertEqual(expected_report.current_records, actual_report.current_records)

    def test_quarantine_reasons_are_arrival_order_invariant(self) -> None:
        for seed in range(40):
            with self.subTest(seed=seed):
                canonical, shuffled = self._workload_pair(seed)

                expected = project(canonical)
                actual = project(shuffled)

                expected_issues = sorted(
                    (item.event.idempotency_key, tuple(issue.code for issue in item.issues))
                    for item in expected.quarantine
                )
                actual_issues = sorted(
                    (item.event.idempotency_key, tuple(issue.code for issue in item.issues))
                    for item in actual.quarantine
                )
                self.assertEqual(expected_issues, actual_issues)

    @staticmethod
    def _workload_pair(seed: int) -> tuple[list, list]:
        rng = random.Random(seed)
        events = generate_order_events(
            rng.randint(10, 100),
            delete_every=rng.choice((0, 5, 10, 13)),
        )
        delivered = inject_faults(
            events,
            FaultProfile(
                duplicate_every=rng.randint(2, 11),
                corrupt_every=rng.randint(3, 17),
                reverse_window=rng.randint(2, 13),
            ),
        )
        shuffled = list(delivered)
        rng.shuffle(shuffled)
        return delivered, shuffled


if __name__ == "__main__":
    unittest.main()
