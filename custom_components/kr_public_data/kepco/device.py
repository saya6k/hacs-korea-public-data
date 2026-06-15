"""KEPCO device."""
from __future__ import annotations
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from ..const import DOMAIN

def kepco_device_info(username: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"kepco_{username}")},
        name=f"한전 ({username})",
        manufacturer="한국전력공사",
        model="KEPCO",
        entry_type=DeviceEntryType.SERVICE,
    )
