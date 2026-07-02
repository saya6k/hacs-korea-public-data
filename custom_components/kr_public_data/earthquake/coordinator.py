"""Earthquake coordinator."""
from __future__ import annotations
import logging
from datetime import timedelta
import aiohttp
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

    async def _fetch(self):
        async with aiohttp.ClientSession() as session:
            return await fetch_earthquakes(session, self._api_key)
