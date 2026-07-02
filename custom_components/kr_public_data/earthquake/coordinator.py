"""Earthquake coordinator."""
from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from . import SCAN_INTERVAL
from .api import fetch_earthquakes
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)

class EarthquakeCoordinator(ResilientCoordinator):
    stale_tolerance = 3

    def __init__(self, hass, api_key):
        super().__init__(hass, _LOGGER, name="earthquake",
                         update_interval=timedelta(seconds=SCAN_INTERVAL))
        self._api_key = api_key
        self._session = async_get_clientsession(hass)

    async def _fetch(self):
        return await fetch_earthquakes(self._session, self._api_key)
