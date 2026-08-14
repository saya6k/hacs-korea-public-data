"""Subway device helpers."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from custom_components.kr_public_data.const import DOMAIN

from . import SUBWAY_LINES


def subway_device(station: str, direction: str, line_id: str = "") -> DeviceInfo:
    """Legacy per-(station, direction, line) device."""
    ln = SUBWAY_LINES.get(line_id, "")
    did = f"subway_{station}_{direction}_{line_id}"
    return DeviceInfo(identifiers={(DOMAIN, did)},
                      translation_key="subway_direction",
                      translation_placeholders={"station": station, "line": ln,
                                                "direction": direction},
                      manufacturer="서울교통공사", model="실시간 도착정보",
                      entry_type=DeviceEntryType.SERVICE)


def subway_line_device(station: str, line_id: str) -> DeviceInfo:
    """One device per (station, line); both directions live under it."""
    ln = SUBWAY_LINES.get(line_id, line_id)
    return DeviceInfo(
        identifiers={(DOMAIN, f"subway_{station}_{line_id}")},
        translation_key="subway_line",
        translation_placeholders={"station": station, "line": ln},
        manufacturer="서울교통공사", model="실시간 도착정보",
        entry_type=DeviceEntryType.SERVICE,
    )
