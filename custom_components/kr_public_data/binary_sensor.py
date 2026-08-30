"""Binary sensor platform dispatcher."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_AIRKOREA,
    ENTRY_BUS,
    ENTRY_PHARMACY,
    ENTRY_SAFETY_ALERT,
    ENTRY_TRANSIT,
    ENTRY_WEATHER,
)


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
        from .pharmacy.device import pharmacy_device, pharmacy_region_device_id
        from .pharmacy.sensor import region_nearby_pharmacies
        for i, region in enumerate(store.get("regions", [])):
            if not region.get("location_sensors"):
                continue
            coord = store["coordinators"].get(i)
            if not coord:
                continue
            sub_id = region.get("subentry_id")
            hub_id = pharmacy_region_device_id(hass, entry, sub_id,
                                               region.get("sido", ""),
                                               region.get("sgg", ""))
            nearby = region_nearby_pharmacies(hass, region, coord)
            ents = [PharmacyOpenBinarySensor(
                        coord, p["hpid"],
                        pharmacy_device(p["hpid"], p["name"], hub_id))
                    for p in nearby if p.get("hpid")]
            if sub_id:
                async_add_entities(ents, config_subentry_id=sub_id)
            else:
                entities += ents

    elif etype == ENTRY_TRANSIT:
        _add_transit(hass, entry, store, async_add_entities)

    elif etype == ENTRY_BUS:
        _add_bus(hass, entry, store, async_add_entities)

    if entities:
        async_add_entities(entities)


def _add_transit(hass: HomeAssistant, entry: ConfigEntry, store: dict,
                 async_add_entities: AddEntitiesCallback) -> None:
    """One 운행 중 binary sensor per (station, line), on the line's child device."""
    from .transit.binary_sensor import SubwayLineRunningBinarySensor
    from .transit.device import subway_line_device, subway_station_device_id
    for sub_id, info in (store.get("station_subs") or {}).items():
        station = info["station"]
        # Same child device as the arrival sensors, so the hub id has to be
        # resolved here too (idempotent — sensor.py already registered it).
        hub_id = subway_station_device_id(hass, entry, sub_id, station)
        async_add_entities(
            [SubwayLineRunningBinarySensor(
                info["coordinator"], station, lid,
                subway_line_device(station, lid, hub_id))
             for lid in info["lines"]],
            config_subentry_id=sub_id)


def _add_bus(hass: HomeAssistant, entry: ConfigEntry, store: dict,
             async_add_entities: AddEntitiesCallback) -> None:
    """One 운행 중 binary sensor per route (정류장) and per 등급 (구간)."""
    from .bus.binary_sensor import (
        BusRouteRunningBinarySensor,
        IntercityBusGradeRunningBinarySensor,
    )
    from .bus.device import (
        bus_stop_device_id,
        bus_stop_key,
        city_bus_route_device,
        intercity_bus_route_device,
        intercity_bus_section_device_id,
        intercity_bus_section_key,
        seoul_bus_route_device,
    )
    for sub_id, info in (store.get("stop_subs") or {}).items():
        node_id, node_name = info["nodeId"], info["nodeName"]
        seoul = info["kind"] == "seoul"
        route_device = seoul_bus_route_device if seoul else city_bus_route_device
        hub_id = bus_stop_device_id(hass, entry, sub_id, info)
        async_add_entities(
            [BusRouteRunningBinarySensor(
                info["coordinator"], bus_stop_key(info), r["routeId"],
                route_device(node_id, node_name, r["routeId"], r["routeNo"], hub_id),
                seoul=seoul)
             for r in info["routes"]],
            config_subentry_id=sub_id)

    for sub_id, info in (store.get("route_subs") or {}).items():
        dep_name, arr_name = info["depTerminalName"], info["arrTerminalName"]
        hub_id = intercity_bus_section_device_id(hass, entry, sub_id, dep_name, arr_name)
        async_add_entities(
            [IntercityBusGradeRunningBinarySensor(
                info["coordinator"], intercity_bus_section_key(dep_name, arr_name),
                grade, intercity_bus_route_device(dep_name, arr_name, grade, hub_id))
             for grade in info["grades"]],
            config_subentry_id=sub_id)
