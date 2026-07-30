"""Earthquake coordinator."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.kr_public_data.resilience import ResilientCoordinator

from . import SCAN_INTERVAL
from .api import fetch_earthquakes

_LOGGER = logging.getLogger(__name__)

class EarthquakeCoordinator(ResilientCoordinator[list[dict]]):
    stale_tolerance = 3

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        super().__init__(hass, _LOGGER, name="earthquake",
                         update_interval=timedelta(seconds=SCAN_INTERVAL))
        self._api_key = api_key
        self._session = async_get_clientsession(hass)

    async def _fetch(self) -> list[dict]:
        return await fetch_earthquakes(self._session, self._api_key)
