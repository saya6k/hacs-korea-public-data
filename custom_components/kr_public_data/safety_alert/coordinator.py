"""Safety Alert coordinator."""
from __future__ import annotations
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from . import SAFETY_SCAN_INTERVAL
from .api import SafetyAlertApiClient
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)


class SafetyAlertCoordinator(ResilientCoordinator):
    # Keep serving the last alerts through blips (a blip must not read as
    # "all clear"), but surface sustained failure honestly.
    stale_tolerance = 4

    def __init__(self, hass, area_code):
        super().__init__(hass, _LOGGER, name=f"safety_alert_{area_code}",
                         update_interval=timedelta(seconds=SAFETY_SCAN_INTERVAL))
        self._area_code = area_code

    async def _fetch(self):
        client = SafetyAlertApiClient()
        result = await client.async_get_safety_alerts(self._area_code)
        alerts = result.get("disasterSmsList", [])
        rtn = result.get("rtnResult", {})
        count = rtn.get("totCnt", len(alerts)) if isinstance(rtn, dict) else len(alerts)
        return {"alerts": alerts, "count": count, "has_data": len(alerts) > 0}
