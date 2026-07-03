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

    elif etype == ENTRY_PHARMACY:
        from .pharmacy.binary_sensor import PharmacyOpenBinarySensor
        from .pharmacy.sensor import region_nearby_pharmacies
        from .pharmacy.device import pharmacy_region_device
        for i, region in enumerate(store.get("regions", [])):
            if not region.get("location_sensors"):
                continue
            coord = store["coordinators"].get(i)
            if not coord:
                continue
            device_info = pharmacy_region_device(region.get("sido", ""), region.get("sgg", ""))
            nearby = region_nearby_pharmacies(hass, region, coord)
            ents = [PharmacyOpenBinarySensor(coord, p["hpid"], p["name"], device_info)
                    for p in nearby if p.get("hpid")]
            sub_id = region.get("subentry_id")
            if sub_id:
                async_add_entities(ents, config_subentry_id=sub_id)
            else:
                entities += ents

    if entities:
        async_add_entities(entities)
