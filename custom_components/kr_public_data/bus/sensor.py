"""City bus sensors - pure TIMESTAMP, no string values."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from ..const import DOMAIN

KST = timezone(timedelta(hours=9))


class CityBusArrivalSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:bus-clock"

    def __init__(self, coordinator, node_id: str, route_id: str, index: int, device_info):
        super().__init__(coordinator)
        self._route_id = route_id
        self._idx = index
        suffix = "now" if index == 0 else "next"
        self._attr_unique_id = f"{DOMAIN}_city_bus_{node_id}_{route_id}_{suffix}"
        self._attr_name = "다음 도착" if index == 0 else "다다음 도착"
        self._attr_device_info = device_info

    @property
    def _item(self) -> dict | None:
        items = (self.coordinator.data or {}).get(self._route_id, [])
        if self._idx >= len(items):
            return None
        return items[self._idx]

    @property
    def native_value(self) -> datetime | None:
        item = self._item
        if item is None:
            return None
        arrtime = item.get("arrtime")
        if arrtime is None:
            return None
        return datetime.now(KST) + timedelta(seconds=int(arrtime))

    @property
    def extra_state_attributes(self):
        item = self._item
        if item is None:
            return {}
        attrs: dict = {}
        if item.get("arrprevstationcnt") is not None:
            attrs["remaining_stops"] = item["arrprevstationcnt"]
        if item.get("vehicletp"):
            attrs["vehicle_type"] = item["vehicletp"]
        arrtime = item.get("arrtime")
        if arrtime is not None:
            arrtime = int(arrtime)
            if arrtime <= 60:
                attrs["status"] = "곧 도착"
            elif arrtime > 0:
                attrs["status"] = f"{arrtime // 60}분 후"
        return attrs
