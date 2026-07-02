"""Fuel price coordinator - fetches for all configured sido/fuel combos."""
from __future__ import annotations
import logging
from datetime import timedelta
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from . import FUEL_SCAN_INTERVAL
from .api import fetch_avg_price, fetch_low_price
from ..exceptions import KrTransientError
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)


class FuelCoordinator(ResilientCoordinator):
    stale_tolerance = 6  # prices move on a daily cadence

    def __init__(self, hass: HomeAssistant, api_key: str,
                 configs: list[dict[str, str]]) -> None:
        super().__init__(hass, _LOGGER, name="fuel",
                         update_interval=timedelta(seconds=FUEL_SCAN_INTERVAL))
        self._api_key = api_key
        self._configs = configs  # [{"sido_code": ..., "fuel_code": ...}, ...]
        self._session = async_get_clientsession(hass)

    async def _fetch(self):
        result: dict[str, Any] = {}
        previous = self.data or {}
        failures = 0
        total = 1 + len(self._configs)
        # Average price (전국) - one call
        try:
            result["average"] = await fetch_avg_price(self._session, self._api_key)
        except Exception as e:
            failures += 1
            _LOGGER.warning("Fuel avg fetch error: %s", e)
            result["average"] = previous.get("average", [])

        # Low price per sido/fuel combo
        for cfg in self._configs:
            key = f"low_{cfg['sido_code']}_{cfg['fuel_code']}"
            try:
                result[key] = await fetch_low_price(
                    self._session, self._api_key, cfg["sido_code"], cfg["fuel_code"])
            except Exception as e:
                failures += 1
                _LOGGER.warning("Fuel low price fetch error %s: %s", key, e)
                result[key] = previous.get(key, [])

        if failures == total:
            raise KrTransientError("all fuel price fetches failed")
        return result
