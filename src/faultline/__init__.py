"""Faultline CDC reliability primitives."""

from .models import CdcEvent, ChangeType, OrderRecord, ValidationIssue
from .projector import CdcProjector, IngestDisposition, ReconciliationReport
from .simulator import FaultProfile, generate_order_events, inject_faults

__all__ = [
    "CdcEvent",
    "CdcProjector",
    "ChangeType",
    "FaultProfile",
    "IngestDisposition",
    "OrderRecord",
    "ReconciliationReport",
    "ValidationIssue",
    "generate_order_events",
    "inject_faults",
]

