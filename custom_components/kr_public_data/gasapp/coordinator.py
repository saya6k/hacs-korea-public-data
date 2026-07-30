"""GasApp coordinator."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.kr_public_data.exceptions import KrAuthError
from custom_components.kr_public_data.resilience import ResilientCoordinator

from . import GASAPP_SCAN_INTERVAL
from .api import GasAppApiClient
from .exceptions import GasAppAuthError

_LOGGER = logging.getLogger(__name__)

class GasAppCoordinator(ResilientCoordinator):
    stale_tolerance = 4  # monthly gas bill data

    def __init__(self, hass: HomeAssistant, token: str, member_id: str,
                 contract_num: str) -> None:
        super().__init__(hass, _LOGGER, name="gasapp",
                         update_interval=timedelta(seconds=GASAPP_SCAN_INTERVAL))
        self.client = GasAppApiClient(async_get_clientsession(hass))
        self.client.set_credentials(token, member_id, contract_num)
        self._contract_num = contract_num

    async def _fetch(self) -> dict[str, Any]:
        try:
            home = await self.client.async_get_home_data()
            bill = await self.client.async_get_current_bill()
        except GasAppAuthError as err:
            raise KrAuthError(f"GasApp token rejected: {err}") from err
        return {"home_data": home, "current_bill": bill}
