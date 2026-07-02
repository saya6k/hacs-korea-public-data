"""Calendar platform dispatcher."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, CONF_ENTRY_TYPE, ENTRY_WEATHER, ENTRY_SCHOOL, ENTRY_AIRKOREA

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    etype = entry.data.get(CONF_ENTRY_TYPE)
    store = hass.data[DOMAIN][entry.entry_id]

    if etype == ENTRY_WEATHER:
        from .weather.calendar import KMAWeatherCalendar
        c = store["coordinator"]
        areas = store.get("areas") or {}
        for sub_id, ac in areas.items():
            async_add_entities([KMAWeatherCalendar(c, ac)],
                               config_subentry_id=sub_id)
        if not areas:
            async_add_entities([KMAWeatherCalendar(c, ac)
                                for ac in store["area_codes"]])

    elif etype == ENTRY_SCHOOL:
        from .school.calendar import SchoolCalendar, SchoolClassCalendar
        coord = store["coordinator"]
        entities = [SchoolCalendar(coord, entry)]
        for gc in coord.grade_classes:
            entities.append(SchoolClassCalendar(coord, entry, gc))
        async_add_entities(entities)
    elif etype == ENTRY_AIRKOREA:
        from .airkorea.sensor import AirForecastCalendar
        c = store["coordinator"]
        sido = entry.data.get("sido", "")
        station_subs = store.get("station_subs") or {}
        for sub_id, st in station_subs.items():
            async_add_entities(
                [AirForecastCalendar(c, st["stationName"], st.get("sido") or sido)],
                config_subentry_id=sub_id)
        if not station_subs:
            async_add_entities([AirForecastCalendar(c, st["stationName"], sido)
                                for st in store.get("stations", [])])
