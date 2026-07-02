"""Disaster message coordinator - resilient to intermittent SSL errors."""
from __future__ import annotations
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from . import DISASTER_SCAN_INTERVAL
from .api import fetch_disaster_messages
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)


class DisasterCoordinator(ResilientCoordinator):
    # safetydata.go.kr flaps often; a blip must not read as "no alerts".
    stale_tolerance = 5

    def __init__(self, hass, api_key, region_filter=""):
        super().__init__(hass, _LOGGER, name="disaster",
                         update_interval=timedelta(seconds=DISASTER_SCAN_INTERVAL))
        self._api_key = api_key
        self._region_filter = region_filter

    async def _fetch(self):
        all_msgs = await fetch_disaster_messages(self._api_key, count=30)
        if self._region_filter:
            return [m for m in all_msgs
                    if self._region_filter in (m.get("area") or "")]
        return all_msgs
