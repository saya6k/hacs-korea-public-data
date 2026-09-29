"""Base tool class for kr_public_data LLM tools."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from custom_components.kr_public_data.const import DOMAIN

from .const import SOURCE

_LOGGER = logging.getLogger(__name__)


class BaseKRTool(llm.Tool):
    """Reads its bound config entry's coordinator data via hass.data."""

    integration = DOMAIN
    annotations = llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )

    service: str = ""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        super().__init__()
        self.hass = hass
        self.entry_id = entry_id

    @property
    def store(self) -> dict[str, Any]:
        return self.hass.data.get(DOMAIN, {}).get(self.entry_id, {})

    def envelope(self, **fields: Any) -> llm.ToolResult:
        """Build a standard response envelope for tools without a card UI."""
        out: dict[str, Any] = {"source": SOURCE, "service": self.service}
        out.update(fields)
        return llm.ToolResult(data=out)

    def error(self, message: str) -> llm.ToolResult:
        return llm.ToolResult(
            data={"source": SOURCE, "service": self.service, "error": message},
            error=True,
        )
