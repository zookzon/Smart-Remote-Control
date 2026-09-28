"""Smart Remote Control integration."""

import logging

from homeassistant import config_entries
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .config_migration import normalise_config

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.REMOTE]
CURRENT_CONFIG_VERSION = 3


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Set up Smart Remote Control from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Migrate legacy config entries without requiring setup again."""
    if entry.version > CURRENT_CONFIG_VERSION:
        _LOGGER.error(
            "Cannot migrate config entry %s from newer version %s",
            entry.entry_id,
            entry.version,
        )
        return False

    data = normalise_config(dict(entry.data))
    options = normalise_config(dict(entry.options))

    if entry.version < CURRENT_CONFIG_VERSION or data != dict(entry.data) or options != dict(entry.options):
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            version=CURRENT_CONFIG_VERSION,
        )
        _LOGGER.info(
            "Migrated Smart Remote Control config entry %s from version %s to %s",
            entry.entry_id,
            entry.version,
            CURRENT_CONFIG_VERSION,
        )
    return True


async def update_listener(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Reload when config entry options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
