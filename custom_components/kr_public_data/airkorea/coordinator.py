"""AirKorea coordinator."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.kr_public_data.exceptions import KrTransientError
from custom_components.kr_public_data.resilience import ResilientCoordinator

from . import SCAN_INTERVAL, SIDO_AREA_CODE
from .api import fetch_air_stagnation, fetch_forecast, fetch_realtime, fetch_uv_index

_LOGGER = logging.getLogger(__name__)


class AirKoreaCoordinator(ResilientCoordinator):
    stale_tolerance = 4

    def __init__(self, hass: HomeAssistant, api_key: str, stations: list[dict[str, Any]],
                 living_api_key: str = "", sido: str = "") -> None:
        super().__init__(hass, _LOGGER, name="airkorea",
                         update_interval=timedelta(seconds=SCAN_INTERVAL))
        self._api_key = api_key
        self._stations = stations
        self._living_key = living_api_key or api_key
        self._area_code = SIDO_AREA_CODE.get(sido, "1100000000")
        self._session = async_get_clientsession(hass)

    async def _fetch(self) -> dict[str, Any]:
        result = {"stations": {}, "forecast": [], "uv": {}, "stagnation": {}}
        previous = self.data or {}
        station_failures = 0
        session = self._session
        for st in self._stations:
            name = st["stationName"]
            try:
                result["stations"][name] = await fetch_realtime(
                    session, self._api_key, name)
            except Exception as e:
                station_failures += 1
                _LOGGER.warning("AirKorea realtime %s: %s", name, e)
                prev_station = (previous.get("stations") or {}).get(name)
                if prev_station:
                    result["stations"][name] = prev_station
        try:
            result["forecast"] = await fetch_forecast(session, self._api_key)
        except Exception as e:
            _LOGGER.warning("AirKorea forecast: %s", e)
            result["forecast"] = previous.get("forecast", [])
        # Living indices - shared for the region
        try:
            result["uv"] = await fetch_uv_index(
                session, self._living_key, self._area_code)
        except Exception as e:
            _LOGGER.debug("AirKorea UV index failed: %s", e)
        try:
            result["stagnation"] = await fetch_air_stagnation(
                session, self._living_key, self._area_code)
        except Exception as e:
            _LOGGER.debug("AirKorea stagnation failed: %s", e)
        # If every station failed and forecast is empty, surface the failure
        if self._stations and station_failures == len(self._stations) and not result["forecast"]:
            raise KrTransientError("AirKorea: all station and forecast fetches failed")
        return result
