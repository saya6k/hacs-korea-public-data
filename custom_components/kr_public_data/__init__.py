"""한국 공공데이터 - unified Korean public data integration."""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from .const import *
from .llm_api import async_cleanup_llm_api, async_setup_llm_api

PLATFORM_MAP = {
    ENTRY_WEATHER: [Platform.EVENT, Platform.CALENDAR, Platform.BINARY_SENSOR],
    ENTRY_TRANSIT: [Platform.SENSOR],
    ENTRY_FUEL: [Platform.SENSOR],
    ENTRY_SCHOOL: [Platform.SENSOR, Platform.CALENDAR],
    ENTRY_DISASTER: [Platform.SENSOR, Platform.EVENT],
    ENTRY_SAFETY_ALERT: [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.EVENT],
    ENTRY_KEPCO: [Platform.SENSOR],
    ENTRY_GASAPP: [Platform.SENSOR],
    ENTRY_ARISU: [Platform.SENSOR],
    ENTRY_PHARMACY: [Platform.SENSOR],
    ENTRY_AIRKOREA: [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.EVENT, Platform.CALENDAR],
    ENTRY_KMA_WEATHER: [Platform.WEATHER],
    ENTRY_EARTHQUAKE: [Platform.EVENT],
}

# Globally registered actions, removed when the last entry of the type unloads.
SERVICES_BY_ETYPE = {
    ENTRY_TRANSIT: ["search_location", "search_transit_path"],
    ENTRY_PHARMACY: ["search_pharmacy"],
    ENTRY_AIRKOREA: ["get_living_index_forecast"],
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    etype = entry.data[CONF_ENTRY_TYPE]
    store: dict = {}

    if etype == ENTRY_WEATHER:
        from .weather.coordinator import WeatherWarningCoordinator
        api_key = entry.data["api_key"]
        # 특보구역 per subentry; legacy entries keep area_codes in entry data.
        areas = {sub_id: sub.data["area_code"]
                 for sub_id, sub in entry.subentries.items()}
        area_codes = list(areas.values()) or entry.data.get("area_codes", [])
        c = WeatherWarningCoordinator(hass, api_key, area_codes)
        await c.async_config_entry_first_refresh()
        store = {"coordinator": c, "area_codes": area_codes, "areas": areas}

    elif etype == ENTRY_TRANSIT:
        from .transit.subway_coordinator import SubwayCoordinator
        from .transit.bus_coordinator import BusCoordinator
        from .transit.services import async_register_services
        seoul_key = entry.data.get("seoul_api_key", "")
        bus_key = entry.data.get("bus_api_key", "")
        sg: dict[str, list] = {}
        for item in entry.data.get("subway_items", []):
            sg.setdefault(item["station"], []).append(item)
        from .resilience import async_first_refresh_all
        sc = {station: SubwayCoordinator(hass, seoul_key, station, subs)
              for station, subs in sg.items()}
        bus_coords = {stop["stop_id"]: BusCoordinator(hass, stop["stop_id"], stop["stop_name"])
                      for stop in entry.data.get("bus_stops", [])}
        await async_first_refresh_all([*sc.values(), *bus_coords.values()], "transit")
        store = {"subway_coords": sc, "bus_coords": bus_coords,
                 "subway_items": entry.data.get("subway_items", []),
                 "bus_stops": entry.data.get("bus_stops", [])}
        if bus_key:
            async_register_services(hass, bus_key)

    elif etype == ENTRY_FUEL:
        from .fuel.coordinator import FuelCoordinator
        api_key = entry.data["api_key"]
        configs = entry.data.get("configs", [])
        if not configs and "sido_code" in entry.data:
            configs = [{"sido_code": entry.data["sido_code"], "fuel_code": entry.data["fuel_code"]}]
        c = FuelCoordinator(hass, api_key, configs)
        await c.async_config_entry_first_refresh()
        store = {"coordinator": c, "configs": configs}

    elif etype == ENTRY_SCHOOL:
        from .school.coordinator import SchoolCoordinator
        c = SchoolCoordinator(hass, entry)
        await c.async_config_entry_first_refresh()
        store = {"coordinator": c}

    elif etype == ENTRY_DISASTER:
        from .disaster.coordinator import DisasterCoordinator
        api_key = entry.data["api_key"]
        c = DisasterCoordinator(hass, api_key)
        await c.async_config_entry_first_refresh()
        # One shared fetch; each 시군구 subentry filters in its entities.
        regions = {sub_id: dict(sub.data) for sub_id, sub in entry.subentries.items()}
        store = {"coordinator": c, "regions": regions,
                 "region": entry.data.get("region_filter", "")}

    elif etype == ENTRY_SAFETY_ALERT:
        from .safety_alert.coordinator import SafetyAlertCoordinator
        regions = entry.data.get("regions", [])
        if not regions and entry.data.get("area_code"):
            regions = [{"code": entry.data["area_code"], "name": entry.data.get("area_name", "")}]
        from .resilience import async_first_refresh_all
        coordinators = {region["code"]: SafetyAlertCoordinator(hass, region["code"])
                        for region in regions}
        await async_first_refresh_all(list(coordinators.values()), "safety_alert")
        store = {"coordinators": coordinators, "regions": regions}

    elif etype == ENTRY_KEPCO:
        from homeassistant.exceptions import ConfigEntryAuthFailed
        from .kepco.coordinator import KepcoCoordinator
        from .kepco.exceptions import KepcoAuthError
        c = KepcoCoordinator(hass, entry.data["username"], entry.data["password"])
        try:
            await c.async_login()
        except KepcoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception:
            # Network flakiness must not block the entry: it loads with stale
            # data and the coordinator retries on schedule.
            pass
        await c.async_config_entry_first_refresh()
        store = {"coordinator": c}

    elif etype == ENTRY_GASAPP:
        from .gasapp.coordinator import GasAppCoordinator
        c = GasAppCoordinator(hass, entry.data["token"],
                               entry.data["member_id"], entry.data["contract_num"])
        await c.async_config_entry_first_refresh()
        store = {"coordinator": c}

    elif etype == ENTRY_ARISU:
        from .arisu.coordinator import ArisuCoordinator
        c = ArisuCoordinator(hass, entry.data["customer_number"], entry.data["customer_name"])
        await c.async_config_entry_first_refresh()
        store = {"coordinator": c}

    elif etype == ENTRY_PHARMACY:
        from .pharmacy.coordinator import PharmacyCoordinator
        from .pharmacy.services import async_register_pharmacy_service
        from .resilience import async_first_refresh_all
        api_key = entry.data["api_key"]
        # One coordinator per 시군구 subentry (the API queries per region).
        coords = {sub_id: PharmacyCoordinator(hass, api_key,
                                              sub.data.get("sido", ""),
                                              sub.data.get("sgg", ""))
                  for sub_id, sub in entry.subentries.items()}
        if not coords:
            # legacy single-region entry (q0/q1 stored in entry data)
            coords[None] = PharmacyCoordinator(hass, api_key,
                                               entry.data.get("q0", ""),
                                               entry.data.get("q1", ""))
        await async_first_refresh_all(list(coords.values()), "pharmacy")
        store = {"coordinators": coords,
                 "coordinator": next(iter(coords.values()))}
        async_register_pharmacy_service(hass, api_key)

    elif etype == ENTRY_AIRKOREA:
        from .airkorea.coordinator import AirKoreaCoordinator
        api_key = entry.data["api_key"]
        living_key = entry.data.get("living_api_key", "") or api_key
        # 측정소 per subentry; legacy entries keep stations in entry data.
        station_subs = {sub_id: dict(sub.data)
                        for sub_id, sub in entry.subentries.items()}
        stations = list(station_subs.values()) or entry.data.get("stations", [])
        sido = entry.data.get("sido", "서울")
        c = AirKoreaCoordinator(hass, api_key, stations,
                                 living_api_key=living_key, sido=sido)
        await c.async_config_entry_first_refresh()
        store = {"coordinator": c, "stations": stations,
                 "station_subs": station_subs}
        from .airkorea.services import async_register_airkorea_services
        async_register_airkorea_services(hass, api_key, living_key, sido)

    elif etype == ENTRY_KMA_WEATHER:
        from .kma_weather.coordinator import KMAWeatherCoordinator
        from .airkorea import SIDO_AREA_CODE
        from .utils import sido_short_name
        api_key = entry.data["api_key"]
        # 시군구 region per subentry; legacy entries keep regions in entry data.
        region_subs = {sub_id: dict(sub.data)
                       for sub_id, sub in entry.subentries.items()}
        regions = list(region_subs.values()) or entry.data.get("regions", [])
        # Entries created while the config flow looked SIDO_AREA_CODE up by
        # full sido name stored area_no="" — recompute from the stored sido.
        area_no = entry.data.get("area_no", "") or SIDO_AREA_CODE.get(
            sido_short_name(entry.data.get("sido", "")), "")
        c = KMAWeatherCoordinator(
            hass, api_key, regions,
            air_api_key=api_key,
            air_station=entry.data.get("air_station", ""),
            living_api_key=api_key,
            area_no=area_no,
        )
        await c.async_config_entry_first_refresh()
        store = {"coordinator": c, "regions": regions,
                 "region_subs": region_subs}

    elif etype == ENTRY_EARTHQUAKE:
        from .earthquake.coordinator import EarthquakeCoordinator
        api_key = entry.data["api_key"]
        c = EarthquakeCoordinator(hass, api_key)
        await c.async_config_entry_first_refresh()
        store = {"coordinator": c}

    hass.data[DOMAIN][entry.entry_id] = store
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORM_MAP.get(etype, []))
    store["unregister_llm"] = await async_setup_llm_api(hass, entry, etype)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    etype = entry.data.get(CONF_ENTRY_TYPE)
    store = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}) or {}
    async_cleanup_llm_api(store.get("unregister_llm"))
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORM_MAP.get(etype, [])):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _async_remove_orphan_services(hass, entry, etype)
    return unload_ok


def _async_remove_orphan_services(hass: HomeAssistant, entry: ConfigEntry, etype: str) -> None:
    """Remove global actions once no loaded entry of this type remains."""
    from homeassistant.config_entries import ConfigEntryState
    names = SERVICES_BY_ETYPE.get(etype)
    if not names:
        return
    for other in hass.config_entries.async_entries(DOMAIN):
        if (other.entry_id != entry.entry_id
                and other.data.get(CONF_ENTRY_TYPE) == etype
                and other.state is ConfigEntryState.LOADED):
            return
    for name in names:
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)
