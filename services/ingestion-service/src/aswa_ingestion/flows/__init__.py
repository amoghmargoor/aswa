"""Prefect workflow orchestration for ASWA ingestion service.

This module provides Prefect flows for:
- Data source synchronization
- Document processing
- Alert evaluation and notifications
"""

from aswa_ingestion.flows.sync_flow import sync_data_source, scheduled_sync_all
from aswa_ingestion.flows.processing_flow import process_pending_documents
from aswa_ingestion.flows.alert_flow import evaluate_alerts

__all__ = [
    "sync_data_source",
    "scheduled_sync_all",
    "process_pending_documents",
    "evaluate_alerts",
]
