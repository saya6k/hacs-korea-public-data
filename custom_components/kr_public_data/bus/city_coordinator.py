"""City bus arrival coordinator - uses bulk API, shared per stop."""
from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from . import CITY_BUS_SCAN_INTERVAL
from .api import fetch_stop_arrivals
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)

class CityBusCoordinator(ResilientCoordinator):
    """One coordinator per stop - fetches bulk, filters per selected route."""
    stale_tolerance = 2  # arrival times are useless once stale

    def __init__(self, hass: HomeAssistant, api_key: str, city_code: int,
                 node_id: str, route_ids: list[str]) -> None:
        super().__init__(hass, _LOGGER, name=f"city_bus_{node_id}",
                         update_interval=timedelta(seconds=CITY_BUS_SCAN_INTERVAL))
        self._api_key = api_key
        self._city_code = city_code
        self._node_id = node_id
        self._session = async_get_clientsession(hass)
        self.route_ids = route_ids  # [routeId, ...]

    async def _fetch(self):
        raw = await fetch_stop_arrivals(self._session, self._api_key,
                                         self._city_code, self._node_id)
        result = {}
        for route_id in self.route_ids:
            matched = [a for a in raw if a.get("routeid") == route_id]
            matched.sort(key=lambda a: int(a.get("arrtime") or 0))
            result[route_id] = matched[:2]
        return result
