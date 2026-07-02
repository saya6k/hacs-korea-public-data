"""Seoul city bus arrival coordinator - one call already covers next+next-next."""
from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from . import CITY_BUS_SCAN_INTERVAL
from .seoul_api import fetch_stop_arrivals
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)

class SeoulBusCoordinator(ResilientCoordinator):
    """One coordinator per stop - keyed by busRouteId, no client-side sort needed."""
    stale_tolerance = 2  # arrival times are useless once stale

    def __init__(self, hass: HomeAssistant, api_key: str, ars_id: str,
                 route_ids: list[str]) -> None:
        super().__init__(hass, _LOGGER, name=f"seoul_bus_{ars_id}",
                         update_interval=timedelta(seconds=CITY_BUS_SCAN_INTERVAL))
        self._api_key = api_key
        self._ars_id = ars_id
        self._session = async_get_clientsession(hass)
        self.route_ids = route_ids  # [busRouteId, ...]

    async def _fetch(self):
        raw = await fetch_stop_arrivals(self._session, self._api_key, self._ars_id)
        return {item["busRouteId"]: item for item in raw
                if item.get("busRouteId") in self.route_ids}
