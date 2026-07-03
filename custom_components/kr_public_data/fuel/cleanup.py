"""Remove stale fuel entities/devices.

Each fuel_region subentry supports a reconfigure step that edits its
fuel_codes selection (`FuelRegionSubentryFlowHandler.async_step_reconfigure`)
without recreating the subentry. Home Assistant only cleans up
entities/devices when a whole subentry is deleted, not when a still-existing
subentry's data shrinks - so a removed fuel_code's device/entities would
otherwise stick around as orphans forever.
"""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from ..const import DOMAIN

# Order matters: "_fuel_low_location_" must be checked before "_fuel_low_"
# since it's a superstring of it.
_ENTITY_PREFIXES = (f"{DOMAIN}_fuel_avg_", f"{DOMAIN}_fuel_low_location_", f"{DOMAIN}_fuel_low_")
_DEVICE_PREFIX = "fuel_"


def async_cleanup_stale_fuel_entities(hass: HomeAssistant, entry: ConfigEntry,
                                      configs: list[dict]) -> None:
    expected = {(c["sido_code"], c["fuel_code"]) for c in configs}

    ent_reg = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        uid = entity_entry.unique_id
        for prefix in _ENTITY_PREFIXES:
            if uid.startswith(prefix):
                sido, _, fuel = uid[len(prefix):].partition("_")
                if (sido, fuel) not in expected:
                    ent_reg.async_remove(entity_entry.entity_id)
                break

    dev_reg = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        for domain, identifier in device_entry.identifiers:
            if domain == DOMAIN and identifier.startswith(_DEVICE_PREFIX):
                sido, _, fuel = identifier[len(_DEVICE_PREFIX):].partition("_")
                if (sido, fuel) not in expected:
                    dev_reg.async_remove_device(device_entry.id)
                break
