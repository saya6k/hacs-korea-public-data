"""Safety Alert coordinator."""
from __future__ import annotations
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from . import SAFETY_SCAN_INTERVAL
from .api import SafetyAlertApiClient

_LOGGER = logging.getLogger(__name__)


class SafetyAlertCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass, area_code):
        super().__init__(hass, _LOGGER, name=f"safety_alert_{area_code}",
                         update_interval=timedelta(seconds=SAFETY_SCAN_INTERVAL))
        self._area_code = area_code

    async def _async_update_data(self):
        client = SafetyAlertApiClient()
        try:
            result = await client.async_get_safety_alerts(self._area_code)
            alerts = result.get("disasterSmsList", [])
            count = result.get("rtnResult", {}).get("totCnt", 0)
            return {"alerts": alerts, "count": count, "has_data": len(alerts) > 0}
        except Exception as e:
            raise UpdateFailed(f"Safety alert error: {e}") from e
