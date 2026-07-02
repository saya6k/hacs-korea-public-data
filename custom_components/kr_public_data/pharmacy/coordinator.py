"""Pharmacy coordinator."""
from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from . import PHARMACY_SCAN_INTERVAL
from .api import fetch_pharmacies
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)

class PharmacyCoordinator(ResilientCoordinator):
    stale_tolerance = 6  # opening hours change daily at most

    def __init__(self, hass, api_key, q0, q1=""):
        super().__init__(hass, _LOGGER, name="pharmacy",
                         update_interval=timedelta(seconds=PHARMACY_SCAN_INTERVAL))
        self._api_key = api_key
        self._q0 = q0
        self._q1 = q1
        self._session = async_get_clientsession(hass)

    async def _fetch(self):
        return await fetch_pharmacies(self._session, self._api_key, self._q0, self._q1)
