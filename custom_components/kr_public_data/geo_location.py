"""Geolocation platform dispatcher."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import *

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    etype = entry.data.get(CONF_ENTRY_TYPE)
    store = hass.data[DOMAIN][entry.entry_id]

    if etype == ENTRY_DISASTER:
        from .disaster.device import region_label
        from .disaster.geo_location import DisasterGeoLocationManager
        c = store["coordinator"]
        regions = store.get("regions") or {}
        for sub_id, r in regions.items():
            sido = r.get("sido", "")
            sgg = r.get("sgg", "")
            label = region_label(sido=sido, sgg=sgg)

            def add(ents, sub_id=sub_id):
                async_add_entities(ents, config_subentry_id=sub_id)

            manager = DisasterGeoLocationManager(c, sido, sgg, label, add)
            entry.async_on_unload(manager.unload)
