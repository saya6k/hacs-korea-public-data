"""Seoul city bus sensors - pure TIMESTAMP, no string values."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from ..const import DOMAIN

KST = timezone(timedelta(hours=9))


class SeoulBusArrivalSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:bus-clock"

    def __init__(self, coordinator, ars_id: str, route_id: str, index: int, device_info):
        super().__init__(coordinator)
        self._route_id = route_id
        self._idx = index
        suffix = "now" if index == 0 else "next"
        self._attr_unique_id = f"{DOMAIN}_seoul_bus_{ars_id}_{route_id}_{suffix}"
        self._attr_name = "다음 도착" if index == 0 else "다다음 도착"
        self._attr_device_info = device_info

    @property
    def _item(self) -> dict | None:
        return (self.coordinator.data or {}).get(self._route_id)

    @property
    def native_value(self) -> datetime | None:
        item = self._item
        if item is None:
            return None
        n = self._idx + 1
        if not item.get(f"vehId{n}"):
            return None
        try:
            seconds = int(item.get(f"traTime{n}") or "")
        except (TypeError, ValueError):
            return None
        return datetime.now(KST) + timedelta(seconds=seconds)

    @property
    def extra_state_attributes(self):
        item = self._item
        if item is None:
            return {}
        n = self._idx + 1
        attrs: dict = {}
        if item.get("adirection"):
            attrs["direction"] = item["adirection"]
        if item.get(f"arrmsg{n}"):
            attrs["status"] = item[f"arrmsg{n}"]
        congestion = item.get(f"congestion{n}")
        if congestion and congestion != "0":
            attrs["congestion"] = congestion
        return attrs
