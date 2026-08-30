"""Subway device helpers."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from custom_components.kr_public_data.const import DOMAIN

from . import SUBWAY_LINES


@callback
def subway_station_device_id(hass: HomeAssistant, entry: ConfigEntry, sub_id: str | None,
                             station: str) -> str:
    """Register the 역 hub device and return its id, for use as via_device_id.

    The hub holds no entities of its own — it exists so every line at the station
    nests under one device. It has to be registered here rather than handed to the
    entity platform as a DeviceInfo, because its id must be known *before* the
    line devices that reference it are built.
    """
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=sub_id,
        identifiers={(DOMAIN, f"subway_station_{station}")},
        translation_key="subway_station",
        translation_placeholders={"station": station},
        manufacturer="서울교통공사", model="지하철역",
        entry_type=DeviceEntryType.SERVICE,
    ).id


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


def subway_line_device(station: str, line_id: str, via_device_id: str) -> DeviceInfo:
    """One device per (station, line); both directions live under it."""
    ln = SUBWAY_LINES.get(line_id, line_id)
    return DeviceInfo(
        identifiers={(DOMAIN, f"subway_{station}_{line_id}")},
        translation_key="subway_line",
        translation_placeholders={"station": station, "line": ln},
        manufacturer="서울교통공사", model="실시간 도착정보",
        entry_type=DeviceEntryType.SERVICE,
        via_device_id=via_device_id,
    )
