"""Subway device helpers."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import (
    ChildDeviceInfo,
    DeviceEntryType,
    DeviceInfo,
)

from custom_components.kr_public_data.const import DOMAIN

from . import SUBWAY_LINES


def subway_station_key(station: str) -> str:
    """Identifier of the 역 hub device, also the prefix of its own entity's unique_id."""
    return f"subway_station_{station}"


def subway_station_device(station: str) -> DeviceInfo:
    """The 역 hub: main device carrying the station's line child devices."""
    return DeviceInfo(
        identifiers={(DOMAIN, subway_station_key(station))},
        translation_key="subway_station",
        translation_placeholders={"station": station},
        manufacturer="서울교통공사", model="지하철역",
        entry_type=DeviceEntryType.SERVICE,
    )


@callback
def subway_station_device_id(hass: HomeAssistant, entry: ConfigEntry, sub_id: str | None,
                             station: str) -> str:
    """Register the 역 hub device and return its id, for use as parent_device_id.

    Registered here rather than left to the entity platform because the id must
    be known *before* the line child devices that reference it are built.
    """
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=sub_id,
        **subway_station_device(station),
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


def subway_line_device(station: str, line_id: str,
                       parent_device_id: str) -> ChildDeviceInfo:
    """One child device per (station, line); both directions live under it.

    Identifiers are unchanged from when this was a main device, so HA converts
    existing entries in place and device ids (and the automations pointing at
    them) survive. A child device carries no manufacturer/model/entry_type —
    those live on the 역 hub.
    """
    ln = SUBWAY_LINES.get(line_id, line_id)
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"subway_{station}_{line_id}")},
        translation_key="subway_line",
        translation_placeholders={"station": station, "line": ln},
        parent_device_id=parent_device_id,
    )
