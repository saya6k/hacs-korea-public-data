"""LLM tools platform for kr_public_data.

Home Assistant's `llm` integration discovers a `<domain>/llm` platform for
every loaded top-level component and aggregates their tools/prompts (see
`homeassistant.components.llm.async_get_tools`, which drives
`homeassistant.helpers.integration_platform.LazyIntegrationPlatforms` — this
module is only imported the first time an LLM request actually needs it, not
at kr_public_data setup). `async_get_tools` is the hook contract; we respond
only to requests for our own per-entry API ids (see `..llm_api`), never
`assist` or any other integration's API, so these tools only ever surface
through a user-selected "한국 공공데이터: ..." API.
"""
from __future__ import annotations

from homeassistant.components.llm import LLMTools
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.llm import LLMContext

from ..const import CONF_ENTRY_TYPE, DOMAIN
from .const import API_PROMPTS
from .tools import TOOLS_BY_ETYPE

_API_ID_PREFIX = f"{DOMAIN}__"


@callback
def async_get_tools(hass: HomeAssistant, llm_context: LLMContext, api_id: str) -> LLMTools | None:
    """Return this entry's kr_public_data tools, or None for any other API id."""
    if not api_id.startswith(_API_ID_PREFIX):
        return None

    etype, sep, entry_id = api_id[len(_API_ID_PREFIX):].partition("__")
    if not sep:
        return None

    entry = hass.config_entries.async_get_entry(entry_id)
    if (
        entry is None
        or entry.state is not ConfigEntryState.LOADED
        or entry.data.get(CONF_ENTRY_TYPE) != etype
    ):
        # Unknown id, entry unloaded since the API was requested, or the
        # etype in the id no longer matches (e.g. after a reconfigure).
        return None

    factories = TOOLS_BY_ETYPE.get(etype)
    if not factories:
        return None

    tools = [factory(hass, entry_id) for factory in factories]
    return LLMTools(tools=tools, prompt=API_PROMPTS[etype])
