"""Bus arrival coordinator using KakaoMap API."""
from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .bus_api import fetch_stop_data, build_bus_dict
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)


class BusCoordinator(ResilientCoordinator):
    """One coordinator per bus stop - fetches from KakaoMap."""
    stale_tolerance = 2  # arrival times are useless once stale

    def __init__(self, hass: HomeAssistant, stop_id: str, stop_name: str) -> None:
        super().__init__(hass, _LOGGER, name=f"bus_{stop_id}",
                         update_interval=timedelta(seconds=90))
        self.stop_id = stop_id
        self.stop_name = stop_name
        self._session = async_get_clientsession(hass)

    async def _fetch(self):
        data = await fetch_stop_data(self._session, self.stop_id)
        return build_bus_dict(data)
