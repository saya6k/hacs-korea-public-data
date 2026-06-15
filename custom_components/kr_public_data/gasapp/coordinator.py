"""GasApp coordinator."""
from __future__ import annotations
import logging
from datetime import timedelta
from typing import Any
import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from . import GASAPP_SCAN_INTERVAL
from .api import GasAppApiClient

_LOGGER = logging.getLogger(__name__)

class GasAppCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass, token, member_id, contract_num):
        super().__init__(hass, _LOGGER, name="gasapp",
                         update_interval=timedelta(seconds=GASAPP_SCAN_INTERVAL))
        self._session = aiohttp.ClientSession()
        self.client = GasAppApiClient(self._session)
        self.client.set_credentials(token, member_id, contract_num)
        self._contract_num = contract_num

    async def _async_update_data(self):
        try:
            home = await self.client.async_get_home_data()
            bill = await self.client.async_get_current_bill()
            return {"home_data": home, "current_bill": bill}
        except Exception as e:
            raise UpdateFailed(f"GasApp error: {e}") from e
