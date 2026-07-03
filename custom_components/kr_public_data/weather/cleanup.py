"""Remove stale weather-warning entities/devices.

Every entity under a `weather_warning` entry belongs to exactly one of its
configured area codes (binary_sensor, calendar, event x WARNING_TYPES) - so a
full-entry diff against the current area-code set is enough, no per-unique-id
parsing needed. This matters because a legacy (pre-subentry) entry's flat
`area_codes` list is still editable via the options flow, and shrinking it
wouldn't otherwise remove the now-unconfigured area's device/entities -
modern subentries are cleaned up natively on deletion, but editing a still
existing legacy entry's list isn't a subentry deletion at all.
"""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from ..const import DOMAIN
from . import WARNING_TYPES


def async_cleanup_stale_weather_entities(hass: HomeAssistant, entry: ConfigEntry,
                                         area_codes: list[str]) -> None:
    expected_ids: set[str] = set()
    expected_device_ids: set[str] = set()
    for ac in area_codes:
        expected_device_ids.add(f"weather_{ac}")
        expected_ids.add(f"{DOMAIN}_weather_alert_{ac}")
        expected_ids.add(f"{DOMAIN}_{ac}_calendar")
        for warning_id, _name, _icon in WARNING_TYPES.values():
            expected_ids.add(f"{DOMAIN}_{ac}_{warning_id}")

    ent_reg = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if entity_entry.unique_id not in expected_ids:
            ent_reg.async_remove(entity_entry.entity_id)

    dev_reg = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        for domain, identifier in device_entry.identifiers:
            if domain == DOMAIN and identifier not in expected_device_ids:
                dev_reg.async_remove_device(device_entry.id)
            break
