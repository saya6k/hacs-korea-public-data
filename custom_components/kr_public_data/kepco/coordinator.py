"""KEPCO coordinator - curl_cffi imported via executor to avoid blocking."""
from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from . import KEPCO_SCAN_INTERVAL
from .exceptions import KepcoAuthError
from ..exceptions import KrAuthError
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)


class KepcoCoordinator(ResilientCoordinator):
    stale_tolerance = 4

    def __init__(self, hass: HomeAssistant, username: str, password: str):
        super().__init__(hass, _LOGGER, name="kepco",
                         update_interval=timedelta(seconds=KEPCO_SCAN_INTERVAL))
        self._hass = hass
        self._username = username
        self._password = password
        self._session = None
        self._client = None

    async def _ensure_client(self):
        """Create curl_cffi session in executor to avoid blocking event loop."""
        if self._client is None:
            def _create_session():
                import curl_cffi
                return curl_cffi.AsyncSession()
            self._session = await self._hass.async_add_executor_job(_create_session)
            from .api import KepcoApiClient
            self._client = KepcoApiClient(self._session)

    async def async_login(self):
        await self._ensure_client()
        return await self._client.async_login(self._username, self._password)

    async def _fetch(self):
        await self._ensure_client()
        try:
            recent = await self._client.async_get_recent_usage()
            usage = await self._client.async_get_usage_info()
            return {"recent_usage": recent, "usage_info": usage}
        except Exception as e:
            # Session may have expired: one re-login attempt before giving up.
            try:
                if await self.async_login():
                    recent = await self._client.async_get_recent_usage()
                    usage = await self._client.async_get_usage_info()
                    return {"recent_usage": recent, "usage_info": usage}
            except KepcoAuthError as auth_err:
                raise KrAuthError(f"KEPCO login rejected: {auth_err}") from auth_err
            except Exception as retry_err:
                _LOGGER.debug("KEPCO retry failed: %s", retry_err)
            raise
