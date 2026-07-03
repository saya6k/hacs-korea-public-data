"""Remove stale safety-alert entities/devices.

The options flow lets a user edit the flat `regions` list in place (see
`config_flow.py`'s `ENTRY_SAFETY_ALERT` branch) - there's no subentry here to
delete, so Home Assistant's native per-subentry cleanup never applies.
Every entity under a safety_alert entry belongs to some region code (same
situation as `weather`), so a full-entry diff against the forward-built
expected id set is enough - no per-unique-id parsing needed.
"""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from ..const import DOMAIN


def async_cleanup_stale_safety_alert_entities(hass: HomeAssistant, entry: ConfigEntry,
                                              regions: list[dict]) -> None:
    codes = [r["code"] for r in regions]
    expected_device_ids = {f"safety_alert_{code}" for code in codes}
    expected_ids: set[str] = set()
    for code in codes:
        expected_ids.add(f"{DOMAIN}_safety_{code}")
        expected_ids.add(f"{DOMAIN}_safety_text_{code}")
        expected_ids.add(f"{DOMAIN}_safety_event_{code}")
        expected_ids.add(f"{DOMAIN}_safety_count_{code}")

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
