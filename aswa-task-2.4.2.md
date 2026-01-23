# Task 2.4.2: Prefect Workflow Orchestration

## Subtask: Create Prefect Flows for Sync and Processing

**Claude Code Prompt:**
```
Create Prefect workflow orchestration at /services/ingestion-service/src/aswa_ingestion/flows/.

1. /services/ingestion-service/pyproject.toml - add dependency:
prefect = ">=2.14"

2. /services/ingestion-service/src/aswa_ingestion/flows/__init__.py:
from .sync_flow import sync_data_source, scheduled_sync_all
from .processing_flow import process_pending_documents
from .alert_flow import evaluate_alerts

3. /services/ingestion-service/src/aswa_ingestion/flows/sync_flow.py:
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from datetime import timedelta
from uuid import UUID
import structlog

logger = structlog.get_logger()

@task(
    name="fetch_data_source",
    retries=2,
    retry_delay_seconds=30,
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(minutes=5)
)
async def fetch_data_source(data_source_id: UUID, tenant_id: UUID) -> dict:
    """Fetch data source configuration from database."""
    from aswa_common.db import get_session
    from aswa_common.db.repositories import DataSourceRepository
    
    async with get_session() as session:
        repo = DataSourceRepository(session, tenant_id)
        ds = await repo.get_by_id(data_source_id)
        if not ds:
            raise ValueError(f"Data source {data_source_id} not found")
        
        return {
            "id": str(ds.id),
            "source_type": ds.source_type,
            "config": ds.config,
            "sync_cursor": ds.sync_cursor
        }

@task(
    name="create_connector",
    retries=1
)
async def create_connector(data_source: dict, tenant_id: UUID):
    """Create and authenticate connector."""
    from aswa_ingestion.connectors import ConnectorFactory, ConnectorConfig
    
    config = ConnectorConfig(
        credentials=data_source["config"].get("credentials", {}),
        settings=data_source["config"].get("settings", {})
    )
    
    connector = ConnectorFactory.create(
        data_source["source_type"],
        config,
        tenant_id
    )
    
    if not await connector.authenticate():
        raise ValueError(f"Failed to authenticate {data_source['source_type']} connector")
    
    return connector

@task(
    name="sync_documents",
    retries=1,
    timeout_seconds=3600  # 1 hour timeout
)
async def sync_documents(
    connector,
    data_source: dict,
    tenant_id: UUID,
    batch_size: int = 100
) -> dict:
    """Sync documents from data source."""
    from aswa_ingestion.connectors.base import SyncCursor
    from aswa_ingestion.services.document_service import DocumentService
    from aswa_common.db import get_session
    
    prefect_logger = get_run_logger()
    
    # Parse existing cursor
    cursor = None
    if data_source.get("sync_cursor"):
        import json
        cursor_data = json.loads(data_source["sync_cursor"])
        cursor = SyncCursor(**cursor_data)
    
    stats = {
        "documents_fetched": 0,
        "documents_created": 0,
        "documents_updated": 0,
        "documents_skipped": 0,
        "errors": 0
    }
    
    last_cursor = cursor
    
    async with get_session() as session:
        doc_service = DocumentService(session)
        
        async for batch, new_cursor in connector.fetch_documents(cursor, batch_size):
            for doc in batch:
                stats["documents_fetched"] += 1
                
                try:
                    # Check for duplicates
                    existing = await doc_service.check_duplicate(
                        doc.version_hash, tenant_id
                    )
                    
                    if existing:
                        if existing.version_hash == doc.version_hash:
                            stats["documents_skipped"] += 1
                            continue
                        else:
                            # Update existing document
                            await doc_service.update_document(existing.id, doc)
                            stats["documents_updated"] += 1
                    else:
                        # Create new document
                        await doc_service.store_document(
                            doc, tenant_id, UUID(data_source["id"])
                        )
                        stats["documents_created"] += 1
                        
                except Exception as e:
                    prefect_logger.error(f"Failed to process document: {e}")
                    stats["errors"] += 1
            
            last_cursor = new_cursor
            prefect_logger.info(f"Processed batch: {stats}")
    
    return {
        "stats": stats,
        "cursor": last_cursor.model_dump() if last_cursor else None
    }

@task(name="update_sync_status")
async def update_sync_status(
    data_source_id: UUID,
    tenant_id: UUID,
    result: dict,
    error: str | None = None
) -> None:
    """Update data source sync status in database."""
    from aswa_common.db import get_session
    from aswa_common.db.repositories import DataSourceRepository
    import json
    
    async with get_session() as session:
        repo = DataSourceRepository(session, tenant_id)
        
        update_data = {
            "last_sync_at": datetime.utcnow(),
            "error_message": error
        }
        
        if result and result.get("cursor"):
            update_data["sync_cursor"] = json.dumps(result["cursor"])
        
        if error:
            update_data["status"] = "error"
        else:
            update_data["status"] = "active"
        
        await repo.update(data_source_id, update_data)
        await session.commit()

@task(name="queue_documents_for_processing")
async def queue_documents_for_processing(
    tenant_id: UUID,
    limit: int = 1000
) -> int:
    """Queue pending documents for processing."""
    from aswa_common.db import get_session
    from aswa_common.db.repositories import DocumentRepository
    from aswa_processor.queue import RedisQueue
    import redis.asyncio as redis
    
    async with get_session() as session:
        repo = DocumentRepository(session, tenant_id)
        pending_docs = await repo.find_pending(limit=limit)
        
        if not pending_docs:
            return 0
        
        # Queue for processing
        redis_client = redis.from_url(settings.redis_url)
        queue = RedisQueue(
            redis_client, 
            "document_processing",
            "processors",
            "sync-flow"
        )
        
        payloads = [
            {"document_id": str(doc.id), "tenant_id": str(tenant_id)}
            for doc in pending_docs
        ]
        
        await queue.enqueue_batch(payloads)
        
        return len(pending_docs)

@flow(
    name="sync_data_source",
    description="Sync documents from a single data source",
    retries=1,
    retry_delay_seconds=60
)
async def sync_data_source(
    data_source_id: UUID,
    tenant_id: UUID,
    full_sync: bool = False
) -> dict:
    """
    Main flow to sync a data source.
    
    Steps:
    1. Fetch data source config
    2. Create and authenticate connector
    3. Sync documents
    4. Update sync status
    5. Queue documents for processing
    """
    prefect_logger = get_run_logger()
    prefect_logger.info(f"Starting sync for data source {data_source_id}")
    
    try:
        # Fetch data source
        data_source = await fetch_data_source(data_source_id, tenant_id)
        
        if full_sync:
            data_source["sync_cursor"] = None
        
        # Create connector
        connector = await create_connector(data_source, tenant_id)
        
        # Sync documents
        result = await sync_documents(connector, data_source, tenant_id)
        
        # Update status
        await update_sync_status(data_source_id, tenant_id, result)
        
        # Queue for processing
        queued = await queue_documents_for_processing(tenant_id)
        result["documents_queued"] = queued
        
        prefect_logger.info(f"Sync completed: {result}")
        return result
        
    except Exception as e:
        prefect_logger.error(f"Sync failed: {e}")
        await update_sync_status(data_source_id, tenant_id, None, str(e))
        raise

@flow(
    name="scheduled_sync_all",
    description="Scheduled sync for all active data sources"
)
async def scheduled_sync_all() -> dict:
    """
    Scheduled flow to sync all active data sources.
    Runs on a schedule (e.g., every hour).
    """
    from aswa_common.db import get_session
    from sqlalchemy import select
    from aswa_common.db.models import DataSource
    
    prefect_logger = get_run_logger()
    
    results = {"success": 0, "failed": 0, "skipped": 0}
    
    async with get_session() as session:
        # Find all active data sources due for sync
        stmt = select(DataSource).where(
            DataSource.status == "active"
        )
        data_sources = (await session.execute(stmt)).scalars().all()
    
    for ds in data_sources:
        # Check if sync is due
        if ds.last_sync_at:
            minutes_since_sync = (datetime.utcnow() - ds.last_sync_at).total_seconds() / 60
            if minutes_since_sync < ds.sync_frequency_minutes:
                results["skipped"] += 1
                continue
        
        try:
            await sync_data_source(ds.id, ds.tenant_id)
            results["success"] += 1
        except Exception as e:
            prefect_logger.error(f"Sync failed for {ds.id}: {e}")
            results["failed"] += 1
    
    prefect_logger.info(f"Scheduled sync completed: {results}")
    return results

4. /services/ingestion-service/src/aswa_ingestion/flows/processing_flow.py:
from prefect import flow, task, get_run_logger
from prefect.concurrency.asyncio import concurrency
from uuid import UUID
from datetime import datetime

@task(name="fetch_pending_documents")
async def fetch_pending_documents(
    tenant_id: UUID | None = None,
    limit: int = 100
) -> list[dict]:
    """Fetch documents pending processing."""
    from aswa_common.db import get_session
    from sqlalchemy import select
    from aswa_common.db.models import Document
    
    async with get_session() as session:
        stmt = select(Document).where(
            Document.processed_status.in_(["pending", "failed"])
        ).limit(limit)
        
        if tenant_id:
            stmt = stmt.where(Document.tenant_id == tenant_id)
        
        docs = (await session.execute(stmt)).scalars().all()
        
        return [
            {
                "id": str(doc.id),
                "tenant_id": str(doc.tenant_id),
                "content_type": doc.content_type,
                "title": doc.title
            }
            for doc in docs
        ]

@task(
    name="process_single_document",
    retries=2,
    retry_delay_seconds=30
)
async def process_single_document(document: dict) -> dict:
    """Process a single document through the pipeline."""
    from aswa_common.db import get_session
    from aswa_common.db.repositories import DocumentRepository
    from aswa_ingestion.processing.pipeline import DocumentProcessingPipeline
    
    doc_id = UUID(document["id"])
    tenant_id = UUID(document["tenant_id"])
    
    async with get_session() as session:
        repo = DocumentRepository(session, tenant_id)
        doc = await repo.get_by_id(doc_id)
        
        if not doc:
            return {"id": document["id"], "status": "not_found"}
        
        # Update status
        await repo.update_status(doc_id, "processing")
        await session.commit()
        
        try:
            # Get pipeline (should be initialized elsewhere and passed in)
            pipeline = await get_processing_pipeline()
            result = await pipeline.process(doc)
            
            return {
                "id": document["id"],
                "status": "success",
                "chunks_created": result.chunks_created,
                "vectors_stored": result.vectors_stored,
                "processing_time_ms": result.processing_time_ms
            }
            
        except Exception as e:
            await repo.update_status(doc_id, "failed", str(e))
            await session.commit()
            return {
                "id": document["id"],
                "status": "failed",
                "error": str(e)
            }

@flow(
    name="process_pending_documents",
    description="Process all pending documents"
)
async def process_pending_documents(
    tenant_id: UUID | None = None,
    batch_size: int = 50,
    max_concurrent: int = 10
) -> dict:
    """
    Flow to process pending documents.
    
    Can be triggered manually or scheduled.
    """
    prefect_logger = get_run_logger()
    prefect_logger.info(f"Starting document processing, tenant={tenant_id}")
    
    stats = {"processed": 0, "success": 0, "failed": 0}
    
    while True:
        # Fetch batch of pending documents
        pending = await fetch_pending_documents(tenant_id, batch_size)
        
        if not pending:
            break
        
        # Process with concurrency limit
        async with concurrency("document-processing", max_concurrent):
            results = await process_single_document.map(pending)
        
        for result in results:
            stats["processed"] += 1
            if result.get("status") == "success":
                stats["success"] += 1
            else:
                stats["failed"] += 1
        
        prefect_logger.info(f"Batch completed: {stats}")
    
    prefect_logger.info(f"Processing completed: {stats}")
    return stats

5. /services/ingestion-service/src/aswa_ingestion/flows/alert_flow.py:
from prefect import flow, task, get_run_logger
from uuid import UUID
from datetime import datetime, timedelta

@task(name="fetch_active_alerts")
async def fetch_active_alerts(tenant_id: UUID | None = None) -> list[dict]:
    """Fetch all active alert configurations."""
    from aswa_common.db import get_session
    from sqlalchemy import select
    from aswa_common.db.models import AlertConfig
    
    async with get_session() as session:
        stmt = select(AlertConfig).where(AlertConfig.status == "active")
        
        if tenant_id:
            stmt = stmt.where(AlertConfig.tenant_id == tenant_id)
        
        alerts = (await session.execute(stmt)).scalars().all()
        
        return [
            {
                "id": str(alert.id),
                "tenant_id": str(alert.tenant_id),
                "name": alert.name,
                "pattern_query": alert.pattern_query,
                "conditions": alert.conditions,
                "notification_channels": alert.notification_channels,
                "frequency": alert.frequency,
                "last_triggered_at": alert.last_triggered_at.isoformat() if alert.last_triggered_at else None
            }
            for alert in alerts
        ]

@task(name="evaluate_alert_conditions")
async def evaluate_alert_conditions(alert: dict) -> dict | None:
    """
    Evaluate if alert conditions are met.
    Returns matched insights or None.
    """
    from aswa_common.db import get_session
    from aswa_ingestion.services.query_service import QueryService
    
    tenant_id = UUID(alert["tenant_id"])
    
    # Determine time window based on frequency
    frequency_windows = {
        "realtime": timedelta(minutes=5),
        "hourly": timedelta(hours=1),
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1)
    }
    
    time_window = frequency_windows.get(alert["frequency"], timedelta(hours=1))
    since = datetime.utcnow() - time_window
    
    # Check if already triggered in this window
    if alert["last_triggered_at"]:
        last_triggered = datetime.fromisoformat(alert["last_triggered_at"])
        if last_triggered > since:
            return None
    
    async with get_session() as session:
        query_service = QueryService(session, tenant_id)
        
        # Search for matching insights
        results = await query_service.search_insights(
            query=alert["pattern_query"],
            filters={
                "created_at": {"gte": since.isoformat()},
                **alert.get("conditions", {})
            },
            limit=100
        )
        
        if not results:
            return None
        
        # Apply additional conditions
        conditions = alert.get("conditions", {})
        
        # Filter by severity if specified
        if "min_severity" in conditions:
            severity_order = ["info", "low", "medium", "high", "critical"]
            min_idx = severity_order.index(conditions["min_severity"])
            results = [
                r for r in results 
                if severity_order.index(r.get("severity", "info")) >= min_idx
            ]
        
        # Filter by confidence if specified
        if "min_confidence" in conditions:
            results = [
                r for r in results 
                if r.get("confidence", 0) >= conditions["min_confidence"]
            ]
        
        if not results:
            return None
        
        return {
            "alert_id": alert["id"],
            "matched_insights": [r["id"] for r in results],
            "match_count": len(results),
            "sample_insights": results[:5]
        }

@task(name="send_alert_notifications")
async def send_alert_notifications(
    alert: dict,
    match_result: dict
) -> dict:
    """Send notifications for triggered alert."""
    from aswa_ingestion.services.notification_service import NotificationService
    
    notification_service = NotificationService()
    channels = alert["notification_channels"]
    
    results = {}
    
    # Build notification content
    content = {
        "alert_name": alert["name"],
        "match_count": match_result["match_count"],
        "sample_insights": match_result["sample_insights"],
        "triggered_at": datetime.utcnow().isoformat()
    }
    
    # Send to Slack
    if "slack" in channels:
        try:
            await notification_service.send_slack(
                channel=channels["slack"]["channel"],
                webhook_url=channels["slack"].get("webhook_url"),
                content=content
            )
            results["slack"] = "sent"
        except Exception as e:
            results["slack"] = f"failed: {e}"
    
    # Send email
    if "email" in channels:
        try:
            await notification_service.send_email(
                recipients=channels["email"]["recipients"],
                subject=f"Alert: {alert['name']}",
                content=content
            )
            results["email"] = "sent"
        except Exception as e:
            results["email"] = f"failed: {e}"
    
    # Send webhook
    if "webhook" in channels:
        try:
            await notification_service.send_webhook(
                url=channels["webhook"]["url"],
                payload={
                    "alert": alert,
                    "result": match_result
                }
            )
            results["webhook"] = "sent"
        except Exception as e:
            results["webhook"] = f"failed: {e}"
    
    return results

@task(name="record_alert_trigger")
async def record_alert_trigger(
    alert_id: UUID,
    match_result: dict,
    notification_results: dict
) -> None:
    """Record alert trigger in history."""
    from aswa_common.db import get_session
    from aswa_common.db.models import AlertHistory, AlertConfig
    
    async with get_session() as session:
        # Create history record
        history = AlertHistory(
            alert_config_id=alert_id,
            triggered_at=datetime.utcnow(),
            matched_insights=match_result["matched_insights"],
            notification_status=notification_results,
            metadata={"match_count": match_result["match_count"]}
        )
        session.add(history)
        
        # Update last triggered time
        from sqlalchemy import update
        stmt = update(AlertConfig).where(
            AlertConfig.id == alert_id
        ).values(
            last_triggered_at=datetime.utcnow(),
            trigger_count=AlertConfig.trigger_count + 1
        )
        await session.execute(stmt)
        await session.commit()

@flow(
    name="evaluate_alerts",
    description="Evaluate all active alerts and send notifications"
)
async def evaluate_alerts(tenant_id: UUID | None = None) -> dict:
    """
    Main flow to evaluate alerts.
    Should be scheduled to run frequently (e.g., every 5 minutes).
    """
    prefect_logger = get_run_logger()
    prefect_logger.info("Starting alert evaluation")
    
    stats = {"evaluated": 0, "triggered": 0, "notifications_sent": 0}
    
    # Fetch active alerts
    alerts = await fetch_active_alerts(tenant_id)
    stats["evaluated"] = len(alerts)
    
    for alert in alerts:
        # Evaluate conditions
        match_result = await evaluate_alert_conditions(alert)
        
        if match_result:
            stats["triggered"] += 1
            prefect_logger.info(
                f"Alert triggered: {alert['name']}, matches: {match_result['match_count']}"
            )
            
            # Send notifications
            notification_results = await send_alert_notifications(alert, match_result)
            stats["notifications_sent"] += sum(
                1 for v in notification_results.values() if v == "sent"
            )
            
            # Record trigger
            await record_alert_trigger(
                UUID(alert["id"]),
                match_result,
                notification_results
            )
    
    prefect_logger.info(f"Alert evaluation completed: {stats}")
    return stats

6. /services/ingestion-service/src/aswa_ingestion/flows/schedules.py:
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import CronSchedule, IntervalSchedule
from datetime import timedelta

def create_deployments():
    """Create Prefect deployments with schedules."""
    
    # Sync all data sources every hour
    sync_deployment = Deployment.build_from_flow(
        flow=scheduled_sync_all,
        name="hourly-sync",
        schedule=IntervalSchedule(interval=timedelta(hours=1)),
        work_queue_name="sync-queue",
        tags=["sync", "scheduled"]
    )
    
    # Process pending documents every 5 minutes
    processing_deployment = Deployment.build_from_flow(
        flow=process_pending_documents,
        name="process-pending",
        schedule=IntervalSchedule(interval=timedelta(minutes=5)),
        work_queue_name="processing-queue",
        tags=["processing", "scheduled"]
    )
    
    # Evaluate alerts every 5 minutes
    alert_deployment = Deployment.build_from_flow(
        flow=evaluate_alerts,
        name="evaluate-alerts",
        schedule=IntervalSchedule(interval=timedelta(minutes=5)),
        work_queue_name="alert-queue",
        tags=["alerts", "scheduled"]
    )
    
    return [sync_deployment, processing_deployment, alert_deployment]

if __name__ == "__main__":
    deployments = create_deployments()
    for deployment in deployments:
        deployment.apply()

7. /services/ingestion-service/tests/flows/:
- conftest.py with Prefect test fixtures
- test_sync_flow.py - test sync flow with mocked connectors
- test_processing_flow.py - test document processing flow
- test_alert_flow.py - test alert evaluation and notifications

Use prefect.testing utilities for flow testing.
Mock external dependencies (DB, Redis, notification services).
Test error handling and retry behavior.
```