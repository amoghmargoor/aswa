"""Airbyte connector provider."""

from aswa_connector.providers.airbyte.provider import AirbyteProvider
from aswa_connector.providers.airbyte.client import AirbyteClient

__all__ = ["AirbyteProvider", "AirbyteClient"]
