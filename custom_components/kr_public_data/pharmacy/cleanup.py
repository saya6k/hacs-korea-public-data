"""Remove stale per-pharmacy entities/devices.

Unlike the flat region list (fixed at entry-creation time), the set of nearby
pharmacies is recomputed from live coordinator data on every setup - a
pharmacy that drops out of radius (location/radius edited via the options
flow) or a whole region that gets `location_sensors` toggled off just stops
being passed to `async_add_entities`. Home Assistant does not remove
previously registered entities/devices on its own in that case, so without
this pass they pile up as orphans across entry reloads.
"""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from ..const import DOMAIN
from .sensor import region_nearby_pharmacies

_LOCATION_PREFIX = f"{DOMAIN}_pharmacy_location_"
_OPEN_PREFIX = f"{DOMAIN}_pharmacy_open_"
_DEVICE_PREFIX = "pharmacy_hpid_"


def async_cleanup_stale_pharmacy_entities(hass: HomeAssistant, entry: ConfigEntry,
                                          regions: list[dict], coords: dict) -> None:
    expected_hpids: set[str] = set()
    for i, region in enumerate(regions):
        if not region.get("location_sensors"):
            continue
        coord = coords.get(i)
        if not coord or not coord.last_update_success:
            # A transient fetch failure on this reload must not be read as
            # "no pharmacies nearby" - that would wipe real devices/entities
            # for a region that's actually fine. Skip cleanup entirely this
            # round; it'll run again (and catch anything truly stale) on the
            # next successful reload.
            return
        expected_hpids.update(
            p["hpid"] for p in region_nearby_pharmacies(hass, region, coord) if p.get("hpid"))

    ent_reg = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        uid = entity_entry.unique_id
        if uid.startswith(_LOCATION_PREFIX):
            hpid = uid[len(_LOCATION_PREFIX):]
        elif uid.startswith(_OPEN_PREFIX):
            hpid = uid[len(_OPEN_PREFIX):]
        else:
            continue
        if hpid not in expected_hpids:
            ent_reg.async_remove(entity_entry.entity_id)

    dev_reg = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        for domain, identifier in device_entry.identifiers:
            if domain == DOMAIN and identifier.startswith(_DEVICE_PREFIX):
                hpid = identifier[len(_DEVICE_PREFIX):]
                if hpid not in expected_hpids:
                    dev_reg.async_remove_device(device_entry.id)
                break
