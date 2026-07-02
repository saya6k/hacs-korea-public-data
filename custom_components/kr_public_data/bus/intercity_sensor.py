"""Intercity/express bus departure sensors - pure TIMESTAMP, no string values."""
from __future__ import annotations
from datetime import datetime
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from ..const import DOMAIN


class IntercityBusDepartureSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:bus-clock"

    def __init__(self, coordinator, dep_name: str, arr_name: str, grade_key: str, index: int, device_info):
        super().__init__(coordinator)
        self._grade_key = grade_key  # "source:gradeNm"
        self._idx = index
        suffix = "now" if index == 0 else "next"
        self._attr_unique_id = f"{DOMAIN}_intercity_bus_{dep_name}_{arr_name}_{grade_key}_{suffix}"
        self._attr_name = "다음 출발" if index == 0 else "다다음 출발"
        self._attr_device_info = device_info

    @property
    def _entry(self):
        items = (self.coordinator.data or {}).get(self._grade_key, [])
        if self._idx >= len(items):
            return None
        return items[self._idx]  # (datetime, raw_item)

    @property
    def native_value(self) -> datetime | None:
        entry = self._entry
        return entry[0] if entry else None

    @property
    def extra_state_attributes(self):
        entry = self._entry
        if entry is None:
            return {}
        _, raw = entry
        source = self._grade_key.split(":", 1)[0]
        attrs: dict = {"type": "고속버스" if source == "express" else "시외버스"}
        if raw.get("charge") is not None:
            attrs["fare"] = raw["charge"]
        if raw.get("arrPlandTime") is not None:
            attrs["scheduled_arrival"] = str(raw["arrPlandTime"])
        return attrs


class IntercityBusFareSensor(CoordinatorEntity, SensorEntity):
    """다음/다다음 출발편 요금 - 같은 등급이면 사실상 고정값이지만
    다음/다다음 사이에도 요금이 바뀌는 경우(성수기 등)를 대비해 각각 노출."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cash"
    _attr_native_unit_of_measurement = "원"

    def __init__(self, coordinator, dep_name: str, arr_name: str, grade_key: str,
                 index: int, device_info):
        super().__init__(coordinator)
        self._grade_key = grade_key
        self._idx = index
        suffix = "now" if index == 0 else "next"
        self._attr_unique_id = f"{DOMAIN}_intercity_bus_{dep_name}_{arr_name}_{grade_key}_fare_{suffix}"
        self._attr_name = "다음 요금" if index == 0 else "다다음 요금"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        items = (self.coordinator.data or {}).get(self._grade_key, [])
        if self._idx >= len(items):
            return None
        _, raw = items[self._idx]
        charge = raw.get("charge")
        return int(charge) if charge is not None else None
