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
        areas = store.get("areas") or {}
        for sub_id, ac in areas.items():
            async_add_entities([WeatherWarningBinarySensor(c, ac)],
                               config_subentry_id=sub_id)
        if not areas:
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
        station_subs = store.get("station_subs") or {}
        for sub_id, st in station_subs.items():
            async_add_entities(
                [AirAlertBinarySensor(c, st["stationName"], st.get("sido") or sido)],
                config_subentry_id=sub_id)
        if not station_subs:
            for st in store.get("stations", []):
                entities.append(AirAlertBinarySensor(c, st["stationName"], sido))

    if entities:
        async_add_entities(entities)
