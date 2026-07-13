"""Opt-in LLM API registration for kr_public_data.

One llm.API is registered per added config entry, so each service instance
appears as a discrete, user-selectable tool source in a conversation agent's
LLM API settings — kr_public_data tools are never contributed to the shared
Assist API automatically.

This module must stay a thin shell and never import the `llm/` platform
package (or any tool module) at module level: `__init__.py` imports this
file at every entry setup, and pulling `llm/` in here would defeat its lazy
loading (see `llm/__init__.py`). The one call that needs
`homeassistant.components.llm` — the platform aggregator — is deferred into
`async_get_api_instance`, which only ever runs once a conversation agent has
resolved this API instance, by which point HA's own `llm` integration is
already loaded and the import is a cache hit.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm

from .const import (
    DOMAIN,
    ENTRY_AIRKOREA,
    ENTRY_ARISU,
    ENTRY_BUS,
    ENTRY_DISASTER,
    ENTRY_EARTHQUAKE,
    ENTRY_FUEL,
    ENTRY_GASAPP,
    ENTRY_KEPCO,
    ENTRY_KMA_WEATHER,
    ENTRY_PHARMACY,
    ENTRY_SAFETY_ALERT,
    ENTRY_SCHOOL,
    ENTRY_TRANSIT,
    ENTRY_WEATHER,
)

_LOGGER = logging.getLogger(__name__)

API_NAMES: dict[str, str] = {
    ENTRY_KMA_WEATHER: "한국 공공데이터: 기상청 날씨",
    ENTRY_WEATHER: "한국 공공데이터: 기상특보",
    ENTRY_AIRKOREA: "한국 공공데이터: 대기질",
    ENTRY_TRANSIT: "한국 공공데이터: 대중교통",
    ENTRY_FUEL: "한국 공공데이터: 유가정보",
    ENTRY_SCHOOL: "한국 공공데이터: 학교 급식·시간표",
    ENTRY_DISASTER: "한국 공공데이터: 재난문자",
    ENTRY_SAFETY_ALERT: "한국 공공데이터: 안전디딤돌 경보",
    ENTRY_KEPCO: "한국 공공데이터: 한전 전기 사용량",
    ENTRY_GASAPP: "한국 공공데이터: 도시가스 요금",
    ENTRY_ARISU: "한국 공공데이터: 아리수 수도 요금",
    ENTRY_PHARMACY: "한국 공공데이터: 운영중인 약국",
    ENTRY_EARTHQUAKE: "한국 공공데이터: 최근 지진",
    ENTRY_BUS: "한국 공공데이터: 버스 도착정보",
}


class _ServiceAPI(llm.API):
    """An llm.API bound to a single config entry of a given service type."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, etype: str) -> None:
        super().__init__(
            hass=hass,
            id=f"{DOMAIN}__{etype}__{entry.entry_id}",
            name=API_NAMES[etype],
        )

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        """Return the instance of the API."""
        from homeassistant.components.llm import (  # noqa: PLC0415
            async_get_tools as async_get_platform_tools,
        )

        llm_tools = await async_get_platform_tools(self.hass, llm_context, self.id)
        return llm.APIInstance(
            api=self,
            api_prompt=llm_tools.prompt or "",
            llm_context=llm_context,
            tools=llm_tools.tools,
        )


@callback
def async_register_llm_api(hass: HomeAssistant, entry: ConfigEntry, etype: str) -> None:
    """Register this entry's LLM API; auto-unregisters on unload."""
    if etype not in API_NAMES:
        return
    api = _ServiceAPI(hass, entry, etype)
    entry.async_on_unload(llm.async_register_api(hass, api))
    _LOGGER.debug("Registered LLM API %s", api.id)
