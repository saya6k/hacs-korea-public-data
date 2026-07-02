"""Arisu coordinator."""
from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from . import ARISU_SCAN_INTERVAL
from .api import ArisuApiClient
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)

class ArisuCoordinator(ResilientCoordinator):
    stale_tolerance = 4  # monthly water bill data

    def __init__(self, hass, customer_number, customer_name):
        super().__init__(hass, _LOGGER, name="arisu",
                         update_interval=timedelta(seconds=ARISU_SCAN_INTERVAL))
        self.client = ArisuApiClient(async_get_clientsession(hass))
        self._num = customer_number
        self._name = customer_name

    async def _fetch(self):
        return await self.client.async_get_water_bill_data(self._num, self._name)
