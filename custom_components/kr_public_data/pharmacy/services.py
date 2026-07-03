"""Pharmacy search action."""
from __future__ import annotations
import logging
import voluptuous as vol
import aiohttp
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from ..const import CONF_ENTRY_TYPE, DOMAIN, ENTRY_PHARMACY
from .api import fetch_pharmacies
from .sensor import pharmacies_within_radius

_LOGGER = logging.getLogger(__name__)


def async_register_pharmacy_service(hass: HomeAssistant, api_key: str) -> None:
    async def handle_search(call: ServiceCall) -> ServiceResponse:
        region = call.data["region"]
        district = call.data.get("district", "")
        count = call.data.get("count", 10)
        async with aiohttp.ClientSession() as session:
            results = await fetch_pharmacies(session, api_key, region, district, num=int(count))
        return {"pharmacies": results, "count": len(results)}

    async def handle_list_nearby(call: ServiceCall) -> ServiceResponse:
        # 등록 시점의 store를 캡처하지 않고 매번 조회 - 엔트리 리로드로 store가
        # 교체돼도 최신 지역/코디네이터를 읽는다.
        results = []
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_ENTRY_TYPE) != ENTRY_PHARMACY:
                continue
            store = hass.data.get(DOMAIN, {}).get(entry.entry_id)
            if not store:
                continue
            for i, region in enumerate(store.get("regions", [])):
                if not region.get("location_sensors"):
                    continue
                coord = store["coordinators"].get(i)
                if not coord:
                    continue
                loc = region.get("location") or {}
                home_lat = loc.get("latitude", hass.config.latitude)
                home_lon = loc.get("longitude", hass.config.longitude)
                radius = loc.get("radius", region.get("radius", 1000))
                nearby = pharmacies_within_radius(coord.data, home_lat, home_lon, radius)
                region_label = f"{region.get('sido', '')} {region.get('sgg', '')}".strip()
                for p in nearby:
                    try:
                        lat, lon = float(p["lat"]), float(p["lon"])
                    except (KeyError, TypeError, ValueError):
                        lat = lon = None
                    results.append({
                        "region": region_label,
                        "name": p.get("name", ""),
                        "address": p.get("address", ""),
                        "phone": p.get("phone", ""),
                        "latitude": lat,
                        "longitude": lon,
                    })
        return {"pharmacies": results, "count": len(results)}

    if not hass.services.has_service(DOMAIN, "search_pharmacy"):
        hass.services.async_register(
            DOMAIN, "search_pharmacy", handle_search,
            schema=vol.Schema({
                vol.Required("region"): str,
                vol.Optional("district", default=""): str,
                vol.Optional("count", default=10): vol.Coerce(int),
            }),
            supports_response=SupportsResponse.ONLY,
        )

    if not hass.services.has_service(DOMAIN, "list_nearby_pharmacies"):
        hass.services.async_register(
            DOMAIN, "list_nearby_pharmacies", handle_list_nearby,
            schema=vol.Schema({}),
            supports_response=SupportsResponse.ONLY,
        )
