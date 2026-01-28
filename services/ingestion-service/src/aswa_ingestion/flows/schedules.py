"""Prefect deployment and schedule configuration.

Defines deployments for all flows with their schedules and
work queue assignments.
"""

import asyncio
from datetime import timedelta

from prefect.deployments import Deployment
from prefect.server.schemas.schedules import CronSchedule, IntervalSchedule

from aswa_ingestion.flows.sync_flow import scheduled_sync_all, sync_data_source
from aswa_ingestion.flows.processing_flow import (
    process_pending_documents,
    reprocess_failed_documents,
)
from aswa_ingestion.flows.alert_flow import evaluate_alerts


def create_sync_deployments() -> list[Deployment]:
    """Create deployments for sync flows.

    Returns:
        List of sync-related deployments
    """
    deployments = []

    # Sync all data sources every hour
    hourly_sync = Deployment.build_from_flow(
        flow=scheduled_sync_all,
        name="hourly-sync-all",
        description="Sync all active data sources hourly",
        schedule=IntervalSchedule(interval=timedelta(hours=1)),
        work_queue_name="sync-queue",
        tags=["sync", "scheduled", "hourly"],
        parameters={},
    )
    deployments.append(hourly_sync)

    # Daily full sync at midnight
    daily_full_sync = Deployment.build_from_flow(
        flow=scheduled_sync_all,
        name="daily-full-sync",
        description="Full sync all data sources daily at midnight",
        schedule=CronSchedule(cron="0 0 * * *", timezone="UTC"),
        work_queue_name="sync-queue",
        tags=["sync", "scheduled", "daily", "full-sync"],
        parameters={},
    )
    deployments.append(daily_full_sync)

    # Manual single data source sync (no schedule)
    manual_sync = Deployment.build_from_flow(
        flow=sync_data_source,
        name="manual-sync",
        description="Manually trigger sync for a single data source",
        work_queue_name="sync-queue",
        tags=["sync", "manual"],
    )
    deployments.append(manual_sync)

    return deployments


def create_processing_deployments() -> list[Deployment]:
    """Create deployments for processing flows.

    Returns:
        List of processing-related deployments
    """
    deployments = []

    # Process pending documents every 5 minutes
    process_pending = Deployment.build_from_flow(
        flow=process_pending_documents,
        name="process-pending-docs",
        description="Process pending documents every 5 minutes",
        schedule=IntervalSchedule(interval=timedelta(minutes=5)),
        work_queue_name="processing-queue",
        tags=["processing", "scheduled"],
        parameters={
            "batch_size": 50,
            "max_concurrent": 10,
        },
    )
    deployments.append(process_pending)

    # Reprocess failed documents hourly
    reprocess_failed = Deployment.build_from_flow(
        flow=reprocess_failed_documents,
        name="reprocess-failed-docs",
        description="Retry failed documents every hour",
        schedule=IntervalSchedule(interval=timedelta(hours=1)),
        work_queue_name="processing-queue",
        tags=["processing", "scheduled", "retry"],
        parameters={
            "limit": 100,
        },
    )
    deployments.append(reprocess_failed)

    # Manual processing trigger (no schedule)
    manual_process = Deployment.build_from_flow(
        flow=process_pending_documents,
        name="manual-process",
        description="Manually trigger document processing",
        work_queue_name="processing-queue",
        tags=["processing", "manual"],
    )
    deployments.append(manual_process)

    return deployments


def create_alert_deployments() -> list[Deployment]:
    """Create deployments for alert flows.

    Returns:
        List of alert-related deployments
    """
    deployments = []

    # Evaluate alerts every 5 minutes
    alert_eval = Deployment.build_from_flow(
        flow=evaluate_alerts,
        name="evaluate-alerts",
        description="Evaluate alerts every 5 minutes",
        schedule=IntervalSchedule(interval=timedelta(minutes=5)),
        work_queue_name="alert-queue",
        tags=["alerts", "scheduled"],
        parameters={},
    )
    deployments.append(alert_eval)

    # Manual alert evaluation (no schedule)
    manual_alerts = Deployment.build_from_flow(
        flow=evaluate_alerts,
        name="manual-alert-eval",
        description="Manually trigger alert evaluation",
        work_queue_name="alert-queue",
        tags=["alerts", "manual"],
    )
    deployments.append(manual_alerts)

    return deployments


def create_all_deployments() -> list[Deployment]:
    """Create all Prefect deployments.

    Returns:
        List of all deployments
    """
    deployments = []
    deployments.extend(create_sync_deployments())
    deployments.extend(create_processing_deployments())
    deployments.extend(create_alert_deployments())
    return deployments


async def apply_all_deployments() -> None:
    """Apply all deployments to Prefect server."""
    deployments = create_all_deployments()

    for deployment in deployments:
        deployment_id = await deployment.apply()
        print(f"Applied deployment: {deployment.name} (ID: {deployment_id})")


def main() -> None:
    """Entry point for applying deployments."""
    asyncio.run(apply_all_deployments())


if __name__ == "__main__":
    main()
