"""Binary sensor platform dispatcher."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import *

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    etype = entry.data.get(CONF_ENTRY_TYPE)
    store = hass.data[DOMAIN][entry.entry_id]
    entities = []

    if etype == ENTRY_WEATHER:
        from .weather.sensor import WeatherWarningBinarySensor
        c = store["coordinator"]
        for ac in store.get("area_codes", []):
            entities.append(WeatherWarningBinarySensor(c, ac))

    elif etype == ENTRY_SAFETY_ALERT:
        from .safety_alert.sensor import SafetyAlertBinarySensor
        for region in store.get("regions", []):
            coord = store["coordinators"].get(region["code"])
            if coord:
                entities.append(SafetyAlertBinarySensor(coord, region["code"], region["name"]))

    elif etype == ENTRY_AIRKOREA:
        from .airkorea.sensor import AirAlertBinarySensor
        c = store["coordinator"]
        sido = entry.data.get("sido", "")
        for st in store.get("stations", []):
            entities.append(AirAlertBinarySensor(c, st["stationName"], sido))

    if entities:
        async_add_entities(entities)
