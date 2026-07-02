"""Subway arrival coordinator - uses bulk API, shared per station."""
from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from . import SUBWAY_SCAN_INTERVAL
from .subway_api import fetch_bulk_arrivals, filter_arrivals
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)

class SubwayCoordinator(ResilientCoordinator):
    """One coordinator per station - fetches bulk, filters per direction/line."""
    stale_tolerance = 2  # arrival times are useless once stale

    def __init__(self, hass: HomeAssistant, api_key: str, station: str,
                 subscriptions: list[dict]) -> None:
        super().__init__(hass, _LOGGER, name=f"subway_{station}",
                         update_interval=timedelta(seconds=SUBWAY_SCAN_INTERVAL))
        self._api_key = api_key
        self._station = station
        self._session = async_get_clientsession(hass)
        self.subscriptions = subscriptions  # [{"direction": ..., "line_id": ...}, ...]

    async def _fetch(self):
        raw = await fetch_bulk_arrivals(self._session, self._api_key, self._station)
        result = {}
        for sub in self.subscriptions:
            direction = sub.get("direction")
            if not direction:
                continue
            key = f"{direction}_{sub.get('line_id', '')}"
            result[key] = filter_arrivals(raw, direction, sub.get("line_id"))
        return result
