"""Subway sensors - pure TIMESTAMP, no string values."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.kr_public_data.const import DOMAIN

from . import DIRECTION_SLUGS, SUBWAY_LINES, line_directions

if TYPE_CHECKING:
    from .subway_coordinator import SubwayCoordinator

KST = timezone(timedelta(hours=9))

class SubwayArrivalSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:subway-variant"

    def __init__(self, coordinator: SubwayCoordinator, station: str, direction: str,
                 line_id: str, index: int,
                 device_info: DeviceInfo | ChildDeviceInfo, name_prefix: str = "") -> None:
        super().__init__(coordinator)
        self._key = f"{direction}_{line_id or ''}"
        self._idx = index
        suffix = "now" if index == 0 else "next"
        self._attr_unique_id = f"{DOMAIN}_subway_{station}_{direction}_{line_id}_{suffix}"
        # Per-line devices hold both directions, so the direction goes into the
        # name; legacy per-direction devices keep the bare name. Direction is a
        # fixed 4-value set, so it gets folded into the key instead of riding in
        # as a placeholder — that way it is localized too.
        slug = DIRECTION_SLUGS.get(name_prefix, "")
        self._attr_translation_key = f"subway_{slug}_{suffix}" if slug else f"subway_{suffix}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> datetime | None:
        items = (self.coordinator.data or {}).get(self._key, [])
        if self._idx >= len(items):
            return None
        return items[self._idx].get("arrival_time")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = (self.coordinator.data or {}).get(self._key, [])
        if self._idx >= len(items):
            return {}
        item = items[self._idx]
        attrs = {k: v for k, v in item.items() if k != "arrival_time" and v}
        dt = item.get("arrival_time")
        if dt:
            remaining = (dt - datetime.now(KST)).total_seconds()
            if remaining <= 60:
                attrs["status"] = "곧 도착"
            elif remaining > 0:
                attrs["status"] = f"{int(remaining // 60)}분 후"
        return attrs


class SubwayStationLineSensor(CoordinatorEntity, SensorEntity):
    """역 허브의 유일한 엔티티 - 지금 열차가 잡히는 호선 수 + 호선 목록.

    한 호선은 방향별 키(`{direction}_{line_id}`)로 나뉘어 들어오므로,
    어느 방향이든 도착 데이터가 있으면 그 호선은 운행 중으로 본다.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:subway-variant"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "subway_station_lines"

    def __init__(self, coordinator: SubwayCoordinator, station_key: str,
                 lines: list[str], device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._lines = lines
        self._attr_unique_id = f"{DOMAIN}_{station_key}_lines"
        self._attr_device_info = device_info

    def _running(self) -> list[str]:
        """도착 데이터가 실제로 있는 호선명. 운행 종료 후에는 빈 리스트다."""
        data = self.coordinator.data or {}
        return sorted(
            SUBWAY_LINES.get(lid, lid)
            for lid in self._lines
            if any(data.get(f"{d}_{lid}") for d in line_directions(lid))
        )

    @property
    def native_value(self) -> int:
        return len(self._running())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "lines": self._running(),
            "all_lines": sorted(SUBWAY_LINES.get(lid, lid) for lid in self._lines),
        }
