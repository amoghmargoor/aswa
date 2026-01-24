"""Source configurations for Airbyte connectors."""

from typing import Any

from aswa_connector.framework.models import ConnectorType, ConnectorDefinition


# Airbyte source definition IDs (from Airbyte's connector catalog)
SOURCE_DEFINITION_IDS = {
    ConnectorType.GMAIL: "ccaborec-2-18e-b2c-gmail",  # Example ID
    ConnectorType.GOOGLE_DRIVE: "71607ba1-c0ac-4799-8049-7f4b90dd50f7",
    ConnectorType.SLACK: "c2281cee-86f9-4a86-bb48-d23286b4c7bd",
    ConnectorType.SALESFORCE: "b117307c-14b6-41aa-9422-947e34922962",
    ConnectorType.CONFLUENCE: "cf6f6c6f-8e12-4e02-8d07-4f0f0f0f0f0f",  # Example
    ConnectorType.JIRA: "68e63de2-bb83-4c7e-93fa-a8a9051e3993",
    ConnectorType.NOTION: "6e00b415-b02e-4160-bf02-58176a0ae687",
    ConnectorType.HUBSPOT: "36c891d9-4bd9-43ac-bad2-10e12756272c",
}


# Connector definitions
CONNECTOR_DEFINITIONS: dict[ConnectorType, ConnectorDefinition] = {
    ConnectorType.GMAIL: ConnectorDefinition(
        type=ConnectorType.GMAIL,
        name="Gmail",
        description="Sync emails from Gmail",
        icon_url="https://connectors.airbyte.com/files/metadata/airbyte/source-google-email/latest/icon.svg",
        auth_type="oauth",
        oauth_provider="google",
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.metadata",
        ],
        config_schema={
            "type": "object",
            "properties": {
                "include_labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels to include (empty for all)",
                },
                "exclude_labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels to exclude",
                    "default": ["SPAM", "TRASH"],
                },
            },
        },
    ),
    ConnectorType.GOOGLE_DRIVE: ConnectorDefinition(
        type=ConnectorType.GOOGLE_DRIVE,
        name="Google Drive",
        description="Sync files from Google Drive",
        icon_url="https://connectors.airbyte.com/files/metadata/airbyte/source-google-drive/latest/icon.svg",
        auth_type="oauth",
        oauth_provider="google",
        scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ],
        config_schema={
            "type": "object",
            "properties": {
                "folder_id": {
                    "type": "string",
                    "description": "Root folder ID (empty for entire drive)",
                },
                "include_shared": {
                    "type": "boolean",
                    "description": "Include shared drives",
                    "default": True,
                },
                "file_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File types to sync",
                    "default": [
                        "application/pdf",
                        "application/vnd.google-apps.document",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ],
                },
            },
        },
    ),
    ConnectorType.SLACK: ConnectorDefinition(
        type=ConnectorType.SLACK,
        name="Slack",
        description="Sync messages from Slack",
        icon_url="https://connectors.airbyte.com/files/metadata/airbyte/source-slack/latest/icon.svg",
        auth_type="oauth",
        oauth_provider="slack",
        scopes=[
            "channels:history",
            "channels:read",
            "files:read",
            "groups:history",
            "groups:read",
            "users:read",
        ],
        config_schema={
            "type": "object",
            "properties": {
                "channel_filter": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Channel names to include (empty for all)",
                },
                "include_private": {
                    "type": "boolean",
                    "description": "Include private channels",
                    "default": False,
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Days of history to sync",
                    "default": 90,
                },
            },
        },
    ),
    ConnectorType.SALESFORCE: ConnectorDefinition(
        type=ConnectorType.SALESFORCE,
        name="Salesforce",
        description="Sync data from Salesforce",
        icon_url="https://connectors.airbyte.com/files/metadata/airbyte/source-salesforce/latest/icon.svg",
        auth_type="oauth",
        oauth_provider="salesforce",
        scopes=["api", "refresh_token", "offline_access"],
        config_schema={
            "type": "object",
            "properties": {
                "is_sandbox": {
                    "type": "boolean",
                    "description": "Is this a sandbox environment",
                    "default": False,
                },
                "streams": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Objects to sync",
                    "default": [
                        "Account",
                        "Contact",
                        "Lead",
                        "Opportunity",
                        "Case",
                        "Task",
                        "Note",
                        "ContentDocument",
                    ],
                },
            },
        },
    ),
}


def get_connector_definition(connector_type: ConnectorType) -> ConnectorDefinition | None:
    """Get connector definition by type.

    Args:
        connector_type: Connector type

    Returns:
        Connector definition or None
    """
    return CONNECTOR_DEFINITIONS.get(connector_type)


def get_all_connector_definitions() -> list[ConnectorDefinition]:
    """Get all connector definitions.

    Returns:
        List of connector definitions
    """
    return list(CONNECTOR_DEFINITIONS.values())


def get_source_definition_id(connector_type: ConnectorType) -> str | None:
    """Get Airbyte source definition ID for a connector type.

    Args:
        connector_type: Connector type

    Returns:
        Airbyte source definition ID or None
    """
    return SOURCE_DEFINITION_IDS.get(connector_type)


def build_source_config(
    connector_type: ConnectorType,
    credentials: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build Airbyte source configuration.

    Args:
        connector_type: Connector type
        credentials: OAuth credentials or API keys
        config: User configuration

    Returns:
        Airbyte connection configuration
    """
    if connector_type == ConnectorType.GMAIL:
        return {
            "credentials": {
                "auth_type": "OAuth2.0",
                "client_id": credentials.get("client_id", ""),
                "client_secret": credentials.get("client_secret", ""),
                "access_token": credentials.get("access_token"),
                "refresh_token": credentials.get("refresh_token"),
            },
            **config,
        }

    elif connector_type == ConnectorType.GOOGLE_DRIVE:
        return {
            "credentials": {
                "auth_type": "OAuth2.0",
                "client_id": credentials.get("client_id", ""),
                "client_secret": credentials.get("client_secret", ""),
                "access_token": credentials.get("access_token"),
                "refresh_token": credentials.get("refresh_token"),
            },
            "folder_url": config.get("folder_id", ""),
            **{k: v for k, v in config.items() if k != "folder_id"},
        }

    elif connector_type == ConnectorType.SLACK:
        return {
            "credentials": {
                "option_title": "OAuth2.0",
                "access_token": credentials.get("access_token"),
            },
            "start_date": config.get("start_date"),
            "lookback_window": config.get("lookback_days", 90),
            "channel_filter": config.get("channel_filter", []),
            "include_private_channels": config.get("include_private", False),
        }

    elif connector_type == ConnectorType.SALESFORCE:
        return {
            "credentials": {
                "auth_type": "OAuth",
                "client_id": credentials.get("client_id", ""),
                "client_secret": credentials.get("client_secret", ""),
                "access_token": credentials.get("access_token"),
                "refresh_token": credentials.get("refresh_token"),
            },
            "is_sandbox": config.get("is_sandbox", False),
            "streams_criteria": [
                {"criteria": "contains", "value": s}
                for s in config.get("streams", [])
            ],
        }

    else:
        # Generic OAuth config
        return {
            "credentials": {
                "access_token": credentials.get("access_token"),
                "refresh_token": credentials.get("refresh_token"),
            },
            **config,
        }
