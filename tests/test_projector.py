from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from faultline.models import ChangeType
from faultline.projector import CdcProjector, IngestDisposition
from faultline.simulator import FaultProfile, generate_order_events, inject_faults


class CdcProjectorTests(unittest.TestCase):
    def test_duplicate_delivery_is_idempotent(self) -> None:
        events = generate_order_events(3, delete_every=0)
        projector = CdcProjector()

        first = projector.ingest(events[0])
        second = projector.ingest(events[0])

        self.assertEqual(IngestDisposition.APPLIED, first)
        self.assertEqual(IngestDisposition.DUPLICATE, second)
        self.assertEqual(1, projector.reconcile().duplicate_events)
        self.assertTrue(projector.reconcile().reconciled)

    def test_out_of_order_delivery_converges(self) -> None:
        events = generate_order_events(25, delete_every=5)
        delivered = inject_faults(events, FaultProfile(reverse_window=9))
        projector = CdcProjector()

        projector.ingest_many(delivered)
        report = projector.reconcile()

        self.assertTrue(report.reconciled)
        self.assertEqual(20, report.current_records)
        self.assertEqual(5, report.deleted_entities)

    def test_invalid_event_is_quarantined(self) -> None:
        event = generate_order_events(1, delete_every=0)[0]
        invalid = replace(event, payload={"amount_cents": -50, "status": "created"})
        projector = CdcProjector()

        disposition = projector.ingest(invalid)

        self.assertEqual(IngestDisposition.QUARANTINED, disposition)
        self.assertEqual("invalid_amount", projector.quarantine[0].issues[0].code)
        self.assertTrue(projector.reconcile().reconciled)

    def test_newer_delete_removes_current_record(self) -> None:
        events = generate_order_events(10, delete_every=10)
        projector = CdcProjector()
        projector.ingest_many(events)

        self.assertNotIn("order-000010", projector.current)
        self.assertTrue(projector.reconcile().reconciled)

    def test_older_update_cannot_resurrect_deleted_record(self) -> None:
        events = generate_order_events(10, delete_every=10)
        delete = next(event for event in events if event.change_type is ChangeType.DELETE)
        older_update = next(
            event
            for event in events
            if event.entity_id == delete.entity_id and event.change_type is ChangeType.UPDATE
        )
        projector = CdcProjector()

        projector.ingest(delete)
        disposition = projector.ingest(older_update)

        self.assertEqual(IngestDisposition.SUPERSEDED, disposition)
        self.assertNotIn(delete.entity_id, projector.current)
        self.assertTrue(projector.reconcile().reconciled)


if __name__ == "__main__":
    unittest.main()

