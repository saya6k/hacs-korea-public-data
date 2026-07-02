"""GasApp coordinator."""
from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from . import GASAPP_SCAN_INTERVAL
from .api import GasAppApiClient
from .exceptions import GasAppAuthError
from ..exceptions import KrAuthError
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)

class GasAppCoordinator(ResilientCoordinator):
    stale_tolerance = 4  # monthly gas bill data

    def __init__(self, hass, token, member_id, contract_num):
        super().__init__(hass, _LOGGER, name="gasapp",
                         update_interval=timedelta(seconds=GASAPP_SCAN_INTERVAL))
        self.client = GasAppApiClient(async_get_clientsession(hass))
        self.client.set_credentials(token, member_id, contract_num)
        self._contract_num = contract_num

    async def _fetch(self):
        try:
            home = await self.client.async_get_home_data()
            bill = await self.client.async_get_current_bill()
        except GasAppAuthError as err:
            raise KrAuthError(f"GasApp token rejected: {err}") from err
        return {"home_data": home, "current_bill": bill}
