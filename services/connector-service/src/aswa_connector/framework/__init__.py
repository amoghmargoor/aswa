"""Connector framework components."""

from aswa_connector.framework.base import ConnectorProvider
from aswa_connector.framework.models import (
    ConnectorDefinition,
    ConnectorType,
    ConnectionConfig,
    Connection,
    ConnectionStatus,
    ConnectionTestResult,
    SyncJob,
    SyncJobStatus,
    SyncRecord,
    OAuthCredentials,
)
from aswa_connector.framework.registry import register_provider, get_provider

__all__ = [
    "ConnectorProvider",
    "ConnectorDefinition",
    "ConnectorType",
    "ConnectionConfig",
    "Connection",
    "ConnectionStatus",
    "ConnectionTestResult",
    "SyncJob",
    "SyncJobStatus",
    "SyncRecord",
    "OAuthCredentials",
    "register_provider",
    "get_provider",
]
