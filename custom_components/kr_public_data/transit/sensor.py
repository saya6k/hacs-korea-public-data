"""Subway sensors - pure TIMESTAMP, no string values."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from ..const import DOMAIN

KST = timezone(timedelta(hours=9))

class SubwayArrivalSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:subway-variant"

    def __init__(self, coordinator, station, direction, line_id, index,
                 device_info, name_prefix=""):
        super().__init__(coordinator)
        self._key = f"{direction}_{line_id or ''}"
        self._idx = index
        suffix = "now" if index == 0 else "next"
        self._attr_unique_id = f"{DOMAIN}_subway_{station}_{direction}_{line_id}_{suffix}"
        base = "다음 열차" if index == 0 else "다다음 열차"
        # Per-line devices hold both directions, so the direction goes into
        # the name; legacy per-direction devices keep the bare name.
        self._attr_name = f"{name_prefix} {base}".strip()
        self._attr_device_info = device_info

    @property
    def native_value(self) -> datetime | None:
        items = (self.coordinator.data or {}).get(self._key, [])
        if self._idx >= len(items):
            return None
        return items[self._idx].get("arrival_time")

    @property
    def extra_state_attributes(self):
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
