"""Provider registry for connector providers."""

from typing import Any

from aswa_common.logging import get_logger

from aswa_connector.framework.base import ConnectorProvider

logger = get_logger(__name__)

# Registry of provider factories
_provider_factories: dict[str, type[ConnectorProvider]] = {}

# Singleton provider instances
_provider_instances: dict[str, ConnectorProvider] = {}


def register_provider(name: str, provider_class: type[ConnectorProvider]) -> None:
    """Register a connector provider.

    Args:
        name: Provider name (e.g., "airbyte", "custom")
        provider_class: Provider class
    """
    logger.debug(f"Registering provider: {name}")
    _provider_factories[name] = provider_class


async def get_provider(name: str) -> ConnectorProvider:
    """Get or create a provider instance.

    Args:
        name: Provider name

    Returns:
        Initialized provider instance

    Raises:
        ValueError: If provider not registered
    """
    if name in _provider_instances:
        return _provider_instances[name]

    if name not in _provider_factories:
        # Try to import and register the provider
        await _auto_register_provider(name)

    if name not in _provider_factories:
        raise ValueError(f"Provider not registered: {name}")

    provider_class = _provider_factories[name]
    provider = provider_class()
    await provider.initialize()

    _provider_instances[name] = provider
    logger.info(f"Provider initialized: {name}")

    return provider


async def _auto_register_provider(name: str) -> None:
    """Auto-register known providers.

    Args:
        name: Provider name
    """
    if name == "airbyte":
        from aswa_connector.providers.airbyte.provider import AirbyteProvider

        register_provider("airbyte", AirbyteProvider)

    elif name == "custom":
        from aswa_connector.providers.custom.provider import CustomProvider

        register_provider("custom", CustomProvider)


def list_registered_providers() -> list[str]:
    """List all registered provider names.

    Returns:
        List of provider names
    """
    return list(_provider_factories.keys())


async def shutdown_providers() -> None:
    """Shutdown all initialized providers."""
    for name, provider in _provider_instances.items():
        logger.info(f"Shutting down provider: {name}")
        try:
            await provider.shutdown()
        except Exception as e:
            logger.exception(f"Error shutting down provider {name}: {e}")

    _provider_instances.clear()
