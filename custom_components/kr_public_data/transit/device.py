"""Subway device helpers."""
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from ..const import DOMAIN
from . import SUBWAY_LINES


def subway_device(station, direction, line_id=""):
    """Legacy per-(station, direction, line) device."""
    ln = SUBWAY_LINES.get(line_id, "")
    label = f"지하철 - {station}역 {ln} {direction}".strip()
    did = f"subway_{station}_{direction}_{line_id}"
    return DeviceInfo(identifiers={(DOMAIN, did)}, name=label,
                      manufacturer="서울교통공사", model="실시간 도착정보",
                      entry_type=DeviceEntryType.SERVICE)


def subway_line_device(station, line_id):
    """One device per (station, line); both directions live under it."""
    ln = SUBWAY_LINES.get(line_id, line_id)
    return DeviceInfo(
        identifiers={(DOMAIN, f"subway_{station}_{line_id}")},
        name=f"지하철 - {station}역 {ln}",
        manufacturer="서울교통공사", model="실시간 도착정보",
        entry_type=DeviceEntryType.SERVICE,
    )
